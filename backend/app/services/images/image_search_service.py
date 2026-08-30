"""
图片服务抽象基类 — 定义图片获取的统一接口，便于扩展多种图片来源。
"""
from abc import ABC, abstractmethod
from typing import Optional


from app.models.enums import ImageMethodEnum
from app.schemas.image import ImageRequest, ImageData


class BaseImageSearchService(ABC):
    """图片服务抽象基类。

    所有图片获取服务（Pexels、Mermaid、Iconify 等）均继承此类，
    必须实现 get_image_data、get_method、get_fallback_image 三个抽象方法。
    可选实现 is_available 方法。

    数据流:
        ImageRequest → get_image_data() → ImageData → FileService.upload_image_data() → URL

    子类实现约定:
        - 图库检索类（Pexels / Iconify / EmojiPack）：从 ImageRequest 取 keywords，
          调用外部 API 搜索，返回 ImageData.from_url(url)。
        - AI 生图类（Mermaid / SvgDiagram）：从 ImageRequest 取 prompt，
          本地生成或调用 LLM，返回 ImageData.from_bytes(...)。
    """

    # ==================== 抽象方法（子类必须实现） ====================

    @abstractmethod
    async def get_image_data(self, request: ImageRequest) -> Optional[ImageData]:
        """根据请求获取图片数据。

        这是外部调用的唯一入口。子类必须实现此方法，根据自身图片来源
        （API 检索 / AI 生成 / 本地渲染）返回对应的 ImageData。

        Args:
            request: 图片请求对象，包含 keywords、prompt、position、type 等字段。
                图库检索类使用 request.keywords，AI 生图类使用 request.prompt。
                可通过 request.get_effective_param(is_ai_generated) 自动选择。

        Returns:
            包含图片字节或 URL 的 ImageData 对象；获取失败时返回 None，
        """
        pass

    @abstractmethod
    def get_method(self) -> ImageMethodEnum:
        """返回该服务对应的图片方式枚举值。

        Returns:
            ImageMethodEnum 枚举成员（如 PEXELS、MERMAID）。
        """
        pass

    @abstractmethod
    def get_fallback_image(self, position: int) -> str:
        """获取降级兜底图片 URL。

        当服务不可用或 API 调用失败时，由策略器调用此方法获取兜底图。
        通常返回 PICSUM 随机图片 URL。

        Args:
            position: 图片在文章中的位置序号（1 为封面图），用于生成不同的随机图。

        Returns:
            兜底图片的 URL 字符串。
        """
        pass

    # ==================== 可选覆写 ====================

    def is_available(self) -> bool:
        """检查该服务当前是否可用。

        子类可覆写以实现健康检查（如 MermaidService 检查 mmdc CLI 是否安装）。

        Returns:
            True 表示服务可用，False 表示不可用。
        """
        return True

    # ==================== 元数据（用于构建给 AI 的配图提示词） ====================
    # 注意：以下为带类型标注的类属性，子类以类属性直接覆写
    # （如 `name = "PEXELS"`），供 Prompt 类在构建配图提示词时按属性读取。

    name: str
    """方式标识，与 ImageMethodEnum.value 一致（如 "PEXELS"），非 UI 标签。

    供 Prompt 类构建配图提示词时引用；与 get_method().value 保持一致。
    """

    description: str
    """一句话适用场景说明（如 "适合真实场景、产品照片..."）。

    供 Prompt 类拼出 "可用配图方式" 列表时使用。
    """

    usage: str
    """详细使用指南（多行，可含示例）。

    供 Prompt 类拼出 "配图方式使用指南" 时使用；用于指导 LLM
    如何为该方式填写 keywords / prompt 等字段。
    """

    is_ai_generate: bool
    """是否为 AI 生图方式。

    与 get_method().is_ai_generated() 保持一致，显式声明便于提示词构建器读取。
    """
