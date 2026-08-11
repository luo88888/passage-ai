"""
模型计价默认单价（model_pricing 未命中时的兜底）
"""

from decimal import Decimal

from pydantic_settings import BaseSettings


class PricingConfig(BaseSettings):
    """模型计价兜底单价。

    当 model_pricing 表未命中（或命中行对应列 NULL）时，用以下系统默认单价计费：
    - LLM：按每 1000 token 计价（与种子数据的 LLM * 兜底一致）
    - IMAGE：按每张图计价（默认免费）
    """

    default_llm_input_price: Decimal = Decimal("1")     # LLM 输入单价（积分 / 1k tokens）
    default_llm_output_price: Decimal = Decimal("2")    # LLM 输出单价（积分 / 1k tokens）
    default_image_price: Decimal = Decimal("0")         # AI 生图单价（积分 / 张，默认免费）
