"""图节点包：每个文件对应一个 LangGraph 节点函数

当前接入图的 12 个节点（app/graph/builder.py 注册）：
  副作用节点：bootstrap / confirm_title / confirm_outline / ai_modify_outline / finalize
  信息采集节点：research（新闻题材专用，bootstrap 后条件边路由进入）
  智能体节点：generate_title / generate_outline / generate_content / image_analyzer / image_generator / merger

占位节点（暂不接入 builder，保留以备后续实现）：
  review / seo

状态适配：compat（dict↔class）
"""
from app.graph.nodes.compat import merge_to_dict_state, to_class_state
from app.graph.nodes.bootstrap import bootstrap_node
from app.graph.nodes.content import content_node
from app.graph.nodes.finalize import finalize_node
from app.graph.nodes.image_analyzer import image_analyzer_node
from app.graph.nodes.image_generator import image_generator_node
from app.graph.nodes.merger import content_merger_node
from app.graph.nodes.outline import outline_node
from app.graph.nodes.confirm_outline import confirm_outline_node
from app.graph.nodes.confirm_title import confirm_title_node
from app.graph.nodes.title import title_node

# AI 修改大纲副作用节点（接入图，由 builder 条件边路由进入）
from app.graph.nodes.ai_modify_outline import ai_modify_outline_node

# 信息采集节点（接入图，新闻题材专用，bootstrap 后条件边路由进入）
from app.graph.nodes.research import research_node

# 占位节点（暂不接入 builder，保留以备后续实现）
from app.graph.nodes.review import review_node
from app.graph.nodes.seo import seo_node

__all__ = [
    "to_class_state",
    "merge_to_dict_state",
    # 副作用节点（接入图）
    "bootstrap_node",
    "confirm_title_node",
    "confirm_outline_node",
    "finalize_node",
    "ai_modify_outline_node",
    # 信息采集节点（接入图，新闻题材专用）
    "research_node",
    # 智能体节点（接入图）
    "title_node",
    "outline_node",
    "content_node",
    "image_analyzer_node",
    "image_generator_node",
    "content_merger_node",
    # 占位节点（暂未接入）
    "review_node",
    "seo_node",
]