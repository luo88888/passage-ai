"""积分相关请求/响应模型。

提供积分余额、积分流水、模型用量记录/统计、模型计价等视图对象（VO），
字段均使用与前端接口一致的驼峰别名，供路由层序列化返回。
"""

from typing import Optional
from pydantic import BaseModel, Field


class PointsBalanceVO(BaseModel):
    """积分余额视图对象。

    Attributes:
        balance: 当前积分余额。
        total_earned: 累计获得积分。
        total_consumed: 累计消耗积分。
    """

    balance: int = Field(default=0, description="当前积分余额")
    total_earned: int = Field(default=0, alias="totalEarned", description="累计获得积分")
    total_consumed: int = Field(default=0, alias="totalConsumed", description="累计消耗积分")

    class Config:
        populate_by_name = True


class PointsTransactionVO(BaseModel):
    """积分流水视图对象。

    Attributes:
        id: 流水 ID。
        user_id: 用户 ID。
        task_id: 关联任务 ID。
        type: 流水类型。
        amount: 变动积分（正=获得，负=消耗）。
        balance_after: 变动后余额。
        description: 描述。
        create_time: 创建时间。
    """

    id: int
    user_id: int = Field(..., alias="userId")
    task_id: Optional[str] = Field(None, alias="taskId")
    type: str
    amount: int
    balance_after: int = Field(..., alias="balanceAfter")
    description: Optional[str] = None
    create_time: str = Field(..., alias="createTime")

    class Config:
        populate_by_name = True


class ModelUsageRecordVO(BaseModel):
    """模型用量记录视图对象。

    Attributes:
        id: 记录 ID。
        user_id: 用户 ID。
        task_id: 任务 ID。
        category: 类别（LLM / IMAGE）。
        provider: 提供商。
        model: 模型名。
        agent_name: 智能体名称。
        call_count: 调用次数。
        input_tokens: 输入 token 数（LLM）。
        output_tokens: 输出 token 数（LLM）。
        image_count: 生成图片张数（IMAGE）。
        cost_points: 消耗积分。
        status: 状态。
        start_time: 开始时间。
        end_time: 结束时间。
        create_time: 创建时间。
    """

    id: int
    user_id: int = Field(..., alias="userId")
    task_id: Optional[str] = Field(None, alias="taskId")
    category: str
    provider: str
    model: str
    agent_name: Optional[str] = Field(None, alias="agentName")
    call_count: int = Field(default=1, alias="callCount")
    input_tokens: Optional[int] = Field(None, alias="inputTokens")
    output_tokens: Optional[int] = Field(None, alias="outputTokens")
    image_count: Optional[int] = Field(None, alias="imageCount")
    cost_points: int = Field(default=0, alias="costPoints")
    status: str = "SUCCESS"
    start_time: str = Field(..., alias="startTime")
    end_time: Optional[str] = Field(None, alias="endTime")
    create_time: str = Field(..., alias="createTime")

    class Config:
        populate_by_name = True


class ModelUsageStatsVO(BaseModel):
    """用户各模型用量聚合视图对象。

    按 (category, provider, model) 聚合一个用户在某时间范围内的用量汇总。

    Attributes:
        category: 类别（LLM / IMAGE）。
        provider: 提供商。
        model: 模型名。
        call_count: 总调用次数。
        input_tokens: 总输入 token 数。
        output_tokens: 总输出 token 数。
        image_count: 总生成图片张数。
        cost_points: 总消耗积分。
    """

    category: str
    provider: str
    model: str
    call_count: int = Field(default=0, alias="callCount")
    input_tokens: int = Field(default=0, alias="inputTokens")
    output_tokens: int = Field(default=0, alias="outputTokens")
    image_count: int = Field(default=0, alias="imageCount")
    cost_points: int = Field(default=0, alias="costPoints")

    class Config:
        populate_by_name = True


class ModelPricingVO(BaseModel):
    """模型计价视图对象。

    Attributes:
        id: 计价配置 ID。
        category: 类别（LLM / IMAGE）。
        provider: 提供商。
        model: 模型名。
        agent_name: 按 Agent 细分（空=不限）。
        input_price_per_1k: 输入 token 单价（积分/1k token）。
        output_price_per_1k: 输出 token 单价（积分/1k token）。
        price_per_image: 每张图积分。
        enabled: 是否启用。
    """

    id: int
    category: str
    provider: str
    model: str
    agent_name: Optional[str] = Field(None, alias="agentName")
    input_price_per_1k: float = Field(default=0, alias="inputPricePer1k")
    output_price_per_1k: float = Field(default=0, alias="outputPricePer1k")
    price_per_image: float = Field(default=0, alias="pricePerImage")
    enabled: bool = True

    class Config:
        populate_by_name = True