"""正文预处理与超长兜底（纯代码，无 LLM，无 IO）。

抽取要把整篇原文喂给模型。这里负责喂之前的两件事，以及超长时切块后的合并：

1. **剔除参考文献段** —— 一律执行。它对 34 个条目的判定没有任何贡献，却占全文
   17%–33%（实测 12 篇里 11 篇命中，合计省 20% 输入）。
2. **仍超上限则切块** —— 每块单独抽取，再用 `merge` 合并回一份 facet。
   常规期刊综述（3.6 万–8.6 万字符）走不到这一步。

合并之所以成立，是因为 facet 回答的是「原文有没有报告 X」，这是**单调命题**：
某块抽到了就是有，别的块没抽到不代表没有。所以取并集即可，不需要投票、不需要仲裁。
（判定阶段相反 —— 那是「比较两篇」，必须看全局，绝不能分块。）
"""

from __future__ import annotations

import math
import re

from pydantic import BaseModel

# 单批次喂给模型的最大字符数。本仓库样本文献全文在 3.6 万–8.6 万字符之间，
# 12 万的上限意味着正常期刊论文剔完参考文献后不会触发切块。
MAX_BATCH_CHARS = 120_000

# --------------------------------------------------------------------------- 剔参考文献

# 只认独占一行的标题，从**最后一个**匹配处砍到文末。刻意做得比「精确识别参考文献
# 区间」粗糙：多砍一点（比如把紧跟其后的附录一起砍）远好过在正文中间挖洞，
# 而精确识别需要序号连续性、引文体征密度等一整套启发式，实测收益为零。
_REF_TITLE = re.compile(
    r'^\s*(?:\d+\s*[.、]?\s*)?(references?|reference list|bibliography|参\s*考\s*文\s*献)\s*[:：]?\s*$',
    re.I,
)
_REF_SEARCH_FLOOR = 0.4   # 参考文献不会出现在文档前 40%
_REF_MAX_CUT = 0.6        # 砍掉超过全文这个比例，八成是认错了，放弃


def drop_references(text: str) -> tuple[str, str]:
    """:return: (剩余正文, 说明)。说明恒非空，供上层记进 warnings。"""
    lines = text.splitlines()
    floor = int(len(lines) * _REF_SEARCH_FLOOR)
    for i in range(len(lines) - 1, floor - 1, -1):
        if _REF_TITLE.match(lines[i].rstrip()):
            cut = sum(len(x) + 1 for x in lines[i:])
            if cut > len(text) * _REF_MAX_CUT:
                return text, f'疑似参考文献段占全文 {cut / len(text):.0%}，超过安全闸，未剔除'
            return '\n'.join(lines[:i]), f'已剔除参考文献段 {cut} 字符'
    return text, '未找到参考文献标题，未剔除'


# --------------------------------------------------------------------------- 切块


def split(text: str) -> list[str]:
    """按行边界等分成若干块，每块不超过上限。

    按「剩余字符 ÷ 剩余块数」动态均摊，而不是固定 `总长/n`：固定目标时余数全堆在
    最后一块，实测 25 万字符会切出 `[96281, 96287, 96294, 24]` —— 一个 24 字符的碎块
    也要占一次模型调用。动态均摊让各块自然等长。
    """
    total = len(text)
    n = math.ceil(total / MAX_BATCH_CHARS)
    if n <= 1:
        return [text]

    chunks: list[str] = []
    cur: list[str] = []
    size, left_chars, left_chunks = 0, total, n
    for line in text.splitlines():
        cur.append(line)
        size += len(line) + 1
        if left_chunks > 1 and size >= left_chars / left_chunks:
            chunks.append('\n'.join(cur))
            left_chars -= size
            left_chunks -= 1
            cur, size = [], 0
    if cur:
        chunks.append('\n'.join(cur))
    return chunks


def prepare(text: str, label: str = '') -> tuple[list[str], list[str]]:
    """剔参考文献 → 仍超则切块。:return: (正文块列表, 告警列表)"""
    tag = f'{label}：' if label else ''
    text, note = drop_references(text)
    notes = [f'{tag}{note}'] if note else []

    if len(text) <= MAX_BATCH_CHARS:
        return [text], notes

    chunks = split(text)
    notes.append(f'{tag}仍有 {len(text)} 字符超过上限，已切成 {len(chunks)} 块分别抽取后合并')
    return chunks, notes


# --------------------------------------------------------------------------- 合并

_PRESENCE_RANK = {'yes': 2, 'no': 1, 'unclear': 0}


def _merge_facet(parts: list[BaseModel]) -> BaseModel:
    """合并同一 facet 在各块上的抽取结果。

    唯一需要防的是 `present='no'`（明确说没做）：分块时每块在模型眼里都像完整文献，
    很容易因为「这块里没有敏感性分析」就填 no，而 no 在判定端等于「两篇都明说没做
    = 做法一致 = dup」，一个假 no 直接造一个假 dup。所以要求它至少带条引用。
    """
    ranked = []
    for p in parts:
        present = getattr(p, 'present', 'unclear')
        if present == 'no' and not (getattr(p, 'quote', '') or '').strip():
            present = 'unclear'
        ranked.append((_PRESENCE_RANK[present], present, p))
    best = max(r for r, *_ in ranked)
    winners = [p for r, _, p in ranked if r == best]

    out = type(parts[0])()
    out.present = next(pr for r, pr, _ in ranked if r == best)
    if isinstance(getattr(parts[0], 'value', None), list):
        seen, values = set(), []
        for p in parts:                       # 列表跨全部块并集，present 等级不限制取值范围
            for v in p.value or []:
                k = str(v).strip().lower()
                if k and k not in seen:
                    seen.add(k)
                    values.append(v)
        out.value = values
        src = next((p for p in winners if p.quote.strip()), winners[0])
    else:
        src = next((p for p in winners if str(p.value).strip()), winners[0])
        out.value = src.value
    out.quote, out.quote_zh, out.section = src.quote, src.quote_zh, src.section
    return out


def merge(parts: list[BaseModel]) -> BaseModel:
    """把一个批次在各块上的结果合并成一个。单块时原样返回。"""
    if len(parts) == 1:
        return parts[0]
    merged = type(parts[0])()
    for name, field in type(parts[0]).model_fields.items():
        values = [getattr(p, name) for p in parts]
        first = values[0]
        if isinstance(first, BaseModel) and hasattr(first, 'present'):
            setattr(merged, name, _merge_facet(values))
        elif isinstance(first, list) or 'list' in str(field.annotation).lower():
            seen, out = {}, []
            for group in values:
                for item in group or []:
                    k = item.model_dump_json() if isinstance(item, BaseModel) else str(item).lower()
                    if k not in seen:
                        seen[k] = True
                        out.append(item)
            setattr(merged, name, out)
        else:
            setattr(merged, name, next((v for v in values if v is not None and v != ''), first))
    return merged
