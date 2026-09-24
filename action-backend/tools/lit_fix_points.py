"""
取穴归一与体系回填：把 `action_literature.acu_points` 统一到标准写法，并填 `acu_system`

跑法（工作目录 action-backend/）::

    python -m tools.lit_fix_points --check   # 只体检，不写库
    python -m tools.lit_fix_points           # 归一并回填

## 修的是什么

实测全库 679 种穴位写法、3513 次出现，其中三类需要收口：

1. **EX 系丢了连字符**（29 种 / 161 次）：`EXHN3` 不是标准写法，`EX-HN3` 才是
2. **别名代码**（`DU20` = `GV20` 百会、`RN12` = `CV12` 中脘、`SJ5` = `TE5` 外关…）
   —— 同一个穴位算成两个，穴位共现网络与「两项研究取穴是否相同」的判断都会错
3. **非经穴体系混在一起**：耳穴（CO/TF/AT/AH）、头针（MS）、阿是穴、蒙医、
   长圆针解剖点 —— 与十四经穴不在同一个坐标系，硬比得出「取穴完全不同」这种
   既正确又无用的结论

**耳穴的 `CO` 不是任脉别名。** 实测 CO4/CO15/CO18 只出现在耳针论文里，与 TF4/AT4/
AH6a 同现，是 WHO/ISO 的耳甲分区码。把它映射成 CV 会是一个真实的错误 —— 这也是为什么
别名表要手写、不能按「两个字母 + 数字」的模式硬套。

## 不动 embedding

`embed_text` 用的是标题/病种/干预/结局/摘要/结论，**不含取穴**，所以归一取穴不会让
向量过期，不需要重算。改动前确认过这一点。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

import psycopg2
from psycopg2.extras import execute_batch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from module_action.service.acupoint_norm import classify_system, normalize_points  # noqa: E402

DB = dict(host='127.0.0.1', port=5432, user='postgres', password='123456', dbname='action')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只体检不写库')
    args = ap.parse_args()

    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    cur.execute("select lit_id, corpus_no, acu_points, acu_system, acu_method from action_literature where del_flag='0'")
    rows = cur.fetchall()

    changed, ups, sys_cnt = [], [], Counter()
    pair_cnt: Counter = Counter()
    for lit_id, no, raw, old_sys, method in rows:
        try:
            pts = json.loads(raw or '[]')
        except (json.JSONDecodeError, TypeError):
            pts = []
        fixed = normalize_points(pts)
        # 针法要传进去：单字脏器名（肝/肾/脾）光看名字判不了体系
        system = classify_system(fixed, method or '')
        sys_cnt[system or '(无取穴)'] += 1
        for a, b in zip(pts, fixed):
            if str(a) != b:
                pair_cnt[f'{a} → {b}'] += 1
        if fixed != [str(x) for x in pts] or (old_sys or '') != system:
            changed.append(no)
            ups.append((json.dumps(fixed, ensure_ascii=False), system, lit_id))

    print(f'全库 {len(rows)} 篇，取穴或体系需更新 {len(changed)} 篇\n')
    print('体系分布：')
    for k, v in sys_cnt.most_common():
        print(f'  {k:<12}{v:>4} 篇')
    print(f'\n归一改写 {sum(pair_cnt.values())} 处，{len(pair_cnt)} 种：')
    for k, v in pair_cnt.most_common(40):
        print(f'  {v:>3}  {k}')

    if args.check:
        cur.close()
        conn.close()
        return

    execute_batch(cur, 'update action_literature set acu_points=%s, acu_system=%s, update_time=now() '
                       'where lit_id=%s', ups, page_size=100)
    conn.commit()
    cur.execute("""select acu_system, count(*) from action_literature where del_flag='0'
                   group by 1 order by 2 desc""")
    print('\n落库后体系分布：')
    for k, v in cur.fetchall():
        print(f'  {k or "(空)":<12}{v:>4}')
    cur.execute("select acu_points from action_literature where del_flag='0'")
    pts = Counter(p for (r,) in cur.fetchall() for p in json.loads(r or '[]'))
    print(f'\n归一后不同穴位写法 {len(pts)} 种（原 679），高频：')
    print('  ' + ' · '.join(f'{k}({v})' for k, v in pts.most_common(12)))
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
