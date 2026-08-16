"""confirm_outline / ai_modify_outline 后的条件路由"""
from __future__ import annotations

from app.schemas.article import ArticleState
from app.graph.constants import NODE_AI_MODIFY_OUTLINE, NODE_GENERATE_CONTENT


def route_after_outline(state: ArticleState) -> str:
    """confirm_outline / ai_modify_outline 后的条件路由

    有 modify_suggestion（路由层 ai-modify-outline 注入）→ 进 AI 修改大纲节点；
    否则（确认大纲时未注入建议 / 节点消费后清空）→ 进 generate_content 继续正文生成。
    """
    return NODE_AI_MODIFY_OUTLINE if state.modify_suggestion else NODE_GENERATE_CONTENT