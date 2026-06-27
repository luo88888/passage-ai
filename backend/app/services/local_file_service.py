"""本地文件存储服务（临时替代腾讯云 COS）"""

import uuid
import shutil
from pathlib import Path
from typing import Optional
import mimetypes

import httpx

from app.config import settings
from app.schemas.image import ImageData, DataType
from app.utils.logger import logger
from app.utils.path_tool import get_abs_path


# 图片保存的根目录（相对于 backend/）
IMAGES_DIR = get_abs_path() / "static" / "images"


class LocalFileService:
    """本地文件存储服务 — 与 CosService 接口一致，可直接替换"""

    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        # 确保目录存在
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    async def upload_image_data(
        self,
        image_data: ImageData,
        folder: str
    ) -> Optional[str]:
        """
        保存图片数据到本地文件系统

        Args:
            image_data: 图片数据
            folder: 子目录名

        Returns:
            可访问的图片 URL（绝对路径）
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
                response = await self.http_client.get(image_data.url)  # type: ignore
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

            # 2. 生成文件名并写入磁盘
            extension = image_data.get_file_extension()
            file_name = f"{uuid.uuid4()}{extension}"
            # 如 folder="pexels" → static/images/pexels/
            target_dir = IMAGES_DIR / folder
            target_dir.mkdir(parents=True, exist_ok=True)
            file_path = target_dir / file_name
            file_path.write_bytes(image_bytes)

            # 3. 返回访问 URL
            url = f"{settings.static_base_url}/static/images/{folder}/{file_name}"
            logger.info(
                "图片保存成功, size=%d bytes, path=%s, url=%s",
                len(image_bytes), file_path, url,
            )
            return url
        except Exception as e:
            logger.error(
                "保存图片到本地失败: type=%s, error=%r, url=%s, data_type=%s",
                type(e).__name__, e,
                getattr(image_data, "url", None), image_data.data_type,
            )
            if image_data.data_type == DataType.URL:
                return image_data.url
            return None

    def use_direct_url(self, image_url: str) -> str:
        """直接使用原始 URL（保留接口兼容）"""
        return image_url

    async def close(self):
        """关闭 HTTP 客户端"""
        await self.http_client.aclose()
