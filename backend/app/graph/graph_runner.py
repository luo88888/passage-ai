"""
文章异步任务服务（LangGraph 编排版，仅负责启停/恢复）

职责已收窄为「创建/启动任务、恢复任务、持有 Task 引用防 GC、并发守卫、失败兜底」：
  - start(task_id, topic, genre, ...): 建初始 state → ainvoke 跑到第一个 interrupt
       （confirm_title 后：标题已落库 + TITLE_GENERATED 已发，等用户确认标题）
  - resume(task_id, inject, user_id): 注入人工输入（确认标题后的 title/description、确认大纲后的 outline）
       → aupdate_state + ainvoke(None) 续跑到下一个 interrupt 或 END
  - reserve_task / attach_task / release_task: 保存 asyncio.Task 引用防 GC，同时充当同 taskId 并发守卫
    （reserve_task 在路由层任何 await 之前原子占坑，重复 resume 被零副作用拒绝；
      attach_task 绑定后台任务并挂释放回调，release_task 供校验/写库失败回滚）
  - _handle_failure: 节点异常冒泡到此 → 结算已发生用量 + 标记 FAILED + 释放并发名额
    + 推 ERROR + 关闭 SSE（容错边界）

成功路径的全部副作用（update_article_status / update_phase / save_title_options /
save_outline / save_article_content / send_sse_message / sse complete）均已收入图节点
（bootstrap / confirm_title / confirm_outline / finalize），本类不再 inline 做这些。
图状态用 SQLite checkpointer 持久化（thread_id = taskId），取代原手工 checkpoint。
"""
import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.database import database
from app.graph.checkpointer import get_checkpointer
from app.graph.sse_bridge import send_sse_message
from app.managers.sse_manager import sse_emitter_manager
from app.models.enums import ArticleStatusEnum, SseMessageTypeEnum
from app.services.article_service import ArticleService
from app.services.model_usage_service import usage_context, usage_recorder
from app.utils.logger import logger
from app.services.settlement_service import SettlementService
from app.exceptions import ErrorCode, throw_if


@dataclass
class RunningTask:
    """正在运行的图任务（并发守卫：同 taskId 禁止重复 resume）

    Attributes:
        task: asyncio.Task 引用（防 GC + task.done() 判活）；先 reserve_task 占坑（None），校验/写库通过后由 attach_task 填入
        action: 本次操作名（拒绝并发时展示给用户）
        started_at: 启动时间戳（time.time()，可展示耗时）
    """
    task: Optional[asyncio.Task]
    action: str
    started_at: float


class ArticleAsyncService:
    """文章异步任务服务：仅负责启停/恢复/失败兜底，成功路径副作用全在图节点里。"""

    def __init__(self) -> None:
        self._graph = None  # 已编译图单例，懒构造（需 lifespan 已 init checkpointer）
        # 持有异步任务引用避免被 GC 回收；同时充当「同 taskId 正在运行」的并发守卫
        self._tasks: Dict[str, RunningTask] = {}

    # ==================== 图与 checkpointer 单例 ====================

    def _get_graph(self):
        """惰性构造已编译图单例（注入 checkpointer）"""
        if self._graph is None:
            from app.graph.builder import build_article_graph
            self._graph = build_article_graph(get_checkpointer())
        return self._graph

    @staticmethod
    def _config(task_id: str) -> Dict[str, Any]:
        """LangGraph 配置：thread_id = taskId，checkpointer 按此隔离各文章状态

        Returns:
            - {"configurable": {"thread_id": task_id}}
        """
        return {"configurable": {"thread_id": task_id}}

    # ==================== AsyncTask 引用管理（GC 修复 + 并发守卫） ====================

    def reserve_task(self, task_id: str, action: str) -> None:
        """原子占用同 taskId 并发名额（无 await，事件循环内天然互斥）。

        必须由路由层在**任何 await / DB 副作用之前**调用；成功后才做余额复查与写库，
        校验失败用 release_task 回滚。重复 resume 在此一步被拒绝（DB 零副作用）。

        Args:
            task_id: 文章任务 ID
            action: 本次操作名，拒绝并发时展示给用户
        Raises:
            BusinessException: 同 taskId 已有任务在跑（OPERATION_ERROR）
        """
        current = self._tasks.get(task_id)
        if current is not None:
            throw_if(
                True,
                ErrorCode.OPERATION_ERROR,
                f"{current.action}，请勿重复操作",
            )
        self._tasks[task_id] = RunningTask(task=None, action=action, started_at=time.time())

    def attach_task(self, task_id: str, task: asyncio.Task) -> None:
        """绑定真正的后台任务并挂释放回调（先 reserve_task 占坑、校验写库通过后才 attach）。

        task 完成时回调释放占用；回调仅在「当前登记的仍是本任务」时才清理，
        防止旧任务完成回调误删同 taskId 新任务引用。

        Args:
            task_id: 文章任务 ID
            task: 后台 asyncio.Task（通常为 asyncio.create_task(resume(...))）
        Raises:
            BusinessException: 未先 reserve_task / 重复绑定（SYSTEM_ERROR，理论不可达）
        """
        current = self._tasks.get(task_id)
        if current is None or current.task is not None:
            logger.error(f"并发名额状态异常，请先 reserve_task 再 attach_task，task_id={task_id}")
            throw_if(
                True,
                ErrorCode.SYSTEM_ERROR
            )
        assert current is not None
        current.task = task
        task.add_done_callback(lambda t, tid=task_id: self._cleanup_done_task(t, tid))

    def _cleanup_done_task(self, task: asyncio.Task, task_id: str) -> None:
        """任务完成回调：仅当「当前登记的 RunningTask 仍是本任务」时才释放占用。

        防止旧任务完成回调误删同 taskId 新任务的引用（release_task 回滚后重新
        reserve/attach 的场景：旧任务仍在跑，其完成回调不得清掉新任务的占坑）。

        Args:
            task: 已完成的后台任务
            task_id: 文章任务 ID
        """
        current = self._tasks.get(task_id)
        if current is not None and current.task is task:
            self._tasks.pop(task_id, None)

    def release_task(self, task_id: str) -> None:
        """释放并发占用（路由层校验/写库失败时回滚占坑，避免名额卡死）"""
        self._tasks.pop(task_id, None)

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

        # 失败兜底：按已发生用量结算（后付费段级结算，best-effort；结算水位幂等防重复扣费）
        try:
            await SettlementService(database).settle_current_segment(task_id)
        except Exception:
            logger.exception("失败结算失败 taskId=%s", task_id)

        logger.error(f"文章生成任务失败：task_id={task_id}, {str(e)}")
        
        # 失败终态：标记 FAILED + 释放并发名额（同一事务，终态一致性）
        await article_service.fail_task_and_release_slot(task_id, str(e))

        send_sse_message(task_id, SseMessageTypeEnum.ERROR, {"message": str(e)})
        sse_emitter_manager.complete(task_id)
        # 清理任务用量内存（已按段结算落库）
        usage_recorder.drop(task_id)

# 全局单例
article_async_service = ArticleAsyncService()
