"""
把 `action_literature.title` 回填成**原文题名**（原语言照录）。

跑法（工作目录 action-backend/）::

    python -m tools.lit_fix_titles --dry     # 只报告不写库
    python -m tools.lit_fix_titles           # 写库
    python -m tools.lit_fix_titles --no 553  # 只处理指定编号

先跑 `sql/034-action-literature-title-orig-pg.sql`（建 `title_en` 并把目录译名搬过去）。
本脚本**可反复运行**：已经是原语言的行不动。

## 为什么要这一步

`目录.xlsx` 是**全英文**的译名索引（569 行零汉字）。它作为抽取时的防夹带锚是称职的，
但直接当题名存进 `title`，296 篇中文文献的引文就变成「中文作者 + 英文题名 + 中文刊名」，
既检索不到也引不了 —— 与 `action_srd_item.cite_*`「原文引用装的是原语言」同一条原则。

## 原题从哪来：文件名优先，正文兜底

PDF 文件名本身就是 `编号.中文题名_第一作者.pdf`，零成本、零幻觉。但有两个坑，
都会产出**看着完全正常的错题名**：

1. **文件名可能被截断过**：`258.电针与盆底肌训练治疗女性压...性尿失禁多中心随机对照试验_苏同生.pdf`
   —— 中间那个省略号是文件名里的字面量，不是显示省略。照抄进库就是一条中间缺字的引文，
   而它在页面上和正确的引文长得一模一样。实测这样的有几十篇（像是某次批量改名截的），
   带 `...`/`…` 的一律不信，转正文兜底。
2. **`lang` 列可能判错**（实测 5 篇中文论文被判成 en）。所以**不按 `lang` 决定取哪份题名**，
   而是按「文件名/正文里实际有没有汉字」判，并把 `lang` 一并修正 —— 按错的 lang
   去挑题名，等于用一个错误去挑另一个错误。

正文兜底走模型：中文期刊的题名在首页前几行，但夹在刊名、卷期、栏目名、作者与单位之间，
正则切不干净。给模型的是**正文前 600 字**，要求原样照抄、不许翻译不许改写 ——
题名是引用信息，改一个字就引错了；模型说拿不准就保留原值转人工，绝不猜。

## 改完要重算向量

`title` 进 `embed_text`，题名一换向量就过期。脚本把改动行的 `embed_hash` 置空，
由定时任务 `literature_task.refresh_stale_embeddings`（每 15 分钟）补算；
想立刻算完就跑 `python -m tools.lit_reembed`。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import unicodedata
from pathlib import Path

import httpx
import psycopg2
from psycopg2.extras import execute_batch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 这几样与 `tools/lit_ingest.py` 同源，但**刻意复制而不 import** —— import 它会把
# `module_action.*` 连同整条后端依赖链拖进来，而 `tools/common` 是常规包、
# `action-backend/common` 是命名空间包，常规包胜出，报错会是莫名其妙的
# `No module named 'common.vo'`（见 CLAUDE.md「三个踩过的坑」之三）
DB = dict(host='127.0.0.1', port=5432, user='postgres', password='123456', dbname='action')
_CTRL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


def _clean(s):
    """清掉 NUL 与 C0 控制字符；非字符串原样返回"""
    return _CTRL.sub('', s) if isinstance(s, str) else s


def nfkc(s: str) -> str:
    """全角→半角。中文文献的题名里常有全角括号与数字"""
    return _clean(unicodedata.normalize('NFKC', s or '')).strip()


HAN = re.compile(r'[一-鿿]')
#: 文件名里的字面省略号 —— 见模块 docstring 的坑 1
ELLIPSIS = re.compile(r'\.{3,}|…')
#: `123.` / `123 ` 这样的编号前缀
NO_PREFIX = re.compile(r'^\s*\d+\s*[.、_-]?\s*')
#: 结尾的 `_作者名`、`-作者名`、` - 副本`
TAIL = re.compile(r'(\s*-\s*副本|[_\-—]\s*[一-鿿A-Za-z][一-鿿A-Za-z·\s]{0,12})\s*$')

TITLE_PROMPT = """下面是一篇期刊论文 PDF 正文的开头部分。请找出这篇论文自己的**题名**。

要求：
1. **原样照抄，一个字都不许改**：不许翻译、不许改写、不许补标点、不许把副标题去掉。
   题名是引用信息，改一个字读者就检索不到原文了。
2. 中文论文抄中文题名，英文论文抄英文题名。同时印了两种时，抄**正文所用语言**那一份。
3. 别把这些当成题名：期刊名、卷期页码、栏目名（如「临床研究」「论著」）、
   基金项目、作者姓名与单位、DOI。
4. 正文里可能夹带了上一篇或下一篇论文的片段。已知这篇论文的英文题名是：
   《{anchor}》—— 以它为准判断哪个才是本文的题名。

只输出一个 JSON：{{"title": "题名原文", "confident": true 或 false}}
拿不准就把 confident 设成 false，不要猜。

正文开头：
{body}"""


def from_filename(fname: str) -> str:
    """
    文件名 → 题名。取不到可信的就返回空串。

    只认「剥掉编号前缀与作者后缀之后仍含汉字」的情况：英文文件名多半就是目录译名的
    另一份拷贝，没有比 `title_en` 更多的信息，不如走正文。
    与 `tools/lit_ingest.orig_title` 同一套规则，改一处要同步另一处。
    """
    stem = re.sub(r'\.pdf$', '', fname or '', flags=re.I)
    stem = NO_PREFIX.sub('', stem)
    stem = TAIL.sub('', stem).strip()
    if not stem or ELLIPSIS.search(stem) or not HAN.search(stem):
        return ''

    return nfkc(stem)[:1000]


async def from_body(client: httpx.AsyncClient, conf: dict, body: str, anchor: str) -> str:
    """
    正文兜底。模型拿不准就返回空串 —— 宁可留着旧值转人工，也不写一个猜的题名。

    **传输层错误要重试，不能和「模型判不准」混为一谈**：前者隔几秒重发多半就过了，
    后者重发多少次都一样。不分开的结果是一次 RemoteProtocolError 把这一篇记成
    「未能确定题名」，而它其实从没被判过。这个 provider 的瞬时断连在本项目已第四次出现。
    """
    prompt = TITLE_PROMPT.format(anchor=anchor[:200], body=body[:600])
    raw = ''
    for attempt in range(3):
        try:
            r = await client.post(
                conf['url'],
                headers={'Authorization': f'Bearer {conf["key"]}', 'Content-Type': 'application/json'},
                json={'model': conf['model'], 'temperature': 0, 'stream': False,
                      'messages': [{'role': 'user', 'content': prompt}]},
            )
            r.raise_for_status()
            raw = (r.json()['choices'][0]['message']['content'] or '').strip()
            break
        except httpx.TransportError as exc:
            if attempt == 2:
                print(f'    连续 3 次连接失败：{type(exc).__name__}'[:120], flush=True)

                return ''
            await asyncio.sleep(4 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001
            print(f'    模型调用失败：{type(exc).__name__}: {exc}'[:120], flush=True)

            return ''
    if not raw:
        return ''
    m = re.search(r'\{.*\}', raw, re.S)
    if not m:
        return ''
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return ''
    if not d.get('confident'):
        return ''

    return nfkc(str(d.get('title') or '').strip())[:1000]


async def model_conf() -> dict:
    """复用后台 `ai_models` 里的模型池，取第一个可用的"""
    from tools.common.model_registry import load_llm_models  # noqa: PLC0415

    pool = [m for m in await load_llm_models() if m.api_key and m.model_code]
    if not pool:
        return {}
    m = pool[0]
    url = (m.base_url or 'https://api.openai.com/v1').strip().rstrip('/')
    if not url.endswith('/chat/completions'):
        url += '/v3/chat/completions' if url.endswith('/api') else '/chat/completions'

    return {'url': url, 'key': m.api_key, 'model': m.model_code, 'label': m.label}


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true', help='只报告，不写库')
    ap.add_argument('--no', type=int, action='append', help='只处理指定编号，可重复')
    ap.add_argument('--env', default='dev')
    args = ap.parse_args()

    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    cur.execute("""select l.corpus_no, l.file_name, l.lang, l.title, l.title_en,
                          substring(coalesce(t.full_text, t.clean_text) from 1 for 900)
                     from action_literature l
                     left join action_literature_text t on t.corpus_no = l.corpus_no
                    where l.del_flag = '0'
                    order by l.corpus_no""")
    rows = cur.fetchall()
    if args.no:
        keep = set(args.no)
        rows = [r for r in rows if r[0] in keep]
    print(f'共 {len(rows)} 篇', flush=True)

    updates: list[tuple] = []
    need_model: list[tuple] = []
    #: 判不出题名的编号 —— 这些行仍挂着英文题名，必须进后台「待复核」而不是悄悄留着
    failed_nos: list[int] = []
    stats = {'filename': 0, 'already': 0, 'body': 0, 'failed': 0, 'lang_fixed': 0}

    for no, fname, lang, title, title_en, body in rows:
        anchor = title_en or title or ''
        # 正文有汉字 = 这是中文论文，与 lang 列怎么写无关（lang 实测有判错的）
        is_zh = bool(HAN.search((body or '')[:400])) or bool(HAN.search(fname or ''))
        if not is_zh:
            # 英文论文：原题就是英文题名，两列同值
            if anchor and title != anchor:
                updates.append((anchor, anchor, lang, no))
            stats['already'] += 1
            continue
        if HAN.search(title or ''):
            stats['already'] += 1
            continue
        if lang != 'zh':
            stats['lang_fixed'] += 1
        cand = from_filename(fname)
        if cand:
            updates.append((cand, anchor, 'zh', no))
            stats['filename'] += 1
        else:
            need_model.append((no, anchor, body or ''))

    if need_model:
        conf = await model_conf()
        if not conf:
            print('⚠ ai_models 里没有可用模型，正文兜底跳过', flush=True)
        else:
            print(f'{len(need_model)} 篇要走正文兜底（模型 {conf["label"]}）', flush=True)
            async with httpx.AsyncClient(timeout=120) as client:
                for no, anchor, body in need_model:
                    got = await from_body(client, conf, body, anchor)
                    if got and HAN.search(got):
                        updates.append((got, anchor, 'zh', no))
                        stats['body'] += 1
                        print(f'  #{no} ← {got[:60]}', flush=True)
                    else:
                        stats['failed'] += 1
                        failed_nos.append(no)
                        print(f'  #{no} 未能确定题名，保留原值（转人工）', flush=True)

    print(f'\n文件名取得 {stats["filename"]} · 正文兜底 {stats["body"]} · '
          f'已是原语言 {stats["already"]} · 失败 {stats["failed"]} · lang 修正 {stats["lang_fixed"]}',
          flush=True)
    if args.dry:
        print('--dry：未写库')
        conn.close()

        return 0
    if updates:
        # title 变了向量就过期 —— 置空 embed_hash 交给定时任务补算（见模块 docstring）
        execute_batch(cur, """update action_literature
                                 set title = %s, title_en = %s, lang = %s, embed_hash = null
                               where corpus_no = %s""",
                      [tuple(_clean(x) for x in u) for u in updates], page_size=100)
    if failed_nos:
        # 标成待复核：后台顶部那个橙色数字点一下就能筛出这一批，复核的主线就是逐类清掉。
        # 不标的话它们与「已经核过、确实是英文题名」的行混在一起，再也分不出来
        cur.execute("update action_literature set review_status = 'pending' where corpus_no = any(%s)",
                    (failed_nos,))
    conn.commit()
    print(f'已更新 {len(updates)} 行，{len(failed_nos)} 行标为待复核')
    conn.close()

    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
