from app.schemas.article import ArticleState


class TitleGeneratorAgent:
    """标题生成智能体"""

    async def run(self, service, state: ArticleState):
        await service.agent1_generate_title_options(state)
