"""IP 提取与固定窗口限流（注册/登录防爆破、意见反馈每日限流）。"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Request

from app.config import settings
from app.redis import get_client
from app.utils.logger import logger
from app.exceptions import ErrorCode, throw_if


def _register_key(ip: str) -> str:
    """构造注册计数 Redis key。"""
    return f"register_ip:{ip}"


def get_client_ip(request: Request) -> Optional[str]:
    """从请求中提取客户端 IP。

    默认直连模式取 request.client.host；
    仅当 trust_forwarded_headers 开启且存在 X-Forwarded-For 时取最左侧非空项
    （若经可信代理转发，转发方会覆盖该头，最左侧为真实客户端地址）。

    Args:
        request: FastAPI 请求对象。

    Returns:
        客户端 IP；无法确定时返回 None
    """
    if settings.trust_forwarded_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            first = forwarded.split(",")[0].strip()
            if first:
                return first
    return request.client.host if request.client else None


async def check_register_rate_limit(ip: str) -> bool:
    """检查该 IP 在窗口内注册次数是否已超限。

    Redis 不可用时拦截；使用 INCR + EXPIRE 首次设过期时间。

    Args:
        ip: 客户端 IP。

    Returns:
        True=放行；False=窗口内注册次数已达上限，应拒绝。

    """
    redis = get_client()
    if not redis:
        logger.error("redis 未初始化，停止注册服务注册 ip=%s", ip)
        throw_if(True, ErrorCode.SYSTEM_ERROR)
        return False

    key = _register_key(ip)
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, settings.register_ip_window_seconds)
    return count <= settings.register_ip_max_count


def _login_fail_key(account: str) -> str:
    """构造登录失败计数 key。"""
    return f"login_fail:{account}"


def _login_lock_key(account: str) -> str:
    """构造登录锁定 key。"""
    return f"login_lock:{account}"


async def is_login_locked(account: str) -> bool:
    """账号是否处于登录锁定状态。

    Args:
        account: 登录账号。

    Returns:
        True=已锁定（Redis 不可用时拦截）。
    """
    redis = get_client()
    if not redis:
        logger.error("redis 未初始化，停止登录功能")
        throw_if(True, ErrorCode.SYSTEM_ERROR)
        return True
    return bool(await redis.exists(_login_lock_key(account)))


async def record_login_failure(account: str) -> bool:
    """记录一次登录失败，失败次数超限时锁定账号。

    窗口内计数用 INCR + 首建 EXPIRE 滚动过期；超限后设置锁定 key（TTL=锁定时长）。

    Args:
        account: 登录账号。

    Returns:
        True=本次失败后账号被锁定；False=尚未锁定。
    """
    redis = get_client()
    if not redis:
        return False

    key = _login_fail_key(account)
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, settings.login_fail_window_seconds)

    if count >= settings.login_fail_max_count:
        await redis.set(
            _login_lock_key(account),
            "1",
            ex=settings.login_lock_seconds,
        )
        return True
    return False


async def clear_login_failures(account: str) -> None:
    """登录成功后清空失败计数与锁定标记。"""
    redis = get_client()
    if not redis:
        return
    await redis.delete(_login_fail_key(account))
    await redis.delete(_login_lock_key(account))


def _login_ip_fail_key(ip: str) -> str:
    """构造 IP 登录失败计数 key。"""
    return f"login_ip_fail:{ip}"


def _login_ip_lock_key(ip: str) -> str:
    """构造 IP 登录锁定 key。"""
    return f"login_ip_lock:{ip}"


async def is_login_ip_locked(ip: str) -> bool:
    """该 IP 是否处于登录锁定状态。

    Args:
        ip: 客户端 IP。

    Returns:
        True=已锁定（Redis 不可用时拦截）。
    """
    redis = get_client()
    if not redis:
        logger.error("redis 未初始化，停止登录功能")
        throw_if(True, ErrorCode.SYSTEM_ERROR)
        return True
    return bool(await redis.exists(_login_ip_lock_key(ip)))


async def record_login_ip_failure(ip: str) -> bool:
    """记录该 IP 一次登录失败，超限时锁定 IP。

    撞库（跨账号高频试探）场景需累计所有登录失败（含账号不存在），
    因此与账号级计数不同，这里不做错误码过滤。

    Args:
        ip: 客户端 IP。

    Returns:
        True=本次失败后 IP 被锁定；False=尚未锁定。
    """
    redis = get_client()
    if not redis:
        return False

    key = _login_ip_fail_key(ip)
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, settings.login_ip_window_seconds)

    if count >= settings.login_ip_max_count:
        await redis.set(
            _login_ip_lock_key(ip),
            "1",
            ex=settings.login_ip_lock_seconds,
        )
        return True
    return False


# ==================== 意见反馈每日限流（Redis 固定窗口） ====================
# 按北京时区（Asia/Shanghai）自然日计数：中国无夏令时，固定 UTC+8，不依赖 tzdata。
SHANGHAI_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


def _feedback_daily_key(user_id: int, day: str) -> str:
    """构造意见反馈每日计数 Redis key。"""
    return f"feedback_daily:{user_id}:{day}"


async def check_feedback_daily_limit(user_id: int) -> bool:
    """检查该用户当天（北京时间自然日）反馈提交次数是否超限。

    固定窗口：INCR + 首建 EXPIRE（TTL 一天），key 带日期，跨天自动换窗口。
    Redis 不可用时拦截（与注册/登录限流一致，避免限流失效）。

    Args:
        user_id: 用户 ID。

    Returns:
        True=放行；False=当天提交次数已达上限，应拒绝。

    Raises:
        BusinessException: Redis 未初始化（SYSTEM_ERROR）。
    """
    redis = get_client()
    if not redis:
        logger.error("redis 未初始化，停止反馈提交 user_id=%s", user_id)
        throw_if(True, ErrorCode.SYSTEM_ERROR)
        return False

    day = datetime.now(SHANGHAI_TZ).strftime("%Y%m%d")
    key = _feedback_daily_key(user_id, day)
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, settings.feedback_daily_window_seconds)
    return count <= settings.feedback_daily_limit
