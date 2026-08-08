"""
Stripe 支付配置
"""

from pydantic_settings import BaseSettings


class PaymentConfig(BaseSettings):
    """Stripe 支付"""

    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_success_url: str = "http://localhost:5173/payment/success"
    stripe_cancel_url: str = "http://localhost:5173/payment/cancel"
