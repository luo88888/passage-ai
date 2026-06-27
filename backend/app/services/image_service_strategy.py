"""
图片服务策略选择器
"""


from typing import Dict, List, Optional

from app.constants.article import ArticleConstant
from app.models.enums import ImageMethodEnum
from app.schemas.image import ImageData, ImageRequest
from app.services.image_search_service import BaseImageSearchService
# COS 暂未弃用，改用本地文件存储
from app.services.local_file_service import LocalFileService
from app.services.pexels_service import PexelsService
# NanoBananaService 暂未注册（见 _register_services 注释），import 保留待额度恢复后启用
# from app.services.nano_banana_service import NanoBananaService
from app.services.mermaid_service import MermaidService
from app.services.iconify_service import IconifyService
from app.services.emoji_pack_service import EmojiPackService
from app.services.svg_diagram_service import SvgDiagramService
from app.utils.logger import logger


class ImageResult:
    """图片获取结果"""
    
    def __init__(self, url: str, method: ImageMethodEnum):
        self.url = url
        self.method = method
    
    def is_success(self) -> bool:
        """判断是否成功"""
        return self.url is not None and len(self.url) > 0



class ImageServiceStrategy:
    """图片服务策略选择器"""
    
    def __init__(self):
        self.service_map: Dict[ImageMethodEnum, BaseImageSearchService] = {}
        self.local_file_service = LocalFileService()
        self._register_services()
    
    def _register_services(self):
        """注册所有图片服务"""
        # NanoBananaService 暂不注册：Gemini 免费额度耗尽（429 RESOURCE_EXHAUSTED），
        # 注册后每次调用都会失败再降级，徒增延迟。待额度/付费到位后再加回此列表。
        services = [
            PexelsService(),
            MermaidService(), IconifyService(),
            EmojiPackService(), SvgDiagramService(),
        ]
        for service in services:
            method = service.get_method()
            self.service_map[service.get_method()] = service
            logger.info(
                f"注册图片服务: {method.value} -> {service.__class__.__name__} "
                f"(AI生图: {method.is_ai_generated()}, 降级: {method.is_fallback()})"
            )
    
    async def get_image_and_upload(
        self,
        image_source: str,  # 应该在 ImageMethodEnum 中，否则使用兜底方法
        request: ImageRequest
    ) -> ImageResult:
        """获取图片并上传到 COS（推荐使用的主方法）"""
        method: ImageMethodEnum = self._resolve_method(image_source)
        service: Optional[BaseImageSearchService] = self.service_map.get(method)
        
        if service is None or not service.is_available():
            return await self._handle_fallback_with_upload(request.position)
        
        try:
            # 1. 获取/生成图片数据
            image_data: Optional[ImageData] = await service.get_image_data(request)
            
            if image_data is None or not image_data.is_valid():
                return await self._handle_fallback_with_upload(request.position)

            # 2. 获取图片保存路径（根据图片获取方式）
            folder = self._get_folder_for_method(method)

            # 3. 上传图片数据
            cos_url = await self.local_file_service.upload_image_data(image_data, folder)
            
            if cos_url:
                return ImageResult(cos_url, method)
            else:
                return await self._handle_fallback_with_upload(request.position)
        except Exception as e:
            logger.error(f"获取图片并上传异常, method={method}, error={e}")
            return await self._handle_fallback_with_upload(request.position)
    
    async def _handle_fallback_with_upload(self, position: Optional[int]) -> ImageResult:
        """处理降级逻辑（降级图片也上传到 COS）"""
        pos = position if position else 1
        fallback_url = ArticleConstant.PICSUM_URL_TEMPLATE.format(pos)
        fallback_data = ImageData.from_url(fallback_url)
        cos_url = await self.local_file_service.upload_image_data(fallback_data, "fallback")   # type: ignore
        final_url = cos_url if cos_url else fallback_url
        return ImageResult(final_url, ImageMethodEnum.get_fallback_method())

    def _resolve_method(self, image_source: str) -> ImageMethodEnum:
        """解析图片来源，处理未知值，str 应该是 ImageMethodEnum 中的值"""
        try:
            return ImageMethodEnum(image_source)
        except ValueError:
            logger.warning(
                f"未知的图片来源: {image_source}, "
                f"默认使用 {ImageMethodEnum.get_default_search_method().value}"
            )
            return ImageMethodEnum.get_default_search_method()

    def _get_folder_for_method(self, method: ImageMethodEnum) -> str:
        """根据图片方法获取 COS 文件夹"""
        folder_map = {
            ImageMethodEnum.PEXELS: "pexels",
            ImageMethodEnum.NANO_BANANA: "nano-banana",
            ImageMethodEnum.MERMAID: "mermaid",
            ImageMethodEnum.ICONIFY: "iconify",
            ImageMethodEnum.EMOJI_PACK: "emoji-pack",
            ImageMethodEnum.SVG_DIAGRAM: "svg-diagram",
            ImageMethodEnum.PICSUM: "picsum",
        }
        return folder_map.get(method, "unknown")

    def get_enabled_methods(self) -> List[ImageMethodEnum]:
        """当前实际已注册、可用的配图方式列表。

        与 service_map 保持一致——注册/取消某服务（如 NanoBanana 额度恢复）后，
        创作页"配图方式"选项会自动同步，无需改接口代码。
        """
        return list(self.service_map.keys())


# 模块级单例：strategy 无状态，LocalFileService 构造开销可忽略，全局复用安全。
image_service_strategy = ImageServiceStrategy()