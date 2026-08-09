"""站内信 ORM 模型。

对应表 message：记录发给用户的站内信（系统通知/反馈回复/VIP 开通/积分变动，以及管理员主动发信）。
全体广播采用写时展开，每个目标用户各插入一行；删除为软删（isDelete）。
"""

from sqlalchemy import Column, BigInteger, DateTime, SmallInteger, String, Text
from sqlalchemy.sql import func

from app.database import Base


class Message(Base):
    """站内信表。

    Attributes:
        id: 主键。
        user_id: 收件用户 ID（全体广播写时展开为每用户一行）。
        type: 类型（SYSTEM/FEEDBACK/VIP/POINTS）。
        title: 标题。
        content: 内容。
        link: 跳转链接（前端路由）。
        related_id: 关联业务 ID（如反馈 ID）。
        is_read: 是否已读。
        read_time: 阅读时间。
        sender_id: 发送者用户 ID（管理员主动发信为管理员 ID；系统自动触发为空，用于管理端已发列表）。
        create_time: 创建时间。
        is_delete: 是否删除（软删）。
    """

    __tablename__ = "message"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    user_id = Column("userId", BigInteger, nullable=False, comment="收件用户ID（全体广播写时展开为每用户一行）")
    type = Column(String(32), nullable=False, default="SYSTEM", comment="类型：SYSTEM/FEEDBACK/VIP/POINTS")
    title = Column(String(200), nullable=False, comment="标题")
    content = Column(Text, nullable=True, comment="内容")
    link = Column(String(512), nullable=True, comment="跳转链接（前端路由）")
    related_id = Column("relatedId", BigInteger, nullable=True, comment="关联业务ID（如反馈ID）")
    is_read = Column("isRead", SmallInteger, nullable=False, default=0, comment="是否已读")
    read_time = Column("readTime", DateTime, nullable=True, comment="阅读时间")
    sender_id = Column("senderId", BigInteger, nullable=True, comment="发送者用户ID（管理员主动发信；系统自动触发为空）")
    create_time = Column("createTime", DateTime, nullable=False, default=func.now(), comment="创建时间")
    is_delete = Column("isDelete", SmallInteger, nullable=False, default=0, comment="是否删除")
