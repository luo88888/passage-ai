"""
智能体基类，提供所有文本型 Agent 共享的能力
"""
from __future__ import annotations

import asyncio
import random
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
import json
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from app.config import settings
from app.constants.prompt import PromptConstant
from app.exceptions import (
    AgentMaxRetriesError,
    LLMOutputFormatError,
    LLMTransientError,
)
from app.services.model_usage_service import usage_context
from app.models.enums import (
    ArticleGenreEnum,
    ArticleLanguageStyleEnum,
    ArticleStyleEnum,
    RetryStageEnum,
    SseMessageTypeEnum,
)
from app.utils.logger import logger
from app.utils.json_tool import loads_with_repair

if TYPE_CHECKING:
    from app.services.agent_log_service import AgentLogService

# ==================== 瞬时错误识别 ====================

# 异常类型名中的瞬时错误关键词（超时 / 限流 / 连接中断 / 5xx 等，可重试）
_TRANSIENT_NAME_KEYWORDS = (
    "timeout",
    "timedout",
    "ratelimit",
    "rate_limit",
    "connection",
    "connecterror",
    "internalserver",
    "serviceunavailable",
    "unavailable",
    "overloaded",
    "temporary",
    "disconnected",
    "econnreset",
    "brokenpipe",
    "incompleteread",
    "networkerror",
    "remoteprotocol",
)

# 异常类型名中的配置/业务错误关键词（缺 Key、无效配置、余额不足等，不重试）
_NON_RETRYABLE_NAME_KEYWORDS = (
    "authentication",
    "unauthorized",
    "forbidden",
    "permission",
    "invalidrequest",
    "badrequest",
    "notfound",
    "keyerror",
    "valueerror",
    "typeerror",
    "attributeerror",
    "assertionerror",
    "notimplemented",
    "unsupported",
    "invalid_api_key",
    "apikey",
    "modelfeaturenotsupported",
)


# ==================== 模块级工具函数 ====================

def _safe_json_dumps(value: Optional[dict]) -> Optional[str]:
    """安全序列化 JSON"""
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return None


@asynccontextmanager
async def agent_log_context(
    agent_log_service: AgentLogService,
    task_id: Optional[str],
    agent_name: str,
    prompt: Optional[str] = None,
    input_data: Optional[dict] = None,
):
    """异步智能体日志上下文（模块级函数，可供任意类使用）"""
    start_time = datetime.now()
    log_data = {
        "taskId": task_id or "unknown",
        "agentName": agent_name,
        "startTime": start_time,
        "status": "RUNNING",
        "prompt": prompt,
        "inputData": _safe_json_dumps(input_data),
        "outputData": None,
        "errorMessage": None,
    }
    try:
        yield log_data
        log_data["status"] = "SUCCESS"
    except Exception as exc:
        log_data["status"] = "FAILED"
        log_data["errorMessage"] = str(exc)
        raise
    finally:
        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        log_data["endTime"] = end_time
        log_data["durationMs"] = duration_ms
        agent_log_service.save_log_async(log_data)


@contextmanager
def agent_log_context_sync(
    agent_log_service: AgentLogService,
    task_id: Optional[str],
    agent_name: str,
    prompt: Optional[str] = None,
    input_data: Optional[dict] = None,
):
    """同步智能体日志上下文（模块级函数，可供任意类使用）"""
    start_time = datetime.now()
    log_data = {
        "taskId": task_id or "unknown",
        "agentName": agent_name,
        "startTime": start_time,
        "status": "RUNNING",
        "prompt": prompt,
        "inputData": _safe_json_dumps(input_data),
        "outputData": None,
        "errorMessage": None,
    }
    try:
        yield log_data
        log_data["status"] = "SUCCESS"
    except Exception as exc:
        log_data["status"] = "FAILED"
        log_data["errorMessage"] = str(exc)
        raise
    finally:
        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        log_data["endTime"] = end_time
        log_data["durationMs"] = duration_ms
        agent_log_service.save_log_async(log_data)


class BaseAgent:
    """基础智能体类，提供 LLM 调用、JSON 解析、日志记录等共享能力"""

    def __init__(
        self,
        model: BaseChatModel,
        agent_log_service: AgentLogService,
        structured_model: Optional[Any] = None,
    ):
        """初始化基础智能体

        Args:
            model: 已配置好的 LangChain BaseChatModel 实例（由 llm_factory 创建）
            agent_log_service: 日志服务
            structured_model: 可选的结构化输出模型（Runnable，如 llm_factory 的
                DeepSeekStructuredModel / with_structured_output 结果），
                供 _call_structured_model 使用；未配置时调用会抛错
        """
        self.model = model
        self.agent_log_service = agent_log_service
        self.structured_model = structured_model

    # ==================== LLM 调用 ====================

    @staticmethod
    def _resolve_max_retry(max_retry: Optional[int]) -> int:
        """解析最大重试次数（不含首次尝试）。

        Args:
            max_retry: 调用方显式指定的重试次数；None 时取 settings.llm_max_attempts - 1。
        """
        if max_retry is not None:
            return max(0, int(max_retry))
        return max(0, settings.llm_max_attempts - 1)

    @staticmethod
    def _backoff_delay(attempt_no: int) -> float:
        """指数退避 + 抖动（attempt_no 从 1 开始）"""
        base = settings.llm_retry_base_seconds
        factor = settings.llm_retry_backoff_factor
        cap = settings.llm_retry_max_seconds
        delay = min(cap, base * (factor ** max(0, attempt_no - 1)))
        return max(0.0, delay * random.uniform(0.8, 1.2))

    @staticmethod
    def _is_format_error(exc: BaseException) -> bool:
        """判断异常是否为模型输出格式/校验错误（可带错误反馈重试）"""
        if isinstance(exc, LLMOutputFormatError):
            return True
        if isinstance(exc, (LLMTransientError, AgentMaxRetriesError)):
            return False
        # MiMo with_structured_output 解析失败为 OutputParserException，
        # 手写 JSON 解析 / pydantic 校验失败为 ValidationError
        return type(exc).__name__ in ("OutputParserException", "ValidationError")

    @staticmethod
    def _is_transient_error(exc: BaseException) -> bool:
        """判断异常是否为可重试的瞬时错误（超时、429、5xx、连接中断等）。

        非重试错误（缺 Key、无效配置、余额不足、参数错误、DB 失败等）返回 False；
        未知异常保守不重试，避免把业务/配置错误反复放大。
        """
        if isinstance(exc, LLMTransientError):
            return True
        if isinstance(exc, (LLMOutputFormatError, AgentMaxRetriesError)):
            return False

        # 1) 异常自带的状态码（openai / httpx 常见）
        for attr in ("status_code", "status"):
            status = getattr(exc, attr, None)
            if status is None:
                continue
            try:
                code = int(status)
            except (TypeError, ValueError):
                continue
            if code in (408, 409, 425, 429):
                return True
            if 500 <= code < 600:
                return True
            return False  # 其余 4xx 属非重试错误

        # 2) httpx.HTTPStatusError 包裹的响应状态码
        response = getattr(exc, "response", None)
        if response is not None:
            status = getattr(response, "status_code", None)
            if status is not None:
                try:
                    code = int(status)
                except (TypeError, ValueError):
                    code = 0
                if code == 429 or 500 <= code < 600:
                    return True

        # 3) 异常类型名启发式匹配
        name = type(exc).__name__.lower()
        if any(keyword in name for keyword in _TRANSIENT_NAME_KEYWORDS):
            return True
        if any(keyword in name for keyword in _NON_RETRYABLE_NAME_KEYWORDS):
            return False

        return False

    @staticmethod
    def _build_format_feedback_prompt(prompt: str, error: BaseException) -> str:
        """格式错误重试提示词：把上次校验错误（与可能的原始输出）拼回提示词。

        始终以原始 prompt 为基础拼接（而非在上一轮反馈上继续叠加），避免提示词无限膨胀。
        """
        raw_output = getattr(error, "raw_output", None)
        if isinstance(raw_output, str):
            raw_output = raw_output.strip()[:2000] or None
        feedback = (
            "\n\n========== 上次输出格式不符合要求，请修正 ==========\n"
            f"错误：{error}\n"
            "请重新输出，严格遵守格式要求，只返回符合要求的 JSON，"
            "不要输出 markdown 代码围栏、解释性文字或任何 JSON 之外的文本。\n"
        )
        if raw_output:
            feedback += f"上次输出：\n{raw_output}\n"
        return prompt + feedback

    @staticmethod
    def _emit_agent_retry(
        stream_handler: Optional[Callable[[Any], None]],
        stage: Optional[RetryStageEnum],
        message: str,
    ) -> None:
        """重试前发送 AGENT_RETRY SSE 信号（前端按 stage 清空对应阶段过程态）。

        stream_handler 为 make_emit 闭包（dict 直接透传）；为 None 或未指定 stage 时不发。
        """
        if stream_handler is None or stage is None:
            return
        try:
            stream_handler({
                "type": SseMessageTypeEnum.AGENT_RETRY.value,
                "stage": stage.value,
                "message": message,
            })
        except Exception:
            logger.exception("发送 AGENT_RETRY 失败, stage=%s", stage)

    async def _run_with_retry(
        self,
        *,
        prompt: str,
        agent_name: Optional[str],
        max_retry: Optional[int],
        attempt: Callable[[str, int], Awaitable[Any]],
        format_retry_attempts: Optional[int] = None,
        retry_stage: Optional[RetryStageEnum] = None,
        stream_handler: Optional[Callable[[Any], None]] = None,
        retry_message: Optional[str] = None,
        fallback_attempt: Optional[Callable[[str, int], Awaitable[Any]]] = None,
    ) -> Any:
        """通用 LLM 调用重试包装。

        重试规则：
          - 格式错误（LLMOutputFormatError / 可识别为格式错误的异常）：把上次校验错误
            拼回提示词重试，最多 format_retry_attempts 次，不等待退避；
          - 瞬时错误（LLMTransientError / 429 / 5xx / 超时等）：指数退避 + 抖动后原提示词重试；
          - 非重试错误（缺 Key、无效配置、余额不足等）：原样向上抛；
          - 重试耗尽后抛 AgentMaxRetriesError，供图节点做降级决策；
          - 配置了备用提供商且主模型预算耗尽时，先用备用提供商再尝试一次。

        Args:
            prompt: 原始用户提示词（格式错误重试时在其基础上追加错误反馈）。
            agent_name: 统计点名称（用于模型用量埋点与日志）。
            max_retry: 最大重试次数（不含首次尝试）；None 时取 settings.llm_max_attempts - 1。
            attempt: 单次尝试函数，签名 async (current_prompt, attempt_no) -> Any；
                抛格式/瞬时/非重试异常交由本方法分类处理。
            format_retry_attempts: 格式错误最多重试次数；None 时取 settings.llm_format_retry_attempts。
            retry_stage: 重试阶段（重试前经 stream_handler 发 AGENT_RETRY，None 不发）。
            stream_handler: SSE 回调（发 AGENT_RETRY 用，None 不发）。
            retry_message: AGENT_RETRY 自定义文案（None 用默认文案）。
            fallback_attempt: 备用提供商尝试函数（签名同 attempt；None 不启用备用）。

        Returns:
            单次尝试成功后的结果。

        Raises:
            AgentMaxRetriesError: 重试耗尽（含备用提供商也失败）。
            非重试异常: 原样向上抛。
        """
        total_attempts = 1 + self._resolve_max_retry(max_retry)
        format_limit = (
            settings.llm_format_retry_attempts
            if format_retry_attempts is None
            else format_retry_attempts
        )
        format_retries_used = 0
        fallback_used = False
        current_prompt = prompt

        for attempt_no in range(1, total_attempts + 1):
            try:
                return await attempt(current_prompt, attempt_no)
            except Exception as exc:
                if isinstance(exc, AgentMaxRetriesError):
                    raise
                is_format = self._is_format_error(exc)
                is_transient = self._is_transient_error(exc)
                if not is_format and not is_transient:
                    # 非重试错误（缺 Key、配置错误、余额不足、DB 失败等）原样抛出
                    raise

                # 主模型预算耗尽（总次数用尽 / 格式修正次数用尽）：尝试备用提供商或统一失败
                if attempt_no >= total_attempts or (
                    is_format and format_retries_used >= format_limit
                ):
                    if fallback_attempt is not None and not fallback_used:
                        fallback_used = True
                        logger.warning(
                            "%s 主模型重试耗尽，切换备用提供商, error=%s",
                            agent_name or "agent",
                            exc,
                        )
                        self._emit_agent_retry(
                            stream_handler,
                            retry_stage,
                            retry_message or (
                                f"{retry_stage.label}生成多次失败，正在切换备用模型重试"
                                if retry_stage else "LLM 多次失败，正在切换备用模型重试"
                            ),
                        )
                        try:
                            return await fallback_attempt(current_prompt, attempt_no)
                        except Exception as fallback_exc:
                            logger.error(
                                "%s 备用提供商调用失败, error=%s",
                                agent_name or "agent",
                                fallback_exc,
                                exc_info=True,
                            )
                            raise AgentMaxRetriesError(
                                f"LLM 调用重试耗尽（主模型与备用提供商均失败，"
                                f"最近错误: {fallback_exc}）",
                                attempts=attempt_no + 1,
                                last_error=fallback_exc,
                            ) from fallback_exc
                    raise AgentMaxRetriesError(
                        f"LLM 调用重试耗尽（共尝试 {attempt_no} 次，最近错误: {exc}）",
                        attempts=attempt_no,
                        last_error=exc,
                    ) from exc

                if is_format:
                    format_retries_used += 1
                    current_prompt = self._build_format_feedback_prompt(prompt, exc)
                    logger.warning(
                        "%s LLM 输出格式错误，第 %s/%s 次修正重试, error=%s",
                        agent_name or "agent",
                        format_retries_used,
                        format_limit,
                        exc,
                    )
                else:
                    logger.warning(
                        "%s LLM 瞬时错误，第 %s 次重试, error=%s",
                        agent_name or "agent",
                        attempt_no,
                        exc,
                    )

                # 重试前发 AGENT_RETRY（先于下一轮输出进入 SSE 历史，断线重放时顺序正确）
                self._emit_agent_retry(
                    stream_handler,
                    retry_stage,
                    retry_message or (
                        f"{retry_stage.label}生成异常，正在重试"
                        if retry_stage else "LLM 生成异常，正在重试"
                    ),
                )
                if not is_format:
                    await asyncio.sleep(self._backoff_delay(attempt_no))

        # 理论不可达（循环内已处理全部失败路径）
        raise AgentMaxRetriesError(
            f"LLM 调用重试耗尽（共尝试 {total_attempts} 次）", attempts=total_attempts
        )

    def _build_fallback_chat_attempt(
        self,
        agent_name: Optional[str],
        stream_handler: Optional[Callable[[Any], None]] = None,
        message_type: Optional[SseMessageTypeEnum] = None,
    ) -> Optional[Callable[[str, int], Awaitable[Any]]]:
        """构造备用提供商的普通调用尝试（未配置 llm_fallback_provider 时返回 None）。

        传入 stream_handler + message_type 时走流式，否则走非流式。
        """
        provider = settings.llm_fallback_provider
        if not provider:
            return None
        try:
            from app.llm_factory.factory import get_chat_model

            fallback_model = get_chat_model(
                provider=provider,
                model_name=settings.llm_fallback_model or None,
            )
        except Exception:
            logger.exception("创建备用 LLM 模型失败 provider=%s", provider)
            return None

        if stream_handler is not None and message_type is not None:
            async def _attempt_streaming(current_prompt: str, _attempt_no: int) -> str:
                content_builder = []
                with usage_context(agent_name=agent_name):
                    async for chunk in fallback_model.astream(
                        [HumanMessage(content=current_prompt)]
                    ):
                        if chunk.content:
                            content_builder.append(chunk.content)
                            stream_handler(
                                message_type.get_streaming_prefix() + chunk.content
                            )
                return "".join(content_builder)

            return _attempt_streaming

        async def _attempt(current_prompt: str, _attempt_no: int) -> str:
            with usage_context(agent_name=agent_name):
                response = await fallback_model.ainvoke(
                    [HumanMessage(content=current_prompt)]
                )
            return response.content  # type: ignore

        return _attempt

    def _build_fallback_structured_attempt(
        self,
        model: Any,
        agent_name: Optional[str],
    ) -> Optional[Callable[[str, int], Awaitable[Any]]]:
        """构造备用提供商的结构化调用尝试（未配置或无法提取 schema 时返回 None）。

        仅当结构化模型暴露 .structured（如 DeepSeekStructuredModel）时才能重建同 schema 的
        备用模型；无法可靠提取 schema 的结构化模型跳过备用。
        """
        provider = settings.llm_fallback_provider
        if not provider:
            return None
        schema = getattr(model, "structured", None)
        if schema is None:
            logger.warning(
                "无法从结构化模型提取 schema，跳过备用提供商重试 provider=%s", provider
            )
            return None
        try:
            from app.llm_factory.factory import get_structured_model

            fallback_model = get_structured_model(
                schema,
                provider=provider,
                model_name=settings.llm_fallback_model or None,
            )
        except Exception:
            logger.exception("创建备用结构化模型失败 provider=%s", provider)
            return None

        async def _attempt(current_prompt: str, _attempt_no: int) -> Any:
            with usage_context(agent_name=agent_name):
                return await fallback_model.ainvoke(current_prompt)

        return _attempt

    async def _call_llm(
        self,
        prompt: str,
        agent_name: Optional[str] = None,
        max_retry: Optional[int] = None,
        retry_stage: Optional[RetryStageEnum] = None,
        stream_handler: Optional[Callable[[Any], None]] = None,
        retry_message: Optional[str] = None,
    ) -> str:
        """调用 LLM（非流式，带瞬时错误重试）

        Args:
            prompt: 用户提示词。
            agent_name: 统计点名称（用于模型用量埋点），由调用方传入。
            max_retry: 最大重试次数（不含首次尝试）；None 时取 settings.llm_max_attempts - 1。
            retry_stage: 重试阶段（重试前经 stream_handler 发 AGENT_RETRY，None 不发）。
            stream_handler: SSE 回调（发 AGENT_RETRY 用，None 不发）。
            retry_message: AGENT_RETRY 自定义文案（None 用默认文案）。

        Raises:
            AgentMaxRetriesError: 重试耗尽。
        """
        async def _attempt(current_prompt: str, _attempt_no: int) -> str:
            with usage_context(agent_name=agent_name):
                response = await self.model.ainvoke(
                    [HumanMessage(content=current_prompt)]
                )
            return response.content  # type: ignore

        return await self._run_with_retry(
            prompt=prompt,
            agent_name=agent_name,
            max_retry=max_retry,
            attempt=_attempt,
            retry_stage=retry_stage,
            stream_handler=stream_handler,
            retry_message=retry_message,
            fallback_attempt=self._build_fallback_chat_attempt(agent_name),
        )

    async def _call_structured_model(
        self,
        prompt: str,
        agent_name: Optional[str] = None,
        structured_model: Optional[Any] = None,
        max_retry: Optional[int] = None,
        retry_stage: Optional[RetryStageEnum] = None,
        stream_handler: Optional[Callable[[Any], None]] = None,
        retry_message: Optional[str] = None,
    ) -> Any:
        """调用结构化输出模型（非流式），返回 Pydantic 实例

        与 _call_llm 的区别：底层模型是 llm_factory 创建的结构化输出模型
        （如 DeepSeekStructuredModel / with_structured_output 结果），
        返回的是校验过的 Pydantic 对象，无需再手工 JSON 解析。
        校验失败（格式错误）时带错误反馈重试；瞬时错误按退避策略重试。

        Args:
            prompt: 用户提示词。
            agent_name: 统计点名称（用于模型用量埋点），由调用方传入。
            structured_model: 可选的结构化模型覆盖（默认用 self.structured_model），
                供图节点复用其他 schema 的结构化模型（如 AI 修改大纲用 OutlineResult）。
            max_retry: 最大重试次数（不含首次尝试）；None 时取 settings.llm_max_attempts - 1。
            retry_stage: 重试阶段（重试前经 stream_handler 发 AGENT_RETRY，None 不发）。
            stream_handler: SSE 回调（发 AGENT_RETRY 用，None 不发）。
            retry_message: AGENT_RETRY 自定义文案（None 用默认文案）。

        Returns:
            结构化模型返回的 Pydantic 实例

        Raises:
            AgentMaxRetriesError: 重试耗尽。
        """
        model = structured_model or self.structured_model
        if model is None:
            raise RuntimeError("未配置结构化输出模型，无法调用 _call_structured_model")

        async def _attempt(current_prompt: str, _attempt_no: int) -> Any:
            with usage_context(agent_name=agent_name):
                result = await model.ainvoke(current_prompt)
            return result

        return await self._run_with_retry(
            prompt=prompt,
            agent_name=agent_name,
            max_retry=max_retry,
            attempt=_attempt,
            retry_stage=retry_stage,
            stream_handler=stream_handler,
            retry_message=retry_message,
            fallback_attempt=self._build_fallback_structured_attempt(model, agent_name),
        )

    async def _call_llm_with_streaming(
        self,
        prompt: str,
        stream_handler: Callable[[Any], None],
        message_type: SseMessageTypeEnum,
        agent_name: Optional[str] = None,
        max_retry: Optional[int] = None,
        retry_stage: Optional[RetryStageEnum] = None,
        retry_message: Optional[str] = None,
    ) -> str:
        """调用 LLM（流式输出，带瞬时错误重试）

        瞬时错误重试前经 stream_handler 发 AGENT_RETRY，前端先清空该阶段的过程态，
        再重新从首个片段开始追加，避免坏片段残留和断线重放重复。

        Args:
            prompt: 用户提示词。
            stream_handler: SSE 流式回调。
            message_type: SSE 消息类型。
            agent_name: 统计点名称（用于模型用量埋点），由调用方传入。
            max_retry: 最大重试次数（不含首次尝试）；None 时取 settings.llm_max_attempts - 1。
            retry_stage: 重试阶段（重试前经 stream_handler 发 AGENT_RETRY，None 不发）。
            retry_message: AGENT_RETRY 自定义文案（None 用默认文案）。

        Raises:
            AgentMaxRetriesError: 重试耗尽。
        """
        async def _attempt(current_prompt: str, _attempt_no: int) -> str:
            content_builder = []
            with usage_context(agent_name=agent_name):
                async for chunk in self.model.astream(
                    [HumanMessage(content=current_prompt)]
                ):
                    if chunk.content:
                        content = chunk.content
                        content_builder.append(content)
                        stream_handler(message_type.get_streaming_prefix() + content)
            return "".join(content_builder)

        return await self._run_with_retry(
            prompt=prompt,
            agent_name=agent_name,
            max_retry=max_retry,
            attempt=_attempt,
            retry_stage=retry_stage,
            stream_handler=stream_handler,
            retry_message=retry_message,
            fallback_attempt=self._build_fallback_chat_attempt(
                agent_name, stream_handler, message_type
            ),
        )

    # ==================== JSON 解析 ====================

    @staticmethod
    def _parse_json_response(content: str, name: str) -> dict:
        """解析 JSON 响应（直接解析失败时用 json_repair 修复，并记录日志）

        Raises:
            LLMOutputFormatError: 解析失败（携带原始输出，供重试时拼回提示词）。
        """
        try:
            content2 = content.strip()
            if content2.startswith("```json") or content2.startswith("```JSON"):
                content2 = content2[7:-3].strip()
            return loads_with_repair(content2, name=name)
        except json.JSONDecodeError as e:
            logger.error(
                "%s解析失败, content=%s, error=%s", name, content, str(e)
            )
            raise LLMOutputFormatError(f"{name}解析失败", raw_output=content) from e

    # ==================== 链路与风格 Prompt ====================

    @staticmethod
    def _get_style_prompt(style: Optional[str]) -> str:
        """根据（已弃用的）文章风格获取对应的 Prompt 附加内容

        @deprecated 保留以兼容旧文章路径；新流程请用 _get_genre_prompt / _get_language_style_prompt。
        """
        if not style:
            return ""
        try:
            style_enum = ArticleStyleEnum(style)
            style_map = {
                ArticleStyleEnum.TECH: PromptConstant.STYLE_TECH_PROMPT,
                ArticleStyleEnum.EMOTIONAL: PromptConstant.STYLE_EMOTIONAL_PROMPT,
                ArticleStyleEnum.EDUCATIONAL: PromptConstant.STYLE_EDUCATIONAL_PROMPT,
                ArticleStyleEnum.HUMOROUS: PromptConstant.STYLE_HUMOROUS_PROMPT,
            }
            return style_map.get(style_enum, "")
        except ValueError:
            return ""

    @staticmethod
    def _get_genre_prompt(genre: Optional[str]) -> str:
        """根据题材获取对应的 Prompt 附加内容（决定全文基调与结构）"""
        if not genre:
            return ""
        try:
            genre_enum = ArticleGenreEnum(genre)
            genre_map = {
                ArticleGenreEnum.NEWS: PromptConstant.GENRE_NEWS_PROMPT,
                ArticleGenreEnum.KNOWLEDGE: PromptConstant.GENRE_KNOWLEDGE_PROMPT,
                ArticleGenreEnum.PRODUCT: PromptConstant.GENRE_PRODUCT_PROMPT,
                ArticleGenreEnum.TUTORIAL: PromptConstant.GENRE_TUTORIAL_PROMPT,
                ArticleGenreEnum.OPINION: PromptConstant.GENRE_OPINION_PROMPT,
                ArticleGenreEnum.STORY: PromptConstant.GENRE_STORY_PROMPT,
            }
            text = genre_map.get(genre_enum, "")
            if text:
                return f"========== 文章题材要求 ==========\n{text}\n\n"
            return ""
        except ValueError:
            return ""

    @staticmethod
    def _get_language_style_prompt(language_style: Optional[str]) -> str:
        """根据语言风格获取对应的 Prompt 附加内容（决定语气特质，取代旧文章风格）"""
        if not language_style:
            return ""
        try:
            style_enum = ArticleLanguageStyleEnum(language_style)
            style_map = {
                ArticleLanguageStyleEnum.PROFESSIONAL: PromptConstant.LANGUAGE_STYLE_PROFESSIONAL,
                ArticleLanguageStyleEnum.ACCESSIBLE: PromptConstant.LANGUAGE_STYLE_ACCESSIBLE,
                ArticleLanguageStyleEnum.HUMOROUS: PromptConstant.LANGUAGE_STYLE_HUMOROUS,
                ArticleLanguageStyleEnum.LITERARY: PromptConstant.LANGUAGE_STYLE_LITERARY,
                ArticleLanguageStyleEnum.FORMAL: PromptConstant.LANGUAGE_STYLE_FORMAL,
            }
            text = style_map.get(style_enum, "")
            if text:
                return f"========== 语言风格要求 ==========\n{text}\n\n"
            return ""
        except ValueError:
            return ""

    @staticmethod
    def _get_news_context_prompt(collected_news: Optional[str]) -> str:
        """新闻题材信息采集产物的注入片段（非空时追加，供标题/大纲/正文 Agent 参考）"""
        if not collected_news or not collected_news.strip():
            return ""
        return (
            "========== 参考新闻资料 ==========\n"
            f"{collected_news.strip()}\n"
        )

    # ==================== 日志上下文管理器（委托给模块级函数） ====================

    def _agent_log_context(
        self,
        task_id: Optional[str],
        agent_name: str,
        prompt: Optional[str] = None,
        input_data: Optional[dict] = None,
    ):
        """异步智能体日志上下文"""
        return agent_log_context(
            self.agent_log_service,
            task_id=task_id,
            agent_name=agent_name,
            prompt=prompt,
            input_data=input_data,
        )

    def _agent_log_context_sync(
        self,
        task_id: Optional[str],
        agent_name: str,
        prompt: Optional[str] = None,
        input_data: Optional[dict] = None,
    ):
        """同步智能体日志上下文"""
        return agent_log_context_sync(
            self.agent_log_service,
            task_id=task_id,
            agent_name=agent_name,
            prompt=prompt,
            input_data=input_data,
        )

    # ==================== 工具方法 ====================

    @staticmethod
    def _safe_json_dumps(value: Optional[dict]) -> Optional[str]:
        """安全序列化 JSON（委托给模块级函数）"""
        return _safe_json_dumps(value)
