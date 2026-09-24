"""
BM25 vs 向量检索 vs 混合：在真实语料上对比，用数字决定要不要上 embedding

跑法（工作目录 action-backend/）::

    set LLM_BASE_URL=... & set LLM_KEY=...
    python -m tools.lit_embed --build     # 建 567 篇的向量（一次性，落 lit_out/vec.npy）
    python -m tools.lit_embed --eval      # 跑对比

## 为什么要测而不是直接上

之前给的是论证不是测量：「抽取层已把 condition/intervention/outcomes 归一成中文，
跨语言问题被解决了，所以 BM25 够用」。这个推理成立与否取决于**真实召回率**，
而 567 篇的规模下建一次向量只要几分钟、几美分，没有理由靠猜。

## 向量不进 pgvector，也不进独立向量库

567 × 1536 × 4B = **3.5 MB**，一个 `.npy` 文件全量常驻内存，numpy 一次矩阵乘
算完全部余弦相似度。为它装 PG 扩展或养一个 Milvus 是净亏。

真要落库时加一列 `bytea` 即可 —— 唯一值得为 pgvector 付成本的场景是后端多副本部署
且文献库频繁更新（进程内缓存会不一致），而这个库是低频更新的。
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
from collections import Counter

import httpx
import numpy as np
import psycopg2

# tools 目录放在 sys.path 末尾。注意：**这解决不了 `common` 的遮蔽**——
# `action-backend/common` 无 __init__.py（PEP 420 命名空间包），`tools/common` 有
# （worker 框架的常规包），而**常规包胜过命名空间包、与路径顺序无关**。
# 所以后端服务不能在 tools 在路径上时做延迟 import，见
# module_action/service/literature_embed_service._arr 上的注释。
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from lit_agent import BM25, doc_text, jl, load_corpus, tok  # noqa: E402
from lit_vector import cfg  # noqa: E402

DB = dict(host='127.0.0.1', port=5432, user='postgres', password='123456', dbname='action')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lit_out')
#: 模型与端点走环境变量，向量文件名带模型标识 —— **两个模型的向量空间不可比**，
#: 混用会得到毫无意义的相似度。文件名分开，是为了能把两套向量都留着做对比，
#: 也是为了「哪份向量是哪个模型算的」这件事一眼可见，而不是靠记。
#: 模型名同样走 `lit_vector.cfg()`，**不在这里给默认值**。这里曾经默认
#: `text-embedding-3-small`（OpenAI 的），而实际端点上的是 `qwen3.7-text-embedding`
#: —— 于是整批调用 404，而 `embed()` 拿零向量占位继续算，最后报出「向量法 P@5 0.010」。
#: 那是个**看着像结论的数字**：它读起来是「向量检索不行」，实际是「模型名配错了」
EMBED_MODEL = cfg().get('embed_model') or 'qwen3.7-text-embedding'
_SLUG = re.sub(r'[^a-z0-9]+', '-', EMBED_MODEL.lower()).strip('-')
VEC = os.path.join(OUT, f'vec-{_SLUG}.npy')
IDS = os.path.join(OUT, f'vec-{_SLUG}.ids.json')
BATCH = int(os.environ.get('EMBED_BATCH', '25'))

#: 评测集：每条是（查询, 该命中的病种类目）。
#: **刻意混入两类难例**：① 同义改写（「睡不着」不含"失眠"二字）；
#: ② 纯英文查询打中文语料。BM25 在这两类上应该明显吃亏 —— 如果实测没吃亏，
#: 说明抽取层的中文归一确实把跨语言问题解决了，那 embedding 就可以不上。
EVAL = [
    ('针刺治疗慢性失眠的疗效', '失眠'),
    ('针灸改善睡眠质量的随机对照研究', '失眠'),
    ('扎针能不能让人睡得着', '失眠'),
    ('acupuncture for insomnia randomized controlled trial', '失眠'),
    ('电针治疗功能性便秘', '便秘'),
    ('针刺改善排便困难与排便次数', '便秘'),
    ('acupuncture for chronic constipation', '便秘'),
    ('针刺治疗膝骨关节炎疼痛', '膝骨关节炎'),
    ('针灸缓解膝盖疼和活动受限', '膝骨关节炎'),
    ('knee osteoarthritis acupuncture pain', '膝骨关节炎'),
    ('针刺治疗卒中后抑郁', '抑郁'),
    ('针灸改善中风病人的情绪低落', '抑郁'),
    ('针刺治疗多囊卵巢综合征', '多囊卵巢综合征'),
    ('针灸调节排卵与月经周期紊乱', '多囊卵巢综合征'),
    ('针刺治疗脑卒中后吞咽困难', '吞咽障碍'),
    ('针灸治疗偏头痛发作', '偏头痛'),
    ('针刺缓解术后疼痛与减少镇痛药', '术后疼痛'),
    ('针刺治疗干眼', '干眼'),
    ('电针治疗女性压力性尿失禁', '尿失禁'),
    ('针刺辅助治疗2型糖尿病', '糖尿病'),
]


def pick():
    """
    embedding 的 key/端点。**统一走 `lit_vector.cfg()`，不在这里另抄一份解析。**

    这里曾经自己读 `EMBED_KEY` / `EMBED_BASE_URL`，而 `.env.*` 里的正式键名是
    `EMBED_API_KEY` —— 于是评测集与线上跑的是**两套配置**，线上悄悄退回 BM25、
    评测集却报着 0.94，两边都没有任何报错。回归基线一旦和生产不是同一份配置，
    它就不再是基线了。`cfg()` 会读 RetrievalConfig 再由环境变量逐项覆盖，两个键名都认。
    """
    conf = cfg()
    if not conf.get('embed_key') or not conf.get('embed_url'):
        raise SystemExit('检索配置不完整：请在 .env 里配 EMBED_ENABLED / EMBED_BASE_URL / EMBED_API_KEY')

    return conf['embed_key'], conf['embed_url'].rstrip('/') + '/embeddings'


async def embed(client, url, key, texts: list[str]) -> list[list[float]]:
    """
    一批文本 → 向量。**失败就抛，不拿零向量占位。**

    占位过（`[[0.0] * dim]`），代价是：一次模型名配错让整批 404，评测照常跑完并报出
    「向量 P@5 0.010」—— 那个数字读起来是「向量检索不行」，实际是「端点/模型名配错了」。
    回归基线最不能做的事就是把配置故障渲染成一个可信的分数。
    """
    last = None
    for attempt in (1, 2, 3):
        try:
            r = await client.post(url, headers={'Authorization': f'Bearer {key}'},
                                  json={'model': EMBED_MODEL, 'input': texts})
            r.raise_for_status()
            data = sorted(r.json()['data'], key=lambda d: d['index'])

            return [d['embedding'] for d in data]
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt == 3:
                raise SystemExit(
                    f'embed 调用失败（模型 {EMBED_MODEL} @ {url}）：{type(exc).__name__}: {exc}'[:300]
                ) from exc
            await asyncio.sleep(3 * attempt)
    raise SystemExit(f'embed 调用失败：{last}')
    return []


def embed_text(p: dict) -> str:
    """
    送去 embed 的文本。**用摘要 + 结构化标签，不用全文** ——
    背景写作要从一篇文献拿的信息就是「研究了什么、发现了什么」，那就是摘要；
    全文进来只会被方法学套话（伦理审批、统计软件、纳排标准）稀释掉主题信号。
    """
    return '。'.join(x for x in [
        p['title'] or '',
        '/'.join(p['condition']) if p['condition'] else '',
        '/'.join(p['cgroup']) if p['cgroup'] else '',
        '/'.join(p['intervention']) if p['intervention'] else '',
        '/'.join(p['outcomes']) if p['outcomes'] else '',
        (p['abstract'] or '')[:1200],
        p['finding'] or '',
    ] if x)[:4000]


async def build():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    papers = load_corpus(cur)
    cur.close()
    conn.close()
    key, url = pick()
    print(f'为 {len(papers)} 篇建向量（{EMBED_MODEL} @ {url}，批 {BATCH}）')
    t0 = time.time()
    vecs: list[list[float]] = []
    async with httpx.AsyncClient(timeout=300) as client:
        for i in range(0, len(papers), BATCH):
            part = papers[i:i + BATCH]
            vecs += await embed(client, url, key, [embed_text(p) for p in part])
            print(f'  {min(i + BATCH, len(papers))}/{len(papers)}', end='\r', flush=True)
    arr = np.asarray(vecs, dtype=np.float32)
    arr /= np.linalg.norm(arr, axis=1, keepdims=True) + 1e-9
    np.save(VEC, arr)
    with open(IDS, 'w', encoding='utf-8') as fh:
        json.dump([p['no'] for p in papers], fh)
    print(f'\n完成 {arr.shape} · {arr.nbytes / 1024 / 1024:.1f} MB · 耗时 {time.time() - t0:.0f}s → {VEC}')
    # 全 0 向量 = 该批调用三次都失败。**必须显式报出来**：0 向量与任何查询的余弦都是 0，
    # 表现是「这几篇永远检索不到」，而排序结果看着完全正常，不查是发现不了的
    zero = int((np.abs(arr).sum(axis=1) < 1e-6).sum())
    if zero:
        print(f'  ⚠ 有 {zero} 篇是全 0 向量（该批调用失败），重跑 --build 补齐')


def rrf(*rank_lists, k=60, weights=None):
    """
    倒数排名融合。用它而不是加权求和：BM25 分数与余弦相似度**量纲不可比**
    （前者无上界、后者 -1~1），归一化后再加权要调一个魔数，换语料就得重调。

    **但等权 RRF 在两路强弱悬殊时会拖后腿**：实测 qwen 向量 P@5=0.94、
    BM25 只有 0.73，等权融合反而掉到 0.85 —— 弱的那一路把强的那一路的正确结果
    挤出前 5。所以留了 `weights`。
    """
    ws = weights or [1.0] * len(rank_lists)
    score: Counter = Counter()
    for ranks, w in zip(rank_lists, ws):
        for pos, no in enumerate(ranks):
            score[no] += w / (k + pos + 1)
    return [no for no, _ in score.most_common()]


#: 重排走 DashScope 原生路径 —— compatible-mode 下没有 /rerank（实测 404）
RERANK_MODEL = cfg().get('rerank_model') or 'qwen3.7-text-rerank'


async def rerank(client, key, host, query: str, docs: list[str], top_n: int) -> list[int]:
    """
    重排：返回按相关度排序后的**原下标**列表。失败时原样返回，绝不打乱

    :return: 排序后的下标；调用失败时返回 `range(len(docs))`
    """
    url = host.rstrip('/') + '/api/v1/services/rerank/text-rerank/text-rerank'
    for attempt in (1, 2):
        try:
            r = await client.post(url, headers={'Authorization': f'Bearer {key}'},
                                  json={'model': RERANK_MODEL,
                                        'input': {'query': query, 'documents': docs},
                                        'parameters': {'top_n': top_n, 'return_documents': False}})
            r.raise_for_status()
            return [x['index'] for x in r.json()['output']['results']]
        except Exception as exc:  # noqa: BLE001
            if attempt == 2:
                print(f'  rerank 失败: {type(exc).__name__}: {exc}'[:110])
                return list(range(len(docs)))
            await asyncio.sleep(2)
    return list(range(len(docs)))


def rerank_text(p: dict) -> str:
    """送去重排的文档文本。比 embed 的更短——重排是逐对打分，长文本只是烧钱"""
    return '。'.join(x for x in [
        p['title'] or '',
        '/'.join(p['cgroup']) if p['cgroup'] else '',
        '/'.join(p['intervention']) if p['intervention'] else '',
        (p['abstract'] or '')[:400],
    ] if x)[:800]


async def evaluate():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    papers = load_corpus(cur)
    cur.close()
    conn.close()
    papers = [p for p in papers if p['design'] != 'protocol']
    by_no = {p['no']: p for p in papers}
    arr = np.load(VEC)
    ids = json.load(open(IDS, encoding='utf-8'))
    keep = [i for i, no in enumerate(ids) if no in by_no]
    arr, ids = arr[keep], [ids[i] for i in keep]
    bm = BM25([tok(doc_text(p)) for p in papers])
    order = [p['no'] for p in papers]
    key, url = pick()

    host = cfg().get('rerank_host') or ''
    do_rerank = bool(host) and not os.environ.get('SKIP_RERANK')

    print(f'语料 {len(papers)} 篇 · 向量 {arr.shape} · 模型 {EMBED_MODEL} · 评测 {len(EVAL)} 题')
    print(f'重排 {RERANK_MODEL if do_rerank else "（跳过）"}\n')
    hdr = f'{"查询":<30}{"类目":<11}{"BM25":>13}{"向量":>13}{"等权":>13}{"权3:1":>13}{"重排":>13}'
    print(hdr)
    print('-' * len(hdr.encode('gbk', 'ignore')))
    agg = {k: {'r5': 0, 'r10': 0, 'mrr': 0.0} for k in ('bm', 'vec', 'hyb', 'hyb3', 'rrk')}

    async with httpx.AsyncClient(timeout=180) as client:
        for q, group in EVAL:
            gold = {p['no'] for p in papers if group in p['cgroup']}
            qv = np.asarray((await embed(client, url, key, [q]))[0], dtype=np.float32)
            qv /= np.linalg.norm(qv) + 1e-9
            vrank = [ids[i] for i in np.argsort(-(arr @ qv))]
            braw = bm.score(tok(q))
            brank = [order[i] for i in np.argsort(-np.asarray(braw))]
            hrank = rrf(brank[:50], vrank[:50])
            # 向量权重 3 倍：弱的那一路只用来补漏，不许把强的那一路挤出前排
            h3rank = rrf(brank[:50], vrank[:50], weights=[1.0, 3.0])
            # 重排：向量召回 30 条交给 cross-encoder 逐对打分。**只重排、不召回** ——
            # 逐对打分是 O(n)，全库 547 篇跑一遍既慢又贵，召回仍归向量
            if do_rerank:
                cand = [by_no[n] for n in vrank[:30]]
                idx = await rerank(client, key, host, q, [rerank_text(p) for p in cand], 10)
                rrank = [cand[i]['no'] for i in idx] + [n for n in vrank[30:]]
            else:
                rrank = vrank

            cells = []
            for name, rank in (('bm', brank), ('vec', vrank), ('hyb', hrank),
                               ('hyb3', h3rank), ('rrk', rrank)):
                top5 = sum(1 for n in rank[:5] if n in gold)
                top10 = sum(1 for n in rank[:10] if n in gold)
                first = next((i for i, n in enumerate(rank) if n in gold), None)
                agg[name]['r5'] += top5 / min(5, len(gold) or 1)
                agg[name]['r10'] += top10 / min(10, len(gold) or 1)
                agg[name]['mrr'] += 1 / (first + 1) if first is not None else 0.0
                cells.append(f'{top5}/5 {top10}/10'.rjust(13))
            print(f'{q[:28]:<30}{group[:5] + "(" + str(len(gold)) + ")":<11}' + ''.join(cells))

    n = len(EVAL)
    print('\n' + '=' * 68)
    print(f'{"":<10}{"P@5":>10}{"P@10":>10}{"MRR":>10}')
    for name, lbl in (('bm', 'BM25'), ('vec', '向量'), ('hyb', '等权RRF'),
                      ('hyb3', 'RRF 向量权3'), ('rrk', '向量+重排')):
        a = agg[name]
        print(f'{lbl:<10}{a["r5"] / n:>10.3f}{a["r10"] / n:>10.3f}{a["mrr"] / n:>10.3f}')
    print('=' * 68)
    print('P@5/P@10 = 前 N 条里属于该病种类目的比例（对小类目按类目大小归一）')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--eval', action='store_true')
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if args.build:
        asyncio.run(build())
    if args.eval:
        if not os.path.exists(VEC):
            raise SystemExit('先跑 --build')
        asyncio.run(evaluate())


if __name__ == '__main__':
    main()
