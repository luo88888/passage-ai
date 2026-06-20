from app.schemas.article import ArticleState


class OutlineGeneratorAgent:
    """大纲生成智能体"""

    async def run(self, service, state: ArticleState, stream_handler):
        await service.agent2_generate_outline(state, stream_handler)
