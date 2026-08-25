"""适配层单测：错误分类与「解析失败也要重试」。

重点是那条最容易被漏掉的路径 —— 解析失败**没有异常**（HTTP 200，LangChain 把它
塞进 `parsing_error` 字段），如果只在事后读一下这个字段就返回错误，它就绕过了
整条重试/切换梯子。判定侧拿不到对象等于整组条目降级 unclear。
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel

from srd_engine.adapters.langchain_client import (
    DISABLE,
    FATAL,
    RETRY,
    SWITCH,
    LlmRunner,
    StructuredParseError,
    classify_error,
    repair_message,
)
from srd_engine.config import FailoverConfig, ModelConfig


class Answer(BaseModel):
    value: str = ''


class FakeChain:
    """假的 with_structured_output 链，按预设脚本逐次返回，并记下每次收到的 messages。

    脚本项是 dict 就直接返回，是异常就抛出去。
    """

    def __init__(self, script: list):
        self.script = script
        self.calls = 0
        self.seen: list[list] = []

    async def ainvoke(self, messages):
        self.calls += 1
        self.seen.append(list(messages))
        item = self.script[min(self.calls - 1, len(self.script) - 1)]
        if isinstance(item, BaseException):
            raise item
        return item


class FakeModel:
    def __init__(self, chain: FakeChain):
        self._chain = chain
        self.methods: list[str] = []

    def with_structured_output(self, schema, method='json_schema', include_raw=False):
        self.methods.append(method)
        return self._chain

    async def ainvoke(self, messages):
        """text 模式走的是模型本身，不走 chain。"""
        self.methods.append('text')
        return await self._chain.ainvoke(messages)


def _runner(script: list, cfg: ModelConfig | None = None, **kw) -> tuple[LlmRunner, FakeChain]:
    chain = FakeChain(script)
    runner = LlmRunner(cfg or ModelConfig(model='fake'), max_concurrency=1,
                       failover=FailoverConfig(freeze_seconds=0.0, **kw))
    model = FakeModel(chain)
    runner._model = lambda cfg, temp: model   # 替掉「建模型」这一步，不碰网络
    chain.model = model
    return runner, chain


OK = {'raw': None, 'parsed': Answer(value='好了'), 'parsing_error': None}
BAD = {'raw': None, 'parsed': None, 'parsing_error': 'Invalid json output: {"value": '}


# --------------------------------------------------------------------------- 错误分类


def test_parse_error_is_retryable():
    assert classify_error(StructuredParseError('Invalid json output')) == RETRY


def test_parse_error_is_not_misread_as_rate_limit_or_content_filter():
    """解析失败的消息里裹着模型原始输出，综述正文出现「限流」「敏感」都不奇怪。

    先按类型判掉，否则会被关键词扫成 SWITCH（换模型没用）或 FATAL（直接判死）。
    """
    assert classify_error(StructuredParseError('…原文提到限流与敏感人群…')) == RETRY
    assert classify_error(StructuredParseError('rate limit 出现在引文里')) == RETRY


def test_exception_name_fallback():
    assert classify_error(type('RateLimitError', (Exception,), {})()) == SWITCH
    assert classify_error(type('AuthenticationError', (Exception,), {})()) == DISABLE
    assert classify_error(type('BadRequestError', (Exception,), {})()) == FATAL
    assert classify_error(type('WhoKnowsError', (Exception,), {})()) == RETRY


# --------------------------------------------------------------------------- 解析失败要重试


def test_parse_error_is_retried_in_place():
    """第一次解析失败、第二次成功 —— 调用方应该拿到对象，而不是一个错误字符串。"""
    runner, chain = _runner([BAD, OK])
    obj, err = asyncio.run(runner.structured(Answer, 'sys', 'human'))

    assert (obj.value, err) == ('好了', '')
    assert chain.calls == 2


def test_parse_error_gives_up_after_the_retry_budget():
    """一直解析不出来就老实报错，不能无限刷。"""
    runner, chain = _runner([BAD], max_retries=2, max_rounds=1)
    obj, err = asyncio.run(runner.structured(Answer, 'sys', 'human'))

    assert obj is None
    assert 'Invalid json output' in err
    assert chain.calls == 2          # max_retries 次，池里只有一个模型、只轮一轮


# --------------------------------------------------------------------------- 重试要带上纠错信息


class Raw:
    """假的 AIMessage。"""

    def __init__(self, content: str = '', tokens: tuple[int, int] = (0, 0)):
        self.content = content
        self.usage_metadata = {'input_tokens': tokens[0], 'output_tokens': tokens[1]}


def test_retry_feeds_the_error_back_to_the_model():
    """重试不是原样重发 —— 必须把上次输出和报错摆给模型看。

    抽取与判定都跑在 temperature=0 上，原样再问一遍多半原样再错一遍。
    """
    bad = {**BAD, 'raw': Raw('{"value": "写到一半就断了')}
    runner, chain = _runner([bad, OK])
    asyncio.run(runner.structured(Answer, 'sys', '原始任务'))

    assert chain.calls == 2
    first, second = chain.seen
    assert len(first) == 2                       # 第一次就是 system + human，不带纠错
    assert len(second) == 3                      # 第二次多一条纠错消息
    repair = second[-1][1]
    assert 'Invalid json output' in repair       # 解析器的报错
    assert '写到一半就断了' in repair              # 上次的原始输出
    assert '截断' in repair and 'JSON' in repair  # 截断时该怎么办
    assert second[1] == first[1]                 # 原始任务原封不动地留着


def test_repair_message_keeps_head_and_tail_of_a_long_output():
    """截断类错误的线索在末尾（JSON 断在哪儿），只留开头会把线索丢掉。"""
    text = 'AAA' + 'x' * 5000 + 'ZZZ'
    msg = repair_message(text, 'Invalid json output')
    assert 'AAA' in msg and 'ZZZ' in msg
    assert '中间省略' in msg
    assert len(msg) < len(text)


def test_no_repair_block_on_the_first_attempt():
    runner, chain = _runner([OK])
    asyncio.run(runner.structured(Answer, 'sys', '原始任务'))
    assert len(chain.seen[0]) == 2


def test_tokens_are_counted_even_when_parsing_fails():
    """解析失败那一次的 token 照样是花掉了的，不记账会让用量统计偏低。"""
    runner, _ = _runner([
        {**BAD, 'raw': Raw('坏输出', (100, 20))},
        {**OK, 'raw': Raw('好输出', (100, 20))},
    ])
    asyncio.run(runner.structured(Answer, 'sys', 'human'))

    assert (runner.token_in, runner.token_out) == (200, 40)   # 失败那次 + 成功那次


# --------------------------------------------------------------------------- 结构化输出方式


class Unsupported(Exception):
    """厂商回的「这种结构化输出方式我不支持」（实测是 400，会被归成 FATAL）。"""

    status_code = 400

    def __str__(self) -> str:
        return "response_format.type: json_schema is not supported by this model"


def test_configured_method_is_used_without_probing():
    """库里指定了方式就直接用它 —— 这一列存在的意义就是不必再撞一次墙。"""
    runner, chain = _runner([OK], cfg=ModelConfig(model='fake', structured_method='function_calling'))
    obj, err = asyncio.run(runner.structured(Answer, 'sys', 'human'))

    assert (obj.value, err) == ('好了', '')
    assert chain.model.methods == ['function_calling']   # 没先试 json_schema
    assert runner.resolved_methods() == {}               # 没探测出新结论，不必回写


def test_unsupported_method_falls_back_one_step_at_a_time():
    """json_schema 被拒 → 降到 function_calling 就该成功，不该一路掉到 text。"""
    runner, chain = _runner([Unsupported(), OK])
    obj, err = asyncio.run(runner.structured(Answer, 'sys', 'human'))

    assert (obj.value, err) == ('好了', '')
    assert chain.model.methods == ['json_schema', 'function_calling']
    # 探测结论要能交给 worker 回写 ai_models，否则下个任务还得再撞一次
    assert runner.resolved_methods() == {'OpenAI:fake': 'function_calling'}


def test_method_is_remembered_within_the_run():
    """降级结果粘在模型上：第二次调用直接用对的方式。"""
    runner, chain = _runner([Unsupported(), OK])
    asyncio.run(runner.structured(Answer, 'sys', 'human'))
    asyncio.run(runner.structured(Answer, 'sys', '第二次'))

    assert chain.model.methods == ['json_schema', 'function_calling', 'function_calling']


def test_method_is_per_model_not_per_runner():
    """池子里混着不同厂商时，A 撞出来的结论不能套到 B 上。"""
    a = ModelConfig(model='a', ref='ai_models:1')
    b = ModelConfig(model='b', ref='ai_models:2')
    runner, _ = _runner([OK])

    assert runner._method_for(a) == 'json_schema'
    runner._demote_method(a, 'json_schema', 'nope')
    assert runner._method_for(a) == 'function_calling'
    assert runner._method_for(b) == 'json_schema'      # B 不受牵连


def test_text_method_parses_json_out_of_a_fenced_reply():
    """最后一档：厂商什么都不保证，自己从围栏里把 JSON 抠出来。"""
    runner, chain = _runner(
        [Raw('```json\n{"value": "抠出来了"}\n```')],
        cfg=ModelConfig(model='fake', structured_method='text'),
    )
    obj, err = asyncio.run(runner.structured(Answer, 'sys', 'human'))

    assert (obj.value, err) == ('抠出来了', '')
    # Schema 必须摆进提示词：这一档没人替你保证字段名
    assert 'JSON Schema' in chain.seen[0][-1][1]


def test_text_method_retries_with_the_parse_error():
    """text 模式解析失败也要走纠错重试，不能一次不成就判死。"""
    runner, chain = _runner(
        [Raw('这不是 JSON'), Raw('{"value": "第二次好了"}')],
        cfg=ModelConfig(model='fake', structured_method='text'),
    )
    obj, err = asyncio.run(runner.structured(Answer, 'sys', 'human'))

    assert (obj.value, err) == ('第二次好了', '')
    assert chain.calls == 2
    assert '这不是 JSON' in chain.seen[1][-2][1]      # 上次的原始输出被摆回去了
