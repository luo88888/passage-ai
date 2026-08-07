"""信息采集节点（新闻题材专用，接入主图编排）

bootstrap 后由条件边 route_after_bootstrap 路由进入（仅 genre == "news" 触发）。
本节点：
  - 读 state：task_id / topic / genre
  - 复用 app.agent.information_collector.agent.InformationCollectorAgent.collect()
    采集与选题相关的最新新闻报道，整理成可注入提示词的摘要文本
  - 结构化结果落库 article.researchData（供创作页/详情页可视化回看）
  - 发 RESEARCH_COMPLETE SSE（携带采集条数 + 搜索词 + 新闻条目结构化列表）
  - return {"collected_news": <摘要文本>}（供下游 title/outline/content 节点注入提示词）

失败契约：采集异常不阻塞流程——捕获后 collected_news 置空，仍发 RESEARCH_COMPLETE(count=0)，
继续由 add_edge(NODE_RESEARCH, NODE_GENERATE_TITLE) 推进标题生成，避免整篇 FAILED。
落库失败同样 best-effort：记日志不阻断。

Agent 访问：模块级单例 get_information_collector() 懒构造 InformationCollectorAgent
（其内部经 llm_factory 自建模型与工具链，不依赖 ArticleService，无 services→graph 循环风险）。
"""
from __future__ import annotations

from typing import Any, Dict

from app.agent.information_collector.agent import InformationCollectorAgent
from app.agent.information_collector.schemas import NewsArticleSummary
from app.graph.sse_bridge import send_sse_message
from app.graph.state import ArticleState
from app.models.enums import SseMessageTypeEnum
from app.utils.logger import logger

# 模块级单例：信息采集 Agent 构造较重（建 LangChain agent + 工具链），全进程复用
_collector: InformationCollectorAgent | None = None


def get_information_collector() -> InformationCollectorAgent:
    """懒加载信息采集 Agent 单例"""
    global _collector
    if _collector is None:
        _collector = InformationCollectorAgent()
    return _collector


def _format_news_context(result: Any) -> str:
    """把 InformationCollectionResult 整理成供提示词注入的参考文本（markdown 列表）。

    每条形如：《标题》(来源, 时间)：摘要。空结果返回空串。
    """
    if not result or not result.relevant_articles:
        return ""
    lines = []
    for a in result.relevant_articles:
        source = a.source or "未知"
        pub = a.publish_time or ""
        brief = f"- 《{a.title}》(来源:{source}"
        if pub:
            brief += f", {pub}"
        brief += f")：{a.summary}"
        lines.append(brief)
    return "\n".join(lines)


def _to_research_article(article: NewsArticleSummary) -> Dict[str, Any]:
    """把单条 NewsArticleSummary 转成可落库/下发 SSE 的结构化 dict（camelCase）"""
    return {
        "title": article.title,
        "url": article.url,
        "summary": article.summary,
        "publishTime": article.publish_time,
        "source": article.source,
        "author": article.author,
        "tags": article.tags or [],
    }


async def research_node(state: ArticleState) -> Dict[str, Any]:
    """信息采集节点：新闻题材采集相关报道，结构化落库 + 下发 SSE + 产出提示词参考文本"""
    task_id = state.get("task_id") or ""
    topic = state.get("topic") or ""
    logger.info("[graph] 信息采集开始, taskId=%s, topic=%s", task_id, topic)

    # requirement 构造：顺带给出题材语义，让采集 Agent 聚焦新闻/时事报道
    requirement = f"请采集与以下新闻主题相关的最新报道与事实信息：{topic}"

    count = 0
    news_context = ""
    search_queries_used: list = []
    articles: list = []
    try:
        collector = get_information_collector()
        result = await collector.collect(requirement)
        count = len(result.relevant_articles) if result else 0
        news_context = _format_news_context(result)
        if result:
            search_queries_used = result.search_queries_used or []
            articles = [_to_research_article(a) for a in result.relevant_articles]
    except Exception as e:
        # 采集失败不阻塞流程：news_context 保持空，count=0
        logger.warning("[graph] 信息采集失败,继续生成（不带参考）, taskId=%s, error=%s", task_id, e)

    research_data = {
        "requirement": requirement,
        "searchQueriesUsed": search_queries_used,
        "articles": articles,
    }
    # 结构化结果落库（best-effort：落库失败不阻断，创作页/详情页回看面板显示空）
    try:
        from app.database import database
        from app.services.article_service import ArticleService

        await ArticleService(database).save_research_data(task_id, research_data)
    except Exception as e:
        logger.warning("[graph] 信息采集结果落库失败, taskId=%s, error=%s", task_id, e)

    send_sse_message(
        task_id,
        SseMessageTypeEnum.RESEARCH_COMPLETE,
        {
            "count": count,
            "searchQueriesUsed": search_queries_used,
            "articles": articles,
        },
    )
    return {"collected_news": news_context}
