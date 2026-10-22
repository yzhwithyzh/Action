"""
第四步「AI 优化」的两份草稿级上下文（纯函数，可离线单测，见 `tools/tests/test_refine_context.py`）。

2026-10 用测试稿件跑一键优化撞出来的两个问题，都是「模型只看得到这一条」造成的：

1. **该改的没改**：第三步全稿检查给出了「天枢、上巨虚未附国际代码 → 改为天枢（ST25）」这类带现成
   修改建议的问题，但一键优化只传了逐条判定的理由，模型根本不知道有这条建议。
   → `issues_by_item`：按引文把检查问题挂回条目（口径与前端 `itemsOfQuote` 一致）。
2. **不该补的乱补**：条目要求里提到的要素，只要不在这一条里，就一律被写成【待补充】——
   主要结局写在第 14 条，第 21a 条被补成「主要结局为【待补充】」；引言里被塞进「电针参数【待补充】」。
   → `manuscript_reference`：把草稿当前各条目正文拼成一份全稿参考给模型看。
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any

_WS = re.compile(r'\s+')

#: 引文短于这个长度不找 —— 太短会到处命中（与前端 `itemsOfQuote` 同一口径）
MIN_QUOTE = 6
#: 整段找不到时退一步用的前缀长度（引文可能跨了条目边界）
HEAD_QUOTE = 16


def squash(text: str) -> str:
    """去掉全部空白再比：合成全文会插标题与换行，引文与条目正文的空白未必一致"""
    return _WS.sub('', text or '')


def _pick(item: dict[str, Any], key: str, lang: str) -> str:
    zh, en = item.get(f'{key}Zh') or '', item.get(f'{key}En') or ''

    return (en or zh) if lang == 'en' else zh


def manuscript_reference(items: Sequence[dict[str, Any]], contents: dict[int, str], lang: str = 'zh') -> str:
    """
    草稿全稿参考：按清单顺序列出各条目当前正文，每段前标【章节 · 条目号】。

    导入的稿件里一段话常同时回填进好几条（随机化那段同时是 17a / 17b / 18 / 19），
    正文相同的只列一次、条目号合并 —— 否则同一段重复四遍，白占上下文还干扰模型判断。
    空着的条目不列。**刻意包含本条自己**：一批几十条用同一份参考，才吃得到前缀缓存。

    :param items: 纳入范围内的条目（清单顺序，驼峰键）
    :param contents: 条目id -> 当前正文
    :param lang: 语言
    :return: 拼好的全稿；一条正文都没有时为空串
    """
    order: list[str] = []
    groups: dict[str, dict[str, Any]] = {}
    for it in items:
        text = (contents.get(int(it['itemId'])) or '').strip()
        key = squash(text)
        if not key:
            continue
        if key not in groups:
            groups[key] = {'domain': _pick(it, 'domain', lang), 'nos': [], 'text': text}
            order.append(key)
        no = _pick(it, 'itemNo', lang)
        if no and no not in groups[key]['nos']:
            groups[key]['nos'].append(no)
    blocks = []
    for key in order:
        g = groups[key]
        label = ' · '.join(x for x in (g['domain'], '/'.join(g['nos'])) if x)
        blocks.append(f'【{label}】\n{g["text"]}' if label else g['text'])

    return '\n\n'.join(blocks)


def _quotes_of(finding: dict[str, Any]) -> list[str]:
    """一条发现的引文：优先用逐条 `claims[].quote`，没有时把 `evidence` 按「 / 」拆开"""
    quotes = [str(c.get('quote') or '') for c in finding.get('claims') or [] if isinstance(c, dict)]
    quotes = [q for q in quotes if q.strip()]
    if quotes:
        return quotes

    return [q for q in str(finding.get('evidence') or '').split(' / ') if q.strip()]


def items_of_quote(quote: str, contents: dict[int, str]) -> list[int]:
    """
    引文出自哪几条（与前端 `itemsOfQuote` 同一口径）：去空白后整段子串匹配，找不到再用前 16 个字找一次

    :param quote: 引文
    :param contents: 纳入范围内的条目id -> 正文
    :return: 命中的条目id
    """
    q = squash(quote)
    if len(q) < MIN_QUOTE:
        return []
    squashed = {iid: squash(text) for iid, text in contents.items()}
    hits = [iid for iid, text in squashed.items() if q in text]
    if hits or len(q) < HEAD_QUOTE:
        return hits
    head = q[:HEAD_QUOTE]

    return [iid for iid, text in squashed.items() if head in text]


def issues_by_item(consistency: str | dict[str, Any] | None, contents: dict[int, str], lang: str = 'zh') -> dict[int, list[str]]:
    """
    第三步全稿一致性检查的发现 → 挂到引文所在的条目上，每条渲染成一句「问题（建议：…）」。

    只取 issue / warn 两档（ok 不是问题）。找不到出处的发现不挂 —— 检查之后正文改过，
    引文就对不上了，硬挂到某一条上只会让模型去改一段不相干的话。

    :param consistency: `action_report_review.consistency`（JSON 串或已解析的字典）
    :param contents: 纳入范围内的条目id -> 当前正文
    :param lang: 语言
    :return: 条目id -> 问题句子列表（去重，保持发现顺序）
    """
    if not consistency:
        return {}
    try:
        data = json.loads(consistency) if isinstance(consistency, str) else consistency
    except (TypeError, ValueError):
        return {}
    out: dict[int, list[str]] = {}
    for check in (data or {}).get('checks') or []:
        for finding in check.get('findings') or []:
            if finding.get('severity') not in ('issue', 'warn'):
                continue
            detail = str(finding.get('detail') or '').strip()
            if not detail:
                continue
            fix = str(finding.get('suggestion') or '').strip()
            if fix:
                detail += f'（建议：{fix}）' if lang != 'en' else f' (Suggested fix: {fix})'
            hit: list[int] = []
            for quote in _quotes_of(finding):
                hit += [i for i in items_of_quote(quote, contents) if i not in hit]
            for iid in hit:
                bucket = out.setdefault(iid, [])
                if detail not in bucket:
                    bucket.append(detail)

    return out
