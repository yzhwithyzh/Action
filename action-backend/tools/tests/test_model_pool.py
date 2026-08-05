"""模型池的行为测试 —— 不连数据库、不连 Redis、不调模型。

覆盖三件事：
1. 错误分类（哪些该重试、哪些该换模型、哪些换了也没用）
2. 粘性轮换与 5 分钟冻结
3. 全池冻结时的等待与放弃

跑法：python -m pytest tools/tests/test_model_pool.py -q
"""

import asyncio

import pytest

from tools.common.worker_config import WorkerConfig
from tools.srd_worker_tool.config.worker_config import ensure_engine_importable

ensure_engine_importable()

from srd_engine.adapters.langchain_client import (  # noqa: E402
    DISABLE,
    FATAL,
    RETRY,
    SWITCH,
    AllModelsFrozenError,
    InMemoryModelHealth,
    LlmRunner,
    classify_error,
)
from srd_engine.config import FailoverConfig, ModelConfig  # noqa: E402

pytestmark = pytest.mark.filterwarnings('ignore::DeprecationWarning')


# --------------------------------------------------------------------------- 错误分类


class ApiError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


@pytest.mark.parametrize(
    ('exc', 'expected'),
    [
        (ApiError('Rate limit reached', 429), SWITCH),
        (ApiError('bad gateway', 502), SWITCH),
        (ApiError('server had an error', 500), SWITCH),
        (ApiError('Incorrect API key provided', 401), DISABLE),
        (ApiError('Insufficient Balance', 402), DISABLE),
        (ApiError('model not found', 404), DISABLE),
        # 400 里混着「余额不足」这类真该换模型的错，靠关键词捞出来
        (ApiError('Insufficient balance, please recharge', 400), DISABLE),
        (ApiError('invalid schema for tool', 400), FATAL),
        (ApiError('content filter triggered', 400), FATAL),
        (ApiError('风控拦截：内容审核不通过', 200), FATAL),
        (ApiError('账户已欠费', None), DISABLE),
        (ApiError('请求过于频繁，请稍后重试', None), SWITCH),
        (ConnectionResetError('connection reset by peer'), RETRY),
        (ApiError('something nobody has seen before', None), RETRY),
    ],
)
def test_classify_error(exc, expected):
    assert classify_error(exc) == expected


def test_unknown_errors_are_retryable_not_fatal():
    """认不出来的错误按可重试处理：重试用尽会自动升级成换模型，不会把整篇评估判死。"""
    assert classify_error(RuntimeError('???')) == RETRY


# --------------------------------------------------------------------------- 轮换与冻结


def pool(n=3):
    return [ModelConfig(provider='P', model=f'm{i}', api_key=f'k{i}', ref=str(i)) for i in range(1, n + 1)]


class FakeChatModel:
    """按剧本抛异常或返回结果的假模型。"""

    def __init__(self, name, script):
        self.name = name
        self.script = list(script)
        self.calls = 0

    async def ainvoke(self, messages):
        self.calls += 1
        step = self.script.pop(0) if self.script else 'ok'
        if isinstance(step, Exception):
            raise step
        return step

    def with_structured_output(self, schema, method=None, include_raw=False):
        return self


def make_runner(scripts, **kwargs):
    """scripts: {model_name: [异常或返回值, ...]}"""
    models = {name: FakeChatModel(name, script) for name, script in scripts.items()}
    runner = LlmRunner(
        pool(len(scripts)),
        max_concurrency=4,
        failover=FailoverConfig(freeze_seconds=300, all_frozen_wait=1, max_rounds=2, max_retries=2),
        **kwargs,
    )
    runner._model = lambda cfg, temperature: models[cfg.model]
    return runner, models


def test_sticky_stays_on_first_model_while_it_works():
    runner, models = make_runner({'m1': [], 'm2': [], 'm3': []})
    for _ in range(5):
        assert asyncio.run(runner.text('s', 'h'))[1] == ''
    assert (models['m1'].calls, models['m2'].calls, models['m3'].calls) == (5, 0, 0)
    assert runner.switches == []


def test_switches_to_next_model_on_rate_limit_and_freezes_the_bad_one():
    runner, models = make_runner({'m1': [ApiError('rate limit', 429)], 'm2': [], 'm3': []})
    _text, err = asyncio.run(runner.text('s', 'h'))

    assert err == '' and models['m2'].calls == 1
    assert len(runner.switches) == 1
    assert runner.switches[0]['from'].endswith('m1#1')
    assert runner.switches[0]['to'].endswith('m2#2')
    # 冻结是「未来 5 分钟内都别用它」，不是「这次调用别用它」
    assert asyncio.run(runner.health.frozen_seconds('1')) == pytest.approx(300, abs=2)
    assert asyncio.run(runner.text('s', 'h'))[1] == ''
    assert models['m1'].calls == 1, '冻结期内不该再碰它'


def test_rate_limit_is_not_retried_in_place():
    """限流原地重试只是继续撞墙，应该立刻换模型。"""
    runner, models = make_runner({'m1': [ApiError('rate limit', 429), ApiError('rate limit', 429)], 'm2': []})
    asyncio.run(runner.text('s', 'h'))
    assert models['m1'].calls == 1


def test_transient_errors_retry_on_the_same_model_first():
    """网络抖动不该白白烧掉一个模型：先原地重试，重试用尽才换。"""
    runner, models = make_runner({'m1': [ConnectionResetError('reset')], 'm2': []})
    assert asyncio.run(runner.text('s', 'h'))[1] == ''
    assert (models['m1'].calls, models['m2'].calls) == (2, 0)
    assert runner.switches == []


def test_fatal_errors_do_not_burn_the_pool():
    """请求本身有问题时换谁都一样，不该把所有模型挨个冻掉。"""
    runner, models = make_runner({'m1': [ApiError('content filter triggered', 400)], 'm2': [], 'm3': []})
    _, err = asyncio.run(runner.text('s', 'h'))

    assert 'content filter' in err
    assert models['m2'].calls == 0
    assert runner.switches == []
    assert asyncio.run(runner.health.frozen_seconds('1')) == 0


def test_frozen_model_returns_after_its_freeze_expires():
    health = InMemoryModelHealth()
    runner, models = make_runner({'m1': [ApiError('rate limit', 429)], 'm2': []}, health=health)
    asyncio.run(runner.text('s', 'h'))
    assert models['m2'].calls == 1

    # 5 分钟后解冻：m1 重新回到候选队列（这里直接把冻结记录抹掉模拟到期）
    health._until.clear()
    runner._frozen_until.clear()
    runner._checked_at.clear()
    runner._index = 0
    assert asyncio.run(runner.text('s', 'h'))[1] == ''
    assert models['m1'].calls == 2


def test_all_models_frozen_by_hard_errors_fails_fast():
    """鉴权/欠费等 5 分钟也不会好，不该占着任务空转。"""
    errors = [ApiError('Insufficient Balance', 402)] * 4
    runner, _ = make_runner({'m1': list(errors), 'm2': list(errors)})

    with pytest.raises(AllModelsFrozenError) as exc:
        asyncio.run(runner.text('s', 'h'))
    assert '等待无意义' in str(exc.value)
    assert 'Balance' in str(exc.value), '要带上真实原因，不能只说「全冻结」'


def test_all_models_frozen_by_rate_limit_waits_then_gives_up():
    """限流是会自愈的，值得等；但等超过上限就得判失败，不能挂死。"""
    errors = [ApiError('rate limit', 429)] * 4
    runner, _ = make_runner({'m1': list(errors), 'm2': list(errors)})

    events = []
    runner._on_event = lambda event, message: events.append(event)
    with pytest.raises(AllModelsFrozenError) as exc:
        asyncio.run(runner.text('s', 'h'))

    assert 'waiting' in events
    assert '已等待超过' in str(exc.value)


def test_pool_exhaustion_raises_instead_of_degrading_every_item():
    """一个模型都用不了时必须让任务失败，而不是产出一份「全 unclear」的报告。"""
    runner, _ = make_runner({'m1': [ApiError('rate limit', 429)] * 4})
    with pytest.raises(AllModelsFrozenError):
        asyncio.run(runner.structured(ModelConfig, 's', 'h'))


def test_pool_dedupes_by_ref():
    """同一个模型配两遍会让冻结与统计对不上账，构造时就去重。"""
    duplicated = [ModelConfig(model='m1', ref='1'), ModelConfig(model='m1', ref='1'), ModelConfig(model='m2', ref='2')]
    assert len(LlmRunner(duplicated).pool) == 2


def test_single_model_still_works_without_a_pool():
    runner = LlmRunner(ModelConfig(model='only', api_key='k'))
    assert runner.cfg.model == 'only'
    assert len(runner.pool) == 1


# --------------------------------------------------------------------------- 冻结表键位


def test_freeze_key_is_shared_across_tools(tmp_path):
    """模型健康状态属于模型而不属于某个工具：SRD 撞到的限流，别的工具也该躲开。"""
    srd = WorkerConfig.from_env(tool_name='srd_worker_tool', base_dir=tmp_path, queue_name='q')
    other = WorkerConfig.from_env(tool_name='other_worker_tool', base_dir=tmp_path, queue_name='q2')
    assert srd.llm_freeze_key('ai_models:3') == other.llm_freeze_key('ai_models:3')
    assert srd.llm_freeze_key('ai_models:3') == 'action_worker:llm:freeze:ai_models:3'


def test_model_types_filter_parsing(tmp_path):
    cfg = WorkerConfig.from_env(tool_name='t', base_dir=tmp_path, queue_name='q', model_types='chat, llm ,')
    assert cfg.model_type_list == ['chat', 'llm']
    assert WorkerConfig.from_env(tool_name='t', base_dir=tmp_path, queue_name='q').model_type_list == []
