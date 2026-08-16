"""
信息采集 Agent 的 Pydantic 结构化数据模型

定义三类结构：
1. ``NewsArticleSummary`` —— 子 Agent（摘要）结构化输出；同时作为最终对外结果中
   ``relevant_articles`` 的元素类型。
2. ``RelevantArticleRef`` / ``CollectResult`` —— 主 Agent 的轻量结构化输出。
   主 Agent 只输出 url + title 的引用列表，**不重复摘要正文**（摘要正文由子 Agent
   通过 ToolMessage 产出，由 ``InformationCollectorAgent.collect`` 后处理拼装），
   以避免昂贵的主模型照搬长摘要产生巨大输出 token 开销。
3. ``InformationCollectionResult`` —— 最终对外结果，由后处理拼装产出而非模型直接输出。
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SerperNewsItem(BaseModel):
    """Serper API 返回的单条新闻（搜索工具内部结构，仅用于文档化/调试）"""

    title: str = Field(default="", description="新闻标题")
    link: str = Field(default="", description="新闻链接")
    snippet: str = Field(default="", description="新闻摘要片段")
    date: Optional[str] = Field(default=None, description="发布日期")
    source: Optional[str] = Field(default=None, description="来源")


class NewsArticleSummary(BaseModel):
    """单篇新闻/文章的摘要信息

    由轻量级子 Agent 对抓取的全文内容进行摘要后返回；同时也是最终对外结果
    ``InformationCollectionResult.relevant_articles`` 的元素类型。
    """

    title: str = Field(description="文章标题")
    url: str = Field(description="文章原始链接")
    summary: str = Field(
        description="基于全文内容的摘要（500字以内），保留关键信息、数据和分析观点，删除广告、导航栏等无关内容"
    )
    publish_time: Optional[str] = Field(
        default=None, description="文章发布时间（如能找到），格式如 2024-6-26"
    )
    tags: list[str] = Field(
        default_factory=list, description="文章标签/关键词（2-5个）"
    )
    author: Optional[str] = Field(default=None, description="作者姓名或机构名称（如能找到）")
    source: Optional[str] = Field(
        default=None, description="来源媒体名称（如能找到）"
    )


class RelevantArticleRef(BaseModel):
    """"相关文章引用"——仅 url + title 的轻量引用

    基于子 Agent 工具产出的摘要判断相关性后，给出最终要纳入结果的文章引用。
    **此处不包含摘要正文**：摘要正文由系统后处理自动拼装，无需重复输出。
    """

    url: str = Field(description="文章原始链接（需与某次抓取工具调用的 url 完全一致）")
    title: str = Field(description="文章标题")


class CollectResult(BaseModel):
    """相关文章引用结果"""

    requirement: str = Field(description="原始信息需求描述")
    search_queries_used: list[str] = Field(
        default_factory=list, description="实际使用的搜索查询词列表"
    )
    relevant_article_refs: list[RelevantArticleRef] = Field(
        default_factory=list,
        description="筛选后的相关文章引用列表（仅 url+title，不含摘要正文）",
    )


class InformationCollectionResult(BaseModel):
    requirement: str = Field(description="原始信息需求描述")
    search_queries_used: list[str] = Field(
        default_factory=list, description="实际使用的搜索查询词列表"
    )
    relevant_articles: list[NewsArticleSummary] = Field(
        default_factory=list, description="最终的相关文章摘要列表"
    )