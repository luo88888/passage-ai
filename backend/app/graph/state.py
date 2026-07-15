"""
LangGraph 文章生成图——共享状态定义（可序列化 dict 形态）

设计要点：
- LangGraph 的 checkpointer（SQLite）会把图状态 JSON 序列化持久化，
  因此本 TypedDict 的所有字段都用「可 JSON 序列化」的原始类型
 （str / list[dict] / dict / list[str]），不直接放 Pydantic 模型对象。
- 现有智能体（app/agent/agents/）的 run(state) 接收的是
  app/schemas/article.py:195 的 class ArticleState（含 Pydantic 模型字段）。
  节点体通过 app/graph/nodes/compat.py 的 to_class_state / merge_to_dict
  在「dict 图状态」与「class 智能体状态」之间双向适配。
- 各字段的 dict 结构与现有持久化/SSE 序列化惯例保持一致：
    * title / title_options        → by_alias（mainTitle/subTitle）
    * outline                       → OutlineResult.model_dump()（无 alias，含 sections）
    * image_requirements / images   → model_dump(by_alias=True)
- 默认 reducer（节点返回字段整体覆盖），无 Annotated 累加需求。
"""
from typing import List, Optional
from typing_extensions import TypedDict


class ArticleState(TypedDict, total=False):
    """文章生成图状态（dict 形态，可序列化）"""

    # ==================== 基础元信息 ====================
    task_id: Optional[str]
    topic: Optional[str]                                     # 用户指定选题
    style: Optional[str]                                     # 文章风格（已弃用，保留兼容）

    # ==================== 创作控制输入（新版） ====================
    genre: Optional[str]                                     # 题材：news/knowledge/product/tutorial/opinion/story
    language_style: Optional[str]                            # 语言风格：professional/accessible/humorous/literary/formal
    word_count: Optional[int]                               # 目标字数（<=10000，None 走默认 2000）
    collected_news: Optional[str]                            # 新闻题材信息采集产物（供标题/大纲/正文提示词注入的摘要文本）

    # ==================== 交互式流程输入 ====================
    user_description: Optional[str]                         # 用户补充描述
    title_options: Optional[List[dict]]                      # 标题方案列表，每项 {"mainTitle","subTitle"}
    enabled_image_methods: Optional[List[str]]               # 可使用的配图方式
    modify_suggestion: Optional[str]                        # AI 修改大纲的用户建议（路由注入，节点消费后清空）

    # ==================== 各智能体产出 ====================
    title: Optional[dict]                                    # {"mainTitle","subTitle"}
    outline: Optional[dict]                                  # {"sections":[{"section","title","points"},...]}
    content: Optional[str]                                   # 正文（agent3 原文 / agent4 带占位符版本覆盖）
    image_requirements: Optional[List[dict]]                 # model_dump(by_alias=True) 形态
    images: Optional[List[dict]]                             # model_dump(by_alias=True) 形态
    cover_image: Optional[str]
    full_content: Optional[str]                              # 图文合并最终结果