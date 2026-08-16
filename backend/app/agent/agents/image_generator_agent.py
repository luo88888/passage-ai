"""
配图生成智能体
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from app.agent.base_agent import _safe_json_dumps, agent_log_context
from app.constants.prompt import PromptConstant
from app.models.enums import ImageMethodEnum, SseMessageTypeEnum
from app.schemas.article import ArticleState, ImageRequirement, ImageResult
from app.utils.logger import logger

if TYPE_CHECKING:
    from app.services.image_generator import ParallelImageGenerator
    from app.services.agent_log_service import AgentLogService


class ImageGeneratorAgent:
    """配图生成智能体"""

    def __init__(
        self,
        parallel_image_generator: ParallelImageGenerator,
        agent_log_service: AgentLogService,
    ):
        self.parallel_image_generator = parallel_image_generator
        self.agent_log_service = agent_log_service

    async def run(
        self,
        state: ArticleState,
        stream_handler: Callable[[str], None],
    ):
        """并行生成所有配图，每完成一张推送 SSE 事件，填充 state.images"""
        async with agent_log_context(
            self.agent_log_service,
            task_id=state.task_id,
            agent_name="agent5_generate_images",
            prompt=PromptConstant.AGENT5_IMAGE_EXECUTION_PROMPT,
            input_data={"requirementsCount": len(state.image_requirements or [])},
        ) as log_data:
            generated_pairs = await self.parallel_image_generator.generate(
                state.image_requirements or []
            )
            image_results = []

            for requirement, result in generated_pairs:
                image_source = requirement.image_source
                logger.info(
                    "智能体5：开始获取配图, position=%s, imageSource=%s, keywords=%s",
                    requirement.position,
                    image_source,
                    requirement.keywords,
                )

                cos_url = result.url
                method = result.method

                image_result = self._build_image_result(
                    requirement, cos_url, method
                )
                image_results.append(image_result)

                # 推送单张配图完成
                image_complete_message = (
                    SseMessageTypeEnum.IMAGE_COMPLETE.get_streaming_prefix()
                    + image_result.model_dump_json(by_alias=True)
                )
                stream_handler(image_complete_message)

                logger.info(
                    "智能体5：配图获取并上传成功, position=%s, method=%s, cosUrl=%s",
                    requirement.position,
                    method.value,
                    cos_url,
                )

            # 并行执行后按位置排序，确保输出稳定
            state.images = sorted(image_results, key=lambda item: item.position)
            log_data["outputData"] = _safe_json_dumps(
                {"imagesCount": len(image_results)}
            )
            logger.info(
                "智能体5：所有配图生成并上传完成, count=%s", len(image_results)
            )

    @staticmethod
    def _build_image_result(
        requirement: ImageRequirement,
        image_url: str,
        method: ImageMethodEnum,
    ) -> ImageResult:
        """构建配图结果"""
        return ImageResult(
            position=requirement.position,
            url=image_url,
            method=method.value,
            keywords=requirement.keywords,
            sectionTitle=requirement.section_title,
            description=requirement.type,
            placeholderId=requirement.placeholder_id,
        )
