"""图文合并节点（包装现有 ContentMergerAgent）

注意 ContentMergerAgent.run 是**同步**方法（非 async，不调 LLM，纯字符串替换占位符）。
读 state：content（带占位符版本）/ images / task_id
写 state：full_content（占位符替换为 markdown 图片语法的最终全文）
SSE：emit MERGE_COMPLETE（携带 fullContent）
"""
from __future__ import annotations

from app.graph.nodes._orchestrator import get_orchestrator
from app.graph.nodes.compat import merge_to_dict_state, to_class_state
from app.graph.sse_bridge import make_emit
from app.graph.state import ArticleState
from app.models.enums import SseMessageTypeEnum
from app.utils.logger import logger


async def content_merger_node(state: ArticleState) -> dict:
    """图文合并：调 ContentMergerAgent.run（同步），产出 full_content"""
    class_state = to_class_state(state)
    orchestrator = get_orchestrator()
    emit = make_emit(state.get("task_id") or "", class_state)

    logger.info("[graph] 图文合并节点, taskId=%s", state.get("task_id"))
    # ContentMergerAgent.run 是同步方法，直接调用（非 await）
    orchestrator.content_merger_agent.run(class_state)
    emit(SseMessageTypeEnum.MERGE_COMPLETE.value)

    return merge_to_dict_state(class_state)