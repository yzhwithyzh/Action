"""P0→P3 编排.

    result = await assess('a.pdf', 'b.pdf', model_cfg, EngineConfig())

进度用 on_progress 回调往外抛（后端接入时把它接到 SSE 即可，引擎本身不认识 HTTP）。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from srd_engine import cache
from srd_engine import pdf as pdf_util
from srd_engine.adapters.langchain_client import LlmRunner
from srd_engine.aggregate import aggregate, build_skeleton
from srd_engine.checklist import ALL_ITEMS, DOMAINS
from srd_engine.config import CRITERIA_VERSION, ENGINE_VERSION, PROMPT_VERSION, EngineConfig, ModelConfig
from srd_engine.extract import extract_doc
from srd_engine.judge import judge_batch

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from srd_engine.schemas import AssessmentResult, ExtractDoc, ItemResult, ParsedDoc

ProgressFn = Callable[[str, int, int, str], None]

# 标题行的合理长度区间
TITLE_MIN_LEN, TITLE_MAX_LEN = 20, 300


def _noop(stage: str, done: int, total: int, detail: str) -> None:
    return None


def guess_title(doc: ParsedDoc) -> str:
    """取首页前几行里最像标题的一行（够用即可，真实标题以调用方传入为准）。"""
    if not doc.pages:
        return ''
    for line in doc.pages[0].text.splitlines()[:25]:
        s = re.sub(r'\s+', ' ', line).strip()
        if TITLE_MIN_LEN <= len(s) <= TITLE_MAX_LEN and not re.match(
            r'^(doi|https?://|received|accepted|©)', s, re.I
        ):
            return s
    return ''


async def prepare_extract(
    runner: LlmRunner,
    doc: ParsedDoc,
    title: str,
    cfg: EngineConfig,
    cache_dir: str | Path | None,
    on_progress: ProgressFn,
    label: str,
) -> tuple[ExtractDoc, list[str]]:
    variant = cache.cache_variant(cfg.extract_scope)
    if cache_dir:
        cached = cache.load(cache_dir, doc, runner.cfg.model, variant)
        if cached is not None:
            on_progress('extract', 1, 1, f'{label} 命中抽取缓存')
            # 把缓存里存的告警一并带出来，保证二次运行的审计痕迹与首次一致（评审 P7）
            return cached, [f'（来自缓存）{n}' for n in cached.notes]

    on_progress('extract', 0, 1, f'{label} 开始抽取')
    extract, warnings = await extract_doc(runner, doc, title=title, cfg=cfg)
    if cache_dir:
        cache.save(cache_dir, doc, runner.cfg.model, extract, variant)
    on_progress('extract', 1, 1, f'{label} 抽取完成')
    return extract, warnings


async def judge_all(
    runner: LlmRunner,
    ea: ExtractDoc,
    eb: ExtractDoc,
    cfg: EngineConfig,
    on_progress: ProgressFn,
) -> list[ItemResult]:
    if cfg.judge_granularity == 'all':
        # 34 条目一次调用。输入约 1.4 万 token 没问题，风险全在输出侧：
        # 实测每条目平均输出约 500 token，34 条约 1.7 万，超过多数模型的单次输出上限。
        # 模型截断时 GroupVerdicts 会少返条目，由 judge_batch 补成 unclear + needs_review。
        results = await judge_batch(runner, ALL_ITEMS, ea, eb, cfg)
        on_progress('judge', len(results), len(ALL_ITEMS), '一次全给')
        return results

    if cfg.judge_granularity == 'per_group':
        groups = [g for d in DOMAINS for g in d.groups]
        done = 0
        batches = await runner.gather([judge_batch(runner, list(g.items), ea, eb, cfg) for g in groups])
        results: list[ItemResult] = []
        for batch in batches:
            results.extend(batch)
            done += len(batch)
            on_progress('judge', done, len(ALL_ITEMS), '')
        return results

    # per_item：每条一次调用，同样走 judge_batch（只是每次只给一条），不再有独立实现
    total = len(ALL_ITEMS)
    batches = await runner.gather([judge_batch(runner, [it], ea, eb, cfg) for it in ALL_ITEMS])
    results = [r for batch in batches for r in batch]
    for finished, result in enumerate(results, start=1):
        on_progress('judge', finished, total, result.code)
    return results


async def assess_from_extracts(
    runner: LlmRunner,
    ea: ExtractDoc,
    eb: ExtractDoc,
    cfg: EngineConfig | None = None,
    doc_a: ParsedDoc | None = None,
    doc_b: ParsedDoc | None = None,
    on_progress: ProgressFn | None = None,
) -> AssessmentResult:
    """已有两篇 facet 时直接判定（跳过解析与抽取）—— 供批量评测与缓存命中场景使用。"""
    cfg = cfg or EngineConfig()
    on_progress = on_progress or _noop

    items = await judge_all(runner, ea, eb, cfg, on_progress)

    result = build_skeleton({it.code: it for it in items})
    result.review_a_title = ea.title
    result.review_b_title = eb.title
    result.doc_a_sha256 = ea.sha256
    result.doc_b_sha256 = eb.sha256
    result.engine_version = ENGINE_VERSION
    result.prompt_version = PROMPT_VERSION
    result.criteria_version = CRITERIA_VERSION
    result.model = runner.cfg.model
    result.judge_granularity = cfg.judge_granularity
    result.token_in, result.token_out, result.llm_calls = runner.token_in, runner.token_out, runner.calls

    aggregate(result, cfg)
    on_progress('done', 1, 1, result.overall_level or '')
    return result


async def assess(
    path_a: str | Path,
    path_b: str | Path,
    model_cfg: ModelConfig | Sequence[ModelConfig] | None = None,
    cfg: EngineConfig | None = None,
    cache_dir: str | Path | None = None,
    title_a: str = '',
    title_b: str = '',
    on_progress: ProgressFn | None = None,
    runner: LlmRunner | None = None,
) -> AssessmentResult:
    """完整流程：解析 → 抽取 → 判定 → 聚合。

    `model_cfg` 给一个就是单模型，给一组就是模型池（撞限流/欠费时自动切换，见 LlmRunner）。
    调用方需要接管冻结状态存储、切换通知这些外部依赖时，自己造好 `runner` 传进来 ——
    worker 就是这么把 Redis 共享健康表接上的，引擎本身不认识 Redis。
    """
    cfg = cfg or EngineConfig()
    on_progress = on_progress or _noop
    if runner is None:
        if model_cfg is None:
            raise ValueError('model_cfg 与 runner 至少给一个')
        runner = LlmRunner(model_cfg, max_concurrency=cfg.max_concurrency)

    on_progress('parse', 0, 2, str(path_a))
    doc_a = pdf_util.parse(path_a)
    on_progress('parse', 1, 2, str(path_b))
    doc_b = pdf_util.parse(path_b)
    on_progress('parse', 2, 2, '')

    (ea, warn_a), (eb, warn_b) = await runner.gather(
        [
            prepare_extract(runner, doc_a, title_a or guess_title(doc_a), cfg, cache_dir, on_progress, '综述A'),
            prepare_extract(runner, doc_b, title_b or guess_title(doc_b), cfg, cache_dir, on_progress, '综述B'),
        ]
    )

    result = await assess_from_extracts(runner, ea, eb, cfg, doc_a, doc_b, on_progress)
    result.errors.extend(f'A: {w}' for w in warn_a)
    result.errors.extend(f'B: {w}' for w in warn_b)
    # 中途换过模型必须留痕：`result.model` 只记得最后在用的那个，光看它无法解释结论
    result.errors.extend(
        f'模型切换：{sw["from"]} → {sw["to"] or "无候选"}（{sw["reason"]}）' for sw in runner.switches
    )
    return result
