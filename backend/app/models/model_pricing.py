"""模型计价 ORM 模型。

对应表 model_pricing：配置各模型积分单价（每 1k token / 每张图），
管理端可增删改查；agentName 为空串表示不区分智能体，model 为 * 表示通配兜底。
"""

from sqlalchemy import Column, BigInteger, String, Numeric, SmallInteger, DateTime
from sqlalchemy.sql import func

from app.database import Base


class ModelPricing(Base):
    """模型计价表。

    Attributes:
        id: 主键。
        category: 类别（LLM / IMAGE）。
        provider: 提供商。
        model: 模型名（LLM 用通配符 * 兜底）。
        agent_name: 按 Agent 细分（空=不限）。
        input_price_per_1k: 输入 token 单价（积分/1k token，LLM，允许小数）。
        output_price_per_1k: 输出 token 单价（积分/1k token，LLM，允许小数）。
        price_per_image: 每张图积分（IMAGE）。
        enabled: 是否启用。
        update_time: 更新时间。
    """

    __tablename__ = "model_pricing"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    category = Column(String(16), nullable=False, comment="类别：LLM / IMAGE")
    provider = Column(String(32), nullable=False, comment="提供商")
    model = Column(String(64), nullable=False, comment="模型名（LLM用通配符 * 兜底）")
    agent_name = Column("agentName", String(50), nullable=False, default="", comment="按Agent细分（空=不限）")
    input_price_per_1k = Column("inputPricePer1k", Numeric(10, 4), nullable=False, default=0, comment="输入token单价（积分/1k token，LLM，允许小数）")
    output_price_per_1k = Column("outputPricePer1k", Numeric(10, 4), nullable=False, default=0, comment="输出token单价（积分/1k token，LLM，允许小数）")
    price_per_image = Column("pricePerImage", Numeric(10, 2), nullable=False, default=0, comment="每张图积分（IMAGE）")
    enabled = Column(SmallInteger, nullable=False, default=1, comment="是否启用")
    update_time = Column("updateTime", DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment="更新时间")