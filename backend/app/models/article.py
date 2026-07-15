"""Article ORM 模型"""

from sqlalchemy import Column, BigInteger, String, DateTime, SmallInteger, Text, Integer
from sqlalchemy.sql import func

from app.database import Base


class Article(Base):
    """文章表"""
    
    __tablename__ = "article"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="id")
    task_id = Column("taskId", String(64), nullable=False, unique=True, comment="任务ID（UUID）")
    user_id = Column("userId", BigInteger, nullable=False, comment="用户ID")
    topic = Column(String(500), nullable=False, comment="选题")
    main_title = Column("mainTitle", String(200), nullable=True, comment="主标题")
    sub_title = Column("subTitle", String(300), nullable=True, comment="副标题")
    outline = Column(Text, nullable=True, comment="大纲（JSON格式）")
    content = Column(Text, nullable=True, comment="正文（Markdown格式）")
    full_content = Column("fullContent", Text, nullable=True, comment="完整图文（Markdown格式，含图片）")
    cover_image = Column("coverImage", String(512), nullable=True, comment="封面图 URL")
    images = Column(Text, nullable=True, comment="配图列表（JSON数组）")
    status = Column(String(20), nullable=False, default="PENDING", comment="状态")
    error_message = Column("errorMessage", Text, nullable=True, comment="错误信息")
    create_time = Column("createTime", DateTime, nullable=False, default=func.now(), comment="创建时间")
    completed_time = Column("completedTime", DateTime, nullable=True, comment="完成时间")
    update_time = Column("updateTime", DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment="更新时间")
    is_delete = Column("isDelete", SmallInteger, nullable=False, default=0, comment="是否删除")
    style = Column(String(20), nullable=True, comment="文章风格：tech/emotional/educational/humorous（已弃用，保留兼容存量数据）")
    user_description = Column("userDescription", Text, nullable=True, comment="用户补充描述")
    enabled_image_methods = Column("enabledImageMethods", Text, nullable=True, comment="允许的配图方式列表（JSON格式）")
    title_options = Column("titleOptions", Text, nullable=True, comment="标题方案列表（JSON格式）")
    genre = Column("genre", String(20), nullable=True, comment="题材：news/knowledge/product/tutorial/opinion/story")
    language_style = Column("languageStyle", String(20), nullable=True, comment="语言风格：professional/accessible/humorous/literary/formal")
    word_count = Column("wordCount", Integer, nullable=True, comment="目标字数（<=10000）")
    phase = Column(
        String(40),
        nullable=False,
        default="PENDING",
        comment="阶段：PENDING/TITLE_GENERATING/TITLE_SELECTING/OUTLINE_GENERATING/OUTLINE_EDITING/CONTENT_GENERATING"
    )
