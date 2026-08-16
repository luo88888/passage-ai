"""
配置包：按主题拆分为多个 mixin，最终组合成单一 Settings 类。

外部统一导入：`from app.config import settings`
"""

import dotenv

dotenv.load_dotenv(override=True)   # 确保 .env 环境变量生效

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config.base import BaseConfig, ENV_FILE
from app.config.images import ImageConfig
from app.config.llm import LLMConfig
from app.config.payment import PaymentConfig
from app.config.quota import QuotaConfig
from app.config.agent import AgentConfig
from app.config.pricing import PricingConfig


class Settings(
    BaseConfig,
    ImageConfig,
    LLMConfig,
    PaymentConfig,
    QuotaConfig,
    AgentConfig,
    PricingConfig,
    BaseSettings,
):
    """应用全局配置（pydantic-settings mixin 组合）"""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
