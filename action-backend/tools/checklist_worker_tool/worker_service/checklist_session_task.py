"""checklist 校验任务 —— 把「一份稿件 × 一份报告规范」的核对包成 worker 任务。

职责边界：
- **算法**在 `engine/`：`audit.py` 逐条完整性（切窗口 → 分批判定 → 引文定位 → 聚合），
  `consistency.py` 全稿逻辑一致性与术语标准化；两者都不认识 Redis / HTTP。
- **本文件**只管把它跑起来：取条目、解析模型池、给进度、写结果、处理停止。

两类判定的主次分明：**逐条完整性是主产物，全稿校验是增补**。所以全稿校验整体失败时
只把它标成「没跑成」、写进日志，不拖垮整个任务 —— 用户已经付过的那几十次条目判定，
不该因为最后四次请求出错就一起丢掉。

任务 payload（后端 `TaskClient.submit` rpush 进队列的 JSON）::

    {
      "session_id": "uuid",              必填（基类构造时就校验）
      "user_id": 1,                      只用于日志与任务元数据
      "guideline_code": "STRICTA",       与 guideline_id 二选一，对应 action_guideline.code
      "guideline_id": 1,
      "manuscript": "稿件全文……",         必填，strip 后不少于 MIN_MANUSCRIPT_CHARS 字
      "locale": "zh",                    条目取中文还是英文、一致性结论用什么语言写，默认 zh
      "part_nos": [1, 3],                可选：只校验这几张清单表（草稿取消纳入了某几张时），缺省=全部
      "engine": {                        可选：算法参数覆盖，只认白名单里的键（见 _audit_config）
        "batch_size": 8, "window_chars": 60000, "window_overlap": 1500,
        "max_concurrency": 4, "max_chars": 300000,
        "consistency": {"max_chars": 60000, "max_concurrency": 2, "max_findings": 20}
      },
      "model_ids": [3, 7],               可选：只用这几个 ai_models 里的模型（CLI 的 --model-ids）
      "model": {                         可选：调参覆盖，只认 temperature / max_tokens / timeout
        "temperature": 0, "max_tokens": 4096,
        "api_key": "...", "provider": "OpenAI", "model": "...", "base_url": "..."
      }                                  ↑ 带了 api_key 就不查 ai_models，只用这一个临时模型（调试用）
    }

模型来源与 srd_worker_tool 一致：payload 带 api_key 时用临时模型，否则取 `ai_models`
表里启用中的池子按 model_sort「粘性 + 出错切换」，都没有则报错（本工具不设环境变量兜底，
因为官网前台调它，配置必须从后台可见可控）。

任务结果（`process()` 的返回值，写进 Redis 的任务状态，后端轮询时读它落库）见 `_finalize`。
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from tools.checklist_worker_tool.config.worker_config import RESULT_DIR, ensure_engine_importable
from tools.checklist_worker_tool.engine.audit import DASH, AuditConfig, ChecklistItem, audit
from tools.checklist_worker_tool.engine.consistency import (
    RULES,
    CheckResult,
    ConsistencyConfig,
    check_consistency,
)
from tools.checklist_worker_tool.engine.consistency import summarize as summarize_checks
from tools.common.base_session_task import BaseSessionTask, TaskPayloadError
from tools.common.model_registry import load_llm_models, model_id_from_ref, save_structured_method

ensure_engine_importable()

from srd_engine.adapters.langchain_client import LlmRunner  # noqa: E402
from srd_engine.config import FailoverConfig, ModelConfig  # noqa: E402

#: 各阶段占总进度的区间（百分比）。逐条判定是花钱也花时间的大头（几十次调用），
#: 全稿校验只有四次，所以区间按调用次数而不是按「步骤数」分。前台进度条直接用这个数。
#: 键名同时是进度事件的 stage 字段：load 取条目 / judge 逐条判定 / cross 全稿校验 / done 收尾
STAGE_RANGE = {'load': (0, 6), 'judge': (6, 86), 'cross': (86, 96), 'done': (96, 100)}

#: 稿件长度下限 —— 比这还短基本是误触，早失败比烧一次模型调用好
MIN_MANUSCRIPT_CHARS = 200

#: payload 覆盖窗口大小时的下限：再小的话一个窗口装不下几句话，同一条目要被判几十遍
MIN_WINDOW_CHARS = 2000

#: 每条错误信息落库前截到多长。报错里可能裹着模型的原始输出（也就是稿件片段），只留开头够排障即可
ERROR_CHARS = 200


def _positive_ints(raw: dict[str, Any], allowed: tuple[str, ...]) -> dict[str, int]:
    """从 payload 里挑出白名单内、值为正整数的覆盖项。

    `isdigit()` 挡掉负数、小数和非数字；再单独挡掉 0 —— 它是合法数字，却会让批大小、并发数、
    字符预算变成 0，分批直接抛异常或一个字都不发。传错了就当没传、用默认值。
    """
    out: dict[str, int] = {}
    for key in allowed:
        text = str(raw.get(key) or '').strip()
        if text.isdigit() and int(text) > 0:
            out[key] = int(text)

    return out


class ChecklistSessionTask(BaseSessionTask):
    """一次「稿件 × 规范」的逐条校验。

    生命周期由基类 `BaseSessionTask.run()` 驱动：``validate()`` → 标 running →
    ``process()`` → 标 completed（返回值即任务结果）。停止、失败、worker 关闭时的中断
    都由基类处理，本类只在长步骤之间调 `raise_if_stopped()` 给停止信号一个落点。
    """

    task_type = 'checklist_review'

    def __init__(self, payload: dict[str, Any], *, model_health: Any = None, **kwargs: Any) -> None:
        """
        :param payload: 队列里弹出来的任务 JSON（格式见文件头）
        :param model_health: 跨进程共享的模型冻结表（Redis 实现），由 `ChecklistWorkerService.task_kwargs` 注入；
            为 None 时 LlmRunner 退回进程内冻结表
        :param kwargs: 基类要的 cfg / store / limiter
        """
        super().__init__(payload, **kwargs)
        # 以下几个在 validate() 里从 payload 解析出来；构造时先给空值，免得 validate 失败时属性不存在
        self._manuscript = ''
        self._guideline_code = ''
        self._guideline_id: int | None = None
        self._locale = 'zh'
        self._part_nos: set[int] | None = None
        self._model_health = model_health
        # 模型池与调用器在 process() 里才建：建池要查数据库，validate 失败的任务不该付这个代价
        self._pool: list[ModelConfig] = []
        self._runner: LlmRunner | None = None

    # ================================================================== 校验

    def validate(self) -> None:
        """payload 校验：只查「不用连库就能判断」的事，早失败、错误信息给人看得懂。

        规范存不存在、有没有条目要查库，放在 `_load_items` 里判。
        """
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

        raw_parts = self.payload.get('part_nos')
        if raw_parts is not None and not isinstance(raw_parts, list):
            raise TaskPayloadError('part_nos 必须是整数列表')
        try:
            self._part_nos = {int(p) for p in raw_parts} if raw_parts else None
        except (TypeError, ValueError) as e:
            raise TaskPayloadError('part_nos 必须是整数列表') from e

    def task_meta(self) -> dict[str, Any]:
        """标 running 时一并写进任务状态的元数据，`cli status` 与排障时看得到。

        只放字数不放稿件本身：任务状态在 Redis 里留 `task_ttl`（默认 7 天），不该挂着一整篇未发表稿件。
        """
        return {
            **super().task_meta(),
            'guideline_code': self._guideline_code,
            'locale': self._locale,
            'manuscript_chars': len(self._manuscript),
        }

    # ================================================================== 主流程

    async def process(self) -> dict[str, Any]:
        """主流程，五步：取条目 → 组模型池 → 逐条判定 → 全稿校验 → 收尾。

        两类判定**串行**而不是并行：它们共用同一个 runner 的并发闸（`max_concurrent_llm`），
        并行只会互相抢槽位；而且逐条判定是主产物，先跑完它，全稿校验失败时也有东西可交。
        """
        # ① 取条目（查库）。规范不存在或没有启用的条目会在这里抛 TaskPayloadError
        await self.report_progress(STAGE_RANGE['load'][0], 100, 'load', '读取规范条目')
        items = await self._load_items()
        await self.log.write_info(f'规范 {self._guideline_code or self._guideline_id}：共 {len(items)} 条待校验')

        # ② 组模型池。两类判定共用这一个 runner：粘性选中的模型、冻结记录、token 计数都跨两步延续
        self._pool = await self._resolve_pool()
        self._runner = self._build_runner()

        # ③ 逐条完整性判定（引擎 audit）
        cfg = self._audit_config()
        await self.report_progress(STAGE_RANGE['judge'][0], 100, 'judge', '逐条判定中')

        lo, hi = STAGE_RANGE['judge']

        def on_progress(done: int, total: int, message: str) -> None:
            # 引擎按「完成了几批 / 共几批」回调，这里把它线性映射进 judge 阶段的进度区间。
            # 引擎是同步回调，用 nowait 版本，不阻塞判定协程
            self.report_progress_nowait(lo + int((hi - lo) * done / max(1, total)), 100, 'judge', message)

        result = await audit(self._runner, self._manuscript, items, cfg, on_progress)
        # 引擎内部不认识停止信号；在两段长步骤之间查一次，用户点了停止就不再花全稿校验那四次调用
        await self.raise_if_stopped()

        # ④ 全稿一致性与术语（引擎 consistency）。失败不抛，见 _run_consistency
        consistency = await self._run_consistency()
        await self.raise_if_stopped()

        # 这一步放在两类判定都跑完之后：探测结果在两步之间还可能继续降级，跑完才是定论
        await self._persist_structured_methods(self._runner)

        # ⑤ 收尾：留档 + 组装返回给后端的结果
        return await self._finalize(result, consistency, items)

    async def _run_consistency(self) -> dict[str, Any]:
        """全稿逻辑一致性与术语标准化校验。

        整体失败不抛：逐条完整性已经跑完了，为最后这几次请求把整份结果作废没有道理。
        失败时回一个「全部 unchecked」的空壳，前台照实显示成「未完成校验」——
        它和「未发现问题」在展示上必须分得开，否则等于把没跑过的检查算成了合格。

        两层失败别混：**单条规则**的模型调用失败，引擎自己就把那条标成 unchecked（不会走到这里的
        except）；走到 except 的是引擎本身抛了异常。以前这里回的是 `checks: []`，前台遇到空列表会把
        整段隐藏 —— 用户看到的是「没有这一项检查」而不是「这一项没跑完」，与上面那条承诺相反。
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
            shells = [CheckResult(key=r.key, kind=r.kind) for r in RULES]  # status 默认就是 unchecked
            return {
                'summary': summarize_checks(shells),
                'checks': [c.to_dict() for c in shells],
                'truncated': False,
                'errors': [f'{type(exc).__name__}: {exc}'],
            }

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
        """把探测出来的结构化输出方式回写进 ai_models（列为空时才写，人工钉死的不覆盖）。

        为什么要记：同一个模型在不同厂商端点上支持的方式不一样（火山方舟上的 deepseek 不认
        json_schema），runner 只能拿真实请求去撞、撞到「不支持」再降级。这种请求带着整篇稿件，
        撞一次要几十秒；不记下来的话每个任务都要重新付一遍。
        `identity` 是 runner 内的模型键（形如 `ai_models:3`），临时模型解析不出 id，跳过。
        """
        for identity, method in runner.resolved_methods().items():
            model_id = model_id_from_ref(identity)
            if model_id and await save_structured_method(model_id, method):
                await self.log.write_info(f'已记住 {identity} 的结构化输出方式：{method}')

    # ================================================================== 条目

    async def _load_items(self) -> list[ChecklistItem]:
        """从 action_guideline_item 取该规范的全部启用条目，按显示顺序排成一条流水清单。

        一份规范可能含多张清单表（RCT = CONSORT 主表 + 摘要表 + STRICTA 表），DAO 已按
        `sort_num` 排好，这里不再重排 —— 引擎按这个顺序每 `batch_size` 条切一批，
        同一张表的相邻条目落在同一批里，模型判的时候上下文更连贯。
        `only_published=True`：后台「规范条目管理」里停用的条目不参与校验。
        """
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
            # DAO 出参已是驼峰字典；英文缺失时回落中文，与前台 pick() 的行为一致。
            # 「—」也算缺失：原表用它表示「此格无内容」，它是非空串，不单独判的话英文界面下
            # 会把一个「—」当条目正文发给模型，而中文列里明明有内容
            text = str(row.get(f'{base}{suffix}') or '')
            return text if text.strip() and not DASH.match(text.strip()) else str(row.get(f'{base}Zh') or '')

        # 草稿在第二步取消纳入了某几张清单表时只校验剩下的（后端 sql/051）。
        # 圈完一条不剩就是 payload 与库对不上（那几张表被后台删了），如实报错，不悄悄退回全部
        if self._part_nos is not None:
            rows = [row for row in rows if int(row.get('partNo') or 1) in self._part_nos]

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
        """payload.model 里的调参覆盖，只认白名单三项。

        白名单是为了不让 payload 改到连接信息（api_key / base_url 走的是另一条「临时模型」分支）；
        值原样透传给 `ModelConfig`，类型由它自己校验。
        """
        raw = self.payload.get('model') or {}
        allowed = ('temperature', 'max_tokens', 'timeout')

        return {k: raw[k] for k in allowed if raw.get(k) not in (None, '')}

    def _requested_model_ids(self) -> list[int] | None:
        """payload 指定的 ai_models 主键，用来把池子缩小到其中几个。

        两处都认（顶层 `model_ids` 与 `model.model_ids`），数组或逗号分隔字符串都行；
        解析不出任何合法 id 时返回 None = 不缩小，用整个池子。
        """
        raw = self.payload.get('model_ids') or (self.payload.get('model') or {}).get('model_ids')
        if not raw:
            return None
        items = raw.split(',') if isinstance(raw, str) else raw
        ids = [int(str(x).strip()) for x in items if str(x).strip().isdigit()]

        return ids or None

    async def _resolve_pool(self) -> list[ModelConfig]:
        """确定这次校验能用哪些模型，按优先级：

        1. payload.model 带了 api_key → 只用这一个临时模型，不参与轮换（CLI / 调试用；
           官网后端从不这么投递）；
        2. 否则查 `ai_models` 表里启用中、配了 key 的模型，按 model_sort 排成池子；
           `model_ids` 可以把池子缩小到其中几个；
        3. 池子为空 → 抛 TaskPayloadError，任务失败并在日志里说清楚要去后台配置。

        `structured_method` 从库里带进来：列非空时 runner 直接用它，不再从 json_schema 起探测。
        """
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
                extra=m.chat_extra,
            )
            for m in models
        ]
        pool = [replace(c, **tuning) for c in pool] if tuning else pool
        if not pool:
            raise TaskPayloadError('ai_models 表里没有启用中且配了 API key 的模型，请先在后台配置')
        await self.log.write_info(
            f'模型池（共 {len(pool)} 个，按 model_sort 轮换）：{"、".join(c.label for c in pool)}'
        )

        return pool

    def _on_model_event(self, event: str, message: str) -> None:
        """模型池的切换/冻结事件写进任务日志。引擎是同步回调，用 emit 不 await。"""
        self.log.emit('warning' if event in ('freeze', 'switch') else 'info', message)

    def _build_runner(self) -> LlmRunner:
        """把模型池包成调用器（srd-engine 的 LlmRunner，引擎只认它的 `structured()`）。

        - `max_concurrency`：runner 的全局并发闸，引擎自己的 `max_concurrency` 是它下面的第二道；
        - `failover`：「粘性 + 出错切换」—— 一直用当前模型，网络抖动先原地重试，
          撞到限流/欠费/5xx 才把它冻结 `freeze_seconds` 秒换下一个；全池都冻结时，
          只对会自愈的错误（限流、5xx、超时）最多等 `all_frozen_wait` 秒，鉴权/欠费不等；
          单次调用最多把池子轮 `max_rounds` 圈，仍失败就把这一次调用判错（引擎按批次失败处理）；
        - `health`：冻结记录存哪（Redis，跨 worker 共享）；
        - `on_event`：切换/冻结事件写进任务日志，用户在前台日志里能看到「换了模型」。
        """
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
        """逐条判定的算法参数：引擎默认值 + payload.engine 里的白名单覆盖。

        并发默认 4 而不是直接用 `max_concurrent_llm`（12）：一个 worker 同时跑 2 个任务，
        每个任务的逐条判定各占 4 个，给另一个任务和全稿校验都留出余量。
        只收正整数（`_positive_ints`），再把几个互相牵制的参数夹到合理范围：
        `batch_size=0` 会让分批直接抛异常；`window_overlap ≥ window_chars` 会让每个窗口只前进一行，
        窗口数随行数线性增长，同样的内容被判几百遍。
        """
        raw = self.payload.get('engine') or {}
        base = AuditConfig(max_concurrency=min(4, self.cfg.max_concurrent_llm))
        allowed = ('batch_size', 'window_chars', 'window_overlap', 'max_concurrency', 'max_chars')
        cfg = replace(base, **_positive_ints(raw, allowed))

        window = max(cfg.window_chars, MIN_WINDOW_CHARS)
        return replace(cfg, window_chars=window, window_overlap=min(cfg.window_overlap, window // 2))

    def _consistency_config(self) -> ConsistencyConfig:
        """全稿校验的算法参数，规则同 `_audit_config`，覆盖项在 payload.engine.consistency 下。

        并发默认 2：每条规则的请求都带着整篇稿件（最多 6 万字符），并发开大了容易撞 token 限流。
        """
        raw = (self.payload.get('engine') or {}).get('consistency') or {}
        base = ConsistencyConfig(max_concurrency=min(2, self.cfg.max_concurrent_llm))
        allowed = ('max_chars', 'max_concurrency', 'max_findings')

        return replace(base, **_positive_ints(raw, allowed))

    # ================================================================== 收尾

    def _usage(self) -> dict[str, Any]:
        """本次任务的模型用量（运维口径，只进日志与留档文件，不回给前台）。

        `token_cached` 是 `token_in` 里命中厂商前缀缓存的部分：14 次左右的调用每次都带着整篇稿件，
        命中率直接决定输入成本。`token_reasoning` 是 `token_out` 里思考模式的推理过程。
        厂商不报这两项时都是 0，与「没命中 / 没思考」分不开。
        """
        r = self._runner
        if r is None:
            return {'calls': 0, 'token_in': 0, 'token_cached': 0, 'token_out': 0, 'token_reasoning': 0,
                    'cache_hit_pct': 0, 'models': []}

        return {
            'calls': r.calls,
            'token_in': r.token_in,
            'token_cached': r.token_cached,
            'token_out': r.token_out,
            'token_reasoning': r.token_reasoning,
            'cache_hit_pct': round(100 * r.token_cached / r.token_in, 1) if r.token_in else 0,
            'models': r.usage_stats(),
        }

    async def _finalize(
        self, result: dict[str, Any], consistency: dict[str, Any], items: list[ChecklistItem]
    ) -> dict[str, Any]:
        """完整判定写文件留档，任务状态里只回前台要用的那份。

        两份的差别：留档文件多了引擎的 `windows` 与完整的报错，是给运维排障用的；
        返回值是后端轮询到 completed 时落库、前台渲染的那份，结构如下::

            {
              "guidelineCode": "STRICTA", "locale": "zh",
              "summary":  {total, reported, vague, missing, completeness},     逐条判定汇总
              "verdicts": [{itemId, status, lines, evidence, reason, located}], 逐条判定
              "consistency": {"summary": {...}, "checks": [...], "truncated": bool},
              "errors": ["..."],                      这次校验里没跑成的部分（见下）
              "lineCount": 412, "truncated": false,   稿件有效行数、是否超长被截断
              "itemCount": 78,
              "models": [...],                        实际用到的模型（运维口径）
              "resultFile": "…/results/<sid>.json"    留档路径（后端目前不读）
            }

        `errors` 非空 = 「任务完成了，但有一部分没判成」：批次失败、条目未作答、全稿校验的
        某条规则没跑成。前台据此在结果区顶部提示「部分判定未完成，建议重新校验」——
        不给这个信号的话，没判成的条目与「判了、确实没写」在页面上长得一模一样。
        逐条判定的在前（主产物），全稿校验的加 `全稿校验 ` 前缀在后；每条截到 ERROR_CHARS，
        报错里可能裹着模型的原始输出，也就是稿件片段。

        **留档文件目前不会被清理**：基类的过期清理只管 temp / checkpoint / logs 三个目录，
        不管 `RESULT_DIR`；用户在官网删除校验记录时也碰不到它。文件里的 evidence 与
        一致性 claims 是稿件原文片段 —— 改这里之前先想清楚这批文件的保留期。
        """
        RESULT_DIR.mkdir(parents=True, exist_ok=True)
        path = RESULT_DIR / f'{self.session_id}.json'
        usage = self._usage()
        payload = {
            'sessionId': self.session_id,
            'guidelineCode': self._guideline_code,
            'locale': self._locale,
            **result,
            'consistency': consistency,
            'usage': usage,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

        summary = result['summary']
        await self.log.write_info(
            f'完成：完整 {summary["reported"]} 条 / 模糊 {summary["vague"]} 条 / '
            f'缺失 {summary["missing"]} 条，完整度 {summary["completeness"]}%'
        )
        if usage['calls']:
            await self.log.write_info(
                f'用量：调用 {usage["calls"]} 次 / 输入 {usage["token_in"]} tokens'
                f'（命中缓存 {usage["token_cached"]}，{usage["cache_hit_pct"]}%）/ '
                f'输出 {usage["token_out"]} tokens（其中思考 {usage["token_reasoning"]}）'
            )
        if result.get('errors'):
            # errors 最多留 5 条，里面既有批次失败也有「N 条未作答」的汇总，数条数没有意义，逐条打出来
            for err in result['errors']:
                await self.log.write_warning(f'逐条判定异常：{str(err)[:200]}')

        await self.report_progress(100, 100, 'done', '校验完成')

        errors = [str(e)[:ERROR_CHARS] for e in result.get('errors') or []]
        errors += [f'全稿校验 {str(e)[:ERROR_CHARS]}' for e in consistency.get('errors') or []]

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
            'errors': errors,
            'lineCount': result['lineCount'],
            'truncated': result['truncated'],
            'itemCount': len(items),
            'models': self._runner.models_used if self._runner else [],
            'resultFile': str(path),
        }
