import asyncio
from typing import Dict

from fastapi.responses import StreamingResponse

from app.utils.logger import logger


class SseEmitterManager:
    """SSE Emitter 管理器"""

    def __init__(self):
        # 存储所有的队列，key 为 taskId
        self._queues: Dict[str, asyncio.Queue] = {}

    def create_emitter(self, task_id: str) -> StreamingResponse:
        """创建 SSE Emitter，返回 StreamingResponse"""
        queue = asyncio.Queue()
        self._queues[task_id] = queue

        async def event_generator():
            try:
                while True:
                    # 从队列获取消息（会阻塞直到有消息）
                    message = await queue.get()

                    # 收到完成信号，结束流
                    if message == "__COMPLETE__":
                        break

                    # 格式化为 SSE 格式推送给前端
                    yield f"data: {message}\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                if task_id in self._queues:
                    del self._queues[task_id]
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"   # 禁用 Nginx 缓冲，确保实时推送
            }
        )

    def send(self, task_id: str, message: str):
        """发送消息到队列"""
        queue = self._queues.get(task_id)
        if queue is None:
            return

        try:
            queue.put_nowait(message)
        except Exception as e:
            logger.error("SSE 消息发送失败 taskId=%s, error=%s", task_id, str(e), exc_info=True)

    def complete(self, task_id: str):
        """发送完成信号，关闭连接"""
        queue = self._queues.get(task_id)
        if queue is None:
            return
        queue.put_nowait("__COMPLETE__")

    def exists(self, task_id: str):
        """检查 Emitter 是否存在"""
        return task_id in self._queues


# 全局单例
sse_emitter_manager = SseEmitterManager()