"""图状态（dict 形态）↔ 智能体状态（class 形态）双向适配

- to_class_state: dict 版 ArticleState（graph/state.py）→ class 版 ArticleState
  （schemas/article.py:195，字段为 Pydantic 模型对象），供现有智能体 run(state) 使用。
- merge_to_dict_state: 智能体就地改完 class state 后，把所有可能产出的字段统一序列化成
  dict 片段，供 LangGraph 节点 return（默认覆盖 reducer 合并回图状态）。

序列化惯例（与现有持久化 / SSE 完成事件保持一致）：
  - title / title_options        → model_dump(by_alias=True)   {"mainTitle","subTitle"}
  - outline                       → OutlineResult.model_dump()（无 alias）
  - image_requirements / images   → model_dump(by_alias=True)
  - 其它标量字段原样返回
"""
from __future__ import annotations

from app.graph.state import ArticleState as DictArticleState
from app.schemas.article import (
    ArticleState as ClassArticleState,
    ImageRequirement,
    ImageResult,
    OutlineResult,
    OutlineSection,
    TitleOption,
    TitleResult,
)


def to_class_state(dict_state: DictArticleState) -> ClassArticleState:
    """dict 版图状态 → class 版智能体状态

    None 字段保持 None。各结构字段用对应 Pydantic 模型重建：
      title(dict)                 -> TitleResult
      title_options(list[dict])    -> list[TitleOption]
      outline(dict)                -> OutlineResult(sections=[OutlineSection,...])
      image_requirements(list[dict]) -> list[ImageRequirement]
      images(list[dict])           -> list[ImageResult]
    """
    state = ClassArticleState()
    state.task_id = dict_state.get("task_id")
    state.topic = dict_state.get("topic")
    state.style = dict_state.get("style")
    state.genre = dict_state.get("genre")
    state.language_style = dict_state.get("language_style")
    state.word_count = dict_state.get("word_count")
    state.collected_news = dict_state.get("collected_news")
    state.user_description = dict_state.get("user_description")
    state.content = dict_state.get("content")
    state.full_content = dict_state.get("full_content")
    state.cover_image = dict_state.get("cover_image")
    state.enabled_image_methods = dict_state.get("enabled_image_methods")

    title_dict = dict_state.get("title")
    state.title = TitleResult(**title_dict) if title_dict else None

    title_options_list = dict_state.get("title_options")
    state.title_options = (
        [TitleOption(**item) for item in title_options_list]
        if title_options_list
        else None
    )

    outline_dict = dict_state.get("outline")
    if outline_dict and outline_dict.get("sections"):
        state.outline = OutlineResult(
            sections=[OutlineSection(**s) for s in outline_dict["sections"]]
        )
    else:
        state.outline = None

    req_list = dict_state.get("image_requirements")
    state.image_requirements = (
        [ImageRequirement(**item) for item in req_list] if req_list else None
    )

    img_list = dict_state.get("images")
    state.images = (
        [ImageResult(**item) for item in img_list] if img_list else None
    )

    return state


def merge_to_dict_state(updated_class_state: ClassArticleState) -> dict:
    """class 版智能体状态（Pydantic） → 可序列化 dict 片段

    返回所有可能被智能体产出的字段；LangGraph 用默认覆盖 reducer 合并。
    None 字段也会回写（覆盖为 None），保证图状态与智能体产出一致。
    """
    return {
        "task_id": updated_class_state.task_id,
        "topic": updated_class_state.topic,
        "style": updated_class_state.style,
        "genre": updated_class_state.genre,
        "language_style": updated_class_state.language_style,
        "word_count": updated_class_state.word_count,
        "collected_news": updated_class_state.collected_news,
        "user_description": updated_class_state.user_description,
        "title": (
            updated_class_state.title.model_dump(by_alias=True)
            if updated_class_state.title
            else None
        ),
        "title_options": (
            [item.model_dump(by_alias=True) for item in updated_class_state.title_options]
            if updated_class_state.title_options
            else None
        ),
        "outline": (
            updated_class_state.outline.model_dump() if updated_class_state.outline else None
        ),
        "content": updated_class_state.content,
        "image_requirements": (
            [req.model_dump(by_alias=True) for req in updated_class_state.image_requirements]
            if updated_class_state.image_requirements
            else None
        ),
        "images": (
            [img.model_dump(by_alias=True) for img in updated_class_state.images]
            if updated_class_state.images
            else None
        ),
        "cover_image": updated_class_state.cover_image,
        "full_content": updated_class_state.full_content,
        "enabled_image_methods": updated_class_state.enabled_image_methods,
    }