"""
文献检索向量的补算服务

被定时任务 `module_task.literature_task.refresh_stale_embeddings` 调用，
也可由 `tools/lit_reembed.py` 走命令行触发（那份不依赖后端环境，用于建库与批量重算）。

## 为什么是「标记过期 + 定时补算」而不是「保存时同步重算」

后台在「参考文献管理」页改了标题/摘要/病种标签之后，那条向量就过期了。两种做法：

- 保存时同步调 embed —— 改完立刻生效，但保存变慢，且 **embed 端点挂了保存就失败**
- 保存时只把 `embed_hash` 置空，由本服务补算 —— 保存永远快、永不失败，代价是有延迟窗口

选后者：这个库是低频更新的，一条文献晚几分钟进检索没有实际影响；而「因为一个外部
embedding 端点不通，导致管理员改不了文献」是明显更糟的失败模式。

## 过期的判据是 hash，不是时间戳

`embed_hash` 是送去 embed 那段文本的指纹。用时间戳判会漏掉「改了别的字段导致
update_time 变了但向量其实没过期」和「批量导入时 update_time 相同但内容不同」两种情况。
另外 `embed_model` 也要判：**不同模型的向量空间不可比**，换模型必须全量重算。

## 整批失败时不写任何东西

写半截会在库里留下「有向量但是错的」，比没有向量危险得多 —— 后者下次会被本服务
捞回来，前者不会，且表现只是「这几篇检索排位不对」，无从归因。
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config.env import RetrievalConfig
from module_action.entity.do.action_do import ActionLiterature
from utils.log_util import logger

#: 单次任务最多补算多少篇。防一次改动扫出几百篇时把任务跑成小时级，
#: 剩下的下一轮继续 —— 补算是幂等的，分几轮跑完与一轮跑完等价
MAX_PER_RUN = 200


def _arr(raw: Any) -> str:
    """
    JSON 文本列 → 斜杠分隔串。

    **刻意不复用 `LiteratureService._load_json`**：那样会让本模块在调用时才去 import
    `action_service`，而 `action-backend/common` 没有 `__init__.py`（是 PEP 420
    命名空间包）、`tools/common` 有（worker 框架的常规包）—— **常规包胜过命名空间包，
    与 sys.path 顺序无关**，所以只要进程里同时有 tools 目录在路径上，
    这个延迟 import 就会炸在 `No module named 'common.vo'`，而报错位置离原因很远。
    这几行重复的代价远小于那个坑。
    """
    if isinstance(raw, list):
        return '/'.join(str(x) for x in raw)
    if not raw:
        return ''
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return ''

    return '/'.join(str(x) for x in parsed) if isinstance(parsed, list) else ''


def build_embed_text(row: Any) -> str:
    """
    送去 embed 的文本。**必须与 `tools/lit_vector.embed_text` 逐字一致** ——
    两边算出的 hash 不同的话，命令行建的向量会被本服务判成过期、反复重算。

    不用全文：背景写作要从一篇文献拿的信息就是「研究了什么、发现了什么」，那就是摘要；
    全文进来会被方法学套话（伦理审批号、统计软件、纳排标准）稀释掉主题信号。
    """
    arr = _arr

    return '。'.join(x for x in [
        row.title or '',
        arr(row.condition), arr(row.condition_group), arr(row.intervention), arr(row.outcomes),
        (row.abstract or '')[:1200],
        row.finding_summary or '',
    ] if x)[:4000]


class LiteratureEmbedService:
    """文献向量补算"""

    @classmethod
    def _hash(cls, text: str) -> str:
        import hashlib  # noqa: PLC0415

        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:32]

    @classmethod
    def _to_bytes(cls, vec: list[float]) -> bytes:
        """L2 归一化后存 float32 原始字节。归一化放写入侧，检索时点积即余弦"""
        import numpy as np  # noqa: PLC0415

        v = np.asarray(vec, dtype=np.float32)

        return (v / (float(np.linalg.norm(v)) + 1e-9)).tobytes()

    @classmethod
    async def _embed(cls, client: httpx.AsyncClient, texts: list[str]) -> list[list[float]]:
        """一批文本 → 向量。整批失败返回空列表"""
        url = RetrievalConfig.embed_base_url.rstrip('/') + '/embeddings'
        for attempt in (1, 2, 3):
            try:
                r = await client.post(
                    url,
                    headers={'Authorization': f'Bearer {RetrievalConfig.embed_api_key}'},
                    json={'model': RetrievalConfig.embed_model, 'input': texts},
                )
                r.raise_for_status()
                data = sorted(r.json()['data'], key=lambda d: d['index'])

                return [d['embedding'] for d in data]
            except Exception as e:  # noqa: BLE001
                if attempt == 3:
                    logger.warning(f'文献向量补算失败：{type(e).__name__}: {e}')

                    return []
                await asyncio.sleep(3 * attempt)

        return []

    @classmethod
    async def refresh_stale_services(cls, query_db: AsyncSession, limit: int = MAX_PER_RUN) -> dict[str, int]:
        """
        补算缺失或过期的向量

        :param query_db: orm对象
        :param limit: 本次最多补算多少篇
        :return: {'scanned', 'updated', 'failed'}
        """
        if not RetrievalConfig.embed_enabled:
            logger.info('未启用向量检索（EMBED_ENABLED=false），跳过文献向量补算')

            return {'scanned': 0, 'updated': 0, 'failed': 0}
        if not (RetrievalConfig.embed_base_url and RetrievalConfig.embed_api_key):
            logger.warning('已启用向量检索但未配置 EMBED_BASE_URL / EMBED_API_KEY，跳过补算')

            return {'scanned': 0, 'updated': 0, 'failed': 0}

        rows = (
            (
                await query_db.execute(
                    select(ActionLiterature)
                    .where(
                        ActionLiterature.del_flag == '0',
                        ActionLiterature.status == '0',
                        ActionLiterature.extract_status == 'ok',
                    )
                    .order_by(ActionLiterature.corpus_no)
                )
            )
            .scalars()
            .all()
        )
        # **跨 commit 只传普通值，不传 ORM 对象**。会话是 expire_on_commit=True，
        # 第一批 commit 之后 `rows` 里剩下的对象全部失效，下一批再读 `row.title`
        # 就会触发懒加载 —— 在 async 会话里直接抛 MissingGreenlet。
        # 表现是「补算跑到第二批必炸」，而第一批已经落库、看着像成功了一半。踩过一次。
        todo: list[tuple[int, str, str]] = []  # (lit_id, embed 输入文本, 目标 hash)
        for row in rows:
            text = build_embed_text(row)
            want = cls._hash(text)
            if (
                row.embedding is None
                or (row.embed_hash or '') != want
                or (row.embed_model or '') != RetrievalConfig.embed_model
            ):
                todo.append((row.lit_id, text, want))
            if len(todo) >= limit:
                break
        scanned = len(rows)
        if not todo:
            logger.info('文献向量均为最新，无需补算')

            return {'scanned': scanned, 'updated': 0, 'failed': 0}

        updated = failed = 0
        batch = max(1, RetrievalConfig.embed_batch)
        async with httpx.AsyncClient(timeout=RetrievalConfig.embed_timeout_seconds) as client:
            for i in range(0, len(todo), batch):
                part = todo[i : i + batch]
                vecs = await cls._embed(client, [text for _, text, _ in part])
                if len(vecs) != len(part):
                    # 整批失败：什么都不写。写半截会留下「有向量但是错的」
                    failed += len(part)
                    continue
                now = datetime.now()
                for (lit_id, _text, want), vec in zip(part, vecs):
                    await query_db.execute(
                        update(ActionLiterature)
                        .where(ActionLiterature.lit_id == lit_id)
                        .values(
                            embedding=cls._to_bytes(vec),
                            embed_model=RetrievalConfig.embed_model,
                            embed_dim=len(vec),
                            embed_hash=want,
                            embed_time=now,
                        )
                    )
                await query_db.commit()
                updated += len(part)

        logger.info(f'文献向量补算完成：扫描{scanned}篇，更新{updated}篇，失败{failed}篇')

        return {'scanned': scanned, 'updated': updated, 'failed': failed}
