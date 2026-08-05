"""端到端联调：真的连 Redis，跑完「投递 → worker 取任务 → 状态/日志/停止」整条链路。

本机没有 Redis 就自动跳过（CI 上起个 redis:7 容器即可）。
用 db 15 + 独立命名空间，绝不碰后端在用的 key。
"""

import asyncio

import pytest

from tools.common.base_session_task import BaseSessionTask
from tools.common.base_worker_service import BaseWorkerService
from tools.common.redis_queue_manager import close_redis, create_redis
from tools.common.task_client import TaskClient
from tools.common.task_store import STATUS_COMPLETED, STATUS_STOPPED
from tools.common.worker_config import WorkerConfig

TIMEOUT = 20


def make_cfg(tmp_path):
    return WorkerConfig.from_env(
        tool_name='it_tool',
        base_dir=tmp_path,
        queue_name='it_queue',
        namespace='action_worker_test',
        env_prefix='IT_WORKER',
        redis_db=15,
        max_concurrent_sessions=2,
        pop_timeout=1,
        stop_check_interval=1,
        shutdown_timeout=10,
    )


@pytest.fixture
def cfg(tmp_path):
    cfg = make_cfg(tmp_path)

    async def check_and_clean():
        client = await create_redis(cfg)
        try:
            await client.ping()
        except Exception as exc:
            await close_redis(client)
            pytest.skip(f'本机无可用 Redis，跳过联调测试: {exc}')
        keys = await client.keys(f'{cfg.namespace}:*')
        if keys:
            await client.delete(*keys)
        await close_redis(client)

    asyncio.run(check_and_clean())
    yield cfg
    asyncio.run(_cleanup(cfg))


async def _cleanup(cfg):
    client = await create_redis(cfg)
    keys = await client.keys(f'{cfg.namespace}:*')
    if keys:
        await client.delete(*keys)
    await close_redis(client)


class EchoTask(BaseSessionTask):
    task_type = 'echo'

    async def process(self):
        await self.report_progress(1, 2, 'echo', '处理中')
        seconds = float(self.payload.get('sleep') or 0)
        if seconds:
            await asyncio.sleep(seconds)
        return {'echo': self.payload.get('text', '')}


class EchoWorker(BaseWorkerService):
    task_cls = EchoTask


async def wait_for(client, session_id, statuses, timeout=TIMEOUT):
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        state = await client.status(session_id)
        if state and state.get('status') in statuses:
            return state
        await asyncio.sleep(0.1)
    pytest.fail(f'等待状态 {statuses} 超时，最后状态：{await client.status(session_id)}')
    return None


def test_end_to_end_submit_and_complete(cfg):
    async def scenario():
        worker = EchoWorker(cfg)
        runner = asyncio.create_task(worker.run())
        async with TaskClient(cfg) as client:
            sid = await client.submit({'text': '你好', 'user_id': 1})
            state = await wait_for(client, sid, {STATUS_COMPLETED})

            assert state['result'] == {'echo': '你好'}
            assert state['progress_current'] == 1
            logs = await client.logs(sid)
            assert logs[-1]['level'] == 'completed'
            assert any('任务开始' in r['message'] for r in logs)

            worker.request_shutdown()
            await asyncio.wait_for(runner, timeout=TIMEOUT)

    asyncio.run(scenario())


def test_end_to_end_stop_running_task(cfg):
    async def scenario():
        worker = EchoWorker(cfg)
        runner = asyncio.create_task(worker.run())
        async with TaskClient(cfg) as client:
            sid = await client.submit({'text': '慢活', 'sleep': 30})
            await wait_for(client, sid, {'running'})

            await client.stop(sid)
            state = await wait_for(client, sid, {STATUS_STOPPED})
            assert '停止' in state['error']

            worker.request_shutdown()
            await asyncio.wait_for(runner, timeout=TIMEOUT)

    asyncio.run(scenario())


def test_pending_state_visible_before_worker_starts(cfg):
    """提交完立刻查，必须能查到 pending —— 否则前端会闪一下「任务不存在」。"""

    async def scenario():
        async with TaskClient(cfg) as client:
            sid = await client.submit({'text': '排队'})
            state = await client.status(sid)
            assert state['status'] == 'pending'
            assert await client.queue_length() == 1

    asyncio.run(scenario())
