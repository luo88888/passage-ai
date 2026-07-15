"""图边包：条件边路由函数

当前接入图的条件边：
- bootstrap 后：新闻题材 → 信息采集节点，其余 → 直接生成标题（bootstrap_routing）
- confirm_outline / ai_modify_outline 后：按是否有 modify_suggestion 分流（builder 内联）

内容审核 Agent 实现后，其条件边路由亦可放此包。
"""
from app.graph.edges.bootstrap_routing import route_after_bootstrap
from app.graph.edges.review_routing import route_after_review

__all__ = ["route_after_bootstrap", "route_after_review"]