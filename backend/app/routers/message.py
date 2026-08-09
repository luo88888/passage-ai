"""站内信接口路由。

用户端：分页（未读优先）/ 未读数 / 已读（单条、全部）/ 删除；管理端：发送（SINGLE/BATCH/ALL）/ 已发列表。
"""
from typing import Optional

from databases import Database
from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.deps import require_admin, require_login
from app.schemas.common import BaseResponse
from app.schemas.message import (
    AdminMessageQueryRequest,
    AdminMessageSendRequest,
    MessageDeleteRequest,
    MessageQueryRequest,
    MessageReadRequest,
    MessageUnreadCountVO,
)
from app.schemas.user import LoginUserVO
from app.services.message_service import MessageService


router = APIRouter(prefix="/message", tags=["站内信"])

# 管理端接口独立路由（/admin/message，仅管理员可访问）
admin_message_router = APIRouter(prefix="/admin/message", tags=["站内信管理"])


@router.get("/page", response_model=BaseResponse[dict])
async def page_message(
    current: int = Query(1, ge=1, description="当前页码"),
    page_size: int = Query(10, ge=1, le=100, alias="pageSize", description="每页大小"),
    type: Optional[str] = Query(None, description="消息类型筛选：SYSTEM/FEEDBACK/VIP/POINTS"),
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login),
):
    """站内信分页（未读优先 + createTime 倒序，type 可选筛选，仅本人）"""
    service = MessageService(db)
    query = MessageQueryRequest(current=current, pageSize=page_size, type=type)
    records, total = await service.page(current_user.id, query)
    return BaseResponse.success(data={
        "records": records,
        "total": total,
        "current": query.current,
        "size": query.page_size,
    })


@router.get("/unread-count", response_model=BaseResponse[MessageUnreadCountVO])
async def get_unread_count(
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login),
):
    """未读站内信数（DB count 实时查询，供头部铃铛角标轮询）"""
    service = MessageService(db)
    count = await service.unread_count(current_user.id)
    return BaseResponse.success(data=MessageUnreadCountVO(count=count))


@router.post("/read", response_model=BaseResponse[int])
async def mark_message_read(
    request: MessageReadRequest,
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login),
):
    """标记已读（{ids: []} 或 {all: true}，仅本人）"""
    service = MessageService(db)
    affected = await service.mark_read(current_user.id, request)
    return BaseResponse.success(data=affected, message="已读成功")


@router.post("/delete", response_model=BaseResponse[int])
async def delete_message(
    request: MessageDeleteRequest,
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login),
):
    """删除站内信（软删，仅本人）"""
    service = MessageService(db)
    affected = await service.delete(current_user.id, request)
    return BaseResponse.success(data=affected, message="删除成功")


@admin_message_router.post("/send", response_model=BaseResponse[int])
async def admin_send_message(
    request: AdminMessageSendRequest,
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_admin),
):
    """管理员发送站内信（targetType: SINGLE/BATCH/ALL + userIds[]，写时展开）"""
    service = MessageService(db)
    count = await service.send(current_user.id, request)
    return BaseResponse.success(data=count, message="发送成功")


@admin_message_router.get("/page", response_model=BaseResponse[dict])
async def admin_page_message(
    current: int = Query(1, ge=1, description="当前页码"),
    page_size: int = Query(10, ge=1, le=100, alias="pageSize", description="每页大小"),
    type: Optional[str] = Query(None, description="消息类型筛选"),
    keyword: Optional[str] = Query(None, description="关键字（匹配标题/内容）"),
    db: Database = Depends(get_db),
    _: LoginUserVO = Depends(require_admin),
):
    """管理端已发消息分页（senderId 非空 = 管理员主动发信）"""
    service = MessageService(db)
    query = AdminMessageQueryRequest(current=current, pageSize=page_size, type=type, keyword=keyword)
    records, total = await service.admin_page(query)
    return BaseResponse.success(data={
        "records": records,
        "total": total,
        "current": query.current,
        "size": query.page_size,
    })
