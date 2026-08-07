"""
标题生成智能体
"""
from app.agent.base_agent import BaseAgent
from app.constants.prompt import PromptConstant
from app.schemas.article import ArticleState, TitleOptionResult
from app.utils.logger import logger


class TitleGeneratorAgent(BaseAgent):
    """标题生成智能体"""

    async def run(self, state: ArticleState):
        """生成 3-5 个标题方案，填充 state.title_options"""
        prompt = PromptConstant.AGENT1_TITLE_PROMPT.format(topic=state.topic)
        prompt += self._get_genre_prompt(state.genre)
        prompt += self._get_language_style_prompt(state.language_style)
        prompt += self._get_news_context_prompt(state.collected_news)

        async with self._agent_log_context(
            task_id=state.task_id,
            agent_name="agent1_generate_titles",
            prompt=prompt,
            input_data={
                "topic": state.topic,
                "genre": state.genre,
                "hasCollectedNews": bool(state.collected_news and state.collected_news.strip()),
            },
        ) as log_data:
            result: TitleOptionResult = await self._call_structured_model(
                prompt, agent_name="agent1_generate_titles"
            )
            state.title_options = result.title_options
            log_data["outputData"] = self._safe_json_dumps(
                {"optionsCount": len(state.title_options)}
            )
            logger.info(
                "智能体1：标题方案生成成功, count=%s", len(state.title_options)
            )
