"""积分用户接口路由（M4）。

提供：余额（含今日签到状态）、积分明细分页、各模型用量统计、每日签到。
积分充值（POST /points/recharge）本期暂不实现，仅预留不做接口。
"""
from databases import Database
from fastapi import APIRouter, Depends

from app.database import get_db
from app.deps import require_login
from app.schemas.common import BaseResponse
from app.schemas.points import (
    ModelUsageStatsVO,
    PointsBalanceVO,
    PointsCheckinVO,
    PointsTransactionQueryRequest,
    PointsTransactionVO,
    PointsUsageStatsQueryRequest,
)
from app.schemas.user import LoginUserVO
from app.services.points_service import PointsService


router = APIRouter(prefix="/points", tags=["积分"])


@router.get("/balance", response_model=BaseResponse[PointsBalanceVO])
async def get_points_balance(
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login),
):
    """查询当前积分余额（余额 + 累计获得/消耗 + 今日签到状态）"""
    service = PointsService(db)
    return BaseResponse.success(data=await service.get_balance_vo(current_user.id))


@router.post("/checkin", response_model=BaseResponse[PointsCheckinVO])
async def checkin(
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login),
):
    """每日签到（Redis SETNX 防重复，赠送 10 积分，记 SIGN_IN 流水）"""
    service = PointsService(db)
    result = await service.checkin(current_user.id)
    return BaseResponse.success(data=result, message=f"签到成功，+{result.gained} 积分")


@router.post("/transactions", response_model=BaseResponse[dict])
async def list_transactions(
    request: PointsTransactionQueryRequest,
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login),
):
    """分页查询积分明细（type/时间/金额筛选）"""
    service = PointsService(db)
    records, total = await service.list_transactions(current_user.id, request)
    return BaseResponse.success(data={
        "records": records,
        "total": total,
        "current": request.current,
        "size": request.page_size,
    })


@router.get("/usage/stats", response_model=BaseResponse[list[ModelUsageStatsVO]])
async def get_usage_stats(
    start_time: str | None = None,
    end_time: str | None = None,
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login),
):
    """查询当前用户各模型用量统计（按 model 聚合次数/token/积分，可按时间范围筛选）"""
    service = PointsService(db)
    query = PointsUsageStatsQueryRequest(startTime=start_time, endTime=end_time)
    return BaseResponse.success(data=await service.get_usage_stats(current_user.id, query))