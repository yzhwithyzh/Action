"""成果发表元数据解析的单测（不连库、不连网、不调模型）。

盯的是几件「错了会安静地毁掉一条记录」的事：

- **DOI 要抠得出、也要抠得干净**：多一个句号、少剥一层 `https://doi.org/`，
  前台就会拼出 `https://doi.org/https://doi.org/10.x/y` 这种死链，或者 Crossref 查不到。
- **作者顺序即署名顺序**：任何重排都是学术事故；机构下标错位则会给作者挂上别人的单位，
  而这种错在页面上长得完全正常（角标是个合法数字），只有作者本人看得出来。
- **模型的出参不可信**：JSON 围栏、字符串数组、越界的 affiliationIndex、"2024年" 这种
  年份都真实出现过。收不干净就会写进库，且没人会再核一遍。

跑法：python -m pytest tools/tests/test_publication_parse.py -q
"""

from __future__ import annotations

import pytest
from module_action.service.publication_parse import (
    build_citation_text,
    build_pdf_messages,
    extract_doi,
    from_crossref,
    parse_ai_json,
    parse_pubmed_xml,
    strip_jats,
)

# --------------------------------------------------------------------------- DOI


@pytest.mark.parametrize(
    ('source', 'expected'),
    [
        ('10.1016/j.ctim.2024.103041', '10.1016/j.ctim.2024.103041'),
        ('https://doi.org/10.1016/j.ctim.2024.103041', '10.1016/j.ctim.2024.103041'),
        ('http://dx.doi.org/10.1001/jama.2023.1234', '10.1001/jama.2023.1234'),
        ('doi: 10.1001/jama.2023.1234', '10.1001/jama.2023.1234'),
        # 出版社页面地址里嵌着 DOI（ScienceDirect / Springer 都是这个形态）
        ('https://link.springer.com/article/10.1007/s11655-023-3608-1', '10.1007/s11655-023-3608-1'),
        ('  10.1016/J.CTIM.2024.103041  ', '10.1016/J.CTIM.2024.103041'),
    ],
)
def test_extract_doi_forms(source: str, expected: str) -> None:
    """DOI、doi: 前缀、doi.org 链接、以及嵌在出版社地址里的，四种都要认。"""
    assert extract_doi(source) == expected


def test_extract_doi_strips_trailing_punctuation() -> None:
    """从正文里粘出来的 DOI 常带着句末标点，留着会让 Crossref 404。"""
    assert extract_doi('见 10.1016/j.ctim.2024.103041。') == '10.1016/j.ctim.2024.103041'
    assert extract_doi('(10.1001/jama.2023.1234)') == '10.1001/jama.2023.1234'


def test_extract_doi_returns_empty_for_plain_url() -> None:
    """不含 DOI 的网址要抠不出来 —— 上层据此报「请手动填写」，而不是去抓这个网址。"""
    assert extract_doi('https://www.example.com/articles/12345') == ''
    assert extract_doi('') == ''


# --------------------------------------------------------------------------- JATS 摘要


def test_strip_jats_keeps_structured_headings_readable() -> None:
    """结构化摘要的小标题是独立标签，直接去标签会把它和正文粘成一句。"""
    raw = (
        '<jats:p><jats:title>Background</jats:title>Acupuncture is widely used.'
        '<jats:title>Methods</jats:title>We searched 5 databases.</jats:p>'
    )
    text = strip_jats(raw)
    assert 'Background：' in text
    assert 'BackgroundAcupuncture' not in text
    assert 'We searched 5 databases.' in text
    assert '<' not in text


def test_strip_jats_drops_leading_abstract_word() -> None:
    """Crossref 的摘要常以「Abstract」开头，留着等于在摘要框里写「摘要」。"""
    assert strip_jats('<jats:p>Abstract Acupuncture works.</jats:p>').startswith('Acupuncture')


def test_strip_jats_on_empty() -> None:
    assert strip_jats(None) == ''
    assert strip_jats('') == ''


# --------------------------------------------------------------------------- Crossref


def _crossref_message() -> dict:
    """一份删繁就简的 Crossref message，字段形态与真实出参一致。"""
    return {
        'title': ['Acupuncture for chronic pain: a systematic review'],
        'author': [
            {
                'given': 'San',
                'family': 'Zhang',
                'affiliation': [{'name': 'Guangzhou University of Chinese Medicine'}],
            },
            {'given': 'Si', 'family': 'Li', 'affiliation': [{'name': 'Kyung Hee University'}]},
            # 第三位与第一位同单位：去重后应共用下标 0
            {'given': 'Wu', 'family': 'Wang', 'affiliation': [{'name': 'Guangzhou University of Chinese Medicine'}]},
            # 没标机构
            {'given': 'Liu', 'family': 'Chen', 'affiliation': []},
        ],
        'abstract': '<jats:p>Acupuncture reduces pain.</jats:p>',
        'container-title': ['Complementary Therapies in Medicine'],
        'volume': '80',
        'issue': '3',
        'page': '103041',
        'published-print': {'date-parts': [[2024, 5, 1]]},
        'created': {'date-parts': [[2026, 1, 1]]},
        'DOI': '10.1016/j.ctim.2024.103041',
        'URL': 'https://doi.org/10.1016/j.ctim.2024.103041',
        'subject': ['Complementary and alternative medicine'],
    }


def test_from_crossref_maps_fields() -> None:
    fields = from_crossref(_crossref_message())
    assert fields['title'] == 'Acupuncture for chronic pain: a systematic review'
    assert fields['journal'] == 'Complementary Therapies in Medicine'
    assert fields['volume'] == '80'
    assert fields['issue'] == '3'
    assert fields['pages'] == '103041'
    assert fields['doi'] == '10.1016/j.ctim.2024.103041'
    assert fields['abstract'] == 'Acupuncture reduces pain.'


def test_from_crossref_preserves_author_order() -> None:
    """署名顺序有学术含义，映射不许重排。"""
    names = [a['name'] for a in from_crossref(_crossref_message())['authors']]
    assert names == ['San Zhang', 'Si Li', 'Wu Wang', 'Liu Chen']


def test_from_crossref_dedupes_affiliations_and_indexes_them() -> None:
    """同一家单位在每位作者下都会重复出现，去重后用下标关联；没标机构的必须是 None。"""
    fields = from_crossref(_crossref_message())
    assert fields['affiliations'] == ['Guangzhou University of Chinese Medicine', 'Kyung Hee University']
    assert [a['affiliation_index'] for a in fields['authors']] == [0, 1, 0, None]


def test_from_crossref_year_prefers_published_over_created() -> None:
    """`created` 是 Crossref 自己的建档时间，取它会把 2024 年的论文标成入库那年。"""
    assert from_crossref(_crossref_message())['publication_year'] == 2024


def test_from_crossref_year_falls_back_to_issued() -> None:
    message = {'title': ['x'], 'issued': {'date-parts': [[2019, 2]]}}
    assert from_crossref(message)['publication_year'] == 2019


def test_from_crossref_never_fills_keywords() -> None:
    """
    Crossref 的 `subject` 是**期刊级学科分类**，不是论文的作者关键词，填进关键词框是错的；
    何况它 2023 年起已被 Crossref 从出参撤下（实测一律 `[]`）。关键词这一项由 PubMed 补。
    """
    message = _crossref_message()
    message['subject'] = ['Complementary and alternative medicine']

    assert from_crossref(message)['keywords'] == []


def test_from_crossref_tolerates_missing_everything() -> None:
    """只有标题的记录（会议摘要常见）不该炸，缺的字段一律留空。"""
    fields = from_crossref({'title': ['Only a title']})
    assert fields['title'] == 'Only a title'
    assert fields['authors'] == []
    assert fields['affiliations'] == []
    assert fields['publication_year'] is None


# --------------------------------------------------------------------------- PubMed 兜底


def _pubmed_xml(abstract: str = '', keywords: str = '', mesh: str = '') -> str:
    """按 efetch 的真实层级拼一份 XML（KeywordList 挂在 MedlineCitation 下，不在 Article 下）。"""
    return f"""<?xml version="1.0" ?>
<PubmedArticleSet><PubmedArticle>
  <MedlineCitation Status="MEDLINE">
    <PMID Version="1">33782057</PMID>
    <Article><ArticleTitle>Acupuncture for chronic pain</ArticleTitle>
      {f'<Abstract>{abstract}</Abstract>' if abstract else ''}
    </Article>
    {f'<MeshHeadingList>{mesh}</MeshHeadingList>' if mesh else ''}
    {f'<KeywordList Owner="NOTNLM">{keywords}</KeywordList>' if keywords else ''}
  </MedlineCitation>
</PubmedArticle></PubmedArticleSet>"""


def test_pubmed_structured_abstract_keeps_headings() -> None:
    """结构化摘要的 Label 要单独成行，否则去标签后会粘成「BACKGROUNDAcupuncture…」。"""
    xml = _pubmed_xml(
        abstract=(
            '<AbstractText Label="BACKGROUND" NlmCategory="BACKGROUND">Acupuncture is widely used.</AbstractText>'
            '<AbstractText Label="METHODS">We searched 5 databases.</AbstractText>'
        )
    )
    got = parse_pubmed_xml(xml)

    assert got['abstract'] == 'BACKGROUND：Acupuncture is widely used.\n\nMETHODS：We searched 5 databases.'
    assert got['pmid'] == '33782057'


def test_pubmed_abstract_keeps_inline_markup_text() -> None:
    """AbstractText 里内嵌 <i>/<sup> 很常见，取文本时不能把里面的字丢掉。"""
    xml = _pubmed_xml(abstract='<AbstractText>P <i>value</i> was 0.03 (n<sup>2</sup>).</AbstractText>')

    assert parse_pubmed_xml(xml)['abstract'] == 'P value was 0.03 (n2).'


def test_pubmed_prefers_author_keywords_over_mesh() -> None:
    xml = _pubmed_xml(
        keywords='<Keyword MajorTopicYN="N">acupuncture</Keyword><Keyword MajorTopicYN="N">chronic pain</Keyword>',
        mesh='<MeshHeading><DescriptorName UI="D026881">Acupuncture Therapy</DescriptorName></MeshHeading>',
    )
    got = parse_pubmed_xml(xml)

    assert got['keywords'] == ['acupuncture', 'chronic pain']
    assert got['keywords_source'] == 'keyword'


def test_pubmed_falls_back_to_mesh_and_says_so() -> None:
    """
    回落 MeSH 时**来源必须标出来**：MeSH 是索引员事后打的受控词，不是作者写的关键词，
    展示到官网前该让管理员知道这回事（提示语里会写明）。
    """
    xml = _pubmed_xml(
        mesh=(
            '<MeshHeading><DescriptorName UI="D026881">Acupuncture Therapy</DescriptorName></MeshHeading>'
            '<MeshHeading><DescriptorName UI="D000818">Animals</DescriptorName></MeshHeading>'
            # 同一个词会因主/次标题重复出现
            '<MeshHeading><DescriptorName UI="D026881">Acupuncture Therapy</DescriptorName></MeshHeading>'
        )
    )
    got = parse_pubmed_xml(xml)

    assert got['keywords'] == ['Acupuncture Therapy', 'Animals']
    assert got['keywords_source'] == 'mesh'


def test_pubmed_empty_when_nothing_there() -> None:
    got = parse_pubmed_xml(_pubmed_xml())

    assert got['abstract'] == ''
    assert got['keywords'] == []
    assert got['keywords_source'] == ''


def test_pubmed_broken_xml_returns_empty_instead_of_raising() -> None:
    """兜底路径不许把主路带崩：Crossref 那份草稿已经能用了。"""
    assert parse_pubmed_xml('<PubmedArticleSet><PubmedArticle>')['abstract'] == ''
    assert parse_pubmed_xml('')['pmid'] == ''
    # esearch 命中但 efetch 返回一份没有 PubmedArticle 的空集
    assert parse_pubmed_xml('<PubmedArticleSet/>')['keywords'] == []


# --------------------------------------------------------------------------- 引用文本


def test_build_citation_text_full() -> None:
    fields = from_crossref(_crossref_message())
    citation = build_citation_text(fields)
    assert citation == (
        'San Zhang, Si Li, Wu Wang, et al. '
        'Acupuncture for chronic pain: a systematic review. '
        'Complementary Therapies in Medicine. 2024;80(3):103041. '
        'doi:10.1016/j.ctim.2024.103041'
    )


def test_build_citation_text_three_authors_has_no_et_al() -> None:
    """三位及以下要列全，et al. 是第四位起才出现的。"""
    fields = {'authors': [{'name': 'A B'}, {'name': 'C D'}, {'name': 'E F'}], 'title': 'T'}
    assert build_citation_text(fields).startswith('A B, C D, E F. T.')


def test_build_citation_text_keeps_year_without_journal() -> None:
    """预印本没有期刊名，年份不能跟着一起丢。"""
    assert build_citation_text({'title': 'T', 'publication_year': 2023}) == 'T. 2023.'


def test_build_citation_text_empty() -> None:
    assert build_citation_text({}) == ''


# --------------------------------------------------------------------------- 模型出参


def test_parse_ai_json_unwraps_code_fence() -> None:
    """模型爱把 JSON 裹进 ```json 围栏，还爱在前面加一句「好的」。"""
    raw = '好的，以下是提取结果：\n```json\n{"title": "T", "publicationYear": 2024}\n```'
    fields = parse_ai_json(raw)
    assert fields['title'] == 'T'
    assert fields['publication_year'] == 2024


def test_parse_ai_json_accepts_string_authors() -> None:
    """给成字符串数组时也要收得住，别整条丢掉。"""
    fields = parse_ai_json('{"authors": ["Zhang San", " Li Si "], "affiliations": []}')
    assert fields['authors'] == [
        {'name': 'Zhang San', 'affiliation_index': None},
        {'name': 'Li Si', 'affiliation_index': None},
    ]


def test_parse_ai_json_drops_out_of_range_affiliation_index() -> None:
    """越界下标必须当没标 —— 挂错单位比不挂单位糟得多，而页面上看不出来。"""
    raw = '{"affiliations": ["A"], "authors": [{"name": "X", "affiliationIndex": 3}]}'
    assert parse_ai_json(raw)['authors'][0]['affiliation_index'] is None


def test_parse_ai_json_splits_keyword_string() -> None:
    """关键词给成一整串（分号或逗号分隔）时就地拆开。"""
    assert parse_ai_json('{"keywords": "acupuncture; chronic pain，RCT"}')['keywords'] == [
        'acupuncture',
        'chronic pain',
        'RCT',
    ]


def test_parse_ai_json_normalizes_year_and_doi() -> None:
    raw = '{"publicationYear": "2024年", "doi": "https://doi.org/10.1016/j.ctim.2024.103041"}'
    fields = parse_ai_json(raw)
    assert fields['publication_year'] == 2024
    assert fields['doi'] == '10.1016/j.ctim.2024.103041'


def test_parse_ai_json_keeps_odd_shaped_doi() -> None:
    """注册机构号不合规的 DOI 也要原样填回表单让人看见，而不是安静清空。"""
    assert parse_ai_json('{"doi": "doi: 10.1/x"}')['doi'] == '10.1/x'


def test_parse_ai_json_rejects_year_out_of_range() -> None:
    """把页码或样本量当年份填回来的情况见过，卡一道范围。"""
    assert parse_ai_json('{"publicationYear": 103041}')['publication_year'] is None


def test_parse_ai_json_raises_on_non_json() -> None:
    """拿不到 JSON 要抛，不能返回空字典 —— 那会被渲染成「解析成功但什么都没填」。"""
    with pytest.raises(ValueError, match='JSON'):
        parse_ai_json('抱歉，我无法从这份文件中提取信息。')


def test_build_pdf_messages_truncates_and_forbids_invention() -> None:
    """只送首部，且「不要编」必须每次都发出去。"""
    messages = build_pdf_messages('x' * 99999)
    assert messages[0]['role'] == 'system'
    assert '一个字都不要编' in messages[0]['content']
    assert len(messages[1]['content']) < 99999
