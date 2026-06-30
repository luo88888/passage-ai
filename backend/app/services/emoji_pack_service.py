"""
表情包搜索服务
"""
from typing import Optional
from urllib.parse import quote

from bs4 import BeautifulSoup
import httpx


from app.config import settings
from app.constants.article import ArticleConstant
from app.models.enums import ImageMethodEnum
from app.schemas.image import ImageData, ImageRequest
from app.services.image_search_service import BaseImageSearchService
from app.utils.logger import logger


class EmojiPackService(BaseImageSearchService):
    """表情包检索服务 — 基于 Bing 图片搜索，自动在关键词后拼接"表情包"后缀，返回 URL 类型 ImageData。"""

    name = "EMOJI_PACK"
    description = "适合表情包、搞笑图片、轻松幽默的配图"
    usage = "提供中文或英文关键词(keywords)描述表情内容。prompt 留空。系统会自动添加'表情包'搜索。"
    is_ai_generate = False

    def __init__(self):
        self.search_url = settings.emoji_pack_search_url
        self.suffix = settings.emoji_pack_suffix
        self.timeout = settings.emoji_pack_timeout / 1000
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36"
                ),
            },
        )

    async def get_image_data(self, request: ImageRequest) -> Optional[ImageData]:
        """调用 Bing 图片搜索表情包，返回 URL 类型 ImageData。

        系统会自动在 request.keywords 后拼接 self.suffix（默认"表情包"），
        并使用 mmasync=1 参数获取异步加载的图片数据。

        Args:
            request: 图片请求对象，使用 request.keywords 作为搜索关键词（中文）。

        Returns:
            URL 类型的 ImageData；搜索无结果时返回 None。
        """
        keywords = request.get_effective_param(False)
        try:
            search_text = keywords + self.suffix
            fetch_url = f"{self.search_url}?q={quote(search_text)}&mmasync=1"

            response = await self.client.get(fetch_url)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'lxml')
            div = soup.find('div', class_='dgControl')
            if not div:
                return None

            img_elements = div.select('img.mimg')
            if not img_elements:
                return None

            image_url = img_elements[0].get('src')
            if not image_url:
                return None

            # 移除 URL 中的尺寸参数（?w=xxx&h=xxx），避免图片质量下降
            question_mark_index = image_url.find("?")
            if question_mark_index > 0:
                image_url = image_url[:question_mark_index]

            return ImageData.from_url(image_url)
        except Exception as e:
            logger.error(
                "表情包检索异常, keywords=%s, type=%s, error=%r",
                keywords, type(e).__name__, e,
            )
            return None

    def get_method(self) -> ImageMethodEnum:
        return ImageMethodEnum.EMOJI_PACK

    def get_fallback_image(self, position: int) -> str:
        return ArticleConstant.PICSUM_URL_TEMPLATE.format(position)


if __name__ == "__main__":
    import asyncio
    from pprint import pprint
    pack_service = EmojiPackService()
    keywords = "生气"
    result = asyncio.run(pack_service.get_image_data(ImageRequest(keywords=keywords)))  # type: ignore
    pprint(result.url if result else "无结果")
