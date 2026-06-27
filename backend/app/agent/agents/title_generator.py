"""
标题生成智能体
"""
from app.agent.base_agent import BaseAgent
from app.constants.prompt import PromptConstant
from app.schemas.article import ArticleState, TitleOption
from app.utils.logger import logger


class TitleGeneratorAgent(BaseAgent):
    """标题生成智能体"""

    async def run(self, state: ArticleState):
        """生成 3-5 个标题方案，填充 state.title_options"""
        prompt = PromptConstant.AGENT1_TITLE_PROMPT.format(topic=state.topic)
        prompt += self._get_style_prompt(state.style)

        async with self._agent_log_context(
            task_id=state.task_id,
            agent_name="agent1_generate_titles",
            prompt=prompt,
            input_data={"topic": state.topic, "style": state.style},
        ) as log_data:
            content = await self._call_llm(prompt)
            title_options_data = self._parse_json_list_response(content, "标题方案")
            state.title_options = [
                TitleOption(**item) for item in title_options_data
            ]
            log_data["outputData"] = self._safe_json_dumps(
                {"optionsCount": len(state.title_options)}
            )
            logger.info(
                "智能体1：标题方案生成成功, count=%s", len(state.title_options)
            )
