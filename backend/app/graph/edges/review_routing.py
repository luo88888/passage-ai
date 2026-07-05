"""条件路由占位（暂不接入 builder，待内容审核 Agent 实现后启用）

当前图没有条件边（线性拓扑：title→outline→content→...→END）。
内容审核 Agent 实现后，在此定义 route_after_review 等条件边路由，
并在 graph/state.py 补 review 相关字段、在 builder 中 add_conditional_edges。
"""
from __future__ import annotations

from app.graph.state import ArticleState

# 审核后分支标识（实现后供 builder add_conditional_edges 映射使用）
ROUTE_APPROVED = "approved"
ROUTE_REJECTED = "rejected"

# 审核不通过时最多重新生成正文的次数（实现后启用）
MAX_REVIEW_ATTEMPTS = 3


def route_after_review(state: ArticleState) -> str:
    """审核后路由（占位，暂不接入图）。

    实现后语义：通过 → ROUTE_APPROVED（进配图流程），不通过 → ROUTE_REJECTED（回正文重写）；
    达到 MAX_REVIEW_ATTEMPTS 强制放行。
    """
    return ROUTE_APPROVED