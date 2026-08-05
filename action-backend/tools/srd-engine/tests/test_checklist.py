"""清单结构与判定口径的完整性检查。"""

from __future__ import annotations

import pytest

from srd_engine.checklist import (
    ALL_ITEMS,
    DEBATE_ITEMS,
    DOMAINS,
    EVIDENCE_ITEMS,
    ITEM_BY_CODE,
    criteria_of,
    load_criteria,
)


def test_structure_matches_excel():
    """4 领域 / 12 分组 / 34 条目，领域 1 与 3 为关键领域。"""
    assert len(DOMAINS) == 4
    assert sum(len(d.groups) for d in DOMAINS) == 12
    assert len(ALL_ITEMS) == 34
    assert [d.is_key for d in DOMAINS] == [True, False, True, False]
    assert [len(d.items) for d in DOMAINS] == [8, 6, 14, 6]


def test_group_codes_are_1_to_12():
    codes = [g.code for d in DOMAINS for g in d.groups]
    assert codes == [str(i) for i in range(1, 13)]


def test_item_codes_unique_and_expected():
    expected = {
        '1a', '1b', '2a', '2b', '2c', '2d', '2e', '2f',
        '3a', '3b', '4a', '4b', '5a', '5b',
        '6a', '6b', '6c', '6d', '6e', '7a', '7b', '7c', '7d', '8a', '8b', '8c', '8d', '8e',
        '9a', '10a', '10b', '11', '12a', '12b',
    }
    assert {it.code for it in ALL_ITEMS} == expected


def test_every_item_has_criteria():
    criteria = load_criteria()
    for item in ALL_ITEMS:
        c = criteria[item.code]
        for key in ('dup_when', 'diff_when', 'unclear_when'):
            assert c.get(key, '').strip(), f'{item.code} 缺少 {key}'


def test_criteria_are_observable_not_tautological():
    """口径不许写成「很相似 / 较相似」这类同义反复（DESIGN.md §4.3）。"""
    banned = ['很相似', '较为相似', '基本相似', '差不多']
    for item in ALL_ITEMS:
        c = criteria_of(item.code)
        text = f'{c.get("dup_when", "")}{c.get("diff_when", "")}'
        for word in banned:
            assert word not in text, f'{item.code} 的口径出现空泛表述「{word}」'


def test_every_item_declares_facet_paths():
    for item in ALL_ITEMS:
        assert item.facet_paths, f'{item.code} 未声明 facet_paths'
        for path in item.facet_paths:
            assert path.split('.')[0] in {'topic', 'method', 'result', 'quality'}


def test_debate_items_are_the_substantially_similar_ones():
    assert {'8c', '8d', '8e', '9a', '10b', '11', '12b'} == DEBATE_ITEMS
    for code in DEBATE_ITEMS:
        assert ITEM_BY_CODE[code].judge_mode == 'debate'
    assert sum(1 for it in ALL_ITEMS if it.judge_mode == 'standard') == 27


def test_evidence_card_items():
    assert {'3a', '6a', '8b'} == EVIDENCE_ITEMS
    for code in EVIDENCE_ITEMS:
        assert ITEM_BY_CODE[code].has_evidence_card


@pytest.mark.parametrize('code', ['10a', '12a'])
def test_method_description_items_are_still_judged(code):
    """10a / 12a 是「用了什么方法」，两篇用同一方法即为重复，不做特殊豁免。"""
    item = ITEM_BY_CODE[code]
    assert item.judge_mode == 'standard'
    assert '同一' in criteria_of(code)['dup_when'] or '相同' in criteria_of(code)['dup_when']


def test_facet_paths_resolve_on_a_blank_extract():
    """所有 facet_path 必须能在 ExtractDoc 上取到，防止拼写错误。"""
    from srd_engine.schemas import ExtractDoc  # noqa: PLC0415

    blank = ExtractDoc()
    for item in ALL_ITEMS:
        for path in item.facet_paths:
            assert blank.get_path(path) is not None, f'{item.code} 的 facet_path {path} 无法解析'
