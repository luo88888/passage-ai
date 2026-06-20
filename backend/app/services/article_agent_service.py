from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
import json

from openai import AsyncOpenAI
from typing import Callable, List, Optional


from app.agent.image_generator import ParallelImageGenerator
from app.agent.orchestrator import ArticleAgentOrchestrator
from app.database import database
from app.config import settings
from app.schemas.article import (
    Agent4Result,
    ArticleState,
    TitleOption,
    OutlineSection,
    OutlineResult,
    ImageResult,
    ImageRequirement
)
from app.models.enums import (
    ArticleStyleEnum,
    SseMessageTypeEnum,
    ImageMethodEnum
)
from app.constants.prompt import PromptConstant
from app.schemas.image import ImageRequest
from app.services.agent_log_service import AgentLogService
from app.services.image_service_strategy import ImageServiceStrategy
from app.services.pexels_service import PexelsService
from app.utils.logger import logger


class ArticleAgentService:
    """文章智能体编排服务，提供下述服务
    1. 执行完整的文章生成
    """

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.dashscope_api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.model = settings.dashscope_model

        # 初始化服务
        self.pexels_service = PexelsService()
        self.image_service_strategy = ImageServiceStrategy()
        self.agent_log_service = AgentLogService(database)

        self.parallel_image_generator = ParallelImageGenerator(
            image_service_strategy=self.image_service_strategy,
            max_concurrency=settings.agent_image_max_concurrency,
            fail_fast=settings.agent_image_fail_fast,
        )
        self.orchestrator = ArticleAgentOrchestrator()


        # self.cos_service = CosService()


    async def agent1_generate_title_options(self, state: ArticleState):
        """智能体1：生成标题方案列表"""
        prompt = PromptConstant.AGENT1_TITLE_PROMPT.format(topic=state.topic)
        prompt += self._get_style_prompt(state.style)

        async with self._agent_log_context(
            task_id=state.task_id,
            agent_name="agent1_generate_titles",
            prompt=prompt,
            input_data={"topic": state.topic, "style": state.style},
        ) as log_data:
            content = await self._call_llm(prompt)
            title_options_data = self._parse_json_list_response(content, "标题方案")
            state.title_options = [TitleOption(**item) for item in title_options_data]
            log_data["outputData"] = self._safe_json_dumps({"optionsCount": len(state.title_options)})
            logger.info("智能体1：标题方案生成成功, count=%s", len(state.title_options))

    async def agent2_generate_outline(
        self,
        state: ArticleState,
        stream_handler: Callable[[str], None]
    ):
        """智能体2：生成大纲（流式输出）"""
        description_section = ""
        if state.user_description and state.user_description.strip():
            description_section = PromptConstant.AGENT2_DESCRIPTION_SECTION.replace(
                "{userDescription}",
                state.user_description,
            )

        prompt = (
            PromptConstant.AGENT2_OUTLINE_PROMPT
            .replace("{mainTitle}", state.title.main_title) # type: ignore
            .replace("{subTitle}", state.title.sub_title)   # type: ignore
            .replace("{descriptionSection}", description_section)
        )
        prompt += self._get_style_prompt(state.style)

        async with self._agent_log_context(
            task_id=state.task_id,
            agent_name="agent2_generate_outline",
            prompt=prompt,
            input_data={
                "mainTitle": state.title.main_title if state.title else None,
                "subTitle": state.title.sub_title if state.title else None,
                "hasUserDescription": bool(state.user_description and state.user_description.strip()),
            },
        ) as log_data:
            content = await self._call_llm_with_streaming(
                prompt, stream_handler, SseMessageTypeEnum.AGENT2_STREAMING
            )
            outline_data = self._parse_json_response(content, "大纲")
            sections = [OutlineSection(**section) for section in outline_data["sections"]]
            state.outline = OutlineResult(sections=sections)
            log_data["outputData"] = self._safe_json_dumps({"sectionsCount": len(state.outline.sections)})

        logger.info(f"智能体2：大纲生成成功, sections={len(state.outline.sections)}")

    async def ai_modify_outline(
        self,
        main_title: str,
        sub_title: str,
        current_outline: List[OutlineSection],
        modify_suggestion: str,
        task_id: Optional[str]
    ) -> List[OutlineSection]:
        """AI 修改大纲"""
        current_outline_json = json.dumps(
            [item.model_dump() for item in current_outline],
            ensure_ascii=False,
        )
        prompt = (
            PromptConstant.AI_MODIFY_OUTLINE_PROMPT
            .replace("{mainTitle}", main_title)
            .replace("{subTitle}", sub_title)
            .replace("{currentOutline}", current_outline_json)
            .replace("{modifySuggestion}", modify_suggestion)
        )

        with self._agent_log_context_sync(
            task_id=task_id or "unknown",
            agent_name="ai_modify_outline",
            prompt=prompt,
            input_data={
                "mainTitle": main_title,
                "subTitle": sub_title,
                "currentSectionsCount": len(current_outline),
            },
        ) as log_data:
            content = await self._call_llm(prompt)
            outline_data = self._parse_json_response(content, "修改后的大纲")
            sections = [OutlineSection(**section) for section in outline_data["sections"]]
            log_data["outputData"] = self._safe_json_dumps({"sectionsCount": len(sections)})
            return sections


    async def agent3_generate_content(
        self,
        state: ArticleState,
        stream_handler: Callable[[str], None]
    ):
        """智能体3：生成正文（流式输出）"""
        assert state.outline is not None
        outline_text = json.dumps(
            [section.model_dump() for section in state.outline.sections],
            ensure_ascii=False
        )
        assert state.title is not None
        prompt = PromptConstant.AGENT3_CONTENT_PROMPT.format(
            mainTitle=state.title.main_title,
            subTitle=state.title.sub_title,
            outline=outline_text,
        )
        prompt += self._get_style_prompt(state.style)

        async with self._agent_log_context(
            task_id=state.task_id,
            agent_name="agent3_generate_content",
            prompt=prompt,
            input_data={
                "mainTitle": state.title.main_title if state.title else None,
                "subTitle": state.title.sub_title if state.title else None,
                "outlineSections": len(state.outline.sections) if state.outline else 0,
            },
        ) as log_data:
            content = await self._call_llm_with_streaming(
                prompt, stream_handler, SseMessageTypeEnum.AGENT3_STREAMING
            )
            state.content = content
            log_data["outputData"] = self._safe_json_dumps({"contentLength": len(content)})
            logger.info(f"智能体3：正文生成成功, length={len(content)}")

    async def agent4_analyze_image_requirements(
        self,
        state: ArticleState
    ):
        """智能体4：分析配图需求"""
        available_methods = self._build_available_methods_description(state.enabled_image_methods)
        method_usage_guide = self._build_method_usage_guide(state.enabled_image_methods)

        prompt = PromptConstant.AGENT4_IMAGE_REQUIREMENTS_PROMPT.format(
            mainTitle = state.title.main_title, # type: ignore
            content = state.content,
            availableMethods = available_methods,
            methodUsageGuide = method_usage_guide
        )
        prompt += self._get_style_prompt(state.style)

        async with self._agent_log_context(
            task_id=state.task_id,
            agent_name="agent4_analyze_image_requirements",
            prompt=prompt,
            input_data={"enabledImageMethods": state.enabled_image_methods},
        ) as log_data:
            content = await self._call_llm(prompt)
            agent4_result = Agent4Result(**self._parse_json_response(content, "配图需求"))
            state.content = agent4_result.content_with_placeholders

            state.image_requirements = self._validate_and_filter_image_requirements(
                agent4_result.image_requirements,
                state.enabled_image_methods
            )
            log_data["outputData"] = self._safe_json_dumps(
                {
                    "rawRequirementsCount": len(agent4_result.image_requirements),
                    "validatedRequirementsCount": len(state.image_requirements),
                }
            )
            logger.info(
                f"智能体4：配图需求分析成功, count={len(agent4_result.image_requirements)}, "
                f"validated={len(state.image_requirements)}, 已在正文中插入占位符"
            )

    async def agent5_generate_images(
        self,
        state: ArticleState,
        stream_handler: Callable[[str], None]
    ):
        """智能体5：生成配图（第 5 期：策略模式 + 统一上传 COS）"""
        async with self._agent_log_context(
            task_id=state.task_id,
            agent_name="agent5_generate_images",
            prompt=PromptConstant.AGENT5_IMAGE_EXECUTION_PROMPT,
            input_data={"requirementsCount": len(state.image_requirements or [])},
        ) as log_data:
            generated_pairs = await self.parallel_image_generator.generate(state.image_requirements or [])
            image_results = []

            for requirement, result in generated_pairs:
                image_source = requirement.image_source
                logger.info(
                    f"智能体5：开始获取配图, position={requirement.position}, "
                    f"imageSource={image_source}, keywords={requirement.keywords}"
                )

                cos_url = result.url
                method = result.method

                # 创建配图结果（URL 已经是 COS 地址）
                image_result = self._build_image_result(requirement, cos_url, method)
                image_results.append(image_result)

                # 推送单张配图完成
                image_complete_message = (
                    SseMessageTypeEnum.IMAGE_COMPLETE.get_streaming_prefix() +
                    image_result.model_dump_json(by_alias=True)
                )
                stream_handler(image_complete_message)

                logger.info(
                    f"智能体5：配图获取并上传成功, position={requirement.position}, "
                    f"method={method.value}, cosUrl={cos_url}"
                )

            # 并行执行后按位置排序，确保输出稳定
            state.images = sorted(image_results, key=lambda item: item.position)
            log_data["outputData"] = self._safe_json_dumps({"imagesCount": len(image_results)})
            logger.info(f"智能体5：所有配图生成并上传完成, count={len(image_results)}")

    def merge_image_into_content(self, state: ArticleState):
        """图文合成：将配图插入正文对应位置"""

        with self._agent_log_context_sync(
            task_id=state.task_id,
            agent_name="agent6_merge_content",
            prompt="merge_images_into_content",
            input_data={"imagesCount": len(state.images or [])},
        ) as log_data:
            content = state.content
            images = state.images

            if not images:
                state.full_content = content
                log_data["outputData"] = self._safe_json_dumps({"fullContentLength": len(content or "")})
                return

            full_content = content

            for image in images:
                placeholder_id = image.placeholder_id
                if placeholder_id:
                    image_markdown = f"![{image.description}]({image.url})"
                    full_content = full_content.replace(placeholder_id, image_markdown) # type: ignore

            state.full_content = full_content
            log_data["outputData"] = self._safe_json_dumps({"fullContentLength": len(full_content) if full_content else 0})
            logger.info("图文合成完成 taskId=%s, fullContentLength=%s", state.task_id, len(images) if images else 0)

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM（非流式）"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content  # type: ignore
        except Exception as e:
            logger.error("LLM 调用失败(非流式) model=%s, error=%s", self.model, str(e), exc_info=True)
            raise
        
    async def _call_llm_with_streaming(
        self,
        prompt: str,
        stream_handler: Callable[[str], None],
        message_type: SseMessageTypeEnum
    ) -> str:
        """调用 LLM（流式输出）"""
        content_builder = []

        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                stream=True
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    content_builder.append(content)
                    stream_handler(message_type.get_streaming_prefix() + content)
        except Exception as e:
            logger.error("LLM 调用失败(流式) model=%s, error=%s", self.model, str(e), exc_info=True)
            raise

        return "".join(content_builder)
    
    def _parse_json_response(self, content: str, name: str, is_list: bool = False) -> dict:
        """解析 JSON 响应"""
        try:
            return json.loads(content)
            # HACK: 可尝试其它解析策略
        except json.JSONDecodeError as e:
            logger.error("%s解析失败 name=%s, error=%s, content=%s", name, name, str(e), content)
            raise RuntimeError(f"{name}解析失败")

    def _build_image_result(
        self,
        requirement: ImageRequirement,
        image_url: str,
        method: ImageMethodEnum
    ) -> ImageResult:
        """构建配图结果"""
        return ImageResult(
            position=requirement.position,
            url=image_url,
            method=method.value,
            keywords=requirement.keywords,
            sectionTitle=requirement.section_title,
            # HACK: description=type
            description=requirement.type,
            placeholderId=requirement.placeholder_id
        )

    def _build_available_methods_description(
        self,
        enabled_methods: Optional[List[str]]
    ) -> str:
        """构建可用配图方式说明"""
        # 如果为空或 None，表示支持所有方式
        if not enabled_methods:
            return self._get_all_methods_description()

        # 只描述允许的方式
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

#    - NANO_BANANA: 适合创意插画、信息图表、需要文字渲染、抽象概念、艺术风格等 AI 生成图片
    # HACK: 可解耦
    def _get_all_methods_description(self) -> str:
        """获取所有配图方式的完整描述"""
        return """   - PEXELS: 适合真实场景、产品照片、人物照片、自然风景等写实图片
   - MERMAID: 适合流程图、架构图、时序图、关系图、甘特图等结构化图表
   - ICONIFY: 适合图标、符号、小型装饰性图标（如：箭头、勾选、星星、心形等）
   - EMOJI_PACK: 适合表情包、搞笑图片、轻松幽默的配图
   - SVG_DIAGRAM: 适合概念示意图、思维导图样式、逻辑关系展示（不涉及精确数据）"""

    def _get_method_usage_description(self, method: ImageMethodEnum) -> str:
        """获取配图方式的使用说明"""
        descriptions = {
            ImageMethodEnum.PEXELS: "适合真实场景、产品照片、人物照片、自然风景等写实图片",
            # ImageMethodEnum.NANO_BANANA: "适合创意插画、信息图表、需要文字渲染、抽象概念、艺术风格等 AI 生成图片",
            ImageMethodEnum.MERMAID: "适合流程图、架构图、时序图、关系图、甘特图等结构化图表",
            ImageMethodEnum.ICONIFY: "适合图标、符号、小型装饰性图标（如：箭头、勾选、星星、心形等）",
            ImageMethodEnum.EMOJI_PACK: "适合表情包、搞笑图片、轻松幽默的配图",
            ImageMethodEnum.SVG_DIAGRAM: "适合概念示意图、思维导图样式、逻辑关系展示（不涉及精确数据）",
        }
        return descriptions.get(method, method.value)   # type: ignore

    def _build_method_usage_guide(
        self,
        enabled_methods: Optional[List[str]]
    ) -> str:
        """构建配图方式的详细使用指南"""
        # 如果没有限制，返回所有方式的使用指南
        methods_to_include = enabled_methods if enabled_methods else [
            "PEXELS", "NANO_BANANA", "MERMAID", "ICONIFY", "EMOJI_PACK", "SVG_DIAGRAM"
        ]

        guides = []
        for method_str in methods_to_include:
            guide = self._get_method_detailed_guide(method_str)
            if guide:
                guides.append(guide)

        return "\n".join(guides)

    def _get_method_detailed_guide(self, method_str: str) -> str:
        """获取单个配图方式的详细使用指南"""
        guides = {
            "PEXELS": "- PEXELS: 提供英文搜索关键词(keywords)，要准确、具体。prompt 留空。",
            # "NANO_BANANA": "- NANO_BANANA: 提供详细的英文生图提示词(prompt)，描述场景、风格、细节。keywords 留空。",
            "MERMAID": "- MERMAID: 在 prompt 字段生成完整的 Mermaid 代码（如流程图、架构图）。keywords 留空。",
            "ICONIFY": "- ICONIFY: 提供英文图标关键词(keywords)，如：check、arrow、star、heart。prompt 留空。",
            "EMOJI_PACK": "- EMOJI_PACK: 提供中文或英文关键词(keywords)描述表情内容。prompt 留空。系统会自动添加'表情包'搜索。",
            "SVG_DIAGRAM": "- SVG_DIAGRAM: 在 prompt 字段描述示意图需求（中文），说明要表达的概念和关系。keywords 留空。\n  示例：绘制思维导图样式的图，中心是'自律'，周围4个分支：习惯、环境、反馈、系统",
        }
        return guides.get(method_str, "")

    def _validate_and_filter_image_requirements(
        self,
        requirements: List[ImageRequirement],
        enabled_methods: Optional[List[str]]
    ) -> List[ImageRequirement]:
        """验证并过滤配图需求"""
        # 如果没有限制，返回所有需求
        if not enabled_methods:
            return requirements

        validated_requirements = []

        for req in requirements:
            image_source = req.image_source

            # 验证 imageSource 是否在允许列表中
            if image_source in enabled_methods:
                validated_requirements.append(req)
                logger.debug(f"配图需求验证通过, position={req.position}, imageSource={image_source}")
            else:
                # 不在允许列表中，降级替换为第一个允许的方式（优先使用第一个允许的方式）
                fallback_source = enabled_methods[0]
                logger.warning(
                    f"配图需求方式不在允许列表，降级替换, position={req.position}, "
                    f"imageSource={image_source}, fallback={fallback_source}, "
                    f"enabledMethods={enabled_methods}"
                )
                req.image_source = fallback_source
                validated_requirements.append(req)

        return validated_requirements

    def _get_style_prompt(self, style: Optional[str]) -> str:
        """根据风格获取对应的 Prompt 附加内容"""
        if not style:
            return ""
        try:
            style_enum = ArticleStyleEnum(style)
            # HACK: 临时兼容，可以解耦
            style_map = {
                ArticleStyleEnum.TECH: PromptConstant.STYLE_TECH_PROMPT,
                ArticleStyleEnum.EMOTIONAL: PromptConstant.STYLE_EMOTIONAL_PROMPT,
                ArticleStyleEnum.EDUCATIONAL: PromptConstant.STYLE_EDUCATIONAL_PROMPT,
                ArticleStyleEnum.HUMOROUS: PromptConstant.STYLE_HUMOROUS_PROMPT,
            }
            return style_map.get(style_enum, "")
        except ValueError:
            return ""

    async def execute_phase1_generate_titles(
        self,
        state: ArticleState,
        stream_handler: Callable[[str], None]
    ):
        try:
            await self.orchestrator.execute_phase1(self, state, stream_handler)
        except Exception as e:
            logger.error(f"阶段1失败, taskId={state.task_id}, error={e}")
            raise RuntimeError(f"标题方案生成失败: {str(e)}")

    async def execute_phase2_generate_outline(
        self,
        state: ArticleState,
        stream_handler: Callable[[str], None]
    ):
        """阶段2：生成大纲"""
        try:
            await self.orchestrator.execute_phase2(self, state, stream_handler)
        except Exception as e:
            logger.error(f"阶段2失败, taskId={state.task_id}, error={e}")
            raise RuntimeError(f"大纲生成失败: {str(e)}")

    async def execute_phase3_generate_content(
        self,
        state: ArticleState,
        stream_handler: Callable[[str], None]
    ):
        """阶段3：生成正文、配图和合并内容"""
        try:
            await self.orchestrator.execute_phase3(self, state, stream_handler)
        except Exception as e:
            logger.error(f"阶段3失败, taskId={state.task_id}, error={e}")
            raise RuntimeError(f"正文生成失败: {str(e)}")

    @asynccontextmanager
    async def _agent_log_context(
        self,
        task_id: Optional[str],
        agent_name: str,
        prompt: Optional[str] = None,
        input_data: Optional[dict] = None,
    ):
        """异步智能体日志上下文"""
        start_time = datetime.now()
        log_data = {
            "taskId": task_id or "unknown",
            "agentName": agent_name,
            "startTime": start_time,
            "status": "RUNNING",
            "prompt": prompt,
            "inputData": self._safe_json_dumps(input_data),
            "outputData": None,
            "errorMessage": None,
        }
        try:
            yield log_data
            log_data["status"] = "SUCCESS"
        except Exception as exc:
            log_data["status"] = "FAILED"
            log_data["errorMessage"] = str(exc)
            raise
        finally:
            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            log_data["endTime"] = end_time
            log_data["durationMs"] = duration_ms
            self.agent_log_service.save_log_async(log_data)

    @contextmanager
    def _agent_log_context_sync(
        self,
        task_id: Optional[str],
        agent_name: str,
        prompt: Optional[str] = None,
        input_data: Optional[dict] = None,
    ):
        """同步智能体日志上下文"""
        start_time = datetime.now()
        log_data = {
            "taskId": task_id or "unknown",
            "agentName": agent_name,
            "startTime": start_time,
            "status": "RUNNING",
            "prompt": prompt,
            "inputData": self._safe_json_dumps(input_data),
            "outputData": None,
            "errorMessage": None,
        }
        try:
            yield log_data
            log_data["status"] = "SUCCESS"
        except Exception as exc:
            log_data["status"] = "FAILED"
            log_data["errorMessage"] = str(exc)
            raise
        finally:
            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            log_data["endTime"] = end_time
            log_data["durationMs"] = duration_ms
            self.agent_log_service.save_log_async(log_data)


    @staticmethod
    def _safe_json_dumps(value: Optional[dict]) -> Optional[str]:
        """安全序列化 JSON"""
        if value is None:
            return None
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return None

    def _parse_json_list_response(self, content: str, name: str) -> list:
        """解析 JSON 数组响应
        Args:
            content: 待解析的 JSON 字符串
            name: 任务名称，用于日志记录和抛出异常
        """
        try:
            result = json.loads(content)
            if not isinstance(result, list):
                raise ValueError("响应不是 JSON 数组")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"{name}解析失败, content={content}, error={e}")
            raise RuntimeError(f"{name}解析失败")
        except ValueError as e:
            logger.error(f"{name}解析失败, content={content}, error={e}")
            raise RuntimeError(f"{name}解析失败")