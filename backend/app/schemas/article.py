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

        

# ==================== 响应模型 ====================

class TitleResult(BaseModel):
    """标题结果"""

    main_title: str = Field(..., alias="mainTitle")
    sub_title: str = Field(..., alias="subTitle")

    class Config:
        populate_by_name = True


class OutlineSection(BaseModel):
    """大纲章节"""

    section: int
    title: str
    points: List[str]


class OutlineResult(BaseModel):
    """大纲结果"""

    sections: List[OutlineSection]


class ImageRequirement(BaseModel):
    """配图需求"""

    position: int
    type: str
    section_title: str = Field(..., alias="sectionTitle")
    keywords: str

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

    class Config:
        populate_by_name = True


class ArticleState:
    """文章生成状态，智能体共享"""

    def __init__(self):
        self.task_id: Optional[str] = None
        self.topic: Optional[str] = None                                    # 用户指定
        self.title_options: Optional[List[TitleOption]] = None
        self.title: Optional[TitleResult] = None                            # 智能体1输出
        self.outline: Optional[OutlineResult] = None                        # 智能体2输出
        self.content: Optional[str] = None                                  # 智能体3输出
        self.image_requirements: Optional[List[ImageRequirement]] = None    # 智能体4输出
        self.images: Optional[List[ImageResult]] = None                     # 智能体5输出
        self.cover_image: Optional[str] = None
        self.full_content: Optional[str] = None                             # 图文合并的最终结果