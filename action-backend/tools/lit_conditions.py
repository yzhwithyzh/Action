"""
病种同义词归并：485 个原始标签 → 规范名 + 上位类目

跑法（工作目录 action-backend/）::

    python -m tools.lit_conditions            # 建/补词表 + 回填 + 前后对比
    python -m tools.lit_conditions --rebuild  # 重跑全部标签（人工修正的仍不覆盖）

## 为什么要归并

抽取产出的 `condition` 是模型按各篇原文写的自由标签，实测 566 篇出了 485 个不同标签、
80% 只出现一次。同一个病散在多个写法里 —— 失眠有 8 种写法共 31 篇，但单看任何一个
都不到覆盖度门槛。不归并的直接后果是：**覆盖度闸对几乎所有研究方向都判「本库撑不住」，
而库里其实有料。**

## 三层的分工，别混用

- ``raw``   原始标签，永不修改
- ``norm``  只合并同义词与异写（失眠症→失眠、干眼症→干眼）
- ``group`` 上位类目，覆盖度统计与检索扩展用（围绝经期失眠 / 原发性失眠 → 失眠）

**norm 与 group 必须分两层**：「围绝经期失眠」不是「失眠」的另一种写法——人群、病因、
干预方案、结局指标都可能不同，合并到 norm 就是把两类研究混为一谈，写进背景会出错。
但判「这个方向撑不撑得住」时它确实该算进失眠。一层解决不了这个矛盾。

## 人工修正优先

词表里 ``source='manual'`` 的行重跑时不覆盖。模型归并必然有判错的（尤其罕见病种），
人工改过一次就不该被下一次重跑冲掉 —— 同 `action_site_text` 的 `text_*` 那套道理。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict

import httpx
import psycopg2
from psycopg2.extras import execute_batch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB = dict(host='127.0.0.1', port=5432, user='postgres', password='123456', dbname='action')
#: 一批多少个标签。**别调大**：实测 90 个/批时服务端在生成完成前断开
#: （`RemoteProtocolError: Server disconnected without sending a response`），
#: 因为输出是 N 个 JSON 对象、长度随 N 线性增长，而这是 reasoning 模型、还要额外
#: 吐思维链 token。实测 30 个/批 35 秒稳定通过，60+ 开始不稳。
BATCH = 30
CONCURRENCY = 4
SYSTEMS = ['神经系统', '精神心理', '消化系统', '骨关节与软组织', '妇科与生殖', '泌尿男科',
           '肿瘤与放化疗', '呼吸系统', '内分泌代谢', '心血管', '五官科', '皮肤科',
           '围手术期与术后', '疼痛', '免疫与风湿', '儿科', '其他']

PROMPT = """你是医学术语规范化专家。下面是从针刺临床研究文献里抽取出的**病种标签**，
括号里是该标签在语料中出现的篇数。它们是各篇论文按自己的写法给出的，同一个病常有多种写法。

请为每一个标签给出三个字段，只输出一个 JSON 数组，不要解释、不要 markdown 围栏：

[{{"raw":"原标签","norm":"规范名","group":"上位类目","system":"系统分类"}}, ...]

**norm（规范名）** —— 只合并**同义词与异写**，即「同一个病的不同写法」：
   失眠症→失眠　干眼症→干眼　膝关节骨性关节炎→膝骨关节炎　卵巢储备功能减退→卵巢储备功能下降
   ⚠ **不同人群、不同病因、不同分型的，绝不合并到 norm**：
     「围绝经期失眠」保持原样，不并入「失眠」
     「卒中后抑郁」保持原样，不并入「抑郁症」
     「严重功能性便秘」保持原样，不并入「功能性便秘」
   没有更规范写法的，norm 就填原标签本身。

**group（上位类目）** —— 用于「本库对这个研究方向够不够」的统计，粒度比 norm 粗一档：
   失眠 / 慢性失眠 / 原发性失眠 / 围绝经期失眠 / 缺血性卒中后失眠 / 老年失眠症 → group 都是「失眠」
   功能性便秘 / 严重功能性便秘 / 卒中后便秘 / 便秘型肠易激综合征 → group 都是「便秘」
   膝骨关节炎 / 晚期膝关节骨关节炎 → group 都是「膝骨关节炎」
   卒中后抑郁 / 抑郁症 / 重性抑郁障碍 → group 都是「抑郁」
   脑卒中 / 脑梗死 / 急性脑梗死 / 缺血性脑卒中 → group 都是「脑卒中」
   group 用**最常用的通用病名**，不要造词，不要用「XX疾病」这类空泛类目。

**system** —— 从这个固定列表里选一个：{systems}
   并发症按**原发病所属系统**归（卒中后便秘 → 神经系统）。

标签清单：
{items}"""


def pick_model():
    code, key = os.environ.get('LLM_MODEL'), os.environ.get('LLM_KEY')
    base = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    if not (code and key):
        raise SystemExit('请设置 LLM_MODEL / LLM_KEY / LLM_BASE_URL')
    url = base.strip().rstrip('/')
    if not url.endswith('/chat/completions'):
        url = url + ('/v3/chat/completions' if url.endswith('/api') else '/chat/completions')
    return code, key, url, 'volces.com' in base


async def ask(client, model, key, url, ark, items, sem):
    body = '\n'.join(f'- {k}（{v}篇）' for k, v in items)
    payload = {'model': model, 'temperature': 0, 'stream': False,
               'messages': [{'role': 'user',
                             'content': PROMPT.format(systems=' / '.join(SYSTEMS), items=body)}]}
    if ark:
        payload['thinking'] = {'type': 'disabled'}
    async with sem:
        for attempt in (1, 2, 3):
            try:
                r = await client.post(url, json=payload,
                                      headers={'Authorization': f'Bearer {key}',
                                               'Content-Type': 'application/json'})
                r.raise_for_status()
                raw = (r.json()['choices'][0]['message']['content'] or '').strip()
                fence = re.search(r'```(?:json)?\s*(.+?)\s*```', raw, re.S)
                txt = fence.group(1) if fence else raw
                s, e = txt.find('['), txt.rfind(']')
                if s < 0 or e <= s:
                    raise ValueError('未返回 JSON 数组')
                return json.loads(txt[s:e + 1])
            except Exception as exc:  # noqa: BLE001
                if attempt == 3:
                    print(f'  ✗ 一批失败: {type(exc).__name__}: {exc}'[:120])
                    return []
                await asyncio.sleep(3 * attempt)


def coverage(cur, col: str, label: str, min_total=8, min_recent=3):
    """按某一列统计「可写背景」的方向数"""
    cur.execute(f"select {col}, year, year_confidence from action_literature where status='0'")
    tot, rec = Counter(), Counter()
    for cond, yr, cf in cur.fetchall():
        try:
            xs = json.loads(cond or '[]')
        except Exception:  # noqa: BLE001
            xs = []
        for x in {str(i).strip() for i in xs if str(i).strip()}:
            tot[x] += 1
            if yr and cf == 'high' and yr >= 2021:
                rec[x] += 1
    ok = [k for k, v in tot.items() if v >= min_total and rec.get(k, 0) >= min_recent]
    return label, len(tot), len(ok), sorted(ok, key=lambda k: -tot[k]), tot, rec


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rebuild', action='store_true')
    args = ap.parse_args()

    conn = psycopg2.connect(**DB)
    cur = conn.cursor()

    # 归并前的基线
    before = coverage(cur, 'condition', '归并前（原始标签）')

    cur.execute("select corpus_no, condition from action_literature where status='0'")
    hits: Counter = Counter()
    for _, cond in cur.fetchall():
        try:
            xs = json.loads(cond or '[]')
        except Exception:  # noqa: BLE001
            xs = []
        for x in xs:
            s = str(x).strip()
            if s:
                hits[s] += 1

    cur.execute('select raw_name, source from action_condition_dict')
    have = {r[0]: r[1] for r in cur.fetchall()}
    manual = {k for k, v in have.items() if v == 'manual'}
    todo = [(k, v) for k, v in hits.most_common()
            if k not in manual and (args.rebuild or k not in have)]
    print(f'原始标签 {len(hits)} 个 · 词表已有 {len(have)} 条（人工修正 {len(manual)}）· 本次归并 {len(todo)} 个\n')

    if todo:
        model, key, url, ark = pick_model()
        sem = asyncio.Semaphore(CONCURRENCY)
        chunks = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
        t0 = time.time()
        async with httpx.AsyncClient(timeout=300) as client:
            res = await asyncio.gather(*[ask(client, model, key, url, ark, ck, sem) for ck in chunks])
        rows, seen = [], set()
        for arr in res:
            for d in arr or []:
                raw = str(d.get('raw') or '').strip()
                if not raw or raw in seen or raw in manual:
                    continue
                seen.add(raw)
                sysname = str(d.get('system') or '其他').strip()
                rows.append((raw[:200], (str(d.get('norm') or raw).strip() or raw)[:200],
                             (str(d.get('group') or d.get('norm') or raw).strip() or raw)[:200],
                             sysname if sysname in SYSTEMS else '其他', hits.get(raw, 0), 'llm'))
        execute_batch(cur, """insert into action_condition_dict
                              (raw_name,norm_name,group_name,system_name,hits,source,create_time)
                              values (%s,%s,%s,%s,%s,%s,now())
                              on conflict (raw_name) do update set
                                norm_name=excluded.norm_name, group_name=excluded.group_name,
                                system_name=excluded.system_name, hits=excluded.hits
                              where action_condition_dict.source <> 'manual'""", rows, page_size=100)
        conn.commit()
        miss = [k for k, _ in todo if k not in seen]
        print(f'归并 {len(rows)} 条，耗时 {(time.time() - t0) / 60:.1f} 分钟'
              + (f'；未返回 {len(miss)} 个（原样入表）：{miss[:12]}' if miss else ''))
        if miss:
            execute_batch(cur, """insert into action_condition_dict
                                  (raw_name,norm_name,group_name,system_name,hits,source,create_time)
                                  values (%s,%s,%s,'其他',%s,'llm',now())
                                  on conflict (raw_name) do nothing""",
                          [(k[:200], k[:200], k[:200], hits.get(k, 0)) for k in miss])
            conn.commit()

    # 回填
    cur.execute('select raw_name, norm_name, group_name from action_condition_dict')
    dic = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
    cur.execute('select lit_id, condition from action_literature')
    ups = []
    for lid, cond in cur.fetchall():
        try:
            xs = [str(x).strip() for x in json.loads(cond or '[]') if str(x).strip()]
        except Exception:  # noqa: BLE001
            xs = []
        nm = list(dict.fromkeys(dic.get(x, (x, x))[0] for x in xs))
        gp = list(dict.fromkeys(dic.get(x, (x, x))[1] for x in xs))
        ups.append((json.dumps(nm, ensure_ascii=False), json.dumps(gp, ensure_ascii=False), lid))
    execute_batch(cur, 'update action_literature set condition_norm=%s, condition_group=%s where lit_id=%s',
                  ups, page_size=200)
    conn.commit()
    print(f'回填 {len(ups)} 篇的 condition_norm / condition_group\n')

    # 前后对比
    after_n = coverage(cur, 'condition_norm', '归并后（规范名 norm）')
    after_g = coverage(cur, 'condition_group', '归并后（上位类目 group）')
    print('=' * 84)
    print('归并效果：达到「可写背景」门槛（总数≥8 且近5年≥3）的研究方向数')
    print('=' * 84)
    for lbl, ntag, nok, ok, tot, rec in (before, after_n, after_g):
        print(f'\n{lbl}：标签 {ntag} 个 → 达标 {nok} 个')
        for k in ok[:20]:
            print(f'     {k:<26}总{tot[k]:>3} 篇 · 近5年 {rec.get(k, 0):>2} 篇')

    print('\n' + '=' * 84)
    print('归并示例（一个 group 底下有多个原始写法的）')
    print('=' * 84)
    cur.execute("""select group_name, count(*) c, sum(hits) h,
                          string_agg(raw_name || '(' || hits || ')', ' · ' order by hits desc)
                   from action_condition_dict where hits > 0
                   group by group_name having count(*) > 1 order by sum(hits) desc limit 14""")
    for g, c, h, names in cur.fetchall():
        print(f'  {g}  ← {c} 种写法 / {h} 篇')
        print(f'     {names[:150]}')

    cur.execute("""select system_name, count(*), sum(hits) from action_condition_dict
                   where hits>0 group by 1 order by 3 desc""")
    print('\n系统分布（语料构成披露用）：')
    for s, c, h in cur.fetchall():
        print(f'  {s:<16}{h:>4} 篇次 / {c} 个病种')
    cur.close()
    conn.close()


if __name__ == '__main__':
    asyncio.run(main())
