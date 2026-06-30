"""
智能体提示词
"""

class PromptConstant:
    """Prompt 模板常量"""
    
    # 智能体1：生成标题
    AGENT1_TITLE_PROMPT = """你是一位爆款文章标题专家,擅长创作吸引人的标题。

根据以下选题,生成 3-5 个爆款文章标题方案:
选题：{topic}

要求:
1. 每个方案包含主标题和副标题
2. 主标题要包含数字、情绪化词汇,吸引眼球
3. 副标题要补充说明,增强吸引力
4. 标题要简洁有力,不超过30字
5. 不同方案要有不同的切入角度
6. 符合新媒体爆款文章的风格

请直接返回 JSON 格式,不要有其他内容:
[
    {{
        "mainTitle": "主标题1",
        "subTitle": "副标题1"
    }},
    {{
        "mainTitle": "主标题2",
        "subTitle": "副标题2"
    }},
    {{
        "mainTitle": "主标题3",
        "subTitle": "副标题3"
    }}
]
"""


    # 智能体2：生成大纲
    # TODO: 优先级2，字数应可指定，与正文生成一致
    AGENT2_OUTLINE_PROMPT = """你是一位专业的文章策划师,擅长设计文章结构。

根据以下标题,生成文章大纲:
主标题：{mainTitle}
副标题：{subTitle}
{descriptionSection}

要求:
1. 大纲要有清晰的逻辑结构
2. 包含开头引入、核心观点(3-5个)、结尾升华
3. 每个章节要有明确的标题和核心要点(2-3个)
4. 适合2000字左右的文章

请直接返回 JSON 格式,不要有其他内容:
{{
  "sections": [
    {{
      "section": 1,
      "title": "章节标题",
      "points": ["要点1", "要点2"]
    }}
  ]
}}
"""


    # 用户补充描述段落
    AGENT2_DESCRIPTION_SECTION = """

用户补充要求：{userDescription}
请在大纲中充分体现用户的补充要求。
"""

    # AI 修改大纲 Prompt
    AI_MODIFY_OUTLINE_PROMPT = """你是一位专业的文章策划师,擅长根据用户反馈优化文章结构。

当前文章信息：
主标题：{mainTitle}
副标题：{subTitle}

当前大纲：
{currentOutline}

用户修改建议：
{modifySuggestion}

要求：
1. 根据用户的修改建议，调整大纲结构
2. 保持大纲的逻辑性和完整性
3. 如果用户建议删除某章节，则删除；建议增加则增加；建议修改则修改
4. 保持 JSON 格式不变
5. 章节序号自动重新排序

请直接返回修改后的 JSON 格式大纲，不要有其他内容：
{{
  "sections": [
    {{
      "section": 1,
      "title": "章节标题",
      "points": ["要点1", "要点2"]
    }}
  ]
}}
"""


    # 智能体3：生成正文
    AGENT3_CONTENT_PROMPT = """你是一位资深的内容创作者,擅长撰写优质文章。

根据以下大纲,创作文章正文:
主标题：{mainTitle}
副标题：{subTitle}
大纲：
{outline}

要求:
1. 内容要充实,每个章节300-400字
2. 语言流畅,富有感染力
3. 适当使用金句,增强可读性
4. 添加过渡句,确保逻辑连贯
5. 使用 Markdown 格式,章节使用 ## 标题

请直接返回 Markdown 格式的正文内容,不要有其他内容。
"""

# NOTE: 修改工具时需同步更新提示词
    # 智能体4：分析配图需求
    AGENT4_IMAGE_REQUIREMENTS_PROMPT = """你是一位专业的新媒体编辑,擅长为文章配图。

根据以下文章内容,分析配图需求,并在正文中插入图片占位符:
主标题：{mainTitle}
正文：
{content}

可用的配图方式：
{imageMethodsGuide}

要求:
1. 识别需要配图的位置(封面、关键章节、段落之间等)
2. 根据文章内容和结构灵活决定配图数量，避免过多或过少
3. **在正文中插入占位符**：使用以下两种格式
   - 普通图片占位符：{{IMAGE_PLACEHOLDER_N}}，其中 N 为配图序号（1, 2, 3...），必须独占一行
   - Icon 占位符：{{ICON_PLACEHOLDER_N}}，可以放在文字行内任意位置（用于 ICONIFY 类型）
   - 注意：position=1 的封面图不需要占位符，不要放在正文中
   - 配图占位符可以放在任意合适位置（章节标题后、段落之间、列表项中、文字行内等）
4. **只能从上述可用的配图方式中选择** imageSource，并参考各方式的用法指南填写 keywords 或 prompt；具体可用的方式与说明见上方"可用的配图方式"列表
9. placeholderId 必须与正文中插入的占位符完全一致
10. position=1 为封面图

请直接返回 JSON 格式,不要有其他内容:
{{
  "contentWithPlaceholders": "## 章节标题1\\n\\n正文内容...\\n\\n{{IMAGE_PLACEHOLDER_1}}\\n\\n## 章节标题2\\n\\n更多正文内容... {{ICON_PLACEHOLDER_1}} 行内图标示例\\n\\n{{IMAGE_PLACEHOLDER_2}}\\n\\n...",
  "imageRequirements": [
    {{
      "position": 1,
      "type": "cover",
      "sectionTitle": "",
      "imageSource": "（从上述可用配图方式中选择）",
      "keywords": "",
      "prompt": "",
      "placeholderId": ""
    }},
    {{
      "position": 2,
      "type": "section",
      "sectionTitle": "章节标题1",
      "imageSource": "（从上述可用配图方式中选择）",
      "keywords": "英文搜索关键词（如使用图库检索类方式）",
      "prompt": "",
      "placeholderId": "{{IMAGE_PLACEHOLDER_1}}"
    }},
    {{
      "position": 3,
      "type": "inline",
      "sectionTitle": "",
      "imageSource": "（从上述可用配图方式中选择）",
      "keywords": "check circle",
      "prompt": "",
      "placeholderId": "{{ICON_PLACEHOLDER_1}}"
    }},
    {{
      "position": 4,
      "type": "section",
      "sectionTitle": "章节标题2",
      "imageSource": "（从上述可用配图方式中选择）",
      "keywords": "",
      "prompt": "（如使用 AI 生图类方式，在此生成完整代码或描述需求）",
      "placeholderId": "{{IMAGE_PLACEHOLDER_2}}"
    }}
  ]
}}
"""
    SVG_DIAGRAM_GENERATION_PROMPT = """### 背景 ###
你是一位资深的信息可视化设计师，擅长将抽象概念转化为直观易懂的 SVG 示意图。
你的作品曾用于知名媒体和技术文档，风格简洁现代、逻辑清晰。

### 需求 ###
{requirement}

### 任务步骤 ###
1. 分析需求：理解要表达的核心概念和逻辑关系
2. 设计布局：确定图形的整体结构（中心辐射、层级、流程等）
3. 选择元素：使用圆形、矩形、箭头、连线等基础图形
4. 配色美化：应用现代配色方案，确保视觉协调
5. 生成代码：输出完整规范的 SVG 代码

### 技术规范 ###
- 必须包含 <?xml version="1.0" encoding="UTF-8"?> 声明
- 必须设置 viewBox="0 0 800 600"，便于自适应缩放
- 字体使用 font-family="Arial, sans-serif"，确保跨平台兼容
- 使用语义化的 id 和 class 命名

### 输出要求 ###
请直接输出完整的 SVG 代码，不要有其他任何内容（不要markdown代码块标记）。
从 <?xml 开始，到 </svg> 结束。
"""

    # 科技风格 Prompt
    STYLE_TECH_PROMPT = """

**重要：请使用科技风格进行创作**
- 语言专业、严谨，多使用专业术语和行业词汇
- 逻辑清晰，重视数据和事实支撑
- 叙述客观理性，避免主观情感表达
"""

    # 情感风格 Prompt
    STYLE_EMOTIONAL_PROMPT = """

**重要：请使用情感风格进行创作**
- 语言温暖细腻，富有感染力和共鸣
- 善用比喻、排比等修辞手法增强表现力
- 注重情感表达，讲述真实故事和感悟
"""

    # 教育风格 Prompt
    STYLE_EDUCATIONAL_PROMPT = """

**重要：请使用教育风格进行创作**
- 语言通俗易懂，深入浅出地讲解概念
- 结构清晰，循序渐进，便于学习理解
- 多用案例、类比帮助读者理解复杂内容
"""

    # 轻松幽默风格 Prompt
    STYLE_HUMOROUS_PROMPT = """

**重要：请使用轻松幽默风格进行创作**
- 语言轻松活泼，幽默风趣
- 善用网络流行语、俏皮话和有趣的比喻
- 适当自嘲或调侃，增加趣味性
"""

    AGENT5_IMAGE_EXECUTION_PROMPT = "并行执行配图生成，确保结果按 position 顺序回填。"