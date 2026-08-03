"""
文章异步任务服务（LangGraph 编排版，仅负责启停/恢复）

职责已收窄为「创建/启动任务、恢复任务、持有 Task 引用防 GC、失败兜底」：
  - start(task_id, topic, style): 建初始 state → ainvoke 跑到第一个 interrupt
       （confirm_title 后：标题已落库 + TITLE_GENERATED 已发，等用户确认标题）
  - resume(task_id, inject): 注入人工输入（确认标题后的 title/description、确认大纲后的 outline）
       → aupdate_state + ainvoke(None) 续跑到下一个 interrupt 或 END
  - register_task: 保存 asyncio.Task 引用，避免被 GC 中断（修复原 # FIXME）
  - _handle_failure: 节点异常冒泡到此 → 标记 FAILED + 推 ERROR + 关闭 SSE（容错边界）

成功路径的全部副作用（update_article_status / update_phase / save_title_options /
save_outline / save_article_content / send_sse_message / sse complete）均已收入图节点
（bootstrap / confirm_title / confirm_outline / finalize），本类不再 inline 做这些。
图状态用 SQLite checkpointer 持久化（thread_id = taskId），取代原手工 checkpoint。
"""
import asyncio
from typing import Any, Dict, Optional

from app.database import database
from app.graph.builder import build_article_graph
from app.graph.checkpointer import get_checkpointer
from app.graph.sse_bridge import send_sse_message
from app.managers.sse_manager import sse_emitter_manager
from app.models.enums import ArticleStatusEnum, SseMessageTypeEnum
from app.services.article_service import ArticleService
from app.services.model_usage_service import usage_context, usage_recorder
from app.utils.logger import logger


class ArticleAsyncService:
    """文章异步任务服务：仅负责启停/恢复/失败兜底，成功路径副作用全在图节点里。"""

    def __init__(self) -> None:
        self._graph = None  # 已编译图单例，懒构造（需 lifespan 已 init checkpointer）
        # 持有异步任务引用，避免被 Python GC 回收（修复原 # FIXME）
        self._tasks: Dict[str, asyncio.Task] = {}

    # ==================== 图与 checkpointer 单例 ====================

    def _get_graph(self):
        """惰性构造已编译图单例（注入 checkpointer）"""
        if self._graph is None:
            self._graph = build_article_graph(get_checkpointer())
        return self._graph

    @staticmethod
    def _config(task_id: str) -> Dict[str, Any]:
        """LangGraph 配置：thread_id = taskId，checkpointer 按此隔离各文章状态

        Returns:
            - {"configurable": {"thread_id": task_id}}
        """
        return {"configurable": {"thread_id": task_id}}

    # ==================== AsyncTask 引用管理（GC 修复） ====================

    def register_task(self, task_id: str, task: asyncio.Task) -> asyncio.Task:
        """注册异步任务引用，完事后自动清理。在路由层调，避免 Task 被 GC。"""
        self._tasks[task_id] = task
        task.add_done_callback(lambda _t: self._tasks.pop(task_id, None))
        return task

    # ==================== 启动：建初始 state 跑到第一个 interrupt ====================

    async def start(
        self,
        task_id: str,
        topic: str,
        genre: Optional[str] = None,
        language_style: Optional[str] = None,
        word_count: Optional[int] = None,
        enabled_image_methods: Optional[list] = None,
        style: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> None:
        """启动文章生成：建初始 state → ainvoke 跑到 confirm_title 后 interrupt

        bootstrap 节点标记 PROCESSING + TITLE_GENERATING（新闻题材经条件边先过信息采集），
        generate_title 节点生成标题方案，confirm_title 节点落库 + 发 TITLE_GENERATED，随后图暂停等用户确认标题。
        本方法不做任何 DB/SSE 副作用（全在节点里），失败走 _handle_failure。
        """
        logger.info(
            "启动文章生成任务, taskId=%s, topic=%s, genre=%s, wordCount=%s",
            task_id, topic, genre, word_count,
        )
        try:
            initial_state: Dict[str, Any] = {
                "task_id": task_id,
                "topic": topic,
                "genre": genre,
                "language_style": language_style,
                "word_count": word_count,
                "enabled_image_methods": enabled_image_methods,
                "style": style,
            }
            graph = self._get_graph()
            with usage_context(task_id=task_id, user_id=user_id):
                await graph.ainvoke(initial_state, self._config(task_id))
            # 跑到 confirm_title 后暂停：标题已落库 + TITLE_GENERATED 已发，无需在此做事
        except Exception as e:
            await self._handle_failure(task_id, e)

    # ==================== 恢复：注入人工输入续跑到下一个 interrupt 或 END ====================

    async def resume(self, task_id: str, inject: Optional[dict] = None, user_id: Optional[int] = None) -> None:
        """恢复文章生成：注入人工输入 → 续跑到下一个 interrupt 或 END

        典型两次调用：
          - 确认标题后：inject = {"title": {...}, "user_description": ...} → 续跑到 confirm_outline 后暂停
          - 确认大纲后：inject = {"outline": {"sections": [...]}} → 续跑到 END（finalize 落全文 + 关 SSE）
        confirm_outline / finalize 节点负责落库 + 发 SSE；本方法仅驱动图，失败走 _handle_failure。
        """
        logger.info("恢复文章生成任务, taskId=%s", task_id)
        try:
            graph = self._get_graph()
            config = self._config(task_id)
            if inject:
                await graph.aupdate_state(config, inject)
            # None=续跑：从当前 checkpoint 接着跑到下一个 interrupt 或 END
            with usage_context(task_id=task_id, user_id=user_id):
                await graph.ainvoke(None, config)
        except Exception as e:
            await self._handle_failure(task_id, e)

    # ==================== 失败兜底（容错边界，留 service 不进图） ====================

    async def _handle_failure(self, task_id: str, e: Exception) -> None:
        """统一失败处理：标记 FAILED + 推 ERROR + 关闭 SSE

        成功路径副作用全部在图节点里；节点异常经 LangGraph 冒泡到 start/resume 的 try/except，
        由本方法兜底标记任务失败并通知前端，service 作为容错边界不进图。
        """
        logger.error("文章生成任务失败, taskId=%s, error=%s", task_id, e, exc_info=True)
        article_service = ArticleService(database)
        await article_service.update_article_status(task_id, ArticleStatusEnum.FAILED, str(e))
        send_sse_message(task_id, SseMessageTypeEnum.ERROR, {"message": str(e)})
        sse_emitter_manager.complete(task_id)
        # 失败兜底：把已发生的模型用量一次性落库（M2 埋点）
        await usage_recorder.flush(task_id)

# 全局单例
article_async_service = ArticleAsyncService()
