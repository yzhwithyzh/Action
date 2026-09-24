"""
背景生成的编排与提示词。

纯算法层：**输入是研究方向 + 数据库游标 + 一个 `ask` 回调，输出是结果字典**。
不认识 Redis、不认识 HTTP、不认识 worker —— `ask` 由调用方注入，
worker 传的是走模型池的实现，离线单测传的是假实现。
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Awaitable, Callable

import numpy as np

from tools.background_worker_tool.engine.pipeline import (
    BM25, MIN_HITS, SLOT_DESIGN_REQ, SLOT_ORDER, TAU, _SHAM,
    cite_of, cited_nums, doc_text, load_corpus, recency, ref_warnings, rel, tok,
)

#: 调模型：(prompt, 是否要 JSON) -> 文本或已解析的对象
Ask = Callable[[str, bool], Awaitable[Any]]
#: 进度回调：(阶段, 0-100)
OnProgress = Callable[[str, int], None]

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


def _refs_block(refs: dict[int, dict]) -> str:
    """交给写作模型的编号表。**只有编号 + 事实，没有标题作者** —— 这是第一道闸"""
    out = []
    for n, p in refs.items():
        out.append(
            f'[{n}] {p["year"] or "年份不详"}年 · {p["design"]} · n={p["n"] or "不详"} · '
            f'对照={"/".join(map(str, p["comparator"]))[:24]} · 结论方向={p["direction"]}\n'
            f'     结果：{(p["finding"] or "")[:150]}\n'
            f'     方案：{p["method"] or "-"} {p["freq"] or ""} 穴位={"/".join(p["points"][:8]) or "-"} '
            f'留针={p["retention"] or "-"}min 次数={p["sessions"] or "-"} 疗程={p["weeks"] or "-"}周'
        )

    return '\n'.join(out)


def _evidence_table(pool: list[dict]) -> dict[str, Any]:
    """
    按对照类型分组、按效应方向判分歧。

    **靠代码判，不靠模型自觉**：LLM 有强烈的阳性叙事倾向，给它 5 篇阳性 2 篇阴性，
    写出来的十有八九是「既往研究一致表明…」。分歧时强制走 mixed-evidence 模板。
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for p in pool:
        if p['direction'] == 'unclear':
            groups['unclear'].append(p)
        elif any(_SHAM.search(str(x)) for x in p['comparator']):
            groups['sham'].append(p)
        else:
            groups['active'].append(p)

    out = {}
    for key in ('sham', 'active'):
        items = groups.get(key, [])
        dirs = Counter(p['direction'] for p in items)
        real = [k for k in dirs if k in ('positive', 'negative', 'no_difference')]
        out[key] = {
            'total': len(items),
            'dirs': dict(dirs),
            'status': 'INCONSISTENT' if len(real) > 1 else 'CONSISTENT',
        }
    out['unclear'] = {'total': len(groups.get('unclear', []))}

    return out


async def generate_background(
    cur: Any,
    topic: str,
    *,
    ask: Ask,
    search: Callable[..., Awaitable[tuple[list[dict], str]]],
    current_year: int,
    on_progress: OnProgress | None = None,
    group_hint: str = '',
    fatal: tuple[type[BaseException], ...] = (),
) -> dict[str, Any]:
    """
    跑一次背景生成。

    :param cur: 数据库游标（同步 psycopg2 游标即可，只做只读查询）
    :param topic: 研究方向
    :param ask: 调模型的回调，`(prompt, want_json) -> 文本或对象`
    :param search: 检索回调，`(query, top_k, *, rerank=True) -> (命中文献列表, 检索模式)`。
        模式为 `bm25` 时表示**向量不可用已降级**（实测 P@5 由 0.94 掉到 0.73），
        必须一路传到出参。`rerank=False` 表示「只要每篇的向量相关度分，不要重排」——
        第④步给整个类目池打分用的就是它，见那里的注释
    :param current_year: 当前年份，近期性与「近 3-5 年」窗口用
    :param on_progress: 进度回调
    :param group_hint: 指定病种类目；留空则由 PICO 结果推断
    :param fatal: **不许被降级逻辑吞掉的异常类型**。第 8 步核验失败是可降级的
        （见那一段的注释），但调用方的「停止任务」信号也是从 `ask` 里抛出来的一个
        普通 Exception —— 引擎不认识它是什么，只知道它不能当成「这次核验没跑成」处理，
        否则用户点了停止，任务还会不紧不慢地把剩下三段核验完再返回
    :return: 结果字典
    """
    def tick(stage: str, pct: int) -> None:
        if on_progress:
            on_progress(stage, pct)

    papers = load_corpus(cur)
    by_no = {p['no']: p for p in papers}

    # ① PICO
    tick('pico', 4)
    pico = await ask(PICO_PROMPT.format(topic=topic), True)
    if not isinstance(pico, dict) or not pico.get('queries'):
        raise ValueError('研究问题解析失败，模型未返回可用的结构化结果')
    tick('pico', 12)

    # 病种类目：软过滤，用于 Evidence Table 与语料构成披露
    group = group_hint
    if not group:
        gcount = Counter(g for p in papers for g in p['cgroup'])
        cand = {str(x) for x in (pico.get('condition') or [])}
        best = [(g, n) for g, n in gcount.items() if any(c in g or g in c for c in cand)]
        group = max(best, key=lambda x: x[1])[0] if best else ''
    pool = [p for p in papers if group and group in p['cgroup']]

    # ② 逐槽位检索 + ③ 覆盖度闸
    bm = BM25([tok(doc_text(p)) for p in papers])
    order = [p['no'] for p in papers]
    slot_hits: dict[str, list[dict]] = {}
    #: 被覆盖度闸拦下的槽位 → `{'need': [该槽位要求的研究设计], 'got': [(实际检到的设计, 篇数)]}`
    #:
    #: **要 need 也要 got，且都是结构化的**：这两个数字合起来才说得清「为什么这段没写」——
    #: 「需要流行病学/系统综述，检到的 30 篇全是 RCT」是一句用户能据以行动的话
    #: （去补一篇流调），而「证据不足」不是。原先这里存的是 `json.dumps(Counter)`，
    #: 前台直接把它插进句子里，页面上就会出现「文献库中缺少 {"rct": 30} 这类研究」
    blocked: dict[str, dict[str, Any]] = {}
    modes: set[str] = set()
    for i, code in enumerate(SLOT_ORDER):
        q = str((pico.get('queries') or {}).get(code) or '')
        hits, mode = await search(q, 12)
        modes.add(mode)
        tau_hard, tau_soft = TAU['vector' if mode.startswith('vector') else 'bm25']
        if mode.startswith('vector'):
            scored = [(p, float(p.get('_score', 0.0))) for p in hits]
        else:
            raw = dict(zip(order, bm.score(tok(q))))
            scored = [(p, rel(raw.get(p['no'], 0.0))) for p in hits]
        req = SLOT_DESIGN_REQ[code]
        fit = [p for p, r in scored if p['design'] in req and r >= tau_hard]
        if len(fit) < MIN_HITS:
            got = Counter(p['design'] for p, _ in scored)
            blocked[code] = {'need': sorted(req),
                             'got': [{'design': d, 'n': n} for d, n in got.most_common()]}
            slot_hits[code] = []
        else:
            slot_hits[code] = fit[:8]
        tick('search', 12 + int(20 * (i + 1) / len(SLOT_ORDER)))

    # ④ 核心文献排序
    base = pool or papers
    topic_q = ' '.join(map(str, (pico.get('condition') or []) + (pico.get('intervention') or [])
                           + (pico.get('outcomes') or [])))
    # **这一步不重排**。要的是类目池里每一篇的向量相关度分（`_score`），不是「前 12 篇」——
    # 命令行原版 `lit_agent.py` 这里就是一次 embedding + 内存里算全库余弦，零外部调用。
    # 曾经走了带重排的检索：池空时 base 回落成全库，547 篇整批送去 rerank，撞上
    # DashScope 单次 500 篇的上限报 400；而即使成功，rerank 只调换顺序、不改 `_score`，
    # 下面的 smap 一分都没用上，纯属白付一次调用。踩过一次
    ranked_hits, _ = await search(topic_q, len(base) or 30, rerank=False)
    smap = {p['no']: float(p.get('_score', 0.0)) for p in ranked_hits}
    if not smap:
        smap = {p['no']: rel(s) for p, s in zip(papers, bm.score(tok(topic_q)))}
    ranked = sorted(base, key=lambda p: -(0.65 * smap.get(p['no'], 0) + 0.35 * recency(p, current_year)))
    refs = {i + 1: p for i, p in enumerate(ranked[:12])}

    # ⑤ Evidence Table
    table = _evidence_table(base)
    tick('search', 34)

    # ⑥ 逐槽位写作
    inconsistent = table['active']['status'] == 'INCONSISTENT' or table['sham']['status'] == 'INCONSISTENT'
    extras = {
        'S2': '注意：本段讲现有疗法及其局限，重点是对照措施的疗效不足之处。',
        'S3': (f'注意：证据分两类且**结论方向不一致**，必须分别陈述、不许只写阳性结论：'
               f'与假针刺对照 {table["sham"]["status"]}，与阳性药/常规疗法对照 {table["active"]["status"]}。'
               if inconsistent else '注意：如实陈述证据方向，不许夸大。'),
        'S4': '注意：本段讲研究缺口，从样本量、对照设置、干预方案异质性、随访时长四个角度写。',
    }
    slot_names = {'S1': '疾病负担与临床重要性', 'S2': '现有疗法及其局限',
                  'S3': '针刺/电针的既往证据', 'S4': '现有证据的不足（研究缺口）'}
    block = _refs_block(refs)
    drafts: dict[str, str] = {}
    gen = [c for c in SLOT_ORDER if slot_hits.get(c)]
    for i, code in enumerate(gen):
        drafts[code] = str(await ask(
            WRITE_PROMPT.format(slot_name=slot_names[code], topic=topic, refs=block,
                                extra=extras.get(code, '')), False) or '')
        tick('write', 34 + int(40 * (i + 1) / max(len(gen), 1)))

    # ⑦ 编号越界硬拦
    over: dict[str, list[int]] = {}
    for code, txt in drafts.items():
        bad = sorted({n for n in cited_nums(txt) if n not in refs})
        if bad:
            over[code] = bad

    # ⑧ 引证核验
    #
    # **核验失败降级，不让整次生成作废**：走到这一步时四段正文已经写完，那是八次模型调用、
    # 四分钟的东西；为了第四道闸把它整个扔掉，用户下次重来还得再付一遍。前三道闸
    #（只给编号表 / 编号越界硬拦 / 参考文献表由代码拼装）都已经生效，正文本身是可用的。
    #
    # 但**降级必须报出来**（`verifyFailed`）：核验过的稿子和没核验过的稿子长得一模一样，
    # 而它们的可信度差着一整道闸 —— 不标出来就等于把「没查」当成了「查过没问题」。
    verdicts: list[dict[str, Any]] = []
    verify_failed: list[str] = []
    for i, code in enumerate(gen):
        try:
            rows = await ask(VERIFY_PROMPT.format(refs=block, text=drafts[code]), True)
        except fatal:
            raise
        except Exception:  # noqa: BLE001
            verify_failed.append(code)
            tick('verify', 74 + int(22 * (i + 1) / max(len(gen), 1)))
            continue
        for r in rows if isinstance(rows, list) else []:
            if str(r.get('verdict')) != 'supports':
                verdicts.append({
                    'slot': code, 'cite': str(r.get('cite')), 'sent': str(r.get('sent'))[:60],
                    'verdict': str(r.get('verdict')), 'why': str(r.get('why'))[:40],
                })
        tick('verify', 74 + int(22 * (i + 1) / max(len(gen), 1)))

    # ⑨ 参考文献表由代码拼装
    used = sorted({n for c in gen for n in cited_nums(drafts[c]) if n in refs})
    dirs = Counter(p['direction'] for p in base)
    ok_n = len(base) - dirs['unclear']
    in5 = [p for p in base if p['year'] and p['yconf'] == 'high' and current_year - p['year'] <= 5]
    tick('verify', 98)

    return {
        'topic': topic,
        'group': group,
        'pico': pico,
        'retrieveMode': 'bm25' if modes == {'bm25'} else ('vector+rerank' if 'vector+rerank' in modes else 'vector'),
        'slots': [
            {
                'code': c, 'title': slot_names[c],
                'blocked': c in blocked,
                'blockedDesigns': blocked.get(c) or None,
                'text': drafts.get(c, ''),
                'overCited': over.get(c, []),
            }
            for c in SLOT_ORDER
        ],
        'refs': [
            {'n': n, 'corpusNo': refs[n]['no'], 'cite': cite_of(refs[n]), 'warn': ref_warnings(refs[n])}
            for n in used
        ],
        'verdicts': verdicts,
        #: 没能核验的段落。非空 = 第四道闸这次没跑成，展示端必须说出来
        'verifyFailed': verify_failed,
        'evidence': table,
        'corpus': {
            'group': group, 'total': len(base),
            'positive': dirs['positive'], 'noDiff': dirs['no_difference'],
            'negative': dirs['negative'], 'unclear': dirs['unclear'],
            'positiveRate': round(dirs['positive'] * 100 / ok_n, 1) if ok_n else 0.0,
            'recent5': len(in5),
            'zh': len([p for p in base if p['lang'] == 'zh']),
            'en': len([p for p in base if p['lang'] == 'en']),
        },
    }
