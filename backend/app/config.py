"""
配置管理
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


# 获取根目录（backend）
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    """
    配置类
    """

    # 服务器配置
    server_port: int = 8567
    server_host: str = "0.0.0.0"

    # 数据库配置
    db_host: str
    db_port: int = 3306
    db_name: str
    db_user: str
    db_password: str

    # Redis 配置
    redis_host: str
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    # Session 配置
    session_secret_key: str
    session_max_age: int = 2592000  # 30天

    # 文章创建去重窗口（秒）：同一用户 + 相同参数在此窗口内不可重复提交
    dedup_window_seconds: int = 60

    # 密码加密盐值
    password_salt: str
   
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # AI 配置
    dashscope_api_key: str
    dashscope_model: str = "qwen-plus"

    # Pexels 图片搜索
    pexels_api_key: str

    # 腾讯云 COS
    tencent_cos_secret_id: str
    tencent_cos_secret_key: str
    tencent_cos_region: str
    tencent_cos_bucket: str
    tencent_cos_domain: str = ""

    # 本地文件存储（临时替代 COS）
    static_base_url: str = "http://localhost:8567"

    # ==================== 配图类 ====================
    # Nano Banana / Gemini AI 生图
    nano_banana_api_key: str
    nano_banana_model: str = "gemini-2.5-flash-image"
    nano_banana_aspect_ratio: str = "16:9"
    nano_banana_image_size: str = "1K"
    nano_banana_output_mime_type: str = "image/png"

    # 智谱 GLM-Image AI 生图（提供 key 后即启用，空则注册时跳过）
    zhipu_api_key: str = ""
    # cogview-3-flash:  1024x1024、768x1344、864x1152、1344x768、1152x864、1440x720、720x1440
    # glm-image: 1568x1056
    zhipu_image_model: str = "cogview-3-flash"
    zhipu_image_size: str = "1152x864"
    # 智谱开放平台生图并发上限为 1，超出会限流失败；此为单服务最大并发
    zhipu_image_max_concurrency: int = 1
    # 生成接口超时（秒）：AI 生图耗时可能较长，过短会 ReadTimeout
    zhipu_image_timeout: int = 120

    # Mermaid 配置
    mermaid_cli_command: str = "mmdc"
    mermaid_background_color: str = "transparent"
    mermaid_output_format: str = "svg"
    mermaid_width: int = 1200
    mermaid_timeout: int = 30000    # ms

    # Iconify 配置
    iconify_api_url: str = "https://api.iconify.design"
    iconify_search_limit: int = 10
    iconify_default_height: int = 64
    iconify_default_color: str = ""

    # 表情包管理
    emoji_pack_search_url: str = "https://cn.bing.com/images/async"
    emoji_pack_suffix: str = "表情包"
    emoji_pack_timeout: int = 10000

    # SVG 示意图配置
    svg_diagram_default_width: int = 800
    svg_diagram_default_height: int = 600
    svg_diagram_folder: str = "svg-diagrams"

    # SVG 示意图生成 LLM 配置（用 llm_factory 路由，空值回退到全局默认）
    # 默认 mimo-v2.5-pro，带思考模型更适合 SVG 代码生成
    svg_diagram_agent_provider: str = "Xiaomi"
    svg_diagram_agent_model: str = "mimo-v2.5-pro"
    svg_diagram_agent_temperature: float = 0.2
    svg_diagram_agent_thinking: bool = False
    svg_diagram_agent_reasoning_effort: str = "high"

    # ==================== Stripe 支付配置 ====================
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_success_url: str = "http://localhost:5173/payment/success"
    stripe_cancel_url: str = "http://localhost:5173/payment/cancel"

    # ===================== 积分与并发限制（M3：后付费段级结算） =====================
    # 积分透支护栏：余额允许为负，最多透支 max_debt_points（100 积分 = 1 元）
    max_debt_points: int = 200
    # 单用户「进行中（含挂起）」创作任务上限（activeTaskCount 原子计数，仅 admin 豁免）
    max_active_tasks: int = 5
    # 僵尸任务判定阈值（小时）：用于对账/清理识别长时间未完成的任务（本期仅对账计数，不强制清理）
    task_stale_hours: int = 24

    # 多智能体并行编排配置
    agent_image_max_concurrency: int = 3
    agent_image_fail_fast: bool = True
    deepseek_api_key: str = ""

    # ===================== LLM 模型配置 ======================
    default_llm_provider: str = "Xiaomi"
    default_model: str = "mimo-v2.5"

    # Serper 搜索 API（信息采集 Agent 用）
    serper_api_key: str = ""

    # ===================== Agent 配置 ========================

    # ---------- 信息采集 Agent（information_collector） ----------
    # 主 Agent（搜索规划 + 筛选），通常用较贵、带思考的模型
    info_collector_main_provider: str = "deepseek"
    info_collector_main_model: str = "deepseek-v4-flash"
    info_collector_main_temperature: float = 0.2
    info_collector_main_thinking: bool = False
    info_collector_main_reasoning_effort: str = "high"

    # 子 Agent（单篇文章摘要），用轻量模型即可
    info_collector_sub_provider: str = "deepseek"
    info_collector_sub_model: str = "deepseek-v4-flash"
    info_collector_sub_temperature: float = 1.0

    # 工具调用次数限制（兜底防失控）
    info_collector_serper_tool_limit: int = 5      # serper_search 单工具调用上限
    info_collector_extract_tool_limit: int = 10     # extract_article_content 单工具调用上限
    info_collector_global_tool_limit: int = 20     # 全局工具调用上限（兜底）
    info_collector_thread_limit: int = 40           # 线程级步数上限

    # 选文 / 返回数量范围
    info_collector_article_count_min: int = 1       # 选文数量下限
    info_collector_article_count_max: int = 10       # 选文数量上限
    info_collector_relevant_news_count: int = 10     # 最终返回的相关新闻数上限

    # 并行与上下文保护
    info_collector_max_concurrency: int = 5         # batch_extract_articles 最大并行数
    info_collector_max_content_chars: int = 30000   # 单篇文章抓取后截断长度
    info_collector_serper_num: int = 10             # Serper 单次返回结果数

    # ===================== 文章生成 Agent LLM 配置 =====================
    # 空字符串 = 使用上方的 default_llm_provider / default_model

    # ---------- 标题生成 Agent ----------
    title_agent_provider: str = ""
    title_agent_model: str = ""
    title_agent_temperature: float = 1.5
    title_agent_thinking: bool = False
    title_agent_reasoning_effort: str = "high"

    # ---------- 大纲生成 Agent ----------
    outline_agent_provider: str = ""
    outline_agent_model: str = ""
    outline_agent_temperature: float = 1.0
    outline_agent_thinking: bool = True
    outline_agent_reasoning_effort: str = "low"

    # ---------- 正文生成 Agent ----------
    content_agent_provider: str = ""
    content_agent_model: str = ""
    content_agent_temperature: float = 1.3
    content_agent_thinking: bool = True
    content_agent_reasoning_effort: str = "low"

    # ---------- 配图需求分析 Agent ----------
    image_analyzer_agent_provider: str = ""
    image_analyzer_agent_model: str = ""
    image_analyzer_agent_temperature: float = 0.2
    image_analyzer_agent_thinking: bool = True
    image_analyzer_agent_reasoning_effort: str = "low"

    @property
    def database_url(self) -> str:
        """
        获取数据库连接 URL
        """
        return f"mysql+pymysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"

    @property
    def redis_url(self) -> str:
        """
        获取 Redis 连接 URL
        """
        if self.redis_password:
            return f"redis://{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


settings = Settings()
