"""模型用量统计服务（M2 埋点 + M3 结算水位）。

负责在内存中按任务聚合各 LLM / AI 生图模型的调用用量，并按「计费段」增量结算落库：

  - 文本类 LLM：由 llm_factory 各 provider 统一挂载的 TokenUsageCallbackHandler
    自动上报（BaseAgent / 信息采集主/子 Agent / SVG 示意图均覆盖）；
  - 图片类：智谱 / Nano Banana 服务在每次生成后按张上报 imageCount。

调用上下文：通过 ContextVar 传递 task_id / user_id / agent_name。
article_async_service.start/resume 设置 task_id + user_id，
各统计点再以 usage_context 覆盖 agent_name（未提供的字段继承外层）。

结算水位（M3）：
  - _aggregates 保存任务累计用量，_settled 保存「已结算水位」快照；
  - compute_unsettled() 返回「上次结算点之后」的新增用量（当前累计 - 水位）；
  - 段级结算成功后 mark_settled() 推进水位；结算事务失败则水位不动，下次结算重试，天然幂等；
  - 任务终态（finalize / _handle_failure / delete）由结算服务 settle 剩余用量后 drop() 清理内存。
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.database import database
from app.utils.logger import logger


# ==================== 调用上下文（ContextVar） ====================


@dataclass
class UsageContext:
    """一次 LLM / 生图调用所属的业务上下文。

    Attributes:
        task_id: 文章任务 ID（生成类任务必填）。
        user_id: 用户 ID。
        agent_name: 统计点名称（如 title / outline / info_collector_main）。
    """

    task_id: Optional[str] = None
    user_id: Optional[int] = None
    agent_name: Optional[str] = None


_USAGE_CONTEXT: ContextVar[Optional[UsageContext]] = ContextVar(
    "usage_context", default=None
)


def get_usage_context() -> Optional[UsageContext]:
    """读取当前协程的用量上下文。

    Returns:
        当前 UsageContext；未设置时返回 None。
    """
    return _USAGE_CONTEXT.get()


@contextmanager
def usage_context(
    task_id: Optional[str] = None,
    user_id: Optional[int] = None,
    agent_name: Optional[str] = None,
):
    """设置用量上下文（支持嵌套覆盖，未提供的字段继承外层上下文）。

    Args:
        task_id: 任务 ID，None 时继承外层。
        user_id: 用户 ID，None 时继承外层。
        agent_name: 统计点名称，None 时继承外层。

    Yields:
        合并后的 UsageContext。
    """
    prev = _USAGE_CONTEXT.get()
    base = prev or UsageContext()
    ctx = UsageContext(
        task_id=task_id if task_id is not None else base.task_id,
        user_id=user_id if user_id is not None else base.user_id,
        agent_name=agent_name if agent_name is not None else base.agent_name,
    )
    token = _USAGE_CONTEXT.set(ctx)
    try:
        yield ctx
    finally:
        _USAGE_CONTEXT.reset(token)


# ==================== 任务级聚合器 ====================


@dataclass
class UsageAccumulator:
    """单个统计键（category+provider+model+agentName）的用量聚合结果。

    Attributes:
        category: 类别（LLM / IMAGE）。
        provider: 提供商。
        model: 模型名。
        agent_name: 统计点名称。
        call_count: 累计调用次数。
        input_tokens: 累计输入 token。
        output_tokens: 累计输出 token。
        image_count: 累计生成图片张数。
        status: SUCCESS / FAILED（任一失败调用则整体标记 FAILED）。
        user_id: 用户 ID（首个带 user_id 的记录写入）。
        start_time: 首次调用开始时间。
        end_time: 末次调用结束时间。
    """

    category: str
    provider: str
    model: str
    agent_name: Optional[str]
    call_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    image_count: int = 0
    status: str = "SUCCESS"
    user_id: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


# 结算水位：每个统计键已结算的 (callCount, inputTokens, outputTokens, imageCount)
SettledKey = Tuple[str, str, str, str]
SettledSnapshot = Tuple[int, int, int, int]


class UsageRecorder:
    """任务级用量聚合器 + 结算水位。

    Attributes:
        _aggregates: taskId → {(category, provider, model, agentName): UsageAccumulator}。
        _settled: taskId → {统计键: 已结算水位快照}。
    """

    def __init__(self) -> None:
        """初始化空聚合字典与空结算水位。"""
        self._aggregates: Dict[str, Dict[SettledKey, UsageAccumulator]] = {}
        self._settled: Dict[str, Dict[SettledKey, SettledSnapshot]] = {}

    # ---------------- 上报入口 ----------------

    def record_llm(
        self,
        *,
        provider: str,
        model: str,
        agent_name: Optional[str],
        input_tokens: int,
        output_tokens: int,
        status: str = "SUCCESS",
    ) -> None:
        """上报一次 LLM 调用用量（由 TokenUsageCallbackHandler 调用）。

        Args:
            provider: 提供商（Xiaomi/DeepSeek）。
            model: 模型名。
            agent_name: 统计点名称。
            input_tokens: 输入 token 数。
            output_tokens: 输出 token 数。
            status: SUCCESS / FAILED。
        """
        ctx = get_usage_context()
        if not ctx or not ctx.task_id:
            # 无任务上下文（如单点调试/测试）不记录，避免孤儿数据
            return
        self._add(
            ctx,
            category="LLM",
            provider=provider,
            model=model,
            agent_name=agent_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            status=status,
        )

    def record_image(
        self,
        *,
        provider: str,
        model: str,
        agent_name: Optional[str] = None,
        image_count: int = 1,
        status: str = "SUCCESS",
    ) -> None:
        """上报一次 AI 生图用量（智谱 / Nano Banana 服务成功/失败时调用）。

        Args:
            provider: 提供商（Zhipu/NanoBanana）。
            model: 模型名。
            agent_name: 统计点名称。
            image_count: 成功生成张数（成功=1，失败=0）。
            status: SUCCESS / FAILED。
        """
        ctx = get_usage_context()
        if not ctx or not ctx.task_id:
            return
        self._add(
            ctx,
            category="IMAGE",
            provider=provider,
            model=model,
            agent_name=agent_name,
            image_count=image_count,
            status=status,
        )

    # ---------------- 内部聚合 ----------------

    def _add(
        self,
        ctx: UsageContext,
        *,
        category: str,
        provider: str,
        model: str,
        agent_name: Optional[str],
        input_tokens: int = 0,
        output_tokens: int = 0,
        image_count: int = 0,
        status: str = "SUCCESS",
    ) -> None:
        """把一次调用聚合进当前任务的对应统计键。"""
        key = (category, provider, model, agent_name or "")
        bucket = self._aggregates.setdefault(ctx.task_id or "", {})
        acc = bucket.get(key)
        now = datetime.now()
        if acc is None:
            acc = UsageAccumulator(
                category=category,
                provider=provider,
                model=model,
                agent_name=agent_name,
            )
            bucket[key] = acc
        acc.call_count += 1
        acc.input_tokens += input_tokens
        acc.output_tokens += output_tokens
        acc.image_count += image_count
        if status == "FAILED":
            acc.status = "FAILED"
        if acc.user_id is None and ctx.user_id is not None:
            acc.user_id = ctx.user_id
        if acc.start_time is None:
            acc.start_time = now
        acc.end_time = now

    # ---------------- 查询 / 结算水位 ----------------

    def get_usage(self, task_id: str) -> List[UsageAccumulator]:
        """查看某任务当前聚合结果（调试/测试用，不弹出）。

        Args:
            task_id: 任务 ID。

        Returns:
            聚合结果列表。
        """
        return list((self._aggregates.get(task_id) or {}).values())

    def compute_unsettled(self, task_id: str) -> List[UsageAccumulator]:
        """计算某任务「上次结算点之后」的新增用量（不弹出、不推进水位）。

        Args:
            task_id: 任务 ID。

        Returns:
            新增用量聚合列表（仅含有用量的统计键）；无新增返回空列表。
        """
        bucket = self._aggregates.get(task_id)
        if not bucket:
            return []
        settled = self._settled.get(task_id) or {}
        result: List[UsageAccumulator] = []
        for key, acc in bucket.items():
            base = settled.get(key, (0, 0, 0, 0))
            delta_call = acc.call_count - base[0]
            delta_input = acc.input_tokens - base[1]
            delta_output = acc.output_tokens - base[2]
            delta_image = acc.image_count - base[3]
            if delta_call <= 0 and delta_input <= 0 and delta_output <= 0 and delta_image <= 0:
                continue
            result.append(
                UsageAccumulator(
                    category=acc.category,
                    provider=acc.provider,
                    model=acc.model,
                    agent_name=acc.agent_name,
                    call_count=delta_call,
                    input_tokens=delta_input,
                    output_tokens=delta_output,
                    image_count=delta_image,
                    status=acc.status,
                    user_id=acc.user_id,
                    start_time=acc.start_time,
                    end_time=acc.end_time,
                )
            )
        return result

    def mark_settled(self, task_id: str) -> None:
        """把当前累计推进为结算水位（结算事务成功后调用）。

        Args:
            task_id: 任务 ID。
        """
        bucket = self._aggregates.get(task_id)
        if not bucket:
            return
        self._settled[task_id] = {
            key: (acc.call_count, acc.input_tokens, acc.output_tokens, acc.image_count)
            for key, acc in bucket.items()
        }

    async def write_rows(self, task_id: str, rows: List[Dict[str, Any]]) -> int:
        """把「本次结算的增量用量行」落库到 model_usage_record。

        在调用方事务内执行（与扣积分同一事务，保证用量记录与积分扣减原子一致）。

        Args:
            task_id: 任务 ID。
            rows: PricingService.calculate_cost 返回的行字典（含 costPoints，缺 userId/taskId）。

        Returns:
            写入条数。
        """
        if not rows:
            return 0

        fallback_user_id: Optional[int] = None
        for row in rows:
            if not row.get("userId"):
                if fallback_user_id is None:
                    fallback_user_id = await self._resolve_user_id(task_id)
                row["userId"] = fallback_user_id
            row["taskId"] = task_id

        try:
            await database.execute_many(
                query="""
                    INSERT INTO model_usage_record (
                        userId, taskId, category, provider, model, agentName,
                        callCount, inputTokens, outputTokens, imageCount,
                        costPoints, status, startTime, endTime
                    )
                    VALUES (
                        :userId, :taskId, :category, :provider, :model, :agentName,
                        :callCount, :inputTokens, :outputTokens, :imageCount,
                        :costPoints, :status, :startTime, :endTime
                    )
                """,
                values=rows,
            )
        except Exception:
            logger.exception("模型用量落库失败 taskId=%s, rows=%s", task_id, len(rows))
            raise
        logger.info("模型用量增量落库完成 taskId=%s, records=%s", task_id, len(rows))
        return len(rows)

    def drop(self, task_id: str) -> None:
        """任务终态清理：清空内存聚合与结算水位（结算完成后调用）。

        Args:
            task_id: 任务 ID。
        """
        self._aggregates.pop(task_id, None)
        self._settled.pop(task_id, None)

    async def _resolve_user_id(self, task_id: str) -> Optional[int]:
        """任务缺失 userId 时回查 article 表补齐。"""
        try:
            row = await database.fetch_one(
                query="SELECT userId FROM article WHERE taskId = :taskId",
                values={"taskId": task_id},
            )
            return int(row["userId"]) if row else None
        except Exception:
            logger.exception("任务 userId 回查失败 taskId=%s", task_id)
            return None


# 全局单例：任务级聚合 + 结算水位
usage_recorder = UsageRecorder()