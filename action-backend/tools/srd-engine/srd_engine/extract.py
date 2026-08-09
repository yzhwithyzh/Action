"""P1：单篇结构化抽取（facet extraction）—— 唯一职责是编排 4 个批次的模型调用。

一篇综述抽一次，之后 34 条判定都只吃 facet 切片，不再回读全文。

配套但不属于本模块的两件事：
- 正文预处理与超长切块、分块结果合并 → `overlong.py`（纯代码）
- 结果的磁盘缓存                     → `cache.py`（唯一碰文件系统的地方）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from srd_engine import overlong
from srd_engine.config import PROMPT_VERSION, EngineConfig
from srd_engine.prompts import extract_messages
from srd_engine.schemas import (
    ExtractDoc,
    MethodFacets,
    ParsedDoc,
    QualityFacets,
    ResultFacets,
    TopicFacets,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

    from srd_engine.adapters.langchain_client import LlmRunner

# 每个批次抽哪些字段。默认整篇喂给模型，`extract_scope='sections'` 时才按这张表挑章节 ——
# 实测挑章节会静默丢掉关键段落（字段填充率 70% vs 全文 87%），保留只为对照，不推荐。
_BATCH_SECTIONS: dict[str, tuple[str, ...]] = {
    'topic': ('abstract', 'introduction', 'background', 'method', 'eligibility', 'inclusion',
              '摘要', '前言', '背景', '方法', '纳入'),
    'method': ('method', 'search', 'information sources', 'data', 'effect measures', 'study selection',
               '方法', '检索', '资料', '数据', '统计'),
    'result': ('result', 'study characteristics', 'meta-analys', 'subgroup', 'sensitivity', 'synthesis',
               'discussion', '结果', '亚组', '敏感性', '讨论'),
    'quality': ('risk of bias', 'grade', 'certainty', 'publication bias', 'funding', 'interest',
                'limitation', 'discussion', '偏倚', '质量', '利益冲突', '局限', '讨论'),
}
#: 失败或抽空的批次最多补跑几轮（含首轮）。
#:
#: 值得多补几轮：抽取是「一篇抽一次、34 条判定都吃这一份 facet」，一个批次抽空，
#: 这篇参与的**每一对**配对的对应条目全判 unclear —— 一次失败被放大几十倍。
#: 而补跑只重跑失败的那个批次（1 次调用），比在判定层加重试便宜得多。
#: 实测 10 对那轮：6 次抽空里第 2 轮救回 3 次，剩下 3 次的 result 批次直接
#: 造成 90 条 unclear（占全部 unclear 的一半）。
MAX_EXTRACT_ROUNDS = 3

BATCH_SCHEMA: dict[str, type[BaseModel]] = {
    'topic': TopicFacets,
    'method': MethodFacets,
    'result': ResultFacets,
    'quality': QualityFacets,
}


def batch_text(doc: ParsedDoc, batch: str, scope: str = 'full') -> tuple[list[str], list[str]]:
    """取该批次要喂给模型的正文（已剔参考文献，超长已切块）。

    :return: (正文块列表, 告警列表)
    """
    text = (
        doc.section_text(*_BATCH_SECTIONS[batch], fallback_all=True)
        if scope == 'sections'
        else doc.full_text
    )
    return overlong.prepare(text, label=f'批次 {batch}')


def is_empty_facets(facets: BaseModel) -> bool:
    """整批 facet 一个字段都没抽到。

    对一篇真实的系统综述来说这不可能是真相 —— 总得有个研究目标、总得检索过什么数据库。
    所以「返回了合法结构但全是空的」只能是模型在长输入下吐了个空壳（实测某些国产
    OpenAI 兼容端点会这样，不报错、HTTP 200、字段全空）。这种批次必须重试，
    否则空壳会被当成正常结果缓存下来，之后每次判定都从这份空壳里读，全篇判 unclear。
    """
    for value in facets.model_dump().values():
        if isinstance(value, dict):          # TextFacet / ListFacet
            if value.get('present') != 'unclear' or value.get('value'):
                return False
        elif value:                          # 列表字段（纳入研究、合并效应量…）与标量
            return False
    return True


async def _run_batches(
    runner: LlmRunner, batches: list[str], plan: dict[str, tuple[list[str], list[str]]], title: str
) -> dict[str, list]:
    """把给定批次（含超长切块）并发跑一遍，返回 {批次: [(对象, 错误), ...]}。"""
    jobs = [(b, t) for b in batches for t in plan[b][0]]
    raw = await runner.gather([
        runner.structured(BATCH_SCHEMA[b], *extract_messages(b, title, t, fragment=len(plan[b][0]) > 1),
                          temperature=0.0)
        for b, t in jobs
    ])
    got: dict[str, list] = {b: [] for b in batches}
    for (b, _), item in zip(jobs, raw, strict=True):
        got[b].append(item)
    return got


def _merge_batch(got: dict[str, list], batch: str) -> tuple[BaseModel | None, str]:
    """合并某批次的各块结果，返回 (合并后的 facet 或 None, 告警)。"""
    good = [obj for obj, err in got[batch] if obj is not None and not err]
    if not good:
        return None, f'抽取批次 {batch} 失败：{next((e for _, e in got[batch] if e), "无返回")}'
    note = (
        f'批次 {batch}：{len(got[batch])} 块中 {len(got[batch]) - len(good)} 块失败，按剩余块合并'
        if len(good) < len(got[batch]) else ''
    )
    return overlong.merge(good), note


async def extract_doc(
    runner: LlmRunner,
    doc: ParsedDoc,
    title: str = '',
    cfg: EngineConfig | None = None,
) -> tuple[ExtractDoc, list[str]]:
    """4 个批次并发抽取，返回 (ExtractDoc, 告警列表)。

    正常情况下就是 4 次调用；失败或抽空的批次会补跑（见 `MAX_EXTRACT_ROUNDS`
    与 `is_empty_facets`），只有超长文献才会因切块而更多。
    最终仍没抽出来的批次记在 `notes` 里，`ExtractDoc.failed_batches` 读得到 ——
    调用方据此决定要不要写缓存（`pipeline.prepare_extract` 就是这么做的）。
    """
    cfg = cfg or EngineConfig()
    batches = list(BATCH_SCHEMA)
    plan = {b: batch_text(doc, b, cfg.extract_scope) for b in batches}
    warnings: list[str] = [n for b in batches for n in plan[b][1]]

    extract = ExtractDoc(
        source=doc.source,
        sha256=doc.sha256,
        title=title,
        prompt_version=PROMPT_VERSION,
        model=runner.cfg.model,
    )

    pending, notes = batches, {}
    for attempt in range(1, MAX_EXTRACT_ROUNDS + 1):
        got = await _run_batches(runner, pending, plan, title)
        failed = []
        for batch in pending:
            merged, note = _merge_batch(got, batch)
            notes[batch] = note
            if merged is None or is_empty_facets(merged):
                failed.append(batch)
                if merged is not None:
                    notes[batch] = f'抽取批次 {batch} 返回空结果（字段全空）'
                continue
            setattr(extract, batch, merged)
        if not failed or attempt == MAX_EXTRACT_ROUNDS:
            pending = failed
            break
        warnings.append(f'抽取批次 {"、".join(failed)} 失败或抽空，重试（第 {attempt + 1}/{MAX_EXTRACT_ROUNDS} 轮）')
        pending = failed

    warnings.extend(n for n in notes.values() if n)
    extract.token_in, extract.token_out = runner.token_in, runner.token_out
    # 告警随 facet 一起落盘 —— 否则缓存命中时审计痕迹全部丢失
    extract.notes = list(warnings)
    return extract, warnings
