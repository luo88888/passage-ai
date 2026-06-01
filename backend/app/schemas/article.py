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
    style: Optional[str] = Field(None, description="文章风格：tech/emotional/educational/humorous")
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
    """创作页可选项：文章风格 / 配图方式"""

    styles: List[OptionItem]
    image_methods: List[OptionItem] = Field(..., alias="imageMethods")

    class Config:
        populate_by_name = True


class ArticleQueryRequest(PageRequest):
    """文章查询请求"""
    
    id: Optional[int] = Field(None, description="文章 ID")
    task_id: Optional[str] = Field(None, alias="taskId", description="任务 ID")
    user_id: Optional[int] = Field(None, alias="userId", description="用户 ID")
    topic: Optional[str] = Field(None, description="选题")
    status: Optional[str] = Field(None, description="状态")


class TitleOption(BaseModel):
    """标题结果"""

    main_title: str = Field(..., alias="mainTitle")
    sub_title: str = Field(..., alias="subTitle")

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
    points: List[str]


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


class ArticleVO(BaseModel):
    """文章视图对象"""
    
    id: int
    task_id: str = Field(..., alias="taskId")
    user_id: int = Field(..., alias="userId")
    topic: str
    user_description: Optional[str] = Field(None, alias="userDescription")
    style: Optional[str] = None
    main_title: Optional[str] = Field(None, alias="mainTitle")
    sub_title: Optional[str] = Field(None, alias="subTitle")
    title_options: Optional[List[TitleOption]] = Field(None, alias="titleOptions")
    outline: Optional[List[Any]] = None
    content: Optional[str] = None
    full_content: Optional[str] = Field(None, alias="fullContent")
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

    position: int
    type: str
    section_title: str = Field(..., alias="sectionTitle")
    keywords: str
    image_source: str = Field(..., alias="imageSource", description="图片来源")
    prompt: str = Field(..., description="AI 生图提示词")
    placeholder_id: str = Field(..., alias="placeholderId", description="占位符ID")

    class Config:
        populate_by_name = True


class Agent4Result(BaseModel):
    """智能体4返回结果"""

    content_with_placeholders: str = Field(..., alias="contentWithPlaceholders")
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


class ArticleState:
    """文章生成状态，智能体共享"""

    def __init__(self):
        self.task_id: Optional[str] = None
        self.topic: Optional[str] = None                                    # 用户指定
        self.title: Optional[TitleResult] = None                            # 智能体1输出
        self.outline: Optional[OutlineResult] = None                        # 智能体2输出
        self.content: Optional[str] = None                                  # 智能体3输出
        self.image_requirements: Optional[List[ImageRequirement]] = None    # 智能体4输出
        self.images: Optional[List[ImageResult]] = None                     # 智能体5输出
        self.cover_image: Optional[str] = None
        self.full_content: Optional[str] = None                             # 图文合并的最终结果
        self.enabled_image_methods: Optional[List[str]] = None              # 可使用的配图方式
        self.style: Optional[str] = None                                    # 文章风格
        self.title_options: Optional[List[TitleOption]] = None              # 标题方案
        self.user_description: Optional[str] = None                         # 用户补充描述
