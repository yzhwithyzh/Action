"""
文献检索的向量层：embed / rerank / 向量库加载与检索

被 `tools/lit_ingest.py`（入库时算向量）与 `tools/lit_agent.py`（检索）共用。

## 检索策略：向量召回 → 重排，BM25 只做降级

20 题评测集实测（`tools/lit_embed.py`，可重复跑）::

                   P@5     P@10     MRR
    BM25          0.730   0.718   0.818
    qwen 向量      0.940   0.862   0.975
    等权 RRF 混合   0.850   0.828   0.950
    向量 + 重排     0.930   0.912   0.950   ← 采用

给写作模型的是 8-12 条文献，所以 **P@10 比 P@5 更重要**，重排在这一项最优。

**混合检索被实测否掉了**：等权 RRF 反而从 0.940 掉到 0.850 —— BM25 太弱，
把向量的正确结果挤出前 5（「针灸缓解膝盖疼」向量 5/5 → 混合 3/5）。
RRF 只在两路强弱相当时才是免费的午餐，悬殊时弱的那一路就是噪声。

## 降级的两种态度，刻意不同

- **重排失败 → 静默降级**成纯向量。降级后 P@5 仍是 0.94，结果依然可用，
  为一个可选加成打断用户不值得。
- **向量不可用 → 退 BM25，但必须在出参里标出来**（`SearchResult.mode`）。
  从 0.94 掉到 0.73 是质的变化，而用户完全看不出来 —— 这种降级不报出来就是欺骗。

## 向量存 bytea，不上 pgvector

567 × 1024 × 4B = 2.2 MB，全量常驻内存、numpy 一次矩阵乘算完全部余弦。
装扩展或养一个向量库是净亏。存库里（而不是 .npy）是因为向量要跟着数据走：
后台改了文献要能重算，多副本部署时也不该各自持有一份不同步的文件。
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from dataclasses import dataclass, field

import httpx
import numpy as np

#: 向量维度上限的护栏：读回来的 bytea 长度必须能被 4 整除且与 embed_dim 对得上，
#: 否则说明这行的向量与声明的维度不一致（换过模型没重算），宁可当没有向量
MAX_DIM = 8192


#: 每个配置项认哪些环境变量（按顺序取第一个非空）。
#: `EMBED_API_KEY` 是 `.env.*` 里的正式名字，`EMBED_KEY` / `LLM_KEY` 是临时试跑时的简写。
_ENV_NAMES = {
    'embed_url': ('EMBED_BASE_URL',),
    'embed_key': ('EMBED_API_KEY', 'EMBED_KEY', 'LLM_KEY'),
    'embed_model': ('EMBED_MODEL',),
    'embed_batch': ('EMBED_BATCH',),
    'rerank_host': ('RERANK_HOST',),
    'rerank_key': ('RERANK_API_KEY', 'RERANK_KEY'),
    'rerank_model': ('RERANK_MODEL',),
    'rerank_n': ('RERANK_CANDIDATES',),
}


def cfg() -> dict:
    """
    检索配置：先取 `config.env.RetrievalConfig`，再由环境变量**逐项**覆盖。

    tools/ 下的脚本常常在没有完整后端环境时跑，所以不强依赖 config 模块 ——
    读不到就只用环境变量那一份。

    **逐项覆盖，不是「有一项就整份用环境变量」。** 原先的写法是
    `if not out['embed_url']: <读 RetrievalConfig>`，即拿 `embed_url` 一项决定整份配置
    的来源。**踩过一次**，而且正好踩在生产路径上：`config/env.py` 用 `load_dotenv`
    把 `.env.*` 灌进 `os.environ`，于是 worker 进程（先 import 了 config.env）里
    `EMBED_BASE_URL` 一定非空 —— 而当时这里认的键名是 `EMBED_KEY`，`.env` 里写的却是
    `EMBED_API_KEY`，key 取不到、fallback 又被 url 那一项挡住，结果就是
    **端点有、密钥空**，每次 embed 都以 `Illegal header value b'Bearer '` 失败，
    整条链路静默退回 BM25（实测 P@5 由 0.94 掉到 0.73）。
    tools/ 脚本反而正常 —— 它们在 import config 之前调 cfg()，走的是完整 fallback。

    这类失败没有任何外部症状：任务照常完成、版面照常渲染、文献照常列出来，
    只是**引的不是最切题的那几篇**。唯一的线索是出参里的 `retrieveMode`。
    """
    out: dict = {
        'embed_url': '', 'embed_key': '', 'embed_model': 'qwen3.7-text-embedding', 'embed_batch': 10,
        'rerank_host': '', 'rerank_key': '', 'rerank_model': 'qwen3.7-text-rerank', 'rerank_n': 30,
    }
    try:
        from config.env import RetrievalConfig as R  # noqa: PLC0415

        if R.embed_enabled:
            out.update(embed_url=R.embed_base_url.rstrip('/'), embed_key=R.embed_api_key,
                       embed_model=R.embed_model, embed_batch=R.embed_batch)
        if R.rerank_enabled:
            out.update(rerank_host=R.rerank_host, rerank_key=R.rerank_api_key,
                       rerank_model=R.rerank_model, rerank_n=R.rerank_candidates)
    except Exception as exc:  # noqa: BLE001
        # **不能静默吞掉**：读不到配置的后果是检索悄悄退回 BM25（P@5 由 0.94 掉到 0.73），
        # 而调用方只会看到「结果不太对」。tools/ 在 sys.path 里排到后端根目录之前时，
        # `common` 会被解析成 tools/common（worker 框架那个包），就会走到这里
        print(f'  ⚠ 读取 RetrievalConfig 失败，向量配置未生效：{type(exc).__name__}: {exc}'[:160])

    for field, names in _ENV_NAMES.items():
        raw = next((os.environ[n] for n in names if os.environ.get(n)), '')
        if not raw:
            continue
        if field in ('embed_batch', 'rerank_n'):
            out[field] = int(raw)
        elif field in ('embed_url', 'rerank_host'):
            out[field] = raw.strip().rstrip('/')
        else:
            # 密钥不 rstrip('/')：那是给地址用的，套到密钥上会把合法的末位字符吃掉
            out[field] = raw.strip()

    # 重排主机默认由 embed 地址推出来：DashScope 的 /rerank 不在 compatible-mode 下
    if not out['rerank_host'] and out['embed_url']:
        out['rerank_host'] = out['embed_url'].split('/compatible-mode')[0]
    if not out['rerank_key']:
        out['rerank_key'] = out['embed_key']

    return out


def embed_text(p: dict) -> str:
    """
    送去 embed 的文本：摘要 + 结构化标签。

    **不用全文**：背景写作要从一篇文献拿的信息就是「研究了什么、发现了什么」——那就是摘要。
    全文进来会被方法学套话（伦理审批号、SPSS 版本、纳排标准）稀释掉主题信号，
    而这些套话在 567 篇里几乎完全相同，等于给所有向量加了同一个偏置。

    把归一后的 `condition_group` 也拼进去是有意的：它让同类研究在向量空间里靠得更近，
    相当于把病种词表的工作成果喂给了 embedding。
    """
    g = lambda k: '/'.join(p.get(k) or [])  # noqa: E731
    return '。'.join(x for x in [
        p.get('title') or '',
        g('condition'), g('cgroup'), g('intervention'), g('outcomes'),
        (p.get('abstract') or '')[:1200],
        p.get('finding') or '',
    ] if x)[:4000]


def rerank_text(p: dict) -> str:
    """送去重排的文档文本。比 embed 的短——重排是逐对打分，长文本只是烧钱"""
    g = lambda k: '/'.join(p.get(k) or [])  # noqa: E731
    return '。'.join(x for x in [
        p.get('title') or '', g('cgroup'), g('intervention'), (p.get('abstract') or '')[:400],
    ] if x)[:800]


def text_hash(text: str) -> str:
    """embed 输入文本的指纹。文本变了 hash 就变，据此判断哪些向量过期"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:32]


def to_bytes(vec: np.ndarray) -> bytes:
    """L2 归一化后存 float32 原始字节。归一化放在写入侧，检索时点积即余弦"""
    v = np.asarray(vec, dtype=np.float32)
    n = float(np.linalg.norm(v))
    return (v / (n + 1e-9)).tobytes()


def from_bytes(raw, dim: int | None) -> np.ndarray | None:
    """bytea → 向量。长度对不上就当没有向量，绝不 reshape 出一个错的"""
    if not raw:
        return None
    buf = bytes(raw)
    if len(buf) % 4 or (dim and len(buf) != dim * 4) or (dim and not 0 < dim <= MAX_DIM):
        return None
    return np.frombuffer(buf, dtype=np.float32)


async def embed_many(client: httpx.AsyncClient, texts: list[str], conf: dict) -> list[list[float]]:
    """一批文本 → 向量。整批失败返回空列表，由调用方决定怎么办"""
    url = conf['embed_url'] + '/embeddings'
    for attempt in (1, 2, 3):
        try:
            r = await client.post(url, headers={'Authorization': f'Bearer {conf["embed_key"]}'},
                                  json={'model': conf['embed_model'], 'input': texts})
            r.raise_for_status()
            data = sorted(r.json()['data'], key=lambda d: d['index'])
            return [d['embedding'] for d in data]
        except Exception as exc:  # noqa: BLE001
            if attempt == 3:
                print(f'    embed 失败: {type(exc).__name__}: {exc}'[:130])
                return []
            await asyncio.sleep(3 * attempt)
    return []


async def rerank_docs(client: httpx.AsyncClient, query: str, docs: list[str],
                      top_n: int, conf: dict) -> list[int] | None:
    """
    重排，返回排序后的**原下标**。

    :return: 下标列表；未配置或调用失败返回 None（调用方据此静默降级成纯向量）
    """
    if not conf.get('rerank_host'):
        return None
    url = conf['rerank_host'].rstrip('/') + '/api/v1/services/rerank/text-rerank/text-rerank'
    for attempt in (1, 2):
        try:
            r = await client.post(url, headers={'Authorization': f'Bearer {conf["rerank_key"]}'},
                                  json={'model': conf['rerank_model'],
                                        'input': {'query': query, 'documents': docs},
                                        'parameters': {'top_n': top_n, 'return_documents': False}})
            r.raise_for_status()
            return [x['index'] for x in r.json()['output']['results']]
        except Exception as exc:  # noqa: BLE001
            if attempt == 2:
                # 4xx 时把响应体带上：DashScope 把真正的原因（「documents 超过 500 篇」、
                # 「query 为空」）只写在 body 里，异常文本只有一句 400 Bad Request 加 URL，
                # 曾经为了看清这一句不得不重新复现一遍
                body = ''
                if isinstance(exc, httpx.HTTPStatusError):
                    body = ' ' + ' '.join(exc.response.text[:300].split())
                print(f'    rerank 失败（降级为纯向量）: {type(exc).__name__}: {exc}'[:120] + body)
                return None
            await asyncio.sleep(2)
    return None


@dataclass
class SearchResult:
    """一次检索的结果。`mode` 必须一路传到出参 —— 降级了要让人知道"""

    #: 命中的文献，按最终排序
    hits: list[dict] = field(default_factory=list)
    #: vector+rerank / vector / bm25 —— **bm25 表示降级了，质量从 0.94 掉到 0.73**
    mode: str = 'bm25'
    #: 降级原因，正常时为空
    note: str = ''


class VectorStore:
    """
    进程内向量库：从库里读回全部向量，numpy 暴力算余弦。

    567 × 1024 = 2.2 MB，加载一次常驻。没有索引结构 —— 这个规模下 HNSW 之类是负收益。
    """

    def __init__(self, papers: list[dict]) -> None:
        vecs, self.ids, self.by_no = [], [], {}
        dims = set()
        for p in papers:
            self.by_no[p['no']] = p
            v = from_bytes(p.get('embedding'), p.get('embed_dim'))
            if v is not None:
                vecs.append(v)
                self.ids.append(p['no'])
                dims.add(len(v))
        # 维度不一致 = 语料里混了两个模型算的向量，它们的相似度毫无意义。
        # 宁可整个不用，也不能拿混的算 —— 混着算不会报错，只会悄悄给出错的排序
        if len(dims) > 1:
            print(f'  ⚠ 向量维度不一致 {sorted(dims)}，疑似混用了不同 embedding 模型，本次不用向量')
            vecs, self.ids = [], []
        self.mat = np.vstack(vecs) if vecs else None
        self.models = {p.get('embed_model') for p in papers if p.get('embedding')}

    @property
    def ready(self) -> bool:
        return self.mat is not None and len(self.ids) > 0

    @property
    def coverage(self) -> tuple[int, int]:
        return len(self.ids), len(self.by_no)

    def search(self, qvec: np.ndarray, top_k: int) -> list[tuple[int, float]]:
        """:return: [(corpus_no, 余弦相似度)]，按相似度降序"""
        if not self.ready:
            return []
        q = np.asarray(qvec, dtype=np.float32)
        q = q / (np.linalg.norm(q) + 1e-9)
        scores = self.mat @ q
        idx = np.argsort(-scores)[:top_k]
        return [(self.ids[i], float(scores[i])) for i in idx]
