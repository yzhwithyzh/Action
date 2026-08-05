"""判定层单测 —— 用假 runner 验证批量判定，不调真实模型。

可靠性阶梯（k=2 投票 + 仲裁 + 双证据辩护）已删除，实测依据见 `judge.py` 模块 docstring：
它的自一致率与单次调用完全相同（都是 95%），76 次调用没有换来更稳的输出。
这里覆盖剩下的三件事：

- 一次调用给完给定条目的评分，逐条落到对应的 ItemResult
- 模型少返条目（输出截断）→ 补成 unclear + needs_review，绝不静默
- 调用整体失败 → 全部条目降级，错误信息进 review_note
"""

from __future__ import annotations

import asyncio

from srd_engine.checklist import ALL_ITEMS, ITEM_BY_CODE
from srd_engine.config import EngineConfig, ModelConfig
from srd_engine.judge import BatchVerdicts, CodedVerdict, judge_batch
from srd_engine.schemas import ExtractDoc, ListFacet


class FakeRunner:
    """按调用顺序吐预设结果的假 runner。"""

    def __init__(self, structured=()):
        self.cfg = ModelConfig(model='fake')
        self._structured = list(structured)
        self.structured_calls: list[tuple[str, float]] = []
        self.token_in = self.token_out = self.calls = 0

    async def structured(self, schema, system, human, temperature=None):
        self.calls += 1
        self.structured_calls.append((human, temperature or 0.0))
        return self._structured.pop(0) if self._structured else (None, '没有更多预设结果')

    @staticmethod
    async def gather(tasks):
        return await asyncio.gather(*tasks)


def _coded(code: str, v: str, reason: str = '理由') -> CodedVerdict:
    return CodedVerdict(code=code, rating=v, reason_zh=reason)  # type: ignore[arg-type]


def _run(coro):
    return asyncio.run(coro)


CFG = EngineConfig()
ITEMS = [ITEM_BY_CODE[c] for c in ('2b', '3a', '7c')]


def test_one_call_judges_every_item():
    runner = FakeRunner(structured=[(
        BatchVerdicts(verdicts=[_coded('2b', '0', 'A'), _coded('3a', '2', 'B'),
                                _coded('7c', 'unclear', 'C')]), '')])
    results = _run(judge_batch(runner, ITEMS, ExtractDoc(), ExtractDoc(), CFG))

    assert runner.calls == 1                                   # 三条目只发一次
    assert [r.code for r in results] == ['2b', '3a', '7c']     # 顺序与传入一致
    assert [r.effective_rating for r in results] == ['0', '2', 'unclear']
    assert [r.score for r in results] == [0, 2, None]
    assert [r.reason_zh for r in results] == ['A', 'B', 'C']
    assert all(not r.needs_review for r in results)


def test_all_34_items_fit_in_a_single_call():
    runner = FakeRunner(structured=[(
        BatchVerdicts(verdicts=[_coded(it.code, '3') for it in ALL_ITEMS]), '')])
    results = _run(judge_batch(runner, list(ALL_ITEMS), ExtractDoc(), ExtractDoc(), CFG))

    assert runner.calls == 1
    assert len(results) == 34
    assert all(r.rating == '3' for r in results)
    # 每个条目的题目都进了同一条提示词
    human = runner.structured_calls[0][0]
    for it in ALL_ITEMS:
        assert f'【评估条目 {it.code}】' in human


def test_missing_items_are_filled_as_unclear_and_flagged():
    """输出被截断时模型会少返条目 —— 少返的必须补齐并标待复核，不能静默丢。"""
    runner = FakeRunner(structured=[(
        BatchVerdicts(verdicts=[_coded('2b', '0')]), '')])            # 只返 1/3
    results = _run(judge_batch(runner, ITEMS, ExtractDoc(), ExtractDoc(), CFG))

    assert [r.code for r in results] == ['2b', '3a', '7c']
    assert results[0].rating == '0'
    for r in results[1:]:
        assert r.rating == 'unclear'
        assert r.needs_review
        assert '未返回' in r.review_note
        assert r.confidence == 'low'


def test_call_failure_degrades_every_item():
    runner = FakeRunner(structured=[(None, 'BadRequestError: 上下文超限')])
    results = _run(judge_batch(runner, ITEMS, ExtractDoc(), ExtractDoc(), CFG))

    assert all(r.rating == 'unclear' for r in results)
    assert all(r.needs_review for r in results)
    assert all('上下文超限' in r.review_note for r in results)


def test_rating_is_recorded_for_audit():
    runner = FakeRunner(structured=[(BatchVerdicts(verdicts=[_coded('2b', '0', '因为都用了 RoB 2')]), '')])
    result = _run(judge_batch(runner, [ITEM_BY_CODE['2b']], ExtractDoc(), ExtractDoc(), CFG))[0]

    assert [v.role for v in result.votes] == ['judge']
    assert result.votes[0].rating == '0'
    assert result.votes[0].reason_zh == '因为都用了 RoB 2'


def test_evidence_card_is_attached_for_items_that_have_one():
    """3a（检索来源）有代码算的客观事实卡，必须进提示词并留在结果里。"""
    a, b = ExtractDoc(), ExtractDoc()
    a.method.databases = ListFacet(value=['PubMed', 'Embase'], present='yes')
    b.method.databases = ListFacet(value=['PubMed', 'CNKI'], present='yes')
    runner = FakeRunner(structured=[(BatchVerdicts(verdicts=[_coded('3a', '0')]), '')])
    result = _run(judge_batch(runner, [ITEM_BY_CODE['3a']], a, b, CFG))[0]

    assert result.evidence_card
    assert '【客观事实】' in runner.structured_calls[0][0]


# --------------------------------------------------------------------------- 条目对位


def test_positional_fallback_when_model_omits_the_code():
    """模型不回填 code 时按顺序对位 —— 否则整批变 unclear，报告什么都没判出来。"""
    runner = FakeRunner(structured=[(
        BatchVerdicts(verdicts=[_coded('', '0'), _coded('', '1'), _coded('', '3')]), '')])
    results = _run(judge_batch(runner, ITEMS, ExtractDoc(), ExtractDoc(), CFG))

    assert [r.code for r in results] == ['2b', '3a', '7c']
    assert [r.rating for r in results] == ['0', '1', '3']
    # 对位是猜的，必须留痕
    assert all(r.needs_review and '按返回顺序对位' in r.review_note for r in results)


def test_no_positional_guess_when_the_count_does_not_match():
    """条数对不上就不猜：能对上几条算几条，其余照旧补 unclear。"""
    runner = FakeRunner(structured=[(BatchVerdicts(verdicts=[_coded('', '0')]), '')])
    results = _run(judge_batch(runner, ITEMS, ExtractDoc(), ExtractDoc(), CFG))

    assert [r.rating for r in results] == ['unclear', 'unclear', 'unclear']


def test_codes_win_over_order_when_present():
    """code 齐全时一律按 code 对，哪怕模型打乱了顺序。"""
    runner = FakeRunner(structured=[(
        BatchVerdicts(verdicts=[_coded('7c', '3'), _coded('2b', '0'), _coded('3a', '1')]), '')])
    results = _run(judge_batch(runner, ITEMS, ExtractDoc(), ExtractDoc(), CFG))

    assert [(r.code, r.rating) for r in results] == [('2b', '0'), ('3a', '1'), ('7c', '3')]
    assert not any(r.needs_review for r in results)
