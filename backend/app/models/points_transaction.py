"""积分流水 ORM 模型。

对应表 points_transaction：记录每笔积分变动（获得/消耗），
amount 为正表示获得、为负表示消耗，balanceAfter 为变动后余额。
"""

from sqlalchemy import Column, BigInteger, Integer, String, DateTime
from sqlalchemy.sql import func

from app.database import Base


class PointsTransaction(Base):
    """积分流水表。

    Attributes:
        id: 主键。
        user_id: 用户 ID。
        task_id: 关联任务 ID（生成类流水必填，其余可为空）。
        type: 流水类型（REGISTER/SIGN_IN/RECHARGE/USAGE_RESERVE/USAGE_SETTLE/USAGE_REFUND/ADMIN_ADJUST）。
        amount: 变动积分（正=获得，负=消耗）。
        balance_after: 变动后余额。
        description: 描述。
        create_time: 创建时间。
    """

    __tablename__ = "points_transaction"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    user_id = Column("userId", BigInteger, nullable=False, comment="用户ID")
    task_id = Column("taskId", String(64), nullable=True, comment="关联任务ID")
    type = Column(String(32), nullable=False, comment="类型：REGISTER/SIGN_IN/RECHARGE/USAGE_RESERVE/USAGE_SETTLE/USAGE_REFUND/ADMIN_ADJUST")
    amount = Column(Integer, nullable=False, comment="变动积分（正=获得，负=消耗）")
    balance_after = Column("balanceAfter", Integer, nullable=False, comment="变动后余额")
    description = Column(String(255), nullable=True, comment="描述")
    create_time = Column("createTime", DateTime, nullable=False, default=func.now(), comment="创建时间")