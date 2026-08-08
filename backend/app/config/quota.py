"""
配额 / 并发 / 僵尸任务限制
"""

from pydantic_settings import BaseSettings


class QuotaConfig(BaseSettings):
    """积分透支护栏 / 并发限制 / 僵尸任务"""

    max_debt_points: int = 200
    max_active_tasks: int = 5
    task_stale_hours: int = 24

    # 多智能体图片并行
    agent_image_max_concurrency: int = 3
    agent_image_fail_fast: bool = True
