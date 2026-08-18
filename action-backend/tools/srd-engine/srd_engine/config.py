"""引擎配置与版本号.

版本号三件套写进每次评估结果，保证「同输入 + 同版本 → 同结论」可追溯：
- ENGINE_VERSION   代码逻辑（聚合算法、投票阶梯）
- PROMPT_VERSION   提示词
- CRITERIA_VERSION 判定口径 YAML
任何一项改动都必须手动升版本，否则历史结果无法解释。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace

# 0.7.0：条目判定由 dup/diff 二选一改为 0–3 四档评分（新版 Excel 表 1 的「评分」列），
#        领域与整体百分比改由分数算；条目编号 9 随 Excel 改为 9a。
# 0.7.1：整体判定理由改成只讲查表这一步，不再逐领域复述得分与百分比（那些同一份报告里
#        本来就逐个列着）。判定逻辑一字未动 —— 升版本只是为了让「同版本 → 同措辞」成立，
#        代价是抽取缓存全失效（缓存键含 ENGINE_VERSION），下一次评估要重抽一遍。
# 0.8.0：**评分方向翻转**（甲方定稿）。0.7.x 沿用 Excel 表 1 表头的「完全相同 0 分 …
#        完全不同 3 分」，现改为「分数即相似度」：3 分完全相同、0 分完全不同，分越高越重复。
#        重复百分比随之由 `(满分−得分)/满分` 改为 `得分/满分`。
#        **这两处一起改的净效果是 pct / level / overall_level 数值一格不动** ——
#        翻转只重新标注了分数这一层。历史数据靠 `schemas.flip_rating` 迁移。
ENGINE_VERSION = 'srd-engine/0.8.0'
PROMPT_VERSION = 'prompt/2026-08-18'
CRITERIA_VERSION = 'criteria/2026-08-18'


@dataclass(frozen=True)
class ModelConfig:
    """单个模型的连接配置.

    后端接入时直接从 ai_models 表构造这个对象（api_key 解密后传入），
    引擎不关心密钥从哪来，也不负责持久化。
    """

    provider: str = 'OpenAI'
    model: str = 'gpt-4o-mini'
    api_key: str = ''
    base_url: str | None = None
    temperature: float = 0.0
    max_tokens: int | None = None
    timeout: float = 180.0
    extra: dict = field(default_factory=dict)
    #: 模型池内的唯一标识（通常是 `ai_models` 主键）。
    #: 同一个 provider/model 可能对应多个账号 —— 每个账号有各自的并发与余额，
    #: 冻结、限流统计必须按账号分开算，所以不能拿 provider/model 当键。不填时退化成 provider:model。
    ref: str = ''
    #: 结构化输出方式：json_schema / function_calling / json_mode / text。
    #: 空串 = 交给运行时探测（从 json_schema 起，撞到「不支持」逐级降级）。
    #: 后端从 `ai_models.structured_method` 填进来 —— 支持情况是**按模型**不同的
    #: （同一个 deepseek 在官方端点与火山方舟上就不一样），所以它属于模型配置而不是引擎配置。
    structured_method: str = ''

    @property
    def identity(self) -> str:
        """模型池内的键：冻结标记、用量统计都按它归集。"""
        return self.ref or f'{self.provider}:{self.model}'

    @property
    def label(self) -> str:
        """给人看的短名，写日志用。"""
        return f'{self.provider}/{self.model}' + (f'#{self.ref}' if self.ref else '')

    def with_temperature(self, temperature: float) -> ModelConfig:
        """派生一个只改温度的副本（判定投票需要不同温度）。

        用 `replace` 而非手工重建 —— 手抄字段是「加了字段忘记抄 → 静默重置成默认值」
        的经典地雷，本仓库已经踩过一次。但 `replace` 不拷贝任何字段，`extra` 是可变
        dict，必须显式拷一份，否则各温度副本共享同一个 dict，frozen 的不可变承诺失效。
        """
        return replace(self, temperature=temperature, extra=dict(self.extra))


@dataclass(frozen=True)
class FailoverConfig:
    """模型池的故障切换参数.

    语义是「粘性 + 出错切换」：一直用当前模型，直到它报错（限流 / 欠费 / 鉴权 / 服务端故障），
    才把它冻结一段时间并切到下一个；冻结到期后它自动重新进入候选。
    """

    #: 出错模型的冻结时长（秒）。到期后自动解冻重新参与轮换。
    freeze_seconds: float = 300.0
    #: 池内模型全被冻结时，最多等多久解冻。超时则本次评估判失败。
    #: 只对「会自愈」的错误（限流 / 5xx / 超时）等待；鉴权、欠费这类等 5 分钟也没用，直接失败。
    all_frozen_wait: float = 600.0
    #: 单次调用最多把整个池子轮几遍。轮完仍失败就把这一次调用判错（引擎会降级成 unclear）。
    max_rounds: int = 2
    #: 同一个模型上的原地重试次数（只对网络抖动这类瞬时错误生效）。
    max_retries: int = 3


@dataclass(frozen=True)
class EngineConfig:
    """一次评估的运行参数."""

    # 抽取时喂给模型的正文范围：
    #   full     —— 整篇（默认）。章节切分只用于导航与页码，不再决定模型能看到什么。
    #   sections —— 按批次的章节关键词挑正文（0.1.0 的老行为，留作对照与超长文献兜底）。
    # 改成 full 的原因见 DESIGN.md：sections 模式下「部分命中」会静默丢掉关键段落，
    # 而回退全文只在「一个章节都没命中」时触发，最该兜底的情况反而兜不住。
    extract_scope: str = 'full'
    # 判定粒度：all（默认，34 条一次调用）/ per_group（12 次）/ per_item（34 次）
    # 默认改为 all 的实测依据见 judge.py 模块 docstring：per_item 的 76 次调用
    # 并未换来更稳的输出，两种模式的自一致率都是 95%。
    judge_granularity: str = 'all'
    # 并发上限（LangChain abatch 的 max_concurrency）
    max_concurrency: int = 8
    # 领域可评估条目占比低于该值 → 标「证据不足」
    evidence_sufficient_ratio: float = 0.5


def model_config_from_env(prefix: str = 'SRD') -> ModelConfig:
    """从环境变量读模型配置，供 CLI / 离线评测使用。

    SRD_PROVIDER / SRD_MODEL / SRD_API_KEY / SRD_BASE_URL / SRD_MAX_TOKENS
    """

    def _env(name: str, default: str = '') -> str:
        return os.environ.get(f'{prefix}_{name}', default).strip()

    max_tokens = _env('MAX_TOKENS')
    return ModelConfig(
        provider=_env('PROVIDER', 'OpenAI'),
        model=_env('MODEL', 'gpt-4o-mini'),
        api_key=_env('API_KEY') or os.environ.get('OPENAI_API_KEY', ''),
        base_url=_env('BASE_URL') or None,
        max_tokens=int(max_tokens) if max_tokens.isdigit() else None,
    )
