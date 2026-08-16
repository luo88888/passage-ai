"""
智谱 GLM-Image AI 生图服务
"""

import logging
from typing import Optional

import httpx

from app.config import settings
from app.constants.article import ArticleConstant
from app.count_semaphore import AsyncCountingSemaphore
from app.models.enums import ImageMethodEnum
from app.schemas.image import ImageRequest, ImageData
from app.services.image_search_service import BaseImageSearchService
from app.services.model_usage_service import usage_recorder
from app.utils.logger import logger


class ZhipuImageService(BaseImageSearchService):
    """智谱原生 AI 生图服务。"""

    name = "ZHIPU"
    description = "适合商业海报、科普插画、多格图画、封面设计与版式结构较为复杂的社交媒体图文内容、人物、风景、动植物等"
    usage = "提供详细的生图提示词（prompt），描述场景、风格、布局、细节等"
    is_ai_generate = True

    # 智谱开放平台图像生成接口
    _API_URL = "https://open.bigmodel.cn/api/paas/v4/images/generations"
    # 返回的图片 URL 临时有效期 30 天，须及时下载转存
    _IMAGE_DOWNLOAD_TIMEOUT = 30.0

    def __init__(self):
        self.api_key = settings.zhipu_api_key
        self.model = settings.zhipu_image_model
        self.size = settings.zhipu_image_size
        self.client = httpx.AsyncClient(timeout=settings.zhipu_image_timeout)
        # 智谱 AI 生图有并发限制，需根据实际情况进行限流
        # 该服务为模块级单例（由 ParallelImageGenerator 注册一次），故此信号量跨文章全局生效。
        self._semaphore = AsyncCountingSemaphore(settings.zhipu_image_max_concurrency)
        logger.info(f"智谱 AI 生图服务初始化成功，model={self.model}，max_concurrency={settings.zhipu_image_max_concurrency}")

    async def get_image_data(self, request: ImageRequest) -> Optional[ImageData]:
        """根据提示词生成图片数据。

        智谱接口返回的是图片临时 URL（有效期 30 天），这里下载为 bytes 后返回，便于后续统一上传转存。
        成功/失败均按张上报模型用量。
        """
        prompt = request.get_effective_param(True)
        if not prompt:
            return None

        # 等待限流槽位（waiting 为当前排队数，便于观测）
        logger.info(f"智谱 {self.model} 等待限流槽位, waiting={self._semaphore.waiting_count}")
        image_url: Optional[str] = None
        succeeded = False
        async with self._semaphore:
            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": self.model or "cogview-3-flash",
                    "prompt": prompt,
                    "size": self.size or "1152x864",
                }
                response = await self.client.post(self._API_URL, headers=headers, json=payload)
                if response.status_code != 200:
                    logger.error(
                        f"智谱 {self.model} 生成图片失败: status={response.status_code}, body={response.text[:500]}"
                    )
                else:
                    error = response.json().get("error") or {}
                    if error:
                        logger.error(
                            f"智谱 {self.model} 生成图片异常: {str(error)}"
                        )
                    else:
                        data = response.json().get("data") or []
                        if not data:
                            logger.error(f"智谱 {self.model} 生成图片异常: 响应 data 为空")
                        else:
                            image_url = data[0].get("url")
                            succeeded = bool(image_url)
                            if not image_url:
                                logger.error(f"智谱 {self.model} 生成图片异常: 响应缺少 url")
            except Exception as e:
                logger.error(
                    f"智谱 {self.model} 生成图片异常, type={type(e).__name__}, error={str(e)}"
                )

        self._record_usage(
            status="SUCCESS" if succeeded else "FAILED",
            image_count=1 if succeeded else 0,
        )
        if not succeeded:
            return None

        # 下载临时图片为 bytes 转存到本地/COS，避免链接过期失效。
        # 放在信号量之外：限流约束的是「智谱生图调用」，下载转存不受其约束。
        return await self._download_image(image_url)

    def _record_usage(self, status: str, image_count: int) -> None:
        """上报智谱生图用量（成功 1 张 / 失败 0 张）。

        Args:
            status: SUCCESS / FAILED。
            image_count: 成功生成张数。
        """
        usage_recorder.record_image(
            provider="Zhipu",
            model=self.model or "cogview-3-flash",
            agent_name="agent5_generate_images",
            image_count=image_count,
            status=status,
        )

    async def _download_image(self, image_url: str) -> Optional[ImageData]:
        """下载智谱返回的临时图片 URL 为 bytes。"""
        try:
            async with httpx.AsyncClient(timeout=self._IMAGE_DOWNLOAD_TIMEOUT) as dl_client:
                dl_resp = await dl_client.get(image_url)
            if dl_resp.status_code != 200:
                logger.error(
                    f"智谱 {self.model} 图片下载失败: status=%s, url=%s",
                    dl_resp.status_code, image_url,
                )
                return None
            mime_type = dl_resp.headers.get("Content-Type") or "image/png"
            return ImageData.from_bytes(dl_resp.content, mime_type)
        except Exception as e:
            logger.error(
                f"智谱 {self.model} 图片下载异常, type={type(e).__name__}, error={str(e)}"
            )
            return None

    def get_method(self) -> ImageMethodEnum:
        return ImageMethodEnum.ZHIPU

    def get_fallback_image(self, position: int) -> str:
        return ArticleConstant.PICSUM_URL_TEMPLATE.format(position)


if __name__ == "__main__":
    import asyncio

    service = ZhipuImageService()
    result = asyncio.run(service.get_image_data(ImageRequest(prompt="1girl, anime style, cute contour, big bright eyes, strawberry blonde hair with pastel highlights, twin tails, wearing white sailor suit and navy pleated skirt, sitting on a wooden bench, holding a textbook, cherry blossom background, petals falling, soft focus, warm golden hour lighting.")))  # type: ignore
    print(f"type: {type(result)}")
    if not result:
        print("result is None")
    else:
        print(f"result: {result.is_valid()}")