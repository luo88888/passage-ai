"""
配图需求分析智能体
"""
from typing import List, Optional

from app.agent.base_agent import BaseAgent
from app.constants.prompt import PromptConstant
from app.models.enums import ImageMethodEnum
from app.schemas.article import Agent4Result, ArticleState, ImageRequirement
from app.utils.logger import logger


class ImageAnalyzerAgent(BaseAgent):
    """配图需求分析智能体"""

    # ==================== 配图方式描述辅助方法 ====================

    def _build_available_methods_description(
        self,
        enabled_methods: Optional[List[str]],
    ) -> str:
        """构建可用配图方式说明"""
        if not enabled_methods:
            return self._get_all_methods_description()

        descriptions = []
        for method_str in enabled_methods:
            try:
                method = ImageMethodEnum(method_str)
                if not method.is_fallback():
                    desc = self._get_method_usage_description(method)
                    descriptions.append(f"   - {method.value}: {desc}")
            except ValueError:
                continue

        return "\n".join(descriptions)

    @staticmethod
    def _get_all_methods_description() -> str:
        """获取所有配图方式的完整描述"""
        return (
            "   - PEXELS: 适合真实场景、产品照片、人物照片、自然风景等写实图片\n"
            "   - MERMAID: 适合流程图、架构图、时序图、关系图、甘特图等结构化图表\n"
            "   - ICONIFY: 适合图标、符号、小型装饰性图标（如：箭头、勾选、星星、心形等）\n"
            "   - EMOJI_PACK: 适合表情包、搞笑图片、轻松幽默的配图\n"
            "   - SVG_DIAGRAM: 适合概念示意图、思维导图样式、逻辑关系展示（不涉及精确数据）"
        )

    @staticmethod
    def _get_method_usage_description(method: ImageMethodEnum) -> str:
        """获取配图方式的使用说明"""
        descriptions = {
            ImageMethodEnum.PEXELS: "适合真实场景、产品照片、人物照片、自然风景等写实图片",
            ImageMethodEnum.MERMAID: "适合流程图、架构图、时序图、关系图、甘特图等结构化图表",
            ImageMethodEnum.ICONIFY: "适合图标、符号、小型装饰性图标（如：箭头、勾选、星星、心形等）",
            ImageMethodEnum.EMOJI_PACK: "适合表情包、搞笑图片、轻松幽默的配图",
            ImageMethodEnum.SVG_DIAGRAM: "适合概念示意图、思维导图样式、逻辑关系展示（不涉及精确数据）",
        }
        return descriptions.get(method, method.value)  # type: ignore

    def _build_method_usage_guide(
        self,
        enabled_methods: Optional[List[str]],
    ) -> str:
        """构建配图方式的详细使用指南"""
        methods_to_include = enabled_methods if enabled_methods else [
            "PEXELS", "NANO_BANANA", "MERMAID", "ICONIFY", "EMOJI_PACK", "SVG_DIAGRAM"
        ]

        guides = []
        for method_str in methods_to_include:
            guide = self._get_method_detailed_guide(method_str)
            if guide:
                guides.append(guide)

        return "\n".join(guides)

    @staticmethod
    def _get_method_detailed_guide(method_str: str) -> str:
        """获取单个配图方式的详细使用指南"""
        guides = {
            "PEXELS": "- PEXELS: 提供英文搜索关键词(keywords)，要准确、具体。prompt 留空。",
            "MERMAID": "- MERMAID: 在 prompt 字段生成完整的 Mermaid 代码（如流程图、架构图）。keywords 留空。",
            "ICONIFY": "- ICONIFY: 提供英文图标关键词(keywords)，如：check、arrow、star、heart。prompt 留空。",
            "EMOJI_PACK": "- EMOJI_PACK: 提供中文或英文关键词(keywords)描述表情内容。prompt 留空。系统会自动添加'表情包'搜索。",
            "SVG_DIAGRAM": (
                "- SVG_DIAGRAM: 在 prompt 字段描述示意图需求（中文），说明要表达的概念和关系。keywords 留空。\n"
                "  示例：绘制思维导图样式的图，中心是'自律'，周围4个分支：习惯、环境、反馈、系统"
            ),
        }
        return guides.get(method_str, "")

    @staticmethod
    def _validate_and_filter_image_requirements(
        requirements: List[ImageRequirement],
        enabled_methods: Optional[List[str]],
    ) -> List[ImageRequirement]:
        """验证并过滤配图需求（不在允许列表中的降级替换）"""
        if not enabled_methods:
            return requirements

        validated_requirements = []

        for req in requirements:
            image_source = req.image_source

            if image_source in enabled_methods:
                validated_requirements.append(req)
                logger.debug(
                    "配图需求验证通过, position=%s, imageSource=%s",
                    req.position,
                    image_source,
                )
            else:
                fallback_source = enabled_methods[0]
                logger.warning(
                    "配图需求方式不在允许列表，降级替换, position=%s, "
                    "imageSource=%s, fallback=%s, enabledMethods=%s",
                    req.position,
                    image_source,
                    fallback_source,
                    enabled_methods,
                )
                req.image_source = fallback_source
                validated_requirements.append(req)

        return validated_requirements

    # ==================== 主流程 ====================

    async def run(self, state: ArticleState):
        """分析配图需求，在正文中插入占位符，填充 state 相关字段"""
        available_methods = self._build_available_methods_description(
            state.enabled_image_methods
        )
        method_usage_guide = self._build_method_usage_guide(
            state.enabled_image_methods
        )

        prompt = PromptConstant.AGENT4_IMAGE_REQUIREMENTS_PROMPT.format(
            mainTitle=state.title.main_title,  # type: ignore
            content=state.content,
            availableMethods=available_methods,
            methodUsageGuide=method_usage_guide,
        )
        prompt += self._get_style_prompt(state.style)

        async with self._agent_log_context(
            task_id=state.task_id,
            agent_name="agent4_analyze_image_requirements",
            prompt=prompt,
            input_data={"enabledImageMethods": state.enabled_image_methods},
        ) as log_data:
            content = await self._call_llm(prompt)
            agent4_result = Agent4Result(
                **self._parse_json_response(content, "配图需求")
            )
            state.content = agent4_result.content_with_placeholders

            state.image_requirements = self._validate_and_filter_image_requirements(
                agent4_result.image_requirements,
                state.enabled_image_methods,
            )
            log_data["outputData"] = self._safe_json_dumps(
                {
                    "rawRequirementsCount": len(agent4_result.image_requirements),
                    "validatedRequirementsCount": len(state.image_requirements),
                }
            )
            logger.info(
                "智能体4：配图需求分析成功, count=%s, validated=%s, 已在正文中插入占位符",
                len(agent4_result.image_requirements),
                len(state.image_requirements),
            )
