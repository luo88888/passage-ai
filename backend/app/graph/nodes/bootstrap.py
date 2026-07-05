"""启动副作用节点（图入口）

读 state：task_id
副作用：
  - update_article_status(task_id, PROCESSING)
  - update_phase(task_id, TITLE_GENERATING)
不产出新字段，return {}（图状态不变）。

阶段流转：DB 初值 PENDING → TITLE_GENERATING（合法，见 enums.ArticlePhaseEnum.can_transition_to）。
"""
from __future__ import annotations

from app.graph.state import ArticleState
from app.models.enums import ArticlePhaseEnum, ArticleStatusEnum
from app.utils.logger import logger


async def bootstrap_node(state: ArticleState) -> dict:
    """启动副作用：标记任务处理中 + 推进到标题生成阶段"""
    task_id = state.get("task_id") or ""

    # 函数体内 import，避免触发 app.services.__init__ → article_async_service → graph 的循环导入
    # （约定见 app/graph/nodes/_orchestrator.py）
    from app.database import database
    from app.services.article_service import ArticleService

    article_service = ArticleService(database)
    logger.info("[graph] 启动节点, taskId=%s", task_id)
    await article_service.update_article_status(task_id, ArticleStatusEnum.PROCESSING)
    await article_service.update_phase(task_id, ArticlePhaseEnum.TITLE_GENERATING)
    return {}