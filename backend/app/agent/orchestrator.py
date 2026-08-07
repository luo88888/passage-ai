from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
    本类负责实例化与持有 6 个 agent，以及各 agent 需要的结构化输出模型
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
        outline_structured_model: Any,
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
        # 结构化输出模型（供图节点复用：AI 修改大纲节点用 OutlineResult schema）
        self.outline_structured_model = outline_structured_model