"""SSE Emitter 管理器（支持历史缓冲 + 断点重放）

核心能力：
  - 每个 taskId 维护「有界历史缓冲」：消息 + 自增 seq，`send()` 先写历史再投递实时队列，
    无订阅者时历史也保留，供后续订阅者 `?after=` 断点重放。
  - `create_emitter(task_id, after_seq)`：在同步代码段内完成「回放 seq>after_seq 的历史 →
    注册实时队列」，以订阅时刻为界，保证每个 seq 恰好被该订阅者消费一次（不重不漏）。
  - SSE 帧升级为 `id: <seq>\ndata: <json>\n\n`，前端可记录 lastEventId 断线续传。
  - `complete()` 发送完成信号后清理队列与历史缓冲，释放内存。
"""
import asyncio
from collections import deque
from typing import Deque, Dict, Tuple

from fastapi.responses import StreamingResponse

from app.utils.logger import logger

# 每任务历史缓冲上限（条数）：超出丢最旧，防止流式片段过多占用进程内存
_HISTORY_MAXLEN = 2000


class SseEmitterManager:
    """SSE Emitter 管理器"""

    def __init__(self):
        # 存储所有的队列，key 为 taskId
        self._queues: Dict[str, asyncio.Queue] = {}
        # 每任务历史缓冲（可重放副本）：deque[(seq, message)]，有界，超限丢最旧
        self._history: Dict[str, Deque[Tuple[int, str]]] = {}
        # 每任务自增序号（seq 全局单调递增，供 ?after= 断点续传）
        self._seq: Dict[str, int] = {}

    def create_emitter(self, task_id: str, after_seq: int = 0) -> StreamingResponse:
        """创建 SSE Emitter，返回 StreamingResponse。

        订阅语义（保证「不重不漏」）：
          - 同步代码段内完成「重放历史(seq > after_seq) → 注册实时队列」，无 await 间隙；
          - 订阅前的事件只经重放路径送达、订阅后的事件只经实时路径送达：
              - send() 发生在注册实时队列之前 → 消息只进历史，由重放送达；
              - send() 发生在注册之后 → 消息进历史 + 实时队列，但重放已完成，只经实时路径送达。
        """
        queue: asyncio.Queue = asyncio.Queue()
        # 1) 先重放历史（同步，无 await 间隙）：seq > after_seq 的消息依序入队
        for seq, message in list(self._history.get(task_id, [])):
            if seq > after_seq:
                queue.put_nowait((seq, message))
        # 2) 再注册实时队列（订阅时刻边界）
        self._queues[task_id] = queue

        async def event_generator():
            try:
                while True:
                    # 从队列获取消息（会阻塞直到有消息）
                    seq, message = await queue.get()

                    # 收到完成信号，结束流
                    if message == "__COMPLETE__":
                        break

                    # 格式化为 SSE 格式推送给前端（带 id: <seq>，供断点续传）
                    yield f"id: {seq}\ndata: {message}\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                # 仅当仍是自己的队列时才清理，避免误删后来订阅者的队列
                if self._queues.get(task_id) is queue:
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
        """发送消息到队列：先写历史缓冲（可重放副本），再投递实时队列"""
        # 1) 写历史：无订阅者时也保留，供后续订阅者重放
        self._append_history(task_id, message)
        # 2) 投递实时队列
        queue = self._queues.get(task_id)
        if queue is None:
            return
        try:
            queue.put_nowait((self._seq[task_id], message))
        except Exception as e:
            logger.error("SSE 消息发送失败 taskId=%s, error=%s", task_id, str(e), exc_info=True)

    def _append_history(self, task_id: str, message: str) -> None:
        """追加一条历史记录并返回其 seq（内部自增序号，全局单调递增）"""
        seq = self._seq.get(task_id, 0) + 1
        self._seq[task_id] = seq
        hist = self._history.setdefault(task_id, deque(maxlen=_HISTORY_MAXLEN))
        hist.append((seq, message))

    def complete(self, task_id: str):
        """发送完成信号，关闭连接；同时清理历史缓冲与序号（释放内存）"""
        queue = self._queues.get(task_id)
        if queue is not None:
            try:
                queue.put_nowait((0, "__COMPLETE__"))
            except Exception as e:
                logger.error("SSE 完成信号发送失败 taskId=%s, error=%s", task_id, str(e), exc_info=True)
        # 清理历史缓冲与序号（释放内存）
        self._history.pop(task_id, None)
        self._seq.pop(task_id, None)

    def exists(self, task_id: str):
        """检查 Emitter 是否存在"""
        return task_id in self._queues


# 全局单例
sse_emitter_manager = SseEmitterManager()
