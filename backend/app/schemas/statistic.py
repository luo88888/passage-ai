"""
Agent 执行日志相关请求/响应模型
"""

from typing import Dict, Optional, List
from pydantic import BaseModel, Field


class AgentLogVO(BaseModel):
    """智能体执行日志视图对象（单个智能体）"""

    id: int = Field(..., description="日志 ID")
    task_id: str = Field(..., alias="taskId", description="任务 ID")
    user_id: Optional[int] = Field(None, alias="userId", description="用户 ID")
    model: Optional[str] = Field(None, description="模型名")
    agent_name: str = Field(..., alias="agentName", description="智能体名称")
    start_time: str = Field(..., alias="startTime", description="开始时间")
    end_time: Optional[str] = Field(None, alias="endTime", description="结束时间")
    duration_ms: Optional[int] = Field(None, alias="durationMs", description="耗时（毫秒）")
    status: str = Field(..., description="状态：RUNNING/SUCCESS/FAILED")
    error_message: Optional[str] = Field(None, alias="errorMessage", description="错误信息")
    prompt: Optional[str] = Field(None, description="使用的 Prompt")
    input_data: Optional[str] = Field(None, alias="inputData", description="输入数据（JSON）")
    output_data: Optional[str] = Field(None, alias="outputData", description="输出数据（JSON）")
    create_time: str = Field(..., alias="createTime", description="创建时间")
    update_time: str = Field(..., alias="updateTime", description="更新时间")

    class Config:
        populate_by_name = True


class AgentExecutionStatsVO(BaseModel):
    """任务执行统计"""

    task_id: str = Field(..., alias="taskId", description="任务 ID")
    user_id: Optional[int] = Field(None, alias="userId", description="用户 ID")
    model: Optional[str] = Field(None, description="模型名")
    total_duration_ms: int = Field(..., alias="totalDurationMs", description="总耗时（毫秒）")
    agent_count: int = Field(..., alias="agentCount", description="智能体执行次数")
    agent_durations: Dict[str, int] = Field(default_factory=dict, alias="agentDurations", description="各智能体耗时映射（智能体名 → 毫秒）")
    overall_status: str = Field(..., alias="overallStatus", description="任务整体状态")
    logs: List[AgentLogVO] = Field(default_factory=list, description="智能体执行日志列表")

    class Config:
        populate_by_name = True


class StatisticsVO(BaseModel):
    """系统统计数据"""

    today_count: int = Field(..., alias="todayCount", description="今日新增文章数")
    week_count: int = Field(..., alias="weekCount", description="本周新增文章数")
    month_count: int = Field(..., alias="monthCount", description="本月新增文章数")
    total_count: int = Field(..., alias="totalCount", description="累计文章总数（未删除）")
    success_rate: float = Field(..., alias="successRate", description="成功率（百分比）")
    avg_duration_ms: int = Field(..., alias="avgDurationMs", description="已完成文章平均耗时（毫秒）")
    active_user_count: int = Field(..., alias="activeUserCount", description="活跃用户数（最近 7 天有创作的去重用户）")
    total_user_count: int = Field(..., alias="totalUserCount", description="用户总数（未删除）")
    vip_user_count: int = Field(..., alias="vipUserCount", description="VIP 用户数")
    quota_used: int = Field(..., alias="quotaUsed", description="普通用户已用配额")
    total_quota: int = Field(default=100, alias="totalQuota", description="普通用户总配额")

    class Config:
        populate_by_name = True
