"""Redis 队列管理器 —— worker 与后端之间唯一的任务通道。

后端只做一件事：`rpush(queue, json)`；worker 只做一件事：`blpop(queue)`。
两边不共享数据库连接、不互相 import，Redis 断了各自能独立重启。

同一个 Redis 连接会被队列、任务状态、日志三方共用（见 `BaseWorkerService`），
所以这里允许外部注入 client，也允许自己按配置建一个。
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from redis import asyncio as aioredis

if TYPE_CHECKING:
    from tools.common.worker_config import WorkerConfig

logger = logging.getLogger(__name__)


async def create_redis(cfg: WorkerConfig) -> aioredis.Redis:
    """按配置建一个 decode 好的异步 Redis 连接（health_check 防长连接被中间件掐断）。"""
    return await aioredis.from_url(
        cfg.redis_url,
        encoding='utf-8',
        decode_responses=True,
        health_check_interval=30,
    )


async def close_redis(client: aioredis.Redis | None) -> None:
    """兼容 redis-py 4/5+：新版本用 aclose()，老版本只有 close()。"""
    if client is None:
        return
    closer = getattr(client, 'aclose', None) or client.close
    await closer()


class RedisQueueManager:
    """任务队列的读写两端。后端进程只用 push_task，worker 只用 pop_task。"""

    def __init__(self, cfg: WorkerConfig, client: aioredis.Redis | None = None) -> None:
        self.cfg = cfg
        self.queue_name = cfg.queue_key
        self._client = client
        self._owns_client = client is None

    # ------------------------------------------------------------------ 连接

    async def connect(self) -> aioredis.Redis:
        """幂等连接，返回可复用的 client。"""
        if self._client is None:
            self._client = await create_redis(self.cfg)
            logger.info('已连接 Redis: %s:%s/%s', self.cfg.redis_host, self.cfg.redis_port, self.cfg.redis_db)
        return self._client

    async def disconnect(self) -> None:
        """只关自己建的连接；注入进来的连接由注入方负责关闭。"""
        if self._client is not None and self._owns_client:
            await close_redis(self._client)
            logger.info('已断开 Redis 连接')
        self._client = None

    # ------------------------------------------------------------------ 队列

    async def push_task(self, payload: dict[str, Any]) -> bool:
        """投递任务（供后端 / 脚本调用）。"""
        try:
            client = await self.connect()
            await client.rpush(self.queue_name, json.dumps(payload, ensure_ascii=False))
        except Exception as exc:
            logger.error('任务入队失败 [%s]: %s', payload.get('session_id'), exc)
            return False
        logger.info('任务已入队: %s → %s', payload.get('session_id'), self.queue_name)
        return True

    async def pop_task(self, timeout: int | None = None) -> dict[str, Any] | None:
        """阻塞取任务；超时返回 None（让主循环有机会检查关闭标志）。

        取到脏数据（非 JSON）时丢弃并继续 —— 一条坏消息不能把 worker 卡死。
        """
        timeout = self.cfg.pop_timeout if timeout is None else timeout
        client = await self.connect()
        result = await client.blpop(self.queue_name, timeout=timeout)
        if not result:
            return None
        _, raw = result
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.error('丢弃无法解析的队列消息: %.200s', raw)
            return None
        if not isinstance(payload, dict):
            logger.error('丢弃非对象的队列消息: %.200s', raw)
            return None
        return payload

    async def requeue_task(self, payload: dict[str, Any]) -> bool:
        """把任务塞回队首（优雅关闭时把还没开跑的任务还回去）。"""
        try:
            client = await self.connect()
            await client.lpush(self.queue_name, json.dumps(payload, ensure_ascii=False))
        except Exception as exc:
            logger.error('任务回队失败 [%s]: %s', payload.get('session_id'), exc)
            return False
        return True

    async def queue_length(self) -> int:
        try:
            client = await self.connect()
            return int(await client.llen(self.queue_name))
        except Exception as exc:
            logger.error('获取队列长度失败: %s', exc)
            return 0

    async def clear_queue(self) -> bool:
        """清空队列（危险，仅测试用）。"""
        try:
            client = await self.connect()
            await client.delete(self.queue_name)
        except Exception as exc:
            logger.error('清空队列失败: %s', exc)
            return False
        logger.warning('队列已清空: %s', self.queue_name)
        return True
