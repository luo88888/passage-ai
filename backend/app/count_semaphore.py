import asyncio

class AsyncCountingSemaphore:
    """可以观测排队数的 asyncio.Semaphore"""
    def __init__(self, value: int):
        self._sem = asyncio.Semaphore(value)
        self._waiting = 0
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        async with self._lock:
            self._waiting += 1
        try:
            await self._sem.acquire()
        except BaseException:
            # 如果获取信号量失败或被取消，必须把等待计数减回去
            async with self._lock:
                self._waiting -= 1
            raise
        async with self._lock:
            self._waiting -= 1
        return self

    async def __aexit__(self, *args):
        self._sem.release()

    @property
    def waiting_count(self) -> int:
        return self._waiting

