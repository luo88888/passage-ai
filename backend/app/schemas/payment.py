"""支付相关请求/响应模型"""

from typing import List, Optional
from pydantic import BaseModel, Field


class RefundRequest(BaseModel):
    """退款请求"""

    reason: Optional[str] = Field(None, description="退款原因")


class VipPlanVO(BaseModel):
    """会员套餐视图（价格 + 特权清单，供前端开通页渲染）

    价格取自后端 ProductTypeEnum.VIP_PERMANENT.price（单一来源），
    特权文案在此处硬编码，与 article_service 中会员专属能力保持一致。
    """

    product_type: str = Field(..., alias="productType", description="产品类型枚举值，如 VIP_PERMANENT")
    price: float = Field(..., description="价格（美元）")
    currency: str = Field(..., description="货币，如 usd")
    title: str = Field(..., description="套餐名称")
    description: str = Field(..., description="套餐简短描述")
    privileges: List[str] = Field(..., description="会员特权文案列表")

    class Config:
        populate_by_name = True


class PaymentRecordVO(BaseModel):
    """支付记录视图"""

    id: int
    user_id: int = Field(..., alias="userId")
    stripe_session_id: Optional[str] = Field(None, alias="stripeSessionId")
    stripe_payment_intent_id: Optional[str] = Field(None, alias="stripePaymentIntentId")
    amount: float
    currency: str
    status: str
    product_type: str = Field(..., alias="productType")
    description: Optional[str] = None
    refund_time: Optional[str] = Field(None, alias="refundTime")
    refund_reason: Optional[str] = Field(None, alias="refundReason")
    create_time: str = Field(..., alias="createTime")
    update_time: str = Field(..., alias="updateTime")

    class Config:
        populate_by_name = True
