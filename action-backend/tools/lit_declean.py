"""
夹带内容的定性与切除：对 `contamination='1'` 的文献跑第二趟

跑法（工作目录 action-backend/）::

    python -m tools.lit_declean            # 处理全部未处理的
    python -m tools.lit_declean --ids 175,118
    python -m tools.lit_declean --force    # 重跑已处理的

## 为什么要第二趟，第一趟不顺便做掉

第一趟的任务是抽 21 个元数据字段，提示词已经很长；再塞一个「顺便标出夹带段落的边界」
会稀释注意力，而边界判定要求模型逐字照抄原文片段（见下），和抽取是两种不同的活儿。
分开跑只多花 124 篇的钱，换来两边各自的提示词都干净。

## 关键设计：让模型报**锚文本**，不报字符下标

模型数不准字符数。让它输出 offset，得到的必然是错位的数字，而错位的表现是
「正文被砍掉一段」这种**静默损坏** —— 切完看着一切正常，只是少了几百字。

所以改成：让它照抄「本文正文真正开始处的前 40 字」与「真正结束处的后 40 字」，
由 Python 用 `find` / `rfind` 定位再切。定位不到就判 failed、保留原文、转人工，绝不猜。

## 三道安全闸

1. **锚点必须在原文里逐字出现**，找不到 → failed
2. **切完的长度不得低于原文 30%** —— 低于说明锚点定位到了错误的位置（比如锚文本
   在正文里重复出现），宁可不切
3. **只写 `clean_text`，不动 `full_text`** —— 切错了能回滚，人工复核时能看到切掉了什么
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time

import httpx
import psycopg2
from psycopg2.extras import execute_batch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB = dict(host='127.0.0.1', port=5432, user='postgres', password='123456', dbname='action')
CONCURRENCY = 10
#: 送模型的正文上限。夹带只出现在首尾，超长的取头尾各一半即可 ——
#: 锚点定位是在**完整原文**上做的，中间省略不影响
HEAD_TAIL = 20000
#: 切完不得低于原文这个比例，低于说明锚点定位错了
MIN_RATIO = 0.30
_CTRL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')

PROMPT = """这篇论文的权威标题是：
《{title}》

下面是从期刊 PDF 抽出的全文。由于纸质期刊排版连续、而 PDF 按页范围裁切，
文件里**可能混入了上一篇或下一篇论文**的内容（首页上半属于上一篇、末页下半属于下一篇）。

请判断混入情况，只输出一个 JSON 对象，不要解释、不要 markdown 围栏：

{{
  "kind": "clean" | "head" | "tail" | "both" | "ref_only" | "unknown",
  "body_start": "本文正文真正开始处的前 40 个字符，从全文中逐字照抄",
  "body_end": "本文正文真正结束处的最后 40 个字符，从全文中逐字照抄",
  "intruders": ["混入的其他论文的标题", ...],
  "note": "一句话说明"
}}

kind 的判据：
- clean     全文都属于本文，没有混入
- head      文件开头混入了上一篇论文的尾部（正文/参考文献/版权信息）
- tail      文件末尾混入了下一篇论文的开头（标题/作者/摘要/正文）
- both      首尾都有
- ref_only  混入的内容**只出现在本文参考文献区之内或之后**，本文的标题/摘要/方法/结果完整无损
- unknown   看不出来

三条硬要求：
1. **body_start 与 body_end 必须是上面全文里逐字出现过的连续片段**，
   不许改写、不许加省略号、不许合并空白。我要用它们做字符串定位。
2. body_start 取本文**标题那一行的开头**（若标题被夹带内容顶到了后面）；
   若文件开头就是本文，取全文最开始的 40 字。
   body_end 取本文最后一段（通常是参考文献末条或结论）的结尾 40 字。
3. kind 为 clean 或 ref_only 时，body_start 与 body_end 一律填 null
   —— 这两种情况不需要切除。

全文：
---
{body}
---"""


def pick_model() -> tuple[str, str, str, bool]:
    code, key = os.environ.get('LLM_MODEL'), os.environ.get('LLM_KEY')
    base = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    if not (code and key):
        raise SystemExit('请设置 LLM_MODEL / LLM_KEY / LLM_BASE_URL')
    url = base.strip().rstrip('/')
    if not url.endswith('/chat/completions'):
        url = url + ('/v3/chat/completions' if url.endswith('/api') else '/chat/completions')
    return code, key, url, 'volces.com' in base


def shrink(text: str) -> str:
    """超长正文取头尾各一半送模型；锚点定位仍在完整原文上做"""
    if len(text) <= HEAD_TAIL * 2:
        return text
    cut = len(text) - HEAD_TAIL * 2
    return f'{text[:HEAD_TAIL]}\n\n…[此处省略中段 {cut} 字符，夹带只可能出现在首尾]…\n\n{text[-HEAD_TAIL:]}'


async def ask(client, model, key, url, ark, title, body, sem):
    payload = {'model': model, 'temperature': 0, 'stream': False,
               'messages': [{'role': 'user', 'content': PROMPT.format(title=title, body=shrink(body))}]}
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
                s, e = txt.find('{'), txt.rfind('}')
                if s < 0 or e <= s:
                    raise ValueError('未返回 JSON')
                return json.loads(txt[s:e + 1])
            except Exception as exc:  # noqa: BLE001
                if attempt == 3:
                    return {'__error__': f'{type(exc).__name__}: {exc}'[:200]}
                await asyncio.sleep(3 * attempt)


def _loose_find(hay: str, needle: str, from_end: bool = False) -> tuple[int, int]:
    """
    先精确找，找不到再放宽空白后找。

    模型照抄时极易把 PDF 里的换行/多空格压成一个空格，精确匹配会全线失败，
    而这类失败在结果上看不出来（只是「切除失败率高」），所以要留这条退路。

    :return: (起点, 终点)，找不到返回 (-1, -1)。**终点必须是真实匹配终点**——
        早先这里只返回起点、由调用方按 `len(needle)+40` 估终点，结果那 40 字余量
        把夹带论文的**标题**又留了回来（实测 #118 尾部留下「竖横针刺法治疗风寒型
        面瘫临床疗效观察 刘美荣,李梦丝」）。标题是全篇关键词密度最高的一段，
        留 40 字标题比不切还糟 —— 检索照样命中。
    """
    idx = hay.rfind(needle) if from_end else hay.find(needle)
    if idx >= 0:
        return idx, idx + len(needle)
    core = re.sub(r'\s+', '', needle)[:24]
    if len(core) < 8:
        return -1, -1
    pat = re.compile(r'\s*'.join(re.escape(ch) for ch in core))
    ms = list(pat.finditer(hay))
    if not ms:
        return -1, -1
    m = ms[-1] if from_end else ms[0]
    return m.start(), m.end()


def slice_body(full: str, d: dict) -> tuple[str, str, int]:
    """
    按锚点切出本文正文。

    :return: (clean_status, clean_text, ratio 百分比)
    """
    kind = str(d.get('kind') or 'unknown')
    if kind in ('clean', 'ref_only'):
        return 'na', '', 100
    if kind == 'unknown':
        return 'manual', '', 100
    bs, be = d.get('body_start'), d.get('body_end')
    if not bs or not be:
        return 'manual', '', 100
    i, _ = _loose_find(full, str(bs))
    _, j = _loose_find(full, str(be), from_end=True)
    if i < 0 or j < 0:
        return 'failed', '', 100
    # 不加余量：多留的那点恰好是夹带论文的标题，而标题是最容易被检索命中的一段
    j = min(j, len(full))
    if j <= i:
        return 'failed', '', 100
    out = full[i:j]
    ratio = int(len(out) / max(len(full), 1) * 100)
    if ratio < MIN_RATIO * 100:
        return 'failed', '', ratio
    return 'ok', _CTRL.sub('', out), ratio


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ids', default='')
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()

    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    where = "l.contamination='1'"
    if not args.force:
        where += " and coalesce(l.clean_status,'na') in ('na','')  and coalesce(l.contam_kind,'')=''"
    if args.ids:
        where += ' and l.corpus_no in (%s)' % ','.join(str(int(x)) for x in args.ids.split(',') if x.strip())
    cur.execute(f"""select l.lit_id, l.corpus_no, l.title, t.full_text
                    from action_literature l join action_literature_text t on t.lit_id = l.lit_id
                    where {where} order by l.corpus_no""")
    rows = cur.fetchall()
    model, key, url, ark = pick_model()
    print(f'待处理 {len(rows)} 篇（contamination=1）· 模型 {model} · 并发 {CONCURRENCY}\n')
    if not rows:
        cur.close()
        conn.close()
        return

    sem = asyncio.Semaphore(CONCURRENCY)
    t0 = time.time()
    stat: dict[str, int] = {}
    CHUNK = 24
    async with httpx.AsyncClient(timeout=300) as client:
        for start in range(0, len(rows), CHUNK):
            part = rows[start:start + CHUNK]
            res = await asyncio.gather(*[ask(client, model, key, url, ark, ti, ft, sem)
                                         for _, _, ti, ft in part])
            up_main, up_text = [], []
            for (lid, no, title, full), d in zip(part, res):
                if '__error__' in d:
                    stat['failed'] = stat.get('failed', 0) + 1
                    up_main.append(('unknown', 'failed', None, '[]', lid))
                    print(f'  ✗ #{no} {d["__error__"][:80]}')
                    continue
                kind = str(d.get('kind') or 'unknown')
                st, clean, ratio = slice_body(full, d)
                stat[f'{kind}/{st}'] = stat.get(f'{kind}/{st}', 0) + 1
                up_main.append((kind, st, ratio,
                                _CTRL.sub('', json.dumps(d.get('intruders') or [], ensure_ascii=False)), lid))
                if st == 'ok':
                    up_text.append((clean, lid))
                    print(f'  ✂ #{no:<4} {kind:<9} 保留 {ratio}%  切掉 {len(full) - len(clean):>6} 字符'
                          f'  混入：{"/".join(str(x)[:26] for x in (d.get("intruders") or []))[:56]}')
                elif st in ('failed', 'manual'):
                    print(f'  ⚠ #{no:<4} {kind:<9} {st} —— 保留原文转人工（{d.get("note", "")[:44]}）')
            execute_batch(cur, 'update action_literature set contam_kind=%s, clean_status=%s, '
                               'clean_ratio=%s, intruders=%s, update_time=now() where lit_id=%s', up_main)
            if up_text:
                execute_batch(cur, 'update action_literature_text set clean_text=%s where lit_id=%s', up_text)
            conn.commit()
            print(f'  [{start + len(part)}/{len(rows)}] 已落库 · 用时 {(time.time() - t0) / 60:.1f}min', flush=True)

    print(f'\n完成，耗时 {(time.time() - t0) / 60:.1f} 分钟')
    print('分类 × 处理结果：')
    for k, v in sorted(stat.items(), key=lambda x: -x[1]):
        print(f'   {k:<24}{v:>4}')

    cur.execute("""select contam_kind, clean_status, count(*) from action_literature
                   where contamination='1' group by 1,2 order by 3 desc""")
    print('\n库内汇总：')
    for k, s, n in cur.fetchall():
        print(f'   {k or "(空)":<12}{s or "(空)":<10}{n:>4} 篇')
    cur.execute("""select count(*) from action_literature
                   where clean_status in ('failed','manual')""")
    print(f'\n需人工核对：{cur.fetchone()[0]} 篇（`select corpus_no,title,intruders from action_literature '
          f"where clean_status in ('failed','manual')`）")
    cur.close()
    conn.close()


if __name__ == '__main__':
    asyncio.run(main())
