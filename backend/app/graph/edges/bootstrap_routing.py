"""bootstrap 后的条件边路由：新闻题材走信息采集，其余直接生成标题"""
from __future__ import annotations

from app.graph.constants import NODE_GENERATE_TITLE, NODE_RESEARCH
from app.graph.state import ArticleState
from app.models.enums import ArticleGenreEnum

# 路由目标常量（与 builder 注册的节点名一致）
ROUTE_TO_RESEARCH = NODE_RESEARCH
ROUTE_TO_TITLE = NODE_GENERATE_TITLE


def route_after_bootstrap(state: ArticleState) -> str:
    """bootstrap 后的条件路由

    新闻题材（genre == "news"）→ 信息采集节点 NODE_RESEARCH，采集新闻后再生标题；
    其余题材 → 直接生成标题 NODE_GENERATE_TITLE。

    Returns:
        目标节点名（NODE_RESEARCH / NODE_GENERATE_TITLE）
    """
    if ArticleGenreEnum.is_news(state.get("genre")):
        return ROUTE_TO_RESEARCH
    return ROUTE_TO_TITLE