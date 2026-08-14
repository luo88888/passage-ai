"""LLM token 用量回调处理器

在 llm_factory 各 provider 的 create_chat_model / create_structured_model 中
统一挂载，所有经由工厂创建的模型（BaseAgent / 信息采集主/子 Agent / SVG 示意图）
调用时自动上报 token 用量，避免逐调用点手工埋点遗漏。

Token 获取优先级：
    1. 响应消息的 usage_metadata（OpenAI 兼容接口通常返回）；
    2. response.llm_output.token_usage（部分厂商旧字段）；
    3. 字符数兜底估算（ceil(字符数 / 3)）。

流式场景：显式开启 stream_usage=True 让厂商在末个 chunk 返回累计 usage；
无 usage 时通过 on_llm_new_token 累积输出字符数做兜底估算。
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from app.utils.logger import logger


def _estimate_tokens(text: str) -> int:
    """按字符数估算 token：ceil(字符数 / 3)。

    Args:
        text: 待估算文本。

    Returns:
        估算 token 数；空文本返回 0。
    """
    if not text:
        return 0
    return math.ceil(len(text) / 3)



def _get_usage_deps():
    """延迟导入用量服务，避免与 app.services 包初始化形成循环导入。"""
    from app.services.model_usage_service import get_usage_context, usage_recorder
    return get_usage_context, usage_recorder


class TokenUsageCallbackHandler(BaseCallbackHandler):
    """LLM token 用量回调处理器。

    以 run_id 为键维护每次调用的临时状态（提示词 / 流式累积输出），
    在 on_llm_end 时统一上报到 UsageRecorder；调用失败走 on_llm_error 记 FAILED。

    Attributes:
        provider: 提供商名（Xiaomi / DeepSeek）。
        model_name: 模型名（如 mimo-v2.5-pro）。
        _prompts: run_id → 本次调用的提示词列表。
        _output_chars: run_id → 流式已累积的输出字符数。
    """

    def __init__(self, provider: str, model_name: str) -> None:
        """初始化回调处理器。

        Args:
            provider: 提供商名。
            model_name: 模型名。
        """
        self.provider = provider
        self.model_name = model_name
        self._prompts: Dict[Any, list[str]] = {}
        self._output_chars: Dict[Any, int] = {}

    # ---------------- 异步回调（项目内 LLM 均为异步调用） ----------------

    """
    事件	           钩子	                    触发时机

    调用开始	    on_llm_start	        LLM 调用发出前
    聊天模型开始	on_chat_model_start	    Chat 模型调用发出前
    流式吐字	    on_llm_new_token	    流式输出的每一个 token
    调用成功	    on_llm_end	            拿到完整结果（含 LLMResult / token 用量）
    调用失败	    on_llm_error	        抛异常时
    """

    # 重写 on_llm_start（而非 on_chat_model_start）在 Chat 模型下同样生效
    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        """记录本次调用的提示词，供无 usage 时估算输入 token。"""
        self._prompts[run_id] = list(prompts)
        self._output_chars[run_id] = 0

    async def on_llm_new_token(self, token: str, *, run_id: Any, **kwargs: Any) -> None:
        """流式场景累积输出字符，供无 usage 时估算输出 token。"""
        if run_id in self._output_chars:
            self._output_chars[run_id] += len(token)

    async def on_llm_end(self, response: LLMResult, *, run_id: Any, **kwargs: Any) -> None:
        """LLM 调用成功：提取/估算用量并上报。"""
        try:
            self._record_success(run_id, response)
        except Exception:
            logger.exception(
                "记录模型用量失败 provider=%s model=%s",
                self.provider,
                self.model_name,
            )
        finally:
            self._prompts.pop(run_id, None)
            self._output_chars.pop(run_id, None)

    async def on_llm_error(self, error: Exception, *, run_id: Any, **kwargs: Any) -> None:
        """LLM 调用失败：记 FAILED（不计 token，默认不计费）。"""
        try:
            get_usage_context, usage_recorder = _get_usage_deps()
            ctx = get_usage_context()
            usage_recorder.record_llm(
                provider=self.provider,
                model=self.model_name,
                agent_name=ctx.agent_name if ctx else None,
                input_tokens=0,
                output_tokens=0,
                status="FAILED",
            )
        except Exception:
            logger.exception(
                "记录模型失败用量异常 provider=%s model=%s",
                self.provider,
                self.model_name,
            )
        finally:
            self._prompts.pop(run_id, None)
            self._output_chars.pop(run_id, None)

    # ---------------- 内部实现 ----------------

    def _record_success(self, run_id: Any, response: LLMResult) -> None:
        """提取 usage 并上报成功调用。"""
        input_tokens, output_tokens = self._extract_usage(response)
        if input_tokens is None or output_tokens is None:
            input_tokens = self._estimate_input(run_id)
            output_tokens = self._estimate_output(run_id, response)

        get_usage_context, usage_recorder = _get_usage_deps()
        ctx = get_usage_context()
        usage_recorder.record_llm(
            provider=self.provider,
            model=self.model_name,
            agent_name=ctx.agent_name if ctx else None,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            status="SUCCESS",
        )

    @staticmethod
    def _extract_usage(response: LLMResult) -> Tuple[Optional[int], Optional[int]]:
        """从响应中提取 (input_tokens, output_tokens)；缺失返回 (None, None)。"""
        # 1) 各 generation message 的 usage_metadata（AIMessage 标准字段）
        for gen_list in response.generations:
            for gen in gen_list:
                msg = getattr(gen, "message", None)
                usage_metadata = (
                    getattr(msg, "usage_metadata", None) if msg is not None else None
                )
                if isinstance(usage_metadata, dict):
                    input_tokens = usage_metadata.get("input_tokens")
                    if input_tokens is not None:
                        return int(input_tokens), int(usage_metadata.get("output_tokens", 0))
        # 2) llm_output.token_usage（OpenAI 兼容旧字段）
        llm_output = response.llm_output or {}
        token_usage = llm_output.get("token_usage") or {}
        if token_usage.get("prompt_tokens") is not None:
            return int(token_usage["prompt_tokens"]), int(token_usage.get("completion_tokens", 0))
        return None, None

    def _estimate_input(self, run_id: Any) -> int:
        """按提示词字符数估算输入 token。"""
        logger.warning(f"获取输入 token 数失败，使用字符数估计，run_id={run_id}")
        prompts = self._prompts.get(run_id) or []
        return sum(_estimate_tokens(p) for p in prompts)

    def _estimate_output(self, run_id: Any, response: LLMResult) -> int:
        """按输出字符数估算输出 token（流式优先用累积值）。"""
        logger.warning(f"获取输出 token 数失败，使用字符数估计，run_id={run_id}")
        chars = self._output_chars.get(run_id) or 0
        if chars <= 0:
            for gen_list in response.generations:
                for gen in gen_list:
                    chars += len(getattr(gen, "text", "") or "")
        return math.ceil(chars / 3) if chars else 0
