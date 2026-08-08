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
