from app.schemas.article import ArticleState


class ImageAnalyzerAgent:
    """配图需求分析智能体"""

    async def run(self, service, state: ArticleState):
        await service.agent4_analyze_image_requirements(state)
