"""腾讯云 COS 服务"""

import logging
import httpx
import uuid
from typing import Optional
from qcloud_cos import CosConfig, CosS3Client   # HACK: 同步阻塞，会阻塞事件循环
from io import BytesIO

from app.config import settings
from app.schemas.image import ImageData, DataType
from app.utils.logger import logger


class CosService:
    """腾讯云 COS 服务"""
    
    def __init__(self):
        # 初始化 COS 客户端
        config = CosConfig(
            Region=settings.tencent_cos_region,
            SecretId=settings.tencent_cos_secret_id,
            SecretKey=settings.tencent_cos_secret_key,
            Scheme='https'
        )
        self.client = CosS3Client(config)
        self.bucket = settings.tencent_cos_bucket
        self.region = settings.tencent_cos_region
        # follow_redirects=True: picsum.photos 返回 302 跳转到 fastly.picsum.photos，
        # 不跟随会被当作下载失败，导致降级链拿不到图。
        self.http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    # 旧版方法
    # async def upload_image(self, image_url: str, folder: str) -> str:
    #     """
    #     上传图片到 COS，只能处理纯外部 URL，固定写死 .jpg 后缀
        
    #     Args:
    #         image_url: 图片 URL
    #         folder: 文件夹
            
    #     Returns:
    #         COS 图片 URL
    #     """
    #     try:
    #         # 下载图片
    #         response = await self.http_client.get(image_url)
    #         if response.status_code != 200:
    #             logger.error(f"下载图片失败: {image_url}")
    #             return image_url  # 降级：直接返回原始 URL
            
    #         image_bytes = response.content
            
    #         # 生成文件名
    #         import uuid
    #         file_name = f"{folder}/{uuid.uuid4()}.jpg"
            
    #         # 上传到 COS
    #         self.client.put_object(
    #             Bucket=self.bucket,
    #             Body=BytesIO(image_bytes),
    #             Key=file_name,
    #             ContentType='image/jpeg'
    #         )
            
    #         # 返回访问 URL
    #         return f"https://{self.bucket}.cos.{self.region}.myqcloud.com/{file_name}"
    #     except Exception as e:
    #         logger.error(f"上传图片到 COS 失败: {e}")
    #         return image_url  # 降级：直接返回原始 URL
    
    async def upload_image_data(
        self,
        image_data: ImageData,
        folder: str
    ) -> Optional[str]:
        """
        上传图片数据到 COS
        支持多种数据格式：字节数据、URL、data URL
        
        Args:
            image_data: 图片数据
            folder: 文件夹，COS 对象的目录前缀
            
        Returns:
            COS 图片 URL
        """
        if not image_data or not image_data.is_valid():
            logger.warning("图片数据无效")
            return None
        
        try:
            # 1. 获取图片字节数据
            if image_data.data_type == DataType.BYTES:
                image_bytes = image_data.bytes
            elif image_data.data_type == DataType.DATA_URL:
                image_bytes = image_data.get_image_bytes()
            elif image_data.data_type == DataType.URL:
                # 下载图片
                response = await self.http_client.get(image_data.url)   # type: ignore
                if response.status_code != 200:
                    logger.error(
                        "下载图片失败: url=%s, status=%s, body=%r",
                        image_data.url, response.status_code,
                        response.text[:200] if response.text else "",
                    )
                    return image_data.url  # 降级：直接返回原始 URL
                image_bytes = response.content
            else:
                logger.error(f"未知的数据类型: {image_data.data_type}")
                return None
            
            if not image_bytes:
                logger.error("图片字节数据为空")
                return None
            
            # 2. 生成文件名
            extension = image_data.get_file_extension()
            file_name = f"{folder}/{uuid.uuid4()}{extension}"
            
            # 3. 上传到 COS
            self.client.put_object(
                Bucket=self.bucket,
                Body=BytesIO(image_bytes),
                Key=file_name,
                ContentType=image_data.mime_type
            )
            
            # 4. 返回访问 URL
            cos_url = f"https://{self.bucket}.cos.{self.region}.myqcloud.com/{file_name}"
            logger.info(f"图片上传成功, size={len(image_bytes)} bytes, cosUrl={cos_url}")
            
            return cos_url
        except Exception as e:
            logger.error(
                "上传图片数据到 COS 失败: type=%s, error=%r, url=%s, data_type=%s",
                type(e).__name__, e,
                getattr(image_data, "url", None), image_data.data_type,
            )
            # 如果是 URL 类型，降级返回原始 URL
            if image_data.data_type == DataType.URL:
                return image_data.url
            return None
    
    def use_direct_url(self, image_url: str) -> str:
        """
        直接使用图片 URL（不上传到 COS）
        
        Args:
            image_url: 图片 URL
            
        Returns:
            图片 URL
        """
        return image_url
    
    async def close(self):
        """关闭 HTTP 客户端"""
        await self.http_client.aclose()
