"""【占位】SEO 优化 Agent 节点（暂不接入 builder，待实现）

SEO 优化智能体暂不实现。此文件保留占位，build_article_graph 不注册本节点，
故运行期不会调用 seo_node。实现后需在 graph/state.py 补 SEO 相关字段、
并在 builder 中 add_node + 接入拓扑（merger 之后、END 之前）。
"""
from __future__ import annotations

from app.graph.state import ArticleState
from app.utils.logger import logger


async def seo_node(state: ArticleState) -> dict:
    """SEO 优化 Agent（占位，暂不接入图）"""
    logger.info("[graph] SEO 优化 Agent（占位，未接入）, taskId=%s", state.get("task_id"))
    return {}