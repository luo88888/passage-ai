"""配图需求分析节点（包装现有 ImageAnalyzerAgent）

读 state：enabled_image_methods / title / content / genre / language_style
写 state：image_requirements（校验降级后的 List[ImageRequirement]）
SSE：emit AGENT4_COMPLETE（携带 imageRequirements）
"""
from __future__ import annotations

from app.graph.nodes._orchestrator import get_orchestrator
from app.graph.sse_bridge import make_emit
from app.models.enums import SseMessageTypeEnum
from app.schemas.article import ArticleState
from app.utils.logger import logger


async def image_analyzer_node(state: ArticleState) -> dict:
    """配图需求分析：调 ImageAnalyzerAgent.run，产出 image_requirements"""
    orchestrator = get_orchestrator()
    emit = make_emit(state.task_id or "", state)

    logger.info("[graph] 配图需求分析节点, taskId=%s", state.task_id)
    await orchestrator.image_analyzer_agent.run(state)
    emit(SseMessageTypeEnum.AGENT4_COMPLETE.value)

    return {"image_requirements": [r.model_dump(by_alias=True) for r in state.image_requirements] if state.image_requirements else None}