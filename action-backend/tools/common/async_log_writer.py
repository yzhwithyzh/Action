"""任务日志写入器 —— 一份日志三个去处：磁盘、Redis 列表（拉历史）、Redis 频道（SSE 实时）。

两个必须坚持的约束：
1. **调用点不阻塞**。业务代码 `log.info(...)` 只是往内存队列丢一条，落盘与推 Redis 由后台协程批量做。
2. **同步回调也能用**。引擎的 `on_progress` 是同步函数，没法 await，所以 `emit()` 是同步的，
   `write_*()` 只是它的 async 包装，方便在 async 代码里读起来顺。

`write_completed()` 会推一条 `level=completed` 的终止事件，前端 SSE 收到它就可以关连接 ——
否则前端只能靠轮询状态才知道该断开。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from tools.common.task_store import TaskStore

logger = logging.getLogger(__name__)

# 一次最多攒多少条再落盘，够大就不会被日志刷屏拖慢
BATCH_SIZE = 200


class AsyncLogWriter:
    """一个任务一个实例，由 BaseSessionTask 创建与关闭。"""

    def __init__(
        self,
        session_id: str,
        log_dir: Path,
        store: TaskStore | None = None,
        *,
        mirror: logging.Logger | None = None,
        filename: str = 'worker.log',
    ) -> None:
        self.session_id = session_id
        self.log_dir = log_dir
        self.store = store
        self.mirror = mirror
        self.log_path = log_dir / session_id / filename
        self._queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._consumer: asyncio.Task | None = None
        self._fh: Any = None
        self._closed = False

    # ------------------------------------------------------------------ 生命周期

    async def start(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = await asyncio.to_thread(self.log_path.open, 'a', encoding='utf-8')
        self._consumer = asyncio.create_task(self._consume(), name=f'logwriter-{self.session_id}')

    async def stop(self) -> None:
        """排空队列后关闭。已经关过就直接返回（finally 里会被重复调用）。"""
        if self._closed:
            return
        self._closed = True
        await self._queue.put(None)
        if self._consumer is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await self._consumer
        if self._fh is not None:
            await asyncio.to_thread(self._fh.close)
            self._fh = None

    # ------------------------------------------------------------------ 写入

    def emit(self, level: str, message: str, **extra: Any) -> None:
        """同步、非阻塞地投一条日志。供同步回调（如引擎进度回调）使用。"""
        if self._closed:
            return
        record = {
            'ts': time.time(),
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'session_id': self.session_id,
            'level': level,
            'message': message,
            **extra,
        }
        self._queue.put_nowait(record)
        if self.mirror is not None:
            self.mirror.log(_LOG_LEVELS.get(level, logging.INFO), '[%s] %s', self.session_id, message)

    async def write(self, level: str, message: str, **extra: Any) -> None:
        self.emit(level, message, **extra)

    async def write_info(self, message: str, **extra: Any) -> None:
        self.emit('info', message, **extra)

    async def write_success(self, message: str, **extra: Any) -> None:
        self.emit('success', message, **extra)

    async def write_warning(self, message: str, **extra: Any) -> None:
        self.emit('warning', message, **extra)

    async def write_error(self, message: str, **extra: Any) -> None:
        self.emit('error', message, **extra)

    async def write_progress(self, current: int, total: int, stage: str, message: str) -> None:
        self.emit('progress', message, stage=stage, current=current, total=total)

    async def write_completed(self, message: str = '任务已结束', status: str = 'completed') -> None:
        """终止事件：SSE 收到即可关闭连接。"""
        self.emit('completed', message, status=status)

    # ------------------------------------------------------------------ 后台消费

    async def _consume(self) -> None:
        while True:
            record = await self._queue.get()
            stop = record is None
            batch = [] if stop else [record]
            while len(batch) < BATCH_SIZE:  # 顺手把已经排队的一起收了
                try:
                    nxt = self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if nxt is None:
                    stop = True
                    break
                batch.append(nxt)
            if batch:
                await self._flush(batch)
            if stop:
                return

    async def _flush(self, batch: list[dict[str, Any]]) -> None:
        text = ''.join(f'{r["time"]} [{r["level"].upper()}] {r["message"]}\n' for r in batch)
        if self._fh is not None:
            try:
                await asyncio.to_thread(self._write_file, text)
            except Exception as exc:
                logger.error('日志落盘失败 [%s]: %s', self.session_id, exc)
        if self.store is not None:
            await self.store.append_logs(self.session_id, batch)

    def _write_file(self, text: str) -> None:
        self._fh.write(text)
        self._fh.flush()


_LOG_LEVELS = {
    'info': logging.INFO,
    'success': logging.INFO,
    'progress': logging.DEBUG,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'completed': logging.INFO,
}
