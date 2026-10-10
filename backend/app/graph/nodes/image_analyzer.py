"""配图需求分析节点（包装现有 ImageAnalyzerAgent）

读 state：enabled_image_methods / title / content / genre / language_style
写 state：image_requirements（校验降级后的 List[ImageRequirement]）
SSE：emit AGENT4_COMPLETE（携带 imageRequirements）

降级契约：配图分析重试耗尽（AgentMaxRetriesError）不整篇失败——
设置 image_requirements = [] 继续配图生成（空配图）与合并，最终产出纯文本文章。
"""
from __future__ import annotations

from app.exceptions import AgentMaxRetriesError
from app.graph.nodes._orchestrator import get_orchestrator
from app.graph.sse_bridge import make_emit, send_agent_retry
from app.models.enums import RetryStageEnum, SseMessageTypeEnum
from app.schemas.article import ArticleState
from app.utils.logger import logger


async def image_analyzer_node(state: ArticleState) -> dict:
    """配图需求分析：调 ImageAnalyzerAgent.run，产出 image_requirements"""
    orchestrator = get_orchestrator()
    emit = make_emit(state.task_id or "", state)

    logger.info("[graph] 配图需求分析节点, taskId=%s", state.task_id)
    try:
        await orchestrator.image_analyzer_agent.run(state, stream_handler=emit)
    except AgentMaxRetriesError as e:
        # 降级：配图分析多次失败不整篇失败，空配图继续后续流程，最终产出纯文本文章
        logger.warning(
            "[graph] 配图需求分析重试耗尽，降级为空配图继续, taskId=%s, error=%s",
            state.task_id,
            e,
        )
        state.image_requirements = []
        send_agent_retry(
            state.task_id or "",
            RetryStageEnum.IMAGE,
            "配图需求分析多次失败，已降级为纯文本文章",
        )
    emit(SseMessageTypeEnum.AGENT4_COMPLETE.value)

    return {
        "image_requirements": (
            [r.model_dump(by_alias=True) for r in state.image_requirements]
            if state.image_requirements else []
        )
    }
