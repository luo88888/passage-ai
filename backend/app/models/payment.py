"""Payment ORM 模型"""

from sqlalchemy import Column, BigInteger, Numeric, String, DateTime, SmallInteger, Text
from sqlalchemy.sql import func

from app.database import Base


class PaymentRecord(Base):
    """支付记录表"""

    __tablename__ = "payment_record"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="id")
    user_id = Column("userId", BigInteger, nullable=False, comment="用户ID")
    stripe_session_id = Column("stripeSessionId", String(128), nullable=True, comment="Stripe Checkout Session ID")
    stripe_payment_intent_id = Column("stripePaymentIntentId", String(128), nullable=True, comment="Stripe 支付意向ID")
    amount = Column(Numeric(10, 2), nullable=False, comment="金额（美元）")
    currency = Column(String(8), nullable=False, default="usd", comment="货币")
    status = Column(String(32), nullable=False, comment="状态")
    product_type = Column("productType", String(32), nullable=False, comment="产品类型")
    description = Column(String(256), nullable=True, comment="描述")
    refund_time = Column("refundTime", DateTime, nullable=True, comment="退款时间")
    refund_reason = Column("refundReason", String(512), nullable=True, comment="退款原因")
    create_time = Column("createTime", DateTime, nullable=False, default=func.now(), comment="创建时间")
    update_time = Column("updateTime", DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment="更新时间")
