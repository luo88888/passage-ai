"""大纲确认副作用节点（generate_outline 节点后、暂停前）

读 state：task_id / outline.sections（List[dict]，每项 {"section","title","points"}）
副作用：
  - save_outline(task_id, [OutlineSection(**s) ...])
  - update_phase(task_id, OUTLINE_EDITING)
  - send_sse_message(task_id, OUTLINE_GENERATED, {"outline": [s.model_dump() ...]})
return {}（图状态不变，大纲已由 generate_outline 节点写入 outline）。

阶段流转：OUTLINE_GENERATING（由路由层 confirm_title 写入）→ OUTLINE_EDITING（合法）。
"""
from __future__ import annotations

from app.graph.sse_bridge import send_sse_message
from app.graph.state import ArticleState
from app.models.enums import ArticlePhaseEnum, SseMessageTypeEnum
from app.utils.logger import logger


async def confirm_outline_node(state: ArticleState) -> dict:
    """大纲确认：落大纲 + 推进阶段 + 发 OUTLINE_GENERATED"""
    task_id = state.get("task_id") or ""
    outline_dict = state.get("outline") or {}
    sections_dict = outline_dict.get("sections", []) if outline_dict else []

    # 函数体内 import，避免触发 app.services.__init__ → article_async_service → graph 的循环导入
    from app.database import database
    from app.schemas.article import OutlineSection
    from app.services.article_service import ArticleService

    sections = [OutlineSection(**s) for s in sections_dict]

    article_service = ArticleService(database)
    logger.info("[graph] 大纲确认节点, taskId=%s", task_id)
    await article_service.save_outline(task_id, sections)
    await article_service.update_phase(task_id, ArticlePhaseEnum.OUTLINE_EDITING)

    send_sse_message(
        task_id,
        SseMessageTypeEnum.OUTLINE_GENERATED,
        {"outline": [s.model_dump() for s in sections]},
    )
    return {}