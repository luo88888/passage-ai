"""用户相关请求/响应模型"""

from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.common import PageRequest



# ============================== 请求模型 ==============================

class UserRegisterRequest(BaseModel):
    """用户注册请求"""
    
    user_account: str = Field(..., min_length=4, max_length=256, alias="userAccount", description="账号")
    user_password: str = Field(..., min_length=8, max_length=512, alias="userPassword", description="密码")
    check_password: str = Field(..., min_length=8, max_length=512, alias="checkPassword", description="确认密码")


class UserLoginRequest(BaseModel):
    """用户登录请求"""
    
    user_account: str = Field(..., min_length=4, max_length=256, alias="userAccount", description="账号")
    user_password: str = Field(..., min_length=8, max_length=512, alias="userPassword", description="密码")


class UserAddRequest(BaseModel):
    """添加用户请求（管理员）"""
    
    user_account: str = Field(..., alias="userAccount", description="账号")
    user_password: str = Field(..., alias="userPassword", description="密码")
    user_name: Optional[str] = Field(None, alias="userName", description="用户昵称")
    user_avatar: Optional[str] = Field(None, alias="userAvatar", description="用户头像")
    user_profile: Optional[str] = Field(None, alias="userProfile", description="用户简介")
    user_role: str = Field(default="user", alias="userRole", description="用户角色")


class UserUpdateRequest(BaseModel):
    """更新用户请求（管理员）"""
    
    id: int = Field(..., description="用户 ID")
    user_name: Optional[str] = Field(None, alias="userName", description="用户昵称")
    user_avatar: Optional[str] = Field(None, alias="userAvatar", description="用户头像")
    user_profile: Optional[str] = Field(None, alias="userProfile", description="用户简介")
    user_role: Optional[str] = Field(None, alias="userRole", description="用户角色")


class UserQueryRequest(PageRequest):
    """用户查询请求"""
    
    id: Optional[int] = Field(None, description="用户 ID")
    user_account: Optional[str] = Field(None, alias="userAccount", description="账号")
    user_name: Optional[str] = Field(None, alias="userName", description="用户昵称")
    user_profile: Optional[str] = Field(None, alias="userProfile", description="用户简介")
    user_role: Optional[str] = Field(None, alias="userRole", description="用户角色")



# ============================== 响应模型 ==============================

class UserVO(BaseModel):
    """用户视图对象"""
    
    id: int
    user_account: str = Field(..., alias="userAccount")
    user_name: Optional[str] = Field(None, alias="userName")
    user_avatar: Optional[str] = Field(None, alias="userAvatar")
    user_profile: Optional[str] = Field(None, alias="userProfile")
    user_role: str = Field(..., alias="userRole")
    quota: Optional[int] = Field(None, description="剩余配额")
    points: Optional[int] = Field(None, description="积分余额")
    vip_time: Optional[str] = Field(None, alias="vipTime", description="成为会员时间")
    create_time: str = Field(..., alias="createTime")
    
    class Config:
        populate_by_name = True


class UserProfileVO(BaseModel):
    """用户主页视图对象（个人详情页展示：基本信息 + 积分/配额 + 创作统计）"""

    id: int
    user_account: str = Field(..., alias="userAccount")
    user_name: Optional[str] = Field(None, alias="userName")
    user_avatar: Optional[str] = Field(None, alias="userAvatar")
    user_profile: Optional[str] = Field(None, alias="userProfile")
    user_role: str = Field(..., alias="userRole")
    quota: Optional[int] = Field(None, description="剩余配额（历史兼容，不再作为创作门槛）")
    points: Optional[int] = Field(None, description="积分余额（权威 user_points）")
    active_task_count: Optional[int] = Field(None, alias="activeTaskCount", description="进行中创作任务数（含挂起）")
    vip_time: Optional[str] = Field(None, alias="vipTime", description="成为会员时间")
    create_time: str = Field(..., alias="createTime", description="注册时间")
    article_count: int = Field(default=0, alias="articleCount", description="创作文章总数（未删除）")

    class Config:
        populate_by_name = True


class LoginUserVO(BaseModel):
    """登录用户视图对象"""
    
    id: int
    user_account: str = Field(..., alias="userAccount")
    user_name: Optional[str] = Field(None, alias="userName")
    user_avatar: Optional[str] = Field(None, alias="userAvatar")
    user_profile: Optional[str] = Field(None, alias="userProfile")
    user_role: str = Field(..., alias="userRole")
    quota: Optional[int] = Field(None, description="剩余配额")
    points: Optional[int] = Field(None, description="积分余额")
    points_version: Optional[int] = Field(None, alias="pointsVersion", description="积分账户乐观锁版本（前端实时刷新余额用）")
    active_task_count: Optional[int] = Field(None, alias="activeTaskCount", description="进行中创作任务数（含挂起，并发限制计数）")
    vip_time: Optional[str] = Field(None, alias="vipTime", description="成为会员时间")
    create_time: str = Field(..., alias="createTime")
    update_time: str = Field(..., alias="updateTime")   # 展示登录用户自己的信息
    
    class Config:
        populate_by_name = True
