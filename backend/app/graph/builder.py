"""
LangGraph 文章生成图——图构建器

本文件只负责图的拓扑组装：注册节点 + 连顺序边 + 配置 interrupt + 注入 checkpointer。
- 节点实现 → app/graph/nodes/（每节点一文件）
- 共享常量 → app/graph/constants.py
- 状态定义 → app/graph/state.py
- checkpointer → app/graph/checkpointer.py

图拓扑（成功路径副作用全在图内）：
    START → bootstrap → generate_title → confirm_title
                               ↓ interrupt_after=confirm_title（暂停等用户确认标题）
           → generate_outline → confirm_outline
                               ↓ interrupt_after=confirm_outline（暂停等用户编辑大纲）
           →（条件边）有 modify_suggestion → ai_modify_outline → interrupt_after（可反复 AI 修改）
                              无 modify_suggestion → generate_content
           → generate_content → image_analyzer → image_generator → merger → finalize → END

三个 interrupt 对应人机协同点：
  - confirm_title 后：标题方案已落库 + TITLE_GENERATED 已发，等用户确认标题 + 补充描述
  - confirm_outline 后：大纲已落库 + OUTLINE_GENERATED 已发，等用户编辑 / AI 修改大纲
  - ai_modify_outline 后：新大纲已落库 + AI_MODIFY_OUTLINE_COMPLETE 已发，等用户再次修改 或 确认大纲

智能体节点保持纯净（只跑 agent + emit 完成 SSE）；持久化/阶段流转/SSE 阶段事件全在副作用节点。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from langgraph.graph import END, START, StateGraph

from app.graph.constants import (
    NODE_AI_MODIFY_OUTLINE,
    NODE_BOOTSTRAP,
    NODE_CONFIRM_OUTLINE,
    NODE_CONFIRM_TITLE,
    NODE_FINALIZE,
    NODE_GENERATE_CONTENT,
    NODE_GENERATE_OUTLINE,
    NODE_GENERATE_TITLE,
    NODE_IMAGE_ANALYZER,
    NODE_IMAGE_GENERATOR,
    NODE_MERGER,
)
from app.graph.nodes import (
    ai_modify_outline_node,
    bootstrap_node,
    confirm_outline_node,
    confirm_title_node,
    content_merger_node,
    content_node,
    finalize_node,
    image_analyzer_node,
    image_generator_node,
    outline_node,
    title_node,
)
from app.graph.state import ArticleState

if TYPE_CHECKING:
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    from langgraph.graph.state import CompiledStateGraph


def _route_after_outline(state: ArticleState) -> str:
    """confirm_outline / ai_modify_outline 后的条件路由

    有 modify_suggestion（路由层 ai-modify-outline 注入）→ 进 AI 修改大纲节点；
    否则（确认大纲时未注入建议 / 节点消费后清空）→ 进 generate_content 继续正文生成。
    """
    return NODE_AI_MODIFY_OUTLINE if state.get("modify_suggestion") else NODE_GENERATE_CONTENT


def build_article_graph(checkpointer: "AsyncSqliteSaver | None") -> "CompiledStateGraph":
    """构建并编译文章生成图

    Args:
        checkpointer: SQLite checkpointer 单例，持久化图状态供人机协同 interrupt 续跑。
    """
    workflow = StateGraph(ArticleState)

    # ==================== 注册节点 ====================
    # 副作用节点（DB 持久化 / 阶段流转 / SSE 人机协同事件）
    workflow.add_node(NODE_BOOTSTRAP, bootstrap_node)
    workflow.add_node(NODE_CONFIRM_TITLE, confirm_title_node)
    workflow.add_node(NODE_CONFIRM_OUTLINE, confirm_outline_node)
    workflow.add_node(NODE_FINALIZE, finalize_node)
    workflow.add_node(NODE_AI_MODIFY_OUTLINE, ai_modify_outline_node)
    # 智能体节点（跑 agent + emit 完成 SSE）
    workflow.add_node(NODE_GENERATE_TITLE, title_node)
    workflow.add_node(NODE_GENERATE_OUTLINE, outline_node)
    workflow.add_node(NODE_GENERATE_CONTENT, content_node)
    workflow.add_node(NODE_IMAGE_ANALYZER, image_analyzer_node)
    workflow.add_node(NODE_IMAGE_GENERATOR, image_generator_node)
    workflow.add_node(NODE_MERGER, content_merger_node)

    # ==================== 顺序边 ====================
    workflow.add_edge(START, NODE_BOOTSTRAP)
    workflow.add_edge(NODE_BOOTSTRAP, NODE_GENERATE_TITLE)
    workflow.add_edge(NODE_GENERATE_TITLE, NODE_CONFIRM_TITLE)          # confirm_title 后 interrupt
    workflow.add_edge(NODE_CONFIRM_TITLE, NODE_GENERATE_OUTLINE)
    workflow.add_edge(NODE_GENERATE_OUTLINE, NODE_CONFIRM_OUTLINE)      # confirm_outline 后 interrupt
    # confirm_outline 后按是否要 AI 修改大纲分流：有 modify_suggestion 走修改节点，否则进 generate_content
    workflow.add_conditional_edges(
        NODE_CONFIRM_OUTLINE,
        _route_after_outline,
        {NODE_AI_MODIFY_OUTLINE: NODE_AI_MODIFY_OUTLINE, NODE_GENERATE_CONTENT: NODE_GENERATE_CONTENT},
    )
    # ai_modify_outline 后同理：还可再次修改（mit 后 interrupt）或确认进 generate_content
    workflow.add_conditional_edges(
        NODE_AI_MODIFY_OUTLINE,
        _route_after_outline,
        {NODE_AI_MODIFY_OUTLINE: NODE_AI_MODIFY_OUTLINE, NODE_GENERATE_CONTENT: NODE_GENERATE_CONTENT},
    )
    workflow.add_edge(NODE_GENERATE_CONTENT, NODE_IMAGE_ANALYZER)
    workflow.add_edge(NODE_IMAGE_ANALYZER, NODE_IMAGE_GENERATOR)
    workflow.add_edge(NODE_IMAGE_GENERATOR, NODE_MERGER)
    workflow.add_edge(NODE_MERGER, NODE_FINALIZE)
    workflow.add_edge(NODE_FINALIZE, END)

    # ==================== 人机协同打断点 ====================
    # 锚点设在副作用节点后：先落库 + 发阶段 SSE，再暂停等用户输入（避免暂停后才发事件）
    # NODE_AI_MODIFY_OUTLINE 后也 interrupt，使"AI 修改"可反复触发（每次 resume 最多执行一次本节点）
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_after=[NODE_CONFIRM_TITLE, NODE_CONFIRM_OUTLINE, NODE_AI_MODIFY_OUTLINE],
    )