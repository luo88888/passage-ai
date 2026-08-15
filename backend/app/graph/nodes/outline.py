"""大纲生成节点（包装现有 OutlineGeneratorAgent）

读 state：title / user_description / task_id / word_count / topic / genre / language_style / collected_news
写 state：outline（OutlineResult）
SSE：流式 AGENT2_STREAMING:* 前缀片段（由 agent 内部通过 emit 推送）+ emit AGENT2_COMPLETE（携带 outline）
"""
from __future__ import annotations

from app.graph.nodes._orchestrator import get_orchestrator
from app.graph.sse_bridge import make_emit
from app.models.enums import SseMessageTypeEnum
from app.schemas.article import ArticleState
from app.utils.logger import logger


async def outline_node(state: ArticleState) -> dict:
    """大纲生成：调 OutlineGeneratorAgent.run，产出 outline"""
    orchestrator = get_orchestrator()
    emit = make_emit(state.task_id or "", state)

    logger.info("[graph] 大纲生成节点, taskId=%s", state.task_id)
    await orchestrator.outline_agent.run(state, emit)
    emit(SseMessageTypeEnum.AGENT2_COMPLETE.value)

    return {"outline": state.outline.model_dump() if state.outline else None}