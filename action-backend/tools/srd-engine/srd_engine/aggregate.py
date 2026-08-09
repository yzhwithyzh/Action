"""P3 聚合：条目评分 → 领域 → 整体判定.

纯代码、零 LLM、无 IO —— 这是整个引擎里唯一决定最终结论的地方，必须能对着
Excel 的表 1 / 表 2 / 表 3 逐格复核。表 3 的 16 格在 tests/test_aggregate.py 里逐格断言。

表 1（条目评分，0.7.0 起）：每条目 0–3 分
    0 完全相同 / 1 部分相同 / 2 部分不同 / 3 完全不同
    领域满分 = 3 × 条目数 → 领域1 /24、领域2 /18、领域3 /42、领域4 /18，合计 /102

表 2（单领域重复程度，按百分比）：
    无重复 0–25% / 低重复 26–50% / 中度重复 51–75% / 高度重复 76–100%
    其中 重复百分比 = (满分 − 得分) ÷ 满分 × 100
         —— 分数量的是「差异」，百分比量的是「重复」，所以要反过来
         unclear 条目连同它那 3 分一起剔出分母（两篇都没写清楚 ≠ 两篇做法相同）

    与 0.6.0 的兼容性：老口径是 `dup 条数 ÷ (dup + diff)`。若全部条目都只打 0 或 3 分，
    新公式退化成完全相同的数值 —— 0 分等价于旧的 dup，3 分等价于旧的 diff。
    1 分与 2 分是新增的中间档，它们让「大同小异」不再被迫二选一。

表 3（整体判定）：关键领域（主题 + 结果）状态 × 非关键领域（方法 + 质量）状态查表
"""

from __future__ import annotations

from srd_engine.checklist import DOMAIN_OF_ITEM, DOMAINS, GROUP_OF_ITEM, ITEM_BY_CODE
from srd_engine.config import CRITERIA_VERSION, ENGINE_VERSION, EngineConfig
from srd_engine.schemas import (
    SCORE_PER_ITEM,
    AssessmentResult,
    DomainResult,
    GroupResult,
    ItemResult,
    Level,
    Rating,
)

# 领域 pct 距分箱边界多少分以内算「临界」（一条之差就跳档，需提示人工复核）
NEAR_BOUNDARY_MARGIN = 5
DOMAIN_COUNT = 4

# 表 2 分箱上界
_BINS: tuple[tuple[int, Level], ...] = ((25, 'none'), (50, 'low'), (75, 'mod'), (100, 'high'))

LEVEL_LABEL_ZH: dict[Level, str] = {
    'none': '无重复',
    'low': '低重复',
    'mod': '中度重复',
    'high': '高度重复',
}
LEVEL_LABEL_EN: dict[Level, str] = {
    'none': 'no duplication',
    'low': 'low duplication',
    'mod': 'moderate duplication',
    'high': 'high duplication',
}

# 表 3：行 = 关键领域状态，列 = 非关键领域状态（0 均低 / 1 一个中度 / 2 两中度或含高度）
MATRIX: dict[str, tuple[Level, Level, Level]] = {
    'both_none': ('none', 'low', 'mod'),
    'both_low': ('low', 'low', 'mod'),
    'one_mod': ('mod', 'mod', 'high'),
    'both_mod_or_high': ('high', 'high', 'high'),
}

KEY_STATE_LABEL_ZH = {
    'both_none': '均为「无重复」',
    'both_low': '均为「低重复」及以下',
    'one_mod': '其中一个为「中度重复」',
    'both_mod_or_high': '均为「中度重复」或包含「高度重复」',
}
NONKEY_COL_LABEL_ZH = {
    0: '均为「低重复」及以下',
    1: '一个达到「中度重复」',
    2: '均达到「中度重复」或其中一个为「高度重复」',
}


def level_of(pct: int | float) -> Level:
    """表 2：百分比 → 重复程度。"""
    for upper, level in _BINS:
        if pct <= upper:
            return level
    return 'high'


def key_state(a: Level, b: Level) -> str:
    """表 3 行：两个关键领域（研究主题、研究结果）的状态。

    Excel 未穷举混合情形（如一个 none 一个 high），本实现一律**取较严的一侧**：
    含 high 即归入最严格的一行。见 DESIGN.md §15.3。
    """
    s = {a, b}
    if s == {'none'}:
        return 'both_none'
    if s <= {'none', 'low'}:
        return 'both_low'
    if 'high' in s or s == {'mod'}:
        return 'both_mod_or_high'
    return 'one_mod'


def nonkey_col(a: Level, b: Level) -> int:
    """表 3 列：两个非关键领域（研究方法、研究质量）的状态。"""
    s = {a, b}
    if s <= {'none', 'low'}:
        return 0
    if 'high' in s:
        return 2
    return 1 if [a, b].count('mod') == 1 else 2


def overall_of(key: tuple[Level, Level], nonkey: tuple[Level, Level]) -> Level:
    """表 3 查表。"""
    return MATRIX[key_state(*key)][nonkey_col(*nonkey)]


# --------------------------------------------------------------------------- 领域打分


def dup_pct(score_sum: int, score_max: int) -> int:
    """得分 → 重复百分比。分数量差异，百分比量重复，故取补。"""
    return round(100 * (score_max - score_sum) / score_max) if score_max else 0


def score_domain(domain: DomainResult, cfg: EngineConfig) -> DomainResult:
    """就地计算领域的得分、百分比与档位（顺带保留旧的 dup/diff/unclear 计数供展示）。"""
    items = domain.items
    scores = [it.score for it in items if it.score is not None]

    domain.dup_count = sum(1 for it in items if it.effective_verdict == 'dup')
    domain.diff_count = sum(1 for it in items if it.effective_verdict == 'diff')
    domain.unclear_count = sum(1 for it in items if it.effective_verdict == 'unclear')
    domain.score_max_full = SCORE_PER_ITEM * len(items)
    domain.score_sum = sum(scores)
    domain.score_max = SCORE_PER_ITEM * len(scores)

    if not scores:
        domain.level = None
        domain.pct = 0
        domain.evidence_sufficient = False
        domain.near_boundary = False
        return domain

    domain.pct = dup_pct(domain.score_sum, domain.score_max)
    domain.level = level_of(domain.pct)
    domain.evidence_sufficient = bool(items) and len(scores) >= len(items) * cfg.evidence_sufficient_ratio
    # 分箱边界附近（8 条领域的每 1 分只值 4.2%，一条评分之差就可能跳档）标出来提示人工复核
    domain.near_boundary = any(abs(domain.pct - b) <= NEAR_BOUNDARY_MARGIN for b, _ in _BINS[:-1])
    return domain


def _effective_level(domain: DomainResult) -> Level:
    """领域完全无可评估条目时，按「无重复」参与查表，同时整体标 provisional。

    注意这只对**部分**领域证据不足成立：四个领域一条都没评出来时，查表得到的
    「无重复」是凭空来的，必须整体判成 `None`（见 `aggregate`），不能落进四档。
    """
    return domain.level or 'none'


# --------------------------------------------------------------------------- 整体判定


def build_overall_reason(result: AssessmentResult) -> tuple[str, str]:
    """模板化生成整体判定理由 —— 不用 LLM 写，保证文字与判定永远一致。"""
    by_seq = {d.seq: d for d in result.domains}
    d1, d2, d3, d4 = (by_seq.get(i) for i in (1, 2, 3, 4))
    if not all((d1, d2, d3, d4)):
        return '', ''
    if result.overall_level is None:
        # 无法判定也要给出理由：报告里留一句空白，看的人只会以为是渲染坏了
        total = len(result.items)
        return (
            f'{total} 个条目全部无法评分（证据不足或模型未返回判定），本次评估**无法判定**重复程度。'
            f'请检查两篇综述的原文是否完整可读，或重新发起一次评估。',
            f'All {total} items were unscorable (insufficient evidence or no verdict returned); '
            f'the degree of duplication could not be determined.',
        )

    def part_zh(d: DomainResult) -> str:
        if d.level is None:
            return f'「{d.name_zh.split("：")[-1]}」证据不足（{d.unclear_count} 条无法评分）'
        return (
            f'「{d.name_zh.split("：")[-1]}」得分 {d.score_sum}/{d.score_max}'
            f'（重复度 {d.pct}%）{LEVEL_LABEL_ZH[d.level]}'
        )

    def part_en(d: DomainResult) -> str:
        if d.level is None:
            return f'"{d.name_en.split(": ")[-1]}" insufficient evidence'
        return (
            f'"{d.name_en.split(": ")[-1]}" scored {d.score_sum}/{d.score_max} '
            f'({d.pct}% duplication) {LEVEL_LABEL_EN[d.level]}'
        )

    ks = key_state(_effective_level(d1), _effective_level(d3))
    col = nonkey_col(_effective_level(d2), _effective_level(d4))

    zh = (
        f'关键领域：{part_zh(d1)}、{part_zh(d3)}，{KEY_STATE_LABEL_ZH[ks]}；'
        f'非关键领域：{part_zh(d2)}、{part_zh(d4)}，{NONKEY_COL_LABEL_ZH[col]}。'
        f'按表 3 判定为**{LEVEL_LABEL_ZH[result.overall_level]}**。'
    )
    if result.provisional:
        zh += '注：关键领域存在证据不足，本结论为初步判定，须经人工复核后方可引用。'
    if result.review_count:
        zh += f'另有 {result.review_count} 条目标记为待人工复核。'

    en = (
        f'Key domains: {part_en(d1)}, {part_en(d3)}; '
        f'non-key domains: {part_en(d2)}, {part_en(d4)}. '
        f'Table 3 verdict: **{LEVEL_LABEL_EN[result.overall_level]}**.'
    )
    if result.provisional:
        en += ' Note: evidence is insufficient in a key domain; this verdict is provisional.'
    return zh, en


def aggregate(result: AssessmentResult, cfg: EngineConfig | None = None) -> AssessmentResult:
    """就地完成领域打分 + 整体判定 + 理由生成。

    人工覆盖某条目后重新调用本函数即可重算，无需重跑 LLM。
    """
    cfg = cfg or EngineConfig()
    for domain in result.domains:
        score_domain(domain, cfg)

    by_seq = {d.seq: d for d in result.domains}
    if len(by_seq) != DOMAIN_COUNT:
        raise ValueError(f'需要 {DOMAIN_COUNT} 个领域，实际 {sorted(by_seq)}')

    items = result.items
    scores = [it.score for it in items if it.score is not None]

    key = (_effective_level(by_seq[1]), _effective_level(by_seq[3]))
    nonkey = (_effective_level(by_seq[2]), _effective_level(by_seq[4]))
    # 一条都没评出来时不许查表。查表会拿四个「证据不足按无重复算」凑出一个
    # 「无重复」——那和「两篇综述毫无重复」在前台长得一模一样，用户会拿它当结论。
    # 判定不出来就老实说判定不出来（level=None → 前台渲染「无法判定」的中性灰）。
    result.overall_level = overall_of(key, nonkey) if scores else None

    result.overall_score_sum = sum(scores)
    result.overall_score_max = SCORE_PER_ITEM * len(scores)
    result.overall_score_max_full = SCORE_PER_ITEM * len(items)
    result.overall_pct = dup_pct(result.overall_score_sum, result.overall_score_max)
    result.unclear_count = sum(1 for it in items if it.effective_verdict == 'unclear')
    result.review_count = sum(1 for it in items if it.needs_review)
    result.provisional = not (by_seq[1].evidence_sufficient and by_seq[3].evidence_sufficient)

    result.overall_reason_zh, result.overall_reason_en = build_overall_reason(result)
    return result


# --------------------------------------------------------------------------- 结果骨架


def build_skeleton(verdicts: dict[str, ItemResult] | None = None) -> AssessmentResult:
    """按清单结构搭出完整的 4 领域 / 12 分组 / 34 条目骨架。

    :param verdicts: {条目编号: ItemResult}，缺的条目自动补成 unclear
    """
    verdicts = verdicts or {}
    result = AssessmentResult()
    for d in DOMAINS:
        dr = DomainResult(seq=d.seq, name_zh=d.name_zh, name_en=d.name_en, is_key=d.is_key)
        for g in d.groups:
            gr = GroupResult(code=g.code, name_zh=g.name_zh, name_en=g.name_en)
            for it in g.items:
                got = verdicts.get(it.code)
                if got is None:
                    got = ItemResult(code=it.code, rating='unclear', needs_review=True,
                                     review_note='未产出评分结果')
                got.group_code = GROUP_OF_ITEM[it.code]
                got.domain_seq = DOMAIN_OF_ITEM[it.code]
                got.question_zh = it.question_zh
                got.question_en = it.question_en
                got.judge_mode = it.judge_mode
                gr.items.append(got)
            dr.groups.append(gr)
        result.domains.append(dr)
    return result


#: 老式三态判定 → 评分。dup 折成 0 分、diff 折成 3 分，即两端满打满算，
#: 这样 0.6.0 的历史 verdict 文件算出来的百分比与当年完全一致。
_VERDICT_RATING: dict[str, Rating] = {'dup': '0', 'diff': '3', 'unclear': 'unclear'}


def from_rating_map(mapping: dict[str, str], cfg: EngineConfig | None = None) -> AssessmentResult:
    """从 {条目编号: '0'|'1'|'2'|'3'|'unclear'} 直接算出完整判定 —— 离线验证与单测用。

    方法学专家不碰模型就能验证「条目评分 → 领域 → 整体结论」这条链路和 Excel 是否一致。
    """
    unknown = set(mapping) - set(ITEM_BY_CODE)
    if unknown:
        raise ValueError(f'未知条目编号：{sorted(unknown)}')
    items = {code: ItemResult(code=code, rating=str(v)) for code, v in mapping.items()}  # type: ignore[arg-type]
    result = build_skeleton(items)
    result.engine_version = ENGINE_VERSION
    result.criteria_version = CRITERIA_VERSION
    return aggregate(result, cfg)


def from_verdict_map(mapping: dict[str, str], cfg: EngineConfig | None = None) -> AssessmentResult:
    """从 {条目编号: 'dup'|'diff'|'unclear'} 算出完整判定 —— 兼容 0.6.0 的历史文件。"""
    bad = {v for v in mapping.values() if v not in _VERDICT_RATING}
    if bad:
        raise ValueError(f'未知判定值：{sorted(bad)}（应为 dup / diff / unclear）')
    return from_rating_map({code: _VERDICT_RATING[v] for code, v in mapping.items()}, cfg)
