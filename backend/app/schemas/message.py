"""站内信请求/响应模型。

提供站内信分页/未读数/已读/删除、管理端发送/已发列表的请求与视图对象（VO），
字段与前端接口一致的驼峰别名，供路由层序列化返回。
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from app.constants.message import MessageConstant
from app.schemas.common import PageRequest


class MessageQueryRequest(PageRequest):
    """站内信分页查询请求（type 筛选）。

    Attributes:
        type: 消息类型筛选（SYSTEM/FEEDBACK/VIP/POINTS）。
    """

    type: Optional[str] = Field(None, description="消息类型筛选：SYSTEM/FEEDBACK/VIP/POINTS")


class MessageVO(BaseModel):
    """站内信视图对象。

    Attributes:
        id: 消息 ID。
        user_id: 收件用户 ID。
        type: 消息类型。
        title: 标题。
        content: 内容。
        link: 跳转链接（前端路由）。
        related_id: 关联业务 ID。
        is_read: 是否已读。
        read_time: 阅读时间。
        create_time: 创建时间。
    """

    id: int
    user_id: int = Field(..., alias="userId")
    type: str
    title: str
    content: Optional[str] = None
    link: Optional[str] = None
    related_id: Optional[int] = Field(None, alias="relatedId")
    is_read: bool = Field(..., alias="isRead")
    read_time: Optional[str] = Field(None, alias="readTime")
    create_time: str = Field(..., alias="createTime")

    class Config:
        populate_by_name = True


class MessageUnreadCountVO(BaseModel):
    """站内信未读数视图对象。

    Attributes:
        count: 未读消息数。
    """

    count: int = Field(default=0, description="未读消息数")


class MessageReadRequest(BaseModel):
    """标记已读请求（单条 ids 或全部 all，仅本人）。

    Attributes:
        ids: 要标记已读的消息 ID 列表（all 为 true 时忽略）。
        all: 是否全部标记已读。
    """

    ids: Optional[List[int]] = Field(None, description="要标记已读的消息 ID 列表")
    all: bool = Field(False, description="是否全部标记已读")


class MessageDeleteRequest(BaseModel):
    """删除站内信请求（软删，仅本人）。

    Attributes:
        ids: 要删除的消息 ID 列表。
    """

    ids: List[int] = Field(..., min_length=1, description="要删除的消息 ID 列表")


class AdminMessageSendRequest(BaseModel):
    """管理员发送站内信请求（SINGLE/BATCH/ALL 写时展开）。

    Attributes:
        target_type: 收件人类型（SINGLE/BATCH/ALL）。
        user_ids: 目标用户 ID 列表（SINGLE 传 1 个、BATCH 传多个；ALL 时忽略）。
        type: 消息类型（默认 SYSTEM）。
        title: 标题（1~200 字）。
        content: 内容。
        link: 跳转链接（可选）。
    """

    target_type: str = Field(..., alias="targetType", description="收件人类型：SINGLE/BATCH/ALL")
    user_ids: Optional[List[int]] = Field(None, alias="userIds", description="目标用户ID列表（ALL 时忽略）")
    type: str = Field(default=MessageConstant.TYPE_SYSTEM, description="消息类型：SYSTEM/FEEDBACK/VIP/POINTS")
    title: str = Field(..., min_length=1, max_length=MessageConstant.MAX_TITLE_LENGTH, description="标题")
    content: Optional[str] = Field(None, max_length=MessageConstant.MAX_CONTENT_LENGTH, description="内容")
    link: Optional[str] = Field(None, max_length=MessageConstant.MAX_LINK_LENGTH, description="跳转链接（前端路由）")

    class Config:
        populate_by_name = True


class AdminMessageQueryRequest(PageRequest):
    """管理端已发消息分页查询请求（type/关键字筛选）。

    Attributes:
        type: 消息类型筛选。
        keyword: 关键字（匹配标题/内容）。
    """

    type: Optional[str] = Field(None, description="消息类型筛选")
    keyword: Optional[str] = Field(None, description="关键字（匹配标题/内容）")


class AdminMessageVO(MessageVO):
    """管理端已发消息视图对象（在 MessageVO 基础上附带发送者信息）。

    Attributes:
        sender_id: 发送者用户 ID（管理员主动发信为管理员 ID）。
    """

    sender_id: Optional[int] = Field(None, alias="senderId", description="发送者用户ID")
