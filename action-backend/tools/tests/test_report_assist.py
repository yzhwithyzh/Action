"""第四步「AI 辅助撰写」的单测（不连库、不调模型）。

盯的是几件「错了会直接骗人或伤到用户」的事：
- 提示词里那三条硬约束（不编造数据 / 不新增方法学事实 / 只输出正文）必须每次都发出去
- 条目要求当**指令**用，不能被当成待续写的素材 —— 与 `report_compose_service` 那条
  「条目要求原文不许进稿件」是同一个坑的两端
- 模型池全挂时如实报错，不静默返回空串（空串会被用户读成「AI 觉得没什么好改的」）
- 润色/翻译在没有正文时必须在**调模型之前**被挡下来，否则是一次白花钱的调用
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
from exceptions.exception import ServiceException
from module_action.service.ai_assist_service import AiAssistService, _endpoint, _extract_text
from module_action.service.report_assist_prompt import (
    AssistContext,
    build_messages,
    needs_current_text,
)

CTX = AssistContext(
    guideline_code='STRICTA',
    item_no='6a',
    domain='方法',
    requirement='针刺细节：选穴依据、进针深度与得气反应',
    current_text='取患侧阳陵泉（GB34）。',
    verdict='vague',
    verdict_reason='未写进针深度与得气',
)


# 独立模式的两种上下文：只有规范代号（第一步给的），与什么都没有
CTX_GUIDELINE_ONLY = AssistContext(guideline_code='STRICTA', current_text='取患侧阳陵泉。')
CTX_BARE = AssistContext(current_text='取患侧阳陵泉。')


# ---------------------------------------------------------------- 提示词


def test_guardrails_ride_along_on_every_action() -> None:
    """三条硬约束每个动作都要带上：这是学术报告工具，编个 p 值出来是科研诚信事故。"""
    for action in ('continue', 'polish', 'translate'):
        system = build_messages(action, CTX, keywords='电针 疏密波')[0]['content']
        assert '绝不编造' in system, action
        assert '绝不新增未提供的方法学事实' in system, action
        assert '只输出正文本身' in system, action


def test_requirement_is_an_instruction_not_material() -> None:
    """条目要求进 system 当指令，不进 user 当素材 —— 进了 user 模型就会把它抄进正文。"""
    msgs = build_messages('continue', CTX, keywords='电针 疏密波')
    assert CTX.requirement in msgs[0]['content']
    assert CTX.requirement not in msgs[1]['content']


def test_step3_verdict_is_handed_to_the_model() -> None:
    """第四步的输入就是第三步的判定，不带过去这一步又变回孤立的演示场。"""
    system = build_messages('polish', CTX)[0]['content']
    assert '描述模糊' in system
    assert '未写进针深度与得气' in system


def test_clean_items_carry_no_verdict_block() -> None:
    """判为已报告（或没判过）的条目不该被塞一句「改写要正面解决这个问题」。"""
    for verdict in ('', 'reported'):
        system = build_messages('polish', AssistContext(current_text='正文', verdict=verdict))[0]['content']
        assert '第三步校验判定' not in system, verdict


def test_polish_styles_differ() -> None:
    """三种风格必须给出不同的指令，否则切换就是个摆设。"""
    outs = {s: build_messages('polish', CTX, style=s)[0]['content'] for s in ('rigorous', 'concise', 'critical')}
    assert len(set(outs.values())) == 3


def test_unknown_style_falls_back_instead_of_crashing() -> None:
    """风格是前端传来的，不认识的值兜到 rigorous，不能 500。"""
    assert build_messages('polish', CTX, style='bogus')[0]['content'] == (
        build_messages('polish', CTX, style='rigorous')[0]['content']
    )


def test_translate_always_targets_english() -> None:
    """这个功能存在的理由就是投稿国际期刊，界面语言不该改变译文方向。"""
    for locale in ('zh', 'en'):
        system = build_messages('translate', CTX, locale=locale)[0]['content']
        assert 'English' in system or '英文' in system


def test_unknown_action_is_rejected() -> None:
    with pytest.raises(ValueError, match='未知的改写动作'):
        build_messages('bogus', CTX)


def test_only_rewrites_need_existing_text() -> None:
    """润色与翻译改的是已有内容；续写只要关键词就够。"""
    assert needs_current_text('polish')
    assert needs_current_text('translate')
    assert not needs_current_text('continue')


# ---------------------------------------------------------------- 调用层


def test_endpoint_tolerates_both_base_url_shapes() -> None:
    """库里存的可能是 `.../v1`，也可能已经带了 `/chat/completions`。"""
    assert _endpoint('https://x/v1') == 'https://x/v1/chat/completions'
    assert _endpoint('https://x/v1/') == 'https://x/v1/chat/completions'
    assert _endpoint('https://x/v1/chat/completions') == 'https://x/v1/chat/completions'
    assert _endpoint(None).endswith('/chat/completions')


def test_extract_text_survives_a_malformed_response() -> None:
    """厂商返回缺字段时返回空串，由上层当「这个模型不可用」处理，不抛 KeyError。"""
    assert _extract_text({'choices': [{'message': {'content': ' hi '}}]}) == 'hi'
    assert _extract_text({}) == ''
    assert _extract_text({'choices': []}) == ''
    assert _extract_text({'choices': [{}]}) == ''


class _Model:
    def __init__(self, mid: int) -> None:
        self.model_id = mid
        self.provider = 'OpenAI'
        self.model_code = f'm{mid}'
        self.model_name = f'm{mid}'
        self.api_key = 'k'
        self.base_url = 'https://x/v1'
        self.max_tokens = 800


def _patch_pool(monkeypatch: pytest.MonkeyPatch, pool: list) -> None:
    async def _pool(*_a: object, **_k: object) -> list:
        return pool

    monkeypatch.setattr(
        'module_action.service.ai_assist_service.AiModelService.get_usable_ai_model_pool_services', _pool
    )


def test_empty_pool_reports_honestly(monkeypatch: pytest.MonkeyPatch) -> None:
    """没有可用模型时如实报错。静默返回空串会被用户读成「AI 觉得没什么好改的」。"""
    _patch_pool(monkeypatch, [])

    with pytest.raises(ServiceException) as got:
        asyncio.run(AiAssistService.rewrite(object(), action='polish', ctx=CTX))

    assert '暂无可用的AI模型' in got.value.message


def test_failover_moves_to_the_next_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """第一个模型限流，第二个应当接上 —— 这就是维护一个池子的全部意义。"""
    _patch_pool(monkeypatch, [_Model(1), _Model(2)])
    tried: list[str] = []

    async def _call(model: object, _messages: list) -> str:
        tried.append(model.model_code)
        if model.model_code == 'm1':
            raise httpx.HTTPStatusError('429', request=None, response=httpx.Response(429))
        return '润色后的正文'

    monkeypatch.setattr(AiAssistService, '_call_one', classmethod(lambda cls, m, msgs, *_: _call(m, msgs)))
    text, label = asyncio.run(AiAssistService.rewrite(object(), action='polish', ctx=CTX))

    assert tried == ['m1', 'm2']
    assert text == '润色后的正文'
    assert '#2' in label


def test_all_models_down_raises_rather_than_returning_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_pool(monkeypatch, [_Model(1), _Model(2)])

    async def _call(_model: object, _messages: list) -> str:
        raise httpx.ConnectTimeout('boom')

    monkeypatch.setattr(AiAssistService, '_call_one', classmethod(lambda cls, m, msgs, *_: _call(m, msgs)))

    with pytest.raises(ServiceException) as got:
        asyncio.run(AiAssistService.rewrite(object(), action='polish', ctx=CTX))

    assert '已尝试 2 个模型' in got.value.message


def test_blank_output_counts_as_a_failed_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """模型 200 了但正文是空的，同样算这一个不可用 —— 不能把空串当成改写结果交出去。"""
    _patch_pool(monkeypatch, [_Model(1), _Model(2)])

    async def _call(model: object, _messages: list) -> str:
        return '' if model.model_code == 'm1' else '有内容'

    monkeypatch.setattr(AiAssistService, '_call_one', classmethod(lambda cls, m, msgs, *_: _call(m, msgs)))
    text, label = asyncio.run(AiAssistService.rewrite(object(), action='polish', ctx=CTX))

    assert text == '有内容'
    assert '#2' in label


# ---------------------------------------------------------------- 独立模式（不带草稿/条目）
#
# 文档第 4 节四项功能的输入全是用户直接给的，没有一项依赖第二步的草稿或第三步的判定。
# 这一组钉的就是「没有条目也构造得出一份像样的提示词」。


def test_guideline_only_context_still_names_the_guideline() -> None:
    """独立模式的常态：第一步匹配到了规范，但用户没有草稿、也没挑具体条目。

    「遵循 STRICTA」要的就是这句话 —— 它不需要「站在某一条上」。
    """
    system = build_messages('polish', CTX_GUIDELINE_ONLY)[0]['content']

    assert 'STRICTA' in system
    # 没有条目要求时不许留一个空的「写作依据」标题：标题下面空着会让模型去猜依据
    assert '照它写，不要抄它' not in system


def test_bare_context_builds_without_any_requirement_block() -> None:
    """连规范都没有（用户跳过第一步直接来第四步）也要能跑，且硬约束一条不少。"""
    msgs = build_messages('polish', CTX_BARE)
    system = msgs[0]['content']

    assert '写作依据' not in system
    assert '绝不编造' in system
    assert '取患侧阳陵泉。' in msgs[1]['content']


def test_guardrails_survive_in_standalone_mode() -> None:
    """解耦不能把三条硬约束一起解掉 —— 独立模式反而更容易被当成通用文案生成器。"""
    for ctx in (CTX_GUIDELINE_ONLY, CTX_BARE):
        for action in ('continue', 'polish', 'translate'):
            system = build_messages(action, ctx, keywords='电针 疏密波')[0]['content']
            assert '绝不编造' in system
            assert '绝不新增未提供的方法学事实' in system


def test_verdict_block_absent_without_a_verdict() -> None:
    """独立模式没有第三步判定，那一段就不该出现（而不是出现一个空判定）。"""
    assert '第三步校验判定' not in build_messages('polish', CTX_GUIDELINE_ONLY)[0]['content']
    assert '第三步校验判定' in build_messages('polish', CTX)[0]['content']
