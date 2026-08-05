"""SRD 任务的行为测试 —— 不连 Redis、不调模型（assess 被替换成桩）。

跑法：python -m pytest tools/tests -q
"""

import asyncio

import pytest

from tools.common.model_registry import LlmModelInfo
from tools.common.resource_limiter import ResourceLimiter
from tools.common.task_store import STATUS_COMPLETED, MemoryTaskStore
from tools.common.worker_config import WorkerConfig
from tools.srd_worker_tool.worker_service import srd_session_task as mod
from tools.srd_worker_tool.worker_service.srd_session_task import SrdSessionTask

pytestmark = pytest.mark.filterwarnings('ignore::DeprecationWarning')


def fake_result():
    from srd_engine.schemas import AssessmentResult

    return AssessmentResult(
        review_a_title='综述A',
        review_b_title='综述B',
        doc_a_sha256='aaa',
        doc_b_sha256='bbb',
        overall_level='mod',
        overall_pct=55,
        overall_reason_zh='两篇在方法学上高度接近',
        engine_version=mod.ENGINE_VERSION,
        prompt_version=mod.PROMPT_VERSION,
        criteria_version=mod.CRITERIA_VERSION,
        model='fake-model',
        llm_calls=12,
        token_in=1000,
        token_out=500,
        unclear_count=3,
        review_count=1,
    )


@pytest.fixture
def env(tmp_path, monkeypatch):
    """一套隔离好的运行环境：结果目录、缓存目录、假 assess、假 ai_models 查询。"""
    monkeypatch.setenv('SRD_API_KEY', 'sk-test')
    monkeypatch.setattr(mod, 'RESULT_DIR', tmp_path / 'results')
    monkeypatch.setattr(mod, 'EXTRACT_CACHE_DIR', tmp_path / 'cache')

    calls = []
    db_models: list = []

    async def fake_assess(path_a, path_b, model_cfg=None, cfg=None, **kwargs):
        runner = kwargs.get('runner')
        calls.append({'a': path_a, 'b': path_b, 'engine': cfg, 'runner': runner,
                      'model': runner.cfg if runner is not None else model_cfg, **kwargs})
        on_progress = kwargs.get('on_progress')
        if on_progress:
            on_progress('parse', 2, 2, '')
            on_progress('judge', 34, 34, '')
        return fake_result()

    async def fake_load_llm_models(model_ids=None, model_types=None):
        """默认库里一个模型都没有 —— 想测模型池的用例自己往 db_models 里塞。"""
        if model_ids:
            return [m for m in db_models if m.model_id in model_ids]
        return list(db_models)

    monkeypatch.setattr(mod, 'assess', fake_assess)
    monkeypatch.setattr(mod, 'load_llm_models', fake_load_llm_models)

    pdf_a = tmp_path / 'a.pdf'
    pdf_b = tmp_path / 'b.pdf'
    pdf_a.write_bytes(b'%PDF-1.4 fake A')
    pdf_b.write_bytes(b'%PDF-1.4 fake B')
    return {'tmp': tmp_path, 'calls': calls, 'a': pdf_a, 'b': pdf_b, 'db_models': db_models}


def db_model(model_id, provider='DeepSeek', code='deepseek-chat', key='sk-db', **kwargs):
    return LlmModelInfo(
        model_id=model_id,
        provider=provider,
        model_code=code,
        model_name=code,
        api_key=key,
        base_url=kwargs.pop('base_url', 'https://api.deepseek.com/v1'),
        **kwargs,
    )


def build(env, store=None, payload_extra=None, **cfg_kwargs):
    cfg = WorkerConfig.from_env(
        tool_name='srd_worker_tool',
        base_dir=env['tmp'] / 'workdir',
        queue_name='srd_assessment',
        env_prefix='SRD_WORKER',
        max_concurrent_sessions=2,
        max_concurrent_llm=16,
        **cfg_kwargs,
    )
    payload = {
        'session_id': 'srd-1',
        'user_id': 3,
        'review_a': {'path': str(env['a']), 'title': '综述A'},
        'review_b': str(env['b']),
        **(payload_extra or {}),
    }
    store = store or MemoryTaskStore()
    return SrdSessionTask(payload, cfg=cfg, store=store, limiter=ResourceLimiter(1, 2, 4)), store


# --------------------------------------------------------------------------- 全流程


def test_full_run_writes_files_and_summary(env):
    task, store = build(env)
    summary = asyncio.run(task.run())

    assert summary['overall_level'] == 'mod'
    assert summary['overall_level_zh'] == '中度重复'
    assert summary['from_checkpoint'] is False
    assert summary['llm_calls'] == 12

    out_dir = mod.RESULT_DIR / 'srd-1'
    assert (out_dir / 'result.json').exists()
    assert (out_dir / 'report.csv').exists()
    assert (out_dir / 'report.txt').exists()

    state = store.tasks['srd-1']
    assert state['status'] == STATUS_COMPLETED
    assert state['result']['overall_pct'] == 55
    assert state['progress_current'] == 100, '引擎回调要能把进度推到 100'


def test_second_run_hits_checkpoint(env):
    """同一个 session 重跑：命中断点，一次模型都不调。"""
    task, _ = build(env)
    asyncio.run(task.run())
    assert len(env['calls']) == 1

    # 断点在成功后会被清掉，这里手工造一份「上次失败但结果已存」的现场
    task2, store2 = build(env)
    task2.checkpoint.save(mod.CHECKPOINT_RESULT, fake_result().model_dump(mode='json'))
    summary = asyncio.run(task2.run())

    assert summary['from_checkpoint'] is True
    assert len(env['calls']) == 1, '命中断点就不该再调引擎'
    assert store2.tasks['srd-1']['status'] == STATUS_COMPLETED


def test_checkpoint_ignored_when_version_differs(env):
    task, _ = build(env)
    stale = fake_result().model_dump(mode='json')
    stale['engine_version'] = 'srd-engine/0.0.1'
    task.checkpoint.save(mod.CHECKPOINT_RESULT, stale)

    summary = asyncio.run(task.run())
    assert summary['from_checkpoint'] is False, '版本不一致的旧结果不能复用'
    assert len(env['calls']) == 1


def test_force_option_ignores_checkpoint(env):
    task, _ = build(env, payload_extra={'options': {'force': True}})
    task.checkpoint.save(mod.CHECKPOINT_RESULT, fake_result().model_dump(mode='json'))
    summary = asyncio.run(task.run())
    assert summary['from_checkpoint'] is False
    assert len(env['calls']) == 1


# --------------------------------------------------------------------------- 参数处理


def test_missing_api_key_fails_fast(env, monkeypatch):
    monkeypatch.delenv('SRD_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    task, store = build(env)
    assert asyncio.run(task.run()) is None
    assert 'API key' in store.tasks['srd-1']['error']


def test_payload_model_overrides_env(env):
    task, _ = build(env, payload_extra={'model': {'provider': 'DeepSeek', 'model': 'deepseek-chat',
                                                  'api_key': 'sk-payload', 'base_url': ''}})
    asyncio.run(task.run())
    model_cfg = env['calls'][0]['model']
    assert (model_cfg.provider, model_cfg.model, model_cfg.api_key) == ('DeepSeek', 'deepseek-chat', 'sk-payload')
    assert model_cfg.base_url is None, '空串不该覆盖掉环境变量里的值'


def test_concurrency_is_clamped_to_llm_share(env):
    """每个任务分到 llm 总闸 / session 数；payload 要 100 也只给 8。"""
    task, _ = build(env, payload_extra={'engine': {'max_concurrency': 100}})
    asyncio.run(task.run())
    assert env['calls'][0]['engine'].max_concurrency == 8


# --------------------------------------------------------------------------- 模型池


def test_pool_comes_from_db_in_sort_order(env):
    """库里有模型就用库里的，顺序即轮询顺序；每条都带 ref，冻结才分得清是哪个账号。"""
    env['db_models'].extend([db_model(3), db_model(7, provider='Moonshot', code='kimi-k2')])
    task, store = build(env)
    summary = asyncio.run(task.run())

    pool = task._pool
    assert [c.model for c in pool] == ['deepseek-chat', 'kimi-k2']
    assert [c.ref for c in pool] == ['ai_models:3', 'ai_models:7']
    assert [c.api_key for c in pool] == ['sk-db', 'sk-db'], '密钥应来自库（已解密），不是环境变量'
    assert summary['model_pool_source'] == 'db'
    assert summary['model_pool'] == ['DeepSeek/deepseek-chat#ai_models:3', 'Moonshot/kimi-k2#ai_models:7']
    assert store.tasks['srd-1']['result']['model_pool_source'] == 'db'


def test_payload_model_ids_narrow_the_pool(env):
    env['db_models'].extend([db_model(3), db_model(7), db_model(9)])
    task, _ = build(env, payload_extra={'model_ids': [7, 9]})
    asyncio.run(task.run())
    assert [c.ref for c in task._pool] == ['ai_models:7', 'ai_models:9']


def test_payload_tuning_applies_to_every_pooled_model(env):
    """只给调参字段（不给 api_key）时，不该退化成单模型，而是套到池里每个模型上。"""
    env['db_models'].extend([db_model(3), db_model(7)])
    task, _ = build(env, payload_extra={'model': {'temperature': 0.7, 'max_tokens': 2048}})
    asyncio.run(task.run())

    assert len(task._pool) == 2
    assert {c.temperature for c in task._pool} == {0.7}
    assert {c.max_tokens for c in task._pool} == {2048}


def test_inline_model_with_key_skips_db(env):
    """payload 直接给了密钥就是一次性的临时模型，不查库也不轮换。"""
    env['db_models'].append(db_model(3))
    task, _ = build(env, payload_extra={'model': {'model': 'gpt-4o', 'api_key': 'sk-inline'}})
    asyncio.run(task.run())

    assert len(task._pool) == 1
    assert task._pool[0].api_key == 'sk-inline'
    assert task._pool_source == 'payload'


def test_db_failure_falls_back_to_env(env, monkeypatch):
    """库连不上不该让任务直接死 —— 环境变量里有密钥就接着跑，但要留下告警。"""
    async def boom(model_ids=None, model_types=None):
        raise RuntimeError('connection refused')

    monkeypatch.setattr(mod, 'load_llm_models', boom)
    task, store = build(env)
    assert asyncio.run(task.run()) is not None

    assert task._pool_source == 'env'
    assert task._pool[0].api_key == 'sk-test'
    messages = [r['message'] for r in store.logs['srd-1']]
    assert any('读取 ai_models 失败' in m for m in messages)


def test_freeze_settings_reach_the_runner(env):
    env['db_models'].extend([db_model(3), db_model(7)])
    task, _ = build(env, model_freeze_seconds=120, model_all_frozen_wait=240, model_max_rounds=3)
    asyncio.run(task.run())

    runner = env['calls'][0]['runner']
    assert (runner.failover.freeze_seconds, runner.failover.all_frozen_wait) == (120.0, 240.0)
    assert runner.failover.max_rounds == 3
    assert runner.health is task._model_health or runner.health is not None


def test_files_shorthand_and_missing_input(env):
    task, _ = build(env, payload_extra={'review_a': None, 'review_b': None,
                                        'files': [str(env['a']), str(env['b'])]})
    assert asyncio.run(task.run()) is not None

    task2, store = build(env, payload_extra={'review_a': None, 'review_b': None})
    assert asyncio.run(task2.run()) is None
    assert '缺少 review_a' in store.tasks['srd-1']['error']


def test_local_file_must_exist(env):
    task, store = build(env, payload_extra={'review_b': {'path': str(env['tmp'] / 'nope.pdf')}})
    assert asyncio.run(task.run()) is None
    assert '不存在' in store.tasks['srd-1']['error']


@pytest.mark.parametrize(
    ('url', 'expected'),
    [
        ('https://x.com/files/综述 A.pdf', '综述_A.pdf'),
        ('https://x.com/a/b.PDF', 'b.PDF'),
        ('https://x.com/download?id=9', 'download.pdf'),
        # 认不出来的后缀一律按 pdf 存：引擎只吃 PDF/TXT，留个奇怪后缀反而更难排查
        ('https://x.com/weird/name.verylongextension', 'name.pdf'),
    ],
)
def test_filename_from_url(url, expected):
    assert SrdSessionTask._filename_from_url(url) == expected
