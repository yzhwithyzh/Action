"""
向量补算：给 `action_literature` 里缺向量或向量过期的行算 embedding 并落库

跑法（工作目录 action-backend/）::

    set EMBED_BASE_URL=... & set EMBED_KEY=... & set EMBED_MODEL=qwen3.7-text-embedding
    python -m tools.lit_reembed              # 只补缺失/过期的
    python -m tools.lit_reembed --all        # 全量重算（换了模型时用）
    python -m tools.lit_reembed --check      # 只体检，不调用模型

## 什么叫「过期」

`embed_hash` 是送去 embed 的那段文本（标题 + 病种 + 干预 + 结局 + 摘要 + 结论）的指纹。
后台在「参考文献管理」页改了其中任何一项，hash 就对不上了 —— 而**过期的表现是
「这篇检索排位莫名其妙」，没有任何报错**。所以补算不是可选的收尾工作，
是后台改完数据之后必须跑的一步。

## 换模型必须 `--all`

不同模型的向量空间不可比，混着用会得到毫无意义的相似度。`VectorStore` 在加载时
会检查维度一致性并整个拒绝使用混合向量，但**同维度不同模型是检查不出来的**
（比如两个都是 1024 维），所以这里按 `embed_model` 也判一次过期。
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from collections import Counter
from datetime import datetime

import httpx
import psycopg2
from psycopg2.extras import execute_batch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# tools 目录放在 sys.path 末尾。注意：**这解决不了 `common` 的遮蔽**——
# `action-backend/common` 无 __init__.py（PEP 420 命名空间包），`tools/common` 有
# （worker 框架的常规包），而**常规包胜过命名空间包、与路径顺序无关**。
# 所以后端服务不能在 tools 在路径上时做延迟 import，见
# module_action/service/literature_embed_service._arr 上的注释。
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from lit_agent import load_corpus  # noqa: E402
from lit_vector import cfg, embed_text, embed_many, text_hash, to_bytes  # noqa: E402

DB = dict(host='127.0.0.1', port=5432, user='postgres', password='123456', dbname='action')


def load_with_embed(cur) -> list[dict]:
    """在 load_corpus 的基础上补上向量相关列"""
    papers = load_corpus(cur)
    cur.execute('select corpus_no, embed_model, embed_hash, embed_dim, '
                '(embedding is not null) as has_vec from action_literature')
    meta = {r[0]: r for r in cur.fetchall()}
    for p in papers:
        m = meta.get(p['no'])
        p['embed_model'], p['embed_hash'] = (m[1] or '', m[2] or '') if m else ('', '')
        p['embed_dim'], p['has_vec'] = (m[3], m[4]) if m else (None, False)
    return papers


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--all', action='store_true', help='全量重算（换模型时用）')
    ap.add_argument('--check', action='store_true', help='只体检')
    args = ap.parse_args()

    conf = cfg()
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    papers = load_with_embed(cur)

    stale, missing, ok = [], [], 0
    for p in papers:
        want = text_hash(embed_text(p))
        p['_want'] = want
        if not p['has_vec']:
            missing.append(p)
        elif args.all or p['embed_hash'] != want or p['embed_model'] != conf['embed_model']:
            stale.append(p)
        else:
            ok += 1

    print(f'语料 {len(papers)} 篇 · 向量最新 {ok} · 缺失 {len(missing)} · 过期 {len(stale)}')
    if stale and not args.all:
        why = Counter('换了模型' if p['embed_model'] != conf['embed_model'] else '文本已改' for p in stale)
        print('  过期原因:', dict(why))
        print('  例:', [p['no'] for p in stale[:12]])
    models = Counter(p['embed_model'] for p in papers if p['has_vec'])
    if models:
        print('  库内向量模型分布:', dict(models))
    if args.check:
        cur.close()
        conn.close()
        return

    todo = missing + stale
    if not todo:
        print('无需补算')
        cur.close()
        conn.close()
        return
    if not conf['embed_url'] or not conf['embed_key']:
        raise SystemExit('未配置 EMBED_BASE_URL / EMBED_KEY')

    print(f'\n补算 {len(todo)} 篇（{conf["embed_model"]} @ {conf["embed_url"]}，批 {conf["embed_batch"]}）')
    t0, done, failed = time.time(), 0, []
    B = conf['embed_batch']
    async with httpx.AsyncClient(timeout=180) as client:
        for i in range(0, len(todo), B):
            part = todo[i:i + B]
            vecs = await embed_many(client, [embed_text(p) for p in part], conf)
            if len(vecs) != len(part):
                # 整批失败：**不写任何东西**。写半截会留下「有向量但是错的」，
                # 比没有向量危险得多 —— 后者下次会被补算捞回来，前者不会
                failed += [p['no'] for p in part]
                print(f'  ✗ 第 {i // B + 1} 批（{len(part)} 篇）失败，跳过：{[p["no"] for p in part]}')
                continue
            rows = [(psycopg2.Binary(to_bytes(v)), conf['embed_model'], len(v),
                     p['_want'], datetime.now(), p['no'])
                    for p, v in zip(part, vecs)]
            execute_batch(cur, 'update action_literature set embedding=%s, embed_model=%s, '
                               'embed_dim=%s, embed_hash=%s, embed_time=%s where corpus_no=%s', rows)
            conn.commit()
            done += len(part)
            el = time.time() - t0
            print(f'  [{done + len(failed)}/{len(todo)}] 已落库 {done} · 用时 {el / 60:.1f}min '
                  f'· 预计剩余 {el / max(done, 1) * (len(todo) - done) / 60:.1f}min', flush=True)

    cur.execute("select count(*), count(embedding), count(distinct embed_model) filter (where embedding is not null),"
                ' min(embed_dim), max(embed_dim) from action_literature')
    total, has, nmodel, dmin, dmax = cur.fetchone()
    print(f'\n完成：补算 {done} · 失败 {len(failed)} · 耗时 {(time.time() - t0) / 60:.1f} 分钟')
    print(f'库内 {total} 篇 · 有向量 {has} · 模型种类 {nmodel} · 维度 {dmin}~{dmax}')
    if failed:
        print(f'  失败编号（重跑本命令即可补上）：{failed}')
    if nmodel and nmodel > 1:
        print('  ⚠ 库内存在多个 embedding 模型算的向量，相似度不可比，请跑 --all 全量重算')
    cur.close()
    conn.close()


if __name__ == '__main__':
    asyncio.run(main())
