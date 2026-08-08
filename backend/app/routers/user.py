"""
用户路由
"""

import os
from typing import Optional
from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from databases import Database

from app.database import get_db
from app.schemas.common import BaseResponse, DeleteRequest
from app.schemas.user import (
    UserRegisterRequest,
    UserLoginRequest,
    UserAddRequest,
    UserUpdateRequest,
    UserQueryRequest,
    UserVO,
    UserProfileVO,
    LoginUserVO,
    UserProfileUpdateRequest,
    UserChangePasswordRequest,
)
from app.services.user_service import UserService
from app.exceptions import BusinessException, ErrorCode, throw_if, throw_if_not
from app.deps import (
    get_current_user,
    get_session_id,
    require_login,
    require_admin,
    generate_session_id
)
from app.utils.session import set_session, remove_session
from app.utils.rate_limit import (
    get_client_ip,
    check_register_rate_limit,
    is_login_locked,
    record_login_failure,
    clear_login_failures,
    is_login_ip_locked,
    record_login_ip_failure,
)
from app.schemas.image import ImageData
from app.services.local_file_service import LocalFileService
from app.config import settings
from app.utils.logger import logger


router = APIRouter(prefix="/user", tags=["用户管理"])


# ==================== 头像上传配置 ====================
# 允许的头像 MIME 类型与扩展名、大小上限（2MB）
_ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_ALLOWED_AVATAR_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_MAX_AVATAR_SIZE = 2 * 1024 * 1024

_avatar_file_service: "LocalFileService | None" = None


def _get_avatar_file_service() -> LocalFileService:
    """懒加载本地文件存储服务（头像上传复用，避免每次请求重建 httpx 客户端）"""
    global _avatar_file_service
    if _avatar_file_service is None:
        _avatar_file_service = LocalFileService()
    return _avatar_file_service


@router.post("/register", response_model=BaseResponse[int])
async def register(
    request: UserRegisterRequest,
    db: Database = Depends(get_db),
    client: Request = None,
):
    """用户注册（同一 IP 在窗口内限次）"""
    ip = get_client_ip(client)
    if ip:
        allowed = await check_register_rate_limit(ip)
        throw_if_not(
            allowed,
            ErrorCode.OPERATION_ERROR,
            f"注册过于频繁，请 {settings.register_ip_window_seconds // 60} 分钟后再试",
        )
    else:
        logger.warning("无法获取客户端 IP，跳过注册限流")

    service = UserService(db)
    user_id = await service.register(request)
    return BaseResponse.success(data=user_id, message="注册成功")


@router.post("/login", response_model=BaseResponse[LoginUserVO])
async def login(
    request: UserLoginRequest,
    response: Response,
    db: Database = Depends(get_db),
    client: Request = None,
):
    """用户登录（单账号失败超限后锁定 + IP 级失败限流，防密码爆破与撞库）"""
    ip = get_client_ip(client)

    # 登录前先查 IP 是否被锁定（撞库防护：IP 级失败超限后整体拦截）
    if ip:
        throw_if(
            await is_login_ip_locked(ip),
            ErrorCode.PASSWORD_ERROR,
            f"登录失败次数过多，请 {settings.login_ip_lock_seconds // 60} 分钟后再试",
        )

    # 再查账号是否被锁定
    throw_if(
        await is_login_locked(request.user_account),
        ErrorCode.PASSWORD_ERROR,
        f"登录失败次数过多，账号已锁定，请 {settings.login_lock_seconds // 60} 分钟后再试",
    )

    service = UserService(db)
    try:
        user = await service.login(request)
    except BusinessException as e:
        # 账号级：仅密码错误时计数锁定（避免攻击者用不同账号名放大锁定）
        if e.error_code == ErrorCode.PASSWORD_ERROR:
            locked = await record_login_failure(request.user_account)
            if locked:
                logger.warning("登录失败超限，账号已锁定 userAccount=%s", request.user_account)
        # IP 级：累计所有登录失败（含账号不存在），防跨账号撞库
        if ip:
            ip_locked = await record_login_ip_failure(ip)
            if ip_locked:
                logger.warning("登录失败超限，IP 已锁定 ip=%s", ip)
        raise

    # 登录成功：清空该账号失败计数与锁定标记（IP 级计数不清空，避免用正确凭据重置撞库计数）
    await clear_login_failures(request.user_account)

    # 生成 Session ID
    session_id = generate_session_id()

    # 保存到 Redis
    # by_alias=True，序列化时使用驼峰命名，确保存入 Redis 的字段名和前端接口保持一致
    await set_session(session_id, {"user": user.model_dump(by_alias=True)})

    # 设置 Cookie
    response.set_cookie(
        key="SESSION",
        value=session_id,
        max_age=settings.session_max_age,
        httponly=True,  # 让 Cookie 无法被 JavaScript 读取，防止 XSS 攻击
        samesite="lax"  # 防止 CSRF 攻击
    )
    logger.info(f"登录成功，ip：{ip or '未知'}")
    return BaseResponse.success(data=user, message="登录成功")


@router.post("/logout", response_model=BaseResponse[bool])
async def logout(
    response: Response,
    current_user: Optional[LoginUserVO] = Depends(get_current_user)
):
    """用户登出"""
    # 删除 Cookie
    # HACK: 未清除 Redis 缓存
    response.delete_cookie(key="SESSION")
    
    return BaseResponse.success(data=True, message="登出成功")


@router.get("/get/login", response_model=BaseResponse[LoginUserVO])
async def get_login_user(
    current_user: LoginUserVO = Depends(require_login)
):
    """获取当前登录用户"""
    return BaseResponse.success(data=current_user)


@router.get("/get", response_model=BaseResponse[UserVO])
async def get_user_by_id(
    id: int,
    db: Database = Depends(get_db)
):
    """根据 ID 获取用户"""
    service = UserService(db)
    user = await service.get_by_id(id)
    return BaseResponse.success(data=user)


@router.get("/profile", response_model=BaseResponse[UserProfileVO])
async def get_user_profile(
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login),
):
    """获取当前登录用户的主页信息（个人详情页：基本信息 + 积分/配额 + 创作数量等统计）"""
    service = UserService(db)
    profile = await service.get_profile(current_user.id)
    throw_if_not(profile, ErrorCode.NOT_FOUND_ERROR, "用户不存在")
    return BaseResponse.success(data=profile)


@router.post("/list/page", response_model=BaseResponse[dict])
async def list_users_by_page(
    request: UserQueryRequest,
    db: Database = Depends(get_db),
    _: LoginUserVO = Depends(require_admin)
):
    """分页查询用户列表（管理员）"""
    service = UserService(db)
    users, total = await service.list_by_page(request)
    
    return BaseResponse.success(data={
        "records": users,
        "total": total,
        "current": request.current,
        "size": request.page_size
    })


@router.post("/add", response_model=BaseResponse[int])
async def add_user(
    request: UserAddRequest,
    db: Database = Depends(get_db),
    _: LoginUserVO = Depends(require_admin)
):
    """添加用户（管理员）"""
    service = UserService(db)
    user_id = await service.add_user(request)
    return BaseResponse.success(data=user_id, message="添加成功")


@router.post("/update", response_model=BaseResponse[bool])
async def update_user(
    request: UserUpdateRequest,
    db: Database = Depends(get_db),
    _: LoginUserVO = Depends(require_admin)
):
    """更新用户（管理员）"""
    service = UserService(db)
    result = await service.update_user(request)
    return BaseResponse.success(data=result, message="更新成功")


@router.post("/delete", response_model=BaseResponse[bool])
async def delete_user(
    request: DeleteRequest,
    db: Database = Depends(get_db),
    _: LoginUserVO = Depends(require_admin)
):
    """删除用户（管理员）"""
    service = UserService(db)
    result = await service.delete_user(request.id)
    return BaseResponse.success(data=result, message="删除成功")


@router.post("/profile/update", response_model=BaseResponse[LoginUserVO])
async def update_user_profile(
    request: UserProfileUpdateRequest,
    db: Database = Depends(get_db),
    session_id: Optional[str] = Depends(get_session_id),
    current_user: LoginUserVO = Depends(require_login),
):
    """更新当前登录用户的个人资料（昵称/头像/简介）

    更新成功后同步刷新 Redis Session 中的用户信息，
    保证下次 GET /user/get/login 返回最新资料。
    """
    service = UserService(db)
    user = await service.update_profile(current_user.id, request)
    throw_if_not(user, ErrorCode.NOT_FOUND_ERROR, "用户不存在")

    # 同步更新 Session（by_alias=True 与登录时保持一致）
    if session_id:
        await set_session(session_id, {"user": user.model_dump(by_alias=True)}) # type: ignore

    return BaseResponse.success(data=user, message="资料更新成功")


@router.post("/change-password", response_model=BaseResponse[bool])
async def change_password(
    request: UserChangePasswordRequest,
    response: Response,
    db: Database = Depends(get_db),
    session_id: Optional[str] = Depends(get_session_id),
    current_user: LoginUserVO = Depends(require_login),
):
    """修改当前登录用户的密码

    安全策略：修改成功后清除 Redis Session 与 Cookie，强制用户重新登录。
    """
    service = UserService(db)
    await service.change_password(current_user.id, request)

    if session_id:
        await remove_session(session_id)
    response.delete_cookie(key="SESSION")

    return BaseResponse.success(data=True, message="密码修改成功，请重新登录")


@router.post("/avatar/upload", response_model=BaseResponse[str])
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: LoginUserVO = Depends(require_login),
):
    """上传用户头像（multipart/form-data，字段名 file）

    仅支持 JPG / PNG / WebP / GIF，大小不超过 2MB；
    文件保存到本地 static/images/avatar/，返回可访问的图片 URL。
    """
    # 校验 MIME 类型与扩展名（双重校验，防止伪造类型）
    content_type = (file.content_type or "").lower()
    throw_if(
        content_type not in _ALLOWED_AVATAR_TYPES,
        ErrorCode.PARAMS_ERROR,
        "仅支持 JPG/PNG/WebP/GIF 格式的头像",
    )
    ext = os.path.splitext(file.filename or "")[1].lower()
    throw_if(ext not in _ALLOWED_AVATAR_EXTS, ErrorCode.PARAMS_ERROR, "不支持的文件格式")

    content = await file.read()
    throw_if(len(content) == 0, ErrorCode.PARAMS_ERROR, "文件内容为空")
    throw_if(len(content) > _MAX_AVATAR_SIZE, ErrorCode.PARAMS_ERROR, "头像大小不能超过 2MB")

    image_data = ImageData.from_bytes(content, mime_type=content_type)
    url = await _get_avatar_file_service().upload_image_data(image_data, folder="avatar")
    throw_if_not(url, ErrorCode.OPERATION_ERROR, "头像上传失败")

    return BaseResponse.success(data=url, message="头像上传成功")
