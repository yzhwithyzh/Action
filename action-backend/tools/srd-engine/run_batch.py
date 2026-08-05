"""批量跑「系统综述」目录里的 A/B 配对，输出每对的完整结果 JSON + 一份汇总 JSON。

用法（先导出 SRD_* 环境变量）：
    python run_batch.py                 # 跑全部配对，已有结果的跳过
    python run_batch.py 1 2 3           # 只跑指定编号
    python run_batch.py --force         # 重跑并覆盖
    python run_batch.py --out out-terra --cache .srd-cache-terra   # 换模型时另存一份
    python run_batch.py --from-db       # 模型改从 ai_models 表取（与 worker 同源，见下）
    python run_batch.py --granularity per_group --timeout 600    # 判定拆细 + 放宽单次调用超时

`--from-db` 会走 `tools/common/model_registry.py`，也就是 worker 用的那条路：
从 `ai_models` 表取启用中的模型池（api_key 已解密），按 `model_sort` 排好交给引擎
「粘性 + 出错切换」地轮换。好处是密钥不必落到 shell 历史或环境变量里，
坏处是这条路要连得上后端数据库 —— 连不上就老老实实用 SRD_* 环境变量。

抽取结果按 sha256 缓存在 --cache 目录，目录里有重复文献时只抽一次。
换模型请同时换 --out 与 --cache，避免与既有结果混在一起
（缓存 key 虽含模型名不会串味，但换目录更便于两份结果对照）。

本脚本只负责「发现配对 → 调引擎 → 汇总落盘」，评估逻辑一律走 pipeline.assess，
不重写任何引擎内部实现。
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from pathlib import Path

from srd_engine.adapters.langchain_client import LlmRunner
from srd_engine.config import EngineConfig, FailoverConfig, ModelConfig, model_config_from_env
from srd_engine.pipeline import ProgressFn, assess
from srd_engine.report import to_csv
from srd_engine.schemas import AssessmentResult

ROOT = Path(__file__).parent
PDF_DIR = ROOT / '系统综述'
OUT_DIR = ROOT / 'out'
CACHE_DIR = ROOT / '.srd-cache'
#: `--from-db` 要 import 后端那套（tools.common / config.database / module_ai）
BACKEND_ROOT = ROOT.parent.parent

LEVEL_ZH = {'none': '无重复', 'low': '低度重复', 'mod': '中度重复', 'high': '高度重复'}

#: 本次用的模型池。空列表表示走 SRD_* 环境变量的单模型路径。
MODEL_POOL: list[ModelConfig] = []
#: 出错模型的冻结时长（秒）。单模型池上调小，见 assess_pair 的 docstring。
FREEZE_SECONDS = FailoverConfig.freeze_seconds


def load_pool_from_db(timeout: float) -> list[ModelConfig]:
    """从 `ai_models` 表取模型池 —— 与 worker 完全同一条路径，不另写一套解密逻辑。"""
    sys.path.insert(0, str(BACKEND_ROOT))
    from tools.common.model_registry import load_llm_models  # noqa: PLC0415 —— 只有 --from-db 才需要

    models = asyncio.run(load_llm_models())
    if not models:
        raise RuntimeError('ai_models 表里没有启用中且配了 API key 的模型')
    return [
        ModelConfig(
            provider=m.provider, model=m.model_code, api_key=m.api_key, base_url=m.base_url,
            temperature=float(m.temperature) if m.temperature is not None else 0.0,
            max_tokens=m.max_tokens, ref=m.ref, timeout=timeout,
        )
        for m in models
    ]


def model_pool() -> list[ModelConfig] | ModelConfig:
    return MODEL_POOL or model_config_from_env()


def clean_title(path: Path) -> str:
    """1A.Acupuncture for ... - 副本.pdf → Acupuncture for ..."""
    name = re.sub(r'^\d+[AB]\.(b\.)?', '', path.stem)
    return re.sub(r'\s*-\s*副本$', '', name).strip()


def discover_pairs() -> list[tuple[int, Path, Path]]:
    by_no: dict[int, dict[str, Path]] = {}
    for f in PDF_DIR.iterdir():
        m = re.match(r'^(\d+)([AB])\.', f.name)
        if m and f.suffix.lower() == '.pdf':
            by_no.setdefault(int(m.group(1)), {})[m.group(2)] = f
    return [(no, by_no[no]['A'], by_no[no]['B']) for no in sorted(by_no) if 'A' in by_no[no] and 'B' in by_no[no]]


async def assess_pair(
    a: Path, b: Path, model_cfg: ModelConfig | list[ModelConfig], cfg: EngineConfig,
    progress: ProgressFn,
) -> AssessmentResult:
    """直接用引擎的公开入口，不再重写编排逻辑。

    这里曾经自带一套「批次失败重试」，是为早期某个会静默返空对象的模型加的；
    抽取降到 4 次调用、且 extract_doc 自己会把失败批次记进 warnings 之后，
    那 53 行重复实现（以及对 `_BATCH_SCHEMA` / `_batch_text` 两个私有符号的依赖）
    已无必要，改回调用 `pipeline.assess`。

    唯一自己造 runner 的理由是 `FailoverConfig`：默认冻结 300s 是给「多模型池」设计的
    （冻一个换一个，不耽误事），池里只有一个模型时它变成纯粹的空等 —— 一次网络抖动
    罚站 5 分钟，10 对配对能白等一小时。`--freeze` 就是为这种单模型场景准备的。
    """
    runner = LlmRunner(
        model_cfg, max_concurrency=cfg.max_concurrency,
        failover=FailoverConfig(freeze_seconds=FREEZE_SECONDS),
    )
    return await assess(a, b, cfg=cfg, runner=runner, cache_dir=CACHE_DIR,
                        title_a=clean_title(a), title_b=clean_title(b), on_progress=progress)


# --------------------------------------------------------------------------- 汇总与入口


def summarize(no: int, a: Path, b: Path, r: AssessmentResult, seconds: float) -> dict:
    return {
        'pair': no,
        'file_a': a.name,
        'file_b': b.name,
        'title_a': r.review_a_title,
        'title_b': r.review_b_title,
        'same_file': r.doc_a_sha256 == r.doc_b_sha256,
        'overall_level': r.overall_level,
        'overall_level_zh': LEVEL_ZH.get(r.overall_level or '', ''),
        'overall_pct': r.overall_pct,
        'overall_score': f'{r.overall_score_sum}/{r.overall_score_max}',
        'overall_score_max_full': r.overall_score_max_full,
        'overall_reason_zh': r.overall_reason_zh,
        'provisional': r.provisional,
        'domains': [
            {
                'seq': d.seq, 'name_zh': d.name_zh, 'is_key': d.is_key,
                'level': d.level, 'pct': d.pct,
                'score_sum': d.score_sum, 'score_max': d.score_max, 'score_max_full': d.score_max_full,
                'unclear': d.unclear_count,
                'evidence_sufficient': d.evidence_sufficient, 'near_boundary': d.near_boundary,
            }
            for d in r.domains
        ],
        'ratings': {it.code: it.effective_rating for it in r.items},
        'unclear_count': r.unclear_count,
        'review_count': r.review_count,
        'llm_calls': r.llm_calls,
        'token_in': r.token_in,
        'token_out': r.token_out,
        'seconds': round(seconds, 1),
        'errors': r.errors,
    }


def run_one(no: int, a: Path, b: Path, cfg: EngineConfig, force: bool) -> dict:
    out_json = OUT_DIR / f'pair-{no:02d}.json'
    if out_json.exists() and not force:
        r = AssessmentResult.model_validate_json(out_json.read_text(encoding='utf-8'))
        print(f'== 配对 {no}：已有结果，跳过', file=sys.stderr)
        return summarize(no, a, b, r, 0.0)

    def progress(stage: str, done: int, total: int, detail: str) -> None:
        if stage != 'judge' or done % 10 == 0 or done == total:
            print(f'  [{no}][{stage}] {done}/{total} {detail}', file=sys.stderr, flush=True)

    print(f'== 配对 {no}：{a.name}  vs  {b.name}', file=sys.stderr, flush=True)
    t0 = time.monotonic()
    result = asyncio.run(assess_pair(a, b, model_pool(), cfg, progress))
    seconds = time.monotonic() - t0

    out_json.write_text(result.model_dump_json(indent=2), encoding='utf-8')
    (OUT_DIR / f'pair-{no:02d}.csv').write_text(to_csv(result), encoding='utf-8-sig')
    s = summarize(no, a, b, result, seconds)
    print(f'   → {s["overall_level"]} 得分 {s["overall_score"]} 重复度 {s["overall_pct"]}%  '
          f'用时 {s["seconds"]}s  调用 {s["llm_calls"]}', file=sys.stderr, flush=True)
    return s


def _opt(argv: list[str], name: str, default: Path) -> Path:
    return ROOT / argv[argv.index(name) + 1] if name in argv else default


def _val(argv: list[str], name: str, default: str) -> str:
    return argv[argv.index(name) + 1] if name in argv else default


def main(argv: list[str]) -> int:
    global OUT_DIR, CACHE_DIR, MODEL_POOL, FREEZE_SECONDS  # noqa: PLW0603 —— 供 assess_pair/run_one 直接读

    force = '--force' in argv
    OUT_DIR = _opt(argv, '--out', OUT_DIR)
    CACHE_DIR = _opt(argv, '--cache', CACHE_DIR)
    granularity = _val(argv, '--granularity', EngineConfig.judge_granularity)
    FREEZE_SECONDS = float(_val(argv, '--freeze', str(FailoverConfig.freeze_seconds)))
    concurrency = int(_val(argv, '--concurrency', '8'))
    timeout = float(_val(argv, '--timeout', '180'))
    opts = ('--out', '--cache', '--granularity', '--concurrency', '--timeout', '--freeze')
    flag_values = {argv[argv.index(f) + 1] for f in opts if f in argv}
    wanted = {int(x) for x in argv if x.isdigit() and x not in flag_values}
    OUT_DIR.mkdir(exist_ok=True)
    CACHE_DIR.mkdir(exist_ok=True)

    if '--from-db' in argv:
        MODEL_POOL = load_pool_from_db(timeout)
        print(f'模型池（来自 ai_models，共 {len(MODEL_POOL)} 个）：'
              f'{"、".join(c.label for c in MODEL_POOL)}', file=sys.stderr)

    cfg = EngineConfig(judge_granularity=granularity, max_concurrency=concurrency)
    pairs = [p for p in discover_pairs() if not wanted or p[0] in wanted]
    print(f'共 {len(pairs)} 对待评估', file=sys.stderr)

    summaries, failures = [], []
    for no, a, b in pairs:
        try:
            summaries.append(run_one(no, a, b, cfg, force))
        except Exception as exc:  # noqa: PERF203 —— 单对失败不影响其余，必须逐对兜
            print(f'!! 配对 {no} 失败：{type(exc).__name__}: {exc}', file=sys.stderr)
            failures.append({'pair': no, 'file_a': a.name, 'file_b': b.name,
                             'error': f'{type(exc).__name__}: {exc}'})

    pool = model_pool()
    summary = {
        'source_dir': str(PDF_DIR),
        'model': pool[0].model if isinstance(pool, list) else pool.model,
        'model_pool': [c.label for c in pool] if isinstance(pool, list) else [pool.label],
        'engine_config': {
            'extract_scope': cfg.extract_scope, 'granularity': cfg.judge_granularity,
            'max_concurrency': cfg.max_concurrency, 'timeout': timeout, 'freeze_seconds': FREEZE_SECONDS,
        },
        'pair_count': len(summaries),
        'pairs': summaries,
        'failures': failures,
        'token_in_total': sum(s['token_in'] for s in summaries),
        'token_out_total': sum(s['token_out'] for s in summaries),
    }
    (OUT_DIR / 'summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(f'\n汇总已写出 {OUT_DIR / "summary.json"}', file=sys.stderr)
    for s in summaries:
        print(f'  配对 {s["pair"]:>2}  {s["overall_level"] or "-":<5} 得分 {s["overall_score"]:>7}  '
              f'{s["overall_pct"]:>3}%  unclear={s["unclear_count"]:>2}  {s["file_a"][:40]}',
              file=sys.stderr)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
