"""
大纲生成智能体
"""
from typing import Callable

from app.agent.base_agent import BaseAgent
from app.constants.prompt import PromptConstant
from app.models.enums import SseMessageTypeEnum
from app.schemas.article import ArticleState, OutlineResult, OutlineSection
from app.utils.logger import logger


class OutlineGeneratorAgent(BaseAgent):
    """大纲生成智能体"""

    async def run(
        self,
        state: ArticleState,
        stream_handler: Callable[[str], None],
    ):
        """流式生成文章大纲，填充 state.outline"""
        description_section = ""
        if state.user_description and state.user_description.strip():
            description_section = PromptConstant.AGENT2_DESCRIPTION_SECTION.replace(
                "{userDescription}",
                state.user_description,
            )

        prompt = (
            PromptConstant.AGENT2_OUTLINE_PROMPT.format(
                mainTitle=state.title.main_title,   # type: ignore
                subTitle=state.title.sub_title,     # type: ignore
                descriptionSection=description_section
            )
        )
        prompt += self._get_style_prompt(state.style)

        async with self._agent_log_context(
            task_id=state.task_id,
            agent_name="agent2_generate_outline",
            prompt=prompt,
            input_data={
                "mainTitle": state.title.main_title if state.title else None,
                "subTitle": state.title.sub_title if state.title else None,
                "hasUserDescription": bool(
                    state.user_description and state.user_description.strip()
                ),
            },
        ) as log_data:
            content = await self._call_llm_with_streaming(
                prompt, stream_handler, SseMessageTypeEnum.AGENT2_STREAMING
            )
            outline_data = self._parse_json_response(content, "大纲")
            sections = [
                OutlineSection(**section) for section in outline_data["sections"]
            ]
            state.outline = OutlineResult(sections=sections)
            log_data["outputData"] = self._safe_json_dumps(
                {"sectionsCount": len(state.outline.sections)}
            )

        logger.info(
            "智能体2：大纲生成成功, sections=%s", len(state.outline.sections)
        )
