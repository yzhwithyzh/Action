"""成果发表服务层里那几段「JSON 列进出」的单测（不连库）。

`PublicationService._encode` / `_decode` 是这张表唯一的特别之处：作者、机构、关键词
在库里是 JSON 文本，在接口上是结构化列表。这层转换错了的表现都很温和 ——
作者列表变空、编辑一次把作者清光、引用文本覆盖掉人工写的那条 —— 没有一个会报错。

跑法：python -m pytest tools/tests/test_publication_service.py -q
"""

from __future__ import annotations

import json

from module_action.entity.vo.action_vo import PublicationModel
from module_action.service.action_service import PublicationService
from module_action.service.publication_meta_service import PublicationMetaService


def _model(**kwargs) -> PublicationModel:
    """用 snake_case 字段名构造（populate_by_name 就是为这个开的）。"""
    return PublicationModel(**kwargs)


def test_encode_serializes_json_columns_with_camel_keys() -> None:
    """库里存的是 affiliationIndex —— 与接口出参、后台表单同形，读回来不必再翻一次。"""
    values = PublicationService._encode(
        _model(
            title='T',
            authors=[{'name': 'Zhang San', 'affiliation_index': 0}],
            affiliations=['GZUCM'],
            keywords=['acupuncture'],
        )
    )
    assert json.loads(values['authors']) == [{'name': 'Zhang San', 'affiliationIndex': 0}]
    assert json.loads(values['affiliations']) == ['GZUCM']
    assert json.loads(values['keywords']) == ['acupuncture']


def test_encode_keeps_chinese_readable() -> None:
    """ensure_ascii=False：存成 \\u9488\\u523a 的话按中文关键词一条都搜不到（列表走 ilike 搜这一列）。"""
    values = PublicationService._encode(_model(title='T', keywords=['针刺']))
    assert '针刺' in values['keywords']


def test_encode_omits_untouched_json_columns() -> None:
    """没带上作者的那次编辑不许变成「清空作者」—— exclude_unset 的语义要一路守到 JSON 列。"""
    values = PublicationService._encode(_model(publication_id=1, title='新标题'))
    assert 'authors' not in values
    assert 'affiliations' not in values
    assert 'keywords' not in values


def test_encode_explicit_empty_list_clears_column() -> None:
    """显式传空列表就是「清空」，这条和上一条是一对。"""
    values = PublicationService._encode(_model(publication_id=1, authors=[]))
    assert values['authors'] == '[]'


def test_decode_parses_json_columns() -> None:
    row = {
        'publicationId': 1,
        'title': 'T',
        'authors': '[{"name": "Zhang San", "affiliationIndex": 0}]',
        'affiliations': '["GZUCM"]',
        'keywords': '["acupuncture"]',
        'abstract': '很长的摘要',
    }
    decoded = PublicationService._decode(row)
    assert decoded['authors'] == [{'name': 'Zhang San', 'affiliationIndex': 0}]
    assert decoded['affiliations'] == ['GZUCM']
    # 详情场景保留摘要
    assert decoded['abstract'] == '很长的摘要'
    # 出参模型认得这份字典（camelCase 键走 alias）
    assert PublicationModel(**decoded).authors[0].affiliation_index == 0


def test_decode_brief_drops_abstract() -> None:
    """列表页是预渲染的，把每篇摘要烤进 HTML 只是白压 payload。"""
    decoded = PublicationService._decode({'title': 'T', 'abstract': 'x', 'citationText': 'y'}, brief=True)
    assert 'abstract' not in decoded
    assert 'citationText' not in decoded


def test_decode_survives_broken_json() -> None:
    """这几列人可以直接改库，一条脏数据不该让整页列表 500。"""
    decoded = PublicationService._decode({'title': 'T', 'authors': '不是 JSON', 'keywords': None})
    assert decoded['authors'] == []
    assert decoded['keywords'] == []


def test_fill_citation_only_when_blank() -> None:
    """各刊引用格式不同，人工写过的那条不许被自动生成的覆盖。"""
    kept = _model(title='T', journal='J', citation_text='我自己写的引用')
    PublicationService._fill_citation(kept)
    assert kept.citation_text == '我自己写的引用'

    filled = _model(title='T', journal='J', publication_year=2024, doi='10.1/x')
    PublicationService._fill_citation(filled)
    assert filled.citation_text == 'T. J. 2024. doi:10.1/x'


def test_doi_prefix_is_stripped_on_input() -> None:
    """后台粘整条 doi.org 链接是常态；不剥前缀前台会拼出 doi.org/https://doi.org/… 的死链。"""
    assert _model(doi='https://doi.org/10.1016/j.ctim.2024.103041').doi == '10.1016/j.ctim.2024.103041'
    assert _model(doi='doi: 10.1001/jama.2023.1234').doi == '10.1001/jama.2023.1234'


def test_empty_author_rows_are_dropped() -> None:
    """后台点了「添加作者」又没填的空行，不该占一个署名位。"""
    model = _model(authors=[{'name': ' '}, {'name': ' Li Si '}])
    assert [a.name for a in model.authors] == ['Li Si']


# --------------------------------------------------------------------------- 解析结果的提示语
#
# 摘要与关键词空着时，一句绿色的「解析成功」加两个空框会被当成解析坏了 ——
# 而真实原因是 Crossref 与 PubMed 都没有这篇的这两项。提示语是唯一能说清这件事的地方。


def test_note_plain_when_crossref_gave_everything() -> None:
    note = PublicationMetaService._parse_note({'abstract': 'a', 'keywords': ['k']}, False, '')

    assert note == '解析成功，请核对各字段后保存'


def test_note_says_where_the_abstract_came_from() -> None:
    note = PublicationMetaService._parse_note({'abstract': 'a', 'keywords': ['k']}, True, 'keyword')

    assert '摘要取自 PubMed' in note
    assert '关键词取自 PubMed' in note


def test_note_flags_mesh_keywords() -> None:
    """MeSH 是索引员事后打的受控词，不是作者关键词 —— 直接发到官网前得让人知道。"""
    note = PublicationMetaService._parse_note({'abstract': 'a', 'keywords': ['Animals']}, False, 'mesh')

    assert 'MeSH' in note
    assert '非作者关键词' in note


def test_note_names_what_is_missing() -> None:
    """两处都没有时要点名缺什么、下一步做什么，前端据此改用警告色提示。"""
    note = PublicationMetaService._parse_note({'abstract': '', 'keywords': []}, False, '')

    assert '摘要与关键词未能获取' in note
    assert 'Crossref 与 PubMed 都没有' in note
    assert '按 PDF 解析' in note


def test_note_distinguishes_pubmed_unreachable() -> None:
    """
    「查通了但这篇没有」和「压根没连上」对运维是两件事：后者多半是服务器没有外网出口。
    混成一句会让人一直以为是数据源没有这篇。
    """
    note = PublicationMetaService._parse_note({'abstract': '', 'keywords': []}, False, '', pubmed_ok=False)

    assert 'PubMed 这次没连上' in note
