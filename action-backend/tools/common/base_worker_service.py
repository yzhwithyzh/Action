"""Worker 服务基类 —— 单进程异步调度器。

    class SrdWorkerService(BaseWorkerService):
        task_cls = SrdSessionTask

    asyncio.run(SrdWorkerService(CONFIG).run())

与参考实现的两点关键差异：

1. **先抢槽位再取任务**。参考实现是「blpop 拿到任务 → 再等 session 信号量」，
   于是队列里的积压会被搬进 worker 内存排队：worker 一重启这些任务就没了，
   横向扩容也没用（任务已经被这台机器占住）。这里反过来，槽位空出来才去 blpop，
   积压留在 Redis 里，谁有空谁取。

2. **关闭时把没开跑的任务还回队列**，不靠「反正会超时重来」。

心跳写在 `...:workers:{worker_id}`（带 TTL），运维可以直接 `redis-cli keys` 看有几个活的。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import signal
import socket
import time
from typing import TYPE_CHECKING, Any

from tools.common.base_session_task import TaskPayloadError
from tools.common.redis_queue_manager import RedisQueueManager, close_redis, create_redis
from tools.common.resource_limiter import ResourceLimiter
from tools.common.task_store import RedisTaskStore

if TYPE_CHECKING:
    from tools.common.base_session_task import BaseSessionTask
    from tools.common.task_store import TaskStore
    from tools.common.worker_config import WorkerConfig

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 15


class BaseWorkerService:
    """从 Redis 队列拉任务、并发执行、优雅关闭。"""

    #: 子类必须指定：本 worker 处理的任务类
    task_cls: type[BaseSessionTask]

    def __init__(self, cfg: WorkerConfig) -> None:
        self.cfg = cfg
        self.limiter = ResourceLimiter.from_config(cfg)
        self.queue = RedisQueueManager(cfg)
        self.store: TaskStore | None = None
        self.redis: Any = None
        self.running_tasks: set[asyncio.Task] = set()
        self.shutdown_flag = False
        self.worker_id = f'{socket.gethostname()}-{os.getpid()}'
        self._started_at = time.time()
        self._processed = 0
        self._failed = 0

    # ================================================================== 生命周期

    async def run(self) -> None:
        logger.info('=' * 60)
        logger.info('%s 启动中（worker_id=%s）', self.cfg.tool_name, self.worker_id)
        logger.info('队列: %s | 并发: %s', self.queue.queue_name, self.limiter.summary())
        logger.info('=' * 60)

        self.redis = await create_redis(self.cfg)
        self.queue = RedisQueueManager(self.cfg, self.redis)
        self.store = self.build_store()
        self._install_signal_handlers()
        heartbeat = asyncio.create_task(self._heartbeat_loop(), name='heartbeat')

        try:
            await self._main_loop()
        except KeyboardInterrupt:
            logger.info('收到 Ctrl+C，准备关闭')
        finally:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat
            await self.shutdown()

    async def _main_loop(self) -> None:
        while not self.shutdown_flag:
            # 先抢 session 槽位：没有空位就不去队列里抢任务，积压留在 Redis
            await self.limiter.session.acquire()
            if self.shutdown_flag:
                self.limiter.session.release()
                break

            payload = None
            try:
                payload = await self.queue.pop_task()
            except asyncio.CancelledError:
                self.limiter.session.release()
                raise
            except Exception as exc:
                logger.error('取任务失败: %s', exc)
                await asyncio.sleep(1)

            if payload is None:  # 超时空转或脏数据
                self.limiter.session.release()
                continue

            if self.shutdown_flag:  # 关闭途中取到的任务，还回队列让别人接
                await self.queue.requeue_task(payload)
                self.limiter.session.release()
                break

            task = asyncio.create_task(
                self._handle_payload(payload), name=f'session-{payload.get("session_id")}'
            )
            self.running_tasks.add(task)
            task.add_done_callback(self.running_tasks.discard)
            logger.info('任务已受理: %s（在跑 %d 个）', payload.get('session_id'), len(self.running_tasks))

    async def _handle_payload(self, payload: dict[str, Any]) -> None:
        """一个任务的完整生命周期；无论怎样都要还回 session 槽位。"""
        session_id = str(payload.get('session_id', 'unknown'))
        try:
            task = self.build_task(payload)
        except TaskPayloadError as exc:
            logger.error('任务参数不合法 [%s]: %s', session_id, exc)
            await self._mark_failed(session_id, f'任务参数不合法: {exc}')
            self.limiter.session.release()
            self._failed += 1
            return
        except Exception as exc:
            logger.exception('构造任务失败 [%s]', session_id)
            await self._mark_failed(session_id, f'构造任务失败: {type(exc).__name__}: {exc}')
            self.limiter.session.release()
            self._failed += 1
            return

        try:
            await task.run()
            self._processed += 1
        except asyncio.CancelledError:
            logger.info('任务被取消 [%s]', session_id)
            raise
        except Exception as exc:
            # BaseSessionTask.run 内部已兜过一层，走到这里说明兜底逻辑本身出了问题
            logger.exception('任务异常逃逸 [%s]', session_id)
            await self._mark_failed(session_id, f'{type(exc).__name__}: {exc}')
            self._failed += 1
        finally:
            self.limiter.session.release()
            logger.info('任务结束 [%s]，资源: %s', session_id, self.limiter.summary())

    async def _mark_failed(self, session_id: str, error: str) -> None:
        if self.store is not None:
            with contextlib.suppress(Exception):
                await self.store.mark_failed(session_id, error)

    async def shutdown(self) -> None:
        """优雅关闭：等在跑的任务跑完，超时才强杀。"""
        self.shutdown_flag = True
        logger.info('正在关闭 %s ...', self.cfg.tool_name)

        if self.running_tasks:
            logger.info('等待 %d 个任务完成（上限 %ds）', len(self.running_tasks), self.cfg.shutdown_timeout)
            pending = list(self.running_tasks)
            try:
                await asyncio.wait_for(
                    asyncio.gather(*pending, return_exceptions=True), timeout=self.cfg.shutdown_timeout
                )
                logger.info('全部任务已完成')
            except TimeoutError:
                logger.warning('等待超时，取消剩余任务（断点已保留，可重新入队）')
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)

        if self.redis is not None:
            with contextlib.suppress(Exception):
                await self.redis.delete(self._heartbeat_key)
        await self.queue.disconnect()
        await close_redis(self.redis)
        self.redis = None
        logger.info('%s 已停止', self.cfg.tool_name)

    def request_shutdown(self) -> None:
        """信号处理器入口：只置标志，真正的收尾在主循环退出后做。"""
        if not self.shutdown_flag:
            logger.info('收到停止信号，等待在跑任务收尾...')
        self.shutdown_flag = True

    # ================================================================== 可覆盖钩子

    def build_store(self) -> TaskStore:
        return RedisTaskStore(self.cfg, self.redis)

    def task_kwargs(self) -> dict[str, Any]:
        """给任务注入进程级依赖（模型健康表、对象存储客户端之类）。

        这些依赖的生命周期属于 worker 进程而不是单个任务，所以在这里建一次、每个任务共用；
        任务自己去 new 一份的话，连接数会随并发任务数一起涨。
        """
        return {}

    def build_task(self, payload: dict[str, Any]) -> BaseSessionTask:
        assert self.store is not None
        return self.task_cls(
            payload, cfg=self.cfg, store=self.store, limiter=self.limiter, **self.task_kwargs()
        )

    # ================================================================== 监控

    @property
    def _heartbeat_key(self) -> str:
        return self.cfg.key('workers', self.worker_id)

    def status(self) -> dict[str, Any]:
        return {
            'worker_id': self.worker_id,
            'tool': self.cfg.tool_name,
            'queue': self.queue.queue_name,
            'running': not self.shutdown_flag,
            'running_tasks': len(self.running_tasks),
            'processed': self._processed,
            'failed': self._failed,
            'uptime': round(time.time() - self._started_at, 1),
            'resources': self.limiter.stats(),
        }

    async def _heartbeat_loop(self) -> None:
        while True:
            try:
                await self.redis.set(
                    self._heartbeat_key,
                    json.dumps(self.status(), ensure_ascii=False),
                    ex=HEARTBEAT_INTERVAL * 3,
                )
            except Exception as exc:
                logger.debug('心跳写入失败: %s', exc)
            await asyncio.sleep(HEARTBEAT_INTERVAL)

    def _install_signal_handlers(self) -> None:
        """Windows 的 ProactorEventLoop 不支持 add_signal_handler，装不上就算了（靠 Ctrl+C）。"""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError, AttributeError, ValueError):
                loop.add_signal_handler(sig, self.request_shutdown)
