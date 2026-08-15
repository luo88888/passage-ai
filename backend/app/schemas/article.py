"""
文章相关请求/响应模型
"""

from typing import Any, Optional, List
from pydantic import BaseModel, Field

from app.schemas.common import PageRequest


# ==================== 请求模型 ====================
class ArticleCreateRequest(BaseModel):
    """创建文章请求"""

    topic: str = Field(..., min_length=1, description="选题")
    style: Optional[str] = Field(None, description="文章风格（已弃用，保留兼容前端旧请求）")
    genre: Optional[str] = Field(None, description="题材：news/knowledge/product/tutorial/opinion/story")
    language_style: Optional[str] = Field(None, alias="languageStyle", description="语言风格：professional/accessible/humorous/literary/formal")
    word_count: Optional[int] = Field(None, alias="wordCount", ge=200, le=10000, description="目标字数（<=10000，为空走默认 2000）")
    enabled_image_methods: Optional[List[str]] = Field(None, alias="enabledImageMethods", description="允许使用的配图方式列表（为空表示可以使用全部方式）")

    class Config:
        populate_by_name = True


class OptionItem(BaseModel):
    """通用可选项（value=后端枚举值，label=前端展示文案，description=可选说明）"""

    value: str
    label: str
    description: Optional[str] = None
    vip_only: bool = Field(False, alias="vipOnly", description="是否为会员专属（配图方式中高级项为 True）")

    class Config:
        populate_by_name = True


class CreationOptionsVO(BaseModel):
    """创作页可选项：题材 / 语言风格 / 配图方式"""

    genres: List[OptionItem] = Field(default_factory=list, description="题材可选项")
    language_styles: List[OptionItem] = Field(..., alias="languageStyles", description="语言风格可选项")
    image_methods: List[OptionItem] = Field(..., alias="imageMethods", description="配图方式可选项")

    class Config:
        populate_by_name = True


class ArticleQueryRequest(PageRequest):
    """文章查询请求"""
    
    id: Optional[int] = Field(None, description="文章 ID")
    task_id: Optional[str] = Field(None, alias="taskId", description="任务 ID")
    user_id: Optional[int] = Field(None, alias="userId", description="用户 ID")
    topic: Optional[str] = Field(None, description="选题")
    status: Optional[str] = Field(None, description="状态（单状态，与 statuses 二选一）")
    statuses: Optional[List[str]] = Field(None, description="状态列表（多状态筛选，例如“进行中”=过滤 PENDING+PROCESSING，与 status 二选一）")


class TitleOption(BaseModel):
    """标题结果"""

    main_title: str = Field(..., alias="mainTitle")
    sub_title: str = Field(..., alias="subTitle")

    class Config:
        populate_by_name = True


class TitleOptionResult(BaseModel):
    """标题方案结构化输出（标题生成智能体返回，供结构化输出模型使用）"""

    title_options: List[TitleOption] = Field(..., alias="titleOptions")

    class Config:
        populate_by_name = True


class ArticleConfirmTitleRequest(BaseModel):
    """确认标题请求"""

    task_id: str = Field(..., alias="taskId", min_length=1, description="任务 ID")
    selected_main_title: str = Field(..., alias="selectedMainTitle", min_length=1, description="用户选择的主标题")
    selected_sub_title: str = Field(..., alias="selectedSubTitle", min_length=1, description="用户选择的副标题")
    user_description: Optional[str] = Field(None, alias="userDescription", description="用户语言描述")

    class Config:
        populate_by_name = True


class OutlineSection(BaseModel):
    """大纲章节"""

    section: int
    title: str
    points: List[str] = Field(..., description="章节要点")
    word_count: Optional[int] = Field(None, alias="wordCount", description="本章目标字数（由大纲生成/用户编辑，驱动正文逐章字数）")

    class Config:
        populate_by_name = True


class ArticleConfirmOutlineRequest(BaseModel):
    """确认大纲请求，传用户编辑后的完整大纲"""

    task_id: str = Field(..., alias="taskId", min_length=1, description="任务 ID")
    outline: List[OutlineSection] = Field(..., alias="outline", description="用户选择的大纲")

    class Config:
        populate_by_name = True


class ArticleAiModifyOutlineRequest(BaseModel):
    """AI 修改大纲请求，传修改建议"""

    task_id: str = Field(..., alias="taskId", min_length=1, description="任务 ID")
    modify_suggestion: str = Field(..., alias="modifySuggestion", description="用户的修改建议")

    class Config:
        populate_by_name = True


# ==================== 响应模型 ====================


class ResearchArticleVO(BaseModel):
    """单条信息采集结果（新闻/文章摘要，对应 information_collector.schemas.NewsArticleSummary）"""

    title: str = Field(..., description="文章标题")
    url: str = Field(..., description="文章原始链接")
    summary: str = Field(..., description="基于全文内容的摘要")
    publish_time: Optional[str] = Field(None, alias="publishTime", description="发布时间")
    source: Optional[str] = Field(None, description="来源媒体")
    author: Optional[str] = Field(None, description="作者/机构")
    tags: List[str] = Field(default_factory=list, description="标签")

    class Config:
        populate_by_name = True


class ResearchDataVO(BaseModel):
    """信息采集结果（对应 article.researchData JSON 列 / RESEARCH_COMPLETE SSE 载荷）"""

    requirement: Optional[str] = Field(None, description="原始信息需求")
    search_queries_used: List[str] = Field(default_factory=list, alias="searchQueriesUsed", description="实际使用的搜索词")
    articles: List[ResearchArticleVO] = Field(default_factory=list, description="相关新闻条目")

    class Config:
        populate_by_name = True


class ArticleVO(BaseModel):
    """文章视图对象"""
    
    id: int
    task_id: str = Field(..., alias="taskId")
    user_id: int = Field(..., alias="userId")
    topic: str
    user_description: Optional[str] = Field(None, alias="userDescription")
    style: Optional[str] = None
    genre: Optional[str] = None
    language_style: Optional[str] = Field(None, alias="languageStyle")
    word_count: Optional[int] = Field(None, alias="wordCount")
    main_title: Optional[str] = Field(None, alias="mainTitle")
    sub_title: Optional[str] = Field(None, alias="subTitle")
    title_options: Optional[List[TitleOption]] = Field(None, alias="titleOptions")
    outline: Optional[List[Any]] = None
    content: Optional[str] = None
    full_content: Optional[str] = Field(None, alias="fullContent")
    research_data: Optional[ResearchDataVO] = Field(None, alias="researchData", description="信息采集结果（结构化）")
    cover_image: Optional[str] = Field(None, alias="coverImage")
    images: Optional[List[Any]] = None
    status: str
    phase: Optional[str] = None
    error_message: Optional[str] = Field(None, alias="errorMessage")
    create_time: str = Field(..., alias="createTime")
    completed_time: Optional[str] = Field(None, alias="completedTime")
    update_time: str = Field(..., alias="updateTime")
    
    
    class Config:
        populate_by_name = True


class TitleResult(BaseModel):
    """标题结果"""

    main_title: str = Field(..., alias="mainTitle")
    sub_title: str = Field(..., alias="subTitle")

    class Config:
        populate_by_name = True


class OutlineResult(BaseModel):
    """大纲结果"""

    sections: List[OutlineSection]


class ImageRequirement(BaseModel):
    """配图需求"""

    position: int = Field(..., description="图片序号，1, 2, 3...递增")   # 图片在文章中的序号
    type: str = Field(..., description="类型：cover/section/inline")       # cover/section/inline
    section_title: str = Field(..., alias="sectionTitle")
    keywords: str = Field(..., description="图库搜索关键词") # 图库搜索关键词
    # ImageMethodEnum
    image_source: str = Field(..., alias="imageSource", description="图片来源")
    prompt: str = Field(..., description="AI 生图提示词")
    # 正文中的占位符标记，图文合并时定位插入点
    placeholder_id: str = Field(..., alias="placeholderId", description="占位符ID, 原文中的完整字面量")

    class Config:
        populate_by_name = True


class Agent4Result(BaseModel):
    """智能体4（配图）返回结果"""

    image_requirements: List[ImageRequirement] = Field(..., alias="imageRequirements")

    class Config:
        populate_by_name = True


class ImageResult(BaseModel):
    """配图结果"""

    position: int
    url: str
    method: str
    keywords: str
    section_title: str = Field(..., alias="sectionTitle")
    description: str
    placeholder_id: str = Field(..., alias="placeholderId", description="占位符ID")

    class Config:
        populate_by_name = True


class ArticleState(BaseModel):
    """文章生成状态（LangGraph 图状态 + 智能体共享状态，统一 Pydantic 模型）

    字段命名统一 snake_case（LangGraph channel 名 = 字段名，持久化/恢复不变化）；
    结构字段（title/title_options/outline/image_requirements/images）为 Pydantic 模型，
    节点返回图状态时用 model_dump(by_alias=True) 序列化为可 JSON 持久化 dict，
    与既有 checkpoint / SSE 序列化惯例保持一致。
    """

    # ==================== 基础元信息 ====================
    task_id: Optional[str] = None
    topic: Optional[str] = None                                    # 用户指定选题
    style: Optional[str] = None                                    # 文章风格（已弃用，保留兼容）

    # ==================== 创作控制输入 ====================
    genre: Optional[str] = None                                    # 题材：news/knowledge/product/tutorial/opinion/story
    language_style: Optional[str] = None                           # 语言风格：professional/accessible/humorous/literary/formal
    word_count: Optional[int] = None                               # 目标字数（<=10000，None 走默认 2000）
    collected_news: Optional[str] = None                           # 新闻题材信息采集产物（供提示词注入的摘要文本）

    # ==================== 交互式流程输入 ====================
    user_description: Optional[str] = None                         # 用户补充描述
    title_options: Optional[List[TitleOption]] = None              # 标题方案
    enabled_image_methods: Optional[List[str]] = None              # 可使用的配图方式
    modify_suggestion: Optional[str] = None                        # AI 修改大纲的用户建议（路由注入，节点消费后清空）

    # ==================== 各智能体产出 ====================
    title: Optional[TitleResult] = None                            # 确认后的标题
    outline: Optional[OutlineResult] = None                        # 大纲
    content: Optional[str] = None                                  # 正文（agent3 原文，含 <imageN> 占位标签）
    image_requirements: Optional[List[ImageRequirement]] = None    # 配图需求
    images: Optional[List[ImageResult]] = None                     # 配图结果
    cover_image: Optional[str] = None
    full_content: Optional[str] = None                             # 图文合并最终结果
