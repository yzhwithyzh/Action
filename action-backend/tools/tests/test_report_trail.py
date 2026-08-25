"""操作留痕的回归测试（用内存 SQLite 跑真 async 会话，不连业务库）。

盯的是两件事：

1. **commit 之后仍要能装出出参。** 会话是 `expire_on_commit=True`，commit 之后再读任何
   ORM 属性（**包括主键**）都会触发懒加载，在 async 会话里直接抛 `MissingGreenlet`。
   实跑时踩到过：`add_trail_services` 原本先 commit 再 `_to_model`，表现是「留痕一条也记不下」。
   CLAUDE.md 里 SRD 那条链路记着同一个坑，这里再踩一次说明光靠注释不够，得有条会红的测试。

2. **留痕只收数字与枚举。** 事件类型必须是白名单里的键，人读的句子由前端渲染 ——
   库里若存渲染好的句子，句子里迟早会混进稿件正文片段，第三步「稿件不入库」的承诺就绕过去了。
"""

from __future__ import annotations

import asyncio

import pytest
from module_action.entity.do.action_do import ActionReportTrail
from module_action.entity.vo.action_vo import TrailAddModel
from module_action.service.action_service import ReportTrailService
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


async def _session():
    """建库 + 会话工厂。与 config/database.py 一致：不传 expire_on_commit，用默认的 True"""
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(ActionReportTrail.__table__.create)

    return engine, async_sessionmaker(autocommit=False, autoflush=False, bind=engine)


async def _add_then_list(user_id: int = 42):
    engine, maker = await _session()
    try:
        async with maker() as db:
            first = await ReportTrailService.add_trail_services(
                db,
                TrailAddModel(event='submitted', draftId=7, guidelineCode='STRICTA', actor='张三', charCount=8421),
                user_id,
            )
            await ReportTrailService.add_trail_services(
                db,
                TrailAddModel(
                    event='judged', draftId=7, actor='deepseek', total=21, reported=14, vague=4,
                    missing=3, completeness=67,
                ),
                user_id,
            )
            mine = await ReportTrailService.get_trail_list_services(db, user_id, 7)
            other = await ReportTrailService.get_trail_list_services(db, user_id + 999, 7)

            return first, mine, other
    finally:
        await engine.dispose()


def test_add_survives_commit() -> None:
    """这条挂掉就是「留痕一条也记不下」—— 主键在 commit 之后读不出来。"""
    first, mine, _ = asyncio.run(_add_then_list())

    assert first.trail_id > 0
    assert first.event == 'submitted'
    assert first.char_count == 8421
    assert len(mine) == 2


def test_latest_first() -> None:
    """审计列表要最近的在前，否则翻到最后才看得见刚发生的事。"""
    _, mine, _ = asyncio.run(_add_then_list())

    assert [r.event for r in mine] == ['judged', 'submitted']


def test_other_users_trail_is_invisible() -> None:
    """越权保护在 DAO 的 where 里，不靠上层写 if。"""
    _, _, other = asyncio.run(_add_then_list())

    assert other == []


def test_counts_round_trip() -> None:
    """留痕存的就是这几个数 —— 前端靠它们拼句子，错一个句子就是错的。"""
    _, mine, _ = asyncio.run(_add_then_list())
    judged = mine[0]

    assert (judged.total, judged.reported, judged.vague, judged.missing) == (21, 14, 4, 3)
    assert judged.completeness == 67


def test_event_is_a_whitelist_not_free_text() -> None:
    """事件是枚举。能传任意字符串，就等于给「库里不存渲染好的句子」开了个后门。"""
    for bad in ('hacked', '', '已提交稿件：本研究纳入 120 例患者'):
        with pytest.raises(ValidationError):
            TrailAddModel(event=bad)


def test_note_is_length_capped() -> None:
    """note 是唯一的自由文本（仅供系统诊断），必须有长度闸，否则整篇稿件塞得进来。"""
    with pytest.raises(ValidationError):
        TrailAddModel(event='failed', note='x' * 301)


def test_completeness_is_a_percentage() -> None:
    for bad in (-1, 101):
        with pytest.raises(ValidationError):
            TrailAddModel(event='judged', completeness=bad)
