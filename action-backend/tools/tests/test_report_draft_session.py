"""报告草稿服务层的事务回归测试（用内存 SQLite 跑真 async 会话，不连业务库、不调模型）。

**为什么值得为一个方法单独开一个文件**：`create_draft_services` 要连着提交事务，而会话是
`expire_on_commit=True`。commit 之后再读任何 ORM 属性（**包括主键**）都会触发一次懒加载，
在 async 会话里直接抛 `MissingGreenlet` —— 表现是「一份草稿都建不出来」，而纯函数单测
和 ruff 都看不见它。CLAUDE.md 里 SRD 那条链路记着同一个坑，这里再踩一次说明光靠注释提醒
不够，得有一条会红的测试钉住。

会话参数照抄 `config/database.py::create_async_session_local`（`expire_on_commit` 取默认
True），否则这条测试就失去意义。
"""

from __future__ import annotations

import asyncio

import pytest
from exceptions.exception import ServiceException
from module_action.entity.do.action_do import ActionReportDraft, ActionReportDraftItem
from module_action.entity.vo.action_vo import ReportDraftCreateModel
from module_action.service.action_service import ReportDraftService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


class _Guideline:
    """够用的规范桩：服务层只读这两个字段"""

    guideline_id = 1
    code = 'STRICTA'


ITEM_ROWS = [
    {'itemId': 11, 'domainZh': '方法', 'itemNoZh': '1', 'contentZh': '针刺细节：选穴与进针深度', 'requireLevel': '0'},
    {'itemId': 12, 'domainZh': '方法', 'itemNoZh': '2', 'contentZh': '对照措施设置', 'requireLevel': '1'},
]


async def _run(monkeypatch: pytest.MonkeyPatch) -> tuple[int, str, int]:
    """建库 → 建草稿 → 保存 → 再读回来，全程走真 async 会话与真 commit。"""
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(ActionReportDraft.__table__.create)
        await conn.run_sync(ActionReportDraftItem.__table__.create)
    # 与 config/database.py 一致：不传 expire_on_commit，用默认的 True
    session_maker = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

    async def _by_code(_db: object, _code: str) -> object:
        return _Guideline()

    async def _by_id(_db: object, _gid: int) -> object:
        return _Guideline()

    async def _items(*_args: object, **_kwargs: object) -> list[dict]:
        return ITEM_ROWS

    monkeypatch.setattr('module_action.service.action_service.GuidelineDao.get_guideline_by_code', _by_code)
    monkeypatch.setattr('module_action.service.action_service.GuidelineDao.get_guideline_detail_by_id', _by_id)
    monkeypatch.setattr('module_action.service.action_service.GuidelineItemDao.get_item_list', _items)

    from module_action.entity.vo.action_vo import ReportDraftCreateModel, ReportDraftItemModel, ReportDraftSaveModel

    async with session_maker() as db:
        created = await ReportDraftService.create_draft_services(
            db, ReportDraftCreateModel(guidelineCode='STRICTA', studyTypeKey='rct', title=''), 42
        )
        saved = await ReportDraftService.save_draft_services(
            db,
            created.draft_id,
            ReportDraftSaveModel(
                title='电针 RCT',
                items=[ReportDraftItemModel(itemId=11, content='针刺操作如下。')],
            ),
            42,
        )
        composed = await ReportDraftService.compose_draft_services(db, created.draft_id, 42)

    await engine.dispose()

    return created.draft_id, composed.text, saved.required_filled


def test_create_and_save_survive_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """建草稿在 commit 之后仍要能装出出参 —— 这条挂掉就是「一份草稿都建不出来」。"""
    draft_id, text, required_filled = asyncio.run(_run(monkeypatch))

    assert draft_id > 0
    assert '针刺操作如下。' in text
    # 条目 11 是必填且已填，条目 12 是选填 —— 必填完成度 1/1
    assert required_filled == 1


def test_requirement_text_never_reaches_the_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    """条目要求原文不许进正文：混进去之后第三步会把这句要求本身判成「已报告」。"""
    _draft_id, text, _ = asyncio.run(_run(monkeypatch))

    assert '针刺细节：选穴与进针深度' not in text
    assert '对照措施设置' not in text


async def _new_session(monkeypatch: pytest.MonkeyPatch):
    """建库 + 打桩，返回可用的会话工厂"""
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(ActionReportDraft.__table__.create)
        await conn.run_sync(ActionReportDraftItem.__table__.create)

    async def _by_code(_db: object, _code: str) -> object:
        return _Guideline()

    async def _by_id(_db: object, _gid: int) -> object:
        return _Guideline()

    async def _items(*_args: object, **_kwargs: object) -> list[dict]:
        return ITEM_ROWS

    monkeypatch.setattr('module_action.service.action_service.GuidelineDao.get_guideline_by_code', _by_code)
    monkeypatch.setattr('module_action.service.action_service.GuidelineDao.get_guideline_detail_by_id', _by_id)
    monkeypatch.setattr('module_action.service.action_service.GuidelineItemDao.get_item_list', _items)

    return engine, async_sessionmaker(autocommit=False, autoflush=False, bind=engine)


async def _run_create_only(monkeypatch: pytest.MonkeyPatch):
    """建一份草稿，返回 (出参模型, 落库后的 ORM 行)"""
    engine, session_maker = await _new_session(monkeypatch)
    async with session_maker() as db:
        created = await ReportDraftService.create_draft_services(
            db, ReportDraftCreateModel(guidelineCode='STRICTA', studyTypeKey='rct', title=''), 42
        )
        row = (await db.execute(select(ActionReportDraft).where(ActionReportDraft.draft_id == created.draft_id))
               ).scalars().first()
        # 会话是 expire_on_commit=True，出了 with 再读属性会懒加载 —— 先取成普通值
        defaults = (row.acu_basis, row.acu_needle, row.create_by)
    await engine.dispose()

    return created, defaults


async def _run_compose_empty(monkeypatch: pytest.MonkeyPatch):
    engine, session_maker = await _new_session(monkeypatch)
    try:
        async with session_maker() as db:
            created = await ReportDraftService.create_draft_services(
                db, ReportDraftCreateModel(guidelineCode='STRICTA', studyTypeKey='rct', title=''), 42
            )
            await ReportDraftService.compose_draft_services(db, created.draft_id, 42)
    finally:
        await engine.dispose()


def test_empty_string_defaults_are_truly_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """空串默认值必须真的是空串。

    DO 里若写成 `server_default="''"`，DDL 会渲染成 `DEFAULT ''''''` —— 默认值变成
    「两个引号字符」这个**非空**字符串。表在本测试里由 `__table__.create` 建出，
    与应用启动时的 `create_all` 同一条路径，所以这条测试盯得住那个坑。

    断言落在 acu_* 上是因为**只有这几列在建表时用得到默认值**（其余几列服务层都显式赋了值），
    换句话说它们眼下的用处就是当这个坑的探针 —— 列本身已停用，见 `ActionReportDraft` 的
    类 docstring。哪天真要 drop 这几列，把探针改到别的空串列上，别把这条测试一起删了。
    """
    created, (acu_basis, acu_needle, create_by) = asyncio.run(_run_create_only(monkeypatch))

    assert acu_basis == ''
    assert acu_needle == ''
    assert create_by == '42'
    assert created.title == 'STRICTA 报告初稿'


def test_empty_draft_refuses_to_compose_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """一份刚建出来、一个字没填的草稿不许合成 —— 上一条挂掉时这条会跟着挂。"""
    with pytest.raises(ServiceException) as got:
        asyncio.run(_run_compose_empty(monkeypatch))

    assert '还没有任何内容' in got.value.message
