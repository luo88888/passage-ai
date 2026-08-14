"""
正文生成智能体
"""
from __future__ import annotations

import json
from typing import Callable, TYPE_CHECKING

from app.agent.base_agent import BaseAgent
from app.constants.prompt import PromptConstant
from app.models.enums import SseMessageTypeEnum
from app.schemas.article import ArticleState
from app.utils.logger import logger

if TYPE_CHECKING:
    from app.services.image_generator import ParallelImageGenerator


class ContentGeneratorAgent(BaseAgent):
    """正文生成智能体"""

    def __init__(self, model, agent_log_service, parallel_image_generator: ParallelImageGenerator):
        super().__init__(model, agent_log_service)
        # 配图方式说明由 ParallelImageGenerator 从已注册服务的 name/description/usage
        # 元数据动态构建（Markdown 表格），用于在正文撰写时注入"可用的配图方式"，
        # 引导 AI 按可用方式撰写 <imageN>描述</imageN> 标签内的需求描述。
        self.parallel_image_generator = parallel_image_generator

    async def run(
        self,
        state: ArticleState,
        stream_handler: Callable[[str], None],
    ):
        """流式生成文章正文，填充 state.content（含 <imageN>描述</imageN> 图片标签）"""
        methods_guide = self.parallel_image_generator.build_image_methods_guide(
            enabled_image_methods=state.enabled_image_methods,
        )
        outline_text = json.dumps(
            [section.model_dump() for section in state.outline.sections],   # type: ignore
            ensure_ascii=False,
        )
        prompt = PromptConstant.AGENT3_CONTENT_PROMPT.format(
            mainTitle=state.title.main_title,   # type: ignore
            subTitle=state.title.sub_title,     # type: ignore
            topic=state.topic,
            outline=outline_text,
            targetWordCount=state.word_count or 2000,
            imageMethodsGuide=methods_guide,
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
                prompt, stream_handler, SseMessageTypeEnum.AGENT3_STREAMING,
                agent_name="agent3_generate_content",
            )
            state.content = content
            log_data["outputData"] = self._safe_json_dumps(
                {"contentLength": len(content)}
            )
            logger.info("智能体3：正文生成成功, length=%s", len(content))
