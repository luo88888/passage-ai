"""
正文生成智能体
"""
import json
from typing import Callable

from app.agent.base_agent import BaseAgent
from app.constants.prompt import PromptConstant
from app.models.enums import SseMessageTypeEnum
from app.schemas.article import ArticleState
from app.utils.logger import logger


class ContentGeneratorAgent(BaseAgent):
    """正文生成智能体"""

    async def run(
        self,
        state: ArticleState,
        stream_handler: Callable[[str], None],
    ):
        """流式生成文章正文，填充 state.content"""
        outline_text = json.dumps(
            [section.model_dump() for section in state.outline.sections],   # type: ignore
            ensure_ascii=False,
        )
        prompt = PromptConstant.AGENT3_CONTENT_PROMPT.format(
            mainTitle=state.title.main_title,   # type: ignore
            subTitle=state.title.sub_title,     # type: ignore
            outline=outline_text,
            targetWordCount=state.word_count or 2000,
        )
        prompt += self._get_genre_prompt(state.genre)
        prompt += self._get_language_style_prompt(state.language_style)
        prompt += self._get_news_context_prompt(state.collected_news)

        async with self._agent_log_context(
            task_id=state.task_id,
            agent_name="agent3_generate_content",
            prompt=prompt,
            input_data={
                "mainTitle": state.title.main_title if state.title else None,
                "subTitle": state.title.sub_title if state.title else None,
                "outlineSections": (
                    len(state.outline.sections) if state.outline else 0
                ),
            },
        ) as log_data:
            content = await self._call_llm_with_streaming(
                prompt, stream_handler, SseMessageTypeEnum.AGENT3_STREAMING
            )
            state.content = content
            log_data["outputData"] = self._safe_json_dumps(
                {"contentLength": len(content)}
            )
            logger.info("智能体3：正文生成成功, length=%s", len(content))
