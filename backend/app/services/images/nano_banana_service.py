"""
Nano banana 生图服务 / Gemini AI（暂时停用该服务）
"""

import logging
from typing import Optional

from google import genai
from google.genai import types

from app.constants.article import ArticleConstant
from app.models.enums import ImageMethodEnum
from app.schemas.image import ImageRequest, ImageData
from app.services.images.image_search_service import BaseImageSearchService
from app.services.model_usage_service import usage_recorder
from app.config import settings

logger = logging.getLogger(__name__)


class NanoBananaService(BaseImageSearchService):
    """Nano Banana (Gemini 原生图片生成) 服务"""

    name = "NANO_BANANA"
    description = "适合创意插画、信息图表、需要文字渲染、抽象概念、艺术风格等 AI 生成图片"
    usage = "提供详细的英文生图提示词(prompt),描述场景、风格、细节"
    is_ai_generate = True
    
    def __init__(self):
        self.api_key = settings.nano_banana_api_key
        self.model = settings.nano_banana_model
        self.aspect_ratio = settings.nano_banana_aspect_ratio
        self.client = genai.Client(api_key=self.api_key)
    
    async def get_image_data(self, request: ImageRequest) -> Optional[ImageData]:
        prompt = request.get_effective_param(True)
        return await self.generate_image_data(prompt)
    
    async def generate_image_data(self, prompt: str) -> Optional[ImageData]:
        """根据提示词生成图片数据"""
        try:
            # 注意: google-genai==1.35.0 的 GenerateContentConfig 没有 image_config / aspect_ratio
            # 参数;画面比例需通过在提示词中追加约束来控制(如 "wide 16:9 aspect ratio")。
            aspect_hint = ""
            if self.aspect_ratio:
                aspect_hint = f"\n\nGenerate the image with aspect ratio {self.aspect_ratio}."
            config = types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            )

            response = self.client.models.generate_content(
                model=self.model or "gemini-2.5-flash-image",
                contents=prompt + aspect_hint,
                config=config
            )
            
            if response.candidates and response.candidates[0].content.parts:    # type: ignore
                for part in response.candidates[0].content.parts:   # type: ignore
                    if part.inline_data:
                        image_bytes = part.inline_data.data
                        mime_type = part.inline_data.mime_type or "image/png"
                        self._record_usage(status="SUCCESS", image_count=1)
                        return ImageData.from_bytes(image_bytes, mime_type) # type: ignore
            self._record_usage(status="FAILED", image_count=0)
            return None
        except Exception as e:
            logger.error(
                "Nano Banana 生成图片异常, type=%s, error=%r",
                type(e).__name__, e,
            )
            self._record_usage(status="FAILED", image_count=0)
            return None

    def _record_usage(self, status: str, image_count: int) -> None:
        """上报 Nano Banana 生图用量（成功 1 张 / 失败 0 张）。

        Args:
            status: SUCCESS / FAILED。
            image_count: 成功生成张数。
        """
        usage_recorder.record_image(
            provider="NanoBanana",
            model=self.model or "gemini-2.5-flash-image",
            agent_name="agent5_generate_images",
            image_count=image_count,
            status=status,
        )

    def get_method(self) -> ImageMethodEnum:
        return ImageMethodEnum.NANO_BANANA

    def get_fallback_image(self, position: int) -> str:
        return ArticleConstant.PICSUM_URL_TEMPLATE.format(position)


if __name__ == "__main__":
    import asyncio
    service = NanoBananaService()

    result = asyncio.run(service.get_image_data(ImageRequest(keywords="hello world")))   # type: ignore
    print(f"type: {type(result)}")
    if not result:
        print("result is None")
    else:
        print(f"result: {result.is_valid()}")