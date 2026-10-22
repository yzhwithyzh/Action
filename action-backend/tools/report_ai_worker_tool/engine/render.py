"""
整篇成文：先定提纲，再逐节写、逐节核对。不认识 Redis / HTTP / 业务表，模型调用由调用方注入。

**两步**（2026-10 改，见 `report_render_prompt` 的模块 docstring）：一次调用让模型按论文通行结构
定提纲、把素材分到各小节；再逐节写。提纲没定成（调用失败、输出解析不出来）就退回按清单章节分组，
成文照样能出 —— 提纲是锦上添花，不该成为整篇失败的新理由。

**按小节分段生成，不一次写整篇**：一次写整篇必然撞输出上限的截断（SRD 与 PDF 解析都踩过），
而截断的现场往往只报得出「内容不完整」。一节一次请求，再把上一节的结尾带给下一节，保证衔接。

某一节调用失败**不让整篇作废**：那一节记下错误、留空，其余照写 —— 已经花掉的那几次调用
不该因为最后一节出错就一起丢掉。页面上那一节显示「没写成，可单独重新生成」。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from module_action.service.render_fidelity import check_section, numbers
from module_action.service.report_render_prompt import (
    Outline,
    RenderItem,
    RenderSection,
    build_messages,
    build_outline_messages,
    fallback_outline,
    labels,
    outline_text,
    parse_outline,
    parse_output,
    reference_text,
    section_hash,
    section_pairs,
    sections_of,
)

#: 带给下一节的上一节结尾长度（字符）
TAIL_CHARS = 200

Ask = Callable[[list[dict]], Awaitable[tuple[str, str]]]


def to_item(it: dict[str, Any]) -> RenderItem:
    """payload 里的一份素材 → `RenderItem`"""
    return RenderItem(
        item_id=int(it['itemId']),
        item_no=str(it.get('itemNo') or ''),
        text=str(it.get('text') or ''),
        placeholder=bool(it.get('placeholder')),
        also=tuple(int(x) for x in it.get('also') or ()),
        also_nos=tuple(str(x) for x in it.get('alsoNos') or ()),
        domain=str(it.get('domain') or ''),
    )


def to_section(raw: dict[str, Any]) -> RenderSection:
    """payload 里的一节 → `RenderSection`"""
    return RenderSection(
        domain=str(raw.get('domain') or ''),
        part=str(raw.get('part') or ''),
        items=tuple(to_item(it) for it in raw.get('items') or []),
    )


async def plan_outline(
    materials: Sequence[RenderItem],
    *,
    lang: str,
    ask: Ask,
    title: str = '',
    guideline_code: str = '',
    fatal: tuple[type[BaseException], ...] = (),
) -> tuple[Outline, bool]:
    """
    让模型定提纲

    :return: (提纲, 是否用的是模型给的提纲)。False = 退回了按清单章节分组
    """
    try:
        raw, _model = await ask(build_outline_messages(materials, lang=lang, title=title, guideline_code=guideline_code))
    except fatal:
        raise
    except Exception:
        return fallback_outline(materials), False
    outline = parse_outline(raw, materials)
    if outline is None:
        return fallback_outline(materials), False

    return outline, True


async def render_sections(
    sections: Sequence[RenderSection],
    *,
    lang: str,
    ask: Ask,
    title: str = '',
    guideline_code: str = '',
    previous_tail: str = '',
    outline: str = '',
    reference: str = '',
    on_section: Callable[[int, str], Awaitable[None]] | None = None,
    fatal: tuple[type[BaseException], ...] = (),
) -> tuple[list[dict[str, Any]], str]:
    """
    逐节写 + 核对

    每节的结果带 `part`（一级部分）、`itemIds`（这一节用到的全部条目，含去重并进来的）与 `hash`
    （素材指纹）：按节判过时、单节重写都靠这两个，不再按清单章节现算。

    :param sections: 各节素材（已按提纲顺序）
    :param lang: 成文语言
    :param ask: 调模型，返回 (正文, 模型标识)
    :param previous_tail: 只重写一节时，它前面那一节的结尾
    :param outline: 全文提纲文本（`outline_text`）
    :param reference: 全稿素材（`reference_text`）
    :param on_section: 开写第 i 节时回调（进度）
    :param fatal: 这些异常不许吞（停止任务）—— 「某节失败不作废整篇」那层 except 不能把停止也吃了
    :return: (各节结果, 最后一次出结果的模型)
    """
    out: list[dict[str, Any]] = []
    tail = previous_tail
    model = ''
    for i, sec in enumerate(sections):
        if on_section:
            await on_section(i, sec.domain)
        label_map = labels(sec)
        also = {it.item_id: it.also for it in sec.items}
        base = {
            'domain': sec.domain,
            'part': sec.part,
            'itemIds': [iid for it in sec.items for iid in it.item_ids],
            'hash': section_hash(section_pairs(sec)),
        }
        try:
            raw, model = await ask(build_messages(
                sec, lang=lang, title=title, guideline_code=guideline_code, previous_tail=tail,
                outline=outline, reference=reference,
            ))
        except fatal:
            raise
        except Exception as e:
            out.append({**base, 'paragraphs': [], 'ok': False, 'issues': [], 'error': f'{type(e).__name__}: {e}'[:300]})
            continue
        paras = parse_output(raw, label_map)
        check = check_section(
            [(it.item_id, '/'.join(it.item_nos), it.text, it.placeholder) for it in sec.items],
            [(p.text, p.item_ids) for p in paras],
        )
        out.append({
            **base,
            # 去重并进来的条目一并标上：页面「这段来自哪几条」要列全，按条目判过时也认得到
            'paragraphs': [
                {'text': p.text, 'itemIds': list(dict.fromkeys(x for iid in p.item_ids for x in (iid, *also.get(iid, ()))))}
                for p in paras
            ],
            'ok': check.ok,
            'issues': [{'kind': x.kind, 'values': list(x.values)} for x in check.issues],
            'error': '',
        })
        if paras:
            tail = paras[-1].text[-TAIL_CHARS:]

    return out, model


def relax_dropped(sections: list[dict[str, Any]], elsewhere: str = '') -> None:
    """
    「丢掉的数字」按**全文**判：一节里没写、但别的小节写了的数字不算丢（就地改 `sections`）。

    逐节写时模型会（也应该）把别处已经写过的内容省掉 —— 素材「招募」里夹着一整段受试者流程，
    流程那一节已经写了，这一节不重复才对。只按本节素材核的话，这种正确的省略全被报成「丢掉的数字」，
    误报一多，用户就学会忽略核对结果。多出来的数字仍按本节核：那是编造的信号，不能放宽。

    :param sections: `render_sections` 的结果
    :param elsewhere: 不在 `sections` 里的其余正文（单节重写时，上一次成文的其他各节）
    """
    doc = '\n'.join(p['text'] for sec in sections for p in sec.get('paragraphs') or []) + '\n' + elsewhere
    present = set(numbers(doc))
    for sec in sections:
        kept = []
        for issue in sec.get('issues') or []:
            if issue.get('kind') == 'droppedNumbers':
                left = [v for v in issue.get('values') or [] if v not in present]
                if not left:
                    continue
                issue = {**issue, 'values': left}
            kept.append(issue)
        sec['issues'] = kept
        if not sec.get('error'):
            sec['ok'] = not kept


async def render_document(
    materials: Sequence[RenderItem],
    *,
    lang: str,
    ask: Ask,
    title: str = '',
    guideline_code: str = '',
    on_phase: Callable[[int, int, str], Awaitable[None]] | None = None,
    fatal: tuple[type[BaseException], ...] = (),
) -> dict[str, Any]:
    """
    整篇：定提纲 → 逐节写

    :param materials: 素材（`build_materials` 去重过的，清单顺序）
    :param on_phase: (已完成步数, 总步数, 说明) —— 总步数 = 1（提纲）+ 小节数，定完提纲才知道
    :return: {'sections', 'model', 'title', 'outlined'}；`title` 是照录的题目素材（没有就空），
        `outlined` 为 False 表示提纲没定成、退回了按清单章节分组
    """
    if on_phase:
        await on_phase(0, 1, '提纲')
    outline, outlined = await plan_outline(materials, lang=lang, ask=ask, title=title, guideline_code=guideline_code, fatal=fatal)
    sections = sections_of(outline, materials)
    total = 1 + len(sections)

    async def on_section(i: int, domain: str) -> None:
        if on_phase:
            await on_phase(1 + i, total, domain)

    paper_title = ''
    title_ids: list[int] = []
    if outline.title_index is not None:
        it = materials[outline.title_index]
        paper_title, title_ids = it.text.strip(), list(it.item_ids)
    result, model = await render_sections(
        sections, lang=lang, ask=ask, title=paper_title or title, guideline_code=guideline_code,
        outline=outline_text(outline), reference=reference_text(materials, lang),
        on_section=on_section, fatal=fatal,
    )
    relax_dropped(result)

    return {
        'sections': result, 'model': model, 'title': paper_title, 'titleItemIds': title_ids,
        'outlined': outlined, 'outline': outline_text(outline),
    }

