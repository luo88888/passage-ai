"""图文合并节点（包装现有 ContentMergerAgent）

注意 ContentMergerAgent.run 是**同步**方法
读 state：content / images / task_id
写 state：full_content（占位符替换为 markdown 图片语法的最终全文）
SSE：emit MERGE_COMPLETE（携带 fullContent）
"""
from __future__ import annotations

from app.graph.nodes._orchestrator import get_orchestrator
from app.graph.sse_bridge import make_emit
from app.models.enums import SseMessageTypeEnum
from app.schemas.article import ArticleState
from app.utils.logger import logger


async def content_merger_node(state: ArticleState) -> dict:
    """图文合并：调 ContentMergerAgent.run（同步），产出 full_content"""
    orchestrator = get_orchestrator()
    emit = make_emit(state.task_id or "", state)

    logger.info("[graph] 图文合并节点, taskId=%s", state.task_id)
    # ContentMergerAgent.run 是同步方法
    orchestrator.content_merger_agent.run(state)
    emit(SseMessageTypeEnum.MERGE_COMPLETE.value)

    return {"full_content": state.full_content}