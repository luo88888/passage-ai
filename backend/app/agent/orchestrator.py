from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_core.language_models import BaseChatModel

from app.agent.agents.ai_modify_outline import AiModifyOutlineAgent
from app.agent.agents.content_generator import ContentGeneratorAgent
from app.agent.agents.content_merger import ContentMergerAgent
from app.agent.agents.image_analyzer import ImageAnalyzerAgent
from app.agent.agents.image_generator_agent import ImageGeneratorAgent
from app.agent.agents.outline_generator import OutlineGeneratorAgent
from app.agent.agents.title_generator import TitleGeneratorAgent

if TYPE_CHECKING:
    from app.services.images.image_generator import ParallelImageGenerator
    from app.services.agent_log_service import AgentLogService


class ArticleAgentOrchestrator:
    """多智能体编排器——创建和管理所有 Agent

    各阶段执行流程现由 app/graph/ 下的 LangGraph 状态图节点驱动，
    节点直接调用本类持有的各 agent（如 title_agent / outline_agent ...）的 run()。
    本类负责实例化与持有 7 个 agent，以及各 agent 需要的结构化输出模型
    （标题 / 配图分析 / AI 修改大纲使用，由 llm_factory.get_structured_model 创建）。
    """

    def __init__(
        self,
        title_model: BaseChatModel,
        title_structured_model: Any,
        outline_model: BaseChatModel,
        content_model: BaseChatModel,
        image_analyzer_model: BaseChatModel,
        image_analyzer_structured_model: Any,
        ai_modify_outline_model: BaseChatModel,
        ai_modify_outline_structured_model: Any,
        agent_log_service: AgentLogService,
        parallel_image_generator: ParallelImageGenerator,
    ):
        self.title_agent = TitleGeneratorAgent(
            model=title_model,
            agent_log_service=agent_log_service,
            structured_model=title_structured_model,
        )
        self.outline_agent = OutlineGeneratorAgent(outline_model, agent_log_service)
        self.content_agent = ContentGeneratorAgent(
            content_model, agent_log_service, parallel_image_generator
        )
        self.image_analyzer_agent = ImageAnalyzerAgent(
            model=image_analyzer_model,
            agent_log_service=agent_log_service,
            parallel_image_generator=parallel_image_generator,
            structured_model=image_analyzer_structured_model,
        )
        self.image_generator_agent = ImageGeneratorAgent(
            parallel_image_generator, agent_log_service
        )
        self.content_merger_agent = ContentMergerAgent(agent_log_service)
        # AI 修改大纲智能体（独立 Agent，结构化输出 OutlineResult schema）
        self.ai_modify_outline_agent = AiModifyOutlineAgent(
            model=ai_modify_outline_model,
            agent_log_service=agent_log_service,
            structured_model=ai_modify_outline_structured_model,
        )