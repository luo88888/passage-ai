"""图相关共享常量

当前接入图的节点为 12 个：5 个副作用节点（bootstrap/confirm_title/confirm_outline/
ai_modify_outline/finalize）+ 1 个信息采集节点（research，新闻题材专用）+ 6 个智能体节点
（generate_title/generate_outline/generate_content/image_analyzer/image_generator/merger）。
副作用节点负责 DB 持久化/阶段流转/SSE 人机协同事件，智能体节点只跑 agent + 发 agent 完成 SSE。
interrupt_after 锚点设在 confirm_title / confirm_outline / ai_modify_outline，保证
「先持久化 + 发阶段事件再暂停」。research 经 bootstrap 后条件边路由进入（新闻题材）；
review / seo 为待实现占位，不注册进 builder。
"""
# ==================== 当前接入图的节点名 ====================
NODE_BOOTSTRAP = "bootstrap"                # 启动副作用：标记 PROCESSING + 推进 TITLE_GENERATING
NODE_GENERATE_TITLE = "generate_title"      # 标题生成智能体：生成标题方案
NODE_CONFIRM_TITLE = "confirm_title"        # 标题确认副作用：save_title_options + TITLE_SELECTING + TITLE_GENERATED
NODE_GENERATE_OUTLINE = "generate_outline"  # 大纲生成智能体：生成大纲
NODE_CONFIRM_OUTLINE = "confirm_outline"    # 大纲确认副作用：save_outline + OUTLINE_EDITING + OUTLINE_GENERATED
NODE_AI_MODIFY_OUTLINE = "ai_modify_outline"  # AI 修改大纲副作用：LLM 重写大纲 + save_outline + AI_MODIFY_OUTLINE_COMPLETE
NODE_GENERATE_CONTENT = "generate_content"  # 正文生成智能体：生成正文
NODE_IMAGE_ANALYZER = "image_analyzer"
NODE_IMAGE_GENERATOR = "image_generator"
NODE_MERGER = "merger"
NODE_FINALIZE = "finalize"                  # 收尾副作用：save_article_content + COMPLETED + ALL_COMPLETE + close SSE

# ==================== 信息采集节点名（接入图，新闻题材专用） ====================
NODE_RESEARCH = "research"    # 信息采集 Agent：新闻题材采集相关报道（bootstrap 后条件边路由进入）

# ==================== 待实现占位节点名（暂不接入 builder） ====================
NODE_REVIEW = "review"         # 内容审核 Agent
NODE_SEO = "seo"               # SEO 优化 Agent