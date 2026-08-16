"""条件路由占位（暂不接入 builder，待内容审核 Agent 实现后启用）
"""
from __future__ import annotations

from app.schemas.article import ArticleState

# 审核不通过时最多重新生成正文的次数
MAX_REVIEW_ATTEMPTS = 3


def route_after_review(state: ArticleState):
    pass