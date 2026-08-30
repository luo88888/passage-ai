"""
Mermaid 流程图生成服务
"""
# NOTE: 依赖：npm install -g @mermaid-js/mermaid-cli

from pathlib import Path
import subprocess
import tempfile
from typing import Optional

from app.config import settings
from app.constants.article import ArticleConstant
from app.models.enums import ImageMethodEnum
from app.schemas.image import ImageData, ImageRequest
from app.services.images.image_search_service import BaseImageSearchService
from app.utils.logger import logger


class MermaidService(BaseImageSearchService):
    """Mermaid 流程图生成服务"""

    name = "MERMAID"
    description = "适合流程图、架构图、时序图、关系图、甘特图等结构化图表"
    usage = "在 prompt 字段生成完整的 Mermaid 代码（如流程图、架构图）。keywords 留空。"
    is_ai_generate = True
    
    def __init__(self):
        self.cli_command = settings.mermaid_cli_command
        self.background_color = settings.mermaid_background_color
        self.output_format = settings.mermaid_output_format
        self.width = settings.mermaid_width
        self.timeout = settings.mermaid_timeout / 1000
    
    async def get_image_data(self, request: ImageRequest) -> Optional[ImageData]:
        mermaid_code = request.get_effective_param(True)
        return await self.generate_diagram_data(mermaid_code)
    
    async def generate_diagram_data(self, mermaid_code: str) -> Optional[ImageData]:
        """生成 Mermaid 图表数据"""
        temp_input_file = None
        temp_output_file = None
        
        try:
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.mmd', delete=False, encoding='utf-8'
            ) as f:
                f.write(mermaid_code)
                temp_input_file = f.name
            
            with tempfile.NamedTemporaryFile(
                suffix=f".{self.output_format}", delete=False
            ) as f:
                temp_output_file = f.name
            
            # 调用 mmdc 命令渲染
            cmd = [
                self.cli_command, '-i', temp_input_file, '-o', temp_output_file,
                '-b', self.background_color, '-w', str(self.width)
            ]
            # HACK: 同步阻塞，阻塞事件循环
            result = subprocess.run(cmd, timeout=self.timeout, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Mermaid 转换失败: {result.stderr}")
            
            with open(temp_output_file, 'rb') as f:
                image_bytes = f.read()
            
            return ImageData.from_bytes(image_bytes, self._get_mime_type())
        except Exception as e:
            logger.error(f"Mermaid 图表生成异常: {e}")
            return None
        finally:
            if temp_input_file:
                Path(temp_input_file).unlink(missing_ok=True)
            if temp_output_file:
                Path(temp_output_file).unlink(missing_ok=True)
    
    def is_available(self) -> bool:
        """检查 mmdc 命令是否可用"""
        try:
            result = subprocess.run(
                [self.cli_command, '--version'], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def get_method(self) -> ImageMethodEnum:
        return ImageMethodEnum.MERMAID

    def get_fallback_image(self, position: int) -> str:
        return ArticleConstant.PICSUM_URL_TEMPLATE.format(position)

    def _get_mime_type(self) -> str:
        """根据输出格式获取 MIME 类型"""
        format_lower = self.output_format.lower()
        if format_lower == "png":
            return "image/png"
        elif format_lower == "svg":
            return "image/svg+xml"
        elif format_lower == "pdf":
            return "application/pdf"
        else:
            return "image/png"


if __name__ == '__main__':
    service = MermaidService()
    print(f"avaliable: {service.is_available()}")