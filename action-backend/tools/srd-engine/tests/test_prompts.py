"""提示词渲染单测 —— 保证 34 条目都能拼出提示词，且关键约束都写进去了。"""

from __future__ import annotations

import pytest

from srd_engine.checklist import ALL_ITEMS, DOMAINS, ITEM_BY_CODE
from srd_engine.evidence import build_evidence_card
from srd_engine.prompts import extract_messages, judge_batch_messages
from srd_engine.schemas import (
    ExtractDoc,
    IncludedStudy,
    ListFacet,
    PooledResult,
    TextFacet,
)


def _populated(label: str) -> ExtractDoc:
    ex = ExtractDoc(title=f'综述{label}')
    ex.topic.intervention = TextFacet(
        value='电针，每周3次共8周，主穴 委中/肾俞',
        quote='Electroacupuncture was delivered three times weekly for eight weeks.',
        present='yes',
    )
    ex.topic.objective = TextFacet(value='评价针刺治疗慢性腰痛的疗效', present='yes')
    ex.method.databases = ListFacet(value=['PubMed', 'Embase', 'CENTRAL'], present='yes')
    ex.result.included_studies = [
        IncludedStudy(first_author='Zhang', year=2019),
        IncludedStudy(first_author='Li', year=2020),
    ]
    ex.result.pooled_results = [
        PooledResult(outcome='VAS', measure='MD', point=-1.3, ci_low=-1.8, ci_high=-0.8, k=8, i2=62.0)
    ]
    ex.result.sensitivity_analyses = ListFacet(
        value=['未做敏感性分析'], quote='No sensitivity analysis was performed.', present='no'
    )
    return ex


@pytest.mark.parametrize('item', ALL_ITEMS, ids=lambda i: i.code)
def test_every_item_renders_a_judge_prompt(item):
    a, b = _populated('A'), _populated('B')
    system, human = judge_batch_messages([item], a, b, {item.code: build_evidence_card(item.code, a, b)})
    assert system and human
    assert item.question_zh in human
    assert '【评分锚点】' in human
    assert '【综述A】' in human and '【综述B】' in human


def test_judge_prompt_states_the_four_scoring_bands():
    system, _ = judge_batch_messages([ITEM_BY_CODE['2b']], ExtractDoc(), ExtractDoc(), {})
    for band in ('"0" 完全相同', '"1" 部分相同', '"2" 部分不同', '"3" 完全不同', '"unclear"'):
        assert band in system, f'提示词缺少档位定义：{band}'
    # 「都明确说未做」= 一致（0 分），「都没写清楚」= 证据不足 —— 这条区分必须写进提示词
    assert '未做某事' in system
    assert '逐字' in system


def test_judge_prompt_states_the_direction_of_the_scale():
    """分越低越重复。方向写反了会让全部结论反过来，必须钉死在测试里。"""
    system, _ = judge_batch_messages([ITEM_BY_CODE['2b']], ExtractDoc(), ExtractDoc(), {})
    assert '分越低越重复' in system


def test_item_block_gives_both_anchors():
    _, human = judge_batch_messages([ITEM_BY_CODE['2b']], ExtractDoc(), ExtractDoc(), {})
    assert '0 分（完全相同）当：' in human
    assert '3 分（完全不同）当：' in human
    # 中间两档只在系统提示词里定义一次，条目块里不重复
    assert '1 分（部分相同）当：' not in human


def test_explicit_absence_is_rendered_differently_from_missing():
    """present=no（明确未做）与 present=unclear（没写清楚）在提示词里必须可区分。"""
    a = _populated('A')
    b = ExtractDoc()
    _, human = judge_batch_messages([ITEM_BY_CODE['7d']], a, b, {})
    assert '【原文明确说明未做】' in human
    assert '（原文未提及或表述含糊）' in human


def test_evidence_card_is_injected_for_6a():
    a, b = _populated('A'), _populated('B')
    card = build_evidence_card('6a', a, b)
    _, human = judge_batch_messages([ITEM_BY_CODE['6a']], a, b, {ITEM_BY_CODE['6a'].code: card})
    assert '客观事实' in human
    assert 'Jaccard' in human


def test_facet_slice_only_contains_relevant_fields():
    """切片：判 2b 时视野里不应出现数据库、GRADE 之类无关内容。"""
    a, b = _populated('A'), _populated('B')
    _, human = judge_batch_messages([ITEM_BY_CODE['2b']], a, b, {})
    assert 'topic.intervention' in human
    assert 'method.databases' not in human
    assert 'quality.grade_ratings' not in human


def test_batch_prompt_warns_against_herding():
    group = DOMAINS[0].groups[1]  # 分组 2：2a–2f
    items = list(group.items)
    system, human = judge_batch_messages(items, _populated('A'), _populated('B'), {})
    assert '不要因为前面的条目打了 0 分' in system
    for item in items:
        assert item.code in human


@pytest.mark.parametrize('batch', ['topic', 'method', 'result', 'quality'])
def test_extract_prompt_forbids_guessing(batch):
    system, human = extract_messages(batch, '某某综述', '正文若干')
    assert '不要猜' in system
    assert '逐字片段' in system
    # 「明确说了没做」与「没提到」不可混同 —— 这条口径是判定端 dup/unclear 的前提
    assert 'present 填 "no"' in system
    assert '正文若干' in human


def test_extract_result_batch_emphasises_included_studies():
    _, human = extract_messages('result', 't', 'x')
    assert 'included_studies' in human
    assert 'included_count_reported' in human
