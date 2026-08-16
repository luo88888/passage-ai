"""积分服务"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from databases import Database

from app.constants.points import PointsConstant
from app.exceptions import BusinessException, ErrorCode, throw_if, throw_if_not
from app.redis import get_client
from app.schemas.points import (
    AdminUsageQueryRequest,
    ModelPricingSaveRequest,
    ModelPricingUpdateRequest,
    ModelPricingVO,
    ModelUsageRecordVO,
    ModelUsageStatsVO,
    PointsBalanceVO,
    PointsCheckinVO,
    PointsOverviewVO,
    PointsTransactionQueryRequest,
    PointsTransactionVO,
    PointsUsageStatsQueryRequest,
)
from app.utils.logger import logger


# 签到/看板统计按北京时区（Asia/Shanghai）自然日刷新：
# 中国无夏令时，固定 UTC+8（不依赖 tzdata，Windows 下 zoneinfo 不可用）；
# 无论服务器部署在哪个时区，每天北京时间 00:00 后即为新的一天，可再次签到。
SHANGHAI_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


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

    # ==================== 账户基础 ====================

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

    async def get_balance_vo(self, user_id: int) -> PointsBalanceVO:
        """查询积分余额视图对象（余额 + 累计获得/消耗 + 今日签到状态）。

        Args:
            user_id: 用户 ID。

        Returns:
            PointsBalanceVO。
        """
        await self.ensure_account(user_id)
        row = await self.db.fetch_one(
            query="""
                SELECT balance, totalEarned, totalConsumed
                FROM user_points WHERE userId = :userId
            """,
            values={"userId": user_id},
        )
        balance = int(row["balance"]) if row else 0
        total_earned = int(row["totalEarned"]) if row else 0
        total_consumed = int(row["totalConsumed"]) if row else 0
        return PointsBalanceVO(
            balance=balance,
            totalEarned=total_earned,
            totalConsumed=total_consumed,
            checkedInToday=await self.is_checked_in_today(user_id),
        )

    # ==================== 积分变动（单事务原子） ====================

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

    async def adjust_points(
        self,
        user_id: int,
        amount: int,
        description: str,
    ) -> int:
        """管理员手工调整用户积分（正=赠送，负=扣减，独立事务），返回变动后余额。

        Args:
            user_id: 目标用户 ID。
            amount: 调整积分（不允许 0）。
            description: 调整说明（写入流水描述）。

        Returns:
            变动后的积分余额。

        Raises:
            BusinessException: amount 为 0 时抛 PARAMS_ERROR。
        """
        throw_if(amount == 0, ErrorCode.PARAMS_ERROR, "调整积分不能为 0")
        async with self.db.transaction():
            return await self._apply_change(
                user_id=user_id,
                amount=amount,
                tx_type=PointsConstant.TX_ADMIN_ADJUST,
                description=description,
            )

    # ==================== 每日签到 ====================

    @staticmethod
    def _get_today_str() -> str:
        """获取北京时区（Asia/Shanghai）的当天日期字符串 YYYY-MM-DD。

        签到按北京自然日刷新，不依赖服务器本地时区；
        服务器时区漂移不会改变「每天北京时间 0 点后可再次签到」的刷新点。

        Returns:
            当天日期字符串（YYYY-MM-DD）。
        """
        return datetime.now(SHANGHAI_TZ).strftime("%Y-%m-%d")

    @staticmethod
    def _checkin_redis_key(user_id: int, day: str) -> str:
        """构造签到 Redis 幂等键。

        Args:
            user_id: 用户 ID。
            day: 日期字符串 YYYY-MM-DD。

        Returns:
            Redis key。
        """
        return f"checkin:{user_id}:{day}"

    async def is_checked_in_today(self, user_id: int) -> bool:
        """今日是否已签到（Redis key 是否存在）。

        Args:
            user_id: 用户 ID。

        Returns:
            True=今日已签到；Redis 不可用时返回 False（放行，实际签到由 SETNX 兜底）。
        """
        redis = get_client()
        if not redis:
            return False
        today = self._get_today_str()
        return bool(await redis.exists(self._checkin_redis_key(user_id, today)))

    async def checkin(self, user_id: int) -> PointsCheckinVO:
        """每日签到：Redis SETNX 防重复 + 赠送积分（TX_SIGN_IN 流水）。

        签到不限制余额（欠费用户签到回正后可再创作）。

        Args:
            user_id: 用户 ID。

        Returns:
            PointsCheckinVO（本次赠送积分 + 签到后余额）。

        Raises:
            BusinessException: 今日已签到（OPERATION_ERROR）；Redis 不可用（SYSTEM_ERROR）。
        """
        redis = get_client()
        if not redis:
            raise BusinessException(ErrorCode.SYSTEM_ERROR, "签到服务暂不可用，请稍后再试")
        today = self._get_today_str()
        key = self._checkin_redis_key(user_id, today)
        acquired = await redis.set(key, "1", nx=True, ex=86400 * 2)
        if not acquired:
            raise BusinessException(ErrorCode.OPERATION_ERROR, "今日已签到，明天再来吧")

        try:
            balance = await self.grant_points(
                user_id=user_id,
                amount=PointsConstant.SIGN_IN_POINTS,
                tx_type=PointsConstant.TX_SIGN_IN,
                description="每日签到赠送积分",
            )
        except Exception:
            # 发放失败回滚签到标记，允许用户重试（best-effort）
            try:
                await redis.delete(key)
            except Exception:
                logger.exception("签到标记回滚失败 userId=%s", user_id)
            raise

        logger.info("用户签到成功 userId=%s, gained=%s, balance=%s", user_id, PointsConstant.SIGN_IN_POINTS, balance)
        return PointsCheckinVO(
            checkedIn=True,
            gained=PointsConstant.SIGN_IN_POINTS,
            balance=balance,
        )

    # ==================== 积分明细 ====================

    async def list_transactions(
        self,
        user_id: int,
        query: PointsTransactionQueryRequest,
    ) -> Tuple[List[PointsTransactionVO], int]:
        """分页查询用户积分流水（type/时间/金额筛选）。

        Args:
            user_id: 用户 ID。
            query: 分页 + 筛选条件。

        Returns:
            (流水 VO 列表, 总数)。
        """
        conditions = ["userId = :userId"]
        values: dict = {"userId": user_id}
        if query.type:
            conditions.append("type = :type")
            values["type"] = query.type
        if query.start_time:
            conditions.append("createTime >= :startTime")
            values["startTime"] = query.start_time
        if query.end_time:
            conditions.append("createTime <= :endTime")
            values["endTime"] = query.end_time
        if query.min_amount is not None:
            conditions.append("amount >= :minAmount")
            values["minAmount"] = query.min_amount
        if query.max_amount is not None:
            conditions.append("amount <= :maxAmount")
            values["maxAmount"] = query.max_amount

        where = " AND ".join(conditions)
        total = await self.db.fetch_val(
            query=f"SELECT COUNT(*) FROM points_transaction WHERE {where}",
            values=values,
        )
        rows = await self.db.fetch_all(
            query=f"""
                SELECT * FROM points_transaction
                WHERE {where}
                ORDER BY createTime DESC, id DESC
                LIMIT :limit OFFSET :offset
            """,
            values={
                **values,
                "limit": query.page_size,
                "offset": (query.current - 1) * query.page_size,
            },
        )
        items = [
            PointsTransactionVO(
                id=r["id"],
                userId=r["userId"],
                taskId=r["taskId"],
                type=r["type"],
                amount=r["amount"],
                balanceAfter=r["balanceAfter"],
                description=r["description"],
                createTime=r["createTime"].isoformat() if r["createTime"] else "",
            )
            for r in rows
        ]
        return items, int(total or 0)

    # ==================== 模型用量统计 ====================

    async def get_usage_stats(
        self,
        user_id: int,
        query: Optional[PointsUsageStatsQueryRequest] = None,
    ) -> List[ModelUsageStatsVO]:
        """按 (category, provider, model) 聚合用户各模型用量统计。

        Args:
            user_id: 用户 ID。
            query: 可选时间范围。

        Returns:
            模型用量聚合列表（按消耗积分倒序）。
        """
        conditions = ["userId = :userId"]
        values: dict = {"userId": user_id}
        if query:
            if query.start_time:
                conditions.append("createTime >= :startTime")
                values["startTime"] = query.start_time
            if query.end_time:
                conditions.append("createTime <= :endTime")
                values["endTime"] = query.end_time

        where = " AND ".join(conditions)
        rows = await self.db.fetch_all(
            query=f"""
                SELECT category, provider, model,
                       SUM(callCount) AS callCount,
                       SUM(COALESCE(inputTokens, 0)) AS inputTokens,
                       SUM(COALESCE(outputTokens, 0)) AS outputTokens,
                       SUM(COALESCE(imageCount, 0)) AS imageCount,
                       SUM(costPoints) AS costPoints
                FROM model_usage_record
                WHERE {where}
                GROUP BY category, provider, model
                ORDER BY costPoints DESC, callCount DESC
            """,
            values=values,
        )
        return [
            ModelUsageStatsVO(
                category=r["category"],
                provider=r["provider"],
                model=r["model"],
                callCount=int(r["callCount"] or 0),
                inputTokens=int(r["inputTokens"] or 0),
                outputTokens=int(r["outputTokens"] or 0),
                imageCount=int(r["imageCount"] or 0),
                costPoints=int(r["costPoints"] or 0),
            )
            for r in rows
        ]

    # ==================== 管理端 ====================

    async def get_overview(self) -> PointsOverviewVO:
        """全局积分/用量看板（管理端）。

        Returns:
            PointsOverviewVO。
        """

        row = await self.db.fetch_one(
            """
            SELECT
                COUNT(*)                       AS userCount,
                COALESCE(SUM(totalEarned), 0)  AS totalEarned,
                COALESCE(SUM(totalConsumed), 0) AS totalConsumed,
                COALESCE(SUM(balance), 0)      AS totalBalance
            FROM user_points
            """
        )
        assert row is not None  # 无 GROUP BY 的聚合查询恒返回一行
        user_count = int(row["userCount"])
        total_earned = int(row["totalEarned"])
        total_consumed = int(row["totalConsumed"])
        total_balance = int(row["totalBalance"])

        row = await self.db.fetch_one(
            """
            SELECT
                COUNT(*)                   AS usageRecordCount,
                COALESCE(SUM(costPoints), 0) AS totalCostPoints
            FROM model_usage_record
            """
        )
        assert row is not None  # 无 GROUP BY 的聚合查询恒返回一行
        usage_record_count = int(row["usageRecordCount"])
        total_cost_points = int(row["totalCostPoints"])

        today = self._get_today_str()
        row = await self.db.fetch_one(
            """
            SELECT
                COUNT(*)                  AS checkinCount,
                COALESCE(SUM(amount), 0)  AS checkinPoints
            FROM points_transaction
            WHERE type = :type AND createTime >= :today
            """,
            values={"type": PointsConstant.TX_SIGN_IN, "today": today},
        )
        assert row is not None  # 无 GROUP BY 的聚合查询恒返回一行
        today_checkin_count = int(row["checkinCount"])
        today_checkin_points = int(row["checkinPoints"])
        return PointsOverviewVO(
            userCount=user_count,
            totalEarned=total_earned,
            totalConsumed=total_consumed,
            totalBalance=total_balance,
            usageRecordCount=usage_record_count,
            totalCostPoints=total_cost_points,
            todayCheckinCount=today_checkin_count,
            todayCheckinPoints=today_checkin_points,
        )

    async def list_model_pricing(self) -> List[ModelPricingVO]:
        """查询全部模型计价配置（管理端）。

        Returns:
            计价配置列表。
        """
        rows = await self.db.fetch_all(
            query="SELECT * FROM model_pricing ORDER BY category, provider, model"
        )
        return [
            ModelPricingVO(
                id=r["id"],
                category=r["category"],
                provider=r["provider"],
                model=r["model"],
                agentName=r["agentName"] or "",
                inputPricePer1k=float(r["inputPricePer1k"] or 0),
                outputPricePer1k=float(r["outputPricePer1k"] or 0),
                pricePerImage=float(r["pricePerImage"] or 0),
                enabled=bool(r["enabled"]),
            )
            for r in rows
        ]

    async def create_model_pricing(self, request: ModelPricingSaveRequest) -> int:
        """新增模型计价配置（管理端）。

        Args:
            request: 新增请求。

        Returns:
            新配置 ID。

        Raises:
            BusinessException: 相同 (category, provider, model, agentName) 已存在。
        """
        agent = request.agent_name or ""
        existing = await self.db.fetch_one(
            query="""
                SELECT id FROM model_pricing
                WHERE category = :category AND provider = :provider
                  AND model = :model AND agentName = :agentName
            """,
            values={"category": request.category, "provider": request.provider, "model": request.model, "agentName": agent},
        )
        throw_if(existing, ErrorCode.OPERATION_ERROR, "相同计价配置已存在")
        new_id = await self.db.execute(
            query="""
                INSERT INTO model_pricing (category, provider, model, agentName, inputPricePer1k, outputPricePer1k, pricePerImage, enabled, updateTime)
                VALUES (:category, :provider, :model, :agentName, :inputPricePer1k, :outputPricePer1k, :pricePerImage, :enabled, NOW())
            """,
            values={
                "category": request.category,
                "provider": request.provider,
                "model": request.model,
                "agentName": agent,
                "inputPricePer1k": request.input_price_per_1k,
                "outputPricePer1k": request.output_price_per_1k,
                "pricePerImage": request.price_per_image,
                "enabled": 1 if request.enabled else 0,
            },
        )
        logger.info("新增模型计价 id=%s, model=%s", new_id, request.model)
        return new_id

    async def update_model_pricing(self, request: ModelPricingUpdateRequest) -> bool:
        """更新模型计价配置（管理端，按 id 全量更新）。

        Args:
            request: 更新请求（含 id）。

        Returns:
            True=更新成功。

        Raises:
            BusinessException: 配置不存在（NOT_FOUND_ERROR）。
        """
        existing = await self.db.fetch_one(
            query="SELECT id FROM model_pricing WHERE id = :id",
            values={"id": request.id},
        )
        throw_if_not(existing, ErrorCode.NOT_FOUND_ERROR, "计价配置不存在")
        agent = request.agent_name or ""
        await self.db.execute(
            query="""
                UPDATE model_pricing
                SET category = :category, provider = :provider, model = :model, agentName = :agentName,
                    inputPricePer1k = :inputPricePer1k, outputPricePer1k = :outputPricePer1k,
                    pricePerImage = :pricePerImage, enabled = :enabled, updateTime = NOW()
                WHERE id = :id
            """,
            values={
                "id": request.id,
                "category": request.category,
                "provider": request.provider,
                "model": request.model,
                "agentName": agent,
                "inputPricePer1k": request.input_price_per_1k,
                "outputPricePer1k": request.output_price_per_1k,
                "pricePerImage": request.price_per_image,
                "enabled": 1 if request.enabled else 0,
            },
        )
        logger.info("更新模型计价 id=%s", request.id)
        return True

    async def list_usage(
        self,
        query: AdminUsageQueryRequest,
    ) -> Tuple[List[ModelUsageRecordVO], int]:
        """分页查询模型用量记录（管理端，按用户/类别/模型/时间筛选）。

        Args:
            query: 分页 + 筛选条件。

        Returns:
            (用量记录 VO 列表, 总数)。
        """
        conditions: List[str] = []
        values: dict = {}
        if query.user_id:
            conditions.append("userId = :userId")
            values["userId"] = query.user_id
        if query.category:
            conditions.append("category = :category")
            values["category"] = query.category
        if query.model:
            conditions.append("model = :model")
            values["model"] = query.model
        if query.start_time:
            conditions.append("createTime >= :startTime")
            values["startTime"] = query.start_time
        if query.end_time:
            conditions.append("createTime <= :endTime")
            values["endTime"] = query.end_time

        where = " AND ".join(conditions) if conditions else "1 = 1"
        total = await self.db.fetch_val(
            query=f"SELECT COUNT(*) FROM model_usage_record WHERE {where}",
            values=values,
        )
        rows = await self.db.fetch_all(
            query=f"""
                SELECT * FROM model_usage_record
                WHERE {where}
                ORDER BY createTime DESC, id DESC
                LIMIT :limit OFFSET :offset
            """,
            values={
                **values,
                "limit": query.page_size,
                "offset": (query.current - 1) * query.page_size,
            },
        )
        items = [
            ModelUsageRecordVO(
                id=r["id"],
                userId=r["userId"],
                taskId=r["taskId"],
                category=r["category"],
                provider=r["provider"],
                model=r["model"],
                agentName=r["agentName"],
                callCount=r["callCount"],
                inputTokens=r["inputTokens"],
                outputTokens=r["outputTokens"],
                imageCount=r["imageCount"],
                costPoints=r["costPoints"],
                status=r["status"],
                startTime=r["startTime"].isoformat() if r["startTime"] else "",
                endTime=r["endTime"].isoformat() if r["endTime"] else None,
                createTime=r["createTime"].isoformat() if r["createTime"] else "",
            )
            for r in rows
        ]
        return items, int(total or 0)

    # ==================== 内部实现 ====================

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