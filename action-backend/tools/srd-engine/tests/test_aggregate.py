"""聚合算法单测 —— 表 1 评分、表 2 分箱与表 3 全 16 格逐格断言。

这是引擎里唯一决定最终结论的地方，必须能对着 Excel 逐格复核。
"""

from __future__ import annotations

import pytest

from srd_engine.aggregate import (
    aggregate,
    build_skeleton,
    dup_pct,
    from_rating_map,
    from_verdict_map,
    key_state,
    level_of,
    nonkey_col,
    overall_of,
)
from srd_engine.checklist import ALL_ITEMS, DOMAINS
from srd_engine.config import EngineConfig
from srd_engine.schemas import ItemResult

# --------------------------------------------------------------------------- 表 2


@pytest.mark.parametrize(
    ('pct', 'expected'),
    [
        (0, 'none'), (25, 'none'),
        (26, 'low'), (50, 'low'),
        (51, 'mod'), (75, 'mod'),
        (76, 'high'), (100, 'high'),
    ],
)
def test_table2_bins(pct, expected):
    assert level_of(pct) == expected


def test_table2_boundaries_are_inclusive_upper():
    """边界取上界闭区间：25→无重复、50→低重复、75→中度重复。"""
    assert (level_of(25), level_of(26)) == ('none', 'low')
    assert (level_of(50), level_of(51)) == ('low', 'mod')
    assert (level_of(75), level_of(76)) == ('mod', 'high')


# --------------------------------------------------------------------------- 表 3 全 16 格

# 行：关键领域（主题、结果）；列：非关键领域（方法、质量）
# 取自 Excel 表 3 的 H/I/J/K 列
TABLE3 = [
    # (关键领域组合, 非关键领域组合, 期望整体判定)
    (('none', 'none'), ('low', 'low'), 'none'),
    (('none', 'none'), ('mod', 'low'), 'low'),
    (('none', 'none'), ('mod', 'mod'), 'mod'),
    (('low', 'low'), ('low', 'low'), 'low'),
    (('low', 'low'), ('mod', 'low'), 'low'),
    (('low', 'low'), ('mod', 'mod'), 'mod'),
    (('mod', 'low'), ('low', 'low'), 'mod'),
    (('mod', 'low'), ('mod', 'low'), 'mod'),
    (('mod', 'low'), ('mod', 'mod'), 'high'),
    (('mod', 'mod'), ('low', 'low'), 'high'),
    (('mod', 'mod'), ('mod', 'low'), 'high'),
    (('mod', 'mod'), ('mod', 'mod'), 'high'),
    (('high', 'mod'), ('low', 'low'), 'high'),
    (('high', 'high'), ('mod', 'low'), 'high'),
    (('high', 'low'), ('low', 'low'), 'high'),
    (('mod', 'high'), ('mod', 'mod'), 'high'),
]


@pytest.mark.parametrize(('key', 'nonkey', 'expected'), TABLE3)
def test_table3_matrix(key, nonkey, expected):
    assert overall_of(key, nonkey) == expected


def test_table3_nonkey_high_counts_as_two_mod():
    """K 列口径：两个非关键领域均中度，**或其中一个为高度** —— 后者也走 K 列。"""
    assert nonkey_col('high', 'none') == 2
    assert nonkey_col('mod', 'mod') == 2
    assert nonkey_col('mod', 'low') == 1
    assert nonkey_col('none', 'low') == 0


def test_key_state_takes_the_stricter_side_for_mixed_cases():
    """Excel 未穷举的混合情形：含 high 一律归入最严格的一行。"""
    assert key_state('none', 'high') == 'both_mod_or_high'
    assert key_state('none', 'low') == 'both_low'
    assert key_state('none', 'mod') == 'one_mod'
    assert key_state('low', 'mod') == 'one_mod'


# --------------------------------------------------------------------------- 领域打分


def _mk(mapping: dict[str, str]):
    """入参是评分表；老的 dup/diff 写法走 from_verdict_map 那条兼容路径。"""
    return from_rating_map(mapping)


def test_domain_pct_is_the_complement_of_the_score():
    """领域重复百分比 =（满分 − 得分）÷ 满分，unclear 连同它那 3 分一并剔出。"""
    # 领域 1 共 8 条：5 条 0 分 + 2 条 3 分 + 1 条 unclear
    # → 得分 6/21 → 重复度 (21−6)/21 = 71% → 中度重复
    ratings = dict(
        zip(
            ['1a', '1b', '2a', '2b', '2c', '2d', '2e', '2f'],
            ['0', '0', '0', '0', '0', '3', '3', 'unclear'],
            strict=True,
        )
    )
    result = _mk(ratings)
    d1 = result.domains[0]
    assert (d1.score_sum, d1.score_max, d1.score_max_full) == (6, 21, 24)
    assert d1.unclear_count == 1
    assert d1.pct == 71
    assert d1.level == 'mod'


def test_middle_bands_land_between_the_anchors():
    """1 分与 2 分是本版新增的档：全 1 分 → 67%，全 2 分 → 33%。

    注意整体判定不是把百分比再分一次箱，而是拿四个领域的档位查表 3：
    全 1 分 → 四个领域都是「中度重复」→ 两个关键领域均中度 → 表 3 给「高度重复」。
    这一跳看着突兀，但它就是 Excel 表 3 写的口径。
    """
    all_one = _mk({c.code: '1' for c in ALL_ITEMS})
    all_two = _mk({c.code: '2' for c in ALL_ITEMS})
    assert (all_one.overall_pct, all_two.overall_pct) == (67, 33)
    assert [d.level for d in all_one.domains] == ['mod'] * 4
    assert [d.level for d in all_two.domains] == ['low'] * 4
    assert all_one.overall_level == 'high'
    assert all_two.overall_level == 'low'


def test_legacy_verdict_map_reproduces_0_6_0_percentages():
    """老的 dup/diff 文件折成 0/3 分后，百分比必须与 0.6.0 的算法完全一致。"""
    verdicts = {c.code: 'dup' for c in ALL_ITEMS}
    for code in ('1a', '1b', '2a', '3a', '6a'):
        verdicts[code] = 'diff'
    for code in ('2f', '7c'):
        verdicts[code] = 'unclear'
    legacy = from_verdict_map(verdicts)
    for d in legacy.domains:                       # 0.6.0 口径：dup ÷ (dup + diff)
        assert d.pct == round(100 * d.dup_count / (d.dup_count + d.diff_count))


def test_dup_pct_handles_the_empty_domain():
    assert dup_pct(0, 0) == 0


def test_unclear_is_not_counted_as_duplicate():
    """两篇都没写清楚 ≠ 两篇做法相同：全 unclear 的领域没有档位。"""
    result = _mk({c.code: 'unclear' for c in ALL_ITEMS})
    for d in result.domains:
        assert d.level is None
        assert d.pct == 0
        assert d.evidence_sufficient is False
    assert result.provisional is True


def test_all_zero_gives_high_duplication():
    result = _mk({c.code: '0' for c in ALL_ITEMS})
    assert [d.pct for d in result.domains] == [100, 100, 100, 100]
    assert [d.score_sum for d in result.domains] == [0, 0, 0, 0]
    # Excel 表 1 白纸黑字的四个领域总分
    assert [d.score_max_full for d in result.domains] == [24, 18, 42, 18]
    assert (result.overall_score_sum, result.overall_score_max_full) == (0, 102)
    assert result.overall_level == 'high'
    assert result.provisional is False


def test_all_three_gives_no_duplication():
    result = _mk({c.code: '3' for c in ALL_ITEMS})
    assert result.overall_level == 'none'
    assert result.overall_pct == 0
    assert (result.overall_score_sum, result.overall_score_max) == (102, 102)


def test_evidence_sufficient_threshold():
    """领域可评估条目不足一半 → 标证据不足。"""
    ratings = {c.code: '0' for c in ALL_ITEMS}
    # 领域 1 的 8 条里让 5 条 unclear（可评分 3/8 < 50%）
    for code in ['1a', '1b', '2a', '2b', '2c']:
        ratings[code] = 'unclear'
    result = _mk(ratings)
    assert result.domains[0].evidence_sufficient is False
    assert result.provisional is True  # 领域 1 是关键领域


def test_near_boundary_flag():
    """8 条领域里 4 条 0 分 4 条 3 分 → 得分 12/24 → 50%（低重复上界）应被标为临界。"""
    ratings = {c.code: '3' for c in ALL_ITEMS}
    for code in ['1a', '1b', '2a', '2b']:
        ratings[code] = '0'
    result = _mk(ratings)
    d1 = result.domains[0]
    assert d1.pct == 50
    assert d1.level == 'low'
    assert d1.near_boundary is True


# --------------------------------------------------------------------------- 覆盖与重算


def test_manual_override_changes_the_overall_verdict():
    """人工改分后重新 aggregate 即可重算，无需重跑 LLM。"""
    result = _mk({c.code: '3' for c in ALL_ITEMS})
    assert result.overall_level == 'none'

    for item in result.items:
        item.override_rating = '0'
    aggregate(result, EngineConfig())
    assert result.overall_level == 'high'
    assert result.overall_pct == 100
    assert result.overall_score_sum == 0


def test_skeleton_fills_missing_items_as_unclear():
    result = build_skeleton({'1a': ItemResult(code='1a', rating='0')})
    assert len(result.items) == 34
    missing = [it for it in result.items if it.code != '1a']
    assert all(it.rating == 'unclear' and it.needs_review for it in missing)


def test_skeleton_matches_checklist_structure():
    result = build_skeleton()
    assert [d.seq for d in result.domains] == [1, 2, 3, 4]
    assert [d.is_key for d in result.domains] == [True, False, True, False]
    assert [len(d.items) for d in result.domains] == [8, 6, 14, 6]
    assert sum(len(d.groups) for d in result.domains) == 12


def test_overall_reason_is_generated_and_consistent():
    result = _mk({c.code: '0' for c in ALL_ITEMS})
    assert '高度重复' in result.overall_reason_zh
    assert 'high duplication' in result.overall_reason_en


def test_unknown_item_code_is_rejected():
    with pytest.raises(ValueError, match='未知条目编号'):
        from_rating_map({'99z': '0'})


def test_unknown_verdict_value_is_rejected():
    with pytest.raises(ValueError, match='未知判定值'):
        from_verdict_map({'1a': '重复'})


def test_domain_structure_is_from_single_source():
    """骨架必须与 checklist 完全一致，避免两处各自维护。"""
    assert sum(len(d.items) for d in DOMAINS) == 34
