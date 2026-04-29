"""
图片服务
"""
from abc import ABC, abstractmethod
from typing import Optional


from app.models.enums import ImageMethodEnum
from app.schemas.image import ImageRequest, ImageData


class BaseImageSearchService(ABC):
    """图片服务类，抽象图片获取逻辑，便于扩展多种来源"""

    async def get_image(self, request: ImageRequest) -> Optional[str]:
        """根据请求获取图片，子类可重写（弃用）"""
        params:str = request.get_effective_param(self.get_method().is_ai_generated())
        return await self.search_image(params)

    async def get_image_data(self, request: ImageRequest) -> Optional[ImageData]:
        """根据请求获取图片数据，子类可重写"""
        url = await self.get_image(request)
        return ImageData.from_url(url)

    @abstractmethod
    async def search_image(self, keywords: str) -> Optional[str]:
        """根据关键词/提示词获取图片"""
        pass

    @abstractmethod
    def get_method(self) -> ImageMethodEnum:
        """获取图片服务类型"""
        pass

    @abstractmethod
    def get_fallback_image(self, position: int) -> str:
        """降级获取图片 URL"""
        pass

    def is_available(self) -> bool:
        """是否可用（子类可重写健康检查）"""
        return True