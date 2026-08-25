"""SRD 评估结果导出 xlsx 的行为测试。

排版层是纯函数（`SrdAssessmentModel` → 字节），不碰数据库，所以整份测试离线可跑。

值得单独测的是三件「错了也不会报错、只会安静导出一份误导人的表」的事：
① 判定不出来时不许写成 0%（那在读表的人眼里就是「两篇毫无重叠」）；
② 原文引用列必须是逐字原文，不是中文译文（否则导出件也丢掉了回原文核对的依据）；
③ 英文导出件不能因为数据侧缺英文就留一整列空白。

跑法：python -m pytest tests/test_srd_export.py -q
"""

import asyncio
import io
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest
from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.worksheet import Worksheet

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_action.entity.vo.action_vo import (
    SrdAssessmentModel,
    SrdDomainModel,
    SrdGroupModel,
    SrdItemModel,
)
from module_action.service.srd_export_service import build_assessment_xlsx

# --------------------------------------------------------------------------- 夹具


def _item(code: str, rating: str | None, score: int | None, **over: object) -> SrdItemModel:
    data: dict = {
        'itemId': int(code[0]),
        'code': code,
        'questionZh': f'问题 {code}',
        'questionEn': f'question {code}',
        'rating': rating,
        'score': score,
        'confidence': 'high',
        'needsReview': '0',
        'reviewNote': '',
        'evidenceCard': '',
        'basisZh': f'理由 {code}',
        'basisEn': f'reason {code}',
        'citeAZh': f'A 的中文译文 {code}',
        'citeAEn': f'A verbatim quote {code}',
        'citeBZh': f'B 的中文译文 {code}',
        'citeBEn': f'B verbatim quote {code}',
    }
    data.update(over)

    return SrdItemModel(**data)


def _assessment(**over: object) -> SrdAssessmentModel:
    group = SrdGroupModel(
        groupId=1,
        code='1',
        nameZh='研究问题',
        nameEn='Research question',
        items=[_item('1a', '2', 2), _item('1b', 'unclear', None)],
    )
    domains = [
        SrdDomainModel(
            domainId=1, seq=1, nameZh='研究主题', nameEn='Study topic', isKey='1',
            level='low', pct=46, scoreSum=13, scoreMax=24, scoreMaxFull=24,
            unclearCount=0, evidenceSufficient='1', nearBoundary='0', groups=[group],
        ),
        # 一条都没评出来的领域：level 为空，pct 是 0 但不该被写成「0%」
        SrdDomainModel(
            domainId=2, seq=2, nameZh='研究方法', nameEn='Study methods', isKey='0',
            level=None, pct=0, scoreSum=0, scoreMax=0, scoreMaxFull=18,
            unclearCount=6, evidenceSufficient='0', nearBoundary='0', groups=[],
        ),
    ]
    data: dict = {
        'assessmentId': 7,
        'reviewATitleZh': '综述 A 中文标题',
        'reviewATitleEn': 'Review A English title',
        'reviewBTitleZh': '综述 B 中文标题',
        'reviewBTitleEn': '',
        'overallLevel': 'low',
        'overallPct': 42,
        'overallScoreSum': 49,
        'overallScoreMax': 84,
        'overallScoreMaxFull': 102,
        'overallReasonZh': '关键领域均为「低重复」及以下，按表 3 判定为低重复。',
        'overallReasonEn': 'Key domains: both were low duplication or below.',
        'provisional': '1',
        'unclearCount': 6,
        'reviewCount': 2,
        'modelName': 'deepseek-chat',
        'engineVersion': 'srd-engine/0.7.1',
        'llmCalls': 10,
        'seconds': 377.0,
        'isSample': '0',
        'domains': domains,
    }
    data.update(over)

    return SrdAssessmentModel(**data)


def _book(lang: str = 'zh', **over: object) -> Workbook:
    return load_workbook(io.BytesIO(build_assessment_xlsx(_assessment(**over), lang)))  # type: ignore[arg-type]


def _cells(ws: Worksheet) -> list[tuple]:
    return list(ws.iter_rows(values_only=True))


def _overview(wb: Workbook, lang: str = 'zh') -> dict:
    ws = wb['概览' if lang == 'zh' else 'Overview']

    return {row[0]: row[1] for row in _cells(ws)[1:] if row[0]}


#: 夹具里那个「一条都没评出来」的领域的序号
BLANK_DOMAIN_SEQ = 2
#: 一份三表的 xlsx 至少这么大；小于它多半是导出了个空壳
MIN_XLSX_BYTES = 1000


# --------------------------------------------------------------------------- 结构


def test_workbook_has_three_sheets_in_reading_order() -> None:
    """从结论往证据走：先概览，再领域，最后条目明细。"""
    assert _book('zh').sheetnames == ['概览', '领域', '条目明细']
    assert _book('en').sheetnames == ['Overview', 'Domains', 'Items']


def test_no_blank_default_sheet() -> None:
    """openpyxl 的 Workbook() 自带一张空表，忘了删就是导出件第一页一片空白。"""
    assert all(wb.sheetnames[0] not in ('Sheet', '') for wb in (_book('zh'), _book('en')))


def test_every_item_lands_in_the_detail_sheet() -> None:
    rows = _cells(_book('zh')['条目明细'])

    assert [r[2] for r in rows[1:]] == ['1a', '1b']


# --------------------------------------------------------------------------- 判定不出来 ≠ 无重复


def test_unassessable_domain_does_not_get_a_zero_percent() -> None:
    """pct 是 0 但 level 为空 —— 写成「0%」在读表的人眼里就是「两篇毫无重叠」。"""
    rows = _cells(_book('zh')['领域'])
    blank_domain = next(r for r in rows[1:] if r[0] == BLANK_DOMAIN_SEQ)

    assert blank_domain[3] == '无法判定'
    # 留白，而不是「0%」（openpyxl 把空串读回来是 None）
    assert blank_domain[4] in (None, '')


def test_unassessable_overall_does_not_get_a_zero_percent() -> None:
    values = _overview(_book('zh', overallLevel=None, overallPct=0))

    assert values['整体判定'] == '无法判定'
    assert values['整体重复度'] in (None, '')


def test_unclear_item_has_no_points() -> None:
    """证据不足不计分，分数格必须留空。

    填 0 分会被读成「完全不同」（0.8.0 方向），把「没得判」说成了「两篇毫无共同点」。
    """
    rows = _cells(_book('zh')['条目明细'])
    unclear = next(r for r in rows[1:] if r[2] == '1b')

    assert unclear[4] == '证据不足'
    assert unclear[5] in (None, '')


def test_rating_labels_follow_the_0_8_0_direction() -> None:
    """3 分 = 完全相同、0 分 = 完全不同。导出件是拿去投稿的，标反了就是学术事故。"""
    a = _assessment()
    a.domains[0].groups[0].items = [_item('1a', '3', 3), _item('1b', '0', 0)]
    rows = _cells(load_workbook(io.BytesIO(build_assessment_xlsx(a, 'zh')))['条目明细'])

    assert [(r[2], r[4], r[5]) for r in rows[1:]] == [('1a', '完全相同', 3), ('1b', '完全不同', 0)]


# --------------------------------------------------------------------------- 原文引用


def test_quote_column_holds_the_verbatim_original_not_the_translation() -> None:
    """导出件丢掉逐字原文，人工复核就没法回原文核了 —— 这正是页面上踩过的那个坑。"""
    rows = _cells(_book('zh')['条目明细'])
    first = rows[1]

    assert first[11] == 'A verbatim quote 1a'
    assert first[12] == 'A 的中文译文 1a'
    assert first[13] == 'B verbatim quote 1a'


def test_translation_column_is_empty_when_the_source_is_already_chinese() -> None:
    """中文文献两列同值；并排放两列一模一样的字，看的人会以为哪里出错了。"""
    same = _item('1a', '2', 2, citeAZh='中文原句', citeAEn='中文原句')
    a = _assessment()
    a.domains[0].groups[0].items = [same]
    wb = load_workbook(io.BytesIO(build_assessment_xlsx(a, 'zh')))
    row = _cells(wb['条目明细'])[1]

    assert row[11] == '中文原句'
    assert row[12] in (None, '')


# --------------------------------------------------------------------------- 双语


def test_english_export_uses_english_content() -> None:
    values = _overview(_book('en'), 'en')

    assert values['Review A'] == 'Review A English title'
    assert values['Overall verdict'] == 'Low duplication'


def test_english_export_falls_back_to_chinese_when_english_is_missing() -> None:
    """数据侧缺英文时不回落，英文导出件会留一整列空白。"""
    values = _overview(_book('en'), 'en')

    assert values['Review B'] == '综述 B 中文标题'


def test_unknown_language_falls_back_to_chinese() -> None:
    wb = load_workbook(io.BytesIO(build_assessment_xlsx(_assessment(), 'fr')))  # type: ignore[arg-type]

    assert wb.sheetnames[0] == '概览'


# --------------------------------------------------------------------------- 出处


def test_real_run_records_which_model_and_engine_produced_it() -> None:
    """导出件是要存档的：日后复现这份结论，靠的就是模型名与引擎版本。"""
    provenance = _overview(_book('zh'))['生成信息']

    assert 'deepseek-chat' in provenance
    assert 'srd-engine/0.7.1' in provenance


def test_sample_export_is_labelled_as_a_demo() -> None:
    """示例数据不能看着像一次真实评估的存档。"""
    provenance = _overview(_book('zh', isSample='1'))['生成信息']

    assert '示例' in provenance


@pytest.mark.parametrize('lang', ['zh', 'en'])
def test_export_is_a_real_xlsx(lang: str) -> None:
    content = build_assessment_xlsx(_assessment(), lang)  # type: ignore[arg-type]

    # xlsx 是 zip 容器，前两个字节固定是 PK
    assert content[:2] == b'PK'
    assert len(content) > MIN_XLSX_BYTES


# --------------------------------------------------------------------------- 服务层


def test_export_goes_through_the_same_visibility_gate_as_viewing() -> None:
    """可见性判定只该有一份实现：另写一份「导出用」的迟早会与「查看用」的分叉。"""
    from module_action.service.action_service import SrdService  # noqa: PLC0415

    with patch.object(SrdService, 'get_assessment_services', new=AsyncMock(return_value=_assessment())) as get:
        content = asyncio.run(SrdService.export_assessment_services(AsyncMock(), 9, user_id=1, lang='en'))

    assert get.await_args.args[1:] == (9, 1)
    assert content[:2] == b'PK'
