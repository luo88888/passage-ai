import httpx
from typing import Optional


from app.config import settings
from app.constants.article import ArticleConstant
from app.models.enums import ImageMethodEnum
from app.services.image_search_service import BaseImageSearchService
from app.utils.logger import logger


class PexelsService(BaseImageSearchService):
    """Pexels 图片检索服务（基于 URL，复用基类默认的 get_image_data() 实现）"""

    def __init__(self):
        self.api_key = settings.pexels_api_key
        self.client = httpx.AsyncClient(timeout=30.0)

    async def search_image(self, keywords: str) -> Optional[str]:
        """根据关键词搜索图片"""
        try:
            url = self._build_search_url(keywords)
            headers = {"Authorization": self.api_key}
            response = await self.client.get(url, headers=headers)

            if response.status_code != 200:
                logger.warning("Pexels 请求异常 keywords=%s, status_code=%s", keywords, response.status_code)
                return None

            return self._extract_image_url(response.json(), keywords)
        except Exception as e:
            logger.error("Pexels API 调用异常 keywords=%s, error=%s", keywords, str(e), exc_info=True)
            return None

    def get_method(self) -> ImageMethodEnum:
        """获取配图方式"""
        return ImageMethodEnum.PEXELS

    def get_fallback_image(self, position: int) -> str:
        """获取降级图片"""
        return ArticleConstant.PICSUM_URL_TEMPLATE.format(position)
    
    def _build_search_url(self, keywords: str) -> str:
        """构建搜索 URL"""
        return (
            f"{ArticleConstant.PEXELS_API_URL}"
            f"?query={keywords}"
            f"&per_page={ArticleConstant.PEXELS_PER_PAGE}"
            f"&orientation={ArticleConstant.PEXELS_ORIENTATION_LANDSCAPE}"
        )
    
    def _extract_image_url(self, response_data: dict, keywords: str) -> Optional[str]:
        """从响应中提取图片 URL"""
        photos = response_data.get("photos", [])
        if not photos:
            return None
        
        photo = photos[0]
        src = photo.get("src", {})
        return src.get("large")


if __name__ == '__main__':
    import asyncio
    px = PexelsService()

    print("正在搜索...")
    result = asyncio.run(px.search_image("apple"))
    print(result)
    print("end")