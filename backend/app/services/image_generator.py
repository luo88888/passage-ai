from __future__ import annotations

import asyncio
from typing import Dict, List, Optional, Tuple

from app.config import settings
from app.constants.article import ArticleConstant
from app.models.enums import ImageMethodEnum
from app.schemas.article import ImageRequirement
from app.schemas.image import ImageData, ImageRequest
from app.services.image_search_service import BaseImageSearchService
from app.services.local_file_service import LocalFileService
from app.services.pexels_service import PexelsService
# NanoBananaService 暂未注册（见 _register_services 注释），import 保留待额度恢复后启用
# from app.services.nano_banana_service import NanoBananaService
from app.services.mermaid_service import MermaidService
from app.services.iconify_service import IconifyService
from app.services.emoji_pack_service import EmojiPackService
from app.services.svg_diagram_service import SvgDiagramService
from app.services.zhipu_image_service import ZhipuImageService
from app.utils.logger import logger


class ImageResult:
    """图片获取结果"""

    def __init__(self, url: str, method: ImageMethodEnum, is_fallback: bool=False):
        self.url = url
        self.method = method
        self.is_fallback: bool = is_fallback

    def is_success(self) -> bool:
        """判断是否成功"""
        return self.url is not None and len(self.url) > 0


class ParallelImageGenerator:
    """并行配图生成器

    职责：
    1. 注册并持有各图片获取服务（service_map），按 ImageMethodEnum 分发；
    2. 提供 get_image_and_upload：获取/生成图片 → 上传 → 返回 URL；异常降级到 PICSUM；
    3. 提供 generate：基于 semaphore 并行处理一组 ImageRequirement 并按原序返回结果；
    4. 暴露 get_enabled_methods（前端"配图方式"选项）与 build_image_methods_guide
       （供配图需求分析智能体读取各服务元数据，动态拼出给 LLM 的配图方式说明表格）。
    """

    def __init__(self, max_concurrency: int, fail_fast: bool):
        self.service_map: Dict[ImageMethodEnum, BaseImageSearchService] = {}
        self.local_file_service = LocalFileService()
        self.max_concurrency = max(1, max_concurrency)
        self.fail_fast = fail_fast
        self._register_services()

    def _register_services(self):
        """注册所有图片服务"""
        # NanoBananaService 暂不注册：Gemini 免费额度耗尽（429 RESOURCE_EXHAUSTED），
        # 注册后每次调用都会失败再降级，徒增延迟。待额度/付费到位后再加回此列表。
        services: List[BaseImageSearchService] = [
            PexelsService(),
            MermaidService(), IconifyService(),
            EmojiPackService(), SvgDiagramService(),
        ]
        # 智谱 AI 生图：仅在配置了 API key 时才注册，避免空 key 时每次调用失败再降级
        if settings.zhipu_api_key:
            services.append(ZhipuImageService())

        for service in services:
            method = service.get_method()
            self.service_map[service.get_method()] = service
            logger.info(
                f"注册图片服务: {method.value} -> {service.__class__.__name__} "
                f"(AI生图: {method.is_ai_generated()}, 降级: {method.is_fallback()}, 是否可用: {service.is_available()})"
            )

    async def get_image_and_upload(
        self,
        image_source: str,  # 应该在 ImageMethodEnum 中，否则使用兜底方法
        request: ImageRequest
    ) -> ImageResult:
        """获取图片并上传到本地文件存储（推荐使用的主方法）"""
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
        """处理降级逻辑（降级图片也上传到本地存储）"""
        pos = position if position else 1
        fallback_url = ArticleConstant.PICSUM_URL_TEMPLATE.format(pos)
        fallback_data = ImageData.from_url(fallback_url)
        cos_url = await self.local_file_service.upload_image_data(fallback_data, "fallback")   # type: ignore
        final_url = cos_url if cos_url else fallback_url
        return ImageResult(
            url=final_url,
            method=ImageMethodEnum.get_fallback_method(),
            is_fallback=True
        )

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
        """根据图片方法获取保存文件夹"""
        # NOTE: 增加图片生成服务时需在此增加对应字段
        folder_map = {
            ImageMethodEnum.PEXELS: "pexels",
            ImageMethodEnum.NANO_BANANA: "nano-banana",
            ImageMethodEnum.ZHIPU: "zhipu",
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
        # return list(self.service_map.keys())
        # method: service
        result = []
        for method, service in self.service_map.items():
            if service.is_available():
                result.append(method)
        return result

    def get_registered_services(self) -> List[BaseImageSearchService]:
        """返回已注册的服务列表，供外部读取 name/description/usage 等元数据。"""
        return list(self.service_map.values())

    def build_image_methods_guide(
        self,
        enabled_image_methods: Optional[List[str]] = None,
    ) -> str:
        """构建给 LLM 的「可用配图方式」说明，Markdown 表格格式，自动过滤不可用的方式

        Args:
            enabled_image_methods: 允许使用的配图方式列表（值为 ImageMethodEnum.value）；
                为 None 表示可以使用全部已注册服务。

        Returns:
            Markdown 表格字符串，列：配图方式 | 适用场景 | 使用指南。
            PICSUM 等兜底方式不暴露给 LLM；过滤后无可用方式时返回占位提示。
        """
        services = list(self.service_map.values())

        # 按启用列表和 is_available() 过滤；None 表示全部已注册服务
        if enabled_image_methods is not None:
            enabled_set = set(enabled_image_methods)
            services = [s for s in services if s.name in enabled_set and s.is_available()]

        # 排除兜底方式（PICSUM 不应作为创作选项暴露给 LLM）
        services = [
            s for s in services
            if not ImageMethodEnum(s.name).is_fallback()
        ]

        if not services:
            return "（无可用配图方式）"

        # usage 文本可能以 "- NAME: " 开头，表格「配图方式」列已含 name，剥离该前缀避免冗余
        def _strip_usage_prefix(usage: str, name: str) -> str:
            prefix = f"- {name}:"
            text = usage[len(prefix):].lstrip() if usage.startswith(prefix) else usage
            # usage 可能跨多行（如 Mermaid/SVG 的示例行），Markdown 表格单元格内的
            # 换行会破坏行结构，统一用 <br> 替换；并折叠行首缩进。
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return " ".join(lines)

        rows = "\n".join(
            f"| {s.name} | {s.description} | {_strip_usage_prefix(s.usage, s.name)} |"
            for s in services
        )
        return "| 配图方式 | 适用场景 | 使用指南 |\n|---|---|---|\n" + rows

    async def generate(
        self,
        requirements: List[ImageRequirement],
    ) -> List[Tuple[ImageRequirement, ImageResult]]:
        """并行生成图片，按输入顺序返回结果"""
        if not requirements:
            return []

        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def _generate_single(requirement: ImageRequirement):
            async with semaphore:
                image_request = ImageRequest(   # type: ignore
                    keywords=requirement.keywords,
                    prompt=requirement.prompt,
                    position=requirement.position,
                    type=requirement.type,
                )
                result = await self.get_image_and_upload(
                    requirement.image_source,
                    image_request,
                )
                return requirement, result

        results = await asyncio.gather(
            *[_generate_single(requirement) for requirement in requirements],
            return_exceptions=True,
        )

        generated_pairs: List[Tuple[ImageRequirement, ImageResult]] = []
        first_error = None
        for item in results:
            if isinstance(item, BaseException):
                if first_error is None:
                    first_error = item
            else:
                generated_pairs.append(item)

        if first_error and (self.fail_fast or not generated_pairs):
            raise first_error
        return generated_pairs


# 模块级单例：服务实例（含 httpx/AsyncOpenAI 客户端）全局复用，构造一次。
# 图节点编排器（app/graph/nodes/_orchestrator.py）与 article_service 的配图选项都依赖此单例。
parallel_image_generator = ParallelImageGenerator(
    max_concurrency=settings.agent_image_max_concurrency,
    fail_fast=settings.agent_image_fail_fast,
)