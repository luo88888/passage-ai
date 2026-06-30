from __future__ import annotations

from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from app.agent.agents.content_generator import ContentGeneratorAgent
from app.agent.agents.content_merger import ContentMergerAgent
from app.agent.agents.image_analyzer import ImageAnalyzerAgent
from app.agent.agents.image_generator_agent import ImageGeneratorAgent
from app.agent.agents.outline_generator import OutlineGeneratorAgent
from app.agent.agents.title_generator import TitleGeneratorAgent
from app.agent.context.stream_handler import StreamHandlerContext
from app.models.enums import SseMessageTypeEnum
from app.schemas.article import ArticleState
from app.utils.logger import logger

if TYPE_CHECKING:
    from app.agent.image_generator import ParallelImageGenerator
    from app.services.agent_log_service import AgentLogService


class ArticleAgentOrchestrator:
    """多智能体编排器——创建和管理所有 Agent，编排三阶段执行流程"""

    def __init__(
        self,
        client: AsyncOpenAI,
        model: str,
        agent_log_service: AgentLogService,
        parallel_image_generator: ParallelImageGenerator,
    ):
        self.title_agent = TitleGeneratorAgent(client, model, agent_log_service)
        self.outline_agent = OutlineGeneratorAgent(client, model, agent_log_service)
        self.content_agent = ContentGeneratorAgent(client, model, agent_log_service)
        self.image_analyzer_agent = ImageAnalyzerAgent(
            client, model, agent_log_service, parallel_image_generator
        )
        self.image_generator_agent = ImageGeneratorAgent(
            parallel_image_generator, agent_log_service
        )
        self.content_merger_agent = ContentMergerAgent(agent_log_service)

    async def execute_phase1(
        self,
        state: ArticleState,
        stream_handler,
    ):
        """阶段1：生成标题方案"""
        stream_context = StreamHandlerContext(stream_handler)
        logger.info("阶段1：开始生成标题方案, taskId=%s", state.task_id)
        await self.title_agent.run(state)
        stream_context.emit(SseMessageTypeEnum.AGENT1_COMPLETE.value)
        logger.info(
            "阶段1：标题方案生成成功, taskId=%s, optionsCount=%s",
            state.task_id,
            len(state.title_options or []),
        )

    async def execute_phase2(
        self,
        state: ArticleState,
        stream_handler,
    ):
        """阶段2：流式生成大纲"""
        stream_context = StreamHandlerContext(stream_handler)
        logger.info("阶段2：开始生成大纲, taskId=%s", state.task_id)
        await self.outline_agent.run(state, stream_context.emit)
        stream_context.emit(SseMessageTypeEnum.AGENT2_COMPLETE.value)
        logger.info("阶段2：大纲生成成功, taskId=%s", state.task_id)

    async def execute_phase3(
        self,
        state: ArticleState,
        stream_handler,
    ):
        """阶段3：生成正文 → 分析配图需求 → 生成配图 → 图文合并"""
        stream_context = StreamHandlerContext(stream_handler)

        logger.info("阶段3：开始生成正文, taskId=%s", state.task_id)
        await self.content_agent.run(state, stream_context.emit)
        stream_context.emit(SseMessageTypeEnum.AGENT3_COMPLETE.value)

        logger.info("阶段3：开始分析配图需求, taskId=%s", state.task_id)
        await self.image_analyzer_agent.run(state)
        stream_context.emit(SseMessageTypeEnum.AGENT4_COMPLETE.value)

        logger.info("阶段3：开始生成配图, taskId=%s", state.task_id)
        await self.image_generator_agent.run(state, stream_context.emit)
        stream_context.emit(SseMessageTypeEnum.AGENT5_COMPLETE.value)

        logger.info("阶段3：开始图文合成, taskId=%s", state.task_id)
        self.content_merger_agent.run(state)
        stream_context.emit(SseMessageTypeEnum.MERGE_COMPLETE.value)
