"""
Session 管理工具
"""

import json
from typing import Optional, Any

from app.config import settings
from app.redis import get_client
from app.utils.logger import logger


def _get_session_key(session_id: str) -> str:
    """获取 Session Key"""
    return f"session:{session_id}"


# ====================== 读写和删除 Session 逻辑 ========================

async def get_session(session_id: str) -> Optional[dict]:
    """获取 Session 数据"""
    redis_client = get_client()
    if not redis_client:
        logger.error("redis_client 未初始化")
        return None

    key = _get_session_key(session_id)
    data = await redis_client.get(key)

    if data:
        return json.loads(data)
    return None


async def set_session(session_id: str, data: dict, expire: Optional[int] = None):
    """设置 Session 数据"""
    redis_client = get_client()
    if not redis_client:
        logger.error("redis_client 未初始化")
        return

    key = _get_session_key(session_id)
    expire_time = expire or settings.session_max_age

    await redis_client.setex(
        key,
        expire_time,
        json.dumps(data)
    )

async def remove_session(session_id: str):
    """删除 Session"""
    redis_client = get_client()
    if not redis_client:
        logger.error("redis_client 未初始化")
        return

    key = _get_session_key(session_id)
    await redis_client.delete(key)



