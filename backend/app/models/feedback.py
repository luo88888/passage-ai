"""意见反馈 ORM 模型。

对应表 feedback：记录用户提交的意见反馈（类型/内容/联系方式/截图）与管理员的处理信息
（回复内容/处理状态），供用户跟踪处理进度、管理端集中筛选与处理。
"""

from sqlalchemy import Column, BigInteger, DateTime, SmallInteger, String, Text
from sqlalchemy.sql import func

from app.database import Base


class Feedback(Base):
    """意见反馈表。

    Attributes:
        id: 主键。
        user_id: 提交用户 ID。
        type: 类型（BUG/FEATURE/COMPLAINT/OTHER）。
        content: 反馈内容。
        contact: 联系方式（电话/邮箱）。
        image_urls: 截图 URL 列表（JSON 数组，最多 5 张）。
        status: 处理状态（PENDING/PROCESSING/RESOLVED）。
        reply_content: 管理员回复内容。
        reply_user_id: 回复管理员 ID。
        reply_time: 回复时间。
        create_time: 创建时间。
        update_time: 更新时间。
        is_delete: 是否删除。
    """

    __tablename__ = "feedback"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    user_id = Column("userId", BigInteger, nullable=False, comment="提交用户ID")
    type = Column(String(32), nullable=False, default="OTHER", comment="类型：BUG/FEATURE/COMPLAINT/OTHER")
    content = Column(Text, nullable=False, comment="反馈内容")
    contact = Column(String(128), nullable=True, comment="联系方式（电话/邮箱）")
    # 与文章表 enabledImageMethods/images 一致：DDL 为 json，ORM 用 Text + 手动 json.dumps/loads 读写
    image_urls = Column("imageUrls", Text, nullable=True, comment="截图URL列表（JSON数组，最多5张）")
    status = Column(String(32), nullable=False, default="PENDING", comment="状态：PENDING/PROCESSING/RESOLVED")
    reply_content = Column("replyContent", Text, nullable=True, comment="管理员回复内容")
    reply_user_id = Column("replyUserId", BigInteger, nullable=True, comment="回复管理员ID")
    reply_time = Column("replyTime", DateTime, nullable=True, comment="回复时间")
    create_time = Column("createTime", DateTime, nullable=False, default=func.now(), comment="创建时间")
    update_time = Column("updateTime", DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment="更新时间")
    is_delete = Column("isDelete", SmallInteger, nullable=False, default=0, comment="是否删除")
