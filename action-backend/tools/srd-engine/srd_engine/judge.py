"""P2：条目判定.

**默认一次调用判完 34 条**（`judge_granularity='all'`）。

DESIGN.md §5/§6 原设计是「一条目一次调用 + k=2 自一致投票 + 分歧仲裁，
7 条主观条目再走双证据辩护」，共 76 次调用。§11.5 要求做的消融实验做完后
该设计被推翻（2026-08-02，4 对 × 34 条目实测）：

    per_item 自己重跑两遍   95% 一致
    all      自己重跑两遍   95% 一致
    per_item vs all        90% 一致

两种模式的**自一致率完全相同**，即 76 次调用并没有换来更稳的输出；
跨模式那 5 个百分点的差异与同配置重跑的抖动无法区分。而代价是 76 倍调用、
6 倍 token。故可靠性阶梯整体删除，三种粒度统一走 `judge_batch`。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from srd_engine.evidence import build_evidence_card
from srd_engine.prompts import judge_batch_messages
from srd_engine.schemas import ExtractDoc, ItemResult, ItemVerdict, VoteRecord

if TYPE_CHECKING:
    from srd_engine.adapters.langchain_client import LlmRunner
    from srd_engine.checklist import Item
    from srd_engine.config import EngineConfig


class CodedVerdict(ItemVerdict):
    """批量判定里的单条结果（多带一个条目编号）。"""

    code: str = Field(description='条目编号，如 2a')


class BatchVerdicts(BaseModel):
    verdicts: list[CodedVerdict] = Field(description='每个条目各一条评分，顺序与题目一致')


def _apply(result: ItemResult, v: ItemVerdict) -> None:
    result.rating = v.rating
    result.reason_zh = v.reason_zh
    result.reason_en = v.reason_en
    result.cite_a, result.cite_a_zh = v.cite_a, v.cite_a_zh
    result.cite_b, result.cite_b_zh = v.cite_b, v.cite_b_zh
    result.confidence = v.confidence


def _blank(item: Item, card: str) -> ItemResult:
    return ItemResult(code=item.code, question_zh=item.question_zh,
                      question_en=item.question_en, evidence_card=card)


def match_verdicts(
    items: list[Item], verdicts: list[CodedVerdict]
) -> tuple[dict[str, CodedVerdict], str]:
    """把模型返回的若干条评分对回条目上，返回 ({条目编号: 评分}, 对位方式的说明)。

    首选按 `code` 精确对。但**有些模型压根不回填 code**（实测火山方舟上的 deepseek
    常常留空），此时按编号对会把整批判成「未返回该条目」→ 全 unclear，
    一份什么都没判出来的报告比报错更糟。
    所以条数刚好对得上时退而按顺序对位 —— 提示词里要求的本来就是「顺序与题目一致」。
    条数对不上就不猜了：能对上几条算几条，其余照旧补 unclear。
    """
    by_code = {v.code.strip(): v for v in verdicts if v.code.strip()}
    if all(it.code in by_code for it in items):
        return by_code, ''
    if len(verdicts) == len(items):
        return dict(zip((it.code for it in items), verdicts, strict=True)), '模型未回填条目编号，已按返回顺序对位'
    return by_code, ''


async def judge_batch(
    runner: LlmRunner, items: list[Item], ea: ExtractDoc, eb: ExtractDoc, cfg: EngineConfig
) -> list[ItemResult]:
    """批量判定：一次调用判完给定的若干条目。

    `per_group` 传一个分组（12 次调用），`all` 传全部 34 条（1 次调用）。
    代价是同一次调用内的羊群效应（前面打了 3 分会带偏后面），以及输出被截断时
    模型会少返条目 —— 少返的一律补成 unclear + needs_review，绝不静默。
    """
    cards = {it.code: build_evidence_card(it.code, ea, eb) for it in items}
    system, human = judge_batch_messages(items, ea, eb, cards)
    obj, err = await runner.structured(BatchVerdicts, system, human, temperature=0.0)

    by_code, how = match_verdicts(items, obj.verdicts if obj else [])
    results: list[ItemResult] = []
    for item in items:
        result = _blank(item, cards[item.code])
        got = by_code.get(item.code)
        if got is None:
            result.rating = 'unclear'
            result.needs_review = True
            result.review_note = err or '批量判定未返回该条目（多半是输出被截断）'
            result.confidence = 'low'
        else:
            _apply(result, got)
            if how:  # 顺序对位是猜的，必须留痕：人工复核时要能看出这条是怎么对上的
                result.needs_review = True
                result.review_note = how
            result.votes.append(VoteRecord(role='judge', rating=got.rating, reason_zh=got.reason_zh))
        results.append(result)
    return results


