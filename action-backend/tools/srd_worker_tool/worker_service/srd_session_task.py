"""SRD 评估任务 —— 把「两篇系统综述的重复性评估」包成一个 worker 任务。

职责边界（很重要，别越界）：
- **引擎**（tools/srd-engine）只管算法：解析 → 抽取 → 评分 → 聚合，不认识 Redis / HTTP / 队列。
- **本文件**只管把任务跑起来：拿文件、给进度、写结果、处理停止，算法一行不重写。
  —— 所以「条目 0–3 分」这套评分口径也在引擎里（`srd_engine/prompts.py` + `aggregate.py`），
  本文件只负责把分数原样搬进任务摘要。

任务 payload（后端 rpush 进队列的 JSON）::

    {
      "session_id": "uuid",                       必填
      "user_id": 1,
      "review_a": {"url": "https://.../a.pdf", "title": "综述A标题"},
      "review_b": {"path": "E:/data/b.pdf"},      url 与 path 二选一
      "engine": {"extract_scope": "full", "judge_granularity": "all", "max_concurrency": 8},
      "model_ids": [3, 7],                        可选：只用这几个 ai_models 里的模型
      "model":  {"temperature": 0.2, "max_tokens": 8192},   可选覆盖，见下
      "options": {"force": false}                 force=true 时忽略断点重跑
    }

`review_a/b` 也接受直接给字符串（URL 或本地路径），或用 `"files": [a, b]` 简写。

模型从哪来（优先级从高到低）：

1. `payload.model` 里**带 api_key** —— 当成一次性的临时模型，直接用，不查库也不轮换；
2. `ai_models` 表里启用中的模型（可用 `payload.model_ids` 缩小范围）——
   按 `model_sort` 排成一个池子交给引擎「粘性 + 出错切换」地轮换，撞到限流/欠费就冻 5 分钟换下一个；
3. 环境变量 `SRD_PROVIDER / SRD_MODEL / SRD_API_KEY / SRD_BASE_URL` —— 库里一个都没有时的兜底。

`payload.model` 里不带 api_key 时，其中的 temperature / max_tokens / timeout 会作为覆盖
套到池子里**每一个**模型上（用来临时调参，不改数据库）。
"""

from __future__ import annotations

import asyncio
import re
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from tools.common.base_session_task import BaseSessionTask, TaskPayloadError
from tools.common.checkpoint_json_manager import safe_name
from tools.common.model_registry import load_llm_models
from tools.srd_worker_tool.config.worker_config import (
    EXTRACT_CACHE_DIR,
    RESULT_DIR,
    ensure_engine_importable,
)

ensure_engine_importable()

from srd_engine.adapters.langchain_client import LlmRunner  # noqa: E402
from srd_engine.config import (  # noqa: E402 —— 必须先把引擎目录塞进 sys.path
    CRITERIA_VERSION,
    ENGINE_VERSION,
    PROMPT_VERSION,
    EngineConfig,
    FailoverConfig,
    ModelConfig,
    model_config_from_env,
)
from srd_engine.pipeline import assess  # noqa: E402
from srd_engine.report import render_text, to_csv  # noqa: E402
from srd_engine.schemas import AssessmentResult  # noqa: E402

LEVEL_ZH = {'none': '无重复', 'low': '低度重复', 'mod': '中度重复', 'high': '高度重复'}

# 各阶段占总进度的区间。抽取 4 次调用、判定几十次，判定理应占大头。
STAGE_RANGE = {'parse': (0, 5), 'extract': (5, 40), 'judge': (40, 95), 'done': (95, 100)}

# 下载单个文件的上限，防止一条脏 URL 把磁盘塞满
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024
DOWNLOAD_TIMEOUT = 120.0

# 断点文件名（存在 checkpoint/{session_id}/ 下）
CHECKPOINT_RESULT = 'result'


class SrdSessionTask(BaseSessionTask):
    """一次 A/B 配对评估。"""

    task_type = 'srd_assessment'

    def __init__(self, payload: dict[str, Any], *, model_health: Any = None, **kwargs: Any) -> None:
        super().__init__(payload, **kwargs)
        # 两篇综述的输入描述，validate() 里归一后填上
        self._spec_a: dict[str, Any] = {}
        self._spec_b: dict[str, Any] = {}
        #: 共享的模型冻结表（worker 传 Redis 实现）。为 None 时引擎退化成进程内存。
        self._model_health = model_health
        #: 本次用的模型池与实际调用它们的 runner，收尾时写进摘要
        self._pool: list[ModelConfig] = []
        self._pool_source = ''  # payload / db / env
        self._runner: LlmRunner | None = None

    # ================================================================== 校验

    def validate(self) -> None:
        self._spec_a = self._read_spec('review_a', 0)
        self._spec_b = self._read_spec('review_b', 1)

    def task_meta(self) -> dict[str, Any]:
        return {
            **super().task_meta(),
            'title_a': self._spec_a.get('title', ''),
            'title_b': self._spec_b.get('title', ''),
            'engine_version': ENGINE_VERSION,
        }

    # ================================================================== 主流程

    async def process(self) -> dict[str, Any]:
        cached = self._load_checkpoint()
        if cached is not None:
            await self.log.write_info('✓ 命中断点：结果版本与当前引擎一致，直接复用')
            return await self._finalize(AssessmentResult.model_validate(cached), from_checkpoint=True)

        # 模型池放在下载之前解析：没模型这活儿根本干不了，早失败省一次下载
        await self.log.write_info('【1/4】准备模型池')
        self._pool = await self._resolve_pool()

        await self.log.write_info('【2/4】准备输入文件')
        path_a, path_b = await self._prepare_inputs()
        await self.raise_if_stopped()

        await self.log.write_info('【3/4】评估中（解析 → 抽取 → 判定 → 聚合）')
        result = await self._assess(path_a, path_b)
        await self.raise_if_stopped()

        await self.log.write_info('【4/4】写出结果')
        self.checkpoint.save(CHECKPOINT_RESULT, result.model_dump(mode='json'))
        return await self._finalize(result, from_checkpoint=False)

    # ================================================================== 输入

    def _read_spec(self, key: str, index: int) -> dict[str, Any]:
        """把三种写法（对象 / 字符串 / files 数组）归一成 {url|path, title}。"""
        spec = self.payload.get(key)
        if spec is None:
            files = self.payload.get('files') or []
            spec = files[index] if len(files) > index else None
        if spec is None:
            raise TaskPayloadError(f'缺少 {key}（也没有 files[{index}]）')
        if isinstance(spec, str):
            spec = {'url': spec} if spec.startswith(('http://', 'https://')) else {'path': spec}
        if not isinstance(spec, dict) or not (spec.get('url') or spec.get('path')):
            raise TaskPayloadError(f'{key} 需要提供 url 或 path')
        return spec

    async def _prepare_inputs(self) -> tuple[Path, Path]:
        """两篇并发准备（下载或校验本地文件）。"""
        return tuple(  # type: ignore[return-value]
            await asyncio.gather(
                self._fetch(self._spec_a, 'A'),
                self._fetch(self._spec_b, 'B'),
            )
        )

    async def _fetch(self, spec: dict[str, Any], label: str) -> Path:
        if spec.get('path'):
            path = Path(spec['path']).expanduser()  # noqa: ASYNC240 —— 本地路径检查是微秒级操作，不值得开线程
            if not path.is_file():
                raise TaskPayloadError(f'综述{label} 的本地文件不存在: {path}')
            await self.log.write_info(f'综述{label}：使用本地文件 {path.name}')
            return path

        url = str(spec['url'])
        target = self.input_dir / f'{label}_{self._filename_from_url(url)}'
        async with self.limiter.io_slot():
            await self.log.write_info(f'综述{label}：开始下载 {url}')
            size = await self._download(url, target)
        await self.log.write_success(f'综述{label}：下载完成 {target.name}（{size / 1024:.0f} KB）')
        return target

    @staticmethod
    def _filename_from_url(url: str) -> str:
        name = unquote(Path(urlparse(url).path).name) or 'review.pdf'
        stem, dot, suffix = name.rpartition('.')
        safe = safe_name(stem or name)
        return f'{safe}.{suffix}' if dot and re.fullmatch(r'[A-Za-z0-9]{1,8}', suffix) else f'{safe}.pdf'

    async def _download(self, url: str, target: Path) -> int:
        import httpx  # noqa: PLC0415 —— 只有走 URL 分支才需要

        total = 0
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + '.part')
        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT, follow_redirects=True) as client, \
                client.stream('GET', url) as resp:
            resp.raise_for_status()
            with tmp.open('wb') as fh:
                async for chunk in resp.aiter_bytes(64 * 1024):
                    total += len(chunk)
                    if total > MAX_DOWNLOAD_BYTES:
                        tmp.unlink(missing_ok=True)
                        raise TaskPayloadError(f'文件超过 {MAX_DOWNLOAD_BYTES // 1024 // 1024}MB 上限: {url}')
                    fh.write(chunk)
        if total == 0:
            tmp.unlink(missing_ok=True)
            raise TaskPayloadError(f'下载到空文件: {url}')
        tmp.replace(target)
        return total

    # ================================================================== 评估

    def _model_config(self) -> ModelConfig:
        """环境变量打底，payload.model 覆盖。空串/None 一律当作「没传」，不覆盖。"""
        cfg = model_config_from_env('SRD')
        raw = self.payload.get('model') or {}
        allowed = ('provider', 'model', 'api_key', 'base_url', 'temperature', 'max_tokens', 'timeout')
        overrides = {k: raw[k] for k in allowed if raw.get(k) not in (None, '')}
        if isinstance(raw.get('extra'), dict):
            overrides['extra'] = dict(raw['extra'])
        return replace(cfg, **overrides) if overrides else cfg

    # ================================================================== 模型池

    def _tuning_overrides(self) -> dict[str, Any]:
        """payload.model 里那些「只调参、不换模型」的字段，会套到池内每个模型上。"""
        raw = self.payload.get('model') or {}
        allowed = ('temperature', 'max_tokens', 'timeout')
        overrides = {k: raw[k] for k in allowed if raw.get(k) not in (None, '')}
        if isinstance(raw.get('extra'), dict):
            overrides['extra'] = dict(raw['extra'])
        return overrides

    def _requested_model_ids(self) -> list[int] | None:
        """payload 里指定的模型主键。数组和 "3,7" 这种字符串都收。"""
        raw = self.payload.get('model_ids') or (self.payload.get('model') or {}).get('model_ids')
        if not raw:
            return None
        items = raw.split(',') if isinstance(raw, str) else raw
        ids = [int(str(x).strip()) for x in items if str(x).strip().isdigit()]
        return ids or None

    async def _load_pool_from_db(self) -> list[ModelConfig]:
        """从 ai_models 表拉一份模型池；库连不上或一条都没有时返回空列表。"""
        try:
            models = await load_llm_models(
                model_ids=self._requested_model_ids(),
                model_types=self.cfg.model_type_list or None,
            )
        except Exception as exc:
            await self.log.write_warning(f'读取 ai_models 失败，回落到环境变量配置：{type(exc).__name__}: {exc}')
            return []

        tuning = self._tuning_overrides()
        return [
            ModelConfig(
                **{
                    'provider': m.provider,
                    'model': m.model_code,
                    'api_key': m.api_key,
                    'base_url': m.base_url,
                    'temperature': float(m.temperature) if m.temperature is not None else 0.0,
                    'max_tokens': m.max_tokens,
                    'ref': m.ref,
                    **tuning,  # payload 的调参覆盖库里的默认值
                }
            )
            for m in models
        ]

    async def _resolve_pool(self) -> list[ModelConfig]:
        """确定这次评估能用哪些模型。优先级见模块 docstring。"""
        inline = (self.payload.get('model') or {}).get('api_key')
        if str(inline or '').strip():
            cfg = self._model_config()
            await self.log.write_info(f'使用 payload 指定的临时模型：{cfg.label}（不参与轮换）')
            self._pool_source = 'payload'
            return [cfg]

        raw = self.payload.get('model') or {}
        if raw.get('provider') or raw.get('model'):
            await self.log.write_warning(
                'payload.model 指定了 provider/model 但没给 api_key：模型池以 ai_models 表为准，'
                '这两项只有在回落到环境变量时才生效（要指定用哪些模型请用 model_ids）'
            )

        pool = await self._load_pool_from_db()
        if pool:
            await self.log.write_info(
                f'模型池（共 {len(pool)} 个，按 model_sort 轮换）：{"、".join(c.label for c in pool)}'
            )
            self._pool_source = 'db'
            return pool

        env_cfg = self._model_config()
        if (env_cfg.api_key or '').strip():
            await self.log.write_warning(f'ai_models 里没有可用模型，回落到环境变量：{env_cfg.label}')
            self._pool_source = 'env'
            return [env_cfg]

        raise TaskPayloadError(
            '没有可用模型：ai_models 表里没有启用中且配了 API key 的模型，'
            'payload.model 与环境变量 SRD_API_KEY 也都没给 API key'
        )

    def _build_runner(self, engine_cfg: EngineConfig) -> LlmRunner:
        """把模型池、共享冻结表、切换通知接到一起。"""
        return LlmRunner(
            self._pool,
            max_concurrency=engine_cfg.max_concurrency,
            failover=FailoverConfig(
                freeze_seconds=float(self.cfg.model_freeze_seconds),
                all_frozen_wait=float(self.cfg.model_all_frozen_wait),
                max_rounds=self.cfg.model_max_rounds,
            ),
            health=self._model_health,
            on_event=self._on_model_event,
            # 只有池子本来就来自数据库时才允许中途重载：全冻结时能捡到运维新启用的模型
            reload_pool=self._load_pool_from_db if self._pool_source == 'db' else None,
        )

    def _on_model_event(self, event: str, message: str) -> None:
        """引擎的同步回调 → 任务日志。别在这里 await。"""
        level = 'warning' if event in ('switch', 'waiting') else 'info'
        self.log.emit(level, f'[模型] {message}', event=event)

    def _engine_config(self) -> EngineConfig:
        """并发做静态切分：每个任务分到 `llm 总闸 / session 总数` 份额。

        不用「跑之前抢 N 个 llm 信号量」那种动态分配 —— 多个任务各抢到一部分就会互相等，
        是教科书式的死锁。静态切分虽然分不满，但永远不会卡住。
        """
        raw = self.payload.get('engine') or {}
        share = max(1, self.cfg.max_concurrent_llm // max(1, self.cfg.max_concurrent_sessions))
        requested = int(raw.get('max_concurrency') or EngineConfig.max_concurrency)
        return EngineConfig(
            extract_scope=str(raw.get('extract_scope') or EngineConfig.extract_scope),
            judge_granularity=str(raw.get('judge_granularity') or EngineConfig.judge_granularity),
            max_concurrency=max(1, min(requested, share)),
            evidence_sufficient_ratio=float(
                raw.get('evidence_sufficient_ratio') or EngineConfig.evidence_sufficient_ratio
            ),
        )

    async def _assess(self, path_a: Path, path_b: Path) -> AssessmentResult:
        engine_cfg = self._engine_config()
        runner = self._build_runner(engine_cfg)
        self._runner = runner
        EXTRACT_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        await self.log.write_info(
            f'模型 {runner.cfg.label}（池内 {len(self._pool)} 个）｜粒度 {engine_cfg.judge_granularity}'
            f'｜并发 {engine_cfg.max_concurrency}｜抽取缓存 {EXTRACT_CACHE_DIR.name}'
        )
        return await assess(
            path_a,
            path_b,
            cfg=engine_cfg,
            runner=runner,
            cache_dir=EXTRACT_CACHE_DIR,
            title_a=str(self._spec_a.get('title') or ''),
            title_b=str(self._spec_b.get('title') or ''),
            on_progress=self._on_engine_progress,
        )

    def _on_engine_progress(self, stage: str, done: int, total: int, detail: str) -> None:
        """引擎的同步回调 → 折算成 0–100 的总进度。别在这里 await。"""
        low, high = STAGE_RANGE.get(stage, (0, 100))
        frac = min(1.0, done / total) if total else 1.0
        percent = int(low + (high - low) * frac)
        label = {'parse': '解析', 'extract': '抽取', 'judge': '判定', 'done': '完成'}.get(stage, stage)
        self.report_progress_nowait(percent, 100, stage, f'{label} {done}/{total} {detail}'.strip())

    # ================================================================== 结果

    def _load_checkpoint(self) -> dict[str, Any] | None:
        """断点只在「引擎三件套版本完全一致」时才认，否则结论无法解释。"""
        if (self.payload.get('options') or {}).get('force'):
            return None
        data = self.checkpoint.load(CHECKPOINT_RESULT)
        if not isinstance(data, dict):
            return None
        same_version = (
            data.get('engine_version') == ENGINE_VERSION
            and data.get('prompt_version') == PROMPT_VERSION
            and data.get('criteria_version') == CRITERIA_VERSION
        )
        return data if same_version else None

    async def _finalize(self, result: AssessmentResult, *, from_checkpoint: bool) -> dict[str, Any]:
        """落盘 JSON / CSV / 文本报告，搬到留档目录，返回给 store 的摘要。"""
        # 进度显式推满：引擎的 done 回调可能被节流吃掉，进度条卡在 95% 很难看
        await self.report_progress(100, 100, 'done', '评估完成')
        out_dir = RESULT_DIR / self.session_id
        await asyncio.to_thread(out_dir.mkdir, parents=True, exist_ok=True)

        files = {
            'json': out_dir / 'result.json',
            'csv': out_dir / 'report.csv',
            'txt': out_dir / 'report.txt',
        }
        await asyncio.to_thread(files['json'].write_text, result.model_dump_json(indent=2), 'utf-8')
        await asyncio.to_thread(files['csv'].write_text, to_csv(result), 'utf-8-sig')
        await asyncio.to_thread(files['txt'].write_text, render_text(result, verbose=True), 'utf-8')

        summary = {
            'task_type': self.task_type,
            'from_checkpoint': from_checkpoint,
            'title_a': result.review_a_title,
            'title_b': result.review_b_title,
            'sha256_a': result.doc_a_sha256,
            'sha256_b': result.doc_b_sha256,
            'same_file': bool(result.doc_a_sha256) and result.doc_a_sha256 == result.doc_b_sha256,
            'overall_level': result.overall_level,
            'overall_level_zh': LEVEL_ZH.get(result.overall_level or '', ''),
            'overall_pct': result.overall_pct,
            # 评分三件套：得分 / 可评分满分 / 名义满分（3 × 34 = 102）
            'overall_score_sum': result.overall_score_sum,
            'overall_score_max': result.overall_score_max,
            'overall_score_max_full': result.overall_score_max_full,
            'overall_reason_zh': result.overall_reason_zh,
            'provisional': result.provisional,
            'domains': [
                {
                    'seq': d.seq, 'name_zh': d.name_zh, 'is_key': d.is_key, 'level': d.level, 'pct': d.pct,
                    'score_sum': d.score_sum, 'score_max': d.score_max, 'score_max_full': d.score_max_full,
                    'dup': d.dup_count, 'diff': d.diff_count, 'unclear': d.unclear_count,
                    'evidence_sufficient': d.evidence_sufficient, 'near_boundary': d.near_boundary,
                }
                for d in result.domains
            ],
            #: 条目评分一览，前端不必再拆 result.json 就能画分数表
            'ratings': {it.code: it.effective_rating for it in result.items},
            'score_distribution': {
                k: sum(1 for it in result.items if it.effective_rating == k)
                for k in ('0', '1', '2', '3', 'unclear')
            },
            'unclear_count': result.unclear_count,
            'review_count': result.review_count,
            'llm_calls': result.llm_calls,
            'token_in': result.token_in,
            'token_out': result.token_out,
            'engine_version': result.engine_version,
            'prompt_version': result.prompt_version,
            'criteria_version': result.criteria_version,
            'model': result.model,
            'model_pool': [c.label for c in self._pool],
            'model_pool_source': self._pool_source,
            # 中途换过模型的话，结论是几个模型合力给出的，摘要里必须能看出来
            'models_used': self._runner.models_used if self._runner else [],
            'model_switches': self._runner.switches if self._runner else [],
            'model_usage': self._runner.usage_stats() if self._runner else [],
            'seconds': round(self.elapsed, 1),
            'files': {k: str(v) for k, v in files.items()},
            'errors': result.errors[:20],
        }
        await self.log.write_success(
            f'结论：{summary["overall_level_zh"] or "-"} '
            f'得分 {result.overall_score_sum}/{result.overall_score_max}'
            f'（名义满分 {result.overall_score_max_full}，重复度 {result.overall_pct}%，'
            f'unclear {result.unclear_count} / 待复核 {result.review_count}）'
        )
        await self.log.write_info(f'结果已留档：{out_dir}')
        return summary

    async def on_success(self, result: dict[str, Any]) -> None:
        """成功后把输入文件挪走的钩子位。

        目前结果就留在本机 `results/{session_id}/`；将来要传对象存储（COS/OSS），
        在这里把 `result['files']` 上传后把 URL 写回去即可，其余流程不用动。
        """

    async def on_failure(self, exc: BaseException) -> None:
        """失败时把已下载的输入留在 work_dir，重跑可省一次下载。"""
        await self.log.write_info(f'输入文件保留在 {self.input_dir}')


def cleanup_result_dir(session_id: str) -> None:
    """删除某次评估的留档结果（供运维脚本调用）。"""
    shutil.rmtree(RESULT_DIR / session_id, ignore_errors=True)
