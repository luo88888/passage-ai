"""
枚举类型定义
"""

from enum import Enum


class ArticleStatusEnum(str, Enum):
    """文章状态枚举"""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ImageMethodEnum(str, Enum):
    """配图方式枚举"""

    PEXELS = "PEXELS"
    PICSUM = "PICSUM"


class SseMessageTypeEnum(str, Enum):
    """SSE 消息类型枚举"""

    AGENT1_COMPLETE = "AGENT1_COMPLETE"     # 智能体1完成（生成标题）
    AGENT2_STREAMING = "AGENT2_STREAMING"   # 智能体2流式输出（大纲）
    AGENT2_COMPLETE = "AGENT2_COMPLETE"     # 智能体2完成
    AGENT3_STREAMING = "AGENT3_STREAMING"   # 智能体3流式输出（正文）
    AGENT3_COMPLETE = "AGENT3_COMPLETE"     # 智能体3流式输出（正文）
    AGENT4_COMPLETE = "AGENT4_COMPLETE"     # 智能体4完成（配图需求）
    IMAGE_COMPLETE = "IMAGE_COMPLETE"       # 单章配图完成
    AGENT5_COMPLETE = "AGENT5_COMPLETE"     # 智能体5完成
    MERGE_COMPLETE = "MERGE_COMPLETE"       # 图片合成完成
    ALL_COMPLETE = "ALL_COMPLETE"           # 全部完成
    ERROR = "ERROR"                         # 错误

    def get_streaming_prefix(self) -> str:
        """获取流式输出消息前缀"""
        return f"{self.value}:"