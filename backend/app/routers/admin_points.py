"""积分管理端接口路由（M4）。

提供：全局积分/用量看板、模型计价 CRUD、手工调整用户积分、按用户/模型查询用量。
所有接口仅管理员可访问。
"""
from databases import Database
from fastapi import APIRouter, Depends

from app.database import get_db
from app.deps import require_admin
from app.schemas.common import BaseResponse
from app.schemas.points import (
    AdminPointsAdjustRequest,
    AdminPointsTransactionsRequest,
    AdminUsageQueryRequest,
    ModelPricingSaveRequest,
    ModelPricingUpdateRequest,
    ModelPricingVO,
    ModelUsageRecordVO,
    PointsOverviewVO,
)
from app.schemas.user import LoginUserVO
from app.services.points_service import PointsService


# /admin/points/*：看板 / 调整 / 用量查询
admin_points_router = APIRouter(prefix="/admin/points", tags=["积分管理"])


@admin_points_router.get("/overview", response_model=BaseResponse[PointsOverviewVO])
async def get_points_overview(
    db: Database = Depends(get_db),
    _: LoginUserVO = Depends(require_admin),
):
    """全局积分/用量看板（仅管理员）"""
    service = PointsService(db)
    return BaseResponse.success(data=await service.get_overview())


@admin_points_router.post("/adjust", response_model=BaseResponse[int])
async def adjust_user_points(
    request: AdminPointsAdjustRequest,
    db: Database = Depends(get_db),
    _: LoginUserVO = Depends(require_admin),
):
    """手工调整用户积分（正=赠送，负=扣减，记 ADMIN_ADJUST 流水）"""
    service = PointsService(db)
    balance = await service.adjust_points(
        user_id=request.user_id,
        amount=request.amount,
        description=request.description,
    )
    return BaseResponse.success(data=balance, message="调整成功")


@admin_points_router.post("/transactions", response_model=BaseResponse[dict])
async def list_user_transactions(
    request: AdminPointsTransactionsRequest,
    db: Database = Depends(get_db),
    _: LoginUserVO = Depends(require_admin),
):
    """分页查询指定用户的积分流水（仅管理员，用于积分管理查看流水）"""
    service = PointsService(db)
    records, total = await service.list_transactions(request.user_id, request)
    return BaseResponse.success(data={
        "records": records,
        "total": total,
        "current": request.current,
        "size": request.page_size,
    })


@admin_points_router.post("/usage", response_model=BaseResponse[dict])
async def list_usage(
    request: AdminUsageQueryRequest,
    db: Database = Depends(get_db),
    _: LoginUserVO = Depends(require_admin),
):
    """分页查询模型用量记录（按用户/类别/模型/时间筛选，仅管理员）"""
    service = PointsService(db)
    records, total = await service.list_usage(request)
    return BaseResponse.success(data={
        "records": records,
        "total": total,
        "current": request.current,
        "size": request.page_size,
    })


# /admin/model-pricing：计价配置 CRUD
model_pricing_router = APIRouter(prefix="/admin/model-pricing", tags=["模型计价管理"])


@model_pricing_router.get("", response_model=BaseResponse[list[ModelPricingVO]])
async def list_model_pricing(
    db: Database = Depends(get_db),
    _: LoginUserVO = Depends(require_admin),
):
    """查询全部模型计价配置（仅管理员）"""
    service = PointsService(db)
    return BaseResponse.success(data=await service.list_model_pricing())


@model_pricing_router.post("", response_model=BaseResponse[int])
async def create_model_pricing(
    request: ModelPricingSaveRequest,
    db: Database = Depends(get_db),
    _: LoginUserVO = Depends(require_admin),
):
    """新增模型计价配置（仅管理员）"""
    service = PointsService(db)
    new_id = await service.create_model_pricing(request)
    return BaseResponse.success(data=new_id, message="新增成功")


@model_pricing_router.put("", response_model=BaseResponse[bool])
async def update_model_pricing(
    request: ModelPricingUpdateRequest,
    db: Database = Depends(get_db),
    _: LoginUserVO = Depends(require_admin),
):
    """更新模型计价配置（按 id，仅管理员）"""
    service = PointsService(db)
    result = await service.update_model_pricing(request)
    return BaseResponse.success(data=result, message="更新成功")