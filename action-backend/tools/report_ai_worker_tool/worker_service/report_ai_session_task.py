"""
报告助手第四步的分钟级 AI 任务：`kind` = refine（一键优化）/ render（整篇成文）。

职责边界同另外几个 worker：**算法与提示词不在这里**（`module_action/service/report_assist_prompt`、
`report_render_prompt`、`render_fidelity`，以及本工具的 `engine/render.py`），**业务库也不在这里写**
—— 结果写进 Redis 任务状态，由后端轮询接口落库。

模型调用直接走后端的 `AiAssistService`（`rewrite` / `complete`）：一键优化里每一条用的就是
单条「AI 优化」那一份提示词与模型池轮询，两条路产出的建议必须是同一个口径，不另抄一份。

任务 payload（后端 `ReportAiService` 组好、rpush 进 `report_ai` 队列）::

    公共：  session_id / user_id / draft_id / kind / locale
    refine：items = [{itemId, ctx: {AssistContext 的字段}, instruction}]
    render（整篇）：lang / title / guideline_code / materials = [{itemId, itemNo, domain, text, placeholder, also, alsoNos}]
      —— 先让模型定提纲、再逐节写（engine/render.render_document）
    render（单节重写）：lang / title / guideline_code / previous_tail / outline / reference /
      sections = [{domain, part, items: [素材]}] —— 沿用上一次的提纲，只写这一节

payload 里带着条目正文（与 checklist worker 带整篇稿件同一口径）；任务状态里只放计数，不放正文。
"""

from __future__ import annotations

import asyncio
from typing import Any

from tools.common.base_session_task import BaseSessionTask, TaskPayloadError, TaskStopped
from tools.common.task_store import STATUS_STOPPED
from tools.report_ai_worker_tool.engine.render import relax_dropped, render_document, render_sections, to_item, to_section

#: 整篇成文单章的超时。一章素材十几条、输出一两千字，模型慢的时候要一两分钟
RENDER_TIMEOUT = 300.0
MAX_REFINE_ITEMS = 200


class ReportAiSessionTask(BaseSessionTask):
    """一键优化 / 整篇成文"""

    task_type = 'report_ai'

    def __init__(self, payload: dict[str, Any], *, model_health: Any = None, **kwargs: Any) -> None:
        super().__init__(payload, **kwargs)
        self._kind = ''
        self._locale = 'zh'
        self._model_health = model_health
        #: 一键优化已经出来的结果。用户中途停止时由 `on_stopped` 连同「已停止」一起写回任务状态 ——
        #: 跑了 50 条被停掉，这 50 条不该跟着一起丢
        self._done: list[dict[str, Any]] = []
        self._failed: list[dict[str, Any]] = []

    # ================================================================== 校验

    def validate(self) -> None:
        kind = str(self.payload.get('kind') or '')
        if kind not in ('refine', 'render'):
            raise TaskPayloadError(f'未知的任务类型：{kind}')
        self._kind = kind
        self._locale = 'en' if str(self.payload.get('locale') or 'zh').lower().startswith('en') else 'zh'
        if kind == 'refine':
            items = self.payload.get('items')
            if not isinstance(items, list) or not items:
                raise TaskPayloadError('一键优化没有要处理的条目')
            if len(items) > MAX_REFINE_ITEMS:
                raise TaskPayloadError(f'一次最多优化 {MAX_REFINE_ITEMS} 条')
        else:
            sections = self.payload.get('sections')
            if not isinstance(sections, list) or not sections:
                raise TaskPayloadError('整篇成文没有可写的章节')

    def task_meta(self) -> dict[str, Any]:
        return {**super().task_meta(), 'kind': self._kind, 'draft_id': self.payload.get('draft_id')}

    # ================================================================== 主流程

    async def process(self) -> dict[str, Any]:
        if self._kind == 'refine':
            return await self._refine()

        return await self._render()

    async def _handle_stopped(self, message: str) -> None:
        """
        停止时把已经出来的建议**与 stopped 状态一次写进去**，后端照样落库。

        不能沿用基类「先 `mark_stopped`、再在 `on_stopped` 里补写结果」：两次写入之间后端轮询
        读到的是「已停止、没有结果」，台账就此定成终态，随后补进来的那 N 条建议再也不会落库。
        """
        if self._kind != 'refine' or not self._done:
            await super()._handle_stopped(message)
            return
        if self._main_task is not None and hasattr(self._main_task, 'uncancel'):
            self._main_task.uncancel()
        await self.store.mark_finished(
            self.session_id,
            STATUS_STOPPED,
            result={'kind': 'refine', 'results': list(self._done), 'failed': list(self._failed), 'stopped': True},
            error=message,
        )
        await self.log.write_warning(f'■ {message}，已生成的 {len(self._done)} 条建议随停止状态一并保留')
        await self.on_stopped()
        await self.log.write_completed('任务已停止', status=STATUS_STOPPED)

    # ---------------------------------------------------------------- 一键优化

    async def _refine(self) -> dict[str, Any]:
        from config.database import AsyncSessionLocal  # noqa: PLC0415
        from module_action.service.ai_assist_service import AiAssistService  # noqa: PLC0415
        from module_action.service.report_assist_prompt import AssistContext  # noqa: PLC0415

        items: list[dict[str, Any]] = list(self.payload['items'])
        total = len(items)
        sem = asyncio.Semaphore(max(1, int(self.cfg.max_concurrent_llm)))
        await self.report_progress(0, total, 'refine', f'共 {total} 条')

        async def one(item: dict[str, Any]) -> None:
            ctx_raw = item.get('ctx') or {}
            async with sem:
                await self.raise_if_stopped()
                try:
                    async with AsyncSessionLocal() as session:
                        text, label = await AiAssistService.rewrite(
                            session,
                            action='refine',
                            ctx=AssistContext(**{
                                **ctx_raw,
                                'issues': tuple(ctx_raw.get('issues') or ()),
                                # 全稿只在 payload 顶层传一份（几十条各带一份太大）；老任务没有这个键时为空
                                'manuscript': str(self.payload.get('manuscript') or ''),
                            }),
                            locale=self._locale,
                            instruction=str(item.get('instruction') or ''),
                        )
                except (TaskStopped, asyncio.CancelledError):
                    raise
                except Exception as e:
                    # 一条失败不拖垮整批：记下来，跑完如实报「几条没生成」
                    self._failed.append({'itemId': int(item['itemId']), 'error': f'{type(e).__name__}: {e}'[:300]})
                    await self.log.write_warning(f'条目 {item["itemId"]} 生成失败：{type(e).__name__}')
                else:
                    self._done.append({
                        'itemId': int(item['itemId']),
                        'text': text,
                        'model': label,
                        'baseText': str(ctx_raw.get('current_text') or ''),
                        'instruction': str(item.get('instruction') or ''),
                    })
            n = len(self._done) + len(self._failed)
            self.report_progress_nowait(n, total, 'refine', f'{n}/{total}')

        # 一条子任务抛出停止信号时要把其余的一并取消：裸 gather 只会把第一个异常往上抛，
        # 已经在调模型的那几条会照跑照计费，跑完 append 到 `_done` 时停止状态早已写出去了
        tasks = [asyncio.create_task(one(it)) for it in items]
        try:
            await asyncio.gather(*tasks)
        except BaseException:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        await self.log.write_info(f'一键优化完成：成功 {len(self._done)} 条，失败 {len(self._failed)} 条')
        await self.report_progress(total, total, 'done', '完成')

        return {'kind': 'refine', 'results': self._done, 'failed': self._failed, 'stopped': False}

    # ---------------------------------------------------------------- 整篇成文

    async def _render(self) -> dict[str, Any]:
        from config.database import AsyncSessionLocal  # noqa: PLC0415
        from module_action.service.ai_assist_service import AiAssistService  # noqa: PLC0415

        lang = 'en' if str(self.payload.get('lang') or 'zh') == 'en' else 'zh'
        title = str(self.payload.get('title') or '')
        code = str(self.payload.get('guideline_code') or '')
        fatal = (TaskStopped, asyncio.CancelledError)

        async def ask(messages: list[dict]) -> tuple[str, str]:
            await self.raise_if_stopped()
            async with AsyncSessionLocal() as session:
                # 输出长度取决于这一节写了多少条，事先估不准 —— 给个猜的上限就会撞截断
                # （PDF 抽取那条路踩过），所以不下发 max_tokens，超时一并放宽
                return await AiAssistService.complete(
                    session, messages, max_tokens=None, timeout=RENDER_TIMEOUT, failure_hint='整篇成文失败',
                )

        if self.payload.get('materials') is not None:
            materials = [to_item(it) for it in self.payload['materials']]

            async def on_phase(i: int, total: int, label: str) -> None:
                await self.report_progress(i, total, label[:40], f'{i + 1}/{total} {label}')

            doc = await render_document(materials, lang=lang, ask=ask, title=title, guideline_code=code, on_phase=on_phase, fatal=fatal)
            result, model = doc['sections'], doc['model']
            extra = {k: doc[k] for k in ('title', 'titleItemIds', 'outlined', 'outline')}
            await self.log.write_info('提纲：' + ('模型给出' if doc['outlined'] else '没定成，退回按清单章节分组'))
        else:
            sections = [to_section(s) for s in self.payload['sections']]
            total = len(sections)

            async def on_section(i: int, domain: str) -> None:
                await self.report_progress(i, total, domain[:40], f'{i + 1}/{total} {domain}')

            result, model = await render_sections(
                sections, lang=lang, ask=ask, title=title, guideline_code=code,
                previous_tail=str(self.payload.get('previous_tail') or ''),
                outline=str(self.payload.get('outline') or ''), reference=str(self.payload.get('reference') or ''),
                on_section=on_section, fatal=fatal,
            )
            # 单节重写：别的小节在上一次成文里，「丢掉的数字」要连它们一起看
            relax_dropped(result, str(self.payload.get('elsewhere') or ''))
            extra = {}
        total = len(result)
        bad = sum(1 for s in result if not s['ok'])
        await self.log.write_info(f'整篇成文完成：{total} 节，核对不通过 {bad} 节')
        await self.report_progress(total, total, 'done', '完成')

        return {'kind': 'render', 'lang': lang, 'sections': result, 'model': model, **extra}
