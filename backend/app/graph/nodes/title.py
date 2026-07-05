"""标题生成节点（包装现有 TitleGeneratorAgent）

读 state：topic / style / task_id
写 state：title_options（List[TitleOption]）
SSE：emit AGENT1_COMPLETE（携带 titleOptions）
"""
from __future__ import annotations

from app.graph.nodes._orchestrator import get_orchestrator
from app.graph.nodes.compat import merge_to_dict_state, to_class_state
from app.graph.sse_bridge import make_emit
from app.graph.state import ArticleState
from app.models.enums import SseMessageTypeEnum
from app.utils.logger import logger


async def title_node(state: ArticleState) -> dict:
    """标题生成：调 TitleGeneratorAgent.run，产出 title_options"""
    class_state = to_class_state(state)
    orchestrator = get_orchestrator()
    emit = make_emit(state.get("task_id") or "", class_state)

    logger.info("[graph] 标题生成节点, taskId=%s", state.get("task_id"))
    await orchestrator.title_agent.run(class_state)
    emit(SseMessageTypeEnum.AGENT1_COMPLETE.value)

    return merge_to_dict_state(class_state)