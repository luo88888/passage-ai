"""
智能体基类，提供所有文本型 Agent 共享的能力
"""
from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
import json
from typing import TYPE_CHECKING, Callable, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from app.constants.prompt import PromptConstant
from app.models.enums import (
    ArticleGenreEnum,
    ArticleLanguageStyleEnum,
    ArticleStyleEnum,
    SseMessageTypeEnum,
)
from app.utils.logger import logger

if TYPE_CHECKING:
    from app.services.agent_log_service import AgentLogService


# ==================== 模块级工具函数 ====================

def _safe_json_dumps(value: Optional[dict]) -> Optional[str]:
    """安全序列化 JSON"""
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return None


@asynccontextmanager
async def agent_log_context(
    agent_log_service: AgentLogService,
    task_id: Optional[str],
    agent_name: str,
    prompt: Optional[str] = None,
    input_data: Optional[dict] = None,
):
    """异步智能体日志上下文（模块级函数，可供任意类使用）"""
    start_time = datetime.now()
    log_data = {
        "taskId": task_id or "unknown",
        "agentName": agent_name,
        "startTime": start_time,
        "status": "RUNNING",
        "prompt": prompt,
        "inputData": _safe_json_dumps(input_data),
        "outputData": None,
        "errorMessage": None,
    }
    try:
        yield log_data
        log_data["status"] = "SUCCESS"
    except Exception as exc:
        log_data["status"] = "FAILED"
        log_data["errorMessage"] = str(exc)
        raise
    finally:
        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        log_data["endTime"] = end_time
        log_data["durationMs"] = duration_ms
        agent_log_service.save_log_async(log_data)


@contextmanager
def agent_log_context_sync(
    agent_log_service: AgentLogService,
    task_id: Optional[str],
    agent_name: str,
    prompt: Optional[str] = None,
    input_data: Optional[dict] = None,
):
    """同步智能体日志上下文（模块级函数，可供任意类使用）"""
    start_time = datetime.now()
    log_data = {
        "taskId": task_id or "unknown",
        "agentName": agent_name,
        "startTime": start_time,
        "status": "RUNNING",
        "prompt": prompt,
        "inputData": _safe_json_dumps(input_data),
        "outputData": None,
        "errorMessage": None,
    }
    try:
        yield log_data
        log_data["status"] = "SUCCESS"
    except Exception as exc:
        log_data["status"] = "FAILED"
        log_data["errorMessage"] = str(exc)
        raise
    finally:
        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        log_data["endTime"] = end_time
        log_data["durationMs"] = duration_ms
        agent_log_service.save_log_async(log_data)


class BaseAgent:
    """基础智能体类，提供 LLM 调用、JSON 解析、日志记录等共享能力"""

    def __init__(
        self,
        model: BaseChatModel,
        agent_log_service: AgentLogService,
    ):
        """初始化基础智能体

        Args:
            model: 已配置好的 LangChain BaseChatModel 实例（由 llm_factory 创建）
            agent_log_service: 日志服务
        """
        self.model = model
        self.agent_log_service = agent_log_service

    # ==================== LLM 调用 ====================

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM（非流式）"""
        logger.debug(f"即将调用 LLM，prompt: {prompt}")
        try:
            response = await self.model.ainvoke([HumanMessage(content=prompt)])
            return response.content  # type: ignore
        except Exception as e:
            logger.error(
                "LLM 调用失败(非流式) model=%s, error=%s",
                self.model,
                str(e),
                exc_info=True,
            )
            raise

    async def _call_llm_with_streaming(
        self,
        prompt: str,
        stream_handler: Callable[[str], None],
        message_type: SseMessageTypeEnum,
    ) -> str:
        """调用 LLM（流式输出）"""
        logger.debug(f"即将调用 LLM，prompt: {prompt}")
        content_builder = []

        try:
            async for chunk in self.model.astream([HumanMessage(content=prompt)]):
                if chunk.content:
                    content = chunk.content
                    content_builder.append(content)
                    stream_handler(message_type.get_streaming_prefix() + content)
        except Exception as e:
            logger.error(
                "LLM 调用失败(流式) model=%s, error=%s",
                self.model,
                str(e),
                exc_info=True,
            )
            raise

        return "".join(content_builder)

    # ==================== JSON 解析 ====================

    @staticmethod
    def _parse_json_response(content: str, name: str) -> dict:
        """解析 JSON 响应"""
        try:
            content2 = content.strip()
            if content2.startswith("```json") or content2.startswith("```JSON"):
                content2 = content2[7:-3].strip()
            return json.loads(content2)
        except json.JSONDecodeError as e:
            logger.error(
                "%s解析失败, content=%s, error=%s", name, content, str(e)
            )
            raise RuntimeError(f"{name}解析失败")

    @staticmethod
    def _parse_json_list_response(content: str, name: str) -> list:
        """解析 JSON 数组响应"""
        try:
            content2 = content.strip()
            if content2.startswith("```json") or content2.startswith("```JSON"):
                content2 = content2[7:-3].strip()
            result = json.loads(content2)
            if not isinstance(result, list):
                raise ValueError("响应不是 JSON 数组")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"{name}解析失败, content={content2}, error={e}")
            raise RuntimeError(f"{name}解析失败")
        except ValueError as e:
            logger.error(f"{name}解析失败, content={content}, error={e}")
            raise RuntimeError(f"{name}解析失败")

    # ==================== 链路与风格 Prompt ====================

    @staticmethod
    def _get_style_prompt(style: Optional[str]) -> str:
        """根据（已弃用的）文章风格获取对应的 Prompt 附加内容

        @deprecated 保留以兼容旧文章路径；新流程请用 _get_genre_prompt / _get_language_style_prompt。
        """
        if not style:
            return ""
        try:
            style_enum = ArticleStyleEnum(style)
            style_map = {
                ArticleStyleEnum.TECH: PromptConstant.STYLE_TECH_PROMPT,
                ArticleStyleEnum.EMOTIONAL: PromptConstant.STYLE_EMOTIONAL_PROMPT,
                ArticleStyleEnum.EDUCATIONAL: PromptConstant.STYLE_EDUCATIONAL_PROMPT,
                ArticleStyleEnum.HUMOROUS: PromptConstant.STYLE_HUMOROUS_PROMPT,
            }
            return style_map.get(style_enum, "")
        except ValueError:
            return ""

    @staticmethod
    def _get_genre_prompt(genre: Optional[str]) -> str:
        """根据题材获取对应的 Prompt 附加内容（决定全文基调与结构）"""
        if not genre:
            return ""
        try:
            genre_enum = ArticleGenreEnum(genre)
            genre_map = {
                ArticleGenreEnum.NEWS: PromptConstant.GENRE_NEWS_PROMPT,
                ArticleGenreEnum.KNOWLEDGE: PromptConstant.GENRE_KNOWLEDGE_PROMPT,
                ArticleGenreEnum.PRODUCT: PromptConstant.GENRE_PRODUCT_PROMPT,
                ArticleGenreEnum.TUTORIAL: PromptConstant.GENRE_TUTORIAL_PROMPT,
                ArticleGenreEnum.OPINION: PromptConstant.GENRE_OPINION_PROMPT,
                ArticleGenreEnum.STORY: PromptConstant.GENRE_STORY_PROMPT,
            }
            text = genre_map.get(genre_enum, "")
            if text:
                return f"========== 文章题材要求 ==========\n{text}\n\n"
            return ""
        except ValueError:
            return ""

    @staticmethod
    def _get_language_style_prompt(language_style: Optional[str]) -> str:
        """根据语言风格获取对应的 Prompt 附加内容（决定语气特质，取代旧文章风格）"""
        if not language_style:
            return ""
        try:
            style_enum = ArticleLanguageStyleEnum(language_style)
            style_map = {
                ArticleLanguageStyleEnum.PROFESSIONAL: PromptConstant.LANGUAGE_STYLE_PROFESSIONAL,
                ArticleLanguageStyleEnum.ACCESSIBLE: PromptConstant.LANGUAGE_STYLE_ACCESSIBLE,
                ArticleLanguageStyleEnum.HUMOROUS: PromptConstant.LANGUAGE_STYLE_HUMOROUS,
                ArticleLanguageStyleEnum.LITERARY: PromptConstant.LANGUAGE_STYLE_LITERARY,
                ArticleLanguageStyleEnum.FORMAL: PromptConstant.LANGUAGE_STYLE_FORMAL,
            }
            text = style_map.get(style_enum, "")
            if text:
                return f"========== 语言风格要求 ==========\n{text}\n\n"
            return ""
        except ValueError:
            return ""

    @staticmethod
    def _get_news_context_prompt(collected_news: Optional[str]) -> str:
        """新闻题材信息采集产物的注入片段（非空时追加，供标题/大纲/正文 Agent 参考）"""
        if not collected_news or not collected_news.strip():
            return ""
        return (
            "========== 参考新闻资料 ==========\n"
            f"{collected_news.strip()}\n"
        )

    # ==================== 日志上下文管理器（委托给模块级函数） ====================

    def _agent_log_context(
        self,
        task_id: Optional[str],
        agent_name: str,
        prompt: Optional[str] = None,
        input_data: Optional[dict] = None,
    ):
        """异步智能体日志上下文"""
        return agent_log_context(
            self.agent_log_service,
            task_id=task_id,
            agent_name=agent_name,
            prompt=prompt,
            input_data=input_data,
        )

    def _agent_log_context_sync(
        self,
        task_id: Optional[str],
        agent_name: str,
        prompt: Optional[str] = None,
        input_data: Optional[dict] = None,
    ):
        """同步智能体日志上下文"""
        return agent_log_context_sync(
            self.agent_log_service,
            task_id=task_id,
            agent_name=agent_name,
            prompt=prompt,
            input_data=input_data,
        )

    # ==================== 工具方法 ====================

    @staticmethod
    def _safe_json_dumps(value: Optional[dict]) -> Optional[str]:
        """安全序列化 JSON（委托给模块级函数）"""
        return _safe_json_dumps(value)
