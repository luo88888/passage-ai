"""正文生成节点（包装现有 ContentGeneratorAgent）

读 state：outline / title / style / task_id
写 state：content（流式拼接的正文 str）
SSE：流式 AGENT3_STREAMING:* 前缀片段（由 agent 内部通过 emit 推送）+ emit AGENT3_COMPLETE
"""
from __future__ import annotations

from app.graph.nodes._orchestrator import get_orchestrator
from app.graph.nodes.compat import merge_to_dict_state, to_class_state
from app.graph.sse_bridge import make_emit
from app.graph.state import ArticleState
from app.models.enums import SseMessageTypeEnum
from app.utils.logger import logger


async def content_node(state: ArticleState) -> dict:
    """正文生成：调 ContentGeneratorAgent.run，产出 content"""
    class_state = to_class_state(state)
    orchestrator = get_orchestrator()
    emit = make_emit(state.get("task_id") or "", class_state)

    logger.info("[graph] 正文生成节点, taskId=%s", state.get("task_id"))
    await orchestrator.content_agent.run(class_state, emit)
    emit(SseMessageTypeEnum.AGENT3_COMPLETE.value)

    return merge_to_dict_state(class_state)