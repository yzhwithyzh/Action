"""针灸逻辑一致性与术语标准化校验的纯算法（报告助手第三步的第二类判定）。

和 `audit.py` 的分工：

- `audit` 回答「**这一条**报告了没有、证据是哪段原文」—— 证据是局部的，所以可以切窗并发。
- 本模块回答「**全稿各处对不对得上**」—— 干预与对照有没有写混、针刺频次与随访时点前后
  矛不矛盾、样本量依据和实际例数配不配、穴位名称用没用标准写法。

**这类检查天然是跨段落的，所以刻意不切窗**：方法写在前、结果写在后，把稿件切成两半再
分别找矛盾，等于让模型只看半篇就下结论 —— 既漏又误报。稿件超出 `max_chars` 时按整行截断
并标 `truncated`，让用户知道后半段没被看过，绝不静默。

流程::

    按字符预算截断（_fit）→ 每条规则一次请求（并发）→ _normalize 收敛 → summarize

    模型交的：  applicable（这项检查适不适用）+ findings[{quotes, detail, suggestion, violates}]
    代码定的：  丢掉 violates=false 的发现 → 每段引文回原文定位（grounding）
               → 按「定位到了几处不同位置」定级（_severity）→ 规则状态取全部发现里最重的一档

**定级不交给模型**，这是本模块和旧版最大的区别：旧版让模型自己填 severity，
不同模型的尺度差得离谱（qwen3.7-plus 16 项全判 issue，其中几条说明里写着「逻辑吻合」）。
**位置也不交给模型**：模型看到的稿件不带行号、只交逐字引文，「在哪」由代码查
（见 `grounding.py` 文件头）。代码能保证「摆不出两处原文的不许标红」；
分不清「真矛盾」和「挑刺」—— 那仍是模型的判断。

不认识 Redis / HTTP / 队列，只依赖一个能发结构化请求的 runner（协议见 `audit.Runner`）。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

from pydantic import BaseModel, Field
from tools.checklist_worker_tool.engine.audit import Runner, line_map
from tools.checklist_worker_tool.engine.grounding import LOCATED_NA, Grounder

#: 单条检查的状态。
#: - ok        跑过了，没发现问题
#: - warn      有疑点，需人工确认（逻辑类只定位到一处，或本身就要人来判）
#: - issue     明确不一致（逻辑类：两处不同位置都定位到了；术语类：定位到了）
#: - na        本检查不适用于这份稿件的研究类型（如系统综述没有自设对照组）
#: - unchecked 没跑成（模型出错）—— **绝不能显示成「没问题」**
OK = 'ok'
WARN = 'warn'
ISSUE = 'issue'
NA = 'na'
UNCHECKED = 'unchecked'
# 单条发现的严重度只有 WARN / ISSUE 两档，由 `_severity` 按结构算；规则状态取其中最重的一档


@dataclass(frozen=True)
class CheckRule:
    """一条全稿校验规则。

    `key` 是前台文案的锚点（`assistant.ckRule.<key>`），加规则时要同步加 i18n 词条，
    否则前台只会显示出键名本身。
    """

    key: str
    #: 'logic' 逻辑一致性 / 'term' 术语标准化 —— 前台分两组显示。
    #: 也决定 issue 的门槛：logic 要两处不同位置互相对照（矛盾天生是两处之间的事），
    #: term 一处即可（「足三里穴」写错了就是写错了，不需要第二处来对照）
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
    #: 所有引文在原文里的位置（代码查出的），前台「在原文中查看」按它高亮
    lines: list[int] = field(default_factory=list)
    evidence: str = ''
    detail: str = ''
    suggestion: str = ''
    #: 引文回原文定位的结论（同 `audit.ItemVerdict.located`），只作提示
    located: str = LOCATED_NA
    #: 逐段的「原文 + 代码查出的位置」。`evidence` 是这些原文拼起来给旧版面用的
    claims: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'severity': self.severity,
            'lines': self.lines,
            'evidence': self.evidence,
            'detail': self.detail,
            'suggestion': self.suggestion,
            'located': self.located,
            'claims': self.claims,
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
    """单条发现（模型结构化输出用）。

    **没有 severity 字段，也没有行号字段，这是刻意的。** 旧结构让模型第一个字段就填 severity，
    模型逐字生成，先写下「issue」再去写说明，于是出现「severity=issue，detail=『88-5=83，逻辑吻合』」。
    现在模型只交事实（几段逐字引文）与一个放在**最后**的 `violates`；定级与位置都由代码算。

    全部必填、不给默认值：走 function calling 的厂商会把可选字段整个省掉（见 audit._ItemJudgement）。
    """

    quotes: list[str] = Field(
        description='问题涉及的原文，逐字照抄、保持原语言，每段不超过 40 字：前后矛盾的两处各给一段；术语不规范给出现的那一处'
    )
    detail: str = Field(description='问题说明：哪几处对不上、差在哪')
    suggestion: str = Field(description='建议怎么改；术语类给出规范写法；没有就给空串')
    violates: bool = Field(
        description='写完上面几项之后再判断：这确实违反了本次校验要求吗？核对下来其实没有问题就填 false',
    )


class _RuleReport(BaseModel):
    """一条规则的检查报告。"""

    applicable: bool = Field(description='本检查是否适用于这份稿件的研究类型')
    findings: list[_Finding] = Field(description='发现的问题；没发现就给空数组')


SYSTEM_PROMPT = (
    '你是针刺临床研究报告规范的审稿助手。给你一份稿件和一项全稿校验要求，'
    '请通读全文后找出违反该要求的地方。\n'
    '硬性要求：\n'
    '  1. 只依据给定稿件判断，不得脑补、不得假设「通常都会这样写」。\n'
    '  2. 每条发现先在 quotes 里摆出原文：必须从稿件逐字照抄（不要翻译、不要概述）；'
    '前后矛盾的，两处都要给。\n'
    '  3. findings 只列有问题的地方。你检查过、确认没有问题的地方不要列出来；'
    '写到一半发现其实没问题的，把 violates 填 false。\n'
    '  4. 没有发现问题就让 findings 为空数组 —— 不要为了凑数把没问题的地方写成问题。\n'
    '  5. 稿件的研究类型使该检查根本不适用时（例如系统综述没有自设对照组、'
    '病例报告没有样本量计算），把 applicable 置为 false 并让 findings 为空。\n'
    '  6. detail 与 suggestion 用{lang}书写。'
)


def _fit(lines: list[str], budget: int) -> tuple[list[str], bool]:
    """按整行截断到字符预算内，返回 (留下的行, 是否截断)。

    留下的永远是**开头连续的若干行**，所以第 i 行就是全稿第 i 行，定位口径不变。
    按行截而不是按字符截，免得最后一行被劈成两半。

    唯一的例外：**第一行本身就超预算**（整篇没有换行的粘贴稿）时把这一行硬截到预算长度 ——
    按整行截的话一行都留不下，模型会拿着一份空稿件，四条规则全判「未发现问题」。
    """
    kept: list[str] = []
    size = 0
    for line in lines:
        if size + len(line) + 1 > budget:
            if not kept:
                kept.append(line[:budget])
            return kept, True
        kept.append(line)
        size += len(line) + 1

    return kept, False


def _severity(rule: CheckRule, positions: list[set[int]]) -> str:
    """定级只看结构，不看模型的措辞。

    `positions` 是这条发现里**每段引文**在原文里的位置（代码查出的行号集合；没找到的引文不在里面）。

    - logic 规则：要有两段引文落在**不同的位置**才是 issue（「前后矛盾」的定义），否则 warn；
    - term 规则：定位到一处就够。

    「不同的位置」= 两个位置集合谁也不包含谁。一段话在原文里出现多处时，它的集合里有好几行；
    另一段只要落在其中某一处，就可能是同一个地方，不算两处 —— 宁可少标红。
    引文找不到就不算数：模型说的「两处矛盾」连原文都对不上，够不上 issue。

    已知局限：同一句话被 PDF 拆在相邻两行、模型把两半各引一段时，会算成两处。
    """
    if rule.kind != 'logic':
        return ISSUE if positions else WARN
    for a, b in combinations(positions, 2):
        if not (a <= b or b <= a):
            return ISSUE

    return WARN


def _normalize(report: _RuleReport, rule: CheckRule, cfg: ConsistencyConfig, grounder: Grounder) -> CheckResult:
    """把模型的原始报告收敛成可展示的结果。

    - 模型自己判 `violates=false` 的丢掉（它写着写着发现没问题了）；
    - 原文、说明、建议一样都没有的丢掉（无从核起）；
    - 引文回原文定位，按定位结果定级（`_severity`）；
    - 规则状态按**全部**发现取最重的一档，再截取前 `max_findings` 条（issue 排前面）。
    """
    findings: list[Finding] = []
    for raw in report.findings:
        if not raw.violates:
            continue
        quotes = [q.strip() for q in raw.quotes if q and q.strip()]
        detail = raw.detail.strip()[:400]
        suggestion = raw.suggestion.strip()[:300]
        evidence = ' / '.join(quotes)[:200]
        if not (detail or suggestion or evidence):
            continue
        ground = grounder.ground(quotes)
        # 每段引文各自的位置；没找到的引文不贡献位置
        positions = [set(h.lines) for h in ground.hits if h.lines]
        findings.append(
            Finding(
                severity=_severity(rule, positions),
                lines=ground.lines,
                evidence=evidence,
                detail=detail,
                suggestion=suggestion,
                located=ground.located,
                claims=[{'quote': h.quote[:120], 'lines': h.lines} for h in ground.hits],
            )
        )

    # 规则状态先按全部发现算：先截断再算的话，排在第 21 条之后的 issue 会被悄悄藏掉
    if not report.applicable and not findings:
        status = NA  # 不适用且没列问题。列了问题的按问题算 —— 不许用「不适用」吞掉已指出的问题
    elif not findings:
        status = OK
    else:
        status = ISSUE if any(f.severity == ISSUE for f in findings) else WARN

    # 截断前把 issue 排到前面（同档位保持模型给的顺序），显示出来的那几条里一定有最严重的
    findings.sort(key=lambda f: f.severity != ISSUE)
    capped = len(findings) > cfg.max_findings

    return CheckResult(
        key=rule.key, kind=rule.kind, status=status, findings=findings[: cfg.max_findings], capped=capped
    )


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
    lines_by_no = line_map(manuscript or '')
    if not lines_by_no:
        raise ValueError('稿件为空')
    visible, truncated = _fit(list(lines_by_no.values()), cfg.max_chars)
    body = '\n'.join(visible)
    # 定位器只按模型**实际看到的**那部分建：截断时，没给模型看的后半段不该有引文落进去。
    # visible 是开头连续的若干行，所以第 i 行仍是全稿第 i 行
    grounder = Grounder({i + 1: line for i, line in enumerate(visible)})
    # 只切换「说明与建议用什么语言写」；指令本身始终是中文（模型读得懂）
    lang = '英文' if str(locale).lower().startswith('en') else '中文'
    system = SYSTEM_PROMPT.format(lang=lang)

    # 兜底：跑不成的规则停在 unchecked，绝不因为一次网络抖动就显示成「未发现问题」
    results: dict[str, CheckResult] = {r.key: CheckResult(key=r.key, kind=r.kind) for r in rules}
    errors: list[str] = []
    done = 0
    lock = asyncio.Lock()
    sem = asyncio.Semaphore(max(1, cfg.max_concurrency))

    async def run_one(rule: CheckRule) -> None:
        """跑一条规则：整篇稿件 + 这条规则的检查要求，一次请求。失败的规则停在 unchecked。"""
        nonlocal done
        # 规则 key 写进提示里，单测的假 runner 靠它认出是哪条规则
        human = (
            f'稿件{"（因超长只给出前一部分）" if truncated else ""}：\n'
            f'-----\n{body}\n-----\n\n'
            f'本次校验要求（{rule.key}）：\n{rule.instruction}'
        )
        async with sem:
            parsed, err = await runner.structured(_RuleReport, system, human)
        async with lock:
            done += 1
            if err:
                errors.append(f'{rule.key}: {err}')
            elif parsed is not None:
                results[rule.key] = _normalize(parsed, rule, cfg, grounder)
            if on_progress:
                on_progress(done, len(rules), f'全稿校验 {done}/{len(rules)} 项')

    # 先预热、再并发：同 audit —— 四条规则共用「system + 整篇稿件」这段前缀，
    # 第一条单独先跑完，其余三条才吃得到它留下的缓存
    if rules:
        await run_one(rules[0])
        await asyncio.gather(*(run_one(r) for r in rules[1:]))

    checks = [results[r.key] for r in rules]

    return {
        'summary': summarize(checks),
        'checks': [c.to_dict() for c in checks],
        'truncated': truncated,
        'errors': errors[:5],
    }
