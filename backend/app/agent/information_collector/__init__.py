"""
信息采集智能体模块

基于 LangChain create_agent 构建的多工具信息采集 Agent，
支持 Serper API 搜索、DDGS 网页抓取和轻量模型摘要。

省 token 设计：主 Agent 仅输出"相关文章引用列表"（url + title），
完整 ``NewsArticleSummary`` 摘要由 ``collect()`` 后处理从 ToolMessage 拼装，
避免昂贵的主模型照搬子 Agent 长摘要造成巨大输出 token 开销。

使用方式:
    from app.agent.information_collector import InformationCollectorAgent

    service = InformationCollectorAgent()
    result = await service.collect("AI领域最新进展")
"""

from app.agent.information_collector.agent import InformationCollectorAgent
from app.agent.information_collector.schemas import (
    CollectResult,
    InformationCollectionResult,
    NewsArticleSummary,
    RelevantArticleRef,
    SerperNewsItem,
)

__all__ = [
    "InformationCollectorAgent",
    "InformationCollectionResult",
    "CollectResult",
    "RelevantArticleRef",
    "NewsArticleSummary",
    "SerperNewsItem",
]