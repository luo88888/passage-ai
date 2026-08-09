"""意见反馈请求/响应模型。

提供提交反馈、我的反馈分页/详情、管理端分页/详情/回复/改状态的请求与视图对象（VO），
字段与前端接口一致的驼峰别名，供路由层序列化返回。
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from app.constants.feedback import FeedbackConstant
from app.schemas.common import PageRequest


class FeedbackSubmitRequest(BaseModel):
    """提交意见反馈请求。

    Attributes:
        type: 反馈类型（BUG/FEATURE/COMPLAINT/OTHER）。
        content: 反馈内容（1~2000 字）。
        contact: 联系方式（选填，电话或邮箱，≤128 字，后端正则校验）。
        image_urls: 截图 URL 列表（选填，最多 5 张）。
    """

    type: str = Field(..., description="反馈类型：BUG/FEATURE/COMPLAINT/OTHER")
    content: str = Field(
        ..., min_length=1, max_length=FeedbackConstant.MAX_CONTENT_LENGTH,
        description="反馈内容（1~2000字）",
    )
    contact: Optional[str] = Field(
        None, max_length=FeedbackConstant.MAX_CONTACT_LENGTH,
        description="联系方式（电话或邮箱）",
    )
    image_urls: Optional[List[str]] = Field(
        None, alias="imageUrls", max_length=FeedbackConstant.MAX_IMAGE_COUNT,
        description="截图URL列表（最多5张）",
    )

    class Config:
        populate_by_name = True


class FeedbackQueryRequest(PageRequest):
    """我的反馈分页查询请求（type/status 筛选）。

    Attributes:
        type: 反馈类型筛选。
        status: 处理状态筛选。
    """

    type: Optional[str] = Field(None, description="反馈类型筛选")
    status: Optional[str] = Field(None, description="处理状态筛选")


class FeedbackVO(BaseModel):
    """反馈视图对象。

    Attributes:
        id: 反馈 ID。
        user_id: 提交用户 ID。
        type: 反馈类型。
        content: 反馈内容。
        contact: 联系方式。
        image_urls: 截图 URL 列表。
        status: 处理状态。
        reply_content: 管理员回复内容。
        reply_user_id: 回复管理员 ID。
        reply_time: 回复时间。
        create_time: 创建时间。
        update_time: 更新时间。
    """

    id: int
    user_id: int = Field(..., alias="userId")
    type: str
    content: str
    contact: Optional[str] = None
    image_urls: Optional[List[str]] = Field(None, alias="imageUrls")
    status: str
    reply_content: Optional[str] = Field(None, alias="replyContent")
    reply_user_id: Optional[int] = Field(None, alias="replyUserId")
    reply_time: Optional[str] = Field(None, alias="replyTime")
    create_time: str = Field(..., alias="createTime")
    update_time: Optional[str] = Field(None, alias="updateTime")

    class Config:
        populate_by_name = True


class AdminFeedbackQueryRequest(PageRequest):
    """管理端反馈分页查询请求（关键字/类型/状态/时间筛选）。

    Attributes:
        keyword: 关键字（匹配用户账号/昵称/反馈内容）。
        type: 反馈类型筛选。
        status: 处理状态筛选。
        start_time: 起始时间（含）。
        end_time: 结束时间（含）。
    """

    keyword: Optional[str] = Field(None, description="关键字（匹配用户账号/昵称/反馈内容）")
    type: Optional[str] = Field(None, description="反馈类型筛选")
    status: Optional[str] = Field(None, description="处理状态筛选")
    start_time: Optional[str] = Field(None, alias="startTime", description="起始时间（含）")
    end_time: Optional[str] = Field(None, alias="endTime", description="结束时间（含）")


class AdminFeedbackVO(FeedbackVO):
    """管理端反馈视图对象（在 FeedbackVO 基础上附带提交用户信息）。

    Attributes:
        user_account: 提交用户账号。
        user_name: 提交用户昵称。
    """

    user_account: Optional[str] = Field(None, alias="userAccount", description="提交用户账号")
    user_name: Optional[str] = Field(None, alias="userName", description="提交用户昵称")


class FeedbackReplyRequest(BaseModel):
    """管理员回复反馈请求（回复内容 + 状态，默认置 RESOLVED）。

    Attributes:
        id: 反馈 ID。
        reply_content: 回复内容（选填；不填则仅更新状态）。
        status: 处理状态（PENDING/PROCESSING/RESOLVED，默认 RESOLVED）。
    """

    id: int = Field(..., description="反馈 ID")
    reply_content: Optional[str] = Field(
        None, max_length=FeedbackConstant.MAX_CONTENT_LENGTH, description="回复内容",
    )
    status: str = Field(default=FeedbackConstant.STATUS_RESOLVED, description="处理状态（默认 RESOLVED）")


class FeedbackStatusRequest(BaseModel):
    """管理员仅改状态请求（不回复）。

    Attributes:
        id: 反馈 ID。
        status: 处理状态（PENDING/PROCESSING/RESOLVED）。
    """

    id: int = Field(..., description="反馈 ID")
    status: str = Field(..., description="处理状态：PENDING/PROCESSING/RESOLVED")
