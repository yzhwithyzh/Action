"""checklist 校验任务 —— 把「一份稿件 × 一份报告规范」的核对包成 worker 任务。

职责边界：
- **算法**在 `engine/`：`audit.py` 逐条完整性（编行号 → 切窗口 → 分批判定 → 聚合），
  `consistency.py` 全稿逻辑一致性与术语标准化；两者都不认识 Redis / HTTP。
- **本文件**只管把它跑起来：取条目、解析模型池、给进度、写结果、处理停止。

两类判定的主次分明：**逐条完整性是主产物，全稿校验是增补**。所以全稿校验整体失败时
只把它标成「没跑成」、写进日志，不拖垮整个任务 —— 用户已经付过的那几十次条目判定，
不该因为最后四次请求出错就一起丢掉。

任务 payload（后端 rpush 进队列的 JSON）::

    {
      "session_id": "uuid",              必填
      "user_id": 1,
      "guideline_code": "STRICTA",       与 guideline_id 二选一
      "guideline_id": 1,
      "manuscript": "稿件全文……",         必填
      "locale": "zh",                    条目取中文还是英文，默认 zh
      "engine": {"batch_size": 8, "max_concurrency": 4},
      "model_ids": [3, 7],               可选：只用这几个 ai_models 里的模型
      "model": {"temperature": 0, "max_tokens": 4096}   可选调参覆盖
    }

模型来源与 srd_worker_tool 一致：payload 带 api_key 时用临时模型，否则取 `ai_models`
表里启用中的池子按 model_sort「粘性 + 出错切换」，都没有则报错（本工具不设环境变量兜底，
因为官网前台调它，配置必须从后台可见可控）。
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from tools.checklist_worker_tool.config.worker_config import RESULT_DIR, ensure_engine_importable
from tools.checklist_worker_tool.engine.audit import AuditConfig, ChecklistItem, audit
from tools.checklist_worker_tool.engine.consistency import ConsistencyConfig, check_consistency
from tools.common.base_session_task import BaseSessionTask, TaskPayloadError
from tools.common.model_registry import load_llm_models, model_id_from_ref, save_structured_method

ensure_engine_importable()

from srd_engine.adapters.langchain_client import LlmRunner  # noqa: E402
from srd_engine.config import FailoverConfig, ModelConfig  # noqa: E402

#: 各阶段占总进度的区间。逐条判定是花钱的大头（几十次调用），全稿校验只有四次。
STAGE_RANGE = {'load': (0, 6), 'judge': (6, 86), 'cross': (86, 96), 'done': (96, 100)}

#: 稿件长度下限 —— 比这还短基本是误触，早失败比烧一次模型调用好
MIN_MANUSCRIPT_CHARS = 200


class ChecklistSessionTask(BaseSessionTask):
    """一次「稿件 × 规范」的逐条校验。"""

    task_type = 'checklist_review'

    def __init__(self, payload: dict[str, Any], *, model_health: Any = None, **kwargs: Any) -> None:
        super().__init__(payload, **kwargs)
        self._manuscript = ''
        self._guideline_code = ''
        self._guideline_id: int | None = None
        self._locale = 'zh'
        self._model_health = model_health
        self._pool: list[ModelConfig] = []
        self._runner: LlmRunner | None = None

    # ================================================================== 校验

    def validate(self) -> None:
        text = str(self.payload.get('manuscript') or '').strip()
        if len(text) < MIN_MANUSCRIPT_CHARS:
            raise TaskPayloadError(f'稿件内容过短（少于 {MIN_MANUSCRIPT_CHARS} 字），无法校验')
        self._manuscript = text

        code = str(self.payload.get('guideline_code') or '').strip()
        gid = self.payload.get('guideline_id')
        if not code and not gid:
            raise TaskPayloadError('必须指定 guideline_code 或 guideline_id')
        self._guideline_code = code
        self._guideline_id = int(gid) if gid else None

        self._locale = 'en' if str(self.payload.get('locale') or 'zh').lower().startswith('en') else 'zh'

    def task_meta(self) -> dict[str, Any]:
        return {
            **super().task_meta(),
            'guideline_code': self._guideline_code,
            'locale': self._locale,
            'manuscript_chars': len(self._manuscript),
        }

    # ================================================================== 主流程

    async def process(self) -> dict[str, Any]:
        await self.report_progress(STAGE_RANGE['load'][0], 100, 'load', '读取规范条目')
        items = await self._load_items()
        await self.log.write_info(f'规范 {self._guideline_code or self._guideline_id}：共 {len(items)} 条待校验')

        self._pool = await self._resolve_pool()
        self._runner = self._build_runner()

        cfg = self._audit_config()
        await self.report_progress(STAGE_RANGE['judge'][0], 100, 'judge', '逐条判定中')

        lo, hi = STAGE_RANGE['judge']

        def on_progress(done: int, total: int, message: str) -> None:
            # 引擎是同步回调，用 nowait 版本，不阻塞判定协程
            self.report_progress_nowait(lo + int((hi - lo) * done / max(1, total)), 100, 'judge', message)

        result = await audit(self._runner, self._manuscript, items, cfg, on_progress)
        await self.raise_if_stopped()

        consistency = await self._run_consistency()
        await self.raise_if_stopped()
        await self._persist_structured_methods(self._runner)

        return await self._finalize(result, consistency, items)

    async def _run_consistency(self) -> dict[str, Any]:
        """全稿逻辑一致性与术语标准化校验。

        整体失败不抛：逐条完整性已经跑完了，为最后这几次请求把整份结果作废没有道理。
        失败时回一个「全部 unchecked」的空壳，前台照实显示成「未完成校验」——
        它和「未发现问题」在展示上必须分得开，否则等于把没跑过的检查算成了合格。
        """
        lo, hi = STAGE_RANGE['cross']
        await self.report_progress(lo, 100, 'cross', '全稿逻辑与术语校验')

        def on_progress(done: int, total: int, message: str) -> None:
            self.report_progress_nowait(lo + int((hi - lo) * done / max(1, total)), 100, 'cross', message)

        try:
            result = await check_consistency(
                self._runner, self._manuscript, self._consistency_config(), self._locale, on_progress=on_progress
            )
        except Exception as exc:
            await self.log.write_warning(f'全稿校验未完成（{type(exc).__name__}: {exc}），逐条完整性结果不受影响')
            return {'summary': {}, 'checks': [], 'truncated': False, 'errors': [f'{type(exc).__name__}: {exc}']}

        summary = result['summary']
        await self.log.write_info(
            f'全稿校验：不一致 {summary["issue"]} 项 / 待核 {summary["warn"]} 项 / '
            f'未发现问题 {summary["ok"]} 项 / 不适用 {summary["na"]} 项 / 未完成 {summary["unchecked"]} 项'
        )
        if result.get('errors'):
            await self.log.write_warning(f'{len(result["errors"])} 项全稿校验请求失败，相关项标为未完成')
        if result.get('truncated'):
            await self.log.write_warning('稿件超出全稿校验的字符预算，仅通读了前一部分')

        return result

    async def _persist_structured_methods(self, runner: LlmRunner) -> None:
        """把探测出来的结构化输出方式回写进 ai_models（列为空时才写，人工钉死的不覆盖）。"""
        for identity, method in runner.resolved_methods().items():
            model_id = model_id_from_ref(identity)
            if model_id and await save_structured_method(model_id, method):
                await self.log.write_info(f'已记住 {identity} 的结构化输出方式：{method}')

    # ================================================================== 条目

    async def _load_items(self) -> list[ChecklistItem]:
        """从 action_guideline_item 取该规范的全部启用条目，按显示顺序排成一条流水清单。"""
        # 局部 import：worker 进程起来后才需要数据库，模块导入期不该被 .env 连坐
        from config.database import AsyncSessionLocal  # noqa: PLC0415
        from module_action.dao.action_dao import GuidelineItemDao  # noqa: PLC0415
        from module_action.entity.vo.action_vo import GuidelineItemPageQueryModel  # noqa: PLC0415

        query = GuidelineItemPageQueryModel(
            guidelineCode=self._guideline_code or None,
            guidelineId=self._guideline_id,
        )
        async with AsyncSessionLocal() as session:
            rows = await GuidelineItemDao.get_item_list(session, query, is_page=False, only_published=True)

        suffix = 'En' if self._locale == 'en' else 'Zh'

        def val(row: Any, base: str) -> str:
            # DAO 出参已是驼峰字典；英文缺失时回落中文，与前台 pick() 的行为一致
            text = str(row.get(f'{base}{suffix}') or '')
            return text or str(row.get(f'{base}Zh') or '')

        items = [
            ChecklistItem(
                item_id=int(row['itemId']),
                item_no=val(row, 'itemNo'),
                domain=val(row, 'domain'),
                content=val(row, 'content'),
                extension=val(row, 'extension'),
            )
            for row in rows
        ]
        if not items:
            raise TaskPayloadError(f'规范 {self._guideline_code or self._guideline_id} 下没有可用的 checklist 条目')

        return items

    # ================================================================== 模型池

    def _tuning_overrides(self) -> dict[str, Any]:
        raw = self.payload.get('model') or {}
        allowed = ('temperature', 'max_tokens', 'timeout')

        return {k: raw[k] for k in allowed if raw.get(k) not in (None, '')}

    def _requested_model_ids(self) -> list[int] | None:
        raw = self.payload.get('model_ids') or (self.payload.get('model') or {}).get('model_ids')
        if not raw:
            return None
        items = raw.split(',') if isinstance(raw, str) else raw
        ids = [int(str(x).strip()) for x in items if str(x).strip().isdigit()]

        return ids or None

    async def _resolve_pool(self) -> list[ModelConfig]:
        """确定这次校验能用哪些模型。"""
        raw = self.payload.get('model') or {}
        if str(raw.get('api_key') or '').strip():
            cfg = ModelConfig(
                provider=str(raw.get('provider') or 'OpenAI'),
                model=str(raw.get('model') or ''),
                api_key=str(raw['api_key']),
                base_url=raw.get('base_url') or None,
                **self._tuning_overrides(),
            )
            await self.log.write_info(f'使用 payload 指定的临时模型：{cfg.label}（不参与轮换）')
            return [cfg]

        try:
            models = await load_llm_models(
                model_ids=self._requested_model_ids(),
                model_types=self.cfg.model_type_list or None,
            )
        except Exception as exc:
            raise TaskPayloadError(f'读取 ai_models 失败：{type(exc).__name__}: {exc}') from exc

        tuning = self._tuning_overrides()
        pool = [
            ModelConfig(
                provider=m.provider,
                model=m.model_code,
                api_key=m.api_key,
                base_url=m.base_url,
                temperature=float(m.temperature) if m.temperature is not None else 0.0,
                max_tokens=m.max_tokens,
                ref=m.ref,
                structured_method=m.structured_method,
            )
            for m in models
        ]
        pool = [replace(c, **tuning) for c in pool] if tuning else pool
        if not pool:
            raise TaskPayloadError('ai_models 表里没有启用中且配了 API key 的模型，请先在后台配置')
        await self.log.write_info(f'模型池（共 {len(pool)} 个，按 model_sort 轮换）：{"、".join(c.label for c in pool)}')

        return pool

    def _on_model_event(self, event: str, message: str) -> None:
        """模型池的切换/冻结事件写进任务日志。引擎是同步回调，用 emit 不 await。"""
        self.log.emit('warning' if event in ('freeze', 'switch') else 'info', message)

    def _build_runner(self) -> LlmRunner:
        return LlmRunner(
            self._pool,
            max_concurrency=self.cfg.max_concurrent_llm,
            failover=FailoverConfig(
                freeze_seconds=float(self.cfg.model_freeze_seconds),
                all_frozen_wait=float(self.cfg.model_all_frozen_wait),
                max_rounds=self.cfg.model_max_rounds,
            ),
            health=self._model_health,
            on_event=self._on_model_event,
        )

    def _audit_config(self) -> AuditConfig:
        raw = self.payload.get('engine') or {}
        base = AuditConfig(max_concurrency=min(4, self.cfg.max_concurrent_llm))
        allowed = ('batch_size', 'window_chars', 'window_overlap', 'max_concurrency', 'max_chars')
        overrides = {k: int(raw[k]) for k in allowed if str(raw.get(k) or '').strip().isdigit()}

        return replace(base, **overrides) if overrides else base

    def _consistency_config(self) -> ConsistencyConfig:
        raw = (self.payload.get('engine') or {}).get('consistency') or {}
        base = ConsistencyConfig(max_concurrency=min(2, self.cfg.max_concurrent_llm))
        allowed = ('max_chars', 'max_concurrency', 'max_findings')
        overrides = {k: int(raw[k]) for k in allowed if str(raw.get(k) or '').strip().isdigit()}

        return replace(base, **overrides) if overrides else base

    # ================================================================== 收尾

    async def _finalize(
        self, result: dict[str, Any], consistency: dict[str, Any], items: list[ChecklistItem]
    ) -> dict[str, Any]:
        """完整判定写文件留档，任务状态里只回前台要用的那份。"""
        RESULT_DIR.mkdir(parents=True, exist_ok=True)
        path = RESULT_DIR / f'{self.session_id}.json'
        payload = {
            'sessionId': self.session_id,
            'guidelineCode': self._guideline_code,
            'locale': self._locale,
            **result,
            'consistency': consistency,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

        summary = result['summary']
        await self.log.write_info(
            f'完成：完整 {summary["reported"]} 条 / 模糊 {summary["vague"]} 条 / '
            f'缺失 {summary["missing"]} 条，完整度 {summary["completeness"]}%'
        )
        if result.get('errors'):
            await self.log.write_warning(f'有 {len(result["errors"])} 批判定失败，相关条目按未报告处理')

        await self.report_progress(100, 100, 'done', '校验完成')

        return {
            'guidelineCode': self._guideline_code,
            'locale': self._locale,
            'summary': summary,
            'verdicts': result['verdicts'],
            'consistency': {
                'summary': consistency.get('summary') or {},
                'checks': consistency.get('checks') or [],
                'truncated': bool(consistency.get('truncated')),
            },
            'lineCount': result['lineCount'],
            'truncated': result['truncated'],
            'itemCount': len(items),
            'models': self._runner.models_used if self._runner else [],
            'resultFile': str(path),
        }
