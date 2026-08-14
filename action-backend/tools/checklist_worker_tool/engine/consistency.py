"""针灸逻辑一致性与术语标准化校验的纯算法（报告助手第三步的第二类判定）。

和 `audit.py` 的分工：

- `audit` 回答「**这一条**报告了没有、报在第几行」—— 证据是局部的，所以可以切窗并发。
- 本模块回答「**全稿各处对不对得上**」—— 干预与对照有没有写混、针刺频次与随访时点前后
  矛不矛盾、样本量依据和实际例数配不配、穴位名称用没用标准写法。

**这类检查天然是跨段落的，所以刻意不切窗**：方法写在前、结果写在后，把稿件切成两半再
分别找矛盾，等于让模型只看半篇就下结论 —— 既漏又误报。稿件超出 `max_chars` 时按整行截断
并标 `truncated`，让用户知道后半段没被看过，绝不静默。

不认识 Redis / HTTP / 队列，只依赖一个能发结构化请求的 runner（协议见 `audit.Runner`）。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field
from tools.checklist_worker_tool.engine.audit import Runner, number_lines

#: 单条检查的状态。
#: - ok        跑过了，没发现问题
#: - warn      有疑点，需人工确认（只定位到一处证据，或本身就要人来判）
#: - issue     明确不一致（相互矛盾的两处都能定位）
#: - na        本检查不适用于这份稿件的研究类型（如系统综述没有自设对照组）
#: - unchecked 没跑成（模型出错）—— **绝不能显示成「没问题」**
OK = 'ok'
WARN = 'warn'
ISSUE = 'issue'
NA = 'na'
UNCHECKED = 'unchecked'

#: 单条发现的严重度，只有两档；规则状态取其中最重的一档
SEVERITY_RANK = {WARN: 1, ISSUE: 2}


@dataclass(frozen=True)
class CheckRule:
    """一条全稿校验规则。

    `key` 是前台文案的锚点（`assistant.ckRule.<key>`），加规则时要同步加 i18n 词条，
    否则前台只会显示出键名本身。
    """

    key: str
    #: 'logic' 逻辑一致性 / 'term' 术语标准化 —— 前台分两组显示
    kind: str
    #: 喂给模型的检查要求（中文；模型读得懂中文指令，输出语言另行指定）
    instruction: str


#: 四条规则，与《智能报告辅助工具》里「针灸逻辑一致性校验」「术语标准化校验」两节一一对应。
RULES: tuple[CheckRule, ...] = (
    CheckRule(
        key='arm',
        kind='logic',
        instruction=(
            '检查「干预措施」与「对照组 / 对照措施」的描述有没有混淆或互相矛盾。典型问题：\n'
            '  · 把对照组的操作写进了试验组（或反过来）；\n'
            '  · 同一组在方法与结果（或摘要与正文）里被描述成了不同的干预；\n'
            '  · 假针 / 安慰针的选穴、深度、是否通电，与试验组的描述前后打架；\n'
            '  · 只写了一组的干预细节，另一组的对照措施交代不清到无法分辨两组差异。'
        ),
    ),
    CheckRule(
        key='schedule',
        kind='logic',
        instruction=(
            '检查「针刺频次 / 疗程」与「随访时间点」在稿件各处是否前后一致。典型问题：\n'
            '  · 方法称每周 3 次，结果或图表按每周 2 次计；\n'
            '  · 疗程 4 周，随访表却列到第 6 周且没有说明；\n'
            '  · 摘要与正文的治疗次数、总针刺次数对不上；\n'
            '  · 结局指标的测量时点与方法里预设的随访时点不一致。'
        ),
    ),
    CheckRule(
        key='sample',
        kind='logic',
        instruction=(
            '检查「样本量计算依据」与最终纳入 / 分析的例数是否逻辑匹配。典型问题：\n'
            '  · 计算需要 120 例，实际纳入 96 例，却未说明脱落、失访或方案调整；\n'
            '  · 报告了把握度或效应量，却没给出样本量计算的参数来源；\n'
            '  · 流程图 / 结果里的各组例数相加与总例数对不上；\n'
            '  · 意向性分析与符合方案分析的例数关系交代不清。'
        ),
    ),
    CheckRule(
        key='acupoint',
        kind='term',
        instruction=(
            '检查穴位名称是否使用标准写法：标准穴名 + 国际标准代码，如「足三里（ST36）」'
            '／「Zusanli (ST36)」。典型问题：\n'
            '  · 冗余后缀，如「足三里穴」；\n'
            '  · 异体字、俗称或古称，未同时给出通用标准穴名；\n'
            '  · 只有穴名没有国际标准代码，或代码写错（如把 ST36 写成 S36、ST-36）；\n'
            '  · 拼音不规范（大小写、分词、声调标注混乱）。\n'
            '每个不规范的穴名单独作为一条发现，suggestion 给出规范写法。'
        ),
    ),
)


@dataclass(frozen=True)
class ConsistencyConfig:
    """算法参数。"""

    #: 全稿检查的字符预算。**不切窗**，超出按整行截断并标 truncated。
    #: 6 万字符约等于一篇 2 万字的中文论文，绝大多数稿件都放得下。
    max_chars: int = 60000
    #: 并发的规则请求数（runner 自己还有一层全局闸）
    max_concurrency: int = 2
    #: 单条规则最多保留几条发现；超出时标 capped，由前台如实说明「只列出前 N 条」
    max_findings: int = 20


@dataclass
class Finding:
    """一条发现。"""

    severity: str = WARN
    lines: list[int] = field(default_factory=list)
    evidence: str = ''
    detail: str = ''
    suggestion: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'severity': self.severity,
            'lines': self.lines,
            'evidence': self.evidence,
            'detail': self.detail,
            'suggestion': self.suggestion,
        }


@dataclass
class CheckResult:
    """一条规则的检查结果。"""

    key: str
    kind: str
    status: str = UNCHECKED
    findings: list[Finding] = field(default_factory=list)
    capped: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            'key': self.key,
            'kind': self.kind,
            'status': self.status,
            'findings': [f.to_dict() for f in self.findings],
            'capped': self.capped,
        }


class _Finding(BaseModel):
    """单条发现（模型结构化输出用）。"""

    severity: str = Field(
        default=WARN,
        description="severity: 'issue' 明确不一致（相互矛盾的两处都能定位）| 'warn' 疑似，需人工确认",
    )
    lines: list[int] = Field(default_factory=list, description='相关行号，取自稿件行号标记；矛盾的两处都要给')
    evidence: str = Field(default='', description='稿件原文片段，不超过 80 字')
    detail: str = Field(default='', description='问题说明：哪两处对不上、差在哪')
    suggestion: str = Field(default='', description='建议怎么改；术语类给出规范写法')


class _RuleReport(BaseModel):
    """一条规则的检查报告。"""

    applicable: bool = Field(default=True, description='本检查是否适用于这份稿件的研究类型')
    findings: list[_Finding] = Field(default_factory=list, description='发现的问题；没发现就留空')


SYSTEM_PROMPT = (
    '你是针刺临床研究报告规范的审稿助手。给你一份稿件（每行已编号）和一项全稿校验要求，'
    '请通读全文后找出违反该要求的地方。\n'
    '硬性要求：\n'
    '  1. 只依据给定稿件判断，不得脑补、不得假设「通常都会这样写」。\n'
    '  2. 每条发现都必须给出稿件中真实存在的行号；不确定就把 severity 降为 warn，不要编造行号。\n'
    '  3. 相互矛盾的两处都能定位时才用 issue；只定位到一处、或需要人工确认的，用 warn。\n'
    '  4. 没有发现问题就让 findings 为空数组 —— 不要为了凑数把没问题的地方写成问题。\n'
    '  5. 稿件的研究类型使该检查根本不适用时（例如系统综述没有自设对照组、'
    '病例报告没有样本量计算），把 applicable 置为 false 并让 findings 为空。\n'
    '  6. detail 与 suggestion 用{lang}书写。'
)


def _fit(numbered: str, budget: int) -> tuple[str, bool]:
    """按整行截断到字符预算内，返回 (文本, 是否截断)。

    按行截而不是按字符截：行号是定位证据的唯一锚点，把一行劈成两半会让末行的行号
    对不上原文。
    """
    if len(numbered) <= budget:
        return numbered, False

    kept: list[str] = []
    size = 0
    for line in numbered.split('\n'):
        if size + len(line) + 1 > budget:
            break
        kept.append(line)
        size += len(line) + 1

    return '\n'.join(kept), True


def _normalize(report: _RuleReport, rule: CheckRule, line_count: int, cfg: ConsistencyConfig) -> CheckResult:
    """把模型的原始报告收敛成可展示的结果。

    三条保守规则，都指向同一件事 —— **说不清位置的问题不许摆出 issue 的架势**：
    - 行号超出稿件行数的丢掉（编造的行号比没有行号更有害，与 audit 同）；
    - 丢完一个行号都不剩的发现降级为 warn（issue 的定义就是「两处都能定位」）；
    - severity 不在枚举内的按 warn。
    """
    findings: list[Finding] = []
    for raw in report.findings:
        lines = [n for n in raw.lines if 1 <= n <= line_count]
        severity = raw.severity if raw.severity in SEVERITY_RANK else WARN
        if not lines:
            severity = WARN
        detail = raw.detail.strip()[:400]
        suggestion = raw.suggestion.strip()[:300]
        evidence = raw.evidence.strip()[:200]
        # 三样全空的「发现」没有任何可核之处，等同于没发现
        if not (detail or suggestion or evidence):
            continue
        findings.append(
            Finding(severity=severity, lines=lines, evidence=evidence, detail=detail, suggestion=suggestion)
        )

    capped = len(findings) > cfg.max_findings
    findings = findings[: cfg.max_findings]

    if not report.applicable and not findings:
        status = NA
    elif not findings:
        status = OK
    else:
        status = ISSUE if any(f.severity == ISSUE for f in findings) else WARN

    return CheckResult(key=rule.key, kind=rule.kind, status=status, findings=findings, capped=capped)


def summarize(checks: list[CheckResult]) -> dict[str, Any]:
    """聚合各档位条数。`unchecked` 单独计数 —— 它不是「没问题」。"""
    counts = {OK: 0, WARN: 0, ISSUE: 0, NA: 0, UNCHECKED: 0}
    for c in checks:
        counts[c.status] = counts.get(c.status, 0) + 1

    return {
        'total': len(checks),
        'ok': counts[OK],
        'warn': counts[WARN],
        'issue': counts[ISSUE],
        'na': counts[NA],
        'unchecked': counts[UNCHECKED],
        'findings': sum(len(c.findings) for c in checks),
    }


async def check_consistency(
    runner: Runner,
    manuscript: str,
    cfg: ConsistencyConfig | None = None,
    locale: str = 'zh',
    rules: tuple[CheckRule, ...] = RULES,
    on_progress: Any = None,
) -> dict[str, Any]:
    """全稿跑一遍逻辑一致性与术语标准化校验。

    :param runner: 能发结构化请求的调用器
    :param manuscript: 稿件全文
    :param cfg: 算法参数
    :param locale: 结论书写语言（'zh' / 'en'）
    :param rules: 要跑的规则，默认全部
    :param on_progress: 可选回调 `(done, total, message)`
    :return: {'summary': {...}, 'checks': [...], 'truncated': bool, 'errors': [...]}
    """
    cfg = cfg or ConsistencyConfig()
    text = manuscript or ''
    numbered, line_count = number_lines(text)
    if not line_count:
        raise ValueError('稿件为空')
    numbered, truncated = _fit(numbered, cfg.max_chars)
    lang = '英文' if str(locale).lower().startswith('en') else '中文'
    system = SYSTEM_PROMPT.format(lang=lang)

    # 兜底：跑不成的规则停在 unchecked，绝不因为一次网络抖动就显示成「未发现问题」
    results: dict[str, CheckResult] = {r.key: CheckResult(key=r.key, kind=r.kind) for r in rules}
    errors: list[str] = []
    done = 0
    lock = asyncio.Lock()
    sem = asyncio.Semaphore(max(1, cfg.max_concurrency))

    async def run_one(rule: CheckRule) -> None:
        nonlocal done
        human = (
            f'稿件（共 {line_count} 行{"，因超长只给出前一部分" if truncated else ""}）：\n'
            f'-----\n{numbered}\n-----\n\n'
            f'本次校验要求（{rule.key}）：\n{rule.instruction}'
        )
        async with sem:
            parsed, err = await runner.structured(_RuleReport, system, human)
        async with lock:
            done += 1
            if err:
                errors.append(f'{rule.key}: {err}')
            elif parsed is not None:
                results[rule.key] = _normalize(parsed, rule, line_count, cfg)
            if on_progress:
                on_progress(done, len(rules), f'全稿校验 {done}/{len(rules)} 项')

    await asyncio.gather(*(run_one(r) for r in rules))

    checks = [results[r.key] for r in rules]

    return {
        'summary': summarize(checks),
        'checks': [c.to_dict() for c in checks],
        'truncated': truncated,
        'errors': errors[:5],
    }
