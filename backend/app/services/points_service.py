"""积分服务。

M1 提供：账户初始化（ensure_account）、积分发放/扣减（grant_points）、余额查询（get_balance）。
M3 扩展：段级结算（settle_usage，允许负余额、后付费扣费）；grant_points 重构为
「_apply_change（行锁 + 流水 + 冗余字段同步，单事务原子）」+ 公共包装。

设计说明（v1.3 后付费段级结算）：
  - 创建不预扣、不估算；任务运行按实际用量在每个计费段边界即时结算；
  - 余额允许为负（最多透支 max_debt_points），透支护栏在路由层/续跑前复查；
  - 所有余额变动均通过 _apply_change 走「行锁更新 + 流水记账 + 冗余字段同步」的单事务流程，
    保证余额与流水一致。
"""

from typing import Optional

from databases import Database

from app.constants.points import PointsConstant
from app.utils.logger import logger


class PointsService:
    """积分服务。

    负责用户积分账户的增改查，所有余额变动均通过 _apply_change 走「行锁更新 + 流水记账 +
    冗余字段同步」的单事务流程，保证余额与流水一致。

    Attributes:
        db: 异步数据库连接。
    """

    def __init__(self, db: Database):
        """初始化积分服务。

        Args:
            db: databases 异步数据库连接实例。
        """
        self.db = db

    async def ensure_account(self, user_id: int) -> None:
        """确保用户存在积分账户。

        账户不存在时创建一条余额为 0 的记录；已存在则不做任何操作（INSERT IGNORE 幂等）。

        Args:
            user_id: 用户 ID。
        """
        await self.db.execute(
            query="""
                INSERT IGNORE INTO user_points (userId, balance, totalEarned, totalConsumed, version, createTime, updateTime)
                VALUES (:userId, 0, 0, 0, 0, NOW(), NOW())
            """,
            values={"userId": user_id},
        )

    async def get_balance(self, user_id: int) -> int:
        """查询用户当前积分余额。

        Args:
            user_id: 用户 ID。

        Returns:
            当前积分余额；无账户时先建账户并返回 0。
        """
        await self.ensure_account(user_id)
        row = await self.db.fetch_one(
            query="SELECT balance FROM user_points WHERE userId = :userId",
            values={"userId": user_id},
        )
        return int(row["balance"]) if row else 0

    async def grant_points(
        self,
        user_id: int,
        amount: int,
        tx_type: str,
        description: str,
        task_id: Optional[str] = None,
    ) -> int:
        """发放/扣减积分（amount 可正可负，独立事务），返回变动后余额。

        Args:
            user_id: 用户 ID。
            amount: 变动积分，正数=获得，负数=消耗；为 0 时直接返回当前余额。
            tx_type: 流水类型，取 PointsConstant.TX_* 常量。
            description: 流水描述（用于积分明细展示）。
            task_id: 关联任务 ID，可选（生成类流水必填）。

        Returns:
            变动后的积分余额。

        Raises:
            Exception: 任一数据库步骤失败时整个事务回滚（由上层统一处理）。
        """
        if amount == 0:
            return await self.get_balance(user_id)
        async with self.db.transaction():
            return await self._apply_change(
                user_id=user_id,
                amount=amount,
                tx_type=tx_type,
                description=description,
                task_id=task_id,
            )

    async def settle_usage(
        self,
        user_id: int,
        task_id: str,
        cost_points: int,
        description: str,
    ) -> int:
        """段级结算扣费（后付费，允许负余额，独立事务），返回变动后余额。

        等价于 grant_points(user_id, -cost_points, TX_USAGE_SETTLE, ...)，
        独立成方法便于语义化调用；如需与用量落库合并同一事务，可调用 _apply_change。

        Args:
            user_id: 用户 ID。
            task_id: 关联任务 ID（必填）。
            cost_points: 本次结算消耗积分（>0 才扣费）。
            description: 流水描述。

        Returns:
            变动后的积分余额。
        """
        if cost_points <= 0:
            return await self.get_balance(user_id)
        async with self.db.transaction():
            return await self._apply_change(
                user_id=user_id,
                amount=-cost_points,
                tx_type=PointsConstant.TX_USAGE_SETTLE,
                description=description,
                task_id=task_id,
            )

    async def _apply_change(
        self,
        user_id: int,
        amount: int,
        tx_type: str,
        description: str,
        task_id: Optional[str] = None,
    ) -> int:
        """在调用方事务内完成一次积分变动，返回变动后余额。

        同一事务内完成：行锁读取余额 → 更新 user_points（含乐观锁版本号自增）→
        写入 points_transaction 流水 → 同步 user.points 冗余展示字段。

        Args:
            user_id: 用户 ID。
            amount: 变动积分，正数=获得，负数=消耗。
            tx_type: 流水类型。
            description: 流水描述。
            task_id: 关联任务 ID，可选。

        Returns:
            变动后的积分余额。

        Raises:
            Exception: 任一数据库步骤失败时整个事务回滚（由调用方事务统一回滚）。
        """
        if amount == 0:
            row = await self.db.fetch_one(
                query="SELECT balance FROM user_points WHERE userId = :userId",
                values={"userId": user_id},
            )
            return int(row["balance"]) if row else 0

        await self.ensure_account(user_id)
        row = await self.db.fetch_one(
            query="""
                SELECT balance FROM user_points WHERE userId = :userId FOR UPDATE
            """,
            values={"userId": user_id},
        )
        if not row:
            # 兜底：并发下 ensure_account 的 INSERT IGNORE 可能未生效，再补一次
            await self.ensure_account(user_id)
            row = await self.db.fetch_one(
                query="""
                    SELECT balance FROM user_points WHERE userId = :userId FOR UPDATE
                """,
                values={"userId": user_id},
            )
        current = int(row["balance"]) if row else 0
        new_balance = current + amount

        await self.db.execute(
            query="""
                UPDATE user_points
                SET balance = :balance,
                    totalEarned = totalEarned + :earned,
                    totalConsumed = totalConsumed + :consumed,
                    version = version + 1,
                    updateTime = NOW()
                WHERE userId = :userId
            """,
            values={
                "balance": new_balance,
                "earned": amount if amount > 0 else 0,
                "consumed": -amount if amount < 0 else 0,
                "userId": user_id,
            },
        )

        await self.db.execute(
            query="""
                INSERT INTO points_transaction (userId, taskId, type, amount, balanceAfter, description, createTime)
                VALUES (:userId, :taskId, :type, :amount, :balanceAfter, :description, NOW())
            """,
            values={
                "userId": user_id,
                "taskId": task_id,
                "type": tx_type,
                "amount": amount,
                "balanceAfter": new_balance,
                "description": description,
            },
        )

        # 同步 user.points 冗余展示字段（权威以 user_points 为准）
        await self.db.execute(
            query="UPDATE user SET points = :points WHERE id = :userId",
            values={"points": new_balance, "userId": user_id},
        )

        logger.info(
            "积分变动 userId=%s, type=%s, amount=%s, balanceAfter=%s, description=%s",
            user_id, tx_type, amount, new_balance, description,
        )
        return new_balance