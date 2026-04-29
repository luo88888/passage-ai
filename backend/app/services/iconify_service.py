from typing import Optional, Union
from urllib.parse import quote

import httpx


from app.constants.article import ArticleConstant
from app.services.image_search_service import BaseImageSearchService
from app.schemas.image import ImageData, ImageRequest
from app.models.enums import ImageMethodEnum
from app.utils.logger import logger
from app.config import settings


class IconifyService(BaseImageSearchService):
    """Iconify 图标库检索服务（提供 275k+ 开源图标）"""

    def __init__(self):
        self.api_url = settings.iconify_api_url
        self.search_limit = settings.iconify_search_limit
        self.default_height = settings.iconify_default_height
        self.default_color = settings.iconify_default_color
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def search_image(self, keywords: str, is_list=False) -> Optional[str]:
        """搜索图标并返回 SVG URL，keywords 是英文，最好是 单数、小写、多词用'-'分割"""
        try:
            search_url = f"{self.api_url}/search?query={quote(keywords)}&limit={self.search_limit}"
            response = await self.client.get(search_url)
            if response.status_code != 200:
                logger.error(f"Failed to search iconify icons: {response.text[:500]}")
                return None
            
            icons = response.json().get("icons", [])
            if not icons:
                return None
            
            # 将形如 "mdi:home" 格式转换为 URL 路径 "mdi/home"
            # icon_name = icons[0]
            # path = icon_name.replace(":", "/")
            # url = f"{self.api_url}/{path}.svg"
            paths = [icon.replace(":", "/") for icon in icons]
            urls = [f"{self.api_url}/{path}.svg" for path in paths]


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
                suffix = "?" + "&".join(params)
                # url += "?" + "&".join(params)
                urls = [f"{url}{suffix}" for url in urls]

            return urls[0]
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

    keywords = "search"
    result = asyncio.run(iconify_service.search_image(keywords))
    print(f"{keywords} 的图标链接为：{result}")
