# -*- coding: utf-8 -*-
"""
语料质量报告：`action_literature` 入库后的第一份体检

跑法：python -m tools.lit_report

回答的是三个问题：这批语料**能支撑哪些研究方向**、**哪些记录不能直接用**、
**「近3-5年核心文献」这个承诺在多少个方向上兑现得了**。
"""
from __future__ import annotations

import json
import re
from collections import Counter

import psycopg2

DB = dict(host='127.0.0.1', port=5432, user='postgres', password='123456', dbname='action')
CURRENT_YEAR = 2026


def jl(s):
    try:
        return json.loads(s) if s else []
    except (json.JSONDecodeError, TypeError):
        return []


def bar(n, total, width=34):
    k = int(round(n / max(total, 1) * width))
    return '█' * k + '·' * (width - k)


def main():
    c = psycopg2.connect(**DB)
    cur = c.cursor()
    cur.execute("""select corpus_no, year, year_confidence, lang, study_design, sample_size,
                          effect_direction, contamination, contamination_note, condition,
                          intervention, comparator, acu_points, journal, country, title,
                          text_chars, pages, acu_deqi
                   from action_literature order by corpus_no""")
    rows = cur.fetchall()
    N = len(rows)
    print('=' * 82)
    print(f'针灸文献知识库 · 语料质量报告   共 {N} 篇')
    print('=' * 82)

    # ── 1 语言与体量 ──
    lang = Counter(r[3] for r in rows)
    chars = sorted(r[16] or 0 for r in rows)
    print('\n【1】语言与体量')
    print(f'   中文 {lang.get("zh", 0)} 篇 · 英文 {lang.get("en", 0)} 篇')
    print(f'   正文字符 中位 {chars[N // 2]:,} · P10 {chars[N // 10]:,} · P90 {chars[N * 9 // 10]:,} · 合计 {sum(chars):,}')
    print(f'   总页数 {sum(r[17] or 0 for r in rows):,}')

    # ── 2 研究类型 ──
    print('\n【2】研究设计分布')
    dz = Counter(r[4] for r in rows)
    label = {'rct': '随机对照试验 RCT', 'nrct': '非随机对照 nRCT', 'animal': '动物/机制研究',
             'sr_meta': '系统综述/Meta', 'case_series': '病例系列', 'protocol': '研究方案(无结果)',
             'other': '其他'}
    for k, v in dz.most_common():
        print(f'   {label.get(k, k):<20}{v:>4} 篇 {bar(v, N)} {v * 100 / N:.1f}%')
    if dz.get('protocol'):
        print(f'   ⚠ protocol {dz["protocol"]} 篇无结果数据，检索时须排除，不得作疗效证据')

    # ── 3 效应方向：发表偏倚 ──
    print('\n【3】效应方向（发表偏倚指标）')
    ed = Counter(r[6] for r in rows)
    lab2 = {'positive': '阳性（优于对照）', 'no_difference': '无差异', 'negative': '阴性（劣于对照）',
            'unclear': '无法判定'}
    for k in ('positive', 'no_difference', 'negative', 'unclear'):
        v = ed.get(k, 0)
        print(f'   {lab2[k]:<20}{v:>4} 篇 {bar(v, N)} {v * 100 / N:.1f}%')
    pos_rate = ed.get('positive', 0) / max(N - ed.get('unclear', 0), 1) * 100
    print(f'   → 可判定文献中阳性率 {pos_rate:.1f}%')
    for lg in ('zh', 'en'):
        sub = [r for r in rows if r[3] == lg and r[6] != 'unclear']
        if sub:
            p = len([r for r in sub if r[6] == 'positive']) / len(sub) * 100
            print(f'     {"中文" if lg == "zh" else "英文"}文献阳性率 {p:.1f}%（n={len(sub)}）')

    # ── 4 年份 ──
    print('\n【4】出版年份')
    ys = [r[1] for r in rows if r[1] and r[2] == 'high']
    lowc = [r for r in rows if r[2] != 'high']
    if ys:
        print(f'   年份可信 {len(ys)} 篇（{min(ys)}–{max(ys)}）· 中位 {sorted(ys)[len(ys) // 2]}')
    print(f'   年份不可信/缺失 {len(lowc)} 篇 → {[r[0] for r in lowc][:20]}')
    for lo, hi, lbl in ((2021, 2026, '近5年 2021-2026'), (2023, 2026, '近3年 2023-2026')):
        k = len([y for y in ys if lo <= y <= hi])
        print(f'   {lbl:<18}{k:>4} 篇 {bar(k, N)} {k * 100 / N:.1f}%')
    dec = Counter((y // 5 * 5) for y in ys)
    print('   分布：' + '  '.join(f'{d}-{d + 4}:{n}' for d, n in sorted(dec.items())))

    # ── 5 语料治理 ──
    print('\n【5】语料治理：需人工核对的记录')
    contam = [r for r in rows if r[7] == '1']
    print(f'   PDF 夹带其他论文内容        {len(contam):>4} 篇 {bar(len(contam), N)} {len(contam) * 100 / N:.1f}%')
    print(f'   年份无法确定                 {len(lowc):>4} 篇')
    nosample = [r for r in rows if not r[5] and r[4] in ('rct', 'nrct')]
    print(f'   对照试验但无样本量           {len(nosample):>4} 篇')
    nopts = [r for r in rows if not jl(r[12]) and r[4] in ('rct', 'nrct', 'case_series')]
    print(f'   临床研究但未抽到穴位         {len(nopts):>4} 篇')
    need = {r[0] for r in contam} | {r[0] for r in lowc} | {r[0] for r in nosample} | {r[0] for r in nopts}
    print(f'   ── 合计需人工核对             {len(need):>4} 篇 ({len(need) * 100 / N:.1f}%)')

    print('\n   夹带位置分布（据 contamination_note 判定）：')
    where = Counter()
    for r in contam:
        note = r[8] or ''
        if re.search(r'参考文献|reference', note, re.I):
            where['仅参考文献区'] += 1
        elif re.search(r'开头|前部|首页|标题前|开始', note):
            where['正文开头'] += 1
        elif re.search(r'末尾|后部|结尾', note):
            where['正文末尾'] += 1
        else:
            where['其他/未明确'] += 1
    for k, v in where.most_common():
        print(f'      {k:<16}{v:>4} 篇 ({v * 100 // max(len(contam), 1)}%)')

    # ── 6 病种覆盖 ──
    print('\n【6】病种覆盖（决定哪些研究方向撑得住）')
    cond = Counter()
    cond_recent = Counter()
    for r in rows:
        for x in jl(r[9]):
            key = str(x).strip()[:20]
            if key:
                cond[key] += 1
                if r[1] and r[2] == 'high' and r[1] >= 2021:
                    cond_recent[key] += 1
    print(f'   共出现 {len(cond)} 个病种标签，Top 22：')
    print(f'   {"病种":<24}{"总数":>5}{"近5年":>7}   支撑度')
    for k, v in cond.most_common(22):
        rc = cond_recent.get(k, 0)
        ok = '✓ 可写背景' if v >= 8 and rc >= 3 else ('△ 勉强' if v >= 5 else '✗ 覆盖不足')
        print(f'   {k:<24}{v:>5}{rc:>7}   {ok}')
    strong = [k for k, v in cond.items() if v >= 8 and cond_recent.get(k, 0) >= 3]
    print(f'\n   → 达到「可写背景」门槛(总数≥8 且近5年≥3)的病种：{len(strong)} 个')
    print(f'     {", ".join(strong[:18])}')

    # ── 7 干预与对照 ──
    print('\n【7】干预与对照')
    itv = Counter(str(x)[:14] for r in rows for x in jl(r[10]))
    cmp_ = Counter(str(x)[:14] for r in rows for x in jl(r[11]))
    print('   干预 Top10：' + ' · '.join(f'{k}({v})' for k, v in itv.most_common(10)))
    print('   对照 Top10：' + ' · '.join(f'{k}({v})' for k, v in cmp_.most_common(10)))
    sham = len([r for r in rows if any(re.search('假针|安慰|sham', str(x), re.I) for x in jl(r[11]))])
    print(f'   假针刺对照 {sham} 篇 ({sham * 100 // N}%) —— 这批是「针刺 vs 安慰针」证据的来源')

    # ── 8 针灸参数 ──
    print('\n【8】针灸专属字段完整度')
    pts = Counter(p for r in rows for p in jl(r[12]))
    haspt = len([r for r in rows if jl(r[12])])
    deqi = Counter(r[18] for r in rows)
    print(f'   抽到穴位的文献 {haspt} 篇 ({haspt * 100 // N}%)，共 {len(pts)} 个不同穴位')
    print('   高频穴位 Top15：' + ' · '.join(f'{k}({v})' for k, v in pts.most_common(15)))
    print(f'   报告得气：是 {deqi.get("1", 0)} · 否 {deqi.get("0", 0)} · 未提及 {deqi.get(None, 0)}')

    # ── 9 期刊 ──
    print('\n【9】期刊分布 Top12')
    jr = Counter((r[13] or '(缺)')[:34] for r in rows)
    for k, v in jr.most_common(12):
        print(f'   {k:<36}{v:>4}')

    cur.close()
    c.close()


if __name__ == '__main__':
    main()
