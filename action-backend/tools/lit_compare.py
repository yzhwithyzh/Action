# -*- coding: utf-8 -*-
"""
把模型抽取（lit_out/papers.jsonl）与助手抽取（lit_out/extracted.py）逐字段比对。

比的是**判定会不会不同**，不是措辞是否一致：`effect_direction` 判错会让不一致检测失效，
`year_confidence` 判错会让「近3-5年」推荐位混进旧文献，这两项是钉死的重点。
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lit_out.extracted import PAPERS  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lit_out', 'papers.jsonl')
MINE = {p['id']: p for p in PAPERS}

model = {}
with open(OUT, encoding='utf-8') as fh:
    for line in fh:
        line = line.strip()
        if line:
            r = json.loads(line)
            model[r['id']] = r


def pts(p):
    """穴位归一到国际代码集合，便于比较（我的记法是 'ST25天枢'，模型是 'ST25'）"""
    raw = ((p.get('acupuncture') or {}).get('points')) or []
    out = set()
    for x in raw:
        m = re.match(r'([A-Z]{2,3}-?[A-Z]{0,2}\d{1,2})', str(x).upper().replace(' ', ''))
        if m:
            out.add(m.group(1))
        else:
            out.add(str(x)[:4])
    return out


KEY = ['year', 'year_confidence', 'journal', 'sample_size', 'study_design', 'effect_direction', 'contamination']
errs = {k: 0 for k in KEY}
errs['points'] = 0
n = 0

print(f'{"id":<6}{"字段":<18}{"模型":<34}{"助手":<34}')
print('-' * 96)
for pid in sorted(model):
    if pid not in MINE:
        continue
    m, a = model[pid], MINE[pid]
    if 'error' in m:
        print(f'#{pid:<5}{"[抽取失败]":<18}{m["error"][:60]}')
        continue
    n += 1
    for k in KEY:
        mv, av = m.get(k), a.get(k)
        if k == 'journal':
            same = bool(mv) == bool(av)          # 只比「有没有」，中英文名不算差异
        elif k == 'year_confidence':
            same = (mv == av)
        else:
            same = (mv == av)
        if not same:
            errs[k] += 1
            print(f'#{pid:<5}{k:<18}{str(mv)[:32]:<34}{str(av)[:32]:<34}')
    pm, pa = pts(m), pts(a)
    if pm != pa:
        errs['points'] += 1
        print(f'#{pid:<5}{"points":<18}{("|".join(sorted(pm)) or "(空)")[:32]:<34}{("|".join(sorted(pa)) or "(空)")[:32]:<34}')

print('-' * 96)
print(f'比对 {n} 篇，各字段不一致篇数：')
for k, v in errs.items():
    mark = '  ★关键' if k in ('effect_direction', 'year', 'year_confidence') else ''
    print(f'   {k:<20}{v:>3} / {n}{mark}')

print('\n=== 模型标记为 contamination 的条目 ===')
for pid in sorted(model):
    m = model[pid]
    if m.get('contamination'):
        mine_flag = MINE.get(pid, {}).get('contamination')
        print(f'  #{pid:<5}（助手：{"也标了" if mine_flag else "未标记"}）{m.get("contamination_note", "")[:88]}')
