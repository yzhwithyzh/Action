"""第三步 checklist 校验的落库与历史链路的行为测试。

覆盖的是**后端这一半**：worker 的结果摘要 → 两张业务表的字段映射、轮询在各种任务状态下
的动作，以及删除时那条「正文要真删」的口径。逐条判定算法在
`tools/checklist_worker_tool` 里测，这里不重复。

为什么值得单独测：这一层是 014 新加的，而它改掉的恰恰是一条**沉默失败**的路径 ——
原先落库由前端在轮到 completed 那一刻发起，用户刷新一下就没人来落库，
库里既没有结果也没有任何痕迹，事后无从判断「是没跑，还是跑了没存」。

跑法：python -m pytest tests/test_checklist_review_history.py -q
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from exceptions.exception import ServiceException
from module_action.entity.do.action_do import ActionReportReview, ActionReportReviewItem
from module_action.service.action_service import ChecklistReviewService, _ReviewRun

# --------------------------------------------------------------------------- 夹具


#: 夹具里那条记录的 id，断言里要拿它对比，别写成裸数字
REVIEW_ID = 12


def _run(**over: object) -> _ReviewRun:
    base = {
        'review_id': REVIEW_ID,
        'session_id': 'sid12',
        'user_id': 1,
        'guideline_id': 3,
        # 默认是「只判定」：回填只在 import 那一次做，别让这批夹具意外走到回填分支
        'purpose': 'check',
        'draft_id': None,
        'run_status': 'running',
        'progress': 40,
        'error_msg': '',
    }

    return _ReviewRun(**{**base, **over})  # type: ignore[arg-type]


def _result() -> dict:
    """一份 worker 风格的结果摘要（`checklist_session_task.process` 的返回值）。"""
    return {
        'guidelineCode': 'STRICTA',
        'locale': 'zh',
        'summary': {'total': 3, 'reported': 1, 'vague': 1, 'missing': 1, 'completeness': 50},
        'verdicts': [
            {'itemId': 101, 'status': 'reported', 'reason': '第 12 行写明了选穴依据', 'evidence': '取双侧肾俞、大肠俞', 'lines': [12]},
            {'itemId': 102, 'status': 'vague', 'reason': '只说「行提插捻转」，未给深度', 'evidence': '按常规深度直刺进针', 'lines': [18, 19]},
            {'itemId': 103, 'status': 'missing', 'reason': '全文未见针具规格', 'evidence': '', 'lines': []},
        ],
        'consistency': {'summary': {'ok': 2, 'warn': 1, 'issue': 0, 'na': 1, 'unchecked': 0}, 'checks': [], 'truncated': False},
        'lineCount': 96,
        'truncated': False,
        'itemCount': 3,
        'models': ['deepseek-chat', 'qwen-max'],
    }


def _persist(result: dict, valid_ids: set[int] | None = None) -> dict:
    """跑一次 `_persist_result`，只看它算出的列值与写下去的判定行。"""
    items = [{'itemId': i} for i in (valid_ids if valid_ids is not None else {101, 102, 103})]
    captured: dict = {}

    async def _edit(_db: object, _rid: int, values: dict) -> None:
        captured['values'] = values

    async def _replace(_db: object, _rid: int, rows: list) -> None:
        captured['rows'] = rows

    with patch(
        'module_action.service.action_service.ReportDraftService._items_of', new=AsyncMock(return_value=items)
    ), patch(
        'module_action.service.action_service.ReportReviewDao.edit_review_dao', new=_edit
    ), patch(
        'module_action.service.action_service.ReportReviewDao.replace_review_items_dao', new=_replace
    ):
        asyncio.run(ChecklistReviewService._persist_result(AsyncMock(), _run(), result))

    return captured


# --------------------------------------------------------------------------- 字段映射


def test_persist_result_maps_summary_and_models() -> None:
    """摘要三档、完整度、行数、模型名都得原样落库 —— 历史列表整行都靠它们渲染。"""
    values = _persist(_result())['values']

    assert (values['run_status'], values['progress']) == ('completed', 100)
    assert (values['reported'], values['vague'], values['missing']) == (1, 1, 1)
    assert (values['item_total'], values['completeness'], values['line_count']) == (3, 50, 96)
    assert values['truncated'] == '0'
    # 模型名拼成一行存，排障时「同一份稿件换个模型判出两样结果」全靠这一列分辨
    assert values['models'] == 'deepseek-chat / qwen-max'
    assert values['error_msg'] == ''
    assert values['finish_time'] is not None


def test_persist_result_converts_line_numbers_to_csv() -> None:
    """引擎给的是数字数组，库里那一列是逗号分隔字符串 —— 转换在这里，不在渲染层。"""
    rows = {r['item_id']: r for r in _persist(_result())['rows']}

    assert rows[101]['lines'] == '12'
    assert rows[102]['lines'] == '18,19'
    assert rows[103]['lines'] == ''


def test_persist_result_keeps_evidence() -> None:
    """evidence 是回看时唯一能定位回原文的东西，014 起随稿件一起存。"""
    rows = {r['item_id']: r for r in _persist(_result())['rows']}

    assert rows[101]['evidence'] == '取双侧肾俞、大肠俞'
    assert rows[102]['reason'].startswith('只说')


def test_persist_result_drops_verdicts_on_unknown_items() -> None:
    """条目 id 来自 worker，而后台可能在任务跑着的时候停用了某几条。

    落进来就是一批孤儿：第四步按 item_id 取要求原文取不到，渲染成一排空白。
    """
    captured = _persist(_result(), valid_ids={101})

    assert [r['item_id'] for r in captured['rows']] == [101]
    # 计数、条目总数、完整度**全部跟着实际落库的行重算**，不照抄 worker 的摘要 ——
    # 否则历史行显示「共 3 条、完整度 50%」而点开只有 1 条，且方向永远是「看起来判得比实际多」
    values = captured['values']
    assert (values['reported'], values['vague'], values['missing']) == (1, 0, 0)
    assert (values['item_total'], values['completeness']) == (1, 100)


def test_persist_result_completeness_counts_vague_as_half() -> None:
    """完整度权重与引擎 `STATUS_WEIGHT` 是同一张表：模糊算半条。

    两处必须一致 —— 不一致的表现是「同一次校验，进度跑完那一刻显示 50%，
    从历史点开变成 33%」，而两个数字都没有明显错到能被一眼看出来。
    """
    values = _persist(_result())['values']

    # reported 1 + vague 0.5 + missing 0 = 1.5 / 3 = 50%
    assert (values['item_total'], values['completeness']) == (3, 50)


def test_persist_result_ignores_malformed_verdicts() -> None:
    """模型偶尔会吐出档位外的 status 或缺 itemId 的行，不该让整次落库炸掉。"""
    bad = _result()
    bad['verdicts'] = [
        {'itemId': 101, 'status': 'unknown', 'reason': 'x'},
        {'status': 'reported', 'reason': '没有 itemId'},
        'not a dict',
        {'itemId': 102, 'status': 'vague', 'reason': 'ok'},
    ]
    captured = _persist(bad)

    assert [r['item_id'] for r in captured['rows']] == [102]


def test_persist_result_stores_consistency_as_json() -> None:
    """一致性结果整块存 JSON：读取模式只有「整份取回渲染」，且形状跟着引擎规则表走。"""
    values = _persist(_result())['values']

    assert values['consistency'] is not None
    assert '"warn": 1' in values['consistency'] or '"warn":1' in values['consistency']


def test_persist_result_tolerates_empty_result() -> None:
    """worker 给了 completed 却没有结果时，也要落成一条能看的记录而不是抛异常。"""
    captured = _persist({})

    assert captured['rows'] == []
    assert captured['values']['run_status'] == 'completed'
    assert captured['values']['consistency'] is None


# --------------------------------------------------------------------------- 轮询


def _sync(run: _ReviewRun, state: dict) -> _ReviewRun:
    """跑一次 `_sync_run`，写库打桩，只看它算出的状态。"""
    with patch('module_action.service.action_service.ReportReviewDao.edit_review_dao', new=AsyncMock()):
        return asyncio.run(ChecklistReviewService._sync_run(AsyncMock(), run, state))


def test_sync_run_records_progress_while_running() -> None:
    out = _sync(_run(), {'status': 'running', 'progress_current': 55, 'progress_total': 100, 'message': '判定 20/34'})

    assert (out.run_status, out.progress) == ('running', 55)


def test_sync_run_records_failure_reason() -> None:
    out = _sync(_run(), {'status': 'failed', 'error': '没有可用模型'})

    assert (out.run_status, out.error_msg) == ('failed', '没有可用模型')


def test_sync_run_falls_back_to_a_reason_when_worker_gives_none() -> None:
    """worker 有时只给状态不给原因；前端拿到空字符串会显示一个没有内容的错误框。"""
    out = _sync(_run(), {'status': 'stopped', 'error': ''})

    assert (out.run_status, out.error_msg) == ('stopped', '已停止')


def test_sync_run_is_idempotent_once_completed() -> None:
    """前端会一直轮询到用户离开页面，没这道闸就会每 2 秒重写一次 282 条判定。"""
    done = _run(run_status='completed', progress=100)

    with patch.object(ChecklistReviewService, '_persist_result', new=AsyncMock()) as persist:
        out = asyncio.run(ChecklistReviewService._sync_run(AsyncMock(), done, {'status': 'completed', 'result': {}}))

    persist.assert_not_awaited()
    assert out is done


def test_state_marks_expired_task_failed_not_silently_running() -> None:
    """Redis 的任务状态有 TTL。查不到又还挂着 running 的，是真过期了，得说出来。

    不标失败的话，历史列表里那一行会永远停在「校验中」，而它其实早就没人在跑了。
    """
    record = ActionReportReview(
        review_id=REVIEW_ID, session_id='sid12', user_id=1, guideline_id=3, run_status='running', progress=40, error_msg=''
    )
    with patch(
        'module_action.service.action_service.ReportReviewDao.get_review_by_session_dao',
        new=AsyncMock(return_value=record),
    ), patch.object(
        ChecklistReviewService, '_fetch_worker_state', new=AsyncMock(return_value=None)
    ), patch.object(
        ChecklistReviewService, '_mark_failed', new=AsyncMock(return_value=_run(run_status='failed', error_msg='任务状态已过期，请重新提交'))
    ) as failed:
        out = asyncio.run(ChecklistReviewService.review_state_services(AsyncMock(), 'sid12', 1))

    assert failed.await_count == 1
    assert out.status == 'failed'
    # reviewId 要一路带回前端 —— 它是刷新之后重新找回这次校验的锚点
    assert out.review_id == REVIEW_ID


# --------------------------------------------------------------------------- 并发闸与孤儿


def _row(review_id: int, run_status: str, session_id: str = 'sid') -> ActionReportReview:
    return ActionReportReview(
        review_id=review_id, session_id=f'{session_id}{review_id}', user_id=1, guideline_id=3,
        run_status=run_status, progress=0, error_msg='',
    )


def test_reconcile_frees_slots_taken_by_orphans() -> None:
    """`pending` 孤儿不能把账号永久锁在门外。

    入队失败、worker 崩了、Redis 状态过了 TTL —— 都会留下一条永远等不到终态的记录，
    而它照样占着 `MAX_RUNNING_PER_USER` 的名额。用户看到的只有一句「你已有 2 个校验
    在进行中」，且**怎么等都不会消失**。对账必须能把它们判掉。
    """
    rows = [_row(1, 'pending'), _row(2, 'pending')]
    # 两趟查询：第一趟挑出待对账的，判完之后第二趟重新点名额
    after = [_row(1, 'failed'), _row(2, 'failed')]

    with patch(
        'module_action.service.action_service.ReportReviewDao.get_user_reviews_dao',
        new=AsyncMock(side_effect=[rows, after]),
    ), patch.object(
        # worker 那边查不到 —— 正是孤儿的特征
        ChecklistReviewService, '_fetch_worker_state', new=AsyncMock(return_value=None)
    ), patch.object(
        ChecklistReviewService, '_mark_failed', new=AsyncMock(return_value=_run(run_status='failed'))
    ) as failed:
        left = asyncio.run(ChecklistReviewService._reconcile_pending(AsyncMock(), 1))

    assert (failed.await_count, left) == (len(rows), 0)


def test_count_running_ignores_terminal_rows() -> None:
    """跑完/失败/停掉的记录不占名额 —— 否则用户跑满 2 次就再也提交不了。"""
    rows = [_row(1, 'completed'), _row(2, 'failed'), _row(3, 'stopped'), _row(4, 'running')]

    with patch(
        'module_action.service.action_service.ReportReviewDao.get_user_reviews_dao',
        new=AsyncMock(return_value=rows),
    ):
        assert asyncio.run(ChecklistReviewService._count_running(AsyncMock(), 1)) == 1


# --------------------------------------------------------------------------- 越权与删除


def test_state_hides_other_peoples_runs() -> None:
    """按 session_id 轮询也要限本人：拿到一个 id 就能读别人的判定不行。"""
    with patch(
        'module_action.service.action_service.ReportReviewDao.get_review_by_session_dao',
        new=AsyncMock(return_value=None),
    ), pytest.raises(ServiceException) as exc:
        asyncio.run(ChecklistReviewService.review_state_services(AsyncMock(), 'sid12', 1))

    assert exc.value.message == '校验任务不存在'


def test_stop_requires_ownership() -> None:
    """014 之前这个口只认 session_id —— 拿到一个 id 就能停任意用户在跑的校验。"""
    with patch(
        'module_action.service.action_service.ReportReviewDao.get_review_by_session_dao',
        new=AsyncMock(return_value=None),
    ), pytest.raises(ServiceException):
        asyncio.run(ChecklistReviewService.stop_review_services(AsyncMock(), 'sid12', 1))


def test_delete_history_hides_other_peoples_records() -> None:
    with patch(
        'module_action.service.action_service.ReportReviewDao.get_review_by_id_dao', new=AsyncMock(return_value=None)
    ), pytest.raises(ServiceException) as exc:
        asyncio.run(ChecklistReviewService.delete_history_services(AsyncMock(), 12, 1))

    assert exc.value.message == '校验记录不存在'


def test_manuscript_and_evidence_columns_are_nullable() -> None:
    """删除时要把正文与原文引用**写成 null**（真删），所以这两列必须可空。

    这是 014 存稿件的对价：用户点「删除」期待的是「那篇稿子没了」，
    而不是「列表里看不见了」。列不可空的话这条路径会在运行时炸掉。
    """
    assert ActionReportReview.__table__.c.manuscript.nullable
    assert ActionReportReviewItem.__table__.c.evidence.nullable


def test_draft_id_is_nullable() -> None:
    """外部粘贴稿件的用户（第三步真正的主用户）没有草稿可挂。

    这一列不可空，他们就永远进不了这张表 —— 历史也就只对一半用户存在。
    """
    assert ActionReportReview.__table__.c.draft_id.nullable


# --------------------------------------------------------------------------- 导入回填
#
# 「导入 = 跑一次 checklist 校验」，同一套 worker、同一个引擎、同一张结果表，
# 区别只在 purpose='import' 那一次跑完会**回填草稿条目**。这一组钉的就是那个开关，
# 以及回填取原文的方式。


def test_backfill_only_runs_for_import() -> None:
    """`check` 那次绝不能回填。

    不分用途的话，用户之后每复查一次，回填就把他在第二步的编辑整个盖掉一遍 ——
    而且发生得悄无声息（判定看起来一切正常）。
    """
    with patch.object(ChecklistReviewService, '_backfill_draft', new=AsyncMock()) as backfill, patch(
        'module_action.service.action_service.ReportDraftService._items_of', new=AsyncMock(return_value=[])
    ), patch(
        'module_action.service.action_service.ReportReviewDao.edit_review_dao', new=AsyncMock()
    ), patch(
        'module_action.service.action_service.ReportReviewDao.replace_review_items_dao', new=AsyncMock()
    ):
        asyncio.run(ChecklistReviewService._persist_result(AsyncMock(), _run(purpose='check', draft_id=9), _result()))
        backfill.assert_not_awaited()

        asyncio.run(ChecklistReviewService._persist_result(AsyncMock(), _run(purpose='import', draft_id=9), _result()))
        assert backfill.await_count == 1


def test_backfill_needs_a_draft() -> None:
    """purpose=import 但没有 draft_id 是上游 bug，别在这里炸掉整次判定。"""
    with patch.object(ChecklistReviewService, '_backfill_draft', new=AsyncMock()) as backfill, patch(
        'module_action.service.action_service.ReportDraftService._items_of', new=AsyncMock(return_value=[])
    ), patch(
        'module_action.service.action_service.ReportReviewDao.edit_review_dao', new=AsyncMock()
    ), patch(
        'module_action.service.action_service.ReportReviewDao.replace_review_items_dao', new=AsyncMock()
    ):
        asyncio.run(ChecklistReviewService._persist_result(AsyncMock(), _run(purpose='import', draft_id=None), _result()))

    backfill.assert_not_awaited()


def test_backfill_failure_does_not_void_the_verdict() -> None:
    """回填炸了，判定仍然算数 —— 它已经落库了，用户至少还能在第三步看结果。"""
    with patch.object(
        ChecklistReviewService, '_backfill_draft', new=AsyncMock(side_effect=RuntimeError('boom'))
    ), patch(
        'module_action.service.action_service.ReportDraftService._items_of', new=AsyncMock(return_value=[])
    ), patch(
        'module_action.service.action_service.ReportReviewDao.edit_review_dao', new=AsyncMock()
    ), patch(
        'module_action.service.action_service.ReportReviewDao.replace_review_items_dao', new=AsyncMock()
    ):
        out = asyncio.run(
            ChecklistReviewService._persist_result(AsyncMock(), _run(purpose='import', draft_id=9), _result())
        )

    assert out.run_status == 'completed'
