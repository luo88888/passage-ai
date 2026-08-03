"""模型用量记录 ORM 模型。

对应表 model_usage_record：记录每个用户每次任务中各 LLM / AI 生图模型的
调用次数、token 消耗、耗时与积分成本，是「各模型使用情况统计」的核心表。
"""

from sqlalchemy import Column, BigInteger, Integer, String, DateTime
from sqlalchemy.sql import func

from app.database import Base


class ModelUsageRecord(Base):
    """模型用量记录表。

    Attributes:
        id: 主键。
        user_id: 用户 ID。
        task_id: 任务 ID（生成类流水必填）。
        category: 类别（LLM / IMAGE）。
        provider: 提供商（Xiaomi/DeepSeek/Zhipu/NanoBanana）。
        model: 模型名（如 mimo-v2.5-pro / cogview-3-flash）。
        agent_name: 智能体名称（如 title/outline/content/info_collector_main）。
        call_count: 调用次数。
        input_tokens: 输入 token 数（LLM）。
        output_tokens: 输出 token 数（LLM）。
        image_count: 生成图片张数（IMAGE）。
        cost_points: 本记录消耗积分。
        status: 状态（SUCCESS/FAILED）。
        start_time: 开始时间。
        end_time: 结束时间。
        create_time: 创建时间。
    """

    __tablename__ = "model_usage_record"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    user_id = Column("userId", BigInteger, nullable=False, comment="用户ID")
    task_id = Column("taskId", String(64), nullable=True, comment="任务ID")
    category = Column(String(16), nullable=False, comment="类别：LLM / IMAGE")
    provider = Column(String(32), nullable=False, comment="提供商：Xiaomi/DeepSeek/Zhipu/NanoBanana")
    model = Column(String(64), nullable=False, comment="模型名")
    agent_name = Column("agentName", String(50), nullable=True, comment="智能体名称")
    call_count = Column("callCount", Integer, nullable=False, default=1, comment="调用次数")
    input_tokens = Column("inputTokens", Integer, nullable=True, comment="输入token（LLM）")
    output_tokens = Column("outputTokens", Integer, nullable=True, comment="输出token（LLM）")
    image_count = Column("imageCount", Integer, nullable=True, comment="生成图片张数（IMAGE）")
    cost_points = Column("costPoints", Integer, nullable=False, default=0, comment="本记录消耗积分")
    status = Column(String(16), nullable=False, default="SUCCESS", comment="SUCCESS/FAILED")
    start_time = Column("startTime", DateTime, nullable=False, comment="开始时间")
    end_time = Column("endTime", DateTime, nullable=True, comment="结束时间")
    create_time = Column("createTime", DateTime, nullable=False, default=func.now(), comment="创建时间")