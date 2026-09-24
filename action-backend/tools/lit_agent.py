"""
研究背景智能生成 Agent：全库端到端

跑法（工作目录 action-backend/）::

    set LLM_BASE_URL=... & set LLM_MODEL=... & set LLM_KEY=...
    python -m tools.lit_agent --topic "针刺治疗慢性失眠的疗效与安全性"
    python -m tools.lit_agent --topic "..." --group 失眠      # 指定病种类目

## 九步

1. 研究问题解析（PICO）           LLM 1 次
2. 逐槽位检索                     BM25，无 LLM
3. 覆盖度闸（分数 + 研究设计）     无 LLM  ← 不合格的槽位如实报告，不生成
4. 核心文献排序                   0.65 相关 + 0.35 近期
5. Evidence Table + 不一致检测    代码判定，不靠模型自觉
6. 逐槽位写作                     LLM 每槽 1 次，**只准引 [n]**
7. 编号越界硬拦                   正则，代码
8. 引证核验（每句 × 每条引文）     LLM 每槽 1 次
9. 参考文献表由代码拼装            模型不参与

## 检索用 clean_text 不用 full_text

实测 566 篇里 124 篇的 PDF 夹带了另一篇论文的正文/参考文献（纸质期刊跨页续排所致），
其中 54 篇已由 `tools/lit_declean.py` 切除。夹带内容进检索池的表现是「这篇功能性便秘
研究在检索面瘫时命中」，而生成时更隐蔽 —— 模型引用夹带段落里的数据、标上本文的编号，
引文是真的、数据是真的，两者对不上号。

## 覆盖度按 condition_group 算，不按原始标签

原始标签 485 个、80% 只出现一次，失眠散在 15 种写法里。按原始标签算覆盖度，
几乎所有方向都会被判「本库撑不住」，而库里其实有料。见 `tools/lit_conditions.py`。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict

import httpx
import numpy as np
import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# tools 目录放在 sys.path 末尾。注意：**这解决不了 `common` 的遮蔽**——
# `action-backend/common` 无 __init__.py（PEP 420 命名空间包），`tools/common` 有
# （worker 框架的常规包），而**常规包胜过命名空间包、与路径顺序无关**。
# 所以后端服务不能在 tools 在路径上时做延迟 import，见
# module_action/service/literature_embed_service._arr 上的注释。
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from lit_vector import (  # noqa: E402
    SearchResult, VectorStore, cfg as vcfg, embed_many, rerank_docs, rerank_text,
)

DB = dict(host='127.0.0.1', port=5432, user='postgres', password='123456', dbname='action')
CURRENT_YEAR = 2026
#: 覆盖度阈值。**向量余弦与 BM25 压缩分是两个量纲，阈值必须分开** ——
#: 共用一套的表现是「换了检索路径之后，同一个方向忽然从『可写』变成『覆盖不足』」，
#: 而这类偏差看不出来是阈值的问题。qwen 向量在本语料上相关文献余弦普遍 0.45+、
#: 不相关的 0.25 以下；BM25 压缩分则贴着 0.6-0.9（见 tools/lit_embed.py 的实测）。
TAU = {'vector': (0.30, 0.42), 'bm25': (0.08, 0.16)}
MIN_HITS = 2
#: 槽位对证据类型的要求。**这是 BM25 分数之外的第二道闸** ——
#: 只按词面相似度判覆盖度，会把「引言里引用了患病率的 RCT」当成流行病学证据，
#: 而拿干预性 RCT 作为流行病学数据的出处是引用错误。
SLOT_DESIGN_REQ = {
    'S1': ({'sr_meta', 'guideline', 'epidemiology'}, '流行病学调查 / 系统综述 / 指南'),
    'S2': ({'rct', 'nrct', 'sr_meta'}, '对照试验 / 系统综述'),
    'S3': ({'rct', 'nrct', 'sr_meta'}, '对照试验 / 系统综述'),
    'S4': ({'rct', 'sr_meta'}, '对照试验 / 系统综述'),
}
SLOT_NAME = {'S1': '疾病负担与临床重要性', 'S2': '现有疗法及其局限',
             'S3': '针刺/电针的既往证据', 'S4': '现有证据的不足（研究缺口）', 'S5': '本研究目的'}
#: 假针刺对照的识别。**必须按语义、且要穷举写法** —— 实测漏过「非效穴浅刺」
#: （我原先只有 `非穴`，而「非效穴」是 非-效-穴，匹配不上），
#: 结果 #475 这篇假针刺对照被分进了「vs 阳性药」组，而 Evidence Table 照样吐出
#: 一个看着正常的判定。假针刺在中文文献里至少有这些写法：
_SHAM = re.compile(r'假针|假电针|假[^,，;；]{0,4}针刺|安慰针|安慰剂针|非经非穴|非效穴|非穴|'
                   r'浅刺非|非治疗穴|旁开非|sham|placebo', re.I)
#: 引用编号。**必须认区间与逗号连写** —— 模型会写 `[1-8,11]` `[2,3,11]`，
#: 只认 `\[(\d+)\]` 的话这些一条都数不到，表现是「S4 引用 1 条」这种明显偏低的统计，
#: 而越界检查会**完全失效**（模型写 `[1-99]` 也报 0 处越界）。踩过一次。
_CITE_BLOCK = re.compile(r'\[([\d\s,，\-–~至]+)\]')


def cited_nums(text: str) -> list[int]:
    """从正文里取出全部被引编号，认 [3] / [1,2] / [1-8] / [1-8,11] 各种写法"""
    out: list[int] = []
    for blk in _CITE_BLOCK.findall(text or ''):
        for part in re.split(r'[,，]', blk):
            part = part.strip()
            m = re.fullmatch(r'(\d+)\s*[\-–~至]\s*(\d+)', part)
            if m:
                a, b = int(m.group(1)), int(m.group(2))
                if 0 < a <= b <= a + 60:
                    out += list(range(a, b + 1))
            elif part.isdigit():
                out.append(int(part))
    return out


# ── 模型 ────────────────────────────────────────────────────
def pick_model():
    code, key = os.environ.get('LLM_MODEL'), os.environ.get('LLM_KEY')
    base = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    if not (code and key):
        raise SystemExit('请设置 LLM_MODEL / LLM_KEY / LLM_BASE_URL')
    url = base.strip().rstrip('/')
    if not url.endswith('/chat/completions'):
        url = url + ('/v3/chat/completions' if url.endswith('/api') else '/chat/completions')
    return code, key, url, 'volces.com' in base


async def call(client, cfg, prompt, sem=None, want_json=True):
    model, key, url, ark = cfg
    payload = {'model': model, 'temperature': 0.2 if not want_json else 0, 'stream': False,
               'messages': [{'role': 'user', 'content': prompt}]}
    if ark:
        payload['thinking'] = {'type': 'disabled'}

    async def _go():
        for attempt in (1, 2, 3):
            try:
                r = await client.post(url, json=payload,
                                      headers={'Authorization': f'Bearer {key}',
                                               'Content-Type': 'application/json'})
                r.raise_for_status()
                raw = (r.json()['choices'][0]['message']['content'] or '').strip()
                if not want_json:
                    return raw
                fence = re.search(r'```(?:json)?\s*(.+?)\s*```', raw, re.S)
                txt = fence.group(1) if fence else raw
                a, b = min([i for i in (txt.find('{'), txt.find('[')) if i >= 0] or [-1]), max(txt.rfind('}'), txt.rfind(']'))
                if a < 0 or b <= a:
                    raise ValueError('未返回 JSON')
                return json.loads(txt[a:b + 1])
            except Exception as exc:  # noqa: BLE001
                if attempt == 3:
                    return {'__error__': f'{type(exc).__name__}: {exc}'[:200]} if want_json else ''
                await asyncio.sleep(3 * attempt)

    if sem is None:
        return await _go()
    async with sem:
        return await _go()


# ── 语料 ────────────────────────────────────────────────────
def jl(s):
    try:
        return json.loads(s) if s else []
    except (json.JSONDecodeError, TypeError):
        return []


def load_corpus(cur) -> list[dict]:
    cur.execute("""select l.corpus_no, l.title, l.year, l.year_confidence, l.authors, l.journal,
                          l.lang, l.abstract, l.population, l.condition, l.condition_group,
                          l.intervention, l.comparator, l.outcomes, l.study_design, l.sample_size,
                          l.effect_direction, l.finding_summary, l.acu_points, l.acu_method,
                          l.acu_frequency, l.acu_retention_min, l.acu_sessions, l.acu_course_weeks,
                          l.contamination, l.truncated, l.clean_status,
                          l.embedding, l.embed_dim, l.embed_model
                   from action_literature l
                   where l.status='0' and l.del_flag='0' and l.extract_status='ok'""")
    cols = ('no title year yconf authors journal lang abstract population condition cgroup '
            'intervention comparator outcomes design n direction finding points method freq '
            'retention sessions weeks contam trunc cstatus embedding embed_dim embed_model').split()
    out = []
    for r in cur.fetchall():
        d = dict(zip(cols, r))
        for k in ('authors', 'condition', 'cgroup', 'intervention', 'comparator', 'outcomes', 'points'):
            d[k] = jl(d[k])
        out.append(d)
    return out


def doc_text(p: dict) -> str:
    return ' '.join([p['title'] or '', p['abstract'] or '', p['population'] or '',
                     ' '.join(p['condition']), ' '.join(p['cgroup']), ' '.join(p['intervention']),
                     ' '.join(p['comparator']), ' '.join(p['outcomes']), p['finding'] or '',
                     ' '.join(p['points']), p['method'] or ''])


def tok(text: str) -> list[str]:
    """中文字符二元组 + 英文词元。环境无 jieba，二元组是无分词器时的标准做法"""
    if not text:
        return []
    t = text.lower()
    out = re.findall(r'[a-z][a-z\-]{2,}|\d{2,}', t)
    for run in re.findall(r'[一-鿿]+', t):
        out += [run[i:i + 2] for i in range(len(run) - 1)] or [run]
    return out


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.k1, self.b, self.docs = k1, b, docs
        self.N = len(docs)
        self.avgdl = sum(len(d) for d in docs) / max(self.N, 1)
        self.tf = [Counter(d) for d in docs]
        df: Counter = Counter()
        for d in docs:
            df.update(set(d))
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}

    def score(self, q):
        out = []
        for i, tf in enumerate(self.tf):
            dl, s = len(self.docs[i]), 0.0
            for t in q:
                f = tf.get(t, 0)
                if f:
                    s += self.idf.get(t, 0) * f * (self.k1 + 1) / (
                        f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            out.append(s)
        return out


def rel(raw_score: float) -> float:
    """BM25 原始分压到 0-1，供覆盖度判定"""
    return 1 - math.exp(-raw_score / 12)


def recency(p) -> float:
    if not p['year'] or p['yconf'] != 'high':
        return 0.0
    return math.exp(-(CURRENT_YEAR - p['year']) / 4)


def cite_of(p) -> str:
    a = p['authors']
    first = a[0] if a else '—'
    etal = ', 等' if len(a) > 1 else ''
    return f'{first}{etal}. {p["title"]}. {p["journal"] or "期刊待核"}. {p["year"] or "年份待核"}.'


PICO_PROMPT = """把下面这个针刺临床研究方向解析成结构化研究问题，只输出 JSON，不要解释：

{{"population":"研究对象","condition":["病种，2-4个同义或相关写法"],
  "intervention":["干预，2-4个"],"comparator":["常见对照，3-5个"],
  "outcomes":["结局指标，3-6个"],
  "queries":{{"S1":"疾病负担/流行病学 检索词","S2":"现有疗法及其局限 检索词",
             "S3":"针刺疗效证据 检索词","S4":"研究缺口/方法学局限 检索词"}}}}

检索词用中文、空格分隔关键词，每条 8-16 个字。

研究方向：{topic}"""

WRITE_PROMPT = """你在为一篇针刺临床研究论文撰写「研究背景」的某一段。

本段主题：{slot_name}
研究方向：{topic}

可用证据（**你只能引用这里列出的编号**）：
{refs}

{extra}

写作要求：
1. **只能写 [n] 形式的引用，n 必须是上面列出的编号。绝不允许写出任何文献的标题、
   作者、期刊、DOI —— 参考文献表由系统按编号自动拼装，你写了也会被丢弃。**
2. **绝不编造数据。** 样本量、P 值、置信区间、效应量只能照抄上面证据里给出的，
   上面没有的一律不写，不许估算、不许举例。
3. **不许把证据里没有的方法学事实写进去**（穴位、频率、疗程、随访时长等）。
4. 中文学术书面语，250-400 字，一段或两段，不要小标题、不要 markdown、不要开场白。
5. 每个实质性论断后面都要跟引用编号。

只输出正文。"""

VERIFY_PROMPT = """核验下面这段研究背景里，每一处引用是否真的被所引文献支持。

证据清单：
{refs}

待核验正文：
{text}

把正文按句号切成句子，对每个「带引用的句子」输出一条判定，只输出 JSON 数组：
[{{"sent":"句子前30字","cite":编号,"verdict":"supports|partial|not_supported","why":"12字以内"}}]

判据：
- supports      该文献确实支持这句话的全部内容
- partial       方向一致但细节对不上（如数字不符、人群不同）
- not_supported 该文献不支持这句话，或这句话的内容根本不在该文献里

没有任何引用的句子不用输出。只输出 JSON 数组。"""


async def retrieve(client, query: str, store: VectorStore, bm: BM25, order: list[int],
                   top_k: int, conf: dict) -> SearchResult:
    """
    一次检索：向量召回 → 重排 → 取前 top_k。向量不可用时退 BM25 并**标注降级**。

    20 题评测集实测（`tools/lit_embed.py`）：BM25 P@5=0.730 / 向量 0.940 /
    向量+重排 P@10=0.912。混合 RRF **被实测否掉**（等权融合反而掉到 0.850，
    BM25 太弱、把向量的正确结果挤出前 5），所以 BM25 只做降级，不进主路径。
    """
    if store.ready and conf.get('embed_url') and conf.get('embed_key'):
        vecs = await embed_many(client, [query], conf)
        if vecs:
            n = max(conf.get('rerank_n', 30), top_k)
            cand = store.search(np.asarray(vecs[0], dtype=np.float32), n)
            papers = [store.by_no[no] for no, _ in cand]
            idx = await rerank_docs(client, query, [rerank_text(p) for p in papers], top_k, conf)
            if idx is not None:
                # 重排只覆盖前 top_k，其余按向量序接在后面（覆盖度闸要看更长的候选）
                head = [papers[i] for i in idx if 0 <= i < len(papers)]
                rest = [p for p in papers if p not in head]
                return SearchResult(hits=head + rest, mode='vector+rerank')
            return SearchResult(hits=papers, mode='vector')

    raw = bm.score(tok(query))
    rank = [order[i] for i in np.argsort(-np.asarray(raw)) if raw[i] > 0]
    return SearchResult(hits=[store.by_no[n] for n in rank[:max(top_k, 30)]], mode='bm25',
                        note='向量检索不可用，已降级为 BM25（实测 P@5 由 0.94 降至 0.73）')


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--topic', required=True)
    ap.add_argument('--group', default='', help='病种类目（condition_group），留空则由 PICO 推断')
    ap.add_argument('--refs', type=int, default=12, help='交给写作模型的最大文献数')
    args = ap.parse_args()

    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    papers = load_corpus(cur)
    cfg = pick_model()

    print('=' * 88)
    print(f'研究方向：{args.topic}')
    print(f'知识库：{len(papers)} 篇')
    print('=' * 88)

    async with httpx.AsyncClient(timeout=300) as client:
        # ① PICO
        t0 = time.time()
        pico = await call(client, cfg, PICO_PROMPT.format(topic=args.topic))
        if '__error__' in pico:
            raise SystemExit(f'PICO 解析失败：{pico["__error__"]}')
        print('\n【1】研究问题解析（PICO）')
        for k in ('population', 'condition', 'intervention', 'comparator', 'outcomes'):
            v = pico.get(k)
            print(f'   {k:<13}{v if isinstance(v, str) else " / ".join(map(str, v or []))}')

        # 语料池：先按 condition_group 过滤（软过滤，同时保留全库一路）
        group = args.group
        if not group:
            gcount = Counter(g for p in papers for g in p['cgroup'])
            cand = {str(x) for x in (pico.get('condition') or [])}
            best = [(g, n) for g, n in gcount.items() if any(c in g or g in c for c in cand)]
            group = max(best, key=lambda x: x[1])[0] if best else ''
        pool = [p for p in papers if group and group in p['cgroup']]
        usable = [p for p in papers if p['design'] != 'protocol']
        print(f'\n   病种类目：{group or "(未识别)"} → 该类目 {len(pool)} 篇'
              f'　|　全库可用 {len(usable)} 篇（已排除 protocol {len(papers) - len(usable)} 篇）')

        # ② 检索：向量为主，BM25 降级备用
        bm = BM25([tok(doc_text(p)) for p in usable])
        order = [p['no'] for p in usable]
        store = VectorStore(usable)
        conf = vcfg()
        have, tot = store.coverage
        print(f'\n【2-3】逐槽位检索 + 覆盖度闸　向量 {have}/{tot} 篇'
              + (f' · {"/".join(m for m in store.models if m)}' if store.models else '')
              + (' · 重排 ' + conf['rerank_model'] if conf.get('rerank_host') else ' · 无重排'))
        slot_hits: dict[str, list] = {}
        modes: dict[str, str] = {}
        blocked = []
        for code in ('S1', 'S2', 'S3', 'S4'):
            q = (pico.get('queries') or {}).get(code) or ''
            res = await retrieve(client, q, store, bm, order, 12, conf)
            modes[code] = res.mode
            # 相关度：向量路用余弦，BM25 路用压缩后的分数。两者都在 0-1，闸的阈值通用
            if res.mode.startswith('vector'):
                qv = await embed_many(client, [q], conf)
                sims = dict(store.search(np.asarray(qv[0], dtype=np.float32), len(store.ids))) if qv else {}
                top = [(p, float(sims.get(p['no'], 0.0))) for p in res.hits[:12]]
            else:
                raw = dict(zip(order, bm.score(tok(q))))
                top = [(p, rel(raw.get(p['no'], 0.0))) for p in res.hits[:12]]
            top1 = top[0][1] if top else 0.0
            req, label = SLOT_DESIGN_REQ[code]
            tau_hard, tau_soft = TAU['vector' if res.mode.startswith('vector') else 'bm25']
            fit = [(p, r) for p, r in top if p['design'] in req and r >= tau_hard]
            if len(fit) < MIN_HITS:
                got = Counter(p['design'] for p, _ in top)
                blocked.append((code, f'本库缺少「{label}」类型的文献'
                                      f'（候选 {len(top)} 篇的设计分布：{dict(got)}）'))
                slot_hits[code] = []
                st = '✗ 不生成，如实报告覆盖不足'
            elif top1 < tau_soft:
                slot_hits[code] = fit[:8]
                st = '△ 生成但标低置信'
            else:
                slot_hits[code] = fit[:8]
                st = '✓ 生成'
            print(f'\n   [{code}] {SLOT_NAME[code]}　查询「{q}」')
            print(f'        最高相关度 {top1:.3f} · 符合证据类型 {len(fit)} 篇 → {st}')
            for p, r in (slot_hits[code] or top)[:4]:
                print(f'          {r:.3f}  #{p["no"]:<4} {str(p["year"] or "—"):<6}{p["design"]:<6}'
                      f'{p["direction"]:<14}{(p["title"] or "")[:44]}')

        # ④ 排序：类目池优先，池空则退回全库
        base = pool or usable
        topic_q = ' '.join(map(str, (pico.get('condition') or []) +
                               (pico.get('intervention') or []) + (pico.get('outcomes') or [])))
        smap: dict[int, float] = {}
        if store.ready and conf.get('embed_url'):
            qv = await embed_many(client, [topic_q], conf)
            if qv:
                smap = dict(store.search(np.asarray(qv[0], dtype=np.float32), len(store.ids)))
        if not smap:
            smap = {p['no']: rel(s) for p, s in zip(usable, bm.score(tok(topic_q)))}
        ranked = sorted(base, key=lambda p: -(0.65 * smap.get(p['no'], 0) + 0.35 * recency(p)))
        print(f'\n【4】核心文献排序（0.65×相关 + 0.35×近期，当前年 {CURRENT_YEAR}）')
        print(f'   {"总分":>6}{"相关":>7}{"近期":>7}  {"年份":<7}{"设计":<7}{"n":>5} {"方向":<15}标题')
        for p in ranked[:14]:
            r, rc = smap.get(p['no'], 0), recency(p)
            flag = ('⚠截断' if p['trunc'] == '1' else '') + ('⚠夹带' if p['contam'] == '1' and p['cstatus'] != 'ok' else '')
            print(f'   {0.65 * r + 0.35 * rc:6.3f}{r:7.3f}{rc:7.3f}  {str(p["year"] or "—"):<7}{p["design"]:<7}'
                  f'{str(p["n"] or "—"):>5} {p["direction"]:<15}#{p["no"]} {(p["title"] or "")[:40]}{flag}')

        # ⑤ Evidence Table
        print('\n【5】Evidence Table + 不一致检测（按病种类目内全部文献）')
        claims = defaultdict(list)
        for p in base:
            if p['direction'] == 'unclear':
                claims['C0 无法判定'].append((p, p['direction']))
            elif any(_SHAM.search(str(x)) for x in p['comparator']):
                claims['C1 针刺 vs 假针刺'].append((p, p['direction']))
            else:
                claims['C2 针刺 vs 阳性药/常规疗法'].append((p, p['direction']))
        incon = {}
        for key in ('C1 针刺 vs 假针刺', 'C2 针刺 vs 阳性药/常规疗法'):
            items = claims.get(key, [])
            dirs = Counter(d for _, d in items)
            real = [k for k in dirs if k in ('positive', 'negative', 'no_difference')]
            status = 'INCONSISTENT' if len(real) > 1 else 'CONSISTENT'
            incon[key] = status
            print(f'\n   {key}：{len(items)} 篇 | {dict(dirs)} | **{status}**')
            for p, d in sorted(items, key=lambda x: -(x[0]['year'] or 0))[:8]:
                print(f'      #{p["no"]:<4} {str(p["year"] or "—"):<6}n={str(p["n"] or "—"):<5}{d:<15}'
                      f'vs {"/".join(map(str, p["comparator"]))[:26]}')
            if status == 'INCONSISTENT':
                print('      → 写作层强制 mixed-evidence 模板，不许只写阳性结论')

        # 参考文献编号表
        refs_p = ranked[:args.refs]
        REFS = {i + 1: p for i, p in enumerate(refs_p)}

        def refs_block(subset=None):
            out = []
            for n, p in REFS.items():
                if subset and p['no'] not in subset:
                    continue
                out.append(f'[{n}] {p["year"] or "年份不详"}年 · {p["design"]} · n={p["n"] or "不详"} · '
                           f'对照={"/".join(map(str, p["comparator"]))[:24]} · 结论方向={p["direction"]}\n'
                           f'     结果：{(p["finding"] or "")[:150]}\n'
                           f'     方案：{p["method"] or "-"} {p["freq"] or ""} 穴位={"/".join(p["points"][:8]) or "-"} '
                           f'留针={p["retention"] or "-"}min 次数={p["sessions"] or "-"} 疗程={p["weeks"] or "-"}周')
            return '\n'.join(out)

        # ⑥ 写作
        print(f'\n【6】逐槽位写作（模型只拿到编号表，共 {len(REFS)} 条）')
        gen_slots = [c for c in ('S2', 'S3', 'S4') if slot_hits[c]]
        extras = {
            'S2': '注意：本段讲现有疗法及其局限，重点是对照措施的疗效不足之处。',
            'S3': ('注意：证据分两类且**结论方向不一致**，必须分别陈述、不许只写阳性结论：'
                   f'与假针刺对照 {incon.get("C1 针刺 vs 假针刺")}，'
                   f'与阳性药/常规疗法对照 {incon.get("C2 针刺 vs 阳性药/常规疗法")}。'
                   if incon.get('C2 针刺 vs 阳性药/常规疗法') == 'INCONSISTENT'
                   else '注意：如实陈述证据方向，不许夸大。'),
            'S4': '注意：本段讲研究缺口，从样本量、对照设置、干预方案异质性、随访时长四个角度写。',
        }
        sem = asyncio.Semaphore(3)
        drafts = await asyncio.gather(*[
            call(client, cfg, WRITE_PROMPT.format(
                slot_name=SLOT_NAME[c], topic=args.topic,
                refs=refs_block({p['no'] for p, _ in slot_hits[c]} | {p['no'] for p in refs_p[:8]}),
                extra=extras.get(c, '')), sem, want_json=False) for c in gen_slots])
        draft = dict(zip(gen_slots, drafts))

        # ⑦ 编号越界硬拦
        print('\n【7】编号越界检查')
        bad_all = {}
        for c, txt in draft.items():
            nums = cited_nums(txt)
            bad = sorted({n for n in nums if n not in REFS})
            bad_all[c] = bad
            print(f'   [{c}] 引用 {len(set(nums))} 条 · 越界 {bad if bad else "0 处 ✓"}')

        # ⑧ 引证核验
        print('\n【8】引证核验（每句 × 每条引文）')
        vres = await asyncio.gather(*[
            call(client, cfg, VERIFY_PROMPT.format(refs=refs_block(), text=draft[c]), sem)
            for c in gen_slots])
        verdicts = {}
        for c, v in zip(gen_slots, vres):
            rows = v if isinstance(v, list) else []
            verdicts[c] = rows
            cnt = Counter(str(r.get('verdict')) for r in rows)
            print(f'   [{c}] 判定 {len(rows)} 处：' + ' · '.join(f'{k} {n}' for k, n in cnt.most_common()))
            for r in rows:
                if str(r.get('verdict')) != 'supports':
                    print(f'        ⚠ [{r.get("cite")}] {str(r.get("sent"))[:34]}… → '
                          f'{r.get("verdict")}（{r.get("why")}）')

    # ── 成稿 ──
    print('\n' + '=' * 88)
    print(f'研究背景初稿　|　{args.topic}')
    print('=' * 88)
    for code, why in blocked:
        print(f'\n【{code}】{SLOT_NAME[code]}\n  ⛔ 未生成 —— {why}')
        print('     该段需引用本库之外的文献，请自行补充。')
    for c in gen_slots:
        print(f'\n【{c}】{SLOT_NAME[c]}')
        print('    ' + (draft[c] or '').replace('\n', '\n    '))
    print(f'\n【S5】{SLOT_NAME["S5"]}\n    因此，本研究拟开展一项【待补充：设计类型】试验，'
          '以【待补充：对照措施】为对照，评价' + args.topic + '，'
          '主要结局为【待补充：主要结局指标】，随访【待补充：随访时长】。')

    used = sorted({n for c in gen_slots for n in cited_nums(draft[c] or '') if n in REFS})
    print('\n' + '=' * 88)
    print('参考文献（由系统按被引编号从库中拼装，写作模型不参与）')
    print('=' * 88)
    for n in used:
        p = REFS[n]
        w = ('  ⚠年份未核实' if p['yconf'] != 'high' else '') + \
            ('  ⚠正文截断' if p['trunc'] == '1' else '') + \
            ('  ⚠PDF含夹带' if p['contam'] == '1' and p['cstatus'] != 'ok' else '')
        print(f'  [{n:>2}] {cite_of(p)}{w}')

    print('\n' + '=' * 88)
    print('推荐核心参考文献（近 3–5 年）')
    print('=' * 88)
    for w, lbl in ((5, '近5年'), (3, '近3年')):
        inw = [p for p in base if p['year'] and p['yconf'] == 'high' and CURRENT_YEAR - p['year'] <= w]
        print(f'  {lbl}：{len(inw)} 篇' + ('' if len(inw) >= 5 else '  ⚠ 覆盖不足'))
        if w == 5:
            for p in sorted(inw, key=lambda x: -(0.65 * smap.get(x['no'], 0) + 0.35 * recency(x)))[:8]:
                print(f'    · {p["year"]}  #{p["no"]:<4} n={str(p["n"] or "—"):<5}{p["direction"]:<15}'
                      f'{(p["title"] or "")[:52]}')

    print('\n' + '=' * 88)
    print('语料构成披露（本次检索所在病种类目）')
    print('=' * 88)
    dirs = Counter(p['direction'] for p in base)
    print(f'  类目「{group}」共 {len(base)} 篇：阳性 {dirs["positive"]} · 无差异 {dirs["no_difference"]}'
          f' · 阴性 {dirs["negative"]} · 无法判定 {dirs["unclear"]}')
    ok = len(base) - dirs['unclear']
    if ok:
        print(f'  可判定文献阳性率 {dirs["positive"] * 100 / ok:.1f}%'
              f'（全库 82.8%，阴性结果 0 篇 —— 存在发表偏倚，本段结论须谨慎解读）')
    print(f'  语种：中文 {len([p for p in base if p["lang"] == "zh"])} · 英文 {len([p for p in base if p["lang"] == "en"])}'
          f'　样本量中位 {sorted([p["n"] for p in base if p["n"]])[len([p for p in base if p["n"]]) // 2] if any(p["n"] for p in base) else "—"}')
    print(f'  质量标记：夹带未处理 {len([p for p in base if p["contam"] == "1" and p["cstatus"] not in ("ok", "na")])}'
          f' · 正文截断 {len([p for p in base if p["trunc"] == "1"])}'
          f' · 年份未核实 {len([p for p in base if p["yconf"] != "high"])}')
    print(f'\n耗时 {time.time() - t0:.0f}s')
    cur.close()
    conn.close()


if __name__ == '__main__':
    asyncio.run(main())
