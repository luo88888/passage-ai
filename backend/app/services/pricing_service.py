"""模型计价服务（M3：积分计算与结算之计价部分）。

负责按 model_pricing 配置把一段用量（UsageAccumulator 列表）换算成积分：
  - LLM：cost = inputTokens/1000 * inputPricePer1k + outputTokens/1000 * outputPricePer1k
  - IMAGE：cost = imageCount * pricePerImage
  - 匹配优先级：(category, provider, model, agentName) 精确 → (category, provider, model, '')
    → (category, provider, '*', '') 兜底；未命中按系统默认单价（LLM 输入 1 / 输出 2，IMAGE 0）
  - 计费段内各模型成本汇总后一次性向上取整（有消耗但不足 1 积分按 1 积分），避免逐次取整放大成本；
    每条记录按「最大余数法」分摊 costPoints，保证 sum(costPoints) == 本段扣除积分（对账一致性）
  - FAILED 状态不计费（costPoints=0），但用量照常落库供统计

规则来源：docs/积分系统开发计划.md v1.3 的 6.1 计价规则。
"""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal
from typing import Any, Dict, List, Optional, Tuple

from databases import Database
from databases.interfaces import Record

from app.services.model_usage_service import UsageAccumulator
from app.utils.logger import logger

# 系统默认单价（model_pricing 未命中时的兜底，与种子数据的 LLM * 兜底一致）
_DEFAULT_LLM_INPUT_PRICE = Decimal("1")
_DEFAULT_LLM_OUTPUT_PRICE = Decimal("2")
_DEFAULT_IMAGE_PRICE = Decimal("0") # NOTE: AI 生图默认免费


class PricingService:
    """模型计价服务。

    Attributes:
        db: 异步数据库连接。
        _pricing_cache: (category, provider, model, agentName) → 计价行缓存（单次结算内复用）。
    """

    def __init__(self, db: Database) -> None:
        """初始化计价服务。

        Args:
            db: databases 异步数据库连接实例。
        """
        self.db = db
        self._pricing_cache: Dict[Tuple[str, str, str, str], Optional[Record]] = {}

    async def calculate_cost(
        self,
        usage_list: List[UsageAccumulator],
    ) -> Tuple[List[Dict[str, Any]], int]:
        """把一段用量换算成积分（计费段级汇总一次取整）。

        Args:
            usage_list: 本次计费段的新增用量（UsageRecorder.compute_unsettled 的结果）。

        Returns:
            (rows, total_points)：
                rows: 与 model_usage_record 列对应的行字典（含 costPoints，不含 userId/taskId，
                    由结算服务补齐），各行 costPoints 按最大余数法分摊，
                    保证 sum(costPoints) == total_points；
                total_points: 本段总扣除积分（ceil(总成本)，有消耗但不足 1 积分按 1 积分；
                    全免费/全失败时为 0）。
        """
        items: List[Tuple[UsageAccumulator, Decimal]] = []
        total_cost = Decimal("0")
        for acc in usage_list:
            cost = await self._calc_one(acc)
            items.append((acc, cost))
            total_cost += cost

        total_points = 0
        if total_cost > 0:
            total_points = int(total_cost.to_integral_value(rounding=ROUND_CEILING))

        rows = self._allocate_cost_points(items, total_points)
        logger.info(
            "计价完成 usageCount=%s, totalCost=%s, totalPoints=%s",
            len(usage_list), total_cost, total_points,
        )
        return rows, total_points

    # ---------------- 单条计价 ----------------

    async def _calc_one(self, acc: UsageAccumulator) -> Decimal:
        """计算单条聚合用量成本。

        Args:
            acc: 单条聚合用量。

        Returns:
            该条用量成本（积分，可为小数）；FAILED 调用不计费返回 0。
        """
        if acc.status == "FAILED":
            return Decimal("0")
        pricing = await self._find_pricing(
            acc.category, acc.provider, acc.model, acc.agent_name
        )

        if acc.category == "IMAGE":
            price_per_image = _DEFAULT_IMAGE_PRICE
            if pricing and pricing["pricePerImage"] is not None:
                price_per_image = Decimal(str(pricing["pricePerImage"]))
            return Decimal(acc.image_count or 0) * price_per_image

        # LLM（其余类别一律按 LLM 计价规则处理）
        input_price = _DEFAULT_LLM_INPUT_PRICE
        output_price = _DEFAULT_LLM_OUTPUT_PRICE
        if pricing:
            if pricing["inputPricePer1k"] is not None:
                input_price = Decimal(str(pricing["inputPricePer1k"]))
            if pricing["outputPricePer1k"] is not None:
                output_price = Decimal(str(pricing["outputPricePer1k"]))
        input_cost = (Decimal(acc.input_tokens or 0) / Decimal(1000)) * input_price
        output_cost = (Decimal(acc.output_tokens or 0) / Decimal(1000)) * output_price
        return input_cost + output_cost

    async def _find_pricing(
        self,
        category: str,
        provider: str,
        model: str,
        agent_name: Optional[str],
    ) -> Optional[Record]:
        """按匹配优先级查找启用中的计价配置。

        优先级（见计划 6.1）：
            (category, provider, model, agentName) 精确
            → (category, provider, model, '') 不限智能体
            → (category, provider, '*', '') 模型通配兜底
        provider 列无通配（LLM 的 * 兜底行 provider='*' 在第三级被匹配到）。

        Args:
            category: 类别（LLM / IMAGE）。
            provider: 提供商。
            model: 模型名。
            agent_name: 智能体名称（可空）。

        Returns:
            命中的计价行（Record）；未命中返回 None。
        """
        agent = agent_name or ""
        candidates = [
            (category, provider, model, agent),
            (category, provider, model, ""),
            (category, provider, "*", ""),
        ]
        for cat, prov, mdl, ag in candidates:
            key = (cat, prov, mdl, ag)
            if key in self._pricing_cache:
                return self._pricing_cache[key]
            row = await self.db.fetch_one(
                """
                    SELECT inputPricePer1k, outputPricePer1k, pricePerImage
                    FROM model_pricing
                    WHERE category = :category AND provider = :provider
                      AND model = :model AND agentName = :agentName AND enabled = 1
                    ORDER BY id ASC
                    LIMIT 1
                """,
                values={
                    "category": cat,
                    "provider": prov,
                    "model": mdl,
                    "agentName": ag,
                },
            )
            self._pricing_cache[key] = row
            if row:
                return row
        return None

    # ---------------- 积分分摊 ----------------

    @staticmethod
    def _allocate_cost_points(
        items: List[Tuple[UsageAccumulator, Decimal]],
        total_points: int,
    ) -> List[Dict[str, Any]]:
        """按最大余数法把 total_points 分摊到各条用量，构造 model_usage_record 行。

        先给每条按 floor(cost) 分配，再把取整余数按小数部分从大到小逐个 +1
        （仅分给有成本的行），保证 sum(costPoints) == total_points。

        Args:
            items: (用量聚合, 本模型成本) 列表。
            total_points: 本段总扣除积分。

        Returns:
            model_usage_record 行字典列表（含 costPoints，不含 userId/taskId）。
        """
        n = len(items)
        floors = [int(cost) for _, cost in items]  # Decimal 正数向下取整
        remainder = total_points - sum(floors)
        extra = [0] * n
        if remainder > 0:
            order = sorted(
                range(n),
                key=lambda i: (items[i][1] - Decimal(floors[i]), i),
                reverse=True,
            )
            for i in order:
                if remainder <= 0:
                    break
                if items[i][1] > 0:
                    extra[i] += 1
                    remainder -= 1

        rows: List[Dict[str, Any]] = []
        for i, (acc, _cost) in enumerate(items):
            rows.append(
                {
                    "category": acc.category,
                    "provider": acc.provider,
                    "model": acc.model,
                    "agentName": acc.agent_name,
                    "callCount": acc.call_count,
                    "inputTokens": acc.input_tokens,
                    "outputTokens": acc.output_tokens,
                    "imageCount": acc.image_count,
                    "costPoints": floors[i] + extra[i],
                    "status": acc.status,
                    "startTime": acc.start_time,
                    "endTime": acc.end_time,
                }
            )
        return rows