import httpx
from typing import Optional

from app.config import settings
from app.constants.article import ArticleConstant
from app.models.enums import ImageMethodEnum
from app.schemas.image import ImageData, ImageRequest
from app.services.images.image_search_service import BaseImageSearchService
from app.utils.logger import logger


class PexelsService(BaseImageSearchService):
    """Pexels 图片检索服务 — 调用 Pexels API 搜索高质量真实摄影图，返回 URL 类型 ImageData。"""

    name = "PEXELS"
    description = "适合真实场景、产品照片、人物照片、自然风景等写实图片"
    usage = "提供英文搜索关键词(keywords)，要准确、具体。prompt 留空。"
    is_ai_generate = False

    def __init__(self):
        self.api_key = settings.pexels_api_key
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_image_data(self, request: ImageRequest) -> Optional[ImageData]:
        """调用 Pexels API 搜索图片，返回 URL 类型 ImageData。

        Args:
            request: 图片请求对象，使用 request.keywords 作为搜索关键词。

        Returns:
            URL 类型的 ImageData；搜索无结果或 API 异常时返回 None。
        """
        keywords = request.get_effective_param(False)
        try:
            url = self._build_search_url(keywords)
            headers = {"Authorization": self.api_key}
            response = await self.client.get(url, headers=headers)

            if response.status_code != 200:
                logger.warning(
                    "Pexels 请求异常 keywords=%s, status_code=%s",
                    keywords, response.status_code,
                )
                return None

            image_url = self._extract_image_url(response.json())
            if not image_url:
                return None
            return ImageData.from_url(image_url)
        except Exception as e:
            logger.error(
                "Pexels API 调用异常 keywords=%s, error=%s",
                keywords, str(e), exc_info=True,
            )
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

    def _extract_image_url(self, response_data: dict) -> Optional[str]:
        """从 Pexels API 响应中提取第一张图片的 large 尺寸 URL。

        Args:
            response_data: Pexels API 返回的 JSON 响应体。

        Returns:
            图片 URL 字符串；无结果时返回 None。
        """
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
    image_data = asyncio.run(px.get_image_data(ImageRequest(keywords="apple"))) # type: ignore
    print(image_data.url if image_data else "无结果")
    print("end")