"""
文章异步任务服务
"""


import json
from typing import Any, Dict

from app.database import database
from app.models.enums import ArticleStatusEnum, SseMessageTypeEnum
from app.schemas.article import ArticleState
from app.services.article_agent_service import ArticleAgentService
from app.managers.sse_manager import sse_emitter_manager
from app.services.article_service import ArticleService
from app.utils.logger import logger


class ArticleAsyncService:
    """文章异步任务服务，提供下述服务：
    1. 执行异步文章生成，传入 task_id 参数
    """


    async def execute_article_generation(self, task_id: str, topic: str):
        """异步执行文章生成"""
        article_agent_service = ArticleAgentService()
        article_service = ArticleService(database)

        try:
            # 更新状态为处理中
            await article_service.update_article_status(task_id, ArticleStatusEnum.PROCESSING)

            # 创建状态对象
            state = ArticleState()
            state.task_id = task_id
            state.topic = topic

            logger.info("开始执行文章生成 taskId=%s, topic=%s", task_id, topic)

            # 执行智能体编排，通过 SSE 推送进度
            await article_agent_service.execute_article_generator(
                state,
                lambda message: self._handle_agent_message(task_id, message, state)
            )

            # 保存完整文章到数据库
            await article_service.save_article_content(task_id, state)

            # 更新状态为已完成
            await article_service.update_article_status(task_id, ArticleStatusEnum.COMPLETED)

            # 推送完成消息并关闭 SSE 连接
            self._send_sse_message(task_id, SseMessageTypeEnum.ALL_COMPLETE, {"taskId": task_id})
            sse_emitter_manager.complete(task_id)
            logger.info("文章生成完成 taskId=%s", task_id)
        except Exception as e:
            logger.error("异步任务失败 taskId=%s, error=%s", task_id, str(e), exc_info=True)
            await article_service.update_article_status(task_id, ArticleStatusEnum.FAILED, str(e))
            self._send_sse_message(task_id, SseMessageTypeEnum.ERROR, {"message": str(e)})
            sse_emitter_manager.complete(task_id)

    def _build_message_data(self, message: str, state: ArticleState) -> Dict[str, Any]:
        """构建要推送给前端的 SSE 消息数据。

        本函数是一个纯路由转换器：根据 message 的形态把它归类成「流式消息」或「完成消息」，
        并组装出对应的 dict；若都不命中则返回 None（由调用方丢弃）。它本身不产生副作用，
        不写 state、不发 SSE，便于单独测试。

        message 有两种形态：
            1) 流式消息：形如 f"{前缀}:{正文片段}"，前缀取自枚举的 get_streaming_prefix()，
               即 "{枚举值}:"。目前涉及三种前缀：
                 - "AGENT2_STREAMING:" 大纲流式片段
                 - "AGENT3_STREAMING:" 正文流式片段
                 - "IMAGE_COMPLETE:"   单张配图完成后的图片 URL
            2) 完成消息：恰好等于某个 SseMessageTypeEnum 的 value（裸标识符），
               例如 "AGENT1_COMPLETE" / "MERGE_COMPLETE" 等。

        Args:
            message: 智能体编排过程中通过回调产出的进度字符串，形态见上方说明。
            state: 贯穿整个编排过程的 ArticleState。仅当 message 命中「完成消息」时才会被读取，
                用来取出对应阶段已生成的产物（标题/大纲/配图/全文等）序列化进返回结果；
                流式消息分支不会使用 state。

        Returns:
            三种可能之一：
                - 流式消息命中：{"type": <枚举值>, "content": <剥掉前缀后的正文片段>}
                - 完成消息命中：{"type": <枚举值>, <阶段产物字段>: ...}（由 _build_complete_message_data 拼装）
                - 都未命中：None（调用方据此丢弃，不推送）
        """
        # 处理流式消息（带冒号分隔符）
        # 三个前缀形如 "AGENT2_STREAMING:"，用 startswith 做前缀匹配，命中后用切片剥离前缀只留正文。
        # 注意：startswith 是顺序短路判断，三个前缀互不为子串，可安全按此顺序依次判断。
        streaming_prefix2 = SseMessageTypeEnum.AGENT2_STREAMING.get_streaming_prefix()
        streaming_prefix3 = SseMessageTypeEnum.AGENT3_STREAMING.get_streaming_prefix()
        image_complete_prefix = SseMessageTypeEnum.IMAGE_COMPLETE.get_streaming_prefix()

        # 大纲流式片段：前端逐步渲染大纲结构
        if message.startswith(streaming_prefix2):
            return {
                "type": SseMessageTypeEnum.AGENT2_STREAMING.value,
                "content": message[len(streaming_prefix2):]
            }
        # 正文流式片段：前端逐步渲染正文内容
        if message.startswith(streaming_prefix3):
            return {
                "type": SseMessageTypeEnum.AGENT3_STREAMING.value,
                "content": message[len(streaming_prefix3):]
            }
        # 单张配图完成：content 为该章配图的图片 URL，前端立即展示
        if message.startswith(image_complete_prefix):
            return {
                "type": SseMessageTypeEnum.IMAGE_COMPLETE.value,
                "content": message[len(image_complete_prefix):]
            }

        # 处理完成消息（枚举值）：message 本身就是某个枚举的 value，
        # 交给 _build_complete_message_data 从 state 取对应阶段产物拼装返回。
        return self._build_complete_message_data(message, state)


    def _build_complete_message_data(self, message: str, state: ArticleState) -> Dict[str, Any]:
        """构建完成消息数据"""
        data = {}
        
        if message == SseMessageTypeEnum.AGENT1_COMPLETE.value:
            data["type"] = SseMessageTypeEnum.AGENT1_COMPLETE.value
            # HACK: 现在只生成一个候选标题
            # data["titleOptions"] = [
            #     item.model_dump(by_alias=True) for item in (state.title_options or [])
            # ]
            data["titleResult"] = state.title.model_dump(by_alias=True) if state.title else None
        elif message == SseMessageTypeEnum.AGENT2_COMPLETE.value:
            data["type"] = SseMessageTypeEnum.AGENT2_COMPLETE.value
            data["outline"] = [s.model_dump() for s in state.outline.sections] if state.outline else []
        elif message == SseMessageTypeEnum.AGENT3_COMPLETE.value:
            data["type"] = SseMessageTypeEnum.AGENT3_COMPLETE.value
        elif message == SseMessageTypeEnum.AGENT4_COMPLETE.value:
            data["type"] = SseMessageTypeEnum.AGENT4_COMPLETE.value
            data["imageRequirements"] = [
                req.model_dump(by_alias=True) for req in state.image_requirements
            ] if state.image_requirements else []
        elif message == SseMessageTypeEnum.AGENT5_COMPLETE.value:
            data["type"] = SseMessageTypeEnum.AGENT5_COMPLETE.value
            data["images"] = [
                img.model_dump(by_alias=True) for img in state.images
            ] if state.images else []
        elif message == SseMessageTypeEnum.MERGE_COMPLETE.value:
            data["type"] = SseMessageTypeEnum.MERGE_COMPLETE.value
            data["fullContent"] = state.full_content
        else:
            return None # type: ignore
        
        return data

    def _send_sse_message(
        self,
        task_id: str,
        type_enum: SseMessageTypeEnum,
        additional_data: Dict[str, Any]
    ):
        """发送 SSE 消息"""
        data = {"type": type_enum.value}
        data.update(additional_data)
        sse_emitter_manager.send(task_id, json.dumps(data, ensure_ascii=False))


    def _handle_agent_message(self, task_id: str, message: str, state: ArticleState):
        """处理智能体消息并推送"""
        data = self._build_message_data(message, state)
        if data is not None:
            sse_emitter_manager.send(task_id, json.dumps(data, ensure_ascii=False))


# 全局单例
article_async_service = ArticleAsyncService()