"""配图生成节点（包装现有 ImageGeneratorAgent）

读 state：image_requirements / task_id
写 state：images（按 position 排序的 List[ImageResult]）
SSE：流式 IMAGE_COMPLETE:<image json>（每张配图完成，由 agent 内部通过 emit 推送）+ emit AGENT5_COMPLETE（携带 images）
"""
from __future__ import annotations

from app.graph.nodes._orchestrator import get_orchestrator
from app.graph.nodes.compat import merge_to_dict_state, to_class_state
from app.graph.sse_bridge import make_emit
from app.graph.state import ArticleState
from app.models.enums import SseMessageTypeEnum
from app.utils.logger import logger


async def image_generator_node(state: ArticleState) -> dict:
    """配图生成：调 ImageGeneratorAgent.run，产出 images"""
    class_state = to_class_state(state)
    orchestrator = get_orchestrator()
    emit = make_emit(state.get("task_id") or "", class_state)

    logger.info("[graph] 配图生成节点, taskId=%s", state.get("task_id"))
    await orchestrator.image_generator_agent.run(class_state, emit)
    emit(SseMessageTypeEnum.AGENT5_COMPLETE.value)

    return merge_to_dict_state(class_state)