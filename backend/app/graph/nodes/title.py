"""标题生成节点（包装现有 TitleGeneratorAgent）

读 state：topic / style / task_id
写 state：title_options（List[TitleOption]）
SSE：emit AGENT1_COMPLETE（携带 titleOptions）
"""
from __future__ import annotations

from app.graph.nodes._orchestrator import get_orchestrator
from app.graph.sse_bridge import make_emit
from app.models.enums import SseMessageTypeEnum
from app.schemas.article import ArticleState
from app.utils.logger import logger


async def title_node(state: ArticleState) -> dict:
    """标题生成：调 TitleGeneratorAgent.run，产出 title_options"""
    orchestrator = get_orchestrator()
    emit = make_emit(state.task_id or "", state)

    logger.info("[graph] 标题生成节点, taskId=%s", state.task_id)
    await orchestrator.title_agent.run(state)
    emit(SseMessageTypeEnum.AGENT1_COMPLETE.value)

    return {"title_options": [o.model_dump(by_alias=True) for o in state.title_options] if state.title_options else None}