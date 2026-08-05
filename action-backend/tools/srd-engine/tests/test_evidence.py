"""代码取证单测：词表归一、纳入研究重叠、合并效应比较。"""

from __future__ import annotations

from srd_engine.evidence import (
    build_evidence_card,
    canonical_databases,
    compare_pooled,
    jaccard,
    study_key,
    study_overlap,
)
from srd_engine.schemas import ExtractDoc, IncludedStudy, ListFacet, PooledResult

# --------------------------------------------------------------------------- 词表归一


def test_database_aliases_normalize_to_same_canonical_name():
    known, unknown = canonical_databases(
        ['PubMed', 'MEDLINE (Ovid)', 'Cochrane Central Register of Controlled Trials', '中国知网', 'WanFang']
    )
    assert 'PubMed/MEDLINE' in known
    assert 'CENTRAL' in known
    assert 'CNKI' in known
    assert 'WanFang' in known
    assert unknown == []


def test_unknown_database_is_reported_not_silently_dropped():
    known, unknown = canonical_databases(['PubMed', '某某自建库'])
    assert 'PubMed/MEDLINE' in known
    assert unknown == ['某某自建库']


def test_jaccard():
    assert jaccard({1, 2, 3}, {2, 3, 4}) == 0.5
    assert jaccard(set(), set()) == 0.0


# --------------------------------------------------------------------------- 6a 纳入研究重叠


def test_study_key_prefers_registry_then_doi_then_author_year():
    assert study_key(IncludedStudy(registry_id='NCT03123456', doi='10.1/x', first_author='Zhang')).startswith('reg:')
    assert study_key(IncludedStudy(doi='10.1/x', first_author='Zhang')).startswith('doi:')
    assert study_key(IncludedStudy(first_author='Zhang', year=2019)) == 'ay:zhang:2019'


def test_same_study_matches_across_formatting_differences():
    a = IncludedStudy(registry_id='NCT 03123456')
    b = IncludedStudy(registry_id='nct03123456')
    assert study_key(a) == study_key(b)


def test_study_overlap_counts_and_jaccard():
    a = [IncludedStudy(first_author='Zhang', year=2019),
         IncludedStudy(first_author='Li', year=2020),
         IncludedStudy(first_author='Wang', year=2021)]
    b = [IncludedStudy(first_author='Li', year=2020),
         IncludedStudy(first_author='Wang', year=2021),
         IncludedStudy(first_author='Chen', year=2022)]
    ov = study_overlap(a, b)
    assert (ov['count_a'], ov['count_b'], ov['intersection'], ov['union']) == (3, 3, 2, 4)
    assert ov['jaccard'] == 0.5
    # 双综述场景下 CCA 与 Jaccard 恒等
    assert ov['cca'] == ov['jaccard']
    assert ov['only_a'] == ['Zhang 2019']
    assert ov['only_b'] == ['Chen 2022']


def test_study_overlap_empty():
    assert study_overlap([], [])['union'] == 0


# --------------------------------------------------------------------------- 8b 合并效应


def test_compare_pooled_same_direction_and_overlapping_ci():
    a = [PooledResult(outcome='VAS 疼痛评分', measure='MD', point=-1.32, ci_low=-1.80, ci_high=-0.84)]
    b = [PooledResult(outcome='vas 疼痛评分', measure='MD', point=-1.15, ci_low=-1.66, ci_high=-0.64)]
    (row,) = compare_pooled(a, b)
    assert row['same_direction'] is True
    assert row['same_measure'] is True
    assert row['ci_overlap'] > 0.8
    assert row['significant_a'] is True and row['significant_b'] is True


def test_compare_pooled_opposite_direction():
    a = [PooledResult(outcome='pain', measure='MD', point=-1.0, ci_low=-1.5, ci_high=-0.5)]
    b = [PooledResult(outcome='pain', measure='MD', point=0.8, ci_low=0.3, ci_high=1.3)]
    (row,) = compare_pooled(a, b)
    assert row['same_direction'] is False
    assert row['ci_overlap'] == 0.0


def test_compare_pooled_ratio_measure_uses_log_scale_and_null_of_one():
    """比值型指标的无效线是 1，不是 0。"""
    a = [PooledResult(outcome='response', measure='RR', point=1.20, ci_low=0.95, ci_high=1.52)]
    b = [PooledResult(outcome='response', measure='RR', point=1.25, ci_low=1.05, ci_high=1.49)]
    (row,) = compare_pooled(a, b)
    assert row['same_direction'] is True
    assert row['significant_a'] is False  # 区间跨过 1
    assert row['significant_b'] is True


def test_compare_pooled_skips_outcomes_without_a_counterpart():
    a = [PooledResult(outcome='pain', measure='MD', point=-1.0)]
    b = [PooledResult(outcome='function', measure='MD', point=-2.0)]
    assert compare_pooled(a, b) == []


# --------------------------------------------------------------------------- 证据卡


def _extract_with_studies(labels, databases=None):
    ex = ExtractDoc()
    ex.result.included_studies = [IncludedStudy(first_author=x, year=2020) for x in labels]
    if databases:
        ex.method.databases = ListFacet(value=databases, present='yes')
    return ex


def test_evidence_card_only_for_three_items():
    a = _extract_with_studies(['Zhang', 'Li'], ['PubMed', 'Embase'])
    b = _extract_with_studies(['Li', 'Chen'], ['PubMed'])
    assert build_evidence_card('6a', a, b)
    assert build_evidence_card('3a', a, b)
    assert build_evidence_card('2b', a, b) == ''


def test_evidence_card_6a_mentions_intersection_and_jaccard():
    a = _extract_with_studies(['Zhang', 'Li'])
    b = _extract_with_studies(['Li', 'Chen'])
    card = build_evidence_card('6a', a, b)
    assert '交集 1 项' in card
    assert 'Jaccard = 0.33' in card


def test_evidence_card_6a_warns_when_list_is_incomplete():
    a = _extract_with_studies(['Zhang', 'Li'])
    a.result.included_count_reported = 14
    b = _extract_with_studies(['Li'])
    card = build_evidence_card('6a', a, b)
    assert '清单可能不完整' in card
    assert '抽取到 2 项，原文自述 14 项' in card
