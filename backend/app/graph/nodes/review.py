"""【占位】内容审核 Agent 节点（暂不接入 builder，待实现）

内容审核智能体暂不实现。此文件保留占位，build_article_graph 不注册本节点，
故运行期不会调用 review_node。实现后需在 graph/state.py 补 review 相关字段、
在 edges/ 加条件边路由、并在 builder 中 add_node + 接入反思循环拓扑。
"""
from __future__ import annotations

from app.graph.state import ArticleState
from app.utils.logger import logger


async def review_node(state: ArticleState) -> dict:
    """内容审核 Agent（占位，暂不接入图）"""
    logger.info("[graph] 内容审核 Agent（占位，未接入）, taskId=%s", state.get("task_id"))
    return {}