"""标题确认副作用节点（generate_title 节点后、暂停前）

读 state：task_id / title_options（List[dict]，每项 {"mainTitle","subTitle"}）
副作用：
  - save_title_options(task_id, [TitleOption(**i) ...])
  - update_phase(task_id, TITLE_SELECTING)
  - send_sse_message(task_id, TITLE_GENERATED, {"titleOptions": ...})
return {}（图状态不变，标题已由 generate_title 节点写入 title_options）。

阶段流转：TITLE_GENERATING → TITLE_SELECTING（合法）。
"""
from __future__ import annotations

from app.graph.sse_bridge import send_sse_message
from app.graph.state import ArticleState
from app.models.enums import ArticlePhaseEnum, SseMessageTypeEnum
from app.utils.logger import logger


async def confirm_title_node(state: ArticleState) -> dict:
    """标题确认：落标题方案 + 推进阶段 + 发 TITLE_GENERATED"""
    task_id = state.get("task_id") or ""
    title_options_dict = state.get("title_options") or []

    # 函数体内 import，避免触发 app.services.__init__ → article_async_service → graph 的循环导入
    from app.database import database
    from app.schemas.article import TitleOption
    from app.services.article_service import ArticleService

    article_service = ArticleService(database)
    logger.info("[graph] 标题确认节点, taskId=%s", task_id)
    await article_service.save_title_options(
        task_id,
        [TitleOption(**item) for item in title_options_dict],
    )
    await article_service.update_phase(task_id, ArticlePhaseEnum.TITLE_SELECTING)

    send_sse_message(
        task_id,
        SseMessageTypeEnum.TITLE_GENERATED,
        {"titleOptions": title_options_dict},
    )
    return {}