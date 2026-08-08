"""
Agent LLM 配置：信息采集 + 标题 / 大纲 / 正文 / 配图分析
"""

from pydantic_settings import BaseSettings


class AgentConfig(BaseSettings):
    """各智能体 LLM 配置（空 provider/model 回退到全局默认）"""

    # ======== 信息采集（主 Agent） ========
    info_collector_main_provider: str = "deepseek"
    info_collector_main_model: str = "deepseek-v4-flash"
    info_collector_main_temperature: float = 0.2
    info_collector_main_thinking: bool = True
    info_collector_main_reasoning_effort: str = "low"

    # 信息采集（子 Agent）
    info_collector_sub_provider: str = "deepseek"
    info_collector_sub_model: str = "deepseek-v4-flash"
    info_collector_sub_temperature: float = 1.0

    # 信息采集工具限制
    info_collector_serper_tool_limit: int = 5
    info_collector_extract_tool_limit: int = 10
    info_collector_global_tool_limit: int = 20
    info_collector_thread_limit: int = 40

    # 信息采集选文数量
    info_collector_article_count_min: int = 1
    info_collector_article_count_max: int = 10
    info_collector_relevant_news_count: int = 10

    # 信息采集并行
    info_collector_max_concurrency: int = 5
    info_collector_max_content_chars: int = 30000
    info_collector_serper_num: int = 10

    # ======== 标题生成 ========
    title_agent_provider: str = ""
    title_agent_model: str = ""
    title_agent_temperature: float = 1.3
    title_agent_thinking: bool = True
    title_agent_reasoning_effort: str = "high"

    # ======== 大纲生成 ========
    outline_agent_provider: str = ""
    outline_agent_model: str = ""
    outline_agent_temperature: float = 1.0
    outline_agent_thinking: bool = True
    outline_agent_reasoning_effort: str = "high"

    # ======== 正文生成 ========
    content_agent_provider: str = ""
    content_agent_model: str = ""
    content_agent_temperature: float = 0.6
    content_agent_thinking: bool = True
    content_agent_reasoning_effort: str = "low"

    # ======== 配图需求分析 ========
    image_analyzer_agent_provider: str = ""
    image_analyzer_agent_model: str = ""
    image_analyzer_agent_temperature: float = 0.2
    image_analyzer_agent_thinking: bool = True
    image_analyzer_agent_reasoning_effort: str = "high"
