from app.schemas.article import ArticleState


class ContentGeneratorAgent:
    """正文生成智能体"""

    async def run(self, service, state: ArticleState, stream_handler):
        await service.agent3_generate_content(state, stream_handler)
