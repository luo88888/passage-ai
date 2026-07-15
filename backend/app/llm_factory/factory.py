"""
统一 LLM 工厂，根据配置或参数路由到不同的模型提供商

用法:
    from app.llm_factory.factory import get_chat_model, get_structured_model

    model = get_chat_model()  # 使用默认 provider/model
    model = get_chat_model("deepseek", "deepseek-v4-flash")
    structured = get_structured_model(MySchema, "xiaomi", "mimo-v2.5")
"""

from typing import Any

from pydantic import BaseModel
from langchain_core.language_models import BaseChatModel

from app.config import settings
from app.llm_factory.deepseek import (
    create_chat_model as _create_deepseek_chat,
    create_structured_model as _create_deepseek_structured,
)
from app.llm_factory.mimo import (
    create_chat_model as _create_mimo_chat,
    create_structured_model as _create_mimo_structured,
)


# 支持的提供商和对应的工厂函数
_PROVIDER_MAP: dict[str, dict[str, Any]] = {
    "xiaomi": {
        "chat": _create_mimo_chat,
        "structured": _create_mimo_structured,
        "default_model": "mimo-v2.5",
    },
    "mimo": {
        "chat": _create_mimo_chat,
        "structured": _create_mimo_structured,
        "default_model": "mimo-v2.5",
    },
    "deepseek": {
        "chat": _create_deepseek_chat,
        "structured": _create_deepseek_structured,
        "default_model": "deepseek-v4-flash",
    },
}


def _resolve_provider(provider: str | None = None) -> str:
    """解析提供商名称，返回小写 key"""
    if provider is None:
        provider = settings.default_llm_provider
    key = provider.lower()
    if key not in _PROVIDER_MAP:
        raise ValueError(
            f"不支持的 LLM 提供商: {provider}，"
            f"支持的提供商: {list(_PROVIDER_MAP.keys())}"
        )
    return key


def get_chat_model(
    provider: str | None = None,
    model_name: str | None = None,
    temperature: float = 0.0,
    thinking: bool = False,
    reasoning_effort: str = "high",
    extra_body: dict[str, Any] | None = None,
) -> BaseChatModel:
    """创建聊天模型，根据 provider 路由到对应厂商

    Args:
        provider: 提供商名称（xiaomi/mimo/deepseek），默认使用 settings.default_llm_provider
        model_name: 模型名称，默认使用对应提供商的默认模型
        temperature: 温度参数
        thinking: 是否启用思考模式
        reasoning_effort: 推理力度（high/max）
        extra_body: 额外请求体参数

    Returns:
        BaseChatModel 实例
    """
    key = _resolve_provider(provider)
    info = _PROVIDER_MAP[key]
    actual_model = model_name or info["default_model"]

    fn = info["chat"]
    return fn(
        model_name=actual_model,
        temperature=temperature,
        thinking=thinking,
        reasoning_effort=reasoning_effort,
        extra_body=extra_body or {},
    )


def get_structured_model(
    structured: type[BaseModel],
    provider: str | None = None,
    model_name: str | None = None,
    temperature: float = 0.0,
    thinking: bool = False,
    reasoning_effort: str = "high",
    extra_body: dict[str, Any] | None = None,
):
    """创建结构化输出模型，根据 provider 路由到对应厂商

    Args:
        structured: Pydantic 模型类
        provider: 提供商名称（xiaomi/mimo/deepseek），默认使用 settings.default_llm_provider
        model_name: 模型名称，默认使用对应提供商的默认模型
        temperature: 温度参数
        thinking: 是否启用思考模式
        reasoning_effort: 推理力度（high/max）
        extra_body: 额外请求体参数

    Returns:
        带结构化输出的模型实例
    """
    key = _resolve_provider(provider)
    info = _PROVIDER_MAP[key]
    actual_model = model_name or info["default_model"]

    fn = info["structured"]
    return fn(
        structured=structured,
        model_name=actual_model,
        temperature=temperature,
        thinking=thinking,
        reasoning_effort=reasoning_effort,
        extra_body=extra_body or {},
    )
