"""AI 修改大纲副作用节点（接入主图编排）

用途：用户在 OUTLINE_EDITING 阶段提交修改建议，路由 fire-and-forget 调
article_async_service.resume(task_id, {"modify_suggestion": ...}) 续跑本图，
条件边据 state.modify_suggestion 路由进本节点。本节点：
  - 读 state：task_id / title(TitleResult) / outline.sections / modify_suggestion
  - 调 AiModifyOutlineAgent.modify_outline 重写大纲
  - ArticleService.save_outline 持久化（不写内联 SQL，不推进阶段，仍为 OUTLINE_EDITING）
  - send_sse_message AI_MODIFY_OUTLINE_COMPLETE（携带新大纲）
  - return {"outline": <new dict>, "modify_suggestion": None}（清空建议，下一轮条件边才会前进）

失败契约：LLM 抛错时本节点 catch、发 AI_MODIFY_OUTLINE_FAILED、不写 DB、不 re-raise，
避免冒泡到 ArticleAsyncService._handle_failure 把整篇文章标 FAILED。失败后 state.outline 不变，
用户随后确认大纲会沿用原文档。

agent 访问：复用 get_orchestrator() 单例持有的 ai_modify_outline_agent（独立 Agent）
"""
from __future__ import annotations

from typing import Any, Dict

from app.graph.nodes._orchestrator import get_orchestrator
from app.graph.sse_bridge import send_sse_message
from app.models.enums import SseMessageTypeEnum
from app.schemas.article import ArticleState
from app.utils.logger import logger
from app.database import database
from app.services.article_service import ArticleService


async def ai_modify_outline_node(state: ArticleState) -> Dict[str, Any]:
    """AI 修改大纲（图节点形态）

    Returns:
        成功：{"outline": <新大纲 dict>, "modify_suggestion": None}
        失败：{"modify_suggestion": None}（不写 DB，沿用原 outline）
    """
    task_id = state.task_id or ""
    logger.info("[graph] AI 修改大纲节点, taskId=%s", task_id)

    title = state.title  # Optional[TitleResult]
    main_title = title.main_title if title else ""
    sub_title = title.sub_title if title else ""
    current_sections = state.outline.sections if state.outline else []
    target_word_count = state.word_count or 2000

    # 复用编排器单例持有的独立 AI 修改大纲智能体
    orchestrator = get_orchestrator()
    agent = orchestrator.ai_modify_outline_agent

    try:
        sections = await agent.run(
            task_id=task_id,
            main_title=main_title,
            sub_title=sub_title,
            current_sections=current_sections,
            modify_suggestion=state.modify_suggestion or "",
            target_word_count=target_word_count,
            language_style=state.language_style,
        )
    except Exception as e:
        # 失败：发失败 SSE、不写 DB、清空 modify_suggestion 让下次确认能前进，不 re-raise
        logger.error("[graph] AI 修改大纲失败, taskId=%s, error=%s", task_id, e, exc_info=True)
        send_sse_message(
            task_id,
            SseMessageTypeEnum.AI_MODIFY_OUTLINE_FAILED,
            {"message": "系统内部错误：AI 修改大纲失败"},
        )
        # AI 修改失败本轮也即时结算（失败调用 0 积分，仅把 FAILED 用量落库，防内存累积）
        try:
            from app.services.settlement_service import SettlementService
            await SettlementService(database).settle_current_segment(task_id)
        except Exception:
            logger.exception("[graph] AI 修改失败段结算失败, taskId=%s", task_id)
        return {"modify_suggestion": None}

    # 成功：持久化 + 发完成 SSE + 回写图状态大纲 / 清空建议
    article_service = ArticleService(database)
    await article_service.save_outline(task_id, sections)
    send_sse_message(
        task_id,
        SseMessageTypeEnum.AI_MODIFY_OUTLINE_COMPLETE,
        {"outline": [s.model_dump() for s in sections]},
    )
    # AI 修改大纲每轮结束即时结算（点一次收一次，best-effort，水位幂等）
    try:
        from app.services.settlement_service import SettlementService
        await SettlementService(database).settle_current_segment(task_id)
    except Exception:
        logger.exception("[graph] AI 修改段结算失败, taskId=%s", task_id)
    return {
        "outline": {"sections": [s.model_dump() for s in sections]},
        "modify_suggestion": None,
    }