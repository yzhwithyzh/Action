"""任务状态存储 —— worker 对外汇报进度的唯一出口。

参考实现把状态直接写进 MySQL（`data_extraction_history` 等表 + 一整套 Service），
本仓库的 action-backend 里没有这些表，而且「实时进度」本来也不该每秒去写库。
所以这里把存储抽象成 `TaskStore` 接口，先给两个实现：

- `RedisTaskStore`  —— 生产用。状态/进度/日志/停止标志全在 Redis，后端直接读，天然支持 SSE。
- `MemoryTaskStore` —— 测试用。不需要起 Redis 就能跑完整生命周期。

将来要落 MySQL 做历史审计，再实现一个 `SqlTaskStore`（或写个双写的 `CompositeTaskStore`）
即可，worker 侧一行不用改。

Redis 键位（cfg.key(...) 统一加 `命名空间:工具名:` 前缀）：
    ...:task:{sid}          hash    状态快照，后端轮询这个
    ...:log:{sid}           list    日志行（LTRIM 限长），前端拉历史日志
    ...:log:channel:{sid}   pubsub  日志实时推送，SSE 订阅这个
    ...:stop:{sid}          string  停止标志，后端置位、worker 轮询
    ...:tasks:active        zset    在跑任务（score=开始时间戳），做监控用
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from redis import asyncio as aioredis

    from tools.common.worker_config import WorkerConfig

logger = logging.getLogger(__name__)

# 任务状态取值（与后端接口约定一致，别随手改字面量）
STATUS_PENDING = 'pending'
STATUS_RUNNING = 'running'
STATUS_COMPLETED = 'completed'
STATUS_FAILED = 'failed'
STATUS_STOPPED = 'stopped'

TERMINAL_STATUSES = frozenset({STATUS_COMPLETED, STATUS_FAILED, STATUS_STOPPED})


def now_ts() -> float:
    return time.time()


class TaskStore(ABC):
    """任务状态的读写接口。worker 只认这个接口，不认具体存储。"""

    @abstractmethod
    async def mark_running(self, session_id: str, meta: dict[str, Any] | None = None) -> None: ...

    @abstractmethod
    async def update_progress(
        self, session_id: str, current: int, total: int, stage: str = '', message: str = ''
    ) -> None: ...

    @abstractmethod
    async def append_logs(self, session_id: str, records: list[dict[str, Any]]) -> None: ...

    @abstractmethod
    async def mark_finished(
        self, session_id: str, status: str, *, result: dict[str, Any] | None = None, error: str = ''
    ) -> None: ...

    @abstractmethod
    async def get(self, session_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def fetch_logs(self, session_id: str, start: int = 0, end: int = -1) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def request_stop(self, session_id: str) -> None: ...

    @abstractmethod
    async def is_stop_requested(self, session_id: str) -> bool: ...

    @abstractmethod
    async def clear_stop(self, session_id: str) -> None: ...

    async def mark_completed(self, session_id: str, result: dict[str, Any]) -> None:
        await self.mark_finished(session_id, STATUS_COMPLETED, result=result)

    async def mark_failed(self, session_id: str, error: str) -> None:
        await self.mark_finished(session_id, STATUS_FAILED, error=error)

    async def mark_stopped(self, session_id: str, message: str = '任务已被停止') -> None:
        await self.mark_finished(session_id, STATUS_STOPPED, error=message)


class RedisTaskStore(TaskStore):
    """Redis 实现。所有写操作都吞异常并记日志 —— 汇报失败不该把任务本身弄挂。"""

    def __init__(self, cfg: WorkerConfig, client: aioredis.Redis) -> None:
        self.cfg = cfg
        self.redis = client

    # ------------------------------------------------------------------ 键位

    def task_key(self, session_id: str) -> str:
        return self.cfg.key('task', session_id)

    def log_key(self, session_id: str) -> str:
        return self.cfg.key('log', session_id)

    def log_channel(self, session_id: str) -> str:
        return self.cfg.key('log', 'channel', session_id)

    def stop_key(self, session_id: str) -> str:
        return self.cfg.key('stop', session_id)

    @property
    def active_key(self) -> str:
        return self.cfg.key('tasks', 'active')

    # ------------------------------------------------------------------ 写

    async def mark_running(self, session_id: str, meta: dict[str, Any] | None = None) -> None:
        fields: dict[str, Any] = {
            'session_id': session_id,
            'tool': self.cfg.tool_name,
            'status': STATUS_RUNNING,
            'progress_current': 0,
            'progress_total': 0,
            'stage': '',
            'message': '任务已开始',
            'error': '',
            'started_at': now_ts(),
            'updated_at': now_ts(),
            'finished_at': '',
        }
        for key, value in (meta or {}).items():
            fields[key] = value if isinstance(value, (str, int, float)) else json.dumps(value, ensure_ascii=False)
        try:
            pipe = self.redis.pipeline()
            pipe.hset(self.task_key(session_id), mapping={k: str(v) for k, v in fields.items()})
            pipe.expire(self.task_key(session_id), self.cfg.task_ttl)
            pipe.zadd(self.active_key, {session_id: now_ts()})
            await pipe.execute()
        except Exception as exc:
            logger.error('写任务状态失败 [%s]: %s', session_id, exc)

    async def update_progress(
        self, session_id: str, current: int, total: int, stage: str = '', message: str = ''
    ) -> None:
        try:
            await self.redis.hset(
                self.task_key(session_id),
                mapping={
                    'progress_current': str(current),
                    'progress_total': str(total),
                    'stage': stage,
                    'message': message,
                    'updated_at': str(now_ts()),
                },
            )
        except Exception as exc:
            logger.error('更新进度失败 [%s]: %s', session_id, exc)

    async def append_logs(self, session_id: str, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        lines = [json.dumps(r, ensure_ascii=False) for r in records]
        try:
            pipe = self.redis.pipeline()
            pipe.rpush(self.log_key(session_id), *lines)
            pipe.ltrim(self.log_key(session_id), -self.cfg.log_max_lines, -1)
            pipe.expire(self.log_key(session_id), self.cfg.task_ttl)
            for line in lines:
                pipe.publish(self.log_channel(session_id), line)
            await pipe.execute()
        except Exception as exc:
            logger.error('写日志失败 [%s]: %s', session_id, exc)

    async def mark_finished(
        self, session_id: str, status: str, *, result: dict[str, Any] | None = None, error: str = ''
    ) -> None:
        fields = {
            'status': status,
            'error': error,
            'updated_at': str(now_ts()),
            'finished_at': str(now_ts()),
        }
        if result is not None:
            fields['result'] = json.dumps(result, ensure_ascii=False)
        try:
            pipe = self.redis.pipeline()
            pipe.hset(self.task_key(session_id), mapping=fields)
            pipe.expire(self.task_key(session_id), self.cfg.task_ttl)
            pipe.zrem(self.active_key, session_id)
            pipe.delete(self.stop_key(session_id))
            await pipe.execute()
        except Exception as exc:
            logger.error('写结束状态失败 [%s]: %s', session_id, exc)

    # ------------------------------------------------------------------ 读

    async def get(self, session_id: str) -> dict[str, Any] | None:
        data = await self.redis.hgetall(self.task_key(session_id))
        if not data:
            return None
        for key in ('progress_current', 'progress_total'):
            if data.get(key):
                data[key] = int(float(data[key]))
        for key in ('started_at', 'updated_at', 'finished_at'):
            if data.get(key):
                data[key] = float(data[key])
        if data.get('result'):
            try:
                data['result'] = json.loads(data['result'])
            except json.JSONDecodeError:
                pass
        return data

    async def fetch_logs(self, session_id: str, start: int = 0, end: int = -1) -> list[dict[str, Any]]:
        raw = await self.redis.lrange(self.log_key(session_id), start, end)
        records = []
        for line in raw:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:  # noqa: PERF203 —— 一行坏日志不该让整段日志读不出来
                records.append({'level': 'info', 'message': line})
        return records

    # ------------------------------------------------------------------ 停止标志

    async def request_stop(self, session_id: str) -> None:
        await self.redis.set(self.stop_key(session_id), '1', ex=self.cfg.task_ttl)

    async def is_stop_requested(self, session_id: str) -> bool:
        try:
            return bool(await self.redis.get(self.stop_key(session_id)))
        except Exception as exc:
            # Redis 抖动时按「没停」处理：宁可多跑一会儿，也不要把正常任务误杀
            logger.error('查询停止标志失败 [%s]: %s', session_id, exc)
            return False

    async def clear_stop(self, session_id: str) -> None:
        await self.redis.delete(self.stop_key(session_id))


class MemoryTaskStore(TaskStore):
    """进程内实现，供单测与离线跑批使用（不需要 Redis）。"""

    def __init__(self) -> None:
        self.tasks: dict[str, dict[str, Any]] = {}
        self.logs: dict[str, list[dict[str, Any]]] = {}
        self.stops: set[str] = set()

    async def mark_running(self, session_id: str, meta: dict[str, Any] | None = None) -> None:
        self.tasks[session_id] = {
            'session_id': session_id,
            'status': STATUS_RUNNING,
            'progress_current': 0,
            'progress_total': 0,
            'stage': '',
            'message': '任务已开始',
            'error': '',
            'started_at': now_ts(),
            **(meta or {}),
        }

    async def update_progress(
        self, session_id: str, current: int, total: int, stage: str = '', message: str = ''
    ) -> None:
        task = self.tasks.setdefault(session_id, {'session_id': session_id})
        task.update(progress_current=current, progress_total=total, stage=stage, message=message, updated_at=now_ts())

    async def append_logs(self, session_id: str, records: list[dict[str, Any]]) -> None:
        self.logs.setdefault(session_id, []).extend(records)

    async def mark_finished(
        self, session_id: str, status: str, *, result: dict[str, Any] | None = None, error: str = ''
    ) -> None:
        task = self.tasks.setdefault(session_id, {'session_id': session_id})
        task.update(status=status, error=error, finished_at=now_ts())
        if result is not None:
            task['result'] = result
        self.stops.discard(session_id)

    async def get(self, session_id: str) -> dict[str, Any] | None:
        return self.tasks.get(session_id)

    async def fetch_logs(self, session_id: str, start: int = 0, end: int = -1) -> list[dict[str, Any]]:
        records = self.logs.get(session_id, [])
        return records[start:] if end == -1 else records[start : end + 1]

    async def request_stop(self, session_id: str) -> None:
        self.stops.add(session_id)

    async def is_stop_requested(self, session_id: str) -> bool:
        return session_id in self.stops

    async def clear_stop(self, session_id: str) -> None:
        self.stops.discard(session_id)
