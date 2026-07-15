"""AI 修改大纲副作用节点（接入主图编排）

用途：用户在 OUTLINE_EDITING 阶段提交修改建议，路由 fire-and-forget 调
article_async_service.resume(task_id, {"modify_suggestion": ...}) 续跑本图，
条件边据 state["modify_suggestion"] 路由进本节点。本节点：
  - 读 state：task_id / title(mainTitle,subTitle) / outline.sections / modify_suggestion
  - 调 LLM 重写大纲（复用 PromptConstant.AI_MODIFY_OUTLINE_PROMPT）
  - ArticleService.save_outline 持久化（不写内联 SQL，不推进阶段，仍为 OUTLINE_EDITING）
  - send_sse_message AI_MODIFY_OUTLINE_COMPLETE（携带新大纲）
  - return {"outline": <new dict>, "modify_suggestion": None}（清空建议，下一轮条件边才会前进）

失败契约：LLM 抛错时本节点 catch、发 AI_MODIFY_OUTLINE_FAILED、不写 DB、不 re-raise，
避免冒泡到 ArticleAsyncService._handle_failure 把整篇文章标 FAILED。失败后 state.outline 不变，
用户随后确认大纲会沿用原文档。

agent 访问：复用 get_orchestrator().title_agent —— 仅借用其 BaseAgent 共享方法
(_call_llm / _agent_log_context_sync / _parse_json_response / _safe_json_dumps)，
不调用 title_agent.run()（语义无关，仅借用其 client/model/agent_log_service），
以避免重复构造 AsyncOpenAI 客户端与 AgentLogService，与 _orchestrator.py 单例目的一致。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from app.constants.prompt import PromptConstant
from app.graph.nodes._orchestrator import get_orchestrator
from app.graph.sse_bridge import send_sse_message
from app.graph.state import ArticleState
from app.models.enums import SseMessageTypeEnum
from app.utils.logger import logger


async def ai_modify_outline_node(state: ArticleState) -> Dict[str, Any]:
    """AI 修改大纲（图节点形态）

    Returns:
        成功：{"outline": <新大纲 dict>, "modify_suggestion": None}
        失败：{"modify_suggestion": None}（不写 DB，沿用原 outline）
    """
    task_id = state.get("task_id") or ""
    logger.info("[graph] AI 修改大纲节点, taskId=%s", task_id)

    title_dict = state.get("title") or {}
    main_title = title_dict.get("mainTitle", "")
    sub_title = title_dict.get("subTitle", "")
    outline_dict = state.get("outline") or {}
    sections_dict: List[dict] = outline_dict.get("sections", []) if outline_dict else []

    # 函数体内 import，避免触发 app.services.__init__ → article_async_service → graph 的循环导入
    from app.database import database
    from app.schemas.article import OutlineSection
    from app.services.article_service import ArticleService

    current_outline = [OutlineSection(**s) for s in sections_dict]
    current_outline_json = json.dumps(
        [item.model_dump() for item in current_outline],
        ensure_ascii=False,
    )

    target_word_count = state.get("word_count") or 2000
    prompt = (
        PromptConstant.AI_MODIFY_OUTLINE_PROMPT
        .replace("{mainTitle}", main_title)
        .replace("{subTitle}", sub_title)
        .replace("{currentOutline}", current_outline_json)
        .replace("{modifySuggestion}", state.get("modify_suggestion") or "")
        .replace("{targetWordCount}", str(target_word_count))
    )

    # 复用编排器单例持有的 title_agent（仅借用 BaseAgent 共享方法，非 title 语义）
    agent = get_orchestrator().title_agent
    # 注入语言风格提示词（与 outline 节点保持一致），使修改后大纲同样贴合语气取向
    prompt += agent._get_language_style_prompt(state.get("language_style"))

    try:
        with agent._agent_log_context_sync(
            task_id=task_id or "unknown",
            agent_name="ai_modify_outline",
            prompt=prompt,
            input_data={
                "mainTitle": main_title,
                "subTitle": sub_title,
                "currentSectionsCount": len(current_outline),
            },
        ) as log_data:
            content = await agent._call_llm(prompt)
            outline_data = agent._parse_json_response(content, "修改后的大纲")
            sections = [OutlineSection(**s) for s in outline_data["sections"]]
            log_data["outputData"] = agent._safe_json_dumps(
                {"sectionsCount": len(sections)}
            )
    except Exception as e:
        # 失败：发失败 SSE、不写 DB、清空 modify_suggestion 让下次确认能前进，不 re-raise
        logger.error("[graph] AI 修改大纲失败, taskId=%s, error=%s", task_id, e, exc_info=True)
        send_sse_message(
            task_id,
            SseMessageTypeEnum.AI_MODIFY_OUTLINE_FAILED,
            {"message": str(e)},
        )
        return {"modify_suggestion": None}

    # 成功：持久化 + 发完成 SSE + 回写图状态大纲 / 清空建议
    article_service = ArticleService(database)
    await article_service.save_outline(task_id, sections)
    send_sse_message(
        task_id,
        SseMessageTypeEnum.AI_MODIFY_OUTLINE_COMPLETE,
        {"outline": [s.model_dump() for s in sections]},
    )
    return {
        "outline": {"sections": [s.model_dump() for s in sections]},
        "modify_suggestion": None,
    }