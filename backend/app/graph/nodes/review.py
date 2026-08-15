"""【占位】内容审核 Agent 节点（暂不接入 builder，待实现）
"""
from __future__ import annotations

from app.schemas.article import ArticleState
from app.utils.logger import logger


async def review_node(state: ArticleState) -> dict:
    """内容审核 Agent（占位，暂不接入图）"""
    logger.info("[graph] 内容审核 Agent（占位，未接入）, taskId=%s", state.task_id)
    return {}