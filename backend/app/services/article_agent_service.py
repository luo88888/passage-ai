import json

from openai import AsyncOpenAI
from typing import Callable


from app.config import settings
from app.schemas.article import (
    ArticleState,
    TitleResult,
    OutlineSection,
    OutlineResult,
    ImageResult,
    ImageRequirement
)
from app.models.enums import (
    SseMessageTypeEnum,
    ImageMethodEnum
)
from app.constants.prompt import PromptConstant
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
        # self.cos_service = CosService()

    async def execute_article_generator(
        self,
        state: ArticleState,
        stream_handler: Callable[[str], None]
    ):
        """执行完整的文章生成流程"""
        try:
            # 智能体1：生成标题
            logger.info("智能体1-生成标题开始 taskId=%s", state.task_id)
            await self.agent1_generate_title(state)
            stream_handler(SseMessageTypeEnum.AGENT1_COMPLETE.value)

            # 智能体2：生成大纲（流式输出）
            logger.info("智能体2-生成大纲开始 taskId=%s", state.task_id)
            await self.agent2_generate_outline(state, stream_handler)
            stream_handler(SseMessageTypeEnum.AGENT2_COMPLETE.value)

            # 智能体3：生成正文（流式输出）
            logger.info("智能体3-生成正文开始 taskId=%s", state.task_id)
            await self.agent3_generate_content(state, stream_handler)
            stream_handler(SseMessageTypeEnum.AGENT3_STREAMING.value)

            # 智能体4：分析配图需求
            logger.info("智能体4-分析配图需求开始 taskId=%s", state.task_id)
            await self.agent4_analyze_image_requirements(state)
            stream_handler(SseMessageTypeEnum.AGENT4_COMPLETE.value)

            # 智能体5：生成配图
            logger.info("智能体5-生成配图开始 taskId=%s", state.task_id)
            await self.agent5_generate_images(state, stream_handler)
            stream_handler(SseMessageTypeEnum.AGENT5_COMPLETE.value)

            # 图文合并：将配图插入正文
            self.merge_image_into_content(state)
            stream_handler(SseMessageTypeEnum.MERGE_COMPLETE.value)
            logger.info("文章生成流程全部完成 taskId=%s", state.task_id)

        except Exception as e:
            logger.error("文章生成失败 taskId=%s, error=%s", state.task_id, str(e), exc_info=True)
            raise RuntimeError(f"文章生成失败：{str(e)}")


    async def agent1_generate_title(self, state: ArticleState):
        """智能体1：生成标题"""
        prompt = PromptConstant.AGENT1_TITLE_PROMPT.format(topic=state.topic)

        content = await self._call_llm(prompt)
        title_data = self._parse_json_response(content, "标题")
        state.title = TitleResult(**title_data)
        logger.info("智能体1-标题生成完成 taskId=%s, mainTitle=%s", state.task_id, state.title.main_title)

    async def agent2_generate_outline(
        self,
        state: ArticleState,
        stream_handler: Callable[[str], None]
    ):
        """智能体2：生成大纲（流式输出）"""
        assert state.title is not None
        prompt = PromptConstant.AGENT2_OUTLINE_PROMPT.format(
            mainTitle=state.title.main_title,
            subTitle=state.title.sub_title
        )

        print(f"智能体2提示词：{prompt}")

        content = await self._call_llm_with_streaming(
            prompt,
            stream_handler,
            SseMessageTypeEnum.AGENT2_STREAMING
        )
        from pprint import pprint
        print("智能体2输出：")
        pprint(content)

        outline_data = self._parse_json_response(content, "大纲")

        print("outline_data")
        pprint(outline_data)
        
        sections = [OutlineSection(**section) for section in outline_data["sections"]]
        state.outline = OutlineResult(sections=sections)
        logger.info("智能体2-大纲生成完成 taskId=%s, sectionsCount=%s", state.task_id, len(sections))

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

        content = await self._call_llm_with_streaming(
            prompt,
            stream_handler,
            SseMessageTypeEnum.AGENT3_STREAMING
        )

        state.content = content
        logger.info("智能体3-正文生成完成 taskId=%s, contentLength=%s", state.task_id, len(content))

    async def agent4_analyze_image_requirements(
        self,
        state: ArticleState
    ):
        """智能体4：分析配图需求"""
        assert state.title is not None
        prompt = PromptConstant.AGENT4_IMAGE_REQUIREMENTS_PROMPT.format(
            mainTitle = state.title.main_title,
            content = state.content
        )

        content = await self._call_llm(prompt)
        requirments_data = self._parse_json_response(content, "配图需求", is_list=True)
        state.image_requirements = [ImageRequirement(**req) for req in requirments_data]
        logger.info("智能体4-配图需求分析完成 taskId=%s, requirementsCount=%s", state.task_id, len(state.image_requirements))

    async def agent5_generate_images(
        self,
        state: ArticleState,
        stream_handler: Callable[[str], None]
    ):
        """智能体5：生成配图（串行执行）"""
        image_results = []
        assert state.image_requirements is not None
        for requirement in state.image_requirements:
            # 调用图片检索服务
            image_url = await self.pexels_service.search_image(requirement.keywords)

            # 降级策略：Pexels 失败时使用 Picsum 随机图片兜底
            method = self.pexels_service.get_method()
            if image_url is None:
                logger.warning("Pexels 检索失败，降级到 Picsum taskId=%s, keywords=%s, position=%s",
                               state.task_id, requirement.keywords, requirement.position)
                image_url = self.pexels_service.get_fallback_image(requirement.position)
                method = ImageMethodEnum.PICSUM

            # MVP 阶段直接使用图片 url，不上传到 COS
            # TODO: 生产阶段应实现图片持久化存储
            # final_image_url = self.cos_service.use_direct_url(image_url)
            final_image_url = image_url

            # 创建配图结果
            image_result = self._build_image_result(requirement, final_image_url, method)
            image_results.append(image_result)

            # 推送单张配图完成
            image_complete_message = (
                SseMessageTypeEnum.IMAGE_COMPLETE.get_streaming_prefix() +
                image_result.model_dump_json(by_alias=True)
            )
            stream_handler(image_complete_message)

        state.images = image_results
        logger.info("智能体5-配图生成完成 taskId=%s, imagesCount=%s", state.task_id, len(image_results))

    def merge_image_into_content(self, state: ArticleState):
        """图文合成：将配图插入正文对应位置"""
        content = state.content
        images = state.images

        if not images:
            state.full_content = content
            return

        full_content_lines = []

        # 按行处理正文，在章节标题后插入对应图片
        assert content is not None
        lines = content.split('\n')
        for line in lines:
            full_content_lines.append(line)

            if (line.startswith('## ')):
                section_title = line[3:].strip()
                # self._insert_image_after_section(full_content_lines, images, section_title)
                for image in images:
                    if image.section_title == section_title:
                        full_content_lines.append(f"![图片无法显示]({image.url})")

        state.full_content = "\n".join(full_content_lines)
        logger.info("图文合成完成 taskId=%s, fullContentLength=%s", state.task_id, len(state.full_content))

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
            # placeholderId=requirement.placeholder_id  # 第 5 期新增
        )