"""【占位】信息采集 Agent 节点（暂不接入 builder，待实现）

数据采集智能体暂不实现。此文件保留占位，build_article_graph 不注册本节点，
故运行期不会调用 research_node。实现后需在 graph/state.py 补 research 相关字段、
并在 builder 中 add_node + 接入拓扑。
"""
from __future__ import annotations

from app.graph.state import ArticleState
from app.utils.logger import logger


async def research_node(state: ArticleState) -> dict:
    """信息采集 Agent（占位，暂不接入图）"""
    logger.info(
        "[graph] 信息采集 Agent（占位，未接入）, taskId=%s, topic=%s",
        state.get("task_id"),
        state.get("topic"),
    )
    return {}