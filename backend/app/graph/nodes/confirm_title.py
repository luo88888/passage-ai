"""标题确认副作用节点（generate_title 节点后、暂停前）

读 state：task_id / title_options（List[TitleOption]）
副作用：
  - save_title_options(task_id, title_options)
  - update_phase(task_id, TITLE_SELECTING)
  - send_sse_message(task_id, TITLE_GENERATED, {"titleOptions": ...})
return {}（图状态不变，标题已由 generate_title 节点写入 title_options）。

阶段流转：TITLE_GENERATING → TITLE_SELECTING（合法）。
"""
from __future__ import annotations

from app.graph.sse_bridge import send_sse_message
from app.models.enums import ArticlePhaseEnum, SseMessageTypeEnum
from app.schemas.article import ArticleState
from app.utils.logger import logger
from app.database import database
from app.services.article_service import ArticleService
from app.services.settlement_service import SettlementService


async def confirm_title_node(state: ArticleState) -> dict:
    """标题确认：落标题方案 + 推进阶段 + 发 TITLE_GENERATED"""
    task_id = state.task_id or ""
    title_options = state.title_options or []

    article_service = ArticleService(database)
    logger.info("[graph] 标题确认节点, taskId=%s", task_id)
    await article_service.save_title_options(task_id, title_options)
    await article_service.update_phase(task_id, ArticlePhaseEnum.TITLE_SELECTING)

    send_sse_message(
        task_id,
        SseMessageTypeEnum.TITLE_GENERATED,
        {"titleOptions": [o.model_dump(by_alias=True) for o in title_options]},
    )

    # 段A 结算：标题生成（含新闻信息采集）用量即时结算。
    # best-effort：结算失败记日志、不阻断流程，未结算用量由下个段边界补结（结算水位幂等防重复扣费）。
    try:
        await SettlementService(database).settle_current_segment(task_id)
    except Exception:
        logger.exception("[graph] 标题段结算失败, taskId=%s", task_id)
    return {}
