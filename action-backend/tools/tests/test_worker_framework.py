"""公共框架的行为测试 —— 不需要 Redis（用 MemoryTaskStore）。

    python -m pytest tools/tests -q
"""

import asyncio

import pytest

from tools.common.base_session_task import BaseSessionTask, TaskPayloadError
from tools.common.resource_limiter import ResourceLimiter
from tools.common.task_store import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_STOPPED,
    MemoryTaskStore,
)
from tools.common.worker_config import WorkerConfig


def make_cfg(tmp_path, **overrides):
    return WorkerConfig.from_env(
        tool_name='test_tool',
        base_dir=tmp_path,
        queue_name='test_queue',
        env_prefix='TEST_WORKER',
        **overrides,
    )


def run_task(task):
    return asyncio.run(task.run())


# --------------------------------------------------------------------------- 配置


def test_queue_key_and_task_keys_are_separate(tmp_path):
    cfg = make_cfg(tmp_path)
    # 队列 key 不含工具名（多进程共享一条队列），状态 key 含工具名（互不覆盖）
    assert cfg.queue_key == 'action_worker:queue:test_queue'
    assert cfg.key('task', 'abc') == 'action_worker:test_tool:task:abc'


def test_env_prefix_wins_over_generic(tmp_path, monkeypatch):
    monkeypatch.setenv('REDIS_HOST', 'generic-host')
    monkeypatch.setenv('TEST_WORKER_REDIS_HOST', 'tool-host')
    assert make_cfg(tmp_path).redis_host == 'tool-host'
    monkeypatch.delenv('TEST_WORKER_REDIS_HOST')
    assert make_cfg(tmp_path).redis_host == 'generic-host'


def test_password_is_masked_in_snapshot(tmp_path):
    cfg = make_cfg(tmp_path, redis_password='s3cret')
    snapshot = cfg.to_dict()
    assert snapshot['redis_password'] == '***'
    assert 's3cret' not in snapshot['redis_url']


# --------------------------------------------------------------------------- 任务生命周期


class OkTask(BaseSessionTask):
    task_type = 'ok'

    async def process(self):
        await self.report_progress(1, 2, 'work', '干到一半')
        (self.output_dir / 'artifact.txt').write_text('done', encoding='utf-8')
        return {'answer': 42}


class BoomTask(BaseSessionTask):
    task_type = 'boom'

    async def process(self):
        raise RuntimeError('炸了')


class ForeverTask(BaseSessionTask):
    task_type = 'forever'

    async def process(self):
        while True:
            await asyncio.sleep(0.01)
            await self.raise_if_stopped()


class BadPayloadTask(BaseSessionTask):
    task_type = 'bad'

    def validate(self):
        raise TaskPayloadError('缺少必填字段')

    async def process(self):
        return {}


def build(task_cls, tmp_path, store=None, **cfg_kwargs):
    store = store or MemoryTaskStore()
    cfg = make_cfg(tmp_path, **cfg_kwargs)
    task = task_cls(
        {'session_id': 's-1', 'user_id': 7},
        cfg=cfg,
        store=store,
        limiter=ResourceLimiter(1, 1, 1),
    )
    return task, store


def test_success_marks_completed_and_cleans_workdir(tmp_path):
    task, store = build(OkTask, tmp_path)
    result = run_task(task)

    assert result == {'answer': 42}
    state = store.tasks['s-1']
    assert state['status'] == STATUS_COMPLETED
    assert state['result'] == {'answer': 42}
    assert state['progress_current'] == 1
    # 成功后现场清理，断点也一并删掉
    assert not task.work_dir.exists()
    assert not task.checkpoint.dir.exists()
    # 结束事件必须发出去，否则前端 SSE 永远不断开
    assert store.logs['s-1'][-1]['level'] == 'completed'


def test_failure_marks_failed_and_keeps_workdir(tmp_path):
    task, store = build(BoomTask, tmp_path)
    assert run_task(task) is None

    state = store.tasks['s-1']
    assert state['status'] == STATUS_FAILED
    assert '炸了' in state['error']
    assert task.work_dir.exists(), '失败要留现场，方便断点续跑与排障'


def test_invalid_payload_fails_fast(tmp_path):
    task, store = build(BadPayloadTask, tmp_path)
    assert run_task(task) is None
    assert store.tasks['s-1']['status'] == STATUS_FAILED


def test_missing_session_id_is_rejected(tmp_path):
    cfg = make_cfg(tmp_path)
    with pytest.raises(TaskPayloadError):
        OkTask({}, cfg=cfg, store=MemoryTaskStore(), limiter=ResourceLimiter(1, 1, 1))


def test_stop_flag_stops_task(tmp_path):
    store = MemoryTaskStore()
    asyncio.run(store.request_stop('s-1'))
    task, store = build(ForeverTask, tmp_path, store=store, stop_check_interval=0)

    assert run_task(task) is None
    state = store.tasks['s-1']
    assert state['status'] == STATUS_STOPPED
    assert task.work_dir.exists(), '被停止时要留断点，重新入队可以续跑'


def test_watchdog_cancels_task_blocked_in_await(tmp_path):
    """业务卡在长 await 里（比如一次几分钟的模型调用）也要能停下来。"""

    class SleepyTask(BaseSessionTask):
        task_type = 'sleepy'

        async def process(self):
            await asyncio.sleep(30)  # 从不主动查停止标志
            return {}

    store = MemoryTaskStore()
    asyncio.run(store.request_stop('s-1'))
    task, store = build(SleepyTask, tmp_path, store=store, stop_check_interval=0)

    async def main():
        return await asyncio.wait_for(task.run(), timeout=5)

    assert asyncio.run(main()) is None
    assert store.tasks['s-1']['status'] == STATUS_STOPPED


def test_stopped_task_reports_progress_and_logs(tmp_path):
    task, store = build(OkTask, tmp_path)
    run_task(task)
    levels = [r['level'] for r in store.logs['s-1']]
    assert 'progress' in levels
    assert 'success' in levels


def test_progress_never_rewinds(tmp_path):
    """被节流跳过的旧进度晚到，不能把进度条刷回去（真出过这个 bug）。"""

    class ProgressTask(BaseSessionTask):
        task_type = 'progress'

        async def process(self):
            self.report_progress_nowait(5, 100, 'parse')  # 进后台队列，稍后才真正写
            self.report_progress_nowait(95, 100, 'judge')  # 距上一条太近，被节流丢弃
            await self.report_progress(100, 100, 'done')
            await asyncio.sleep(0)  # 给迟到的后台写一个执行机会
            return {}

    task, store = build(ProgressTask, tmp_path)
    run_task(task)
    assert store.tasks['s-1']['progress_current'] == 100


def test_expired_dirs_are_purged(tmp_path):
    """别的 session 留下的过期目录会被顺手清掉。"""
    import os
    import time

    cfg_kwargs = {'workdir_retention_days': 1}
    task, _ = build(OkTask, tmp_path, **cfg_kwargs)
    stale = task.cfg.temp_dir / 'old-session'
    stale.mkdir(parents=True)
    old = time.time() - 3 * 86400
    os.utime(stale, (old, old))

    run_task(task)
    assert not stale.exists()
