"""正文预处理与超长兜底（overlong.py）：剔参考文献 → 仍超则分块合并。

两步都**只在超长时触发**。常规期刊综述（3.6 万–8.6 万字符）一步都走不到，
所以这里刻意用超过上限的合成输入来压出这两条路径。
"""

from __future__ import annotations

from srd_engine.extract import batch_text
from srd_engine.overlong import MAX_BATCH_CHARS, drop_references, merge, split
from srd_engine.schemas import (
    IncludedStudy,
    ListFacet,
    MethodFacets,
    ParsedDoc,
    ParsedPage,
    ResultFacets,
    TextFacet,
)


def _doc(text: str) -> ParsedDoc:
    return ParsedDoc(source='t', sha256='x', page_count=1, pages=[ParsedPage(no=1, text=text)])


def _body(n: int) -> str:
    return '\n'.join(f'第 {i} 行正文：本研究纳入随机对照试验比较针刺与常规治疗。' for i in range(n))


# --------------------------------------------------------------------------- 不超长时零介入


def test_references_are_always_dropped():
    """参考文献一律剔除，不论长短 —— 它对 34 条目的判定没有贡献却占全文 17%–33%。"""
    doc = _doc(_body(200) + '\nReferences\n[1] Zhang. Some paper. 2020;1:1-9.')
    chunks, notes = batch_text(doc, 'topic')
    assert len(chunks) == 1                       # 常规长度不分块
    assert 'References' not in chunks[0]
    assert 'Zhang. Some paper' not in chunks[0]
    assert any('已剔除参考文献段' in n for n in notes)


def test_normal_length_is_not_chunked():
    doc = _doc(_body(200))
    chunks, _ = batch_text(doc, 'topic')
    assert len(chunks) == 1
    assert chunks[0] == doc.full_text             # 没有参考文献可剔时正文一字不改


# --------------------------------------------------------------------------- 第一步：剔参考文献


def test_references_dropped_only_when_oversized():
    body = _body(60_000)                              # 远超上限
    text = body + '\nReferences\n' + _body(2_000)
    doc = _doc(text)
    _chunks, notes = batch_text(doc, 'topic')
    assert any('超过上限' in n for n in notes)
    assert any('已剔除参考文献段' in n for n in notes)


def test_drop_references_takes_the_last_title():
    text = 'References\n' + _body(100) + '\nReferences\n尾部条目'
    out, note = drop_references(text)
    assert out.count('References') == 1               # 只砍最后一个标题之后的内容
    assert '尾部条目' not in out
    assert '已剔除' in note


def test_drop_references_ignores_titles_in_the_first_40_percent():
    text = _body(10) + '\nReferences\n' + _body(200)
    out, note = drop_references(text)
    assert out == text
    assert '未找到' in note


def test_drop_references_aborts_when_cut_is_too_large():
    """砍掉超过 60% 说明八成认错了 —— 宁可不剔，也不能把正文挖掉。

    要触发它，尾部的行必须比正文行长得多（真实的参考文献条目正是如此）；
    行长均匀时 `_REF_SEARCH_FLOOR` 已经蕴含了 cut ≤ 60%，闸门不会触发。
    """
    head = '\n'.join(f'短正文{i}' for i in range(100))
    tail = '\n'.join(f'[{i}] Koppen IJ, Vriesman MH, Saps M, et al. ' + 'x' * 160 for i in range(100))
    text = f'{head}\nReferences\n{tail}'
    out, note = drop_references(text)
    assert out == text
    assert '安全闸' in note


def test_no_reference_title_leaves_text_alone():
    out, note = drop_references(_body(100))
    assert out == _body(100)
    assert '未找到' in note


# --------------------------------------------------------------------------- 第二步：分块


def test_split_covers_everything_and_respects_limit():
    text = _body(120_000)
    chunks = split(text)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= MAX_BATCH_CHARS
    # 不丢内容：拼回去与原文等价（只差块间换行）
    assert '\n'.join(chunks).replace('\n', '') == text.replace('\n', '')


def test_split_returns_single_chunk_when_within_limit():
    assert split('短正文') == ['短正文']


def test_split_does_not_leave_a_tiny_tail_chunk():
    """按 n 份等分时末尾会溢出几十字符的碎块，留余量避免。"""
    chunks = split('\n'.join('x' * 60 for _ in range(6000)))
    assert len(chunks) > 1
    assert min(len(c) for c in chunks) > MAX_BATCH_CHARS // 4


def test_oversized_after_dropping_references_gets_chunked():
    text = _body(60_000) + '\nReferences\n' + _body(100)
    doc = _doc(text)
    chunks, notes = batch_text(doc, 'topic')
    assert len(chunks) > 1
    assert any('已切成' in n for n in notes)


# --------------------------------------------------------------------------- 合并


def test_single_part_returns_as_is():
    a = MethodFacets(databases=ListFacet(value=['PubMed'], present='yes'))
    assert merge([a]) is a


def test_lists_union_across_all_parts_regardless_of_present():
    """块 5 的 present='unclear' 不该让它抽到的库被丢掉 —— 召回优先。"""
    a = MethodFacets(databases=ListFacet(value=['PubMed', 'Embase'], present='yes'))
    b = MethodFacets(databases=ListFacet(value=['embase', 'CNKI'], present='unclear'))
    merged = merge([a, b])
    assert [x.lower() for x in merged.databases.value] == ['pubmed', 'embase', 'cnki']
    assert merged.databases.present == 'yes'


def test_yes_beats_unclear():
    a = MethodFacets(search_date_range=TextFacet(present='unclear'))
    b = MethodFacets(search_date_range=TextFacet(value='2000-2023', quote='from 2000', present='yes'))
    merged = merge([a, b])
    assert merged.search_date_range.present == 'yes'
    assert merged.search_date_range.value == '2000-2023'


def test_no_without_quote_is_downgraded():
    """分块路径唯一的假 no 防线：说「明确未做」至少得给条引用。"""
    a = MethodFacets(search_structure=TextFacet(value='未做', quote='', present='no'))
    merged = merge([a, MethodFacets()])
    assert merged.search_structure.present == 'unclear'


def test_no_with_quote_is_kept():
    a = MethodFacets(search_structure=TextFacet(
        value='未做敏感性分析', quote='No sensitivity analysis was performed', present='no'))
    merged = merge([a, MethodFacets()])
    assert merged.search_structure.present == 'no'


def test_object_lists_are_deduped():
    a = ResultFacets(included_studies=[IncludedStudy(first_author='Zhang', year=2019)])
    b = ResultFacets(included_studies=[IncludedStudy(first_author='Zhang', year=2019),
                                       IncludedStudy(first_author='Li', year=2020)])
    merged = merge([a, b])
    assert len(merged.included_studies) == 2


def test_scalar_takes_first_non_empty():
    parts = [ResultFacets(included_count_reported=None),
             ResultFacets(included_count_reported=18)]
    assert merge(parts).included_count_reported == 18
