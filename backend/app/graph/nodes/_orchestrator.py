"""图节点共享的智能体编排器单例

图节点共享一个编排器单例。

get_orchestrator() 首次调用时惰性构造（import 也放在函数体内，避免与 services 层形成循环导入）：
  - 复用 app.agent.image_generator.parallel_image_generator（图片服务单例）
  - 通过 llm_factory 为各 Agent 创建独立的 BaseChatModel 与结构化输出模型
    （标题 / 配图分析 / AI 修改大纲 3 处使用结构化输出，支持按 Agent 独立配置）
  - 构造 ArticleAgentOrchestrator 持有 7 个 agent 与结构化输出模型
"""
from __future__ import annotations

from app.agent.orchestrator import ArticleAgentOrchestrator
from app.config import settings

# database / parallel_image_generator 延迟到 get_orchestrator() 内 import，
# 避免模块导入时触发 app.services.__init__ → article_async_service → graph 的循环。

_orchestrator: ArticleAgentOrchestrator | None = None


def get_orchestrator() -> ArticleAgentOrchestrator:
    """惰性获取共享编排器单例（持有 6 个 agent 实例）

    运行期才构造；AgentLogService / parallel_image_generator / database 的 import 延迟到此处，
    避免模块导入时触发 app.services.__init__ → article_async_service → graph 的循环。
    """
    global _orchestrator
    if _orchestrator is None:
        from app.services.agent_log_service import AgentLogService
        from app.database import database
        from app.agent.image_generator import parallel_image_generator
        from app.llm_factory.factory import (
            get_chat_model,
            get_structured_model,
            resolve_agent_config,
        )
        from app.schemas.article import Agent4Result, OutlineResult, TitleOptionResult

        agent_log_service = AgentLogService(database)

        # 解析各 Agent 专属配置（空值回退到全局默认）
        title_cfg = resolve_agent_config(
            agent_provider=settings.title_agent_provider,
            agent_model=settings.title_agent_model,
            agent_temperature=settings.title_agent_temperature,
            agent_thinking=settings.title_agent_thinking,
            agent_reasoning_effort=settings.title_agent_reasoning_effort,
        )
        outline_cfg = resolve_agent_config(
            agent_provider=settings.outline_agent_provider,
            agent_model=settings.outline_agent_model,
            agent_temperature=settings.outline_agent_temperature,
            agent_thinking=settings.outline_agent_thinking,
            agent_reasoning_effort=settings.outline_agent_reasoning_effort,
        )
        ai_modify_outline_cfg = resolve_agent_config(
            agent_provider=settings.ai_modify_outline_agent_provider,
            agent_model=settings.ai_modify_outline_agent_model,
            agent_temperature=settings.ai_modify_outline_agent_temperature,
            agent_thinking=settings.ai_modify_outline_agent_thinking,
            agent_reasoning_effort=settings.ai_modify_outline_agent_reasoning_effort,
        )
        content_cfg = resolve_agent_config(
            agent_provider=settings.content_agent_provider,
            agent_model=settings.content_agent_model,
            agent_temperature=settings.content_agent_temperature,
            agent_thinking=settings.content_agent_thinking,
            agent_reasoning_effort=settings.content_agent_reasoning_effort,
        )
        image_analyzer_cfg = resolve_agent_config(
            agent_provider=settings.image_analyzer_agent_provider,
            agent_model=settings.image_analyzer_agent_model,
            agent_temperature=settings.image_analyzer_agent_temperature,
            agent_thinking=settings.image_analyzer_agent_thinking,
            agent_reasoning_effort=settings.image_analyzer_agent_reasoning_effort,
        )

        # 通过 llm_factory 为各 Agent 创建独立的 BaseChatModel
        title_model = get_chat_model(**title_cfg)
        outline_model = get_chat_model(**outline_cfg)
        ai_modify_outline_model = get_chat_model(**ai_modify_outline_cfg)
        content_model = get_chat_model(**content_cfg)
        image_analyzer_model = get_chat_model(**image_analyzer_cfg)

        # 结构化输出模型：标题 / 配图分析 / AI 修改大纲 3 处直接产出 Pydantic 对象
        # （复用各 Agent 的解析配置；DeepSeek thinking 模式自动走 prompt_json，兼容思考模式）
        title_structured_model = get_structured_model(TitleOptionResult, **title_cfg)
        image_analyzer_structured_model = get_structured_model(
            Agent4Result, **image_analyzer_cfg
        )
        ai_modify_outline_structured_model = get_structured_model(
            OutlineResult, **ai_modify_outline_cfg
        )

        _orchestrator = ArticleAgentOrchestrator(
            title_model=title_model,
            title_structured_model=title_structured_model,
            outline_model=outline_model,
            content_model=content_model,
            image_analyzer_model=image_analyzer_model,
            image_analyzer_structured_model=image_analyzer_structured_model,
            ai_modify_outline_model=ai_modify_outline_model,
            ai_modify_outline_structured_model=ai_modify_outline_structured_model,
            agent_log_service=agent_log_service,
            parallel_image_generator=parallel_image_generator,
        )
    return _orchestrator