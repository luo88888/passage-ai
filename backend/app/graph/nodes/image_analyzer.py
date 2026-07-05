"""配图需求分析节点（包装现有 ImageAnalyzerAgent）

读 state：enabled_image_methods / title / content / style / task_id
写 state：content（覆盖为带占位符版本）/ image_requirements（校验降级后的 List[ImageRequirement]）
SSE：emit AGENT4_COMPLETE（携带 imageRequirements）
"""
from __future__ import annotations

from app.graph.nodes._orchestrator import get_orchestrator
from app.graph.nodes.compat import merge_to_dict_state, to_class_state
from app.graph.sse_bridge import make_emit
from app.graph.state import ArticleState
from app.models.enums import SseMessageTypeEnum
from app.utils.logger import logger


async def image_analyzer_node(state: ArticleState) -> dict:
    """配图需求分析：调 ImageAnalyzerAgent.run，产出带占位符的 content + image_requirements"""
    class_state = to_class_state(state)
    orchestrator = get_orchestrator()
    emit = make_emit(state.get("task_id") or "", class_state)

    logger.info("[graph] 配图需求分析节点, taskId=%s", state.get("task_id"))
    await orchestrator.image_analyzer_agent.run(class_state)
    emit(SseMessageTypeEnum.AGENT4_COMPLETE.value)

    return merge_to_dict_state(class_state)