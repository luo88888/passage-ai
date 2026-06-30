"""
配图需求分析智能体
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from app.agent.base_agent import BaseAgent
from app.constants.prompt import PromptConstant
from app.schemas.article import Agent4Result, ArticleState, ImageRequirement
from app.utils.logger import logger

if TYPE_CHECKING:
    from openai import AsyncOpenAI

    from app.agent.image_generator import ParallelImageGenerator
    from app.services.agent_log_service import AgentLogService


class ImageAnalyzerAgent(BaseAgent):
    """配图需求分析智能体"""

    def __init__(
        self,
        client: AsyncOpenAI,
        model: str,
        agent_log_service: AgentLogService,
        parallel_image_generator: ParallelImageGenerator,
    ):
        super().__init__(client, model, agent_log_service)
        # 配图方式说明由 ParallelImageGenerator 从已注册服务的 name/description/usage
        # 元数据动态构建（Markdown 表格），本智能体不再硬编码方式列表。
        self.parallel_image_generator = parallel_image_generator

    @staticmethod
    def _validate_and_filter_image_requirements(
        requirements: List[ImageRequirement],
        enabled_methods: Optional[List[str]],
    ) -> List[ImageRequirement]:
        """验证并过滤配图需求（不在允许列表中的降级替换）"""
        if not enabled_methods:
            return requirements

        validated_requirements = []

        for req in requirements:
            image_source = req.image_source

            if image_source in enabled_methods:
                validated_requirements.append(req)
                logger.debug(
                    "配图需求验证通过, position=%s, imageSource=%s",
                    req.position,
                    image_source,
                )
            else:
                fallback_source = enabled_methods[0]
                logger.warning(
                    "配图需求方式不在允许列表，降级替换, position=%s, "
                    "imageSource=%s, fallback=%s, enabledMethods=%s",
                    req.position,
                    image_source,
                    fallback_source,
                    enabled_methods,
                )
                req.image_source = fallback_source
                validated_requirements.append(req)

        return validated_requirements

    # ==================== 主流程 ====================

    async def run(self, state: ArticleState):
        """分析配图需求，在正文中插入占位符，填充 state 相关字段"""
        methods_guide = self.parallel_image_generator.build_image_methods_guide(
            enabled_image_methods=state.enabled_image_methods,
        )
        prompt = PromptConstant.AGENT4_IMAGE_REQUIREMENTS_PROMPT.format(
            mainTitle=state.title.main_title,  # type: ignore
            content=state.content or "",
            imageMethodsGuide=methods_guide,
        )
        prompt += self._get_style_prompt(state.style)

        async with self._agent_log_context(
            task_id=state.task_id,
            agent_name="agent4_analyze_image_requirements",
            prompt=prompt,
            input_data={"enabledImageMethods": state.enabled_image_methods},
        ) as log_data:
            content = await self._call_llm(prompt)
            agent4_result = Agent4Result(
                **self._parse_json_response(content, "配图需求")
            )
            state.content = agent4_result.content_with_placeholders

            state.image_requirements = self._validate_and_filter_image_requirements(
                agent4_result.image_requirements,
                state.enabled_image_methods,
            )
            log_data["outputData"] = self._safe_json_dumps(
                {
                    "rawRequirementsCount": len(agent4_result.image_requirements),
                    "validatedRequirementsCount": len(state.image_requirements),
                }
            )
            logger.info(
                "智能体4：配图需求分析成功, count=%s, validated=%s, 已在正文中插入占位符",
                len(agent4_result.image_requirements),
                len(state.image_requirements),
            )