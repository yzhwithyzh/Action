"""报告规范 checklist 逐条校验的纯算法。

做的就是投稿时那张表最后一列要填的事：**逐条判定这条在稿件里报告了没有，报在第几行**。

不认识 Redis / HTTP / 队列，只依赖一个能发结构化请求的 runner（协议见 `Runner`）。
worker 负责把它跑起来、给进度、写结果。

流程::

    编行号 → 切窗口 → (条目分批 × 窗口) 并发判定 → 同条目跨窗口取最优 → 聚合完整度

窗口：稿件超过 `window_chars` 时按行切成若干重叠窗口，每条目在每个窗口各判一次。
同一条目在不同窗口的判定按 reported > vague > missing 取最优 —— 只要有一个窗口
找到了证据，这条就算报告了；行号是全稿真实行号，不受切窗影响。
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel, Field

#: 判定档位。与前台第三步的三种展示状态一一对应。
REPORTED = 'reported'
VAGUE = 'vague'
MISSING = 'missing'

#: 完整度权重：模糊算半条。前台百分比就是按它算出来的。
STATUS_WEIGHT = {REPORTED: 1.0, VAGUE: 0.5, MISSING: 0.0}
STATUS_RANK = {MISSING: 0, VAGUE: 1, REPORTED: 2}

#: 原表里用「—」表示该条无对应内容
DASH = re.compile(r'^[—–-]+$')


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

    def prompt_text(self) -> str:
        """喂给模型的条目描述：正文为「—」时用扩展条目顶上。"""
        body = self.content if _has_text(self.content) else self.extension
        ext = self.extension if _has_text(self.extension) and _has_text(self.content) else ''
        line = f'[{self.item_id}] {self.item_no or "-"} · {self.domain}：{body}'

        return f'{line}\n    （针刺/非药物扩展要求：{ext}）' if ext else line


@dataclass
class ItemVerdict:
    """一条条目的判定结果。"""

    item_id: int
    status: str = MISSING
    lines: list[int] = field(default_factory=list)
    evidence: str = ''
    reason: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'itemId': self.item_id,
            'status': self.status,
            'lines': self.lines,
            'evidence': self.evidence,
            'reason': self.reason,
        }


@dataclass(frozen=True)
class AuditConfig:
    """算法参数。"""

    #: 每次请求塞几条条目 —— 太多会让模型偷懒漏判，太少则调用次数翻倍
    batch_size: int = 8
    #: 单个窗口的字符预算
    window_chars: int = 24000
    #: 相邻窗口的重叠字符数，避免证据正好被切在边界上
    window_overlap: int = 1500
    #: 并发的判定请求数（runner 自己还有一层全局闸）
    max_concurrency: int = 4
    #: 稿件硬上限，超出直接截断并在结果里说明
    max_chars: int = 300000


class _ItemJudgement(BaseModel):
    """单条判定（模型结构化输出用）。"""

    item_id: int = Field(description='条目 id，原样回填')
    status: str = Field(description="judgement: 'reported' | 'vague' | 'missing'")
    lines: list[int] = Field(default_factory=list, description='报告所在行号，可多个；未报告时留空')
    evidence: str = Field(default='', description='稿件中的原文片段，不超过 80 字；未报告时留空')
    reason: str = Field(default='', description='模糊或未报告的原因/补充建议；已完整报告时留空')


class _BatchJudgement(BaseModel):
    """一批条目的判定。"""

    items: list[_ItemJudgement] = Field(default_factory=list)


SYSTEM_PROMPT = (
    '你是针刺临床研究报告规范的审稿助手。给你一份稿件（每行已编号）和若干条报告规范条目，'
    '逐条判断该条目在稿件里报告了没有。\n'
    '判定档位只有三个：\n'
    '  reported —— 稿件中有明确、可定位的对应描述；必须给出行号与原文片段。\n'
    '  vague    —— 提到了但描述不完整、不具体、无法据此复现；给出行号，并在 reason 里说明缺什么。\n'
    '  missing  —— 稿件中找不到对应描述；lines 留空，在 reason 里说明应补充什么。\n'
    '硬性要求：\n'
    '  1. 只依据给定稿件判断，不得脑补、不得假设「通常都会写」。\n'
    '  2. 行号必须真实取自稿件的行号标记，不确定就降级为 vague 或 missing，不要编造行号。\n'
    '  3. 每个给定条目都要给出结果，item_id 原样回填，不得增删条目。\n'
    '  4. reason 用与条目相同的语言书写。'
)


def _has_text(s: str) -> bool:
    return bool(s) and not DASH.match(s.strip())


def line_map(text: str) -> dict[int, str]:
    """行号 → 该行原文。

    **这是全仓「第 N 行」的唯一定义**，`number_lines` 与后端的回填都走它。
    单独抽出来是因为「空行不占行号」这条规则已经被踩过一次：照物理行号去取原文，
    稿件里出现第一个空行之后就整体错位，而错位**不报任何错** —— 行号仍在合法范围、
    页面照常滚过去，只是指着一段不相干的话。实测一份 2193 字的稿件：物理 77 行、
    有效 39 行。前端那份对照实现在 `action-frontend/composables/manuscriptLines.ts`。

    :param text: 原始稿件
    :return: {行号: 该行原文}，行号从 1 开始，空行不占号
    """
    out: dict[int, str] = {}
    no = 0
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        no += 1
        out[no] = line

    return out


def number_lines(text: str) -> tuple[str, int]:
    """给稿件编行号。

    行号是 checklist 最后一列「报告于第几行」的载体，也是模型定位证据的唯一锚点。
    空行保留但不编号，避免行号被大量空行撑开。

    :param text: 原始稿件
    :return: (带行号的文本, 有效行数)
    """
    numbered: list[str] = []
    no = 0
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            numbered.append('')
            continue
        no += 1
        numbered.append(f'{no:>4} | {line}')

    return '\n'.join(numbered), no


def split_windows(numbered: str, cfg: AuditConfig) -> list[str]:
    """把带行号的稿件切成若干重叠窗口；放得下就只有一个窗口。"""
    if len(numbered) <= cfg.window_chars:
        return [numbered]

    lines = numbered.split('\n')
    windows: list[str] = []
    buf: list[str] = []
    size = 0
    for line in lines:
        buf.append(line)
        size += len(line) + 1
        if size >= cfg.window_chars:
            windows.append('\n'.join(buf))
            # 回退若干行做重叠
            back: list[str] = []
            back_size = 0
            while buf and back_size < cfg.window_overlap:
                item = buf.pop()
                back.insert(0, item)
                back_size += len(item) + 1
            buf = back
            size = back_size
    if buf:
        windows.append('\n'.join(buf))

    return windows


def _chunk(items: list[ChecklistItem], size: int) -> list[list[ChecklistItem]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _better(a: ItemVerdict, b: ItemVerdict) -> ItemVerdict:
    """同条目跨窗口取最优：档位高的赢，同档位取有行号的。"""
    if STATUS_RANK[b.status] > STATUS_RANK[a.status]:
        return b
    if STATUS_RANK[b.status] == STATUS_RANK[a.status] and not a.lines and b.lines:
        return b

    return a


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

    :param runner: 能发结构化请求的调用器
    :param manuscript: 稿件全文
    :param items: 待校验的规范条目
    :param cfg: 算法参数
    :param on_progress: 可选回调 `(done, total, message)`，用于上报进度
    :return: {'summary': {...}, 'verdicts': [...], 'lineCount': n, 'windows': n, 'truncated': bool}
    """
    cfg = cfg or AuditConfig()
    if not items:
        raise ValueError('规范条目为空，无法校验')
    text = manuscript or ''
    truncated = len(text) > cfg.max_chars
    if truncated:
        text = text[: cfg.max_chars]

    numbered, line_count = number_lines(text)
    if not line_count:
        raise ValueError('稿件为空')
    windows = split_windows(numbered, cfg)
    batches = _chunk(items, cfg.batch_size)

    # 兜底：模型没回的条目按「未报告」处理，绝不因为漏回而显示成已报告
    best: dict[int, ItemVerdict] = {i.item_id: ItemVerdict(item_id=i.item_id) for i in items}
    errors: list[str] = []
    jobs = [(bi, batch, wi, win) for bi, batch in enumerate(batches) for wi, win in enumerate(windows)]
    done = 0
    lock = asyncio.Lock()
    sem = asyncio.Semaphore(max(1, cfg.max_concurrency))

    async def run_one(batch: list[ChecklistItem], window: str, wi: int) -> None:
        nonlocal done
        human = (
            f'稿件（共 {line_count} 行，本片段为第 {wi + 1}/{len(windows)} 段，行号即全稿行号）：\n'
            f'-----\n{window}\n-----\n\n'
            '待判定的报告规范条目：\n' + '\n'.join(it.prompt_text() for it in batch)
        )
        async with sem:
            parsed, err = await runner.structured(_BatchJudgement, SYSTEM_PROMPT, human)
        async with lock:
            done += 1
            if err:
                errors.append(err)
            elif parsed is not None:
                allowed = {it.item_id for it in batch}
                for j in parsed.items:
                    if j.item_id not in allowed:
                        continue
                    status = j.status if j.status in STATUS_WEIGHT else MISSING
                    cand = ItemVerdict(
                        item_id=j.item_id,
                        status=status,
                        lines=[n for n in j.lines if 1 <= n <= line_count],
                        evidence=j.evidence.strip()[:200],
                        reason=j.reason.strip()[:400],
                    )
                    best[j.item_id] = _better(best[j.item_id], cand)
            if on_progress:
                on_progress(done, len(jobs), f'已判定 {done}/{len(jobs)} 批')

    await asyncio.gather(*(run_one(batch, win, wi) for _, batch, wi, win in jobs))

    verdicts = [best[i.item_id] for i in items]

    return {
        'summary': summarize(verdicts),
        'verdicts': [v.to_dict() for v in verdicts],
        'lineCount': line_count,
        'windows': len(windows),
        'truncated': truncated,
        'errors': errors[:5],
    }
