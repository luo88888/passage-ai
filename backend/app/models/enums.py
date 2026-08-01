"""
枚举类型定义
"""

from decimal import Decimal
from enum import Enum
from typing import Optional


class ArticleStatusEnum(str, Enum):
    """文章状态枚举"""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


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

    TITLE_GENERATED = "TITLE_GENERATED"    # 标题生成完成，等待用户选择
    OUTLINE_GENERATED = "OUTLINE_GENERATED" # 大纲生成完成，等待用户编辑
    AI_MODIFY_OUTLINE_COMPLETE = "AI_MODIFY_OUTLINE_COMPLETE"  # AI 修改大纲完成
    AI_MODIFY_OUTLINE_FAILED = "AI_MODIFY_OUTLINE_FAILED"     # AI 修改大纲失败
    RESEARCH_COMPLETE = "RESEARCH_COMPLETE"   # 信息采集完成（新闻题材）

    def get_streaming_prefix(self) -> str:
        """获取流式输出消息前缀"""
        return f"{self.value}:"


class ImageMethodEnum(str, Enum):
    """配图方式枚举

    每个成员形如 (value, label, description)：
    - value: 与策略器/数据库约定的英文标识，保持向后兼容（ImageMethodEnum("PEXELS")、e.value 等用法不受影响）
    - label: 前端展示用中文名
    - description: 可选简短说明
    """

    label: str
    description: str

    PEXELS = "PEXELS", "Pexels 真实图", "高质量真实摄影图，适合封面与场景配图"
    NANO_BANANA = "NANO_BANANA", "Nano Banana", "AI 创意插画，适合抽象概念与信息图表"
    ZHIPU = "ZHIPU", "智谱 GLM-Image", "AI 生图，擅长文字密集的商业海报/科普插画/多格图画/人物/风景/动植物"
    MERMAID = "MERMAID", "Mermaid 流程图", "代码生成流程图/时序图等结构化图表"
    ICONIFY = "ICONIFY", "Iconify 图标", "海量开源图标库，适合图标点缀"
    EMOJI_PACK = "EMOJI_PACK", "表情包", "表情图，增加趣味性"
    SVG_DIAGRAM = "SVG_DIAGRAM", "SVG 图表", "AI 生成 SVG 矢量图，适合示意图"
    PICSUM = "PICSUM", "Picsum 兜底图", "降级专用随机图（不在创作选项中暴露）"

    def __new__(cls, value: str, label: str = "", description: str = ""):
        # str 枚举需用 __new__ 构造成员，显式设置 _value_ 以兼容元组写法
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.label = label
        obj.description = description
        return obj

    def is_ai_generated(self) -> bool:
        """是否为 AI 生成图片"""
        return self in [
            ImageMethodEnum.NANO_BANANA,
            ImageMethodEnum.ZHIPU,
            ImageMethodEnum.MERMAID,
            ImageMethodEnum.SVG_DIAGRAM
        ]

    def is_fallback(self) -> bool:
        """是否为降级方案"""
        return self in [
            ImageMethodEnum.PICSUM
        ]

    @classmethod
    def get_default_search_method(cls):
        return cls.PEXELS

    @classmethod
    def get_fallback_method(cls):
        return cls.PICSUM


class ArticleStyleEnum(str, Enum):
    """文章风格枚举（已弃用，保留以兼容存量数据）

    @deprecated 已被 ArticleGenreEnum + ArticleLanguageStyleEnum 取代，新流程不再写入/读取 style 列。
    每个成员形如 (value, label, description)，value 保持向后兼容。
    创作页"默认"项由前端写死，对应 style=null（后端走通用爆款风格），故此处不含"默认"。
    """

    label: str
    description: str

    TECH = "tech", "科技风", "语言专业严谨，重数据与事实"
    EMOTIONAL = "emotional", "情感风", "语言温暖细腻，注重共鸣"
    EDUCATIONAL = "educational", "教育风", "深入浅出，结构清晰便于学习"
    HUMOROUS = "humorous", "幽默风", "轻松活泼，善用流行语与比喻"

    def __new__(cls, value: str, label: str = "", description: str = ""):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.label = label
        obj.description = description
        return obj

    @classmethod
    def is_valid(cls, value: Optional[str]) -> bool:
        """校验是否为有效的风格值"""
        if not value:
            return True  # 允许为空
        return value in [e.value for e in cls]


class ArticleGenreEnum(str, Enum):
    """文章题材枚举（决定全文基调、提示词，以及是否走信息采集）

    每个成员形如 (value, label, description)，value 保持向后兼容。
    创作页"默认"项由前端写死，对应 genre=null（后端走通用爆款基调），故此处不含"默认"。
    仅 NEWS 题材在 bootstrap 后触发信息采集节点。
    """

    label: str
    description: str

    NEWS = "news", "新闻", "聚焦时事热点，强调时效与事实来源"
    KNOWLEDGE = "knowledge", "知识科普", "讲解专业概念，深入浅出传播知识"
    PRODUCT = "product", "产品介绍", "突出卖点与价值，引导用户理解产品"
    TUTORIAL = "tutorial", "教程指南", "按步骤讲解操作方法，便于上手实操"
    OPINION = "opinion", "观点评论", "表达独立观点，有论证有立场"
    STORY = "story", "故事叙事", "以叙事打动读者，重情节与代入"

    def __new__(cls, value: str, label: str = "", description: str = ""):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.label = label
        obj.description = description
        return obj

    @classmethod
    def is_valid(cls, value: Optional[str]) -> bool:
        """校验是否为有效的题材值"""
        if not value:
            return True  # 允许为空
        return value in [e.value for e in cls]

    @classmethod
    def is_news(cls, value: Optional[str]) -> bool:
        """是否为新闻题材（触发信息采集）"""
        return value == cls.NEWS.value


class ArticleLanguageStyleEnum(str, Enum):
    """语言风格枚举（附加到正文/大纲提示词的语气特质，取代旧文章风格 style）

    每个成员形如 (value, label, description)，value 保持向后兼容。
    创作页"默认"项由前端写死，对应 language_style=null（后端走通用语气），故此处不含"默认"。
    """

    label: str
    description: str

    PROFESSIONAL = "professional", "专业严谨", "用词规范、术语准确、逻辑严密"
    ACCESSIBLE = "accessible", "通俗易懂", "口语化表达、少术语、贴近大众"
    HUMOROUS = "humorous", "活泼幽默", "轻松风趣、善用比喻与网络梗"
    LITERARY = "literary", "文艺抒情", "语言优美、重意境与情感渲染"
    FORMAL = "formal", "正式客观", "中立克制、陈述事实、避免主观"

    def __new__(cls, value: str, label: str = "", description: str = ""):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.label = label
        obj.description = description
        return obj

    @classmethod
    def is_valid(cls, value: Optional[str]) -> bool:
        """校验是否为有效的语言风格值"""
        if not value:
            return True  # 允许为空
        return value in [e.value for e in cls]


class ArticlePhaseEnum(str, Enum):
    """文章阶段枚举"""

    PENDING = "PENDING"                         # 待处理
    TITLE_GENERATING = "TITLE_GENERATING"       # 阶段1：生成标题
    TITLE_SELECTING = "TITLE_SELECTING"         # 阶段2：选择标题
    OUTLINE_GENERATING = "OUTLINE_GENERATING"   # 阶段3：生成大纲
    OUTLINE_EDITING = "OUTLINE_EDITING"         # 阶段4：编辑大纲
    CONTENT_GENERATING = "CONTENT_GENERATING"   # 阶段5：生成正文

    def can_transition_to(self, target_phase: "ArticlePhaseEnum") -> bool:
        """校验是否可流转到目标阶段"""
        transitions = {
            ArticlePhaseEnum.PENDING: {ArticlePhaseEnum.TITLE_GENERATING},
            ArticlePhaseEnum.TITLE_GENERATING: {ArticlePhaseEnum.TITLE_SELECTING},
            ArticlePhaseEnum.TITLE_SELECTING: {ArticlePhaseEnum.OUTLINE_GENERATING},
            ArticlePhaseEnum.OUTLINE_GENERATING: {ArticlePhaseEnum.OUTLINE_EDITING},
            ArticlePhaseEnum.OUTLINE_EDITING: {ArticlePhaseEnum.CONTENT_GENERATING},
            ArticlePhaseEnum.CONTENT_GENERATING: set(),
        }
        return target_phase in transitions.get(self, set())


class PaymentStatusEnum(str, Enum):
    """支付状态枚举"""

    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class ProductTypeEnum(str, Enum):
    """产品类型枚举"""

    VIP_PERMANENT = "VIP_PERMANENT"

    @property
    def description(self) -> str:
        descriptions = {
            ProductTypeEnum.VIP_PERMANENT: "永久会员",
        }
        return descriptions[self]

    @property
    def price(self) -> Decimal:
        prices = {
            ProductTypeEnum.VIP_PERMANENT: Decimal("1.99"),
        }
        return prices[self]
