"""
智能体基类，提供所有文本型 Agent 共享的能力
"""
from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
import json
from typing import TYPE_CHECKING, Any, Callable, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from app.constants.prompt import PromptConstant
from app.services.model_usage_service import usage_context
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
        structured_model: Optional[Any] = None,
    ):
        """初始化基础智能体

        Args:
            model: 已配置好的 LangChain BaseChatModel 实例（由 llm_factory 创建）
            agent_log_service: 日志服务
            structured_model: 可选的结构化输出模型（Runnable，如 llm_factory 的
                DeepSeekStructuredModel / with_structured_output 结果），
                供 _call_structured_model 使用；未配置时调用会抛错
        """
        self.model = model
        self.agent_log_service = agent_log_service
        self.structured_model = structured_model

    # ==================== LLM 调用 ====================

    async def _call_llm(self, prompt: str, agent_name: Optional[str] = None) -> str:
        """调用 LLM（非流式）

        Args:
            prompt: 用户提示词。
            agent_name: 统计点名称（用于模型用量埋点），由调用方传入。
        """
        logger.debug(f"即将调用 LLM，prompt: {prompt}")
        try:
            with usage_context(agent_name=agent_name):
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

    async def _call_structured_model(
        self,
        prompt: str,
        agent_name: Optional[str] = None,
        structured_model: Optional[Any] = None,
    ) -> Any:
        """调用结构化输出模型（非流式），返回 Pydantic 实例

        与 _call_llm 的区别：底层模型是 llm_factory 创建的结构化输出模型
        （如 DeepSeekStructuredModel / with_structured_output 结果），
        返回的是校验过的 Pydantic 对象，无需再手工 JSON 解析。

        Args:
            prompt: 用户提示词。
            agent_name: 统计点名称（用于模型用量埋点），由调用方传入。
            structured_model: 可选的结构化模型覆盖（默认用 self.structured_model），
                供图节点复用其他 schema 的结构化模型（如 AI 修改大纲用 OutlineResult）。

        Returns:
            结构化模型返回的 Pydantic 实例
        """
        model = structured_model or self.structured_model
        if model is None:
            raise RuntimeError("未配置结构化输出模型，无法调用 _call_structured_model")
        logger.debug(f"即将调用结构化 LLM，prompt: {prompt}")
        try:
            with usage_context(agent_name=agent_name):
                result = await model.ainvoke(prompt)
            return result
        except Exception as e:
            logger.error(
                "结构化 LLM 调用失败 model=%s, error=%s",
                model,
                str(e),
                exc_info=True,
            )
            raise

    async def _call_llm_with_streaming(
        self,
        prompt: str,
        stream_handler: Callable[[str], None],
        message_type: SseMessageTypeEnum,
        agent_name: Optional[str] = None,
    ) -> str:
        """调用 LLM（流式输出）

        Args:
            prompt: 用户提示词。
            stream_handler: SSE 流式回调。
            message_type: SSE 消息类型。
            agent_name: 统计点名称（用于模型用量埋点），由调用方传入。
        """
        logger.debug(f"即将调用 LLM，prompt: {prompt}")
        content_builder = []

        try:
            with usage_context(agent_name=agent_name):
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
