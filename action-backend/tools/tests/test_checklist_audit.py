"""checklist 逐条校验算法的单测（不连 Redis、不连库、不调模型）。

盯的是几件「错了会直接骗人」的事：
- 模型漏回的条目必须兜底成 missing，不能默认算已报告
- 编造的行号（超出稿件行数）必须丢掉
- 同一条目在多个窗口的判定要取最优，不能被后一个窗口的 missing 覆盖掉
"""

from __future__ import annotations

import asyncio

import pytest
from tools.checklist_worker_tool.engine.audit import (
    MISSING,
    REPORTED,
    VAGUE,
    AuditConfig,
    ChecklistItem,
    ItemVerdict,
    audit,
    number_lines,
    split_windows,
    summarize,
)


def make_items(n: int) -> list[ChecklistItem]:
    return [ChecklistItem(item_id=i, item_no=f'{i}a', domain='方法', content=f'条目{i}') for i in range(1, n + 1)]


def make_text(lines: int) -> str:
    return '\n'.join(f'这是稿件第 {i} 行，写了一些足够长的内容用于测试。' for i in range(1, lines + 1))


class ScriptedRunner:
    """按 (窗口序号, 条目id) 事先编排好的判定结果。"""

    def __init__(self, script: dict[int, dict[int, str]] | None = None, drop: set[int] | None = None) -> None:
        self.script = script or {}
        self.drop = drop or set()
        self.calls = 0

    async def structured(self, schema, system, human, temperature=None):
        self.calls += 1
        window_no = int(human.split('本片段为第 ')[1].split('/')[0]) if '本片段为第 ' in human else 1
        ids = [int(line.split(']')[0][1:]) for line in human.splitlines() if line.startswith('[')]
        items = []
        for i in ids:
            if i in self.drop:
                continue
            status = self.script.get(window_no, {}).get(i, MISSING)
            items.append(
                {
                    'item_id': i,
                    'status': status,
                    'lines': [1, 10**6] if status != MISSING else [],
                    'evidence': 'x' * 400,
                    'reason': 'r',
                }
            )
        return schema(items=items), ''


def test_number_lines_skips_blank_lines():
    numbered, count = number_lines('甲\n\n乙\n  \n丙')
    assert count == 3
    assert numbered.splitlines()[0].endswith('| 甲')
    assert numbered.splitlines()[1] == ''


def test_split_windows_overlaps():
    numbered, _ = number_lines(make_text(400))
    cfg = AuditConfig(window_chars=2000, window_overlap=400)
    windows = split_windows(numbered, cfg)
    assert len(windows) > 1
    # 相邻窗口要有重叠，证据落在边界上才不会两边都看不全
    assert windows[0].splitlines()[-1] in windows[1]


def test_missing_items_default_to_missing():
    """模型漏回 3 号条目 —— 结果里它必须是 missing，而不是凭空算作已报告。"""
    items = make_items(4)
    runner = ScriptedRunner(script={1: {1: REPORTED, 2: VAGUE, 4: REPORTED}}, drop={3})
    result = asyncio.run(audit(runner, make_text(30), items, AuditConfig(batch_size=4)))
    by_id = {v['itemId']: v for v in result['verdicts']}
    assert by_id[3]['status'] == MISSING
    assert by_id[1]['status'] == REPORTED


def test_fabricated_line_numbers_are_dropped():
    items = make_items(2)
    runner = ScriptedRunner(script={1: {1: REPORTED, 2: REPORTED}})
    result = asyncio.run(audit(runner, make_text(20), items, AuditConfig(batch_size=2)))
    for v in result['verdicts']:
        assert all(1 <= n <= result['lineCount'] for n in v['lines'])


def test_evidence_is_truncated():
    items = make_items(1)
    runner = ScriptedRunner(script={1: {1: REPORTED}})
    result = asyncio.run(audit(runner, make_text(20), items, AuditConfig(batch_size=1)))
    assert len(result['verdicts'][0]['evidence']) <= 200


def test_best_verdict_wins_across_windows():
    """第 1 个窗口找到了证据、第 2 个没找到 —— 结论应当保留「已报告」。"""
    items = make_items(1)
    cfg = AuditConfig(batch_size=1, window_chars=1200, window_overlap=200)
    runner = ScriptedRunner(script={1: {1: REPORTED}, 2: {1: MISSING}})
    result = asyncio.run(audit(runner, make_text(200), items, cfg))
    assert result['windows'] > 1
    assert result['verdicts'][0]['status'] == REPORTED


def test_summarize_counts_vague_as_half():
    verdicts = [
        ItemVerdict(1, REPORTED),
        ItemVerdict(2, VAGUE),
        ItemVerdict(3, MISSING),
        ItemVerdict(4, MISSING),
    ]
    assert summarize(verdicts) == {
        'total': 4,
        'reported': 1,
        'vague': 1,
        'missing': 2,
        'completeness': 38,  # (1 + 0.5) / 4 = 37.5 -> 38
    }


def test_truncates_overlong_manuscript():
    items = make_items(1)
    runner = ScriptedRunner(script={1: {1: REPORTED}})
    cfg = AuditConfig(batch_size=1, max_chars=500, window_chars=10_000)
    result = asyncio.run(audit(runner, make_text(200), items, cfg))
    assert result['truncated'] is True


def test_empty_inputs_raise():
    with pytest.raises(ValueError):
        asyncio.run(audit(ScriptedRunner(), make_text(10), []))
    with pytest.raises(ValueError):
        asyncio.run(audit(ScriptedRunner(), '   ', make_items(1)))
