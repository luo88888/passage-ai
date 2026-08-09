from typing import List, Optional
from databases import Database
from fastapi import APIRouter, Depends, Header, Request


from app.constants.user import UserConstant
from app.database import get_db
from app.deps import get_session_id, require_login
from app.exceptions import BusinessException, ErrorCode, throw_if
from app.schemas.common import BaseResponse
from app.schemas.payment import PaymentRecordVO, VipPlanVO
from app.schemas.user import LoginUserVO
from app.services.payment_service import PaymentService
from app.services.user_service import UserService
from app.utils.session import set_session



payment_router = APIRouter(prefix="/payment", tags=["支付管理"])
webhook_router = APIRouter(prefix="/webhook", tags=["支付回调"])


@payment_router.get("/plans", response_model=BaseResponse[List[VipPlanVO]])
async def get_vip_plans(
    db: Database = Depends(get_db),
):
    """获取会员套餐列表（价格 + 特权，公开接口，无需登录）"""
    service = PaymentService(db)
    plans = service.list_vip_plans()
    return BaseResponse.success(data=plans)


@payment_router.post("/create-vip-session", response_model=BaseResponse[str])
async def create_vip_payment_session(
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login),
):
    """创建 VIP 支付会话"""
    service = PaymentService(db)
    session_url = await service.create_vip_payment_session(current_user.id)
    return BaseResponse.success(data=session_url)


@payment_router.post("/activate-vip", response_model=BaseResponse[bool])
async def activate_vip(
    db: Database = Depends(get_db),
    session_id: Optional[str] = Depends(get_session_id),
    current_user: LoginUserVO = Depends(require_login),
):
    """直接开通永久会员（临时免支付：Stripe 停用期间，点击「立即开通」即开通）"""
    service = PaymentService(db)
    success = await service.activate_vip(current_user.id)
    if success and session_id:
        # 同步刷新 Redis Session，避免 GET /user/get/login 仍返回旧角色（需重新登录才生效）
        fresh_user = await UserService(db).get_login_user(current_user.id)
        if fresh_user:
            await set_session(session_id, {"user": fresh_user.model_dump(by_alias=True)})
    return BaseResponse.success(data=success)


@payment_router.post("/refund", response_model=BaseResponse[bool])
async def refund(
    reason: Optional[str] = None,
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login),
):
    """申请退款"""
    if current_user.user_role != UserConstant.VIP_ROLE:
        raise BusinessException(ErrorCode.NO_AUTH_ERROR, "仅 VIP 会员可退款")
    service = PaymentService(db)
    success = await service.handle_refund(current_user.id, reason)
    return BaseResponse.success(data=success)


@payment_router.get("/records", response_model=BaseResponse[List[PaymentRecordVO]])
async def get_payment_records(
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login),
):
    """获取当前用户支付记录"""
    service = PaymentService(db)
    records = await service.get_payment_records(current_user.id)
    return BaseResponse.success(data=records)


# # FIXME: p0 Webhook 处理失败时返回 HTTP 200,Stripe 不会重试
@webhook_router.post("/stripe")
async def stripe_webhook(
    http_request: Request,
    stripe_signature: str = Header(..., alias="Stripe-Signature"),
    db: Database = Depends(get_db),
):
    """Stripe webhook 回调"""
    payload = (await http_request.body()).decode("utf-8")
    service = PaymentService(db)
    try:
        event = service.construct_event(payload, stripe_signature)
        event_type = getattr(event, "type", None) or event.get("type")
        data_object = None
        if hasattr(event, "data") and getattr(event.data, "object", None):
            data_object = event.data.object
        elif isinstance(event, dict):
            data_object = event.get("data", {}).get("object")

        if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
            await service.handle_payment_success(data_object)
        return "success"
    except Exception:   # TODO: 应进行日志记录
        return "error"
