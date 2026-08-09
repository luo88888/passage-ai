"""站内信服务。

负责站内信的写入（send_message 可复用工具）、用户端分页/未读数/已读/删除，以及管理端发送
（SINGLE/BATCH/ALL 写时展开）与已发列表。

设计约定（docs/local/意见反馈与站内信功能开发计划.md v1.1）：
- 发信不阻塞主流程：send_message 默认失败只记日志（raise_on_error=False），
  反馈回复 / VIP 开通 / 积分调整等主操作不因通知失败而回滚；
- 未读数直接用 DB count 实时查询（用户量小，避免 Redis 缓存与 DB 不一致）；
- 全体广播写时展开：每个目标用户各插入一行；senderId 标记管理员主动发信，用于管理端已发列表。
"""

from typing import List, Optional, Tuple

from databases import Database
from databases.interfaces import Record

from app.constants.message import MessageConstant
from app.exceptions import ErrorCode, throw_if, throw_if_not
from app.schemas.message import (
    AdminMessageQueryRequest,
    AdminMessageSendRequest,
    AdminMessageVO,
    MessageDeleteRequest,
    MessageQueryRequest,
    MessageReadRequest,
    MessageVO,
)
from app.utils.logger import logger


def _fmt(dt) -> Optional[str]:
    """格式化 datetime 为 ISO 字符串（None 原样返回）。"""
    return dt.isoformat() if dt else None


class MessageService:
    """站内信服务。

    Attributes:
        db: 异步数据库连接。
    """

    def __init__(self, db: Database):
        """初始化站内信服务。

        Args:
            db: databases 异步数据库连接实例。
        """
        self.db = db

    # ==================== 写入（可复用工具） ====================

    async def send_message(
        self,
        user_id: int,
        msg_type: str = MessageConstant.TYPE_SYSTEM,
        title: str = "",
        content: Optional[str] = None,
        link: Optional[str] = None,
        related_id: Optional[int] = None,
        sender_id: Optional[int] = None,
        raise_on_error: bool = False,
    ) -> Optional[int]:
        """写入一条站内信（可复用工具）。

        供反馈回复 / VIP 开通 / 积分调整 / 管理员发信等场景调用。发信独立于主业务，
        默认失败只记日志不抛出（raise_on_error=False），避免通知失败阻塞/回滚主流程。

        Args:
            user_id: 收件用户 ID。
            msg_type: 消息类型（SYSTEM/FEEDBACK/VIP/POINTS）。
            title: 标题（超长截断至 DDL 上限 200）。
            content: 内容。
            link: 跳转链接（前端路由）。
            related_id: 关联业务 ID（如反馈 ID）。
            sender_id: 发送者用户 ID（管理员主动发信为管理员 ID；系统自动触发为空）。
            raise_on_error: 失败时是否抛出异常。

        Returns:
            新消息 ID；失败且 raise_on_error=False 时返回 None。

        Raises:
            Exception: raise_on_error=True 且写入失败时抛出原始异常。
        """
        try:
            msg_id = await self.db.execute(
                query="""
                    INSERT INTO message (userId, type, title, content, link, relatedId, senderId, isRead, createTime)
                    VALUES (:userId, :type, :title, :content, :link, :relatedId, :senderId, 0, NOW())
                """,
                values={
                    "userId": user_id,
                    "type": msg_type,
                    "title": (title or "")[: MessageConstant.MAX_TITLE_LENGTH],
                    "content": content,
                    "link": link,
                    "relatedId": related_id,
                    "senderId": sender_id,
                },
            )
            return int(msg_id)
        except Exception:
            logger.exception(
                "发送站内信失败 user_id=%s, type=%s, title=%s", user_id, msg_type, title
            )
            if raise_on_error:
                raise
            return None

    # ==================== 管理端发送 ====================

    async def send(self, admin_id: int, request: AdminMessageSendRequest) -> int:
        """管理员发送站内信（SINGLE/BATCH/ALL 写时展开）。

        单用户写 1 条，批量/全体为每个目标用户各插入一行；发送者记录为管理员 ID，
        供管理端「已发列表」查询。

        Args:
            admin_id: 发送管理员 ID。
            request: 发送请求。

        Returns:
            成功写入的消息条数。

        Raises:
            BusinessException: 收件人类型/消息类型不合法，或目标用户不存在。
        """
        throw_if(
            request.target_type not in MessageConstant.TARGETS,
            ErrorCode.PARAMS_ERROR,
            "收件人类型不合法",
        )
        throw_if(
            request.type not in MessageConstant.TYPES,
            ErrorCode.PARAMS_ERROR,
            "消息类型不合法",
        )

        user_ids = await self._resolve_target_user_ids(request)
        throw_if(not user_ids, ErrorCode.PARAMS_ERROR, "目标用户不存在")

        count = 0
        async with self.db.transaction():
            for user_id in user_ids:
                msg_id = await self.send_message(
                    user_id=user_id,
                    msg_type=request.type,
                    title=request.title.strip(),
                    content=request.content,
                    link=request.link,
                    sender_id=admin_id,
                    raise_on_error=True,
                )
                if msg_id:
                    count += 1

        logger.info(
            "管理员发送站内信 adminId=%s, targetType=%s, count=%s",
            admin_id, request.target_type, count,
        )
        return count

    async def _resolve_target_user_ids(self, request: AdminMessageSendRequest) -> List[int]:
        """解析目标收件用户 ID 列表（过滤已删除/不存在的用户）。

        Args:
            request: 发送请求。

        Returns:
            目标用户 ID 列表。
        """
        if request.target_type == MessageConstant.TARGET_ALL:
            rows = await self.db.fetch_all("SELECT id FROM user WHERE isDelete = 0")
            return [int(r["id"]) for r in rows]

        ids = request.user_ids or []
        throw_if(not ids, ErrorCode.PARAMS_ERROR, "目标用户不能为空")
        if request.target_type == MessageConstant.TARGET_SINGLE:
            throw_if(len(ids) != 1, ErrorCode.PARAMS_ERROR, "单用户发送需指定 1 个用户 ID")

        placeholders = ", ".join(f":uid_{i}" for i in range(len(ids)))
        rows = await self.db.fetch_all(
            f"SELECT id FROM user WHERE id IN ({placeholders}) AND isDelete = 0",
            values={f"uid_{i}": v for i, v in enumerate(ids)},
        )
        return [int(r["id"]) for r in rows]

    # ==================== 用户端 ====================

    async def page(self, user_id: int, query: MessageQueryRequest) -> Tuple[List[MessageVO], int]:
        """分页查询当前用户站内信（未读优先 + createTime 倒序，type 可选筛选）。

        Args:
            user_id: 当前用户 ID。
            query: 分页查询参数。

        Returns:
            (消息列表, 总数)。
        """
        where = "WHERE userId = :userId AND isDelete = 0"
        values = {"userId": user_id}
        if query.type:
            where += " AND type = :type"
            values["type"] = query.type # type: ignore

        total = await self.db.fetch_val(f"SELECT COUNT(*) FROM message {where}", values=values)
        rows = await self.db.fetch_all(
            f"""SELECT * FROM message {where}
                ORDER BY isRead ASC, createTime DESC, id DESC
                LIMIT :limit OFFSET :offset""",
            values={
                **values,
                "limit": query.page_size,
                "offset": (query.current - 1) * query.page_size,
            },
        )
        return [self._to_vo(r) for r in rows], int(total or 0)

    async def get_detail(self, user_id: int, message_id: int) -> MessageVO:
        """查询单条站内信详情（仅本人，归属校验）。

        Args:
            user_id: 当前用户 ID。
            message_id: 消息 ID。

        Returns:
            消息视图对象。

        Raises:
            BusinessException: 消息不存在或不属于当前用户（NOT_FOUND_ERROR）。
        """
        row = await self.db.fetch_one(
            query="""
                SELECT * FROM message
                WHERE id = :id AND userId = :userId AND isDelete = 0
            """,
            values={"id": message_id, "userId": user_id},
        )
        throw_if_not(row, ErrorCode.NOT_FOUND_ERROR, "消息不存在")
        return self._to_vo(row)  # type: ignore
    async def unread_count(self, user_id: int) -> int:
        """查询当前用户未读站内信数。

        DB count 实时查询（用户量小），避免 Redis 缓存与 DB 不一致。

        Args:
            user_id: 当前用户 ID。

        Returns:
            未读消息数。
        """
        row = await self.db.fetch_one(
            query="""
                SELECT COUNT(*) AS cnt FROM message
                WHERE userId = :userId AND isRead = 0 AND isDelete = 0
            """,
            values={"userId": user_id},
        )
        return int(row["cnt"]) if row else 0

    async def mark_read(self, user_id: int, request: MessageReadRequest) -> int:
        """标记已读（单条 ids 或全部 all），仅本人。

        Args:
            user_id: 当前用户 ID。
            request: 已读请求。

        Returns:
            本次标记条数。

        Raises:
            BusinessException: ids 为空且未指定 all。
        """
        if request.all:
            query = """
                UPDATE message SET isRead = 1, readTime = NOW()
                WHERE userId = :userId AND isRead = 0 AND isDelete = 0
            """
            values = {"userId": user_id}
        else:
            ids = request.ids or []
            throw_if(not ids, ErrorCode.PARAMS_ERROR, "请指定要标记已读的消息")
            placeholders = ", ".join(f":mid_{i}" for i in range(len(ids)))
            query = (
                "UPDATE message SET isRead = 1, readTime = NOW() "
                f"WHERE userId = :userId AND id IN ({placeholders}) AND isDelete = 0"
            )
            values = {"userId": user_id, **{f"mid_{i}": v for i, v in enumerate(ids)}}

        affected = await self.db.execute(query=query, values=values)
        return int(affected or 0)

    async def delete(self, user_id: int, request: MessageDeleteRequest) -> int:
        """删除站内信（软删，仅本人）。

        Args:
            user_id: 当前用户 ID。
            request: 删除请求（ids）。

        Returns:
            本次删除条数。
        """
        ids = request.ids
        placeholders = ", ".join(f":mid_{i}" for i in range(len(ids)))
        query = (
            "UPDATE message SET isDelete = 1 "
            f"WHERE userId = :userId AND id IN ({placeholders}) AND isDelete = 0"
        )
        values = {"userId": user_id, **{f"mid_{i}": v for i, v in enumerate(ids)}}
        affected = await self.db.execute(query=query, values=values)
        return int(affected or 0)

    # ==================== 管理端 ====================

    async def admin_page(
        self, query: AdminMessageQueryRequest
    ) -> Tuple[List[AdminMessageVO], int]:
        """管理端已发消息分页（senderId 非空 = 管理员主动发信，含单/批量/全体广播展开行）。

        Args:
            query: 分页查询参数（type/关键字筛选）。

        Returns:
            (消息列表, 总数)。
        """
        where = "WHERE senderId IS NOT NULL AND isDelete = 0"
        values: dict = {}
        if query.type:
            where += " AND type = :type"
            values["type"] = query.type
        if query.keyword:
            where += " AND (title LIKE :kw OR content LIKE :kw)"
            values["kw"] = f"%{query.keyword}%"

        total = await self.db.fetch_val(
            f"SELECT COUNT(*) FROM message {where}", values=values
        )
        rows = await self.db.fetch_all(
            f"""SELECT * FROM message {where}
                ORDER BY createTime DESC, id DESC
                LIMIT :limit OFFSET :offset""",
            values={
                **values,
                "limit": query.page_size,
                "offset": (query.current - 1) * query.page_size,
            },
        )
        return [self._to_admin_vo(r) for r in rows], int(total or 0)

    # ==================== 内部实现 ====================

    def _to_vo(self, row: Record) -> MessageVO:
        """Record → MessageVO。"""
        d = dict(row)
        return MessageVO(
            id=d["id"],
            userId=d["userId"],
            type=d["type"],
            title=d["title"],
            content=d.get("content"),
            link=d.get("link"),
            relatedId=d.get("relatedId"),
            isRead=bool(d.get("isRead")),
            readTime=_fmt(d.get("readTime")),
            createTime=_fmt(d.get("createTime")),
        )

    def _to_admin_vo(self, row: Record) -> AdminMessageVO:
        """Record → AdminMessageVO（在 MessageVO 基础上附带发送者信息）。"""
        vo = self._to_vo(row)
        return AdminMessageVO(
            id=vo.id,
            userId=vo.user_id,
            type=vo.type,
            title=vo.title,
            content=vo.content,
            link=vo.link,
            relatedId=vo.related_id,
            isRead=vo.is_read,
            readTime=vo.read_time,
            createTime=vo.create_time,
            senderId=dict(row).get("senderId"),
        )
