"""SRD 评估落库链路的行为测试。

覆盖的是**后端这一半**：worker 摘要 + `result.json` → 四张业务表的字段映射，
以及轮询接口在各种任务状态下的动作。引擎算法本身在 `tools/srd-engine/tests` 里测，
worker 任务在 `tools/tests/test_srd_session_task.py` 里测，这里都不重复。

为什么值得单独测：映射层是**唯一一处**把引擎的口径翻译成库结构的地方，
翻错了不会报错，只会安静地渲染出一份数字不对的报告。

跑法：python -m pytest tests/test_srd_assessment.py -q
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from exceptions.exception import ServiceException
from module_action.entity.do.action_do import ActionSrdAssessment, ActionSrdDomain
from module_action.service.action_service import SrdService, _SrdRun

# --------------------------------------------------------------------------- 夹具


def _item(code: str, rating: str, **over: object) -> dict:
    """一条引擎风格的条目结果。"""
    return {
        'code': code,
        'question_zh': f'问题 {code}',
        'question_en': f'question {code}',
        'rating': rating,
        'reason_zh': f'理由 {code}',
        'reason_en': f'reason {code}',
        'cite_a': f'A quote {code}',
        'cite_a_zh': f'A 引用 {code}',
        'cite_b': f'B quote {code}',
        'cite_b_zh': f'B 引用 {code}',
        'confidence': 'high',
        'needs_review': False,
        'review_note': '',
        'evidence_card': '',
        **over,
    }


def _detail() -> dict:
    """一份最小但结构完整的 result.json。"""
    return {
        'review_a_title': '综述 A 的真实标题',
        'review_b_title': '综述 B 的真实标题',
        'overall_level': 'mod',
        'overall_pct': 46,
        'overall_score_sum': 55,
        'overall_score_max': 99,
        'overall_score_max_full': 102,
        'overall_reason_zh': '按表 3 判定为中度重复。',
        'overall_reason_en': 'Table 3 verdict: moderate duplication.',
        'provisional': True,
        'unclear_count': 1,
        'review_count': 2,
        'model': 'deepseek-chat',
        'engine_version': 'srd-engine/0.7.0',
        'prompt_version': 'prompt/2026-08-05',
        'criteria_version': 'criteria/1',
        'llm_calls': 9,
        'token_in': 128000,
        'token_out': 19000,
        'domains': [
            {
                'seq': 1,
                'name_zh': '领域 1：研究主题',
                'name_en': 'Domain 1: Research topic',
                'is_key': True,
                'level': 'mod',
                'pct': 67,
                'score_sum': 8,
                'score_max': 24,
                'score_max_full': 24,
                'dup_count': 7,
                'diff_count': 1,
                'unclear_count': 0,
                'evidence_sufficient': True,
                'near_boundary': False,
                'groups': [
                    {
                        'code': '1',
                        'name_zh': '确定范围和问题',
                        'name_en': 'Defining scope and question',
                        'items': [_item('1a', '1'), _item('1b', '0')],
                    }
                ],
            },
            {
                'seq': 2,
                'name_zh': '领域 2：研究方法',
                'name_en': 'Domain 2: Study methods',
                'is_key': False,
                'level': None,
                'pct': 0,
                'score_sum': 0,
                'score_max': 0,
                'score_max_full': 18,
                'dup_count': 0,
                'diff_count': 0,
                'unclear_count': 6,
                'evidence_sufficient': False,
                'near_boundary': False,
                'groups': [
                    {
                        'code': '3',
                        'name_zh': '检索与筛选研究',
                        'name_en': 'Searching & screening',
                        'items': [_item('3a', 'unclear', evidence_card='A∩B = 3/12 篇')],
                    }
                ],
            },
        ],
    }


def _run() -> _SrdRun:
    return _SrdRun(assessment_id=7, session_id='sid7', user_id=1, run_status='running', progress=40, error_msg='')


# --------------------------------------------------------------------------- 字段映射


def test_assessment_values_carry_score_triplet_and_versions() -> None:
    """得分三件套与版本三件套都得原样落库 —— 少一个都会让历史结果无法解释。"""
    values = SrdService._assessment_values(_detail(), {'seconds': 214.6, 'model': 'ignored-if-detail-has-one'})

    assert (values['run_status'], values['progress']) == ('completed', 100)
    assert (values['overall_score_sum'], values['overall_score_max'], values['overall_score_max_full']) == (55, 99, 102)
    assert (values['overall_pct'], values['unclear_count'], values['review_count']) == (46, 1, 2)
    assert values['provisional'] == '1'
    # detail 里的 model 优先于摘要里的
    assert values['model_name'] == 'deepseek-chat'
    assert values['engine_version'] == 'srd-engine/0.7.0'
    assert values['criteria_version'] == 'criteria/1'
    assert values['seconds'] == pytest.approx(214.6)
    # 占位标题（文件名）必须被引擎抽出的真实标题覆盖掉
    assert values['review_a_title_zh'] == '综述 A 的真实标题'


def test_domain_values_strip_engine_name_prefix() -> None:
    """引擎的领域名带「领域 1：」前缀，而前台模板自己会拼序号，存进去就会重影。"""
    d1, d2 = (SrdService._domain_values(d) for d in _detail()['domains'])

    assert d1['name_zh'] == '研究主题'
    assert d1['name_en'] == 'Research topic'
    assert d1['is_key'] == '1'
    assert (d1['score_sum'], d1['score_max'], d1['score_max_full']) == (8, 24, 24)
    assert d1['evidence_sufficient'] == '1'
    assert d2['is_key'] == '0'
    # 全领域证据不足：level 为 None 要如实落 null，不能兜成 'none'——
    # 「没得判」和「无重复」是两回事
    assert d2['level'] is None
    assert d2['evidence_sufficient'] == '0'


def test_verdict_columns_have_no_default() -> None:
    """判定列绝不能带 server_default。

    带了之后 SQLAlchemy 会把显式传进来的 None 当成「没给值」直接从 INSERT 里省掉
    （列有默认值时的既定行为），于是「一条刚排队的任务」和「一个全领域证据不足的结果」
    都会被静默写成那个默认值。实测过：原 DDL 的 default 'mod' 会让它们全变成「中度重复」。
    """
    assert ActionSrdAssessment.__table__.c.overall_level.server_default is None
    assert ActionSrdDomain.__table__.c.level.server_default is None


def test_item_values_map_rating_to_score() -> None:
    """0–3 分照搬；unclear 的分数必须是 null，不进分子也不进分母。"""
    scored = SrdService._item_values(_item('1a', '2'))
    unclear = SrdService._item_values(_item('3a', 'unclear'))

    assert (scored['rating'], scored['score']) == ('2', 2)
    assert (unclear['rating'], unclear['score']) == ('unclear', None)
    assert SrdService._item_values(_item('x', '0'))['score'] == 0


def test_item_values_prefer_human_override() -> None:
    """人工覆盖过的条目，落库要落覆盖值 —— 否则后台改了判定，前台还显示模型的原判。"""
    values = SrdService._item_values(
        _item('8c', '3', override_rating='1', override_reason_zh='人工复核：两篇结论方向一致')
    )

    assert (values['rating'], values['score']) == ('1', 1)
    assert values['basis_zh'] == '人工复核：两篇结论方向一致'


def test_item_values_route_original_quote_to_en_column() -> None:
    """引擎给的是「原文 + 中文翻译」，库里是「中文/英文」两列，别把原文丢了。"""
    values = SrdService._item_values(_item('1a', '0'))

    assert values['cite_a_zh'] == 'A 引用 1a'
    assert values['cite_a_en'] == 'A quote 1a'
    assert values['basis_en'] == 'reason 1a'


def test_item_values_reject_unknown_rating() -> None:
    """模型吐出档位外的值时降级成证据不足，而不是塞一个前端认不出的枚举进库。"""
    values = SrdService._item_values(_item('1a', '4'))

    assert (values['rating'], values['score']) == ('unclear', None)


# --------------------------------------------------------------------------- 结果文件


def test_load_result_json_reads_path_from_summary(tmp_path: Path) -> None:
    target = tmp_path / 'result.json'
    target.write_text(json.dumps({'overall_pct': 46}), encoding='utf-8')

    loaded = asyncio.run(SrdService._load_result_json({'files': {'json': str(target)}}))

    assert loaded == {'overall_pct': 46}


def test_load_result_json_returns_none_when_unreadable(tmp_path: Path) -> None:
    """后端与 worker 没共享文件系统时就是这个分支，必须能被识别出来。"""
    assert asyncio.run(SrdService._load_result_json({'files': {'json': str(tmp_path / 'nope.json')}})) is None
    assert asyncio.run(SrdService._load_result_json({})) is None


# --------------------------------------------------------------------------- 轮询


def _sync(run: _SrdRun, state: dict) -> _SrdRun:
    """跑一次 `_sync_run`，写库与文件清理都打桩，只看它算出的状态。"""
    with patch.object(SrdService, '_cleanup_inputs', new=AsyncMock()), \
            patch('module_action.service.action_service.SrdDao.edit_assessment_dao', new=AsyncMock()):
        return asyncio.run(SrdService._sync_run(AsyncMock(), run, state))


def test_sync_run_records_progress_while_running() -> None:
    out = _sync(_run(), {'status': 'running', 'progress_current': 55, 'progress_total': 100, 'message': '判定 20/34'})

    assert (out.run_status, out.progress) == ('running', 55)


def test_sync_run_records_failure_reason() -> None:
    out = _sync(_run(), {'status': 'failed', 'error': '没有可用模型'})

    assert out.run_status == 'failed'
    assert out.error_msg == '没有可用模型'


def test_sync_run_falls_back_to_a_reason_when_worker_gives_none() -> None:
    """worker 有时只给状态不给原因；前端拿到空字符串会显示一个没有内容的错误框。"""
    out = _sync(_run(), {'status': 'stopped', 'error': ''})

    assert (out.run_status, out.error_msg) == ('stopped', '已停止')


def test_sync_run_is_idempotent_once_completed() -> None:
    """前端会一直轮询到用户离开页面，没这道闸就会每 3 秒重写一次 34 条目。"""
    done = _SrdRun(assessment_id=7, session_id='sid7', user_id=1, run_status='completed', progress=100, error_msg='')

    with patch.object(SrdService, '_persist_result', new=AsyncMock()) as persist:
        out = asyncio.run(SrdService._sync_run(AsyncMock(), done, {'status': 'completed', 'result': {}}))

    persist.assert_not_awaited()
    assert out is done


def test_sync_run_cleans_up_inputs_on_terminal_states() -> None:
    """用户上传的原文不该在任务结束后继续留在服务器上。"""
    for status in ('completed', 'failed', 'stopped'):
        with patch.object(SrdService, '_cleanup_inputs', new=AsyncMock()) as cleanup, \
                patch.object(SrdService, '_persist_result', new=AsyncMock(return_value=_run())), \
                patch('module_action.service.action_service.SrdDao.edit_assessment_dao', new=AsyncMock()):
            asyncio.run(SrdService._sync_run(AsyncMock(), _run(), {'status': status, 'result': {}}))

        cleanup.assert_awaited_once_with('sid7')


def test_persist_result_marks_failed_when_result_file_missing() -> None:
    """读不到结果就判失败，而不是落一份没有判定依据的报告 —— 用户会拿它当结论。"""
    with patch.object(SrdService, '_load_result_json', new=AsyncMock(return_value=None)), \
            patch.object(SrdService, '_mark_failed', new=AsyncMock()) as failed:
        asyncio.run(SrdService._persist_result(AsyncMock(), _run(), {}))

    assert failed.await_count == 1
    assert '共享文件系统' in failed.await_args.args[2]


# --------------------------------------------------------------------------- 越权


def test_get_assessment_hides_other_peoples_runs() -> None:
    """真实评估里是用户自己两篇文献的逐条比对，不是公开数据。"""
    other = type('Row', (), {'assessment_id': 9, 'is_sample': '0', 'user_id': 2})()

    with patch(
        'module_action.service.action_service.SrdDao.get_assessment_by_id', new=AsyncMock(return_value=other)
    ), pytest.raises(ServiceException) as exc:
        asyncio.run(SrdService.get_assessment_services(AsyncMock(), 9, user_id=1))

    # 「不存在」而不是「无权访问」：后者等于确认这个 id 是真的
    assert exc.value.message == '评估记录不存在'
