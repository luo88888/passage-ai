"""图相关共享常量"""

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