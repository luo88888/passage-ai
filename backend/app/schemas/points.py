"""积分相关请求/响应模型。

提供积分余额、积分流水、模型用量记录/统计、模型计价等视图对象（VO），
字段均使用与前端接口一致的驼峰别名，供路由层序列化返回。
"""

from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.common import PageRequest


class PointsBalanceVO(BaseModel):
    """积分余额视图对象。

    Attributes:
        balance: 当前积分余额。
        total_earned: 累计获得积分。
        total_consumed: 累计消耗积分。
        checked_in_today: 今日是否已签到。
    """

    balance: int = Field(default=0, description="当前积分余额")
    total_earned: int = Field(default=0, alias="totalEarned", description="累计获得积分")
    total_consumed: int = Field(default=0, alias="totalConsumed", description="累计消耗积分")
    checked_in_today: bool = Field(default=False, alias="checkedInToday", description="今日是否已签到")

    class Config:
        populate_by_name = True


class PointsCheckinVO(BaseModel):
    """每日签到结果视图对象。

    Attributes:
        checked_in: 本次是否签到成功。
        gained: 本次赠送积分。
        balance: 签到后积分余额。
    """

    checked_in: bool = Field(default=False, alias="checkedIn", description="本次是否签到成功")
    gained: int = Field(default=0, description="本次赠送积分")
    balance: int = Field(default=0, description="签到后积分余额")

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


class PointsTransactionQueryRequest(PageRequest):
    """积分流水分页查询请求。

    Attributes:
        type: 流水类型筛选（REGISTER/SIGN_IN/USAGE_SETTLE/ADMIN_ADJUST 等）。
        start_time: 起始时间（含）。
        end_time: 结束时间（含）。
        min_amount: 最小变动积分。
        max_amount: 最大变动积分。
    """

    type: Optional[str] = Field(None, description="流水类型筛选")
    start_time: Optional[str] = Field(None, alias="startTime", description="起始时间（含）")
    end_time: Optional[str] = Field(None, alias="endTime", description="结束时间（含）")
    min_amount: Optional[int] = Field(None, alias="minAmount", description="最小变动积分")
    max_amount: Optional[int] = Field(None, alias="maxAmount", description="最大变动积分")


class PointsUsageStatsQueryRequest(BaseModel):
    """用户各模型用量统计查询请求。

    Attributes:
        start_time: 起始时间（含，默认全部）。
        end_time: 结束时间（含）。
    """

    start_time: Optional[str] = Field(None, alias="startTime", description="起始时间（含）")
    end_time: Optional[str] = Field(None, alias="endTime", description="结束时间（含）")


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


class ModelPricingSaveRequest(BaseModel):
    """模型计价新增请求。

    Attributes:
        category: 类别（LLM / IMAGE）。
        provider: 提供商。
        model: 模型名（LLM 用 * 通配兜底）。
        agent_name: 按 Agent 细分（空=不限）。
        input_price_per_1k: 输入 token 单价（积分/1k token）。
        output_price_per_1k: 输出 token 单价（积分/1k token）。
        price_per_image: 每张图积分（IMAGE）。
        enabled: 是否启用。
    """

    category: str = Field(..., description="类别：LLM / IMAGE")
    provider: str = Field(..., description="提供商")
    model: str = Field(..., description="模型名（LLM 用 * 通配兜底）")
    agent_name: Optional[str] = Field(None, alias="agentName", description="按 Agent 细分（空=不限）")
    input_price_per_1k: float = Field(0, alias="inputPricePer1k", description="输入 token 单价（积分/1k token）")
    output_price_per_1k: float = Field(0, alias="outputPricePer1k", description="输出 token 单价（积分/1k token）")
    price_per_image: float = Field(0, alias="pricePerImage", description="每张图积分（IMAGE）")
    enabled: bool = Field(True, description="是否启用")


class ModelPricingUpdateRequest(BaseModel):
    """模型计价更新请求（按 id 更新）。

    Attributes:
        id: 计价配置 ID。
        category: 类别（LLM / IMAGE）。
        provider: 提供商。
        model: 模型名。
        agent_name: 按 Agent 细分（空=不限）。
        input_price_per_1k: 输入 token 单价（积分/1k token）。
        output_price_per_1k: 输出 token 单价（积分/1k token）。
        price_per_image: 每张图积分（IMAGE）。
        enabled: 是否启用。
    """

    id: int = Field(..., description="计价配置 ID")
    category: str = Field(..., description="类别：LLM / IMAGE")
    provider: str = Field(..., description="提供商")
    model: str = Field(..., description="模型名")
    agent_name: Optional[str] = Field(None, alias="agentName", description="按 Agent 细分（空=不限）")
    input_price_per_1k: float = Field(0, alias="inputPricePer1k", description="输入 token 单价（积分/1k token）")
    output_price_per_1k: float = Field(0, alias="outputPricePer1k", description="输出 token 单价（积分/1k token）")
    price_per_image: float = Field(0, alias="pricePerImage", description="每张图积分（IMAGE）")
    enabled: bool = Field(True, description="是否启用")


class AdminPointsTransactionsRequest(PointsTransactionQueryRequest):
    """管理端按用户查询积分流水请求。

    Attributes:
        user_id: 目标用户 ID（必填）。
    """

    user_id: int = Field(..., alias="userId", description="目标用户 ID")


class AdminPointsAdjustRequest(BaseModel):
    """管理员手工调整用户积分请求。

    Attributes:
        user_id: 目标用户 ID。
        amount: 调整积分（正=赠送，负=扣减，不允许 0）。
        description: 调整说明（展示在流水描述）。
    """

    user_id: int = Field(..., alias="userId", description="目标用户 ID")
    amount: int = Field(..., description="调整积分（正=赠送，负=扣减）")
    description: str = Field(..., description="调整说明")


class PointsOverviewVO(BaseModel):
    """全局积分/用量看板视图对象（管理端）。

    Attributes:
        user_count: 积分账户数。
        total_earned: 累计发放积分。
        total_consumed: 累计消耗积分。
        total_balance: 全体用户当前余额合计。
        usage_record_count: 模型用量记录条数。
        total_cost_points: 用量累计折算积分。
        today_checkin_count: 今日签到人数。
        today_checkin_points: 今日签到发放积分合计。
    """

    user_count: int = Field(default=0, alias="userCount", description="积分账户数")
    total_earned: int = Field(default=0, alias="totalEarned", description="累计发放积分")
    total_consumed: int = Field(default=0, alias="totalConsumed", description="累计消耗积分")
    total_balance: int = Field(default=0, alias="totalBalance", description="全体用户当前余额合计")
    usage_record_count: int = Field(default=0, alias="usageRecordCount", description="模型用量记录条数")
    total_cost_points: int = Field(default=0, alias="totalCostPoints", description="用量累计折算积分")
    today_checkin_count: int = Field(default=0, alias="todayCheckinCount", description="今日签到人数")
    today_checkin_points: int = Field(default=0, alias="todayCheckinPoints", description="今日签到发放积分合计")


class AdminUsageQueryRequest(PageRequest):
    """管理端模型用量查询请求。

    Attributes:
        user_id: 按用户筛选（可选）。
        category: 按类别筛选（LLM / IMAGE，可选）。
        model: 按模型筛选（可选）。
        start_time: 起始时间（含）。
        end_time: 结束时间（含）。
    """

    user_id: Optional[int] = Field(None, alias="userId", description="按用户筛选")
    category: Optional[str] = Field(None, description="类别：LLM / IMAGE")
    model: Optional[str] = Field(None, description="模型名")
    start_time: Optional[str] = Field(None, alias="startTime", description="起始时间（含）")
    end_time: Optional[str] = Field(None, alias="endTime", description="结束时间（含）")