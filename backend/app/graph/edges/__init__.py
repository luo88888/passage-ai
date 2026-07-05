"""图边包：条件边路由函数

当前图为线性拓扑（title→outline→content→...→END），所有顺序边在 builder.py 用
add_edge 注册，无需拆到 edges/。内容审核 Agent 实现后，条件边路由放此包。
"""
from app.graph.edges.review_routing import route_after_review

__all__ = ["route_after_review"]