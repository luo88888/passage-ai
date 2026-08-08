"""
配图相关配置：Pexels / Nano Banana / 智谱 / Mermaid / Iconify / 表情包 / SVG / 腾讯云 COS / 本地存储
"""

from pydantic_settings import BaseSettings


class ImageConfig(BaseSettings):
    """配图服务配置"""

    # Pexels
    pexels_api_key: str

    # 本地文件存储
    static_base_url: str = "http://localhost:8567"

    # Nano Banana / Gemini
    nano_banana_api_key: str
    nano_banana_model: str = "gemini-2.5-flash-image"
    nano_banana_aspect_ratio: str = "16:9"
    nano_banana_image_size: str = "1K"
    nano_banana_output_mime_type: str = "image/png"

    # 智谱 GLM-Image
    zhipu_api_key: str = ""
    zhipu_image_model: str = "cogview-3-flash"
    # cogview-3-flash:  1024x1024、768x1344、864x1152、1344x768、1152x864、1440x720、720x1440
    # glm-image: 1568x1056
    zhipu_image_size: str = "1152x864"
    zhipu_image_max_concurrency: int = 1
    zhipu_image_timeout: int = 120

    # Mermaid
    mermaid_cli_command: str = "mmdc"
    mermaid_background_color: str = "transparent"
    mermaid_output_format: str = "svg"
    mermaid_width: int = 1200
    mermaid_timeout: int = 30000

    # Iconify
    iconify_api_url: str = "https://api.iconify.design"
    iconify_search_limit: int = 10
    iconify_default_height: int = 64
    iconify_default_color: str = ""

    # 表情包
    emoji_pack_search_url: str = "https://cn.bing.com/images/async"
    emoji_pack_suffix: str = "表情包"
    emoji_pack_timeout: int = 10000

    # SVG 示意图
    svg_diagram_default_width: int = 800
    svg_diagram_default_height: int = 600
    svg_diagram_folder: str = "svg-diagrams"

    # SVG 示意图 LLM
    svg_diagram_agent_provider: str = "deepseek"
    svg_diagram_agent_model: str = "deepseek-v4-flash"
    svg_diagram_agent_temperature: float = 0.2
    svg_diagram_agent_thinking: bool = True
    svg_diagram_agent_reasoning_effort: str = "high"
