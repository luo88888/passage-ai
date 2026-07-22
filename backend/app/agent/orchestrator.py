from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.language_models import BaseChatModel

from app.agent.agents.content_generator import ContentGeneratorAgent
from app.agent.agents.content_merger import ContentMergerAgent
from app.agent.agents.image_analyzer import ImageAnalyzerAgent
from app.agent.agents.image_generator_agent import ImageGeneratorAgent
from app.agent.agents.outline_generator import OutlineGeneratorAgent
from app.agent.agents.title_generator import TitleGeneratorAgent

if TYPE_CHECKING:
    from app.agent.image_generator import ParallelImageGenerator
    from app.services.agent_log_service import AgentLogService


class ArticleAgentOrchestrator:
    """多智能体编排器——创建和管理所有 Agent

    各阶段执行流程现由 app/graph/ 下的 LangGraph 状态图节点驱动，
    节点直接调用本类持有的各 agent（如 title_agent / outline_agent ...）的 run()。
    本类仅负责实例化与持有 6 个 agent，不再持有阶段编排方法。
    """

    def __init__(
        self,
        title_model: BaseChatModel,
        outline_model: BaseChatModel,
        content_model: BaseChatModel,
        image_analyzer_model: BaseChatModel,
        agent_log_service: AgentLogService,
        parallel_image_generator: ParallelImageGenerator,
    ):
        self.title_agent = TitleGeneratorAgent(title_model, agent_log_service)
        self.outline_agent = OutlineGeneratorAgent(outline_model, agent_log_service)
        self.content_agent = ContentGeneratorAgent(
            content_model, agent_log_service, parallel_image_generator
        )
        self.image_analyzer_agent = ImageAnalyzerAgent(
            image_analyzer_model, agent_log_service, parallel_image_generator
        )
        self.image_generator_agent = ImageGeneratorAgent(
            parallel_image_generator, agent_log_service
        )
        self.content_merger_agent = ContentMergerAgent(agent_log_service)