from typing import Optional

from openai import AsyncOpenAI


from app.constants.article import ArticleConstant
from app.constants.prompt import PromptConstant
from app.services.image_search_service import BaseImageSearchService
from app.schemas.image import ImageData, ImageRequest
from app.models.enums import ImageMethodEnum
from app.utils.logger import logger
from app.config import settings

class SvgDiagramService(BaseImageSearchService):
    """SVG 概念示意图生成服务"""

    name = "SVG_DIAGRAM"
    description = "适合概念示意图、思维导图样式、逻辑关系展示（不涉及精确数据）"
    usage = (
        "在 prompt 字段描述示意图需求（中文），说明要表达的概念和关系。keywords 留空。\n"
        "  示例：绘制思维导图样式的图，中心是'自律'，周围4个分支：习惯、环境、反馈、系统"
    )
    is_ai_generate = True
    
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.dashscope_api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.model = settings.dashscope_model
    
    async def get_image_data(self, request: ImageRequest) -> Optional[ImageData]:
        requirement = request.get_effective_param(True)
        return await self.generate_svg_diagram_data(requirement)
    
    async def generate_svg_diagram_data(self, requirement: str) -> Optional[ImageData]:
        """生成 SVG 概念示意图数据"""
        try:
            prompt = PromptConstant.SVG_DIAGRAM_GENERATION_PROMPT.format(requirement=requirement)
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            svg_code = response.choices[0].message.content.strip()  # type: ignore
            
            # 移除 markdown 代码块标记（如 ```svg ... ```）
            if svg_code.startswith("```"):
                lines = svg_code.split("\n")[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                svg_code = "\n".join(lines).strip()
            
            # 验证 SVG 格式
            svg_lower = svg_code.lower()
            if not ("<svg" in svg_lower and "</svg>" in svg_lower):
                logger.error("生成的 SVG 代码格式无效")
                return None
            
            return ImageData.from_bytes(svg_code.encode('utf-8'), "image/svg+xml")
        except Exception as e:
            logger.error(f"SVG 概念示意图生成异常: {e}")
            return None
    
    def get_method(self) -> ImageMethodEnum:
        return ImageMethodEnum.SVG_DIAGRAM

    def get_fallback_image(self, position: int) -> str:
        return ArticleConstant.PICSUM_URL_TEMPLATE.format(position)
