"""图节点 → SSE 桥接

提供图节点构造传给智能体的 stream_handler 闭包。

make_emit(task_id, state) 返回一个 Callable[[str], None]：
  - 形如 "AGENT2_STREAMING:片段" / "AGENT3_STREAMING:片段" / "IMAGE_COMPLETE:url" 的流式消息
    → 包装成 {"type":<枚举值>, "content":<剥前缀正文>}
  - 恰好等于枚举 value 的完成消息
    → 由 _build_complete_message_data 从 state 取阶段产物拼装
  - 推送到 sse_emitter_manager（以 task_id 为 key 的全局队列）

闭包按引用捕获 state（Pydantic model），智能体就地修改后完成事件能读到最新产物。
"""
import json
from typing import Any, Callable, Dict

from app.managers.sse_manager import sse_emitter_manager
from app.models.enums import SseMessageTypeEnum
from app.schemas.article import ArticleState
from app.utils.logger import logger


def _build_message_data(message: str, state: ArticleState) -> Dict[str, Any]:
    """构建 SSE 消息数据（纯路由转换，无副作用）。

    message 两种形态：
      1) 流式：f"{前缀}:{正文片段}"，前缀为 "{枚举值}:"（AGENT2_STREAMING/AGENT3_STREAMING/IMAGE_COMPLETE）
      2) 完成：恰好等于某 SseMessageTypeEnum 的 value（裸标识符）
    """
    streaming_prefix2 = SseMessageTypeEnum.AGENT2_STREAMING.get_streaming_prefix()
    streaming_prefix3 = SseMessageTypeEnum.AGENT3_STREAMING.get_streaming_prefix()
    image_complete_prefix = SseMessageTypeEnum.IMAGE_COMPLETE.get_streaming_prefix()

    if message.startswith(streaming_prefix2):
        return {
            "type": SseMessageTypeEnum.AGENT2_STREAMING.value,
            "content": message[len(streaming_prefix2):],
        }
    if message.startswith(streaming_prefix3):
        return {
            "type": SseMessageTypeEnum.AGENT3_STREAMING.value,
            "content": message[len(streaming_prefix3):],
        }
    if message.startswith(image_complete_prefix):
        return {
            "type": SseMessageTypeEnum.IMAGE_COMPLETE.value,
            "content": message[len(image_complete_prefix):],
        }

    return _build_complete_message_data(message, state)


def _build_complete_message_data(message: str, state: ArticleState) -> Dict[str, Any]:
    """构建完成消息数据：从 state 取对应阶段产物"""
    data: Dict[str, Any] = {}

    if message == SseMessageTypeEnum.AGENT1_COMPLETE.value:
        data["type"] = SseMessageTypeEnum.AGENT1_COMPLETE.value
        data["titleOptions"] = [
            item.model_dump(by_alias=True) for item in (state.title_options or [])
        ]
    elif message == SseMessageTypeEnum.AGENT2_COMPLETE.value:
        data["type"] = SseMessageTypeEnum.AGENT2_COMPLETE.value
        data["outline"] = [s.model_dump() for s in state.outline.sections] if state.outline else []
    elif message == SseMessageTypeEnum.AGENT3_COMPLETE.value:
        # NOTE: 此处可携带完整正文，在一定程度上缓解正文生成阶段历史缓冲把最早的流式片段挤掉的问题
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
        logger.error("未知完成消息: %s", message)
        return None  # type: ignore

    return data


def make_emit(task_id: str, state: ArticleState) -> Callable[[str], None]:
    """构造传给智能体 run() 的 stream_handler 闭包。

    智能体就地修改后完成事件能读到最新产物。
    """
    def emit(message: str) -> None:
        """智能体流式回调：把裸消息转换为 SSE 数据并推送到全局队列。

        闭包按引用捕获 task_id 与 state（智能体就地修改后完成事件能读到最新产物），
        消息两种形态：
          - 流式：f"{枚举值}:{正文片段}" → 剥前缀为 {"type", "content"}
          - 完成：恰好等于某 SseMessageTypeEnum 的 value → 从 state 取阶段产物拼装
        若 _build_message_data 返回 None（未知完成消息）则静默忽略，不推送。

        Args:
            message: 智能体传出的原始消息（流式带前缀 / 完成裸标识符）。
        """
        data = _build_message_data(message, state)
        if data is not None:
            sse_emitter_manager.send(task_id, json.dumps(data, ensure_ascii=False))

    return emit


def send_sse_message(task_id: str, type_enum: SseMessageTypeEnum, additional_data: Dict[str, Any]) -> None:
    """发送裸 {type, ...} SSE 消息（用于人机协同/收尾事件 TITLE_GENERATED/OUTLINE_GENERATED/ALL_COMPLETE/ERROR）"""
    data = {"type": type_enum.value}
    data.update(additional_data)
    sse_emitter_manager.send(task_id, json.dumps(data, ensure_ascii=False))