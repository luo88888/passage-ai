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
from app.services.image_search_service import BaseImageSearchService
from app.utils.logger import logger



class EmojiPackService(BaseImageSearchService):
    """表情包检索服务（基于 Bing 图片搜索）"""
    
    def __init__(self):
        self.search_url = settings.emoji_pack_search_url
        self.suffix = settings.emoji_pack_suffix
        self.timeout = settings.emoji_pack_timeout / 1000
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
    
    async def search_image(self, keywords: str) -> Optional[str]:
        """搜索表情包"""
        try:
            # 程序固定拼接"表情包"后缀
            search_text = keywords + self.suffix
            # 必须添加 mmasync=1 参数，否则返回的 HTML 中没有图片数据
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
            
            return image_url
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
    result = asyncio.run(pack_service.search_image(keywords))
    pprint(result)