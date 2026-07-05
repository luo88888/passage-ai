"""收尾副作用节点（merger 节点后、END 前）

读 state：全部产物（title/outline/content/images/full_content 等）
副作用：
  - save_article_content(task_id, class_state)   # 复用 to_class_state 重建 class ArticleState
  - update_article_status(task_id, COMPLETED)
  - send_sse_message(task_id, ALL_COMPLETE, {taskId})
  - sse_emitter_manager.complete(task_id)         # 关闭 SSE 连接
return {}（图状态不变，全文已由 merger 节点写入 full_content）。

阶段状态由路由层 confirm_outline 已推进到 CONTENT_GENERATING；此处仅置 status=COMPLETED
（status 不走 phase 流转校验，update_article_status 无 can_transition_to 约束）。
"""
from __future__ import annotations

from app.graph.nodes.compat import to_class_state
from app.graph.sse_bridge import send_sse_message
from app.graph.state import ArticleState
from app.managers.sse_manager import sse_emitter_manager
from app.models.enums import ArticleStatusEnum, SseMessageTypeEnum
from app.utils.logger import logger


async def finalize_node(state: ArticleState) -> dict:
    """收尾：落正文/配图/全文 + 标记完成 + 发 ALL_COMPLETE + 关闭 SSE"""
    task_id = state.get("task_id") or ""
    class_state = to_class_state(state)

    # 函数体内 import，避免触发 app.services.__init__ → article_async_service → graph 的循环导入
    from app.database import database
    from app.services.article_service import ArticleService

    article_service = ArticleService(database)
    logger.info("[graph] 收尾节点, taskId=%s", task_id)
    await article_service.save_article_content(task_id, class_state)
    await article_service.update_article_status(task_id, ArticleStatusEnum.COMPLETED)

    send_sse_message(
        task_id,
        SseMessageTypeEnum.ALL_COMPLETE,
        {"taskId": task_id},
    )
    sse_emitter_manager.complete(task_id)
    return {}