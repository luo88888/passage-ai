"""意见反馈接口路由。

用户端：提交 / 我的反馈分页 / 详情；管理端：全量分页 / 详情 / 回复 / 仅改状态。
截图上传（POST /feedback/upload，复用头像上传白名单范式 + LocalFileService 落盘）已实现。
"""
import os
from typing import Optional

from databases import Database
from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.database import get_db
from app.deps import require_admin, require_login
from app.exceptions import ErrorCode, throw_if, throw_if_not
from app.schemas.common import BaseResponse
from app.schemas.feedback import (
    AdminFeedbackQueryRequest,
    AdminFeedbackVO,
    FeedbackQueryRequest,
    FeedbackReplyRequest,
    FeedbackStatusRequest,
    FeedbackSubmitRequest,
    FeedbackVO,
)
from app.schemas.image import ImageData
from app.schemas.user import LoginUserVO
from app.services.feedback_service import FeedbackService
from app.services.local_file_service import LocalFileService


# ==================== 反馈截图上传配置 ====================
# 与头像上传一致：白名单 MIME/扩展名 + 单张 2MB 上限；不接受 SVG（防存储型 XSS，见 docs/local/代码审查报告.md P0-7）
_ALLOWED_FEEDBACK_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_ALLOWED_FEEDBACK_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_MAX_FEEDBACK_IMAGE_SIZE = 2 * 1024 * 1024

_feedback_file_service: "LocalFileService | None" = None


def _get_feedback_file_service() -> LocalFileService:
    """懒加载本地文件存储服务（反馈截图上传复用，避免每次请求重建 httpx 客户端）"""
    global _feedback_file_service
    if _feedback_file_service is None:
        _feedback_file_service = LocalFileService()
    return _feedback_file_service


router = APIRouter(prefix="/feedback", tags=["意见反馈"])

# 管理端接口独立路由（/admin/feedback，仅管理员可访问）
admin_feedback_router = APIRouter(prefix="/admin/feedback", tags=["意见反馈管理"])




@router.post("/upload", response_model=BaseResponse[str])
async def upload_feedback_image(
    file: UploadFile = File(...),
    current_user: LoginUserVO = Depends(require_login),
):
    """上传反馈截图（multipart/form-data，字段名 file）

    仅支持 JPG / PNG / WebP / GIF，大小不超过 2MB，不接受 SVG（防存储型 XSS）；
    单张上传返回可访问 URL，同一反馈可多次调用（提交时最多 5 张，由提交接口兜底校验）。
    文件保存到本地 static/images/feedback/。
    """
    # 校验 MIME 类型与扩展名（双重校验，防止伪造类型）
    content_type = (file.content_type or "").lower()
    throw_if(
        content_type not in _ALLOWED_FEEDBACK_TYPES,
        ErrorCode.PARAMS_ERROR,
        "仅支持 JPG/PNG/WebP/GIF 格式的截图",
    )
    ext = os.path.splitext(file.filename or "")[1].lower()
    throw_if(ext not in _ALLOWED_FEEDBACK_EXTS, ErrorCode.PARAMS_ERROR, "不支持的文件格式")

    content = await file.read()
    throw_if(len(content) == 0, ErrorCode.PARAMS_ERROR, "文件内容为空")
    throw_if(len(content) > _MAX_FEEDBACK_IMAGE_SIZE, ErrorCode.PARAMS_ERROR, "截图大小不能超过 2MB")

    image_data = ImageData.from_bytes(content, mime_type=content_type)
    url = await _get_feedback_file_service().upload_image_data(image_data, folder="feedback")
    throw_if_not(url, ErrorCode.OPERATION_ERROR, "截图上传失败")

    return BaseResponse.success(data=url, message="上传成功")

@router.post("/submit", response_model=BaseResponse[int])
async def submit_feedback(
    request: FeedbackSubmitRequest,
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login),
):
    """提交意见反馈（每日限流：每用户每天最多 feedback_daily_limit 条，超限返回 REQUEST_TOO_FREQUENT）"""
    service = FeedbackService(db)
    feedback_id = await service.submit(current_user.id, request)
    return BaseResponse.success(data=feedback_id, message="提交成功")


@router.get("/page", response_model=BaseResponse[dict])
async def page_my_feedback(
    current: int = Query(1, ge=1, description="当前页码"),
    page_size: int = Query(10, ge=1, le=100, alias="pageSize", description="每页大小"),
    type: Optional[str] = Query(None, description="反馈类型筛选：BUG/FEATURE/COMPLAINT/OTHER"),
    status: Optional[str] = Query(None, description="处理状态筛选：PENDING/PROCESSING/RESOLVED"),
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login),
):
    """我的反馈分页（type/status 筛选，仅本人）"""
    service = FeedbackService(db)
    query = FeedbackQueryRequest(current=current, pageSize=page_size, type=type, status=status)
    records, total = await service.page_mine(current_user.id, query)
    return BaseResponse.success(data={
        "records": records,
        "total": total,
        "current": query.current,
        "size": query.page_size,
    })


@router.get("/{feedback_id}", response_model=BaseResponse[FeedbackVO])
async def get_feedback(
    feedback_id: int,
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login),
):
    """反馈详情（仅本人，归属校验）"""
    service = FeedbackService(db)
    return BaseResponse.success(data=await service.get_detail(current_user.id, feedback_id))


@admin_feedback_router.get("/page", response_model=BaseResponse[dict])
async def admin_page_feedback(
    current: int = Query(1, ge=1, description="当前页码"),
    page_size: int = Query(10, ge=1, le=100, alias="pageSize", description="每页大小"),
    keyword: Optional[str] = Query(None, description="关键字（匹配用户账号/昵称/反馈内容）"),
    type: Optional[str] = Query(None, description="反馈类型筛选"),
    status: Optional[str] = Query(None, description="处理状态筛选"),
    start_time: Optional[str] = Query(None, alias="startTime", description="起始时间（含）"),
    end_time: Optional[str] = Query(None, alias="endTime", description="结束时间（含）"),
    db: Database = Depends(get_db),
    _: LoginUserVO = Depends(require_admin),
):
    """管理端全量分页（关键字/类型/状态/时间筛选，含提交用户信息）"""
    service = FeedbackService(db)
    query = AdminFeedbackQueryRequest(
        current=current, pageSize=page_size,
        keyword=keyword, type=type, status=status,
        startTime=start_time, endTime=end_time,
    )
    records, total = await service.admin_page(query)
    return BaseResponse.success(data={
        "records": records,
        "total": total,
        "current": query.current,
        "size": query.page_size,
    })


@admin_feedback_router.get("/{feedback_id}", response_model=BaseResponse[AdminFeedbackVO])
async def admin_get_feedback(
    feedback_id: int,
    db: Database = Depends(get_db),
    _: LoginUserVO = Depends(require_admin),
):
    """管理端反馈详情（含提交用户信息）"""
    service = FeedbackService(db)
    return BaseResponse.success(data=await service.admin_detail(feedback_id))


@admin_feedback_router.post("/reply", response_model=BaseResponse[FeedbackVO])
async def admin_reply_feedback(
    request: FeedbackReplyRequest,
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_admin),
):
    """管理员回复反馈（回复内容 + 状态，默认置 RESOLVED；联动发送 FEEDBACK 站内信）"""
    service = FeedbackService(db)
    result = await service.reply(current_user.id, request)
    return BaseResponse.success(data=result, message="回复成功，已通知用户")


@admin_feedback_router.post("/status", response_model=BaseResponse[FeedbackVO])
async def admin_update_feedback_status(
    request: FeedbackStatusRequest,
    db: Database = Depends(get_db),
    _: LoginUserVO = Depends(require_admin),
):
    """管理员仅改状态（不回复）"""
    service = FeedbackService(db)
    result = await service.update_status(request)
    return BaseResponse.success(data=result, message="状态更新成功")
