"""
一次背景生成任务。

算法在 `engine/generate.py`（纯函数，不认识 Redis/HTTP/业务表）；这里只负责把它接上
模型池、检索层与进度上报 —— 与 `tools/checklist_worker_tool` 同一种分层。

## 检索：向量为主，BM25 只做降级，且**降级要标出来**

20 题评测集实测（`tools/lit_embed.py --eval`，可重复跑）::

                    P@5     P@10     MRR
    BM25           0.730   0.718   0.818
    qwen 向量       0.940   0.862   0.975
    向量 + 重排      0.930   0.912   0.950   ← 采用

混合检索**被实测否掉**：等权 RRF 反而从 0.940 掉到 0.850 —— BM25 太弱，把向量的正确
结果挤出前 5。RRF 只在两路强弱相当时才是免费的午餐。

两种降级态度刻意不同：**重排失败 → 静默降级**成纯向量（P@5 仍 0.94，结果依然可用）；
**向量不可用 → 退 BM25 但必须写进出参**（`retrieveMode`）——从 0.94 掉到 0.73 是质的
变化，而用户完全看不出来，不报出来就是欺骗。
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from typing import Any

import httpx
import numpy as np

from tools.background_worker_tool.engine.generate import generate_background
from tools.background_worker_tool.engine.pipeline import BM25, doc_text, load_corpus, rel, tok
from tools.common.base_session_task import BaseSessionTask, TaskPayloadError, TaskStopped

MIN_TOPIC_CHARS = 4
MAX_TOPIC_CHARS = 200
#: 单次模型调用超时。写作一段 400 字、核验一段十几句，都在这个量级内
LLM_TIMEOUT = 180.0

#: 传输层错误在同一个模型上重试几次（含首次）。见 `_call_pool` 的 docstring
_TRANSPORT_RETRY = 3
_RETRY_BACKOFF = 4.0
#: 「这一次连接不行」而不是「这个模型不行」的错误。httpx 的传输层异常全在 TransportError 下
_TRANSIENT = (httpx.TransportError,)


class BackgroundSessionTask(BaseSessionTask):
    """研究方向 → 研究背景初稿 + 推荐参考文献。"""

    task_type = 'background_gen'

    def __init__(self, payload: dict[str, Any], *, model_health: Any = None, **kwargs: Any) -> None:
        super().__init__(payload, **kwargs)
        self._topic = ''
        self._locale = 'zh'
        self._group = ''
        self._model_health = model_health
        self._model_label = ''
        self._store: Any = None
        self._conf: dict[str, Any] = {}

    # ================================================================== 校验

    def validate(self) -> None:
        topic = str(self.payload.get('topic') or '').strip()
        if len(topic) < MIN_TOPIC_CHARS:
            raise TaskPayloadError(f'研究方向过短（少于 {MIN_TOPIC_CHARS} 字），无法检索')
        self._topic = topic[:MAX_TOPIC_CHARS]
        self._locale = 'en' if str(self.payload.get('locale') or 'zh').lower().startswith('en') else 'zh'
        self._group = str(self.payload.get('condition_group') or '').strip()

    def task_meta(self) -> dict[str, Any]:
        return {**super().task_meta(), 'topic': self._topic, 'locale': self._locale}

    # ================================================================== 主流程

    async def process(self) -> dict[str, Any]:
        import psycopg2  # noqa: PLC0415

        from config.env import DataBaseConfig, RetrievalConfig  # noqa: PLC0415
        from tools.common.model_registry import load_llm_models  # noqa: PLC0415
        from tools.lit_vector import VectorStore, cfg as vcfg  # noqa: PLC0415

        pool = [m for m in await load_llm_models() if m.api_key and m.model_code]
        if not pool:
            # 如实报错，不静默返回空串 —— 后者会被用户读成「AI 觉得没什么可写的」
            raise RuntimeError('暂无可用的AI模型，请在后台「AI模型管理」中配置')
        self._conf = vcfg()

        # 用同步 psycopg2 而不是后端那套 async 会话：引擎只做只读查询、且要在
        # 同步回调里被反复调用；为它拖进 SQLAlchemy 的 async 生命周期只会把
        # 「跨 commit 读 ORM 属性抛 MissingGreenlet」那类坑一并引进来
        conn = psycopg2.connect(
            host=DataBaseConfig.db_host, port=DataBaseConfig.db_port,
            user=DataBaseConfig.db_username, password=DataBaseConfig.db_password,
            dbname=DataBaseConfig.db_database,
        )
        try:
            cur = conn.cursor()
            papers = load_corpus(cur)
            store = VectorStore(papers)
            have, tot = store.coverage
            await self.log.write_info(
                f'语料 {tot} 篇，其中 {have} 篇有向量'
                + (f'（{"/".join(m for m in store.models if m)}）' if store.models else '')
            )
            bm = BM25([tok(doc_text(p)) for p in papers])
            order = [p['no'] for p in papers]
            by_no = {p['no']: p for p in papers}

            async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
                async def ask(prompt: str, want_json: bool) -> Any:
                    await self.raise_if_stopped()

                    return await self._call_pool(client, pool, prompt, want_json)

                async def search(query: str, top_k: int, *, rerank: bool = True) -> tuple[list[dict], str]:
                    return await self._search(client, query, top_k, store, bm, order, by_no, rerank=rerank)

                def on_progress(stage: str, pct: int) -> None:
                    # 引擎是同步回调，用 nowait 版本，不阻塞生成协程
                    self.report_progress_nowait(pct, 100, stage, stage)

                result = await generate_background(
                    cur, self._topic, ask=ask, search=search,
                    current_year=datetime.now().year, on_progress=on_progress,
                    group_hint=self._group,
                    # 引证核验失败可降级，但「停止任务」也是从 ask 里抛出来的异常 ——
                    # 引擎不认识它，得由这里告诉它「这个不许吞」
                    fatal=(TaskStopped, asyncio.CancelledError),
                )
        finally:
            conn.close()

        await self.raise_if_stopped()
        result['model'] = self._model_label
        await self.report_progress(100, 100, 'done', '完成')

        blocked = sum(1 for s in result['slots'] if s['blocked'])
        await self.log.write_info(
            f'完成：生成 {len(result["slots"]) - blocked} 段、覆盖不足 {blocked} 段、'
            f'引文 {len(result["refs"])} 条、待复核 {len(result["verdicts"])} 处、'
            f'检索模式 {result["retrieveMode"]}'
        )

        return result

    # ================================================================== 模型池

    async def _call_pool(self, client: httpx.AsyncClient, pool: list, prompt: str, want_json: bool) -> Any:
        """
        顺序轮询 + 出错切换。**不做跨进程冻结** —— 这是几分钟一次的任务，
        一次生成只发 9 次请求，冻结表的维护成本高于收益（与 `ai_assist_service` 同口径）。

        **传输层错误先原地重试再换模型**（`_TRANSPORT_RETRY` 次，指数退避）。
        「换下一个」这套逻辑假设的是「这个模型不行」（欠费、限流、模型不存在），
        而 `RemoteProtocolError`（Server disconnected）说的是「这一次连接不行」——
        同一个端点隔几秒重发多半就过了。**踩过一次**：池里只有一个模型时，
        一次瞬时断连让一次已经跑到第 8 步、烧掉四分钟和八次调用的任务整个作废，
        而错误信息只有一句 `RemoteProtocolError`，看不出是「provider 抖了一下」。
        这条链路上同类错误在本项目已出现三次（灌库、OCR、这里）。
        """
        last = ''
        for m in pool:
            url = (m.base_url or 'https://api.openai.com/v1').strip().rstrip('/')
            if not url.endswith('/chat/completions'):
                url += '/v3/chat/completions' if url.endswith('/api') else '/chat/completions'
            body: dict[str, Any] = {
                'model': m.model_code, 'temperature': 0 if want_json else 0.2,
                'stream': False, 'messages': [{'role': 'user', 'content': prompt}],
                # 后台「支持推理」配成否就关思考，参数名按端点挑（见 utils/llm_thinking_util）
                **m.thinking_params,
            }
            raw = ''
            for attempt in range(_TRANSPORT_RETRY):
                await self.raise_if_stopped()
                try:
                    r = await client.post(url, json=body,
                                          headers={'Authorization': f'Bearer {m.api_key}',
                                                   'Content-Type': 'application/json'})
                    r.raise_for_status()
                    raw = (r.json()['choices'][0]['message']['content'] or '').strip()
                    break
                except _TRANSIENT as e:
                    last = f'{type(e).__name__}'
                    if attempt + 1 >= _TRANSPORT_RETRY:
                        await self.log.write_info(f'模型 {m.label} 连续 {_TRANSPORT_RETRY} 次连接失败({last})，切换下一个')
                        break
                    wait = _RETRY_BACKOFF * (attempt + 1)
                    await self.log.write_info(f'模型 {m.label} 连接失败({last})，{wait}s 后重试第 {attempt + 2} 次')
                    await asyncio.sleep(wait)
                except Exception as e:  # noqa: BLE001
                    # 不是传输问题（欠费、限流、模型不存在……）：重试同一个模型没有意义
                    last = f'{type(e).__name__}'
                    await self.log.write_info(f'模型 {m.label} 调用失败({last})，切换下一个')
                    break
            if not raw:
                last = last or '返回内容为空'
                continue
            self._model_label = m.label
            if not want_json:
                return raw

            return _parse_json(raw)

        raise RuntimeError(f'AI 调用失败，已尝试 {len(pool)} 个模型（最后一次：{last}）')

    # ================================================================== 检索

    async def _search(self, client: httpx.AsyncClient, query: str, top_k: int,
                      store: Any, bm: BM25, order: list[int], by_no: dict[int, dict],
                      *, rerank: bool = True) -> tuple[list[dict], str]:
        """
        检索。`rerank=False` 时只取向量候选、每篇带 `_score`，不调 rerank ——
        给第④步「整个类目池逐篇打分」用：那里的 top_k 是池的篇数（池空时是全库），
        整批送去 rerank 会撞 DashScope 单次 500 篇的上限，而且 rerank 不改 `_score`，
        对打分毫无贡献。槽位检索（top_k=12）照常重排。
        """
        from tools.lit_vector import embed_many, rerank_docs, rerank_text  # noqa: PLC0415

        if store.ready and self._conf.get('embed_url') and self._conf.get('embed_key'):
            vecs = await embed_many(client, [query], self._conf)
            if vecs:
                n = max(int(self._conf.get('rerank_n', 30)), top_k)
                cand = store.search(np.asarray(vecs[0], dtype=np.float32), n)
                papers = []
                for no, score in cand:
                    p = dict(by_no[no])
                    p['_score'] = score
                    papers.append(p)
                if not rerank:
                    return papers, 'vector'
                idx = await rerank_docs(client, query, [rerank_text(p) for p in papers], top_k, self._conf)
                if idx is not None:
                    head = [papers[i] for i in idx if 0 <= i < len(papers)]
                    seen = {p['no'] for p in head}

                    return head + [p for p in papers if p['no'] not in seen], 'vector+rerank'

                return papers, 'vector'

        raw = bm.score(tok(query))
        rank = [order[i] for i in np.argsort(-np.asarray(raw)) if raw[i] > 0]
        out = []
        for no in rank[:max(top_k, 30)]:
            p = dict(by_no[no])
            p['_score'] = rel(dict(zip(order, raw)).get(no, 0.0))
            out.append(p)

        return out, 'bm25'


_FENCE = re.compile(r'```(?:json)?\s*(.+?)\s*```', re.S)


def _parse_json(raw: str) -> Any:
    """容错解析：去围栏、截取第一个 { 或 [ 到最后一个 } 或 ]"""
    txt = _FENCE.search(raw).group(1) if _FENCE.search(raw) else raw
    starts = [i for i in (txt.find('{'), txt.find('[')) if i >= 0]
    if not starts:
        raise ValueError('模型没有返回 JSON')
    a = min(starts)
    b = max(txt.rfind('}'), txt.rfind(']'))
    if b <= a:
        raise ValueError('模型返回的 JSON 不完整')

    return json.loads(txt[a:b + 1])
