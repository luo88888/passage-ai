import base64
from enum import Enum

from pydantic import BaseModel, Field
from typing import Optional


class ImageRequest(BaseModel):
    """图片请求对象"""

    keyword: Optional[str] = Field(None, description="搜索关键词（用于图库检索）")
    prompt: Optional[str] = Field(None, description="生图提示词（用于 AI 生图")
    position: Optional[int] = Field(None, description="图片位置序号")
    type: Optional[str] = Field(None, description="图片类型（cover/section）")
    aspect_ratio: Optional[str] = Field(None, description="宽高比（如 16:9，1:1）")
    style: Optional[str] = Field(None, description="图片风格描述")


    def get_effective_param(self, is_ai_generated: bool) -> str:
        """AI 生图优先使用 prompt，图库检索使用 keywords"""
        if is_ai_generated:
            return self.prompt if self.prompt else self.keyword or ""
        return self.keyword if self.keyword else self.prompt or ""


class DataType(str, Enum):
    """数据类型枚举

    - BYTES: 内存中的二进制 bytes，Mermaid 图表 / Nano / Banana 生成图
    - URL: 图片 URL，外部图片链接
    - DATA_URL: base64 编码的小图/缩略图
    """
    BYTES = "BYTES"         # 字节数据（Mermaid、Nano、Banana 等）
    URL = "URL"             # 外部 URL
    DATA_URL = "DATA_URL"   # base64 data URL，适合 小图标、缩略图


class ImageData:
    """图片数据封装类"""

    def __init__(
        self,
        bytes_data: Optional[bytes] = None,
        url: Optional[str] = None,
        mime_type: Optional[str] = None,
        data_type: Optional[DataType] = None      
    ):
        self.bytes = bytes_data     # 在 BYTES 类型下有意义
        self.url = url              # 在 URL/DATA_URL 类型下有意义
        self.mime_type = mime_type or "image/png"
        self.data_type = data_type  # 当前数据类型（BYTES/URL/DATA_URL）

    @classmethod
    def from_url(cls, url: Optional[str]) -> Optional["ImageData"]:
        """从 URL 创建 ImageData"""
        if not url:
            return None
        if url.startswith("data:"):  # base64 data URL
            return cls.from_data_url(url)
        return cls(url=url, data_type=DataType.URL)

    @classmethod
    def from_data_url(cls, data_url: str) -> Optional["ImageData"]:
        """从 base64 data URL 创建 ImageData"""
        if not data_url or not data_url.startswith("data:"):
            return None
        
        # 解析 data URL 格式: data:image/png;base64,xxxxx
        mime_type = "image/png"
        mime_end = data_url.find(";")
        if mime_end > 5:
            mime_type = data_url[5:mime_end]
        
        return cls(url=data_url, mime_type=mime_type, data_type=DataType.DATA_URL)

    @classmethod
    def from_bytes(cls, bytes_data: bytes, mime_type: str = "image/png") -> Optional["ImageData"]:
        """从字节数据创建 ImageData"""
        if not bytes_data:
            return None
        return cls(bytes_data=bytes_data, mime_type=mime_type, data_type=DataType.BYTES)

    def is_valid(self) -> bool:
        """检查图片数据是否有效"""
        if self.data_type == DataType.BYTES:
            return self.bytes is not None and len(self.bytes) > 0
        elif self.data_type in [DataType.URL, DataType.DATA_URL]:
            return self.url is not None and len(self.url) > 0
        return False

    def get_file_extension(self) -> str:
        """获取文件扩展名"""
        if not self.mime_type:
            return ".png"
        mime_lower = self.mime_type.lower()
        if mime_lower in ["image/jpeg", "image/jpg"]:
            return ".jpg"
        elif mime_lower == "image/svg+xml":
            return ".svg"
        return ".png"

    def get_image_bytes(self) -> Optional[bytes]:
        """获取图片字节数据（如果是 data URL，会解码 base64）"""
        if self.data_type == DataType.BYTES:
            return self.bytes
        
        if self.data_type == DataType.DATA_URL and self.url:
            # 解析 base64 data URL
            base64_start = self.url.find(",")
            if base64_start > 0:
                base64_data = self.url[base64_start + 1:]
                return base64.b64decode(base64_data)
        
        return None