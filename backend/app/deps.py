"""依赖注入"""

import uuid
from typing import Optional
from fastapi import Cookie, Depends, HTTPException, status

from databases import Database

from app.config import settings
from app.constants.user import UserConstant
from app.database import get_db
from app.exceptions import ErrorCode, BusinessException, throw_if
from app.schemas.user import LoginUserVO
from app.services.points_service import PointsService
from app.utils.session import get_session
from app.utils.logger import logger


async def get_session_id(session_id: Optional[str] = Cookie(None, alias="SESSION")) -> Optional[str]:
    """从 Cookie 中获取 Session ID"""
    return session_id


async def get_current_user(
    session_id: Optional[str] = Depends(get_session_id)
) -> Optional[LoginUserVO]:
    """获取当前登录用户（可选）"""
    if not session_id:
        return None

    session_data = await get_session(session_id)
    if not session_data or "user" not in session_data:
        return None

    user_data = session_data["user"]
    return LoginUserVO(**user_data)


async def require_login(
    current_user: Optional[LoginUserVO] = Depends(get_current_user)
) -> LoginUserVO:
    """要求必须登录"""
    if not current_user:
        logger.warning("访问需要登录的接口但未登录")
        raise BusinessException(ErrorCode.NOT_LOGIN_ERROR)
    return current_user


async def require_admin(
    current_user: LoginUserVO = Depends(require_login)
) -> LoginUserVO:
    """要求必须是管理员"""
    if current_user.user_role != "admin":
        logger.warning("无管理员权限访问受控接口 userId=%s, userRole=%s",
                       current_user.id, current_user.user_role)
        raise BusinessException(ErrorCode.NO_AUTH_ERROR)
    return current_user


async def require_create_slot(
    current_user: LoginUserVO = Depends(require_login),
    db: Database = Depends(get_db),
) -> LoginUserVO:
    """创建文章前置闸门：余额 >= 0 且进行中任务数 < max_active_tasks（快速失败）。

    仅 admin 豁免（不限并发、不校验余额）；VIP 与普通用户同价按积分结算。
    权威原子校验（activeTaskCount+1）在 create_article_task_with_slot_check 的事务内完成，
    本依赖只做读侧快速失败，避免无效请求进入事务/启动图任务。

    Args:
        current_user: 当前登录用户。
        db: 异步数据库连接。

    Returns:
        通过校验的当前用户。

    Raises:
        BusinessException: 欠费（INSUFFICIENT_POINTS）或并发超限（OPERATION_ERROR）。
    """
    if current_user.user_role == UserConstant.ADMIN_ROLE:
        return current_user

    points_service = PointsService(db)
    balance = await points_service.get_balance(current_user.id)
    throw_if(
        balance < 0,
        ErrorCode.INSUFFICIENT_POINTS,
        f"当前欠费 {-balance} 积分，请先签到/充值后再创作",
    )

    row = await db.fetch_one(
        query="SELECT activeTaskCount FROM user WHERE id = :userId AND isDelete = 0",
        values={"userId": current_user.id},
    )
    active_count = int(row["activeTaskCount"]) if row else 0
    throw_if(
        active_count >= settings.max_active_tasks,
        ErrorCode.OPERATION_ERROR,
        f"进行中创作任务数已达上限（最多 {settings.max_active_tasks} 个），请先完成或删除后再创建",
    )
    return current_user


def generate_session_id() -> str:
    """生成 Session ID"""
    return str(uuid.uuid4())