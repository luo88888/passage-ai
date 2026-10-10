"""
LLM 默认提供方 + 各服务 API Key
"""

from pydantic_settings import BaseSettings


class LLMConfig(BaseSettings):
    """LLM 默认 provider/model + 外部 API key"""

    default_llm_provider: str = "deepseek"
    default_model: str = "deepseek-v4-flash"

    # AI / 搜索 API key
    deepseek_api_key: str

    mimo_api_key: str = ""
    mimo_base_url: str = ""

    serper_api_key: str = ""

    # ======== LLM 调用重试 ========
    llm_max_attempts: int = 3            # 单次 LLM 调用的最大尝试次数（含首次）
    llm_retry_base_seconds: float = 0.5  # 瞬时错误指数退避基础秒数
    llm_retry_max_seconds: float = 5.0   # 退避最大秒数
    llm_retry_backoff_factor: float = 2.0  # 退避因子
    llm_format_retry_attempts: int = 2   # 格式错误带错误反馈的修正重试次数
    llm_fallback_provider: str = ""      # 可选：主提供商持续失败后的备用提供商（空则禁用）
    llm_fallback_model: str = ""         # 可选：备用模型名（空则用备用提供商的默认模型）
