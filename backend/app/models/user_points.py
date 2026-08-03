"""用户积分账户 ORM 模型。

对应表 user_points：每个用户一条记录，balance 为权威积分余额，
version 用于乐观锁防并发超扣，user 表的 points 列仅为冗余展示。
"""

from sqlalchemy import Column, BigInteger, Integer, DateTime
from sqlalchemy.sql import func

from app.database import Base


class UserPoints(Base):
    """用户积分账户表。

    Attributes:
        id: 主键。
        user_id: 用户 ID（唯一）。
        balance: 当前积分余额。
        total_earned: 累计获得积分。
        total_consumed: 累计消耗积分。
        version: 乐观锁版本号。
        create_time: 创建时间。
        update_time: 更新时间。
    """

    __tablename__ = "user_points"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    user_id = Column("userId", BigInteger, nullable=False, unique=True, comment="用户ID")
    balance = Column(Integer, nullable=False, default=0, comment="当前积分余额")
    total_earned = Column("totalEarned", Integer, nullable=False, default=0, comment="累计获得积分")
    total_consumed = Column("totalConsumed", Integer, nullable=False, default=0, comment="累计消耗积分")
    version = Column(Integer, nullable=False, default=0, comment="乐观锁版本号")
    create_time = Column("createTime", DateTime, nullable=False, default=func.now(), comment="创建时间")
    update_time = Column("updateTime", DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment="更新时间")