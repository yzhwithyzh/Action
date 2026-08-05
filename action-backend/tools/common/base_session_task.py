"""会话任务基类 —— 一个任务从入队到落盘的完整骨架。

新增一个工具时，子类只需要回答三件事：

    class XxxSessionTask(BaseSessionTask):
        task_type = 'xxx'

        def validate(self) -> None:      # 可选：payload 校验，早失败早报错
            ...

        async def process(self) -> dict: # 必须：干活，返回结果摘要
            ...

基类负责的、每个工具都会重复写错的部分：
- 工作目录 / 断点目录的创建与过期清理
- 状态机（running → completed / failed / stopped）与状态上报
- 进度上报（含同步回调入口与写 Redis 的节流）
- 停止信号：后台每隔几秒查一次 Redis 标志，命中就取消主协程
- 日志写入器的启停，以及结束事件（前端 SSE 靠它断连）
- 失败时保留现场、成功时清理现场

关于取消语义的约定（踩过坑，别改）：
- 用户点停止 → 看门狗置 `_stop_requested` 再 cancel → 状态标 `stopped`，工作目录**保留**
- worker 优雅关闭时的 cancel → `_stop_requested` 为假 → 状态标 `failed`（错误写明是中断），
  且**必须把 CancelledError 重新抛出去**，否则 asyncio 会认为这个任务「拒绝了取消」。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import shutil
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from tools.common.async_log_writer import AsyncLogWriter
from tools.common.checkpoint_json_manager import CheckpointJsonManager
from tools.common.task_store import STATUS_COMPLETED, STATUS_FAILED, STATUS_STOPPED

if TYPE_CHECKING:
    from pathlib import Path

    from tools.common.resource_limiter import ResourceLimiter
    from tools.common.task_store import TaskStore
    from tools.common.worker_config import WorkerConfig

logger = logging.getLogger(__name__)

# 进度写 Redis 的最小间隔：判定阶段每条目都会回调，不节流会把 Redis 打成日志盘
PROGRESS_MIN_INTERVAL = 0.3


class TaskStopped(Exception):
    """用户主动停止。业务代码可以直接 `await self.raise_if_stopped()` 把它抛出来。"""


class TaskPayloadError(ValueError):
    """payload 不合法 —— 这类失败不该重试，直接标 failed。"""


class BaseSessionTask(ABC):
    """一次任务执行。实例不复用：重跑就新建一个。"""

    #: 子类覆盖，用于日志与结果里的类型标记
    task_type: str = 'task'
    #: 任务成功后是否删掉工作目录（失败/停止时一律保留，便于断点续跑与排障）
    cleanup_work_dir_on_success: bool = True

    def __init__(
        self,
        payload: dict[str, Any],
        *,
        cfg: WorkerConfig,
        store: TaskStore,
        limiter: ResourceLimiter,
    ) -> None:
        self.payload = payload
        self.cfg = cfg
        self.store = store
        self.limiter = limiter

        self.session_id: str = str(payload.get('session_id') or '').strip()
        if not self.session_id:
            raise TaskPayloadError('payload 缺少 session_id')
        self.user_id = payload.get('user_id')

        self.work_dir: Path = cfg.temp_dir / self.session_id
        self.input_dir: Path = self.work_dir / 'input'
        self.output_dir: Path = self.work_dir / 'output'

        self.checkpoint = CheckpointJsonManager(cfg.checkpoint_dir / self.session_id)
        self.log = AsyncLogWriter(self.session_id, cfg.logs_dir, store, mirror=logger)

        self._stop_requested = False
        self._stop_cached = False
        self._main_task: asyncio.Task | None = None
        self._watchdog: asyncio.Task | None = None
        self._bg_tasks: set[asyncio.Task] = set()
        self._last_progress_at = 0.0
        self._progress_seq = 0
        self._progress_last: tuple[int, int, str, str] | None = None
        self._started_at = 0.0

    # ================================================================== 子类接口

    @abstractmethod
    async def process(self) -> dict[str, Any]:
        """干活。返回结果摘要（会被 JSON 序列化进任务状态，别塞大对象）。"""

    def validate(self) -> None:
        """payload 校验。不合法请抛 `TaskPayloadError`。默认不校验。"""

    def task_meta(self) -> dict[str, Any]:
        """写进任务状态的静态信息（用户、输入文件名之类），供后端展示。"""
        return {'user_id': self.user_id, 'task_type': self.task_type}

    async def on_success(self, result: dict[str, Any]) -> None:
        """成功后的收尾钩子（记账、通知、上传等）。默认什么都不做。"""

    async def on_stopped(self) -> None:
        """用户停止后的收尾钩子。"""

    async def on_failure(self, exc: BaseException) -> None:
        """失败后的收尾钩子。"""

    # ================================================================== 主流程

    async def run(self) -> dict[str, Any] | None:
        """模板方法。返回结果摘要；被停止或失败时返回 None。"""
        self._main_task = asyncio.current_task()
        self._started_at = time.monotonic()
        result: dict[str, Any] | None = None
        cancelled: asyncio.CancelledError | None = None

        await self._setup()
        try:
            self.validate()
            await self.store.mark_running(self.session_id, self.task_meta())
            await self.log.write_info(f'▶ 任务开始：{self.task_type} / {self.session_id}')

            self._watchdog = asyncio.create_task(self._watch_stop(), name=f'stopwatch-{self.session_id}')
            result = await self.process()

            await self.store.mark_completed(self.session_id, result or {})
            await self.on_success(result or {})
            await self.log.write_success(f'✓ 任务完成，用时 {self.elapsed:.1f}s')
            await self.log.write_completed('任务已完成', status=STATUS_COMPLETED)

        except TaskStopped as exc:
            await self._handle_stopped(str(exc) or '任务已被停止')

        except asyncio.CancelledError as exc:
            cancelled = exc
            if self._stop_requested:
                await self._handle_stopped('任务已被停止')
            else:
                # worker 关闭导致的取消：如实标失败，任务可以重新入队再跑（断点还在）
                await self.store.mark_failed(self.session_id, 'worker 关闭，任务被中断')
                await self.log.write_warning('■ 任务被中断（worker 关闭），断点已保留')
                await self.log.write_completed('任务已中断', status=STATUS_FAILED)

        except Exception as exc:
            logger.exception('任务失败 [%s]', self.session_id)
            await self.store.mark_failed(self.session_id, f'{type(exc).__name__}: {exc}')
            await self.log.write_error(f'✗ 任务失败：{type(exc).__name__}: {exc}')
            await self.on_failure(exc)
            await self.log.write_completed('任务已失败', status=STATUS_FAILED)

        finally:
            await self._teardown(success=result is not None and not self._stop_requested)

        if cancelled is not None and not self._stop_requested:
            raise cancelled  # 尊重取消，别把 CancelledError 吞掉
        return result

    async def _handle_stopped(self, message: str) -> None:
        # 3.11+ 的取消状态是计数式的：吞掉 CancelledError 而不 uncancel，
        # 这个 Task 会一直是「取消中」，外层 gather 看到的状态就不对了。
        if self._main_task is not None and hasattr(self._main_task, 'uncancel'):
            self._main_task.uncancel()
        await self.store.mark_stopped(self.session_id, message)
        await self.log.write_warning(f'■ {message}，断点已保留，可重新入队续跑')
        await self.on_stopped()
        await self.log.write_completed('任务已停止', status=STATUS_STOPPED)

    # ================================================================== 准备与收尾

    async def _setup(self) -> None:
        for path in (self.input_dir, self.output_dir):
            path.mkdir(parents=True, exist_ok=True)
        await self.log.start()

    async def _teardown(self, *, success: bool) -> None:
        if self._watchdog is not None:
            self._watchdog.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._watchdog

        for task in list(self._bg_tasks):  # 等进度上报之类的零散协程收尾
            task.cancel()
        if self._bg_tasks:
            await asyncio.gather(*self._bg_tasks, return_exceptions=True)

        # 最后一条进度以「同步、必达」的方式补写一次：中间态被节流丢掉无所谓，
        # 但停在 95% 的进度条会让人以为任务卡住了
        if self._progress_last is not None:
            with contextlib.suppress(Exception):
                await self.store.update_progress(self.session_id, *self._progress_last)

        if success and self.cleanup_work_dir_on_success:
            await asyncio.to_thread(shutil.rmtree, self.work_dir, True)
            self.checkpoint.cleanup()
        elif not success:
            await self.log.write_info(f'现场已保留：{self.work_dir}')

        await self.log.stop()
        await asyncio.to_thread(self._purge_expired)

    def _purge_expired(self) -> None:
        """清掉别的 session 留下的过期目录（同步执行，放线程里跑）。"""
        cutoff_work = time.time() - self.cfg.workdir_retention_days * 86400
        cutoff_log = time.time() - self.cfg.log_retention_days * 86400
        for root, cutoff in ((self.cfg.temp_dir, cutoff_work), (self.cfg.checkpoint_dir, cutoff_work),
                             (self.cfg.logs_dir, cutoff_log)):
            if not root.exists():
                continue
            for entry in root.iterdir():
                if not entry.is_dir() or entry.name == self.session_id:
                    continue
                try:
                    if entry.stat().st_mtime < cutoff:
                        shutil.rmtree(entry, ignore_errors=True)
                except OSError:
                    continue

    # ================================================================== 进度

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._started_at

    async def report_progress(self, current: int, total: int, stage: str = '', message: str = '') -> None:
        self._progress_seq += 1
        self._progress_last = (current, total, stage, message)
        await self.store.update_progress(self.session_id, current, total, stage, message)
        await self.log.write_progress(current, total, stage, message or f'{stage} {current}/{total}')

    def report_progress_nowait(self, current: int, total: int, stage: str = '', message: str = '') -> None:
        """同步版本，供引擎的同步 on_progress 回调直接调用。

        日志一定进队列（不丢），写状态则按 `PROGRESS_MIN_INTERVAL` 节流 ——
        判定阶段每条目都回调，不节流会把 Redis 当日志盘用。
        """
        self.log.emit('progress', message or f'{stage} {current}/{total}',
                      stage=stage, current=current, total=total)
        self._progress_seq += 1
        self._progress_last = (current, total, stage, message)
        now = time.monotonic()
        if now - self._last_progress_at < PROGRESS_MIN_INTERVAL and current < total:
            return
        self._last_progress_at = now
        self._spawn(self._write_progress(self._progress_seq, current, total, stage, message))

    async def _write_progress(self, seq: int, current: int, total: int, stage: str, message: str) -> None:
        """后台写进度。落地前再确认一次自己还是最新的一条。

        这里踩过坑：被节流跳过的旧进度是「排队等事件循环」的协程，它可能在更晚的
        进度写完之后才真正执行，把 100% 又刷回 5%。序号校验挡的就是这种回退。
        """
        if seq != self._progress_seq:
            return
        await self.store.update_progress(self.session_id, current, total, stage, message)

    def _spawn(self, coro: Any) -> None:
        """起一个不等待结果的后台协程，并持有引用防止被 GC 提前回收。"""
        task = asyncio.ensure_future(coro)
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)

    # ================================================================== 停止信号

    async def should_stop(self) -> bool:
        """查一次停止标志（命中后缓存，不再回查 Redis）。"""
        if self._stop_cached:
            return True
        if await self.store.is_stop_requested(self.session_id):
            self._stop_cached = True
            return True
        return False

    async def raise_if_stopped(self) -> None:
        if await self.should_stop():
            self._stop_requested = True
            raise TaskStopped('任务已被停止')

    async def _watch_stop(self) -> None:
        """后台看门狗：轮询停止标志，命中就取消主协程。

        为什么要 cancel 而不是设个标志让业务自己查：业务大部分时间卡在模型调用里，
        不 cancel 的话用户点了停止还得等一轮 LLM 跑完（几分钟起步）。
        """
        while True:
            await asyncio.sleep(self.cfg.stop_check_interval)
            if await self.should_stop():
                self._stop_requested = True
                logger.info('检测到停止标志，取消任务 [%s]', self.session_id)
                if self._main_task is not None:
                    self._main_task.cancel()
                return
