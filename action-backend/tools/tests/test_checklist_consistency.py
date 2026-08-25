"""全稿逻辑一致性与术语标准化校验的单测（不连 Redis、不连库、不调模型）。

盯的是几件「错了会直接骗人」的事：
- 模型出错的规则必须停在 unchecked，绝不能显示成「未发现问题」
- 编造的行号（超出稿件行数）必须丢掉，且丢光行号的发现要从 issue 降为 warn
- applicable=false 只在没有发现时才算「不适用」，不能用来吞掉已经列出的问题
- 稿件超长必须标 truncated（这类检查不切窗，后半段是真没看）
"""

from __future__ import annotations

import asyncio

import pytest
from tools.checklist_worker_tool.engine.consistency import (
    ISSUE,
    NA,
    OK,
    RULES,
    UNCHECKED,
    WARN,
    CheckResult,
    ConsistencyConfig,
    check_consistency,
    summarize,
)


def make_text(lines: int) -> str:
    return '\n'.join(f'这是稿件第 {i} 行，写了一些足够长的内容用于测试。' for i in range(1, lines + 1))


class ScriptedRunner:
    """按规则 key 事先编排好的检查结果。"""

    def __init__(self, script: dict[str, dict] | None = None, fail: set[str] | None = None) -> None:
        self.script = script or {}
        self.fail = fail or set()
        self.calls = 0

    def _rule_key(self, human: str) -> str:
        return human.split('本次校验要求（')[1].split('）')[0]

    async def structured(self, schema, system, human, temperature=None):
        self.calls += 1
        key = self._rule_key(human)
        if key in self.fail:
            return None, 'boom'
        return schema(**self.script.get(key, {'applicable': True, 'findings': []})), ''


def run(runner, text=None, cfg=None, **kwargs):
    return asyncio.run(check_consistency(runner, text or make_text(30), cfg, **kwargs))


def by_key(result) -> dict[str, dict]:
    return {c['key']: c for c in result['checks']}


def test_all_rules_are_checked():
    runner = ScriptedRunner()
    result = run(runner)
    assert runner.calls == len(RULES)
    assert by_key(result).keys() == {r.key for r in RULES}
    assert all(c['status'] == OK for c in result['checks'])


def test_failed_rule_stays_unchecked():
    """模型出错的那条必须是 unchecked —— 显示成「未发现问题」等于把没跑过的检查算成合格。"""
    runner = ScriptedRunner(fail={'sample'})
    result = run(runner)
    checks = by_key(result)
    assert checks['sample']['status'] == UNCHECKED
    assert checks['arm']['status'] == OK
    assert result['summary']['unchecked'] == 1
    assert result['errors'] and result['errors'][0].startswith('sample:')


def test_fabricated_line_numbers_are_dropped_and_downgraded():
    """行号全是编的 —— 行号丢掉，且这条不再够格当 issue。"""
    runner = ScriptedRunner(
        script={
            'arm': {
                'applicable': True,
                'findings': [{'severity': ISSUE, 'lines': [10**6], 'detail': '两组写混了', 'evidence': 'x'}],
            }
        }
    )
    result = run(runner)
    arm = by_key(result)['arm']
    assert arm['findings'][0]['lines'] == []
    assert arm['findings'][0]['severity'] == WARN
    assert arm['status'] == WARN


def test_real_line_numbers_keep_issue_severity():
    runner = ScriptedRunner(
        script={
            'schedule': {
                'applicable': True,
                'findings': [{'severity': ISSUE, 'lines': [3, 11], 'detail': '每周 3 次 vs 每周 2 次'}],
            }
        }
    )
    result = run(runner)
    schedule = by_key(result)['schedule']
    assert schedule['findings'][0]['lines'] == [3, 11]
    assert schedule['status'] == ISSUE


def test_not_applicable_only_when_empty():
    """applicable=false 不能用来吞掉已经列出来的问题。"""
    runner = ScriptedRunner(
        script={
            'arm': {'applicable': False, 'findings': []},
            'sample': {
                'applicable': False,
                'findings': [{'severity': WARN, 'lines': [2], 'detail': '例数对不上'}],
            },
        }
    )
    checks = by_key(run(runner))
    assert checks['arm']['status'] == NA
    assert checks['sample']['status'] == WARN


def test_empty_findings_are_dropped():
    """既没说明、也没建议、也没原文的「发现」无从核起，等同于没发现。"""
    runner = ScriptedRunner(script={'acupoint': {'applicable': True, 'findings': [{'severity': ISSUE, 'lines': [1]}]}})
    acupoint = by_key(run(runner))['acupoint']
    assert acupoint['findings'] == []
    assert acupoint['status'] == OK


def test_findings_are_capped_and_flagged():
    findings = [{'severity': WARN, 'lines': [1], 'detail': f'第 {i} 个不规范穴名'} for i in range(30)]
    runner = ScriptedRunner(script={'acupoint': {'applicable': True, 'findings': findings}})
    acupoint = by_key(run(runner, cfg=ConsistencyConfig(max_findings=5)))['acupoint']
    assert len(acupoint['findings']) == 5
    assert acupoint['capped'] is True


def test_text_fields_are_truncated():
    runner = ScriptedRunner(
        script={
            'arm': {
                'applicable': True,
                'findings': [
                    {
                        'severity': WARN,
                        'lines': [1],
                        'evidence': 'e' * 500,
                        'detail': 'd' * 999,
                        'suggestion': 's' * 999,
                    }
                ],
            }
        }
    )
    f = by_key(run(runner))['arm']['findings'][0]
    assert len(f['evidence']) <= 200
    assert len(f['detail']) <= 400
    assert len(f['suggestion']) <= 300


def test_overlong_manuscript_is_flagged():
    """不切窗，超预算就截断 —— 但必须标出来，否则用户以为后半段也看过了。"""
    result = run(ScriptedRunner(), text=make_text(400), cfg=ConsistencyConfig(max_chars=1000))
    assert result['truncated'] is True
    assert run(ScriptedRunner(), text=make_text(5))['truncated'] is False


def test_truncation_keeps_whole_lines():
    class Capture(ScriptedRunner):
        human = ''

        async def structured(self, schema, system, human, temperature=None):
            Capture.human = human
            return await super().structured(schema, system, human)

    asyncio.run(check_consistency(Capture(), make_text(400), ConsistencyConfig(max_chars=1000)))
    body = Capture.human.split('-----')[1]
    # 每一行要么是空行，要么完整带着「N | 」前缀和句号结尾
    for line in [x for x in body.split('\n') if x.strip()]:
        assert '|' in line and line.rstrip().endswith('。')


def test_locale_switches_output_language():
    class Capture(ScriptedRunner):
        system = ''

        async def structured(self, schema, sys_prompt, human, temperature=None):
            Capture.system = sys_prompt
            return await super().structured(schema, sys_prompt, human)

    asyncio.run(check_consistency(Capture(), make_text(10), locale='en'))
    assert '英文书写' in Capture.system
    asyncio.run(check_consistency(Capture(), make_text(10), locale='zh'))
    assert '中文书写' in Capture.system


def test_summarize_counts_each_bucket():
    checks = [
        CheckResult('a', 'logic', OK),
        CheckResult('b', 'logic', WARN),
        CheckResult('c', 'logic', ISSUE),
        CheckResult('d', 'term', UNCHECKED),
    ]
    assert summarize(checks) == {
        'total': 4,
        'ok': 1,
        'warn': 1,
        'issue': 1,
        'na': 0,
        'unchecked': 1,
        'findings': 0,
    }


def test_empty_manuscript_raises():
    with pytest.raises(ValueError):
        asyncio.run(check_consistency(ScriptedRunner(), '   '))
