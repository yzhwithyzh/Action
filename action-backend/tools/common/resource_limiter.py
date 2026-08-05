"""资源限流器 —— 一个进程内的三级闸门。

- session：同时在跑几个任务（决定内存与工作目录占用）
- io：下载、PDF 解析这类 IO/CPU 动作（跨任务共享，避免 10 个任务同时解 50 个 PDF）
- llm：模型调用总数（跨任务共享，避免撞供应商限流）

三个信号量都是**进程级**的：多开一个 worker 进程就是多一份额度，扩容靠加进程。
参考实现里 session 槽位用 acquire/release 手工配对，漏 release 就永久少一个槽；
这里统一用 async context manager，异常路径也一定会还。
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class _Gate:
    """带用量统计的信号量。`_value` 是 asyncio 私有属性，这里自己记，不去读它。"""

    def __init__(self, name: str, total: int) -> None:
        self.name = name
        self.total = max(1, total)
        self.used = 0
        self._sem = asyncio.Semaphore(self.total)

    async def acquire(self) -> None:
        await self._sem.acquire()
        self.used += 1

    def release(self) -> None:
        self.used -= 1
        self._sem.release()

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        await self.acquire()
        try:
            yield
        finally:
            self.release()

    @property
    def semaphore(self) -> asyncio.Semaphore:
        """给需要直接传信号量的第三方库用（如引擎内部的并发控制）。"""
        return self._sem

    def stats(self) -> dict[str, int]:
        return {'total': self.total, 'used': self.used, 'free': self.total - self.used}


class ResourceLimiter:
    """三级闸门的持有者，由 WorkerService 建一份，传给每个 SessionTask。"""

    def __init__(
        self,
        max_concurrent_sessions: int = 3,
        max_concurrent_io: int = 10,
        max_concurrent_llm: int = 30,
    ) -> None:
        self.session = _Gate('session', max_concurrent_sessions)
        self.io = _Gate('io', max_concurrent_io)
        self.llm = _Gate('llm', max_concurrent_llm)

    @classmethod
    def from_config(cls, cfg: Any) -> ResourceLimiter:
        return cls(
            max_concurrent_sessions=cfg.max_concurrent_sessions,
            max_concurrent_io=cfg.max_concurrent_io,
            max_concurrent_llm=cfg.max_concurrent_llm,
        )

    # 三个语法糖，调用点读起来更像人话：`async with limiter.session_slot():`
    def session_slot(self) -> Any:
        return self.session.slot()

    def io_slot(self) -> Any:
        return self.io.slot()

    def llm_slot(self) -> Any:
        return self.llm.slot()

    def stats(self) -> dict[str, dict[str, int]]:
        return {'sessions': self.session.stats(), 'io': self.io.stats(), 'llm': self.llm.stats()}

    def summary(self) -> str:
        s = self.stats()
        return (
            f'sessions={s["sessions"]["used"]}/{s["sessions"]["total"]} '
            f'io={s["io"]["used"]}/{s["io"]["total"]} '
            f'llm={s["llm"]["used"]}/{s["llm"]["total"]}'
        )
