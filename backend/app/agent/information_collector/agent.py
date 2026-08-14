"""
信息采集 Agent —— 基于 LangChain create_agent 的多工具智能体

架构:
    ┌──────────────────────────────────────┐
    │         InformationCollectorAgent     │
    │                                      │
    │  ┌─────┐    ┌───────┐   ┌─────────┐  │
    │  │Main │───▶│Serper │──▶│ Batch   │  │
    │  │Agent│    │Search │   │Extract  │  │
    │  │     │    │(限次) │   │(并行)   │  │
    │  └─────┘    └───────┘   └─────────┘  │
    │                   │          │       │
    │                   ▼          ▼       │
    │              新闻列表    结构化摘要   │
    └──────────────────────────────────────┘

省 token 设计:
    主 Agent（昂贵的大模型）仅输出"相关文章引用列表"（url + title），**不重复摘要正文**。
    子 Agent（轻量模型）产出的 ``NewsArticleSummary`` 完整摘要只存在于 ToolMessage 中。
    ``collect()`` 后处理从 ToolMessage 反解析出摘要，按主 Agent 给的 url 引用列表拼装
    最终的 ``List[NewsArticleSummary]``，避免主模型照搬长摘要造成巨大输出 token 开销。

使用方式:
    from app.agent.information_collector.agent import InformationCollectorAgent

    service = InformationCollectorAgent()
    result = await service.collect("最近AI领域有什么重要进展？")
    print(result.model_dump_json(indent=2, ensure_ascii=False))
"""

from __future__ import annotations

import json
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import HumanMessage, ToolMessage

from app.agent.information_collector.schemas import (
    CollectResult,
    InformationCollectionResult,
    NewsArticleSummary,
)
from app.agent.information_collector.tools import (
    batch_extract_articles,
    extract_article_content,
    serper_search,
)
from app.config import settings
from app.llm_factory.factory import get_chat_model
from app.utils.logger import logger
from app.utils.json_tool import loads_with_repair
from app.services.model_usage_service import usage_context



# 会产出 NewsArticleSummary 的工具名（collect 后处理需识别这些 ToolMessage）
_SUMMARY_TOOL_NAMES = {
    "extract_article_content",
    "batch_extract_articles",
}


class InformationCollectorAgent:
    """信息采集主 Agent

    使用 LangChain create_agent 构建一个具备搜索 + 提取能力的智能体。
    模型、工具次数限制、选文数量、并行度等全部由 ``app.config.settings``
    的 ``info_collector_*`` 字段驱动，提示词据此动态构建。

    Agent 工作流程:
    1. 理解用户的信息需求
    2. 规划搜索策略（使用不同关键词和参数）
    3. 调用 serper_search 搜索（次数受 ``info_collector_serper_tool_limit`` 限制）
    4. 分析搜索结果，筛选最相关的新闻
    5. 调用 batch_extract_articles 并行提取内容（推荐）
    6. 结构化输出 CollectResult（仅 url+title 引用，不含摘要正文）

    最终对外结果由 ``collect()`` 后处理拼装:
    - 从 ToolMessage 反解析出 ``NewsArticleSummary`` 摘要
    - 按主 Agent 给的 url 引用列表组装 ``InformationCollectionResult``

    Parameters 均来自配置，详见 ``app.config.settings`` 的 ``info_collector_*`` 字段。
    """

    def __init__(self):
        self._init_agent()

    # ------------------------------------------------------------------ #
    # 构建主 Agent
    # ------------------------------------------------------------------ #

    def _build_system_prompt(self) -> str:
        """根据配置动态构建主 Agent 系统提示词。"""
        s = settings
        return (
            "你是一个专业的信息采集助手。你的任务是从互联网上收集与用户需求相关的新闻信息。\n\n"
            "## 工作流程\n"
            "1. **分析需求**：仔细理解用户的信息需求，确定关键搜索词\n"
            "2. **执行搜索**：使用 serper_search 工具进行搜索，"
            f"最多可调用 {s.info_collector_serper_tool_limit} 次\n"
            "   - 根据搜索结果，调整关键词或时间范围进行补充搜索\n"
            "   - 如果结果足够，可以不调用满设定的次数\n"
            f"3. **筛选文章**：从搜索结果中选择 {s.info_collector_article_count_min}-"
            f"{s.info_collector_article_count_max} 篇与需求最相关的文章获取摘要\n"
            "   - 优先选择标题和摘要高度相关的\n"
            "   - 优先选择知名来源和近期发布的\n"
            "4. **提取内容**：对选中的文章，推荐使用 batch_extract_articles 批量并行提取\n"
            f"   - 该工具最多可调用 {s.info_collector_batch_extract_tool_limit} 次，"
            f"单次并行度 max_concurrency 不超过 {s.info_collector_max_concurrency}\n"
            f"   - 也可逐篇调用 extract_article_content（最多可调用 "
            f"{s.info_collector_extract_tool_limit} 次）\n"
            "   - 达到某工具次数上限后，该工具会返回错误提示不再执行，"
            "请改用其他工具或直接进入整理阶段\n"
            "   - 对于内容可能高度相似的文章，不需要全部提取"
            "   - 信息足够即可，不需要提取所有文章内容"
            "5. **综合整理**：基于提取的内容，筛选出最终要纳入结果的相关文章\n"
            f"   - 最终输出 {s.info_collector_relevant_news_count} 篇以内相关文章\n\n"
            "## 注意事项\n"
            "- 搜索时尽量使用不同的关键词和参数组合，提高覆盖率\n"
            "- 中文需求请使用中文关键词搜索（gl=cn, hl=zh-cn）\n"
            "- 只选择真正相关的文章进行深度提取，无关文章直接跳过\n"
            "- 每篇文章提取后，注意核实信息是否与需求相关\n"
            f"- 工具调用总次数上限 {s.info_collector_global_tool_limit} 次，"
            "请优先用 batch_extract_articles 批量提取\n\n"
            "## 输出要求\n"
            "- 最终通过 response_format 输出 CollectResult，其中 relevant_article_refs "
            "**只列 url 与 title，不需复述文章摘要正文**\n"
            "- 文章摘要正文已由 batch_extract_articles / extract_article_content 工具产出，"
            "系统会自动从工具结果中拼装完整摘要\n"
            "- url 必须与你调用抓取工具时传入的某个 URL 完全一致，否则系统无法匹配拼装\n"
        )

    def _init_agent(self):
        """根据配置创建主 Agent（模型、工具、次数限制、结构化输出）。"""
        s = settings
        model = get_chat_model(
            provider=s.info_collector_main_provider,
            model_name=s.info_collector_main_model,
            temperature=s.info_collector_main_temperature,
            thinking=s.info_collector_main_thinking,
            reasoning_effort=s.info_collector_main_reasoning_effort,
        )

        # 1. serper_search 单工具次数限制：达到上限后工具不再执行，返回错误提示给 LLM，Agent 继续
        serper_limit_middleware = ToolCallLimitMiddleware(
            tool_name="serper_search",
            run_limit=s.info_collector_serper_tool_limit,
            exit_behavior="continue",
        )
        # 2. extract_article_content 单工具次数限制
        extract_limit_middleware = ToolCallLimitMiddleware(
            tool_name="extract_article_content",
            run_limit=s.info_collector_extract_tool_limit,
            exit_behavior="continue",
        )
        # 3. batch_extract_articles 单工具次数限制
        batch_extract_limit_middleware = ToolCallLimitMiddleware(
            tool_name="batch_extract_articles",
            run_limit=s.info_collector_batch_extract_tool_limit,
            exit_behavior="continue",
        )
        # 4. 全局工具调用限制（兜底保护）：达到上限直接结束整个任务
        global_limit_middleware = ToolCallLimitMiddleware(
            run_limit=s.info_collector_global_tool_limit,
            thread_limit=s.info_collector_thread_limit,
            exit_behavior="end",
        )

        self.agent = create_agent(
            model=model,
            tools=[serper_search, extract_article_content, batch_extract_articles],
            system_prompt=self._build_system_prompt(),
            # 注意顺序：具体的工具限制在前，全局兜底限制在最后
            middleware=[
                serper_limit_middleware,
                extract_limit_middleware,
                batch_extract_limit_middleware,
                global_limit_middleware,
            ],
            # 主 Agent 仅输出 url+title 引用列表，不输出摘要正文（省 token）
            response_format=ToolStrategy(CollectResult),
        )

    # ------------------------------------------------------------------ #
    # 执行 + 后处理拼装
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_summary_from_tool_message(msg: ToolMessage) -> list[NewsArticleSummary]:
        """从一条 ToolMessage 的 content 中解析出 NewsArticleSummary 列表。

        - extract_article_content：content 为单个 NewsArticleSummary 的 JSON
        - batch_extract_articles：content 为 NewsArticleSummary 列表的 JSON 数组
          （其中可能混杂含 ``error`` 字段的失败条目，会被跳过）
        """
        content = msg.content
        if isinstance(content, (bytes, bytearray)):
            content = content.decode("utf-8", errors="ignore")
        if not isinstance(content, str) or not content.strip():
            return []

        try:
            data = loads_with_repair(content, name=f"ToolMessage({msg.name})")
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"ToolMessage content 解析 JSON 失败 (name={msg.name}): {e}")
            return []

        # 归一化为 list[dict]
        items: list[dict[str, Any]] = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = [data]
        else:
            return []

        summaries: list[NewsArticleSummary] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            # 跳过抓取/摘要失败条目（含 error 字段）及无 url 条目
            if "error" in item or not item.get("url"):
                continue
            try:
                summaries.append(NewsArticleSummary(**item))
            except Exception as e:  # Pydantic 校验失败（字段缺失等）
                logger.warning(
                    f"NewsArticleSummary 构造失败 (url={item.get('url')}): {e}"
                )
        return summaries

    def _collect_summaries_from_messages(
        self, messages: list[Any]
    ) -> dict[str, NewsArticleSummary]:
        """遍历 Agent 执行后的消息，从抓取工具的 ToolMessage 中拼出 url -> 摘要映射。"""
        summary_map: dict[str, NewsArticleSummary] = {}
        for msg in messages:
            if not isinstance(msg, ToolMessage):
                continue
            if msg.name not in _SUMMARY_TOOL_NAMES:
                continue
            for summary in self._parse_summary_from_tool_message(msg):
                # 同一 url 以最后出现的摘要为准（重抓取覆盖旧结果）
                summary_map[str(summary.url)] = summary
        return summary_map

    async def collect(self, requirement: str) -> InformationCollectionResult:
        """执行信息采集，返回拼装后的 ``InformationCollectionResult``。

        主 Agent 只产出轻量引用列表（省 token），完整 ``NewsArticleSummary`` 摘要
        由后处理从 ToolMessage 中按主 Agent 给的 url 顺序拼装。
        """
        logger.info(f"信息采集开始: {requirement}")

        with usage_context(agent_name="info_collector_main"):
            result_state = await self.agent.ainvoke(
                {"messages": [HumanMessage(content=requirement)]}
            )
        messages = result_state.get("messages", [])
        structured_response = result_state.get("structured_response")

        # 解析 ToolMessage 摘要（即便主 Agent 结构化输出失败，也可尽力返回已抓到的摘要）
        summary_map = self._collect_summaries_from_messages(messages)

        # 主 Agent 结构化输出为空：尽力而为返回按抓取顺序的摘要
        if structured_response is None:
            logger.warning(
                "信息采集主 Agent 未产出 structured_response（CollectResult），"
                "将按 ToolMessage 摘要顺序兜底返回"
            )
            relevant_articles = list(summary_map.values())[
                : settings.info_collector_relevant_news_count
            ]
            return InformationCollectionResult(
                requirement=requirement,
                search_queries_used=[],
                relevant_articles=relevant_articles,
            )

        # structured_response 优先按已是对象处理，兼容序列化为 dict 的情况
        if isinstance(structured_response, CollectResult):
            collect_result = structured_response
        elif isinstance(structured_response, dict):
            try:
                collect_result = CollectResult(**structured_response)
            except Exception as e:
                logger.warning(f"CollectResult 构造失败: {e}")
                collect_result = CollectResult(
                    requirement=requirement, search_queries_used=[], relevant_article_refs=[]
                )
        else:
            collect_result = CollectResult(
                requirement=requirement, search_queries_used=[], relevant_article_refs=[]
            )

        # 按主 Agent 给的 url 引用列表顺序，从 summary_map 拼装完整摘要
        relevant_articles: list[NewsArticleSummary] = []
        for ref in collect_result.relevant_article_refs:
            summary = summary_map.get(str(ref.url))
            if summary is None:
                # 主 Agent 引用了但子 Agent 抓取/摘要失败 —— 跳过缺失条目（best-effort）
                logger.warning(
                    f"主 Agent 引用的 url 在 ToolMessage 摘要中未找到，跳过: {ref.url}"
                )
                continue
            relevant_articles.append(summary)

        # 裁剪到配置的相关新闻数上限
        relevant_articles = relevant_articles[
            : settings.info_collector_relevant_news_count
        ]

        logger.info(
            f"信息采集完成: 引用 {len(collect_result.relevant_article_refs)} 条，"
            f"拼装成功 {len(relevant_articles)} 条摘要"
        )

        return InformationCollectionResult(
            requirement=collect_result.requirement or requirement,
            search_queries_used=collect_result.search_queries_used,
            relevant_articles=relevant_articles,
        )



if __name__ == '__main__':
    import asyncio

    async def test():
        print("="*20, "开始测试...", "="*20)

        agent = InformationCollectorAgent()
        query = "kimi k3模型怎么样？"
        result = await agent.collect(query)

        print(type(result))

        print(result)

    asyncio.run(test())
    