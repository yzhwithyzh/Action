"""结果渲染：终端文本报告 + CSV 导出。"""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING

from srd_engine.aggregate import LEVEL_LABEL_ZH
from srd_engine.schemas import RATING_LABEL_ZH

if TYPE_CHECKING:
    from srd_engine.schemas import AssessmentResult, DomainResult, ItemResult

# 分越高越重复，标记按「重复程度」排（不按分数大小排）：●=完全相同 … ○=完全不同
_RATING_MARK = {'3': '●', '2': '◐', '1': '◔', '0': '○', 'unclear': '?'}


def _render_item(it: ItemResult, verbose: bool) -> str:
    tail = ''
    if it.needs_review:
        tail += ' ⚠待复核'
    if it.override_rating:
        tail += ' ✎人工覆盖'
    rating = it.effective_rating
    score = '－' if it.score is None else f'{it.score}分'
    lines = [
        f'      {_RATING_MARK[rating]} {it.code:<4} {score:<4}'
        f'{RATING_LABEL_ZH[rating]:<5}{it.reason_zh[:60]}{tail}'
    ]
    if verbose:
        if it.evidence_card:
            lines.append(f'           客观事实：{it.evidence_card.splitlines()[0]}')
        if it.cite_a:
            lines.append(f'           A："{it.cite_a[:90]}"')
        if it.cite_b:
            lines.append(f'           B："{it.cite_b[:90]}"')
        if it.review_note:
            lines.append(f'           复核原因：{it.review_note}')
    return '\n'.join(lines) + '\n'


def _domain_flags(d: DomainResult) -> str:
    flag = '' if d.evidence_sufficient else '  ⚠证据不足'
    return flag + ('  ⚠临界' if d.near_boundary else '')


def render_text(result: AssessmentResult, verbose: bool = False) -> str:
    out = io.StringIO()
    w = out.write

    w('=' * 78 + '\n')
    w('SRD 系统综述重复性评估结果\n')
    w('=' * 78 + '\n')
    w(f'综述A：{result.review_a_title or "（未知）"}\n')
    w(f'综述B：{result.review_b_title or "（未知）"}\n\n')

    for d in result.domains:
        key = '【关键领域】' if d.is_key else '　　　　　　'
        level = LEVEL_LABEL_ZH[d.level] if d.level else '证据不足'
        w(f'{key} {d.name_zh}：得分 {d.score_sum}/{d.score_max}'
          f'（满分 {d.score_max_full}，重复度 {d.pct}%）→ {level}{_domain_flags(d)}\n')
        for g in d.groups:
            w(f'    {g.code}. {g.name_zh}\n')
            for it in g.items:
                w(_render_item(it, verbose))
        w('\n')

    w('-' * 78 + '\n')
    overall = LEVEL_LABEL_ZH[result.overall_level] if result.overall_level else '无法判定'
    w(f'整体判定：{overall}（总得分 {result.overall_score_sum}/{result.overall_score_max}，'
      f'名义满分 {result.overall_score_max_full}，重复度 {result.overall_pct}%）')
    w('  ※初步判定，须人工复核\n' if result.provisional else '\n')
    w(f'{result.overall_reason_zh}\n')
    w('-' * 78 + '\n')
    w(f'证据不足 {result.unclear_count} 条　待人工复核 {result.review_count} 条\n')
    w(f'模型 {result.model}　调用 {result.llm_calls} 次　'
      f'token 入 {result.token_in} / 出 {result.token_out}\n')
    w(f'{result.engine_version} | {result.prompt_version} | {result.criteria_version} | '
      f'粒度 {result.judge_granularity}\n')
    if result.errors:
        w(f'告警 {len(result.errors)} 条：\n')
        for e in result.errors[:20]:
            w(f'  - {e}\n')
    w('本工具为辅助判断，结论须由方法学专家确认后方可引用。\n')
    return out.getvalue()


def to_csv(result: AssessmentResult) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator='\n')
    writer.writerow(
        ['领域', '关键领域', '分组', '条目', '问题', '评分', '评分档位', '判定方式', '把握度', '待复核',
         '理由', '综述A引用', '综述B引用']
    )
    for d in result.domains:
        for g in d.groups:
            for it in g.items:
                writer.writerow([
                    d.name_zh, '是' if d.is_key else '否', f'{g.code} {g.name_zh}', it.code,
                    it.question_zh, '' if it.score is None else it.score,
                    RATING_LABEL_ZH[it.effective_rating], it.judge_mode, it.confidence,
                    '是' if it.needs_review else '', it.reason_zh, it.cite_a, it.cite_b,
                ])
    writer.writerow([])
    for d in result.domains:
        level = LEVEL_LABEL_ZH[d.level] if d.level else '证据不足'
        writer.writerow([d.name_zh, f'得分 {d.score_sum}/{d.score_max}',
                         f'满分 {d.score_max_full}', f'{d.pct}%', level])
    overall = LEVEL_LABEL_ZH[result.overall_level] if result.overall_level else '无法判定'
    writer.writerow(['整体判定', overall, f'得分 {result.overall_score_sum}/{result.overall_score_max}',
                     f'{result.overall_pct}%', result.overall_reason_zh])
    return buf.getvalue()
