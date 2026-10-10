"""
大纲生成智能体
"""
from typing import Callable

from app.agent.base_agent import BaseAgent
from app.constants.prompt import PromptConstant
from app.models.enums import RetryStageEnum, SseMessageTypeEnum
from app.schemas.article import ArticleState, OutlineResult, OutlineSection
from app.utils.logger import logger


class OutlineGeneratorAgent(BaseAgent):
    """大纲生成智能体"""

    async def run(
        self,
        state: ArticleState,
        stream_handler: Callable[[str], None],
    ):
        """流式生成文章大纲，填充 state.outline

        重试策略（与正文不同，大纲需要 JSON 解析校验）：
          - 首次尝试保持流式，维持现有用户体验；
          - 解析失败后发送 AGENT_RETRY，后续重试改为非流式生成，
            解析成功后再由节点的 AGENT2_COMPLETE 全量回填；
          - 若仍失败，抛出 AgentMaxRetriesError。
        """
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
                descriptionSection=description_section,
                targetWordCount=state.word_count or 2000,
                topic=state.topic
            )
        )
        prompt += self._get_genre_prompt(state.genre)
        prompt += self._get_language_style_prompt(state.language_style)
        prompt += self._get_news_context_prompt(state.collected_news)

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
            async def _attempt_outline(
                current_prompt: str, attempt_no: int
            ) -> OutlineResult:
                """单次大纲生成尝试：首次流式、格式错误修正重试改非流式"""
                if attempt_no == 1:
                    # 首次尝试保持流式（瞬时错误在流式方法内部自行重试）
                    content = await self._call_llm_with_streaming(
                        current_prompt,
                        stream_handler,
                        SseMessageTypeEnum.AGENT2_STREAMING,
                        agent_name="agent2_generate_outline",
                        retry_stage=RetryStageEnum.OUTLINE,
                        retry_message="大纲生成异常，正在重新生成",
                    )
                else:
                    # 格式错误修正重试改为非流式，解析成功后由 AGENT2_COMPLETE 全量回填
                    content = await self._call_llm(
                        current_prompt,
                        agent_name="agent2_generate_outline",
                        retry_stage=RetryStageEnum.OUTLINE,
                        stream_handler=stream_handler,
                        retry_message="大纲格式异常，正在重新生成",
                    )
                outline_data = self._parse_json_response(content, "大纲")
                sections = [
                    OutlineSection(**section) for section in outline_data["sections"]
                ]
                return OutlineResult(sections=sections)

            state.outline = await self._run_with_retry(
                prompt=prompt,
                agent_name="agent2_generate_outline",
                max_retry=None,
                attempt=_attempt_outline,
                retry_stage=RetryStageEnum.OUTLINE,
                stream_handler=stream_handler,
                retry_message="大纲格式异常，正在重新生成",
            )
            log_data["outputData"] = self._safe_json_dumps(
                {"sectionsCount": len(state.outline.sections)}
            )

        logger.info(
            "智能体2：大纲生成成功, sections=%s", len(state.outline.sections)
        )
