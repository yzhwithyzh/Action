"""报告规范 checklist 逐条校验的纯算法。

做的就是投稿时那张表最后一列要填的事：**逐条判定这条在稿件里报告了没有，证据是哪段原文**。

不认识 Redis / HTTP / 队列，只依赖一个能发结构化请求的 runner（协议见 `Runner`）。
worker 负责把它跑起来、给进度、写结果。

流程::

    切窗口 → (条目分批 × 窗口) 并发判定 → 引文回原文定位 → 同条目跨窗口取最优 → 聚合完整度

    split_windows   _chunk × windows      _verdict()         _better()       summarize()
                    └ runner.structured(_batch_schema(...))

- **不给模型看行号，也不让它报行号**：模型看到的是原文本身，只负责逐字照抄引文；
  「在第几行」由 `grounding.py` 在原文里查出来。模型报的行号会错、会编（实测 qwen3.8-flash
  吐过等差数列），而且错了看不出来 —— 代码查出来的位置换什么模型都一样。
- **行号的口径**：非空行从 1 编号，空行不占号（`line_map` 是全仓唯一定义）。
  后端回填草稿、前台高亮原文都按这一套编号。
- **切窗口**：稿件超过 `window_chars` 时按行切成若干重叠窗口，每条目在每个窗口各判一次。
  默认 6 万字符（与全稿一致性同一个预算），常见论文放得下，不必切。
- **分批**：每 `batch_size` 条条目一次请求。一次只问一条太贵（78 条 × 窗口数次调用），
  一次问全部模型会偷懒漏判；默认 8 条是两者之间的折中（payload 可覆盖）。请求数 = 批数 × 窗口数。
- **取最优**：同一条目在不同窗口的判定按 reported > vague > missing 取最优 ——
  只要有一个窗口找到了证据，这条就算报告了（其余窗口判 missing 只说明「这一段里没有」）。
- **聚合**：完整度 =（已报告 × 1 + 模糊 × 0.5）/ 总条目数。

**换模型时效果不许大起大落**，所以凡是代码能定的事都不交给模型：

- **条目标签由 Schema 锁死**（`_batch_schema`）：一批 8 条在提示里标成 `[A]`…`[H]`，模型只回字母，
  代码再换算回 item_id。实测 qwen3.8-flash 发 8 条回 18 条（多出的 10 条编号是编的），
  开思考模式时把库主键 `[101]` 回成 1、2、3…… —— 主键对模型毫无意义、又紧挨着条目号「1a」，
  本来就难抄对。字母短、不与条目号里的数字混淆；重复或漏回走纠错重试。
- **Schema 在一次任务内逐字不变**，前缀缓存才命中得了。function_calling / json_schema 下 Schema
  渲染在提示词**最前面**，旧写法按批生成 `enum: [101..108]`、`[109..116]`……，每批开头都不同，
  后面整篇稿件都算未命中（实测 10 批命中 0）。现在枚举固定是 A…（批大小个字母），
  「这一批只有 A–F」（最后一批不满）由校验器兜底，越界照样走纠错重试。
- **位置由代码查**（`grounding.py`）：找不到的打标 `located='no'`，没给引文的打标
  `located='none'`，都只提示人工核对，**不改判定** —— 理由与校准数据见该模块文件头。
- **没判到 ≠ 判了没写**：一个窗口都没判到的条目挂 `UNANSWERED_REASON`，部分窗口没判到、
  最终又是 missing 的挂 `PARTIAL_REASON` —— 用户不该照着一个没人看过的结论去补稿。
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, Protocol

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field, WithJsonSchema, model_validator
from tools.checklist_worker_tool.engine.grounding import LOCATED_NA, LOCATED_PARTIAL, LOCATED_YES, Grounder

#: 判定档位。与前台第三步的三种展示状态一一对应。
REPORTED = 'reported'
VAGUE = 'vague'
MISSING = 'missing'

#: 完整度权重：模糊算半条。前台百分比就是按它算出来的。
STATUS_WEIGHT = {REPORTED: 1.0, VAGUE: 0.5, MISSING: 0.0}
STATUS_RANK = {MISSING: 0, VAGUE: 1, REPORTED: 2}
#: 同档位时按核对结论比优：找到了的 > 部分找到的 > 其余
_LOCATED_RANK = {LOCATED_YES: 2, LOCATED_PARTIAL: 1}

#: 原表里用「—」表示该条无对应内容
DASH = re.compile(r'^[—–-]+$')

#: JavaScript `\s` 的字符集。行号的「空行」判断**必须用它**而不是 Python 的 `str.strip()`：
#: 前台 `composables/manuscriptLines.ts` 用 JS 的 `trim()` 判空，两边的空白字符集差两个 ——
#: U+FEFF（BOM）JS 算空白、Python 不算；U+001F JS 不算、Python 算。只差一行，
#: 就会让前台高亮从那一行起整体错一行（txt 稿件开头带 BOM + 换行时必现）。
JS_WHITESPACE = (
    '\t\n\v\f\r \u00a0\u1680'
    '\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a'
    '\u2028\u2029\u202f\u205f\u3000\ufeff'
)


class Runner(Protocol):
    """LLM 调用协议 —— 与 srd-engine 的 `LlmRunner.structured` 同签名。"""

    async def structured(
        self, schema: type, system: str, human: str, temperature: float | None = None
    ) -> tuple[Any, str]: ...


@dataclass(frozen=True)
class ChecklistItem:
    """一条待校验的规范条目（来自 action_guideline_item）。"""

    item_id: int
    item_no: str
    domain: str
    content: str
    extension: str = ''

    def prompt_text(self, label: str) -> str:
        """喂给模型的条目描述：正文为「—」时用扩展条目顶上。

        :param label: 批内标签（`LABELS` 里的字母），模型回填它来对号入座；库主键不给模型看
        """
        body = self.content if _has_text(self.content) else self.extension
        ext = self.extension if _has_text(self.extension) and _has_text(self.content) else ''
        line = f'[{label}] {self.item_no or "-"} · {self.domain}：{body}'

        return f'{line}\n    （针刺/非药物扩展要求：{ext}）' if ext else line


@dataclass
class ItemVerdict:
    """一条条目的判定结果。"""

    item_id: int
    status: str = MISSING
    #: 引文在原文里的位置，**由代码查出**（grounding），不是模型报的
    lines: list[int] = field(default_factory=list)
    evidence: str = ''
    reason: str = ''
    #: 引文回原文定位的结论（见 grounding.LOCATED_*）：
    #: 'yes' / 'partial' 找到 · 'no' 给了引文但找不到 · 'none' 非 missing 却没给引文 · '' 无需或无从核对。
    #: 'no' 与 'none' 时前台提示人工核对 —— 只是提示，status 不因它改变
    located: str = LOCATED_NA

    def to_dict(self) -> dict[str, Any]:
        return {
            'itemId': self.item_id,
            'status': self.status,
            'lines': self.lines,
            'evidence': self.evidence,
            'reason': self.reason,
            'located': self.located,
        }


@dataclass(frozen=True)
class AuditConfig:
    """算法参数。"""

    #: 每次请求塞几条条目 —— 太多会让模型偷懒漏判，太少则调用次数翻倍
    batch_size: int = 8
    #: 单个窗口的字符预算。与全稿一致性的 `max_chars` 同为 6 万：那一层整篇一次性发给模型
    #: 跑得好好的，说明模型吃得下；这里切得越碎，「跨窗口合并」出错的机会越多
    window_chars: int = 60000
    #: 相邻窗口的重叠字符数，避免证据正好被切在边界上
    window_overlap: int = 1500
    #: 并发的判定请求数（runner 自己还有一层全局闸）
    max_concurrency: int = 4
    #: 稿件硬上限，超出直接截断并在结果里说明
    max_chars: int = 300000


#: 每条判定最多几段引文、每段多长。短而多段比一段长引文好核：模型写长了就爱用「……」拼接
MAX_QUOTES = 3
QUOTE_HINT_CHARS = 40


class _ItemJudgement(BaseModel):
    """单条判定（模型结构化输出用）。

    字段顺序是刻意的：**先引文、后结论**。模型逐字生成，先写结论再找证据，
    找不到也只能硬圆 —— 一致性那层的 severity 就是这么自相矛盾的。
    `label` 在 `_batch_schema` 里被收窄成固定的字母枚举。**没有行号字段**：位置由代码查。

    **全部字段必填、不给默认值**（没有内容时给空数组/空串）。走 function calling 的厂商
    （如火山方舟上的 deepseek）会把 Schema 里的可选字段整个省掉：实测新结构刚上时
    `quotes` 可选，deepseek 就只回「已报告」而不给引文，同一篇稿子完整度从 65% 掉到 38%。
    """

    label: str = Field(description='条目标签：给定条目前方括号里的字母，原样回填')
    quotes: list[str] = Field(
        description=(
            f'稿件中对应该条目的原文，逐字照抄，每段不超过 {QUOTE_HINT_CHARS} 字，最多 {MAX_QUOTES} 段；'
            '不要用省略号拼接，不要写「前言部分介绍了……」这类概述；未报告时给空数组'
        ),
    )
    status: Literal['reported', 'vague', 'missing'] = Field(description='判定档位')
    reason: str = Field(description='模糊或未报告的原因/补充建议；已完整报告时给空串')


def _to_label(value: Any) -> Any:
    """`"[a]"` / `" B "` / `"【C】"` → `"A"` / `"B"` / `"C"`。

    json_mode / text 路径下没有约束解码，模型常把方括号一起抄回来或写成小写，不收口的话整批解析失败。
    """
    if isinstance(value, str):
        return value.strip().strip('[]【】()（）').strip().upper()

    return value


#: 批内标签。一批最多 26 条（`batch_size` 超出时按 26 切），见 `_batch_schema`
LABELS = tuple('ABCDEFGHIJKLMNOPQRSTUVWXYZ')


def _batch_schema(labels: tuple[str, ...], batch: tuple[str, ...], *, strict: bool) -> type[BaseModel]:
    """输出结构：`label` 只能取给定的字母。

    :param labels: Schema 里的枚举，**同一次任务的每一批都传同一份**（`LABELS[:批大小]`）——
        它决定发给厂商的 Schema 文本，而 Schema 排在提示词最前面，每批一变前缀缓存就全部落空
    :param batch: 这一批实际用到的字母（最后一批不满时比 `labels` 短），只进校验器、不进 Schema

    - Schema 里**始终**写成 `{"type": "string", "enum": [...]}`。不用 `Literal`：只有一个值时
      它生成的是 `const`，有的厂商不认 `const`，会被判成「不支持这种结构化输出方式」而降级，
      降级结果还会被回写进 `ai_models`，从此所有任务都用更弱的方式。
    - json_schema / function_calling 下枚举由厂商约束解码，模型写不出别的字母；
      「属于枚举但不在这一批」与 json_mode / text 下的一切越界都由 AfterValidator 兜底 ——
      越界变成解析失败、走纠错重试（纠错消息会把报错原文摆给模型看），而不是被静默丢掉。
    - `strict=True` 时漏回也算解析失败。重试用尽仍漏的，由调用方降级到 `strict=False` 再要一次，
      接受残缺结果 —— 为一条漏回把整批八条作废不划算。两种 strict 的 Schema 文本相同，
      差别只在校验器里，所以降级重试同样吃得到缓存。
    """
    enum = list(labels)
    allowed = tuple(batch)

    def _in_batch(value: str) -> str:
        if value not in allowed:
            raise ValueError(f'label {value!r} 不在本批给定的条目里：{list(allowed)}')
        return value

    label_type = Annotated[
        str,
        BeforeValidator(_to_label),
        AfterValidator(_in_batch),
        WithJsonSchema({'type': 'string', 'enum': enum, 'description': '条目标签：给定条目前方括号里的字母，原样回填'}),
    ]

    class ItemJudgement(_ItemJudgement):
        label: label_type  # type: ignore[valid-type]

    class BatchJudgement(BaseModel):
        """一批条目的判定。"""

        items: list[ItemJudgement] = Field(default_factory=list)

        @model_validator(mode='after')
        def _complete(self) -> BatchJudgement:
            seen = [j.label for j in self.items]
            dup = sorted({i for i in seen if seen.count(i) > 1})
            if dup:
                raise ValueError(f'label 重复：{dup}；每个条目只给一个结果')
            missing = [i for i in allowed if i not in seen]
            if strict and missing:
                raise ValueError(f'漏回了这些条目：{missing}；给定的每个条目都要给出结果')
            return self

    return BatchJudgement


SYSTEM_PROMPT = (
    '你是针刺临床研究报告规范的审稿助手。给你一份稿件和若干条报告规范条目，'
    '逐条判断该条目在稿件里报告了没有。\n'
    '判定档位只有三个：\n'
    '  reported —— 稿件中有明确的对应描述；必须给出逐字引文。\n'
    '  vague    —— 提到了但描述不完整、不具体、无法据此复现；给出引文，并在 reason 里说明缺什么。\n'
    '  missing  —— 稿件中找不到对应描述；quotes 留空，在 reason 里说明应补充什么。\n'
    '每个条目先找引文、再下结论。\n'
    '硬性要求：\n'
    '  1. 只依据给定稿件判断，不得脑补、不得假设「通常都会写」。\n'
    '  2. quotes 必须是从稿件逐字照抄的原文（保持原语言，不要翻译、不要改写、不要概述）。'
    '结构性要求（如摘要是否分目的/方法/结果/结论、题目能否识别为随机试验）照抄能说明问题的'
    '小标题或题目原文即可。\n'
    '  3. 每个给定条目都要给出结果，且只给一次；label 回填条目前方括号里的字母，不得增删条目。\n'
    '  4. reason 用与条目相同的语言书写。'
)


def _has_text(s: str) -> bool:
    """有实际内容：非空，且不是原表里表示「此格无内容」的破折号。"""
    return bool(s) and not DASH.match(s.strip())


def _clean_line(raw: str) -> str:
    """去掉行尾空白；整行只有空白时返回空串。空白按 JS `\\s` 的字符集算，见 `JS_WHITESPACE`。"""
    line = raw.rstrip(JS_WHITESPACE)

    return line if line.strip(JS_WHITESPACE) else ''


def line_map(text: str) -> dict[int, str]:
    """行号 → 该行原文。

    **这是全仓「第 N 行」的唯一定义**，引文定位、后端的回填、前台的高亮都以它为准。
    单独抽出来是因为「空行不占行号」这条规则已经被踩过一次：照物理行号去取原文，
    稿件里出现第一个空行之后就整体错位，而错位**不报任何错** —— 行号仍在合法范围、
    页面照常滚过去，只是指着一段不相干的话。实测一份 2193 字的稿件：物理 77 行、
    有效 39 行。前端那份对照实现在 `action-frontend/composables/manuscriptLines.ts`：
    断行照 `str.splitlines()`，判空照 JS 的 `\\s`（见 `JS_WHITESPACE`）。

    :param text: 原始稿件
    :return: {行号: 该行原文}，行号从 1 开始，空行不占号
    """
    out: dict[int, str] = {}
    no = 0
    for raw in text.splitlines():
        line = _clean_line(raw)
        if not line:
            continue
        no += 1
        out[no] = line

    return out


def number_lines(text: str) -> tuple[str, int]:
    """给稿件编行号（带编号的全文 + 有效行数），口径与 `line_map` 相同。

    引擎自己已经不用它给模型看了（模型不接触行号）；留着是因为它是「前台面板里那列行号」
    的参照实现，`test_line_map_agrees_with_number_lines` 用它钉住两者一致。

    :param text: 原始稿件
    :return: (带行号的文本, 有效行数)
    """
    numbered: list[str] = []
    no = 0
    for raw in text.splitlines():
        line = _clean_line(raw)
        if not line:
            numbered.append('')
            continue
        no += 1
        numbered.append(f'{no:>4} | {line}')

    return '\n'.join(numbered), no


def split_windows(lines: list[str], cfg: AuditConfig) -> list[str]:
    """把稿件（非空行，按原顺序）切成若干重叠窗口；放得下就只有一个窗口。

    按整行累加，再放一行就要超 `window_chars` 时先出一个窗口，然后从末尾往回退若干整行
    （合计不超过 `window_overlap`）作为下一个窗口的开头 —— 证据正好落在边界上时，
    两个窗口里至少有一个是完整的。

    几个边界：

    - **单行超过 `window_chars` 时先按字符硬切成几段**。窗口里没有行号，劈开一行不影响定位
      （位置由代码拿引文去整篇原文里查）；不切的话这一行会被反复带进后面的窗口，
      实测一行 3000 字加 40 行短行，`window_chars=2000` 时切出 31 个窗口，同样的内容被判几十遍；
    - 回退重叠时不跨过比 `window_overlap` 还长的行；带着重叠再放不下下一行时，丢掉重叠；
    - 每个窗口至少有一行是上一个窗口没有的，不会出现只有重叠内容的窗口。
    """
    step = cfg.window_chars
    pieces = [line[i : i + step] for line in lines for i in range(0, len(line), step)]

    windows: list[str] = []
    buf: list[str] = []
    size = 0
    for piece in pieces:
        if buf and size + len(piece) + 1 > cfg.window_chars:
            windows.append('\n'.join(buf))
            back: list[str] = []
            back_size = 0
            while buf and back_size + len(buf[-1]) + 1 <= cfg.window_overlap:
                item = buf.pop()
                back.insert(0, item)
                back_size += len(item) + 1
            buf, size = back, back_size
            if size + len(piece) + 1 > cfg.window_chars:
                buf, size = [], 0
        buf.append(piece)
        size += len(piece) + 1
    if buf:
        windows.append('\n'.join(buf))

    return windows


def _chunk(items: list[ChecklistItem], size: int) -> list[list[ChecklistItem]]:
    """按原顺序每 `size` 条切一批。条目顺序来自 DAO（按 sort_num），同一张清单表的相邻条目落在同一批。"""
    return [items[i : i + size] for i in range(0, len(items), size)]


def _better(a: ItemVerdict | None, b: ItemVerdict) -> ItemVerdict:
    """同条目跨窗口取最优：档位高的赢；同档位先取引文找到了的，再取有位置的。

    `a` 为 None 表示这条还没有任何窗口判过，直接采用 `b`。**不能拿一个空的 missing 当初值**：
    同为 missing、都没有位置时比不出高下，会保留初值，模型写的「应补充什么」就被整个丢掉 ——
    改造前「理由为空的未报告」一篇有二三十条，就是这么来的。
    """
    if a is None:
        return b
    if STATUS_RANK[b.status] != STATUS_RANK[a.status]:
        return b if STATUS_RANK[b.status] > STATUS_RANK[a.status] else a
    rank_a, rank_b = _LOCATED_RANK.get(a.located, 0), _LOCATED_RANK.get(b.located, 0)
    if rank_a != rank_b:
        return b if rank_b > rank_a else a
    if not a.lines and b.lines:
        return b

    return a


#: 模型始终没给出判定的条目挂这句理由。它仍按「未报告」计（保守），但必须和
#: 「模型看过、判为没写」分得开 —— 否则用户会照着一个没人判过的结论去补稿
UNANSWERED_REASON = '模型未返回该条的判定，已按未报告处理；建议重新校验'
#: 稿件切成多个窗口、其中有窗口没判到这一条，而判到的窗口都说没写。证据可能恰好在没判到的那段里
PARTIAL_REASON = '稿件有部分片段未能完成判定，该条已按未报告处理；建议重新校验'


def _verdict(j: _ItemJudgement, item_id: int, grounder: Grounder) -> ItemVerdict:
    """把模型的一条判定收敛成结果：引文回原文定位，位置全由代码查出。

    - missing：不定位，引文与位置一律清空。模型判了没写又附上引文是自相矛盾，
      留着的话后端导入回填会把这段不相干的原文填进条目框；
    - 其余：有引文就定位；一段引文都没给时标 `none`（前台提示「未提供原文依据」），判定不改。
    """
    status = j.status if j.status in STATUS_WEIGHT else MISSING
    reason = j.reason.strip()[:400]
    if status == MISSING:
        return ItemVerdict(item_id=item_id, status=MISSING, reason=reason)

    quotes = [q.strip() for q in j.quotes if q and q.strip()][:MAX_QUOTES]
    ground = grounder.ground(quotes)

    return ItemVerdict(
        item_id=item_id,
        status=status,
        lines=ground.lines,
        evidence=' … '.join(quotes)[:200],
        reason=reason,
        located=ground.located,
    )


def _finish(
    items: list[ChecklistItem],
    best: dict[int, ItemVerdict | None],
    answered_in: dict[int, set[int]],
    window_count: int,
) -> tuple[list[ItemVerdict], list[str]]:
    """收尾：按条目顺序排出最终判定，给没判到的条目挂上明确的理由（状态仍是 missing，保守）。

    - 一个窗口都没判到 → `UNANSWERED_REASON`；
    - 最终是 missing、但有窗口没判到 → `PARTIAL_REASON`（附上判到的窗口里模型写的说明）。
      多窗口时「判了没写」只说明「判到的那几段里没有」，证据可能恰好在没判到的那段。

    :return: (判定列表, 给 errors 用的汇总说明)
    """
    unanswered, partial = 0, 0
    verdicts: list[ItemVerdict] = []
    for item in items:
        v = best[item.item_id]
        if v is None:
            v = ItemVerdict(item_id=item.item_id, reason=UNANSWERED_REASON)
            unanswered += 1
        elif v.status == MISSING and len(answered_in[item.item_id]) < window_count:
            v.reason = f'{PARTIAL_REASON}（已判定部分的说明：{v.reason}）' if v.reason else PARTIAL_REASON
            partial += 1
        verdicts.append(v)

    notes = []
    if unanswered:
        notes.append(f'{unanswered} 条条目模型未给出判定，已按未报告处理')
    if partial:
        notes.append(f'{partial} 条条目有部分片段未判定，已按未报告处理')

    return verdicts, notes


def summarize(verdicts: list[ItemVerdict]) -> dict[str, Any]:
    """聚合完整度。模糊算半条，四舍五入到整数百分比。"""
    total = len(verdicts)
    counts = {REPORTED: 0, VAGUE: 0, MISSING: 0}
    for v in verdicts:
        counts[v.status] = counts.get(v.status, 0) + 1
    score = sum(STATUS_WEIGHT.get(v.status, 0.0) for v in verdicts)

    return {
        'total': total,
        'reported': counts[REPORTED],
        'vague': counts[VAGUE],
        'missing': counts[MISSING],
        'completeness': round(score / total * 100) if total else 0,
    }


async def audit(
    runner: Runner,
    manuscript: str,
    items: list[ChecklistItem],
    cfg: AuditConfig | None = None,
    on_progress: Any = None,
) -> dict[str, Any]:
    """逐条校验稿件。

    :param runner: 能发结构化请求的调用器（协议见 `Runner`；worker 里是 srd-engine 的 LlmRunner，单测里是脚本化的假 runner）
    :param manuscript: 稿件全文
    :param items: 待校验的规范条目，顺序即输出顺序
    :param cfg: 算法参数
    :param on_progress: 可选回调 `(done, total, message)`，每完成一批（一次请求）调一次
    :return: ::

        {
          'summary':   {total, reported, vague, missing, completeness},
          'verdicts':  [ItemVerdict.to_dict(), ...]   与 items 一一对应、同序
          'lineCount': 有效行数（空行不计）,
          'windows':   切了几个窗口,
          'truncated': 稿件是否超过 max_chars 被截断,
          'errors':    最多 5 条：「N 条未作答 / 部分未判」的汇总（有的话排前面）+ 失败批次的报错,
        }

    **不抛模型错误**：单批失败只记进 errors，这批条目保持 missing 并挂上理由；只有参数本身不对
    （没有条目、稿件为空）才抛 ValueError。
    """
    cfg = cfg or AuditConfig()
    if not items:
        raise ValueError('规范条目为空，无法校验')
    text = manuscript or ''
    truncated = len(text) > cfg.max_chars
    if truncated:
        text = text[: cfg.max_chars]

    # ── 准备：行号口径、切窗、分批。定位器按截断后的文本建，与模型看到的内容同源
    lines_by_no = line_map(text)
    line_count = len(lines_by_no)
    if not line_count:
        raise ValueError('稿件为空')
    windows = split_windows(list(lines_by_no.values()), cfg)
    size = min(cfg.batch_size, len(LABELS))
    batches = _chunk(items, size)
    #: 每批 Schema 的枚举都是这一份，见 `_batch_schema`
    labels = LABELS[:size]
    grounder = Grounder(lines_by_no)

    # ── 共享状态（多个协程并发写，统一在 lock 里改）
    #: 每条目目前的最优判定；None = 还没有任何窗口判过
    best: dict[int, ItemVerdict | None] = {i.item_id: None for i in items}
    #: 每条目在哪几个窗口里拿到过判定。只要有窗口没判到、最终又是 missing，就不能当成「看过、确实没写」
    answered_in: dict[int, set[int]] = {i.item_id: set() for i in items}
    errors: list[str] = []
    # 一个 job = 一批条目 × 一个窗口 = 一次模型请求
    jobs = [(bi, batch, wi, win) for bi, batch in enumerate(batches) for wi, win in enumerate(windows)]
    done = 0
    lock = asyncio.Lock()
    # 引擎自己的并发闸；runner 里还有一道全局闸，两者取小
    sem = asyncio.Semaphore(max(1, cfg.max_concurrency))

    async def run_one(batch: list[ChecklistItem], window: str, wi: int) -> None:
        """跑一个 job：发请求 → 收敛每条判定 → 与该条目已有的判定比优。"""
        nonlocal done
        # 稿件在前、待判条目在后（长上下文提示的常见排法：问题离作答位置更近）。
        # 「本片段为第 x/y 段」让模型知道自己只看到一部分，没找到的就判 missing，别脑补
        part = f'，本片段为第 {wi + 1}/{len(windows)} 段' if len(windows) > 1 else ''
        human = f'稿件{part}：\n-----\n{window}\n-----\n\n待判定的报告规范条目：\n' + '\n'.join(
            it.prompt_text(labels[k]) for k, it in enumerate(batch)
        )
        #: 批内字母 → 库主键。模型只看得到字母，换算由代码做
        by_label = {labels[k]: it.item_id for k, it in enumerate(batch)}
        in_batch = tuple(by_label)
        async with sem:
            # 严格结构：标签必须齐全、不重复、不越界。不满足时 runner 会带着报错原文做纠错重试
            parsed, err = await runner.structured(_batch_schema(labels, in_batch, strict=True), SYSTEM_PROMPT, human)
            if err:
                # 纠错重试用尽仍不齐（多半是漏回）：放宽到「允许残缺」再要一次，能拿回几条是几条。
                # 注意：若 err 是网络/全池冻结这类错误，这一次多半同样失败 —— 代价是故障时多等一轮，
                # 换来的是「漏回一条就整批作废」不会发生
                parsed, err = await runner.structured(
                    _batch_schema(labels, in_batch, strict=False), SYSTEM_PROMPT, human
                )
        async with lock:
            done += 1
            if err:
                errors.append(err)
            elif parsed is not None:
                # 标签已由 Schema 与校验器约束；这里再过滤一遍是纯防御
                for j in parsed.items:
                    item_id = by_label.get(j.label)
                    if item_id is None:
                        continue
                    answered_in[item_id].add(wi)
                    best[item_id] = _better(best[item_id], _verdict(j, item_id, grounder))
            if on_progress:
                on_progress(done, len(jobs), f'已判定 {done}/{len(jobs)} 批')

    # 先预热、再并发：每个窗口的第一批单独先发，跑完厂商那边才有这段前缀的缓存；
    # 一起起跑的话头几个请求谁也吃不到谁的（实测并发 4 时前 4 批命中 0、之后每批命中 85%+）。
    # 代价是多等一次请求的时间（约 10 秒）。真正的并发度由 sem 与 runner 的闸决定
    warmup = [j for j in jobs if j[0] == 0]
    await asyncio.gather(*(run_one(batch, win, wi) for _, batch, wi, win in warmup))
    await asyncio.gather(*(run_one(batch, win, wi) for bi, batch, wi, win in jobs if bi != 0))

    verdicts, notes = _finish(items, best, answered_in, len(windows))
    # 汇总放在最前面：errors 最多留 5 条，排在后面的话批次失败一多，这几条恰好被截掉
    errors[:0] = notes

    return {
        'summary': summarize(verdicts),
        'verdicts': [v.to_dict() for v in verdicts],
        'lineCount': line_count,
        'windows': len(windows),
        'truncated': truncated,
        'errors': errors[:5],
    }
