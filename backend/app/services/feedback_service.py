"""意见反馈服务。

负责意见反馈的提交（每日限流 + 联系方式校验）、我的反馈分页/详情（归属校验）、
管理端分页/详情/回复/仅改状态，以及「管理员回复 → 发送 FEEDBACK 站内信」的联动
（发信失败只记日志，不阻塞回复主流程）。
"""

import json
import re
from typing import List, Optional, Tuple

from databases import Database
from databases.interfaces import Record

from app.config import settings
from app.constants.feedback import FeedbackConstant
from app.constants.message import MessageConstant
from app.exceptions import ErrorCode, throw_if, throw_if_not
from app.schemas.feedback import (
    AdminFeedbackQueryRequest,
    AdminFeedbackVO,
    FeedbackQueryRequest,
    FeedbackReplyRequest,
    FeedbackStatusRequest,
    FeedbackSubmitRequest,
    FeedbackVO,
)
from app.services.message_service import MessageService
from app.utils.logger import logger
from app.utils.rate_limit import check_feedback_daily_limit

# 联系方式校验（已确认：电话需为合法手机号、邮箱需通过格式校验，非法返回 PARAMS_ERROR）
_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


class FeedbackService:
    """意见反馈服务。

    Attributes:
        db: 异步数据库连接。
    """

    def __init__(self, db: Database):
        """初始化意见反馈服务。

        Args:
            db: databases 异步数据库连接实例。
        """
        self.db = db

    # ==================== 用户端 ====================

    async def submit(self, user_id: int, request: FeedbackSubmitRequest) -> int:
        """提交意见反馈（每日限流 + 参数校验 + 落库，初始状态 PENDING）。

        Args:
            user_id: 当前用户 ID。
            request: 提交请求。

        Returns:
            新反馈 ID。

        Raises:
            BusinessException: 参数非法（PARAMS_ERROR）或每日提交超限（REQUEST_TOO_FREQUENT）。
        """
        throw_if(
            request.type not in FeedbackConstant.TYPES,
            ErrorCode.PARAMS_ERROR,
            "反馈类型不合法",
        )
        throw_if(
            not request.content or not request.content.strip(),
            ErrorCode.PARAMS_ERROR,
            "反馈内容不能为空",
        )

        if request.contact:
            throw_if(
                not (_PHONE_RE.match(request.contact) or _EMAIL_RE.match(request.contact)),
                ErrorCode.PARAMS_ERROR,
                "联系方式格式不正确（需为手机号或邮箱）",
            )

        image_urls = request.image_urls or []
        throw_if(
            len(image_urls) > FeedbackConstant.MAX_IMAGE_COUNT,
            ErrorCode.PARAMS_ERROR,
            f"截图最多 {FeedbackConstant.MAX_IMAGE_COUNT} 张",
        )
        for url in image_urls:
            throw_if(
                not url or not url.strip() or len(url) > 1024,
                ErrorCode.PARAMS_ERROR,
                "截图 URL 不合法",
            )

        # 每日提交限流（Redis 固定窗口；Redis 不可用时拦截，避免限流失效）
        throw_if(
            not await check_feedback_daily_limit(user_id),
            ErrorCode.REQUEST_TOO_FREQUENT,
            f"今日反馈提交次数已达上限（{settings.feedback_daily_limit} 条），请明天再试",
        )

        feedback_id = await self.db.execute(
            query="""
                INSERT INTO feedback (userId, type, content, contact, imageUrls, status, createTime, updateTime)
                VALUES (:userId, :type, :content, :contact, :imageUrls, :status, NOW(), NOW())
            """,
            values={
                "userId": user_id,
                "type": request.type,
                "content": request.content.strip(),
                "contact": request.contact,
                "imageUrls": json.dumps(image_urls, ensure_ascii=False) if image_urls else None,
                "status": FeedbackConstant.STATUS_PENDING,
            },
        )
        logger.info("用户提交反馈 feedbackId=%s, userId=%s, type=%s", feedback_id, user_id, request.type)
        return int(feedback_id)

    async def page_mine(
        self, user_id: int, query: FeedbackQueryRequest
    ) -> Tuple[List[FeedbackVO], int]:
        """我的反馈分页（type/status 筛选，仅本人）。

        Args:
            user_id: 当前用户 ID。
            query: 分页查询参数。

        Returns:
            (反馈列表, 总数)。
        """
        where = "WHERE userId = :userId AND isDelete = 0"
        values = {"userId": user_id}
        if query.type:
            where += " AND type = :type"
            values["type"] = query.type         # type: ignore
        if query.status:
            where += " AND status = :status"
            values["status"] = query.status     # type: ignore

        total = await self.db.fetch_val(f"SELECT COUNT(*) FROM feedback {where}", values=values)
        rows = await self.db.fetch_all(
            f"""SELECT * FROM feedback {where}
                ORDER BY createTime DESC, id DESC
                LIMIT :limit OFFSET :offset""",
            values={
                **values,
                "limit": query.page_size,
                "offset": (query.current - 1) * query.page_size,
            },
        )
        return [self._to_vo(r) for r in rows], int(total or 0)

    async def get_detail(self, user_id: int, feedback_id: int) -> FeedbackVO:
        """反馈详情（仅本人，归属校验）。

        Args:
            user_id: 当前用户 ID。
            feedback_id: 反馈 ID。

        Returns:
            反馈视图对象。

        Raises:
            BusinessException: 反馈不存在或不属于当前用户（NOT_FOUND_ERROR）。
        """
        row = await self.db.fetch_one(
            query="""
                SELECT * FROM feedback
                WHERE id = :id AND userId = :userId AND isDelete = 0
            """,
            values={"id": feedback_id, "userId": user_id},
        )
        throw_if_not(row, ErrorCode.NOT_FOUND_ERROR, "反馈不存在")
        return self._to_vo(row) # type: ignore

    # ==================== 管理端 ====================

    async def admin_page(
        self, query: AdminFeedbackQueryRequest
    ) -> Tuple[List[AdminFeedbackVO], int]:
        """管理端全量分页（关键字/类型/状态/时间筛选，附带提交用户信息）。
        # NOTE: 性能开销大

        Args:
            query: 分页查询参数。

        Returns:
            (反馈列表, 总数)。
        """
        where = "WHERE f.isDelete = 0"
        values: dict = {}
        if query.keyword:
            where += " AND (u.userAccount LIKE :kw OR u.userName LIKE :kw OR f.content LIKE :kw)"
            values["kw"] = f"%{query.keyword}%"
        if query.type:
            where += " AND f.type = :type"
            values["type"] = query.type
        if query.status:
            where += " AND f.status = :status"
            values["status"] = query.status
        if query.start_time:
            where += " AND f.createTime >= :startTime"
            values["startTime"] = query.start_time
        if query.end_time:
            where += " AND f.createTime <= :endTime"
            values["endTime"] = query.end_time

        total = await self.db.fetch_val(
            f"SELECT COUNT(*) FROM feedback f LEFT JOIN user u ON u.id = f.userId {where}",
            values=values,
        )
        rows = await self.db.fetch_all(
            f"""SELECT f.*, u.userAccount, u.userName
                FROM feedback f LEFT JOIN user u ON u.id = f.userId
                {where}
                ORDER BY f.createTime DESC, f.id DESC
                LIMIT :limit OFFSET :offset""",
            values={
                **values,
                "limit": query.page_size,
                "offset": (query.current - 1) * query.page_size,
            },
        )
        return [self._to_admin_vo(r) for r in rows], int(total or 0)

    async def admin_detail(self, feedback_id: int) -> AdminFeedbackVO:
        """管理端反馈详情（含提交用户信息）。

        Args:
            feedback_id: 反馈 ID。

        Returns:
            管理端反馈视图对象。

        Raises:
            BusinessException: 反馈不存在（NOT_FOUND_ERROR）。
        """
        row = await self.db.fetch_one(
            query="""
                SELECT f.*, u.userAccount, u.userName
                FROM feedback f LEFT JOIN user u ON u.id = f.userId
                WHERE f.id = :id AND f.isDelete = 0
            """,
            values={"id": feedback_id},
        )
        throw_if_not(row, ErrorCode.NOT_FOUND_ERROR, "反馈不存在")
        return self._to_admin_vo(row) # type: ignore

    async def reply(self, admin_id: int, request: FeedbackReplyRequest) -> FeedbackVO:
        """管理员回复反馈（回复内容 + 状态，默认置 RESOLVED），并联动发送 FEEDBACK 站内信。

        发信独立于主流程：站内信发送失败只记日志，不因通知失败回滚回复。

        Args:
            admin_id: 回复管理员 ID。
            request: 回复请求。

        Returns:
            更新后的反馈视图对象。

        Raises:
            BusinessException: 状态不合法（PARAMS_ERROR）或反馈不存在（NOT_FOUND_ERROR）。
        """
        throw_if(
            request.status not in FeedbackConstant.STATUSES,
            ErrorCode.PARAMS_ERROR,
            "处理状态不合法",
        )
        row = await self.db.fetch_one(
            query="SELECT * FROM feedback WHERE id = :id AND isDelete = 0",
            values={"id": request.id},
        )
        throw_if_not(row, ErrorCode.NOT_FOUND_ERROR, "反馈不存在")

        feedback_id = request.id
        reply_content = request.reply_content.strip() if request.reply_content else None

        await self.db.execute(
            query="""
                UPDATE feedback
                SET status = :status, replyContent = :replyContent, replyUserId = :replyUserId,
                    replyTime = NOW(), updateTime = NOW()
                WHERE id = :id
            """,
            values={
                "id": feedback_id,
                "status": request.status,
                "replyContent": reply_content,
                "replyUserId": admin_id,
            },
        )

        # 联动发送 FEEDBACK 站内信（link 指向反馈详情；失败只记日志，不阻塞回复主流程）
        try:
            await MessageService(self.db).send_message(
                user_id=int(row["userId"]), # type: ignore
                msg_type=MessageConstant.TYPE_FEEDBACK,
                title="您的意见反馈已回复" if reply_content else "您的意见反馈状态已更新",
                content=reply_content or f"您的反馈已处理，当前状态：{request.status}",
                link=f"{FeedbackConstant.LINK_PREFIX}{feedback_id}",
                related_id=feedback_id,
                raise_on_error=False,
            )
        except Exception:
            logger.exception("反馈回复联动发送站内信失败 feedbackId=%s", feedback_id)

        updated = await self.db.fetch_one(
            query="SELECT * FROM feedback WHERE id = :id AND isDelete = 0",
            values={"id": feedback_id},
        )
        return self._to_vo(updated)

    async def update_status(self, request: FeedbackStatusRequest) -> FeedbackVO:
        """管理员仅改状态（不回复；如需通知用户请走回复接口）。

        Args:
            request: 状态请求。

        Returns:
            更新后的反馈视图对象。

        Raises:
            BusinessException: 状态不合法（PARAMS_ERROR）或反馈不存在（NOT_FOUND_ERROR）。
        """
        throw_if(
            request.status not in FeedbackConstant.STATUSES,
            ErrorCode.PARAMS_ERROR,
            "处理状态不合法",
        )
        row = await self.db.fetch_one(
            query="SELECT * FROM feedback WHERE id = :id AND isDelete = 0",
            values={"id": request.id},
        )
        throw_if_not(row, ErrorCode.NOT_FOUND_ERROR, "反馈不存在")

        await self.db.execute(
            query="UPDATE feedback SET status = :status, updateTime = NOW() WHERE id = :id",
            values={"id": request.id, "status": request.status},
        )

        updated = await self.db.fetch_one(
            query="SELECT * FROM feedback WHERE id = :id AND isDelete = 0",
            values={"id": request.id},
        )
        return self._to_vo(updated) # type: ignore

    # ==================== 内部实现 ====================

    def _to_vo(self, row: Record) -> FeedbackVO:
        """Record → FeedbackVO。"""
        d = dict(row)
        image_urls = None
        if d.get("imageUrls"):
            try:
                parsed = json.loads(d["imageUrls"])
                image_urls = parsed if isinstance(parsed, list) else None
            except (TypeError, ValueError):
                image_urls = None
        return FeedbackVO(
            id=d["id"],
            userId=d["userId"],
            type=d["type"],
            content=d["content"],
            contact=d.get("contact"),
            imageUrls=image_urls,
            status=d["status"],
            replyContent=d.get("replyContent"),
            replyUserId=d.get("replyUserId"),
            replyTime=d["replyTime"].isoformat() if d.get("replyTime") else None,
            createTime=d["createTime"].isoformat() if d.get("createTime") else None,
            updateTime=d["updateTime"].isoformat() if d.get("updateTime") else None,
        )

    def _to_admin_vo(self, row: Record) -> AdminFeedbackVO:
        """Record → AdminFeedbackVO（在 FeedbackVO 基础上附带提交用户信息）。"""
        d = dict(row)
        vo = self._to_vo(row)
        return AdminFeedbackVO(
            id=vo.id,
            userId=vo.user_id,
            type=vo.type,
            content=vo.content,
            contact=vo.contact,
            imageUrls=vo.image_urls,
            status=vo.status,
            replyContent=vo.reply_content,
            replyUserId=vo.reply_user_id,
            replyTime=vo.reply_time,
            createTime=vo.create_time,
            updateTime=vo.update_time,
            userAccount=d.get("userAccount"),
            userName=d.get("userName"),
        )
