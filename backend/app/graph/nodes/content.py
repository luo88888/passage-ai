"""正文生成节点（包装现有 ContentGeneratorAgent）

读 state：outline / title / task_id / topic / genre / language_style / collected_news / word_count
写 state：content（流式拼接的正文 str）
SSE：流式 AGENT3_STREAMING:* 前缀片段（由 agent 内部通过 emit 推送）+ emit AGENT3_COMPLETE
"""
from __future__ import annotations

from app.graph.nodes._orchestrator import get_orchestrator
from app.graph.sse_bridge import make_emit
from app.models.enums import SseMessageTypeEnum
from app.schemas.article import ArticleState
from app.utils.logger import logger


async def content_node(state: ArticleState) -> dict:
    """正文生成：调 ContentGeneratorAgent.run，产出 content"""
    orchestrator = get_orchestrator()
    emit = make_emit(state.task_id or "", state)

    logger.info("[graph] 正文生成节点, taskId=%s", state.task_id)
    await orchestrator.content_agent.run(state, emit)
    emit(SseMessageTypeEnum.AGENT3_COMPLETE.value)

    return {"content": state.content}