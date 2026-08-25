"""编排层单测：34 条目跑完 → 骨架 → 聚合 → 元信息，全程用假 runner。"""

from __future__ import annotations

import asyncio

from srd_engine import cache
from srd_engine.config import CRITERIA_VERSION, ENGINE_VERSION, EngineConfig, ModelConfig
from srd_engine.judge import BatchVerdicts
from srd_engine.pipeline import assess_from_extracts, guess_title, prepare_extract
from srd_engine.report import render_text, to_csv
from srd_engine.schemas import ExtractDoc, ItemVerdict, ParsedDoc, ParsedPage, TextFacet


class ConstantRunner:
    """所有条目都打同一个分的假 runner。"""

    def __init__(self, rating: str = '0'):
        self.cfg = ModelConfig(model='fake-model')
        self.rating = rating
        self.token_in = 1000
        self.token_out = 200
        self.calls = 0

    async def structured(self, schema, system, human, temperature=None):
        self.calls += 1
        if schema is BatchVerdicts:
            codes = [line.split('】')[0].replace('【评估条目 ', '') for line in human.splitlines()
                     if line.startswith('【评估条目 ')]
            return BatchVerdicts(
                verdicts=[
                    {'code': c, 'rating': self.rating, 'reason_zh': f'{c} 的理由'} for c in codes  # type: ignore[list-item]
                ]
            ), ''
        return ItemVerdict(rating=self.rating, reason_zh='理由'), ''  # type: ignore[arg-type]

    async def text(self, system, human, temperature=None):
        self.calls += 1
        return '证据若干', ''

    @staticmethod
    async def gather(tasks):
        return await asyncio.gather(*tasks)


def _assess(runner, cfg):
    a = ExtractDoc(title='综述A', sha256='aaa')
    b = ExtractDoc(title='综述B', sha256='bbb')
    return asyncio.run(assess_from_extracts(runner, a, b, cfg))


def test_default_all_mode_produces_all_34_items_and_a_score():
    runner = ConstantRunner('3')
    result = _assess(runner, EngineConfig())

    assert len(result.items) == 34
    assert {it.rating for it in result.items} == {'3'}
    assert result.overall_level == 'high'
    assert [d.pct for d in result.domains] == [100, 100, 100, 100]
    # 全 3 分 = 满分 = 满分重复
    assert (result.overall_score_sum, result.overall_score_max) == (102, 102)


def test_per_group_mode_uses_twelve_calls():
    runner = ConstantRunner('3')
    result = _assess(runner, EngineConfig(judge_granularity='per_group'))

    assert runner.calls == 12
    assert len(result.items) == 34
    assert {it.rating for it in result.items} == {'3'}


def test_metadata_is_recorded_for_reproducibility():
    runner = ConstantRunner('0')
    result = _assess(runner, EngineConfig())

    assert result.engine_version == ENGINE_VERSION
    assert result.criteria_version == CRITERIA_VERSION
    assert result.model == 'fake-model'
    assert result.judge_granularity == 'all'
    assert result.llm_calls == runner.calls
    assert result.review_a_title == '综述A'
    assert result.doc_b_sha256 == 'bbb'


def test_progress_callback_reports_every_item():
    seen: list[tuple[str, str]] = []
    runner = ConstantRunner('3')
    a, b = ExtractDoc(), ExtractDoc()
    asyncio.run(
        assess_from_extracts(
            runner, a, b, EngineConfig(),
            on_progress=lambda stage, done, total, detail: seen.append((stage, detail)),
        )
    )
    judged = [d for s, d in seen if s == 'judge']
    # 默认 all 模式一次判完，进度只报一次；逐条进度是 per_item 模式才有的
    assert len(judged) == 1
    assert seen[-1][0] == 'done'


def test_unclear_everywhere_marks_the_result_provisional():
    result = _assess(ConstantRunner('unclear'), EngineConfig())
    assert result.provisional is True
    assert result.unclear_count == 34
    assert all(d.level is None for d in result.domains)


# --------------------------------------------------------------------------- 报告渲染


def test_text_report_contains_the_decisive_numbers():
    result = _assess(ConstantRunner('3'), EngineConfig())
    text = render_text(result, verbose=True)

    assert 'SRD 系统综述重复性评估结果' in text
    assert '整体判定：高度重复' in text
    assert '总得分 102/102' in text
    assert '【关键领域】' in text
    assert '结论须由方法学专家确认' in text


def test_csv_export_has_one_row_per_item_plus_summary():
    result = _assess(ConstantRunner('2'), EngineConfig())
    rows = [r for r in to_csv(result).splitlines() if r.strip()]
    # 1 表头 + 34 条目 + 4 领域小计 + 1 整体
    assert len(rows) == 1 + 34 + 4 + 1
    assert rows[0].startswith('领域,关键领域,分组,条目')
    assert rows[-1].startswith('整体判定')


# --------------------------------------------------------------------------- 抽取缓存不许存残次品

DOC = ParsedDoc(sha256='deadbeef', page_count=1, pages=[ParsedPage(no=1, text='正文')])


def _noop(stage, done, total, detail):
    return None


def _fake_extract(result: ExtractDoc):
    """替掉 extract_doc，让 prepare_extract 拿到我们指定的抽取产物。"""

    async def fake(runner, doc, title='', cfg=None):
        return result, list(result.notes)

    return fake


def test_failed_extraction_is_not_cached(monkeypatch, tmp_path):
    """抽空的 facet 绝不能落盘。

    抽取是「一篇抽一次、34 条判定都吃这一份」，残缺的一份存下来，
    这篇参与的每一对配对都会从空壳里读，而且再也不会重抽。
    """
    broken = ExtractDoc(sha256='deadbeef', notes=['抽取批次 result 失败：无返回'])
    assert broken.failed_batches == ['result']
    monkeypatch.setattr('srd_engine.pipeline.extract_doc', _fake_extract(broken))

    _, warnings = asyncio.run(
        prepare_extract(ConstantRunner(), DOC, '标题', EngineConfig(), tmp_path, _noop, '综述A')
    )
    assert list(tmp_path.glob('*.json')) == []
    assert any('不写缓存' in w for w in warnings)


def test_complete_extraction_is_cached(monkeypatch, tmp_path):
    good = ExtractDoc(sha256='deadbeef', notes=['批次 topic：已剔除参考文献段 100 字符'])
    assert good.failed_batches == []          # 「剔除参考文献」是正常告警，不是失败
    monkeypatch.setattr('srd_engine.pipeline.extract_doc', _fake_extract(good))

    asyncio.run(prepare_extract(ConstantRunner(), DOC, '标题', EngineConfig(), tmp_path, _noop, '综述A'))
    assert len(list(tmp_path.glob('*.json'))) == 1


def test_poisoned_cache_from_an_older_run_is_ignored(monkeypatch, tmp_path):
    """0.7.0 之前存下来的残缺 facet：命中也要丢掉重抽，否则错误永远固化在缓存里。"""
    broken = ExtractDoc(sha256='deadbeef', notes=['抽取批次 result 返回空结果（字段全空）'])
    cache.save(tmp_path, DOC, 'fake-model', broken)
    assert len(list(tmp_path.glob('*.json'))) == 1

    fresh = ExtractDoc(sha256='deadbeef')
    fresh.topic.objective = TextFacet(value='评价针刺疗效', present='yes')
    monkeypatch.setattr('srd_engine.pipeline.extract_doc', _fake_extract(fresh))

    got, _ = asyncio.run(
        prepare_extract(ConstantRunner(), DOC, '标题', EngineConfig(), tmp_path, _noop, '综述A')
    )
    assert got.topic.objective.value == '评价针刺疗效'     # 用的是重抽的结果，不是缓存


# --------------------------------------------------------------------------- 标题猜测


def test_guess_title_picks_a_plausible_line():
    doc = ParsedDoc(
        page_count=1,
        pages=[ParsedPage(no=1, text='DOI: 10.1000/xyz\nAcupuncture for chronic low back pain: '
                                     'a systematic review and meta-analysis\nReceived 1 Jan 2024')],
    )
    assert guess_title(doc).startswith('Acupuncture for chronic')


def test_guess_title_returns_empty_for_empty_doc():
    assert guess_title(ParsedDoc()) == ''
