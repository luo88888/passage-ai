"""
配额 / 并发 / 僵尸任务限制
"""

from pydantic_settings import BaseSettings


class QuotaConfig(BaseSettings):
    """积分透支护栏 / 并发限制 / 僵尸任务"""

    max_debt_points: int = 200
    max_active_tasks: int = 5
    task_stale_hours: int = 24

    # 注册速率限制：同一 IP 在窗口内最多注册次数
    register_ip_max_count: int = 5
    register_ip_window_seconds: int = 3600
    # 是否信任反向代理传递的 X-Forwarded-For（直连 uvicorn 时保持 False，防止伪造头绕过）
    trust_forwarded_headers: bool = False

    # 登录失败限流：单账号窗口内失败次数超限后锁定一段时间（防密码爆破）
    login_fail_max_count: int = 5
    login_fail_window_seconds: int = 1800   # 失败计数窗口（30 分钟）
    login_lock_seconds: int = 300           # 超限后锁定时长（5 分钟）

    # 登录失败限流（IP 级）：同一 IP 窗口内登录失败超限后锁定一段时间（防跨账号撞库）
    login_ip_max_count: int = 10
    login_ip_window_seconds: int = 1800     # 失败计数窗口（30 分钟）
    login_ip_lock_seconds: int = 300        # 超限后锁定时长（5 分钟）

    # 多智能体图片并行
    agent_image_max_concurrency: int = 3
    agent_image_fail_fast: bool = True
