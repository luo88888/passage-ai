"""配图生成节点（包装现有 ImageGeneratorAgent）

读 state：image_requirements / task_id
写 state：images（按 position 排序的 List[ImageResult]）
SSE：流式 IMAGE_COMPLETE:<image json>（每张配图完成，由 agent 内部通过 emit 推送）+ emit AGENT5_COMPLETE（携带 images）
"""
from __future__ import annotations

from app.graph.nodes._orchestrator import get_orchestrator
from app.graph.sse_bridge import make_emit
from app.models.enums import SseMessageTypeEnum
from app.schemas.article import ArticleState
from app.utils.logger import logger


async def image_generator_node(state: ArticleState) -> dict:
    """配图生成：调 ImageGeneratorAgent.run，产出 images"""
    orchestrator = get_orchestrator()
    emit = make_emit(state.task_id or "", state)

    logger.info("[graph] 配图生成节点, taskId=%s", state.task_id)
    await orchestrator.image_generator_agent.run(state, emit)
    emit(SseMessageTypeEnum.AGENT5_COMPLETE.value)

    return {"images": [i.model_dump(by_alias=True) for i in state.images] if state.images else None}