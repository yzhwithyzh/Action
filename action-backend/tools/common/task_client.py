"""任务客户端 —— 给「投递方」用的那一半 API（后端接口、运维脚本、测试都用它）。

后端接入 worker 只需要这个类，不需要 import 任何 worker 内部实现：

    client = TaskClient(SRD_CONFIG)
    session_id = await client.submit({'review_a': ..., 'review_b': ..., 'model': {...}})
    state = await client.status(session_id)          # 轮询
    async for record in client.subscribe_logs(sid):  # 或者 SSE 实时推
        yield record
    await client.stop(session_id)                    # 用户点「停止」

`submit` 会先把任务状态写成 pending 再入队 —— 顺序反了的话，worker 可能比状态先落地，
前端刚提交就查到「任务不存在」。
"""

from __future__ import annotations

import contextlib
import json
import time
import uuid
from typing import TYPE_CHECKING, Any

from tools.common.redis_queue_manager import RedisQueueManager, close_redis, create_redis
from tools.common.task_store import STATUS_PENDING, RedisTaskStore

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from tools.common.worker_config import WorkerConfig


class TaskClient:
    """一个工具（一条队列）的投递端。线程安全性同 redis-py：一个事件循环用一个实例。"""

    def __init__(self, cfg: WorkerConfig) -> None:
        self.cfg = cfg
        self._redis: Any = None
        self._queue: RedisQueueManager | None = None
        self._store: RedisTaskStore | None = None

    async def connect(self) -> None:
        if self._redis is None:
            self._redis = await create_redis(self.cfg)
            self._queue = RedisQueueManager(self.cfg, self._redis)
            self._store = RedisTaskStore(self.cfg, self._redis)

    async def close(self) -> None:
        await close_redis(self._redis)
        self._redis = None
        self._queue = None
        self._store = None

    async def __aenter__(self) -> TaskClient:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # ------------------------------------------------------------------ 投递

    async def submit(self, payload: dict[str, Any], session_id: str | None = None) -> str:
        """入队一个任务，返回 session_id。"""
        await self.connect()
        assert self._queue is not None and self._store is not None
        sid = session_id or str(payload.get('session_id') or uuid.uuid4())
        payload = {**payload, 'session_id': sid, 'submitted_at': time.time()}

        await self._redis.hset(
            self._store.task_key(sid),
            mapping={
                'session_id': sid,
                'tool': self.cfg.tool_name,
                'status': STATUS_PENDING,
                'progress_current': '0',
                'progress_total': '0',
                'message': '排队中',
                'error': '',
                'created_at': str(time.time()),
            },
        )
        await self._redis.expire(self._store.task_key(sid), self.cfg.task_ttl)
        await self._queue.push_task(payload)
        return sid

    # ------------------------------------------------------------------ 查询与控制

    async def status(self, session_id: str) -> dict[str, Any] | None:
        await self.connect()
        assert self._store is not None
        return await self._store.get(session_id)

    async def logs(self, session_id: str, start: int = 0, end: int = -1) -> list[dict[str, Any]]:
        await self.connect()
        assert self._store is not None
        return await self._store.fetch_logs(session_id, start, end)

    async def stop(self, session_id: str) -> None:
        """请求停止。worker 最多 `stop_check_interval` 秒后响应。"""
        await self.connect()
        assert self._store is not None
        await self._store.request_stop(session_id)

    async def queue_length(self) -> int:
        await self.connect()
        assert self._queue is not None
        return await self._queue.queue_length()

    async def subscribe_logs(self, session_id: str, *, replay: bool = True) -> AsyncIterator[dict[str, Any]]:
        """订阅日志，收到 `level=completed` 后自行结束 —— 正好可以直接接 SSE。

        顺序是「先订阅、再补历史」：反过来的话，补历史那一瞬间产生的日志会永久丢失。
        代价是补历史与实时流可能重叠，用时间戳去重（比丢日志好处理得多）。
        `replay=False` 则只要订阅之后的新日志。
        """
        await self.connect()
        assert self._store is not None
        channel = self._store.log_channel(session_id)
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            last_ts = 0.0
            if replay:
                for record in await self._store.fetch_logs(session_id):
                    last_ts = max(last_ts, float(record.get('ts') or 0))
                    yield record
                    if record.get('level') == 'completed':
                        return

            async for message in pubsub.listen():
                if message.get('type') != 'message':
                    continue
                try:
                    record = json.loads(message['data'])
                except (TypeError, json.JSONDecodeError):
                    continue
                if float(record.get('ts') or 0) <= last_ts:
                    continue  # 补历史时已经发过
                yield record
                if record.get('level') == 'completed':
                    return
        finally:
            with contextlib.suppress(Exception):
                await pubsub.unsubscribe(channel)
                closer = getattr(pubsub, 'aclose', None) or pubsub.close
                await closer()
