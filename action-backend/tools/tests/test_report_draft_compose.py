"""报告初稿合成的单测（不连库、不调模型）。

盯的是几件「错了会直接骗人」的事：
- checklist 的**条目要求原文**绝不能出现在初稿正文里 —— 它长得就像一句合格的报告，
  混进去之后第三步会把这句要求本身判成「已报告」，整轮逐条判定作废。
  眼下这条由数据结构保证（`ComposeItem` 没有那个字段），用例守的是「服务层别把它传下来」
- 用户填过的正文在任何路径下都不许消失（条目被后台下线时要兜到末尾一节）
- 未填的**必填**条目要留下可见的缺口，未填的**选填**条目不留噪声
- 越权取草稿与「不存在」返回同一句话，不能靠报错文案区分出别人有没有这份草稿
"""

from __future__ import annotations

import asyncio

import pytest
from exceptions.exception import ServiceException
from module_action.service.action_service import ReportDraftService
from module_action.service.report_compose_service import (
    ComposeItem,
    compose_draft_text,
)

#: 一份最小可用的条目表：两个章节，含必填与选填
ITEMS = (
    ComposeItem(item_id=1, domain='题目和摘要', item_no='1a', require_level='0'),
    ComposeItem(item_id=2, domain='题目和摘要', item_no='1b', require_level='1'),
    ComposeItem(item_id=3, domain='方法', item_no='6a', require_level='0'),
    ComposeItem(item_id=4, domain='方法', item_no='6b', require_level='0'),
)


def test_compose_item_carries_no_requirement_text() -> None:
    """条目要求被抄进稿件 = 第三步把要求本身判成已报告，这是整条链路最要命的一处。

    所以合成层根本拿不到那个值 —— 这条用例守的就是「别把字段加回来」。
    """
    assert not hasattr(ComposeItem(item_id=1), 'content')


def test_draft_contains_only_user_text_and_placeholders() -> None:
    """正文里除了用户自己写的话，就只该有占位标记与章节名。"""
    result = compose_draft_text('测试稿', ITEMS, {1: '本文标题已写明为随机对照试验。'})

    assert result.text.splitlines() == [
        '测试稿',
        '',
        '题目和摘要',
        '本文标题已写明为随机对照试验。',
        '',
        '方法',
        '【待补充：条目 6a】',
        '【待补充：条目 6b】',
    ]


def test_required_gaps_are_marked_optional_gaps_are_not() -> None:
    """缺口要看得见，但不能让选填项的「待补充」把初稿淹没。"""
    result = compose_draft_text('', ITEMS, {1: '正文一'})

    # 1a 已填、1b 选填未填、6a 与 6b 必填未填
    assert result.missing_required == 2
    assert result.text.count('【待补充') == 2
    assert '【待补充：条目 6a】' in result.text
    assert '1b' not in result.text


def test_empty_section_drops_its_heading() -> None:
    """一条都没填的章节连标题一起丢掉，否则早期草稿是一屏空标题。"""
    only_optional = (ComposeItem(item_id=2, domain='题目和摘要', item_no='1b', require_level='1'),)
    result = compose_draft_text('', only_optional, {})

    assert result.text == ''
    assert result.char_count == 0


def test_english_draft_uses_english_placeholders() -> None:
    result = compose_draft_text('Draft', ITEMS, {}, locale='en')

    assert '[To be completed: item 1a]' in result.text
    assert '待补充' not in result.text


def test_filled_count_ignores_blank_content() -> None:
    result = compose_draft_text('', ITEMS, {1: '正文', 2: '   ', 3: ''})

    assert result.filled_count == 1


def test_orphan_texts_are_appended_not_dropped() -> None:
    """条目被后台停用后，用户为它写的正文没有章节可归——但那仍是用户的原话，只能挪位置不能丢。"""
    result = compose_draft_text('', ITEMS, {1: '正文一'}, orphan_texts=('一段已下线条目的正文。',))

    assert '其他内容' in result.text
    assert '一段已下线条目的正文。' in result.text


# ---------------------------------------------------------------- 服务层的三道闸


class _StubDao:
    """把 DAO 换成可控的桩：这几条用例要验的是服务层的判断，不是 SQL。"""

    def __init__(self, draft: object | None) -> None:
        self._draft = draft

    async def get_draft_by_id(self, _db: object, _draft_id: int, _user_id: int) -> object | None:
        return self._draft

    async def get_draft_items(self, _db: object, _draft_id: int, _user_id: int) -> list:
        return []


class _StubDraft:
    draft_id = 1
    guideline_id = 1
    title = '空草稿'


class _Guideline:
    code = 'STRICTA'


async def _detail(_db: object, _gid: int) -> object:
    return _Guideline()


async def _items(*_args: object, **_kwargs: object) -> list:
    return [
        {
            'itemId': 1,
            'domainZh': '方法',
            'itemNoZh': '1',
            'contentZh': '文题能识别是随机临床试验。',
            'requireLevel': '0',
        }
    ]


def test_foreign_draft_and_missing_draft_share_one_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """不区分「没有这份草稿」与「这份不是你的」——分开报，拿 id 逐个试就能探出别人有几份。"""
    stub = _StubDao(None)
    monkeypatch.setattr('module_action.service.action_service.ReportDraftDao', stub)

    with pytest.raises(ServiceException) as got:
        asyncio.run(ReportDraftService.compose_draft_services(object(), 999, 42))

    assert got.value.message == '草稿不存在'


def test_empty_draft_refuses_to_compose(monkeypatch: pytest.MonkeyPatch) -> None:
    """一条正文都没有时合出来只是一串「待补充」，送去第三步等于白烧一次模型调用。"""
    monkeypatch.setattr('module_action.service.action_service.ReportDraftDao', _StubDao(_StubDraft()))
    monkeypatch.setattr('module_action.service.action_service.GuidelineDao.get_guideline_detail_by_id', _detail)
    monkeypatch.setattr('module_action.service.action_service.GuidelineItemDao.get_item_list', _items)

    with pytest.raises(ServiceException) as got:
        asyncio.run(ReportDraftService.compose_draft_services(object(), 1, 42))

    assert '还没有任何内容' in got.value.message


def test_service_does_not_pass_requirement_text_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """条目要求原文不许从服务层漏进合成层 —— 结构上挡住了，这里守的是别绕过去。"""
    rows = [type('_Row', (), {'item_id': 1, 'content': '本文标题已写明为随机对照试验。'})()]

    class _Dao(_StubDao):
        async def get_draft_items(self, _db: object, _draft_id: int, _user_id: int) -> list:
            return rows

    monkeypatch.setattr('module_action.service.action_service.ReportDraftDao', _Dao(_StubDraft()))
    monkeypatch.setattr('module_action.service.action_service.GuidelineDao.get_guideline_detail_by_id', _detail)
    monkeypatch.setattr('module_action.service.action_service.GuidelineItemDao.get_item_list', _items)

    got = asyncio.run(ReportDraftService.compose_draft_services(object(), 1, 42))

    assert '文题能识别是随机临床试验' not in got.text
    assert '本文标题已写明为随机对照试验。' in got.text
