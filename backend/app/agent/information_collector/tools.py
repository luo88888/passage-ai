"""
信息采集 Agent 的 LangChain 工具定义

提供两个核心工具:
1. serper_search: 调用 Google Serper API 搜索新闻
2. extract_article_content: 抓取网页内容并用轻量模型摘要

工具函数使用 @tool 装饰器定义，供 LangChain create_agent 使用。
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Optional
import asyncio
import dotenv

import httpx
from langchain.tools import tool
from ddgs import DDGS

dotenv.load_dotenv(override=True)


from app.utils.logger import logger
from app.config import settings
from app.agent.information_collector.schemas import NewsArticleSummary
from app.llm_factory.factory import get_structured_model
from app.services.model_usage_service import usage_context


# ==================== serper_search 工具 ====================

@tool
async def serper_search(
    query: str,
    gl: str = "cn",
    hl: str = "zh-cn",
    tbs: str = "qdr:m",
    num: Optional[int] = None,
) -> str:
    """调用 Google Serper API 搜索新闻。

    使用前请仔细阅读以下说明：
    - 默认为中文页面，过去一个月内的最新新闻（可用 tbs 调整：qdr:h=1小时, qdr:d=1天, qdr:w=1周, qdr:m=1月，qdr:y=1年）
    - 如果一次查询没有找到足够的相关结果，可以尝试调整关键词和参数
    - 调用次数受系统配置限制（达到上限后会被中间件拦截），请合理规划搜索策略

    Args:
        query: 搜索关键词（建议使用关键术语，10 词以内，避免过长）
        gl: 搜索国家/地区代码，默认 cn，可选 us、jp、in 等
        hl: 搜索语言代码，默认 zh-cn，可选 en、ja、ru 等
        tbs: 时间范围过滤器，默认 qdr:m（一个月内）
        num: 返回结果数量，默认 10

    Returns:
        JSON 格式的搜索结果字符串，包含新闻列表
    """

    api_key = settings.serper_api_key or os.environ.get("SERPER_API_KEY", "")
    if not api_key:
        return json.dumps({
            "error": "未配置 SERPER_API_KEY，无法执行搜索",
            "news": []
        }, ensure_ascii=False)

    # 未显式传 num 时取系统配置
    if num is None:
        num = settings.info_collector_serper_num

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://google.serper.dev/news",
                json={
                    "q": query,
                    "gl": gl,
                    "hl": hl,
                    "tbs": tbs,
                    "num": num,
                },
                headers={
                    "X-API-KEY": api_key,
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            result = response.json()

        news_count = len(result.get("news", []))
        logger.info(f"Serper 搜索完成: 获取到 {news_count} 条新闻")

        # 返回精简的 JSON（保留关键字段；调用次数由 ToolCallLimitMiddleware 强制限制）
        simplified = {
            "search_query": query,
            "total_results": news_count,
            "news": [
                {
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "date": item.get("date", ""),
                    "source": item.get("source", ""),
                }
                for item in result.get("news", [])
            ],
        }
        return json.dumps(simplified, ensure_ascii=False)

    except httpx.HTTPError as e:
        logger.error(f"Serper API 请求失败: {e}")
        return json.dumps({
            "error": f"搜索请求失败: {str(e)}",
            "news": []
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Serper 搜索异常: {e}", exc_info=True)
        return json.dumps({
            "error": f"搜索过程发生异常: {str(e)}",
            "news": []
        }, ensure_ascii=False)


# ==================== extract_article_content 工具 ====================

@tool
async def extract_article_content(
    url: str,
    requirement: str,
) -> str:
    """抓取指定 URL 的文章全文内容，使用轻量模型进行摘要。

    该工具会：
    1. 使用 DDGS 引擎抓取网页全文内容（自动转为 Markdown 格式）
    2. 使用轻量级 LLM 对内容进行摘要
    3. 提取摘要、发布时间、标签、作者等结构化信息
    4. 返回结构化的摘要结果

    适用于对 serper_search 返回的相关新闻进行深度内容提取。
    每次调用只能处理一个 URL，处理多个 URL 请多次调用。

    Args:
        url: 需要抓取的网页 URL
        requirement: 信息需求描述，用于判断内容相关性和指导摘要方向

    Returns:
        JSON 格式的摘要结果，包含标题、摘要、发布时间、标签、作者等信息
    """

    logger.info(f"开始抓取文章内容: {url}")

    # Step 1: 在线程池中执行同步 DDGS 抓取
    try:
        page = await asyncio.to_thread(_extract_with_ddgs, url)
        if not page or not page.get("content"):
            return json.dumps({
                "error": f"无法抓取页面内容: {url}",
                "title": page.get("title", "") if page else "",
                "url": url,
            }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"DDGS 抓取失败 {url}: {e}")
        return json.dumps({
            "error": f"网页抓取失败: {str(e)}",
            "url": url,
        }, ensure_ascii=False)

    content = page.get("content", "")
    title = page.get("title", "")
    logger.info(f"DDGS 抓取完成: {url}, 内容长度 {len(content)} 字符")

    # Step 2: 截断过长内容（防止超出模型上下文），截断长度由配置决定
    max_content_chars = settings.info_collector_max_content_chars
    if len(content) > max_content_chars:
        content = content[:max_content_chars] + "\n\n[内容已截断...]"

    # Step 3: 使用轻量级模型进行结构化摘要（provider/model 走配置）
    try:
        summary_model = get_structured_model(
            NewsArticleSummary,
            provider=settings.info_collector_sub_provider,
            model_name=settings.info_collector_sub_model,
            temperature=settings.info_collector_sub_temperature,
            thinking=False,
        )

        # TODO: P2 优化提示词，摘要尽可能保留具体数据、数值等关键内容
        prompt = (
            f"请根据以下网页内容，提取结构化信息。\n\n"
            f"信息需求：{requirement}\n\n"
            f"网页标题：{title}\n"
            f"网页URL：{url}\n\n"
            f"请提取：\n"
            f"1. 标题（保留原标题）\n"
            f"2. URL（保留原URL）\n"
            f"3. 摘要（500字以内，保留与需求相关的关键信息、数据和分析观点，忽略广告、导航栏等无关内容）\n"
            f"4. 发布时间（如果能从内容中找到，格式如 2024-07-26）\n"
            f"5. 标签（2-5个关键词）\n"
            f"6. 作者（如果能找到）\n"
            f"7. 来源（媒体名称）\n\n"
            f"========== 网页内容（Markdown格式）==========：\n{content}"
        )

        with usage_context(agent_name="info_collector_sub"):
            result: NewsArticleSummary = await summary_model.ainvoke(prompt)
        result.url = url    # 直接使用原始 url
        logger.info(f"摘要完成: {url}, 标签: {result.tags}, 原始长度：{len(content)}, 结构化结果长度：{len(str(result.model_json_schema()))}")

        return json.dumps(result.model_dump(), ensure_ascii=False)

    except Exception as e:
        logger.error(f"摘要失败 {url}: {e}", exc_info=True)
        return json.dumps({
            "error": f"摘要生成失败: {str(e)}",
            "url": url,
            "title": title,
        }, ensure_ascii=False)


def _extract_with_ddgs(url: str) -> Optional[dict]:
    """同步 DDGS 抓取函数（供 asyncio.to_thread 调用）

    DDGS().extract() 返回格式:
    {
        "title": "...",
        "content": "Markdown 格式的正文内容",
        ...
    }
    """
    from ddgs import DDGS

    try:
        ddgs = DDGS()
        result = ddgs.extract(url)
        return result
    except Exception as e:
        logger.error(f"DDGS extract 异常 {url}: {e}")
        return None


# ==================== batch_extract_articles 工具（并行子 Agent） ====================

@tool
async def batch_extract_articles(
    urls: list[str],
    requirement: str,
    max_concurrency: Optional[int] = None,
) -> str:
    """批量并行抓取并摘要多个 URL 的文章内容。

    该工具内部并行处理多个 URL，每个 URL 的处理流程：
    1. 抓取网页全文
    2. 轻量级 LLM 结构化摘要
    3. 提取标题、摘要、发布时间、标签、作者等信息

    与 extract_article_content 不同，此工具可以一次性处理多个 URL，
    通过并行处理大幅提升处理速度。建议在确定需要提取哪些 URL 后使用。

    Args:
        urls: 需要抓取的网页 URL 列表（建议 2-8 个）
        requirement: 原始的信息需求描述
        max_concurrency: 最大并行数，默认取系统配置 ``info_collector_max_concurrency``

    Returns:
        JSON 格式的摘要结果数组
    """

    if max_concurrency is None:
        max_concurrency = settings.info_collector_max_concurrency

    if max_concurrency < 1 or max_concurrency > settings.info_collector_max_concurrency:
        msg = f"参数异常，max_concurrency={max_concurrency}, 允许取值范围: [1, {settings.info_collector_max_concurrency}]"
        logger.warning(msg)
        return str({
            "error": msg
        })

    logger.info(f"开始批量并行抓取 {len(urls)} 个 URL, 最大并行数: {max_concurrency}")

    semaphore = asyncio.Semaphore(max_concurrency)

    async def _process_one(url: str) -> dict:
        """处理单个 URL（带并发控制）"""
        async with semaphore:
            # 调用单 URL 工具的核心逻辑
            result_json = await extract_article_content.ainvoke({
                "url": url,
                "requirement": requirement,
            })
            try:
                return json.loads(result_json)
            except json.JSONDecodeError:
                return {"error": "解析结果失败", "url": url, "raw": result_json}

    tasks = [_process_one(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 处理异常
    output = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            output.append({"error": str(result), "url": urls[i]})
        else:
            output.append(result)

    success_count = sum(1 for r in output if "error" not in r)
    logger.info(f"批量抓取完成: {success_count}/{len(urls)} 个 URL 成功")

    return json.dumps(output, ensure_ascii=False)
