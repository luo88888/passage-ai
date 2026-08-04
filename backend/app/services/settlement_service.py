"""积分结算服务（M3：后付费段级结算 + 启动对账）。

职责：
  1. settle_current_segment：按「计费段」增量结算——
     取新增用量（UsageRecorder 结算水位）→ 计价（PricingService）→
     同一事务写 model_usage_record + 扣 user_points（USAGE_SETTLE 流水）→ 推进结算水位；
     允许负余额（透支护栏由路由层/续跑前复查），admin 豁免扣费但用量照常落库；
  2. reconcile_active_task_counts：启动对账，纠正 user.activeTaskCount 与 article 表
     「进行中（含挂起）」任务数一致（服务重启一致性）。

并发名额（acquire / release）在 ArticleService 中实现（与文章创建/终态同事务），
本服务不重复实现，仅提供结算与对账。
"""

from __future__ import annotations

from typing import Optional

from databases import Database

from app.constants.points import PointsConstant
from app.constants.user import UserConstant
from app.services.model_usage_service import get_usage_context, usage_recorder
from app.services.points_service import PointsService
from app.services.pricing_service import PricingService
from app.utils.logger import logger


class SettlementService:
    """积分结算服务。

    Attributes:
        db: 异步数据库连接。
    """

    def __init__(self, db: Database):
        """初始化积分结算服务。

        Args:
            db: databases 异步数据库连接实例。
        """
        self.db = db

    async def settle_current_segment(self, task_id: str) -> int:
        """结算某任务「上次结算点之后」的新增用量。

        流程：compute_unsettled（水位增量）→ PricingService.calculate_cost →
        同一事务内写 model_usage_record + 扣 user_points（USAGE_SETTLE 流水）→ 推进结算水位。

        Args:
            task_id: 任务 ID。

        Returns:
            本次扣除积分（无新增用量返回 0；admin 豁免扣费返回 0，但用量照常落库）。

        Raises:
            Exception: 落库/扣费失败时抛出（调用方决定重试/兜底；水位未推进，天然幂等可重试）。
        """
        ctx = get_usage_context()
        user_id = ctx.user_id if ctx else None
        if user_id is None:
            user_id = await self._resolve_user_id(task_id)
        if not user_id:
            logger.warning("结算跳过：无法解析任务 userId, taskId=%s", task_id)
            return 0

        delta = usage_recorder.compute_unsettled(task_id)
        if not delta:
            return 0

        pricing = PricingService(self.db)
        rows, total_points = await pricing.calculate_cost(delta)
        is_admin = await self._is_admin(user_id)

        async with self.db.transaction():
            if rows:
                # 显式补齐 userId（结算上下文已解析；与扣积分同一事务，用量与扣减原子一致）
                for row in rows:
                    row["userId"] = user_id
                await usage_recorder.write_rows(task_id, rows)
            if not is_admin and total_points > 0:
                await PointsService(self.db)._apply_change(
                    user_id=user_id,
                    amount=-total_points,
                    tx_type=PointsConstant.TX_USAGE_SETTLE,
                    description=f"文章生成积分结算（{total_points} 积分）",
                    task_id=task_id,
                )

        # 事务成功后才推进结算水位（失败回滚则水位不动，下次结算自动重试，防重复扣费）
        usage_recorder.mark_settled(task_id)
        logger.info(
            "任务段级结算完成 taskId=%s, userId=%s, costPoints=%s, isAdmin=%s",
            task_id, user_id, total_points, is_admin,
        )
        return 0 if is_admin else total_points

    # ---------------- 内部工具 ----------------

    async def _resolve_user_id(self, task_id: str) -> Optional[int]:
        """任务结算时回查 article 表补齐 userId。"""
        try:
            row = await self.db.fetch_one(
                query="SELECT userId FROM article WHERE taskId = :taskId",
                values={"taskId": task_id},
            )
            return int(row["userId"]) if row else None
        except Exception:
            logger.exception("结算 userId 回查失败 taskId=%s", task_id)
            return None

    async def _is_admin(self, user_id: int) -> bool:
        """判断用户是否为管理员（admin 豁免计费）。"""
        try:
            row = await self.db.fetch_one(
                query="SELECT userRole FROM user WHERE id = :userId AND isDelete = 0",
                values={"userId": user_id},
            )
            return bool(row and row["userRole"] == UserConstant.ADMIN_ROLE)
        except Exception:
            logger.exception("用户角色查询失败 userId=%s", user_id)
            return False


async def reconcile_active_task_counts() -> int:
    """启动对账：把 user.activeTaskCount 纠正为与 article 表「进行中（含挂起）」任务数一致。

    article 进行中任务 = status IN ('PENDING','PROCESSING') AND isDelete = 0。
    计数持久化在 MySQL，服务重启不丢；启动时对账修复历史漂移与僵尸任务计数。

    Returns:
        受影响（被纠正）的用户行数。
    """
    from app.database import database  # 函数体内 import，避免启动期循环导入

    try:
        result = await database.execute(
            query="""
                UPDATE user u
                SET activeTaskCount = (
                    SELECT COUNT(*) FROM article a
                    WHERE a.userId = u.id
                      AND a.status IN ('PENDING', 'PROCESSING')
                      AND a.isDelete = 0
                )
            """
        )
        logger.info("用户进行中任务数对账完成，受影响行数=%s", result)
        return result
    except Exception:
        logger.exception("用户进行中任务数对账失败")
        return 0