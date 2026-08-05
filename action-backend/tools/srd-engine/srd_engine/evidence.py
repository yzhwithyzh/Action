"""代码取证 —— 只算客观事实，不下判定.

3a / 6a / 8b 三条目涉及「数清单」和「读数字」，LLM 从长文本里做这两件事本来就不可靠，
而它们恰是重复性最直接的证据。这里用代码算好，作为「客观事实卡」塞进提示词，
判定权仍在 LLM（见 DESIGN.md §4.4）。
"""

from __future__ import annotations

import math
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from srd_engine.schemas import ExtractDoc, IncludedStudy, PooledResult

VOCAB_DIR = Path(__file__).parent / 'vocab'

# 比值型效应指标：比较大小时要取对数（1 是无效线）
_RATIO_MEASURES = {'RR', 'OR', 'HR', 'IRR'}


# --------------------------------------------------------------------------- 词表归一


@lru_cache(maxsize=1)
def _databases_index() -> dict[str, str]:
    data = yaml.safe_load((VOCAB_DIR / 'databases.yaml').read_text(encoding='utf-8')) or {}
    return _build_index(data)


@lru_cache(maxsize=8)
def _measures_index(category: str) -> dict[str, str]:
    data = yaml.safe_load((VOCAB_DIR / 'measures.yaml').read_text(encoding='utf-8')) or {}
    return _build_index(data.get(category, {}))


def _build_index(mapping: dict[str, list[str]]) -> dict[str, str]:
    index: dict[str, str] = {}
    for canonical, aliases in mapping.items():
        index[_norm(canonical)] = canonical
        for alias in aliases or []:
            index[_norm(alias)] = canonical
    return index


def _norm(text: str) -> str:
    """归一：全角转半角、去空白与常见标点、转小写。"""
    text = unicodedata.normalize('NFKC', str(text)).lower()
    return re.sub(r'[\s\-_/\\.,;:()（）\[\]「」【】、]+', '', text)


def canonicalize(values: list[str], index: dict[str, str]) -> tuple[set[str], list[str]]:
    """把一组词映射到标准名。返回 (标准名集合, 未识别的原词)。"""
    known: set[str] = set()
    unknown: list[str] = []
    for raw in values or []:
        key = _norm(raw)
        if not key:
            continue
        hit = index.get(key)
        if hit is None:
            # 退一步做包含匹配，容忍 "PubMed (via NCBI)" 这类写法
            hit = next((c for k, c in index.items() if k and (k in key or key in k)), None)
        if hit:
            known.add(hit)
        else:
            unknown.append(str(raw).strip())
    return known, unknown


def canonical_databases(values: list[str]) -> tuple[set[str], list[str]]:
    return canonicalize(values, _databases_index())


def canonical_measures(values: list[str]) -> tuple[set[str], list[str]]:
    return canonicalize(values, _measures_index('effect_measures'))


def jaccard(a: set, b: set) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


# --------------------------------------------------------------------------- 6a 纳入研究重叠


def study_key(study: IncludedStudy) -> str:
    """归一化匹配键，优先级 registry_id > doi > (作者姓, 年份)。"""
    if study.registry_id:
        return f'reg:{_norm(study.registry_id)}'
    if study.doi:
        return f'doi:{_norm(study.doi)}'
    author = _norm(study.first_author)
    if author and study.year:
        return f'ay:{author}:{study.year}'
    if study.label:
        return f'lb:{_norm(study.label)}'
    return f'lb:{author or "?"}'


def study_overlap(a: list[IncludedStudy], b: list[IncludedStudy]) -> dict:
    """两篇纳入研究的交并集。

    双综述场景下 CCA（Corrected Covered Area, Pieper 2014）与 Jaccard 恒等：
        CCA = (r - N) / (N*c - N)，c=2, r=|A|+|B|, N=|A∪B|  ⟹  |A∩B| / |A∪B|
    这里同时返回，便于报告里按方法学同行熟悉的名字呈现。
    """
    ka = {study_key(s): s for s in a}
    kb = {study_key(s): s for s in b}
    inter = set(ka) & set(kb)
    union = set(ka) | set(kb)
    j = len(inter) / len(union) if union else 0.0
    return {
        'count_a': len(ka),
        'count_b': len(kb),
        'intersection': len(inter),
        'union': len(union),
        'jaccard': round(j, 4),
        'cca': round(j, 4),
        'shared_labels': sorted(_label(ka[k]) for k in inter),
        'only_a': sorted(_label(ka[k]) for k in set(ka) - inter),
        'only_b': sorted(_label(kb[k]) for k in set(kb) - inter),
    }


def _label(s: IncludedStudy) -> str:
    if s.label:
        return s.label
    base = s.first_author or '?'
    return f'{base} {s.year}' if s.year else base


def count_mismatch(extract: ExtractDoc) -> str:
    """抽取到的纳入研究数与原文自述数不符 → 该篇清单不可靠，须人工确认。"""
    reported = extract.result.included_count_reported
    got = len(extract.result.included_studies)
    if reported and got and reported != got:
        return f'抽取到 {got} 项，原文自述 {reported} 项'
    return ''


# --------------------------------------------------------------------------- 8b 合并效应比较


def _log_if_ratio(value: float, measure: str) -> float:
    if measure.upper() in _RATIO_MEASURES:
        return math.log(value) if value > 0 else float('nan')
    return value


def _interval_overlap(a_low: float, a_high: float, b_low: float, b_high: float) -> float:
    lo, hi = max(a_low, b_low), min(a_high, b_high)
    if hi <= lo:
        return 0.0
    widths = [a_high - a_low, b_high - b_low]
    narrow = min(w for w in widths if w > 0) if any(w > 0 for w in widths) else 0.0
    return round(min(1.0, (hi - lo) / narrow), 4) if narrow else 0.0


def _outcome_key(name: str) -> str:
    return _norm(name)


def compare_pooled(a: list[PooledResult], b: list[PooledResult]) -> list[dict]:
    """逐个共同结局比较方向 / 大小 / 置信区间重叠。"""
    index_b = {_outcome_key(r.outcome): r for r in b if r.outcome}
    rows: list[dict] = []
    for ra in a:
        rb = index_b.get(_outcome_key(ra.outcome))
        if rb is None:
            continue
        row: dict = {
            'outcome': ra.outcome,
            'measure_a': ra.measure,
            'measure_b': rb.measure,
            'a': _fmt_effect(ra),
            'b': _fmt_effect(rb),
            'same_measure': _norm(ra.measure) == _norm(rb.measure),
        }
        if ra.point is not None and rb.point is not None:
            la = _log_if_ratio(ra.point, ra.measure)
            lb = _log_if_ratio(rb.point, rb.measure)
            if not (math.isnan(la) or math.isnan(lb)):
                row['same_direction'] = (la >= 0) == (lb >= 0)
                hi = max(abs(la), abs(lb))
                row['magnitude_ratio'] = round(min(abs(la), abs(lb)) / hi, 4) if hi else 1.0
        if None not in (ra.ci_low, ra.ci_high, rb.ci_low, rb.ci_high):
            row['ci_overlap'] = _interval_overlap(
                _log_if_ratio(ra.ci_low, ra.measure),  # type: ignore[arg-type]
                _log_if_ratio(ra.ci_high, ra.measure),  # type: ignore[arg-type]
                _log_if_ratio(rb.ci_low, rb.measure),  # type: ignore[arg-type]
                _log_if_ratio(rb.ci_high, rb.measure),  # type: ignore[arg-type]
            )
            row['significant_a'] = _is_significant(ra)
            row['significant_b'] = _is_significant(rb)
        rows.append(row)
    return rows


def _is_significant(r: PooledResult) -> bool:
    """置信区间是否跨过无效线（比值型为 1，差值型为 0）。"""
    if r.ci_low is None or r.ci_high is None:
        return False
    null_value = 1.0 if r.measure.upper() in _RATIO_MEASURES else 0.0
    return not (r.ci_low <= null_value <= r.ci_high)


def _fmt_effect(r: PooledResult) -> str:
    if r.point is None:
        return '未报告'
    ci = f' ({r.ci_low}, {r.ci_high})' if r.ci_low is not None and r.ci_high is not None else ''
    extra = []
    if r.k:
        extra.append(f'k={r.k}')
    if r.i2 is not None:
        extra.append(f'I²={r.i2}%')
    tail = f'  [{", ".join(extra)}]' if extra else ''
    return f'{r.measure} {r.point}{ci}{tail}'


# --------------------------------------------------------------------------- 证据卡


def build_evidence_card(code: str, a: ExtractDoc, b: ExtractDoc) -> str:
    """为 3a / 6a / 8b 生成塞进提示词的「客观事实」文本。其余条目返回空串。"""
    if code == '3a':
        return _card_3a(a, b)
    if code == '6a':
        return _card_6a(a, b)
    if code == '8b':
        return _card_8b(a, b)
    return ''


def _card_3a(a: ExtractDoc, b: ExtractDoc) -> str:
    sa, unknown_a = canonical_databases(a.method.databases.value + a.method.extra_sources.value)
    sb, unknown_b = canonical_databases(b.method.databases.value + b.method.extra_sources.value)
    if not sa and not sb:
        return ''
    lines = [
        f'综述A 的检索来源（{len(sa)} 个）：{"、".join(sorted(sa)) or "无"}',
        f'综述B 的检索来源（{len(sb)} 个）：{"、".join(sorted(sb)) or "无"}',
        f'交集（{len(sa & sb)} 个）：{"、".join(sorted(sa & sb)) or "无"}',
        f'仅A 有：{"、".join(sorted(sa - sb)) or "无"}',
        f'仅B 有：{"、".join(sorted(sb - sa)) or "无"}',
        f'Jaccard 相似度：{jaccard(sa, sb):.2f}',
    ]
    if unknown_a or unknown_b:
        lines.append(f'未能归一化的来源（请自行判断）：A={unknown_a or "无"}；B={unknown_b or "无"}')
    return '\n'.join(lines)


def _card_6a(a: ExtractDoc, b: ExtractDoc) -> str:
    ov = study_overlap(a.result.included_studies, b.result.included_studies)
    if not ov['union']:
        return ''
    lines = [
        f'综述A 纳入 {ov["count_a"]} 项，综述B 纳入 {ov["count_b"]} 项',
        f'交集 {ov["intersection"]} 项，并集 {ov["union"]} 项',
        f'Jaccard = {ov["jaccard"]:.2f}（双综述下 CCA 与之等值）',
        f'共同纳入的研究：{"、".join(ov["shared_labels"][:30]) or "无"}',
        f'仅A 纳入：{"、".join(ov["only_a"][:20]) or "无"}',
        f'仅B 纳入：{"、".join(ov["only_b"][:20]) or "无"}',
    ]
    for tag, ex in (('A', a), ('B', b)):
        warn = count_mismatch(ex)
        if warn:
            lines.append(f'⚠ 综述{tag} 的纳入研究清单可能不完整：{warn}')
    return '\n'.join(lines)


def _card_8b(a: ExtractDoc, b: ExtractDoc) -> str:
    rows = compare_pooled(a.result.pooled_results, b.result.pooled_results)
    if not rows:
        return ''
    lines = []
    for r in rows:
        parts = [f'结局「{r["outcome"]}」：A = {r["a"]}；B = {r["b"]}']
        if not r['same_measure']:
            parts.append('（两篇效应指标不同）')
        if 'same_direction' in r:
            parts.append(f'方向{"一致" if r["same_direction"] else "相反"}')
            parts.append(f'效应量比 {r["magnitude_ratio"]:.2f}')
        if 'ci_overlap' in r:
            parts.append(f'置信区间重叠 {r["ci_overlap"]:.0%}')
            if 'significant_a' in r:
                parts.append(
                    f'统计显著性：A={"显著" if r["significant_a"] else "不显著"}，'
                    f'B={"显著" if r["significant_b"] else "不显著"}'
                )
        lines.append('；'.join(parts))
    return '\n'.join(lines)
