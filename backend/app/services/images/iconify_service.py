from typing import Optional
from urllib.parse import quote

import httpx


from app.constants.article import ArticleConstant
from app.services.images.image_search_service import BaseImageSearchService
from app.schemas.image import ImageData, ImageRequest
from app.models.enums import ImageMethodEnum
from app.utils.logger import logger
from app.config import settings


class IconifyService(BaseImageSearchService):
    """Iconify 图标库检索服务 — 调用 Iconify API 搜索 275k+ 开源图标，返回 SVG URL 类型的 ImageData。"""

    name = "ICONIFY"
    description = "适合图标、符号、小型装饰性图标（如：箭头、勾选、星星、心形等）"
    usage = "提供英文图标关键词(keywords)，如：check、arrow、star、heart。prompt 留空。keywords规范：英文、单数、小写，多词用 '-' 分割（如 'check-circle'）"
    is_ai_generate = False

    def __init__(self):
        self.api_url = settings.iconify_api_url
        self.search_limit = settings.iconify_search_limit
        self.default_height = settings.iconify_default_height
        self.default_color = settings.iconify_default_color
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_image_data(self, request: ImageRequest) -> Optional[ImageData]:
        """调用 Iconify API 搜索图标，返回 URL 类型 ImageData。

        关键词规范：英文、单数、小写，多词用 '-' 分割（如 "check-circle"）。

        Args:
            request: 图片请求对象，使用 request.keywords 作为图标关键词。

        Returns:
            URL 类型的 ImageData（SVG 格式）；无匹配图标时返回 None。
        """
        keywords = request.get_effective_param(False)
        try:
            search_url = f"{self.api_url}/search?query={quote(keywords)}&limit={self.search_limit}"
            response = await self.client.get(search_url)
            if response.status_code != 200:
                logger.error("Iconify 搜索失败: %s", response.text[:500])
                return None

            icons = response.json().get("icons", [])
            if not icons:
                return None

            # 将 "mdi:home" 格式转换为 URL 路径 "mdi/home.svg"
            path = icons[0].replace(":", "/")
            svg_url = f"{self.api_url}/{path}.svg"

            # 添加高度和颜色参数
            params = []
            if self.default_height > 0:
                params.append(f"height={self.default_height}")
            if self.default_color:
                color = self.default_color
                if color.startswith("#"):
                    color = "%23" + color[1:]
                params.append(f"color={color}")

            if params:
                svg_url += "?" + "&".join(params)

            return ImageData.from_url(svg_url)
        except Exception as e:
            logger.error(
                "Iconify 图标检索异常, keywords=%s, type=%s, error=%r",
                keywords, type(e).__name__, e,
            )
            return None

    def get_method(self) -> ImageMethodEnum:
        return ImageMethodEnum.ICONIFY

    def get_fallback_image(self, position: int) -> str:
        return ArticleConstant.PICSUM_URL_TEMPLATE.format(position)


if __name__ == "__main__":
    import asyncio
    iconify_service = IconifyService()

    async def test():
        keywords = ["red-apple", "hen", "gold", "big-dog", "篮球小鸡", "苹果", "star", "星星"]

        async def fetch_one(keyword: str) -> Optional[str]:
            result = await iconify_service.get_image_data(ImageRequest(keywords=keyword))  # type: ignore
            return result.url if result else None

        urls = await asyncio.gather(
            *[fetch_one(keyword) for keyword in keywords], 
            return_exceptions=True
        )

        for i, url in enumerate(urls):
            print(f"{keywords[i]} 的图标链接为：{url}")

    asyncio.run(test())
