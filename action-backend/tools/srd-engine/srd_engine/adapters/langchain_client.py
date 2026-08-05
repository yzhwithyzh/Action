"""LangChain 适配层 —— 引擎里唯一 import LangChain 的地方.

对外只暴露 LlmRunner：

    runner = LlmRunner(model_cfg, max_concurrency=8)                    # 单模型
    runner = LlmRunner([cfg_a, cfg_b, cfg_c], health=..., on_event=...) # 模型池 + 故障切换
    obj, err = await runner.structured(ItemVerdict, system, human, temperature=0.3)
    text, err = await runner.text(system, human)

换栈（比如换回 agno、或直接用 HTTP）只需重写本文件，其余模块零改动。

关于并发：这里用 asyncio.Semaphore 统一限流，而不是 Runnable.abatch(max_concurrency)。
原因是本引擎各阶段的 schema 与调用形态不一致（抽取 4 种 schema、判定 1 种、辩护是纯文本），
abatch 只能约束「同一条链的一批同构输入」，跨阶段的总并发仍需自己兜。
用一个信号量把全局并发管住，行为更可预期，也更好排障。

关于模型池（0.6.1 新增）：单个厂商都有并发/RPM 上限，一次评估几十次调用很容易撞上，
所以 LlmRunner 接受**一组**模型并做「粘性 + 出错切换」：

    正常时一直用当前模型（同一次评估尽量由同一个模型判定，结论才好解释）
    ↓ 撞到限流 / 欠费 / 鉴权 / 服务端 5xx
    冻结该模型 freeze_seconds（默认 5 分钟）→ 切下一个 → 到期自动回到候选队列

冻结状态存在哪由调用方决定：传 `health` 就用共享存储（worker 传的是 Redis 实现，
多进程共享同一份健康状态），不传就退化成进程内存（CLI / 单测够用）。
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, TypeVar

from pydantic import BaseModel

from srd_engine.config import FailoverConfig, ModelConfig

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterable, Sequence

    from langchain_core.language_models import BaseChatModel

T = TypeVar('T', bound=BaseModel)

logger = logging.getLogger(__name__)

# provider -> 构造函数。绝大多数国产厂商是 OpenAI 兼容端点，统一走 ChatOpenAI + base_url。
_OPENAI_COMPATIBLE_DEFAULT_BASE = {
    'DeepSeek': 'https://api.deepseek.com/v1',
    'DashScope': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    'Moonshot': 'https://api.moonshot.cn/v1',
    'SiliconFlow': 'https://api.siliconflow.cn/v1',
    'ZhipuAI': 'https://open.bigmodel.cn/api/paas/v4',
    'OpenRouter': 'https://openrouter.ai/api/v1',
}

# 一次调用的处置方式
RETRY = 'retry'  # 瞬时抖动：原地重试，重试用尽再当 SWITCH 处理
SWITCH = 'switch'  # 该模型暂时不可用（限流 / 5xx）：冻结 + 换下一个，值得等它解冻
DISABLE = 'disable'  # 该模型短期内治不好（鉴权 / 欠费 / 模型不存在）：冻结 + 换下一个，但不值得等
FATAL = 'fatal'  # 请求本身有问题（参数非法 / 内容审核）：换谁都一样，直接把这次调用判错

# 全池冻结时的轮询间隔
_FROZEN_POLL_INTERVAL = 5.0
# 「这个模型是好的」这一判断的本地缓存时长，避免每次调用都去问一遍共享健康表
_HEALTH_CACHE_SECONDS = 5.0

_DISABLE_STATUS = {401, 402, 403, 404}
_SWITCH_STATUS = {408, 409, 429, 500, 502, 503, 504, 529}
_FATAL_STATUS = {400, 413, 422}
# 5xx 一律当服务端故障（换个厂商多半就好了）
_SERVER_ERROR_STATUS = 500
# 全池冻结时最多每隔这么久重拉一次模型清单
_RELOAD_MIN_INTERVAL = 60.0

# 有些厂商（尤其是国产 OpenAI 兼容端点）不走标准状态码，只能扫消息文本
_DISABLE_KEYWORDS = (
    'insufficient', 'balance', 'quota', 'billing', 'payment', 'arrears', 'expired',
    'unauthorized', 'invalid api key', 'invalid_api_key', 'api key', 'permission',
    '欠费', '余额', '额度', '未授权', '无权限', '密钥', '已过期',
)
_SWITCH_KEYWORDS = (
    'rate limit', 'rate_limit', 'too many requests', 'overloaded', 'server error',
    'service unavailable', 'temporarily', 'timeout', 'timed out',
    '限流', '请求过于频繁', '繁忙', '服务不可用', '超时',
)
_FATAL_KEYWORDS = (
    'content filter', 'content_filter', 'data_inspection_failed', 'risk control',
    '内容审核', '违规', '敏感',
)

# 「这个厂商不认这种结构化输出方式」的错误特征。命中就换一种方式重试，而不是把调用判死 ——
# 实测火山方舟上的 deepseek 会回 `response_format.type: json_schema is not supported by this model`，
# 它是 400，会被 classify_error 归成 FATAL，换模型没用、重试也没用，只能换方式。
_UNSUPPORTED_METHOD_KEYWORDS = (
    'response_format', 'json_schema', 'json schema', 'tool_choice', 'function calling', 'function_call',
)
_UNSUPPORTED_HINTS = ('not supported', 'not valid', 'unsupported', 'invalid', '不支持')


def is_unsupported_structured_method(err: str) -> bool:
    """错误信息是否在说「这种结构化输出方式我不支持」。"""
    text = err.lower()
    return any(k in text for k in _UNSUPPORTED_METHOD_KEYWORDS) and any(
        h in text for h in _UNSUPPORTED_HINTS
    )


class AllModelsFrozenError(RuntimeError):
    """池内所有模型都不可用（且不值得再等）。"""


class ModelHealth(Protocol):
    """模型健康状态的共享存储接口。

    worker 侧用 Redis 实现，多个 worker 进程共享同一份冻结记录：
    A 进程撞到限流把模型冻上，B 进程就不会再去撞一次。
    """

    async def frozen_seconds(self, key: str) -> float:
        """返回该模型还剩多少秒解冻；0 表示可用。"""
        ...

    async def freeze(self, key: str, seconds: float, reason: str) -> None:
        """把该模型冻结指定时长。"""
        ...


class InMemoryModelHealth:
    """进程内实现（CLI / 单测 / 没配 Redis 时的兜底）。"""

    def __init__(self) -> None:
        self._until: dict[str, float] = {}

    async def frozen_seconds(self, key: str) -> float:
        return max(0.0, self._until.get(key, 0.0) - time.monotonic())

    async def freeze(self, key: str, seconds: float, reason: str) -> None:
        self._until[key] = time.monotonic() + seconds


@dataclass
class ModelUsage:
    """单个模型在本次运行中的用量与故障计数（写进任务摘要，方便运维看谁在扛活）。"""

    label: str
    calls: int = 0
    errors: int = 0
    token_in: int = 0
    token_out: int = 0
    freezes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'label': self.label,
            'calls': self.calls,
            'errors': self.errors,
            'token_in': self.token_in,
            'token_out': self.token_out,
            'freezes': self.freezes[:5],
        }


def make_chat_model(cfg: ModelConfig, temperature: float | None = None) -> BaseChatModel:
    """按 ModelConfig 造一个 LangChain BaseChatModel。"""
    temp = cfg.temperature if temperature is None else temperature
    provider = cfg.provider or 'OpenAI'

    if provider == 'Anthropic':
        from langchain_anthropic import ChatAnthropic  # noqa: PLC0415

        return ChatAnthropic(
            model=cfg.model,
            api_key=cfg.api_key or None,
            base_url=cfg.base_url or None,
            temperature=temp,
            max_tokens=cfg.max_tokens or 4096,
            timeout=cfg.timeout,
            **cfg.extra,
        )

    if provider == 'Google':
        from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: PLC0415

        return ChatGoogleGenerativeAI(
            model=cfg.model,
            google_api_key=cfg.api_key or None,
            temperature=temp,
            max_output_tokens=cfg.max_tokens,
            **cfg.extra,
        )

    from langchain_openai import ChatOpenAI  # noqa: PLC0415

    base_url = cfg.base_url or _OPENAI_COMPATIBLE_DEFAULT_BASE.get(provider)
    return ChatOpenAI(
        model=cfg.model,
        api_key=cfg.api_key or 'EMPTY',
        base_url=base_url,
        temperature=temp,
        max_tokens=cfg.max_tokens,
        timeout=cfg.timeout,
        **cfg.extra,
    )


def classify_error(exc: BaseException) -> str:
    """把一次调用失败归成四类之一，决定「重试 / 换模型 / 直接判错」。

    判断顺序刻意是「内容审核 → 状态码 → 关键词 → 异常类名」：
    状态码最可靠，但国产兼容端点经常把限流塞进 200/400 的消息体里，所以关键词兜一层；
    都认不出来的按可重试处理（重试用尽会自动升级成换模型），宁可多试一个模型，
    也不要让一次未知抖动把整篇评估判死。
    """
    text = f'{type(exc).__name__}: {exc}'.lower()
    if any(k in text for k in _FATAL_KEYWORDS):
        return FATAL

    status = getattr(exc, 'status_code', None) or getattr(getattr(exc, 'response', None), 'status_code', None)
    if isinstance(status, int):
        if status in _DISABLE_STATUS:
            return DISABLE
        if status in _SWITCH_STATUS or status >= _SERVER_ERROR_STATUS:
            return SWITCH
        if status in _FATAL_STATUS:
            # 400 里混着「余额不足」这类真该换模型的错，先按关键词捞一遍
            return DISABLE if any(k in text for k in _DISABLE_KEYWORDS) else FATAL

    if any(k in text for k in _DISABLE_KEYWORDS):
        return DISABLE
    if any(k in text for k in _SWITCH_KEYWORDS):
        return SWITCH
    name = type(exc).__name__
    if 'RateLimit' in name:
        return SWITCH
    if 'Authentication' in name or 'PermissionDenied' in name or 'NotFound' in name:
        return DISABLE
    if 'BadRequest' in name or 'Validation' in name:
        return FATAL
    return RETRY


class LlmRunner:
    """统一的调用入口：结构化输出 / 纯文本 + 全局并发控制 + 模型池故障切换 + token 计数。"""

    def __init__(
        self,
        cfg: ModelConfig | Sequence[ModelConfig],
        max_concurrency: int = 8,
        max_retries: int | None = None,
        structured_method: str = 'json_schema',
        *,
        failover: FailoverConfig | None = None,
        health: ModelHealth | None = None,
        on_event: Callable[[str, str], None] | None = None,
        reload_pool: Callable[[], Awaitable[Sequence[ModelConfig]]] | None = None,
    ) -> None:
        pool = [cfg] if isinstance(cfg, ModelConfig) else list(cfg)
        if not pool:
            raise ValueError('模型池不能为空')

        self.failover = failover or FailoverConfig()
        if max_retries is not None:  # 兼容旧签名：位置参数仍然是「同模型重试次数」
            self.failover = FailoverConfig(
                freeze_seconds=self.failover.freeze_seconds,
                all_frozen_wait=self.failover.all_frozen_wait,
                max_rounds=self.failover.max_rounds,
                max_retries=max_retries,
            )
        self.max_retries = self.failover.max_retries
        self.structured_method = structured_method
        self.health: ModelHealth = health or InMemoryModelHealth()
        self._on_event = on_event
        self._reload_pool = reload_pool

        self.pool: list[ModelConfig] = _dedupe(pool)
        self.usage: dict[str, ModelUsage] = {c.identity: ModelUsage(label=c.label) for c in self.pool}
        #: 发生过的模型切换，写进任务摘要做审计
        self.switches: list[dict[str, str]] = []

        self._index = 0
        self._sem = asyncio.Semaphore(max(1, max_concurrency))
        self._models: dict[tuple[str, float], Any] = {}
        # 本地视图：{identity: 解冻时刻}，避免每次调用都打一次共享健康表
        self._frozen_until: dict[str, float] = {}
        self._hard_frozen: set[str] = set()
        self._checked_at: dict[str, float] = {}
        self._all_frozen_deadline: float | None = None
        self._reloaded_at = 0.0

        self.token_in = 0
        self.token_out = 0
        self.calls = 0

    # ---------------------------------------------------------------- 只读视图

    @property
    def cfg(self) -> ModelConfig:
        """当前正在用的模型。历史调用点都读这个，签名保持不变。"""
        return self.pool[min(self._index, len(self.pool) - 1)]

    @property
    def models_used(self) -> list[str]:
        """本次运行里真正发起过调用的模型（按池内顺序）。"""
        return [u.label for u in self.usage.values() if u.calls]

    def usage_stats(self) -> list[dict[str, Any]]:
        return [u.to_dict() for u in self.usage.values() if u.calls or u.freezes]

    # ---------------------------------------------------------------- 内部

    def _emit(self, event: str, message: str) -> None:
        logger.info('[模型池] %s', message)
        if self._on_event is not None:
            try:
                self._on_event(event, message)
            except Exception:  # 通知失败不能影响主流程
                logger.debug('模型事件回调失败', exc_info=True)

    def _model(self, cfg: ModelConfig, temperature: float) -> BaseChatModel:
        key = (cfg.identity, temperature)
        if key not in self._models:
            self._models[key] = make_chat_model(cfg, temperature)
        return self._models[key]

    def _count(self, message: object, cfg: ModelConfig | None = None) -> None:
        usage = getattr(message, 'usage_metadata', None) or {}
        if usage:
            token_in = int(usage.get('input_tokens') or 0)
            token_out = int(usage.get('output_tokens') or 0)
        else:
            meta = (getattr(message, 'response_metadata', None) or {}).get('token_usage') or {}
            token_in = int(meta.get('prompt_tokens') or 0)
            token_out = int(meta.get('completion_tokens') or 0)
        self.token_in += token_in
        self.token_out += token_out
        record = self.usage.get((cfg or self.cfg).identity)
        if record is not None:
            record.token_in += token_in
            record.token_out += token_out

    @staticmethod
    def _messages(system: str, human: str) -> list[tuple[str, str]]:
        return [('system', system), ('human', human)]

    # ---------------------------------------------------------------- 模型池调度

    async def _is_frozen(self, cfg: ModelConfig) -> bool:
        """先看本地视图，本地认为健康时才按缓存周期去问一次共享健康表。"""
        now = time.monotonic()
        until = self._frozen_until.get(cfg.identity)
        if until is not None:
            if until > now:
                return True
            del self._frozen_until[cfg.identity]
            self._hard_frozen.discard(cfg.identity)

        if now - self._checked_at.get(cfg.identity, -_HEALTH_CACHE_SECONDS * 2) < _HEALTH_CACHE_SECONDS:
            return False
        self._checked_at[cfg.identity] = now
        try:
            remaining = await self.health.frozen_seconds(cfg.identity)
        except Exception as exc:  # 健康表抖动时按「可用」处理，别让它挡住正事
            logger.debug('查询模型冻结状态失败 [%s]: %s', cfg.identity, exc)
            return False
        if remaining > 0:
            self._frozen_until[cfg.identity] = now + remaining
            return True
        return False

    async def _pick(self) -> ModelConfig | None:
        """从当前指针开始找第一个没被冻结的模型（粘性：找到谁就把指针挪过去）。"""
        pool = self.pool
        for offset in range(len(pool)):
            index = (self._index + offset) % len(pool)
            cfg = pool[index]
            if not await self._is_frozen(cfg):
                self._index = index
                return cfg
        return None

    async def _acquire(self) -> ModelConfig:
        """取一个可用模型；全被冻结时按策略等待解冻。"""
        while True:
            cfg = await self._pick()
            if cfg is not None:
                if self._all_frozen_deadline is not None:
                    self._all_frozen_deadline = None
                    self._emit('recovered', f'模型恢复可用，继续跑：{cfg.label}')
                return cfg

            frozen = self._frozen_summary()
            # 鉴权 / 欠费这类错误等 5 分钟也不会自己好，没必要占着任务空转
            if all(c.identity in self._hard_frozen for c in self.pool):
                raise AllModelsFrozenError(f'模型池全部不可用（鉴权/欠费类错误，等待无意义）：{frozen}')

            now = time.monotonic()
            if self._all_frozen_deadline is None:
                self._all_frozen_deadline = now + self.failover.all_frozen_wait
                self._emit(
                    'waiting',
                    f'池内 {len(self.pool)} 个模型全部被冻结，最多等 {self.failover.all_frozen_wait:.0f}s：{frozen}',
                )
                await self._try_reload()
                continue
            if now >= self._all_frozen_deadline:
                raise AllModelsFrozenError(
                    f'模型池全部被冻结，已等待超过 {self.failover.all_frozen_wait:.0f}s：{frozen}'
                )
            nearest = min((t - now for t in self._frozen_until.values()), default=_FROZEN_POLL_INTERVAL)
            await asyncio.sleep(max(0.5, min(_FROZEN_POLL_INTERVAL, nearest, self._all_frozen_deadline - now)))

    def _frozen_summary(self) -> str:
        now = time.monotonic()
        parts = [
            f'{c.label} 剩 {max(0.0, self._frozen_until.get(c.identity, now) - now):.0f}s'
            for c in self.pool
        ]
        return '；'.join(parts)

    async def _try_reload(self) -> None:
        """全池冻结时重新拉一次模型清单 —— 运维新加/启用的模型能立刻救场。"""
        if self._reload_pool is None or time.monotonic() - self._reloaded_at < _RELOAD_MIN_INTERVAL:
            return
        self._reloaded_at = time.monotonic()
        try:
            fresh = _dedupe(list(await self._reload_pool()))
        except Exception as exc:  # 拉不到就用旧的接着等
            logger.warning('重新加载模型池失败: %s', exc)
            return
        added = [c for c in fresh if c.identity not in self.usage]
        if not added:
            return
        self.pool = [*self.pool, *added]
        for c in added:
            self.usage[c.identity] = ModelUsage(label=c.label)
        self._emit('reloaded', f'重新加载模型池，新增 {len(added)} 个候选：{"、".join(c.label for c in added)}')

    async def _penalize(self, cfg: ModelConfig, kind: str, reason: str) -> None:
        """冻结出错的模型并把指针挪到下一个。"""
        seconds = self.failover.freeze_seconds
        now = time.monotonic()
        self._frozen_until[cfg.identity] = now + seconds
        self._checked_at[cfg.identity] = now
        if kind == DISABLE:
            self._hard_frozen.add(cfg.identity)
        record = self.usage.get(cfg.identity)
        if record is not None:
            record.freezes.append(reason[:200])
        try:
            await self.health.freeze(cfg.identity, seconds, reason[:200])
        except Exception as exc:  # 共享健康表写不进去，至少本进程记住了
            logger.debug('写模型冻结标记失败 [%s]: %s', cfg.identity, exc)

        if self.pool[min(self._index, len(self.pool) - 1)].identity == cfg.identity:
            self._index = (self._index + 1) % len(self.pool)
        nxt = self.pool[self._index]
        self.switches.append({'from': cfg.label, 'to': nxt.label if nxt.identity != cfg.identity else '', 'reason': reason[:200]})
        target = f'切换到 {nxt.label}' if nxt.identity != cfg.identity else '池内无其他候选'
        self._emit('switch', f'{cfg.label} 已冻结 {seconds:.0f}s（{reason[:120]}）→ {target}')

    async def _attempt(
        self, cfg: ModelConfig, run: Callable[[BaseChatModel], Awaitable[Any]], temperature: float | None
    ) -> tuple[str, Any, str]:
        """在一个模型上跑一次（含瞬时错误的原地重试）。返回 (处置, 结果, 错误)。"""
        temp = cfg.temperature if temperature is None else temperature
        model = self._model(cfg, temp)
        kind, err = RETRY, '未知错误'
        for attempt in range(1, max(1, self.max_retries) + 1):
            async with self._sem:
                self.calls += 1
                record = self.usage.get(cfg.identity)
                if record is not None:
                    record.calls += 1
                try:
                    return 'ok', await run(model), ''
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # 异常分类交给 classify_error
                    kind = classify_error(exc)
                    err = f'{type(exc).__name__}: {exc}'
                    if record is not None:
                        record.errors += 1
            if kind == FATAL:
                return FATAL, None, err
            if kind != RETRY or attempt >= self.max_retries:
                break
            await asyncio.sleep(min(8.0, 0.5 * 2**attempt) * (0.5 + random.random()))  # 抖动，避免并发调用同时醒来
        return (SWITCH if kind == RETRY else kind), None, err

    async def _dispatch(
        self, run: Callable[[BaseChatModel], Awaitable[Any]], temperature: float | None
    ) -> tuple[Any, str, ModelConfig | None]:
        """一次逻辑调用：在模型池上轮换直到成功或轮够 max_rounds 遍。

        注意 `AllModelsFrozenError` 是**往外抛**的，不像单次调用失败那样降级成错误字符串：
        一个模型都用不了的时候，34 条判定会全变成 unclear，产出一份「什么都没判出来」的报告 ——
        那比直接失败更糟，用户会拿着这份报告当结论。抛出去让任务标 failed，
        断点与抽取缓存都还在，配好模型重新入队即可续跑。
        """
        limit = len(self.pool) * max(1, self.failover.max_rounds)
        tried, err = 0, '未发起调用'
        while tried < limit:
            try:
                cfg = await self._acquire()
            except AllModelsFrozenError as exc:
                # 已经试过几个模型才走到这里的话，把首个真实错误一并带出去，否则只剩「全冻结」这句空话
                raise AllModelsFrozenError(f'{err}；{exc}' if tried else str(exc)) from exc
            tried += 1
            outcome, value, attempt_err = await self._attempt(cfg, run, temperature)
            if outcome == 'ok':
                return value, '', cfg
            if outcome == FATAL:
                return None, attempt_err, cfg
            err = attempt_err
            await self._penalize(cfg, outcome, attempt_err)
        return None, f'模型池已轮换 {tried} 次仍失败：{err}', None

    # ---------------------------------------------------------------- 对外

    async def structured(
        self, schema: type[T], system: str, human: str, temperature: float | None = None
    ) -> tuple[T | None, str]:
        """结构化输出。返回 (对象, 错误信息)；失败时对象为 None。

        厂商不认 `json_schema` 时自动降级到 `function_calling` / `json_mode` 再试
        （顺序见 `structured_method_fallbacks`），成功的那种方式会**粘住**，
        后续调用直接用它，不再每次都先撞一次墙。
        """
        messages = self._messages(system, human)
        err = ''
        for method in [self.structured_method, *self.structured_method_fallbacks()]:

            async def run(model: BaseChatModel, _method: str = method) -> Any:
                chain = model.with_structured_output(schema, method=_method, include_raw=True)
                return await chain.ainvoke(messages)

            out, err, cfg = await self._dispatch(run, temperature)
            if err:
                if not is_unsupported_structured_method(err):
                    return None, err
                self._emit('fallback', f'结构化输出方式 {method} 不被支持（{err[:120]}），换下一种再试')
                continue

            if method != self.structured_method:
                self.structured_method = method     # 粘住，别每次都白撞一次
                self._emit('fallback', f'结构化输出方式已切换为 {method}')
            if isinstance(out, dict):
                if out.get('raw') is not None:
                    self._count(out['raw'], cfg)
                if out.get('parsing_error'):
                    return None, f'结构化输出解析失败: {out["parsing_error"]}'
                return out.get('parsed'), ''
            return out, ''
        return None, err or '所有结构化输出方式都不被支持'

    async def text(self, system: str, human: str, temperature: float | None = None) -> tuple[str, str]:
        """纯文本输出（辩护阶段用）。返回 (文本, 错误信息)。"""
        messages = self._messages(system, human)

        async def run(model: BaseChatModel) -> Any:
            return await model.ainvoke(messages)

        msg, err, cfg = await self._dispatch(run, temperature)
        if err:
            return '', err
        self._count(msg, cfg)
        content = getattr(msg, 'content', msg)
        if isinstance(content, list):  # 部分厂商返回分段内容
            content = ''.join(part.get('text', '') if isinstance(part, dict) else str(part) for part in content)
        return str(content), ''

    @staticmethod
    async def gather(tasks: Iterable[Awaitable]) -> list:
        """并发跑一组协程；并发上限由 runner 的信号量统一约束。"""
        return await asyncio.gather(*tasks)

    def structured_method_fallbacks(self) -> list[str]:
        """厂商不支持 json_schema 时的降级顺序。"""
        order = ['json_schema', 'function_calling', 'json_mode']
        return [m for m in order if m != self.structured_method]


def _dedupe(pool: Sequence[ModelConfig]) -> list[ModelConfig]:
    """同一个 identity 只留第一个 —— 重复配置会让冻结与统计对不上账。"""
    seen: set[str] = set()
    result: list[ModelConfig] = []
    for cfg in pool:
        if cfg.identity in seen:
            continue
        seen.add(cfg.identity)
        result.append(cfg)
    return result
