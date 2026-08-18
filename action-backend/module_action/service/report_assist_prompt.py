"""
第四步「AI 辅助撰写」的提示词构造（纯函数，可离线单测）。

和 `report_compose_service` / `srd_export_service` 同一种分层：**输入是数据结构，输出是
消息列表，中间不碰数据库、不碰 HTTP、不读全局配置**。发请求、切模型那些事在
`ai_assist_service`，见 `tools/tests/test_report_assist_prompt.py`。

## 上下文是可选的，不是前提

`AssistContext` 的字段**全部有默认值，全部可以为空**，这不是图省事：

《智能报告辅助工具.docx》第 4 节四项功能（续写 / 背景生成 / 润色 / 翻译）的输入
**全都是用户直接给的**——关键词、研究方向、要润色的那段话、要翻译的摘要。没有一项依赖
第二步的草稿或第三步的判定。这里一度写着「必须带着条目走」，理由是文档那句「遵循 STRICTA
条目规范」露了馅、遵循哪一条得先站在某一条上 —— **那个推理是错的**：这句话要的是
「知道按哪份规范写」，而那个信息**第一步就给了**；把「需要规范」读成「需要具体条目」，
再推出「需要草稿和判定」，实际效果是把已经写好稿、直接来第三步的用户
（文档意义上最主要的一类用户）整个挡在第四步之外。

所以现在：`guideline_code` 单独给就够用，`item_no` / `requirement` / `verdict` 有就带上、
没有就不带。有草稿时那条路（条目要求 + 已写正文 + 第三步判定 + 改完写回）依然在，
它是**快捷方式，不是入口条件**。

条目要求一旦带上，进的是 system 提示、当**指令**用，绝不当成待续写的内容 —— 否则模型会把
「文题能识别是随机临床试验」这句要求本身抄进正文，与 `report_compose_service` 那条
「条目要求原文不许进稿件」是同一个坑的两端。

## 三条不许越的线

写进 system 提示、且每个动作都重复一遍，因为这是学术报告工具，不是文案生成器：

1. **不许编造研究数据。** 样本量、p 值、置信区间、随访时长、不良事件数……模型没拿到就
   留空位（`【待补充：样本量】`），绝不许猜一个像样的数字。一篇稿子里混进一个编造的
   `n=120, p=0.03` 是科研诚信事故，不是文风问题。
2. **不许新增未提供的方法学事实。** 用户说「电针疏密波」，就只能展开疏密波；不能顺手补上
   「频率 2/100 Hz、留针 30 分钟」这类没说过的参数 —— 那些恰恰是 STRICTA 要求如实报告的。
3. **只输出正文本身。** 不要「好的，以下是…」这类开场白，不要 markdown 标记，不要把条目
   编号重复一遍。这段文字会被直接写进稿件字段。
"""

from __future__ import annotations

from dataclasses import dataclass

#: 支持的语言
ZH = 'zh'
EN = 'en'

#: 三个动作
CONTINUE = 'continue'
POLISH = 'polish'
TRANSLATE = 'translate'


@dataclass(frozen=True)
class AssistContext:
    """
    一次改写请求的全部上下文（服务层从库里取好后传进来）
    """

    #: 规范代号，如 STRICTA / CONSORT
    guideline_code: str = ''
    #: 条目号（1a / 6b …）
    item_no: str = ''
    #: 章节/领域（方法 / 结果 …）
    domain: str = ''
    #: 条目要求原文。**当指令用，绝不当待续写内容**
    requirement: str = ''
    #: 条目的扩展说明（部分规范有）
    extension: str = ''
    #: 用户已经写在这一条里的正文
    current_text: str = ''
    #: 第三步对这一条的判定（vague / missing / reported / 空=没判过）
    verdict: str = ''
    #: 第三步给出的判定说明
    verdict_reason: str = ''


#: 润色风格 → 给模型的具体要求。**空字符串不在表内**，由调用方兜到 rigorous
_STYLE_RULES = {
    'rigorous': {
        ZH: '更严谨：补足方法学限定语（如「本研究中」「按方案集」），避免绝对化措辞，'
        '把因果表述降级为关联表述，除非原文明确说明是随机对照设计。',
        EN: 'More rigorous: add methodological qualifiers, avoid absolute claims, and downgrade '
        'causal wording to associational unless the text states a randomised design.',
    },
    'concise': {
        ZH: '更精炼：删去冗词与重复，合并同义句，保持信息量不变的前提下缩短篇幅。不要删掉任何数据或限定语。',
        EN: 'More concise: cut redundancy and merge duplicate sentences while preserving every '
        'data point and qualifier.',
    },
    'critical': {
        ZH: '更具批判性：显式点出本条所述做法的局限与潜在偏倚来源，但只针对原文已给出的信息，不引入新事实。',
        EN: 'More critical: make the limitations and potential sources of bias explicit, but only '
        'for information already present in the text.',
    },
}

#: 三条硬约束，每次都随 system 提示发出去
_GUARDRAILS = {
    ZH: (
        '你是针刺临床研究报告的写作助手，服务于国际报告规范（EQUATOR）下的论文撰写。\n'
        '必须遵守以下三条，违反任何一条都比不作答更糟：\n'
        '1. 绝不编造研究数据。样本量、p 值、置信区间、随访时长、不良事件数等，'
        '凡是没有在输入中给出的，一律写成「【待补充：xxx】」占位，不许猜测或举例。\n'
        '2. 绝不新增未提供的方法学事实。用户没说的针具规格、穴位、频率、留针时长、'
        '对照设置等，不许替他补全 —— 那些正是报告规范要求如实披露的内容。\n'
        '3. 只输出正文本身。不要开场白、不要解释你做了什么、不要 markdown 标记、'
        '不要重复条目编号或条目要求。'
    ),
    EN: (
        'You assist with writing acupuncture clinical research reports under the international '
        'reporting guidelines (EQUATOR).\n'
        'Three rules; breaking any of them is worse than not answering:\n'
        '1. Never fabricate study data. Sample sizes, p values, confidence intervals, follow-up '
        'durations, adverse-event counts — anything not supplied must be written as a '
        '"[to be completed: ...]" placeholder, never guessed or exemplified.\n'
        '2. Never add methodological facts that were not supplied. Needle specifications, points, '
        'frequencies, retention times and control set-ups are exactly what the guideline requires '
        'to be reported truthfully.\n'
        '3. Output the prose only. No preamble, no explanation of what you did, no markdown, '
        'no repetition of the item number or its requirement.'
    ),
}


def _requirement_block(ctx: AssistContext, lang: str) -> str:
    """
    把条目要求拼成一段「写作依据」。

    这段进 system 提示，是**指令**不是素材 —— 模型照着它写，而不是把它抄进正文。

    三档，按手上有什么给什么：

    · 有条目要求 → 完整的「写作依据」块（草稿模式，或独立模式下用户挑了某一条）
    · 只有规范代号 → 一句「按 STRICTA 规范写」（独立模式的常态）
    · 什么都没有 → 空串，整块不出现。**不能留一个光秃秃的「写作依据」标题**：
      标题下面空着会让模型去猜依据是什么，比不给还糟

    :param ctx: 上下文
    :param lang: 语言
    :return: 可直接拼进 system 提示的一段文字；无上下文时为空串
    """
    body = '\n'.join(x for x in (ctx.requirement.strip(), ctx.extension.strip()) if x)
    head = ' · '.join(x for x in (ctx.guideline_code, ctx.item_no, ctx.domain) if x)

    if not body:
        if not ctx.guideline_code:
            return ''

        return (
            f'写作依据：遵循 {ctx.guideline_code} 报告规范的要求与体例。'
            if lang == ZH
            else f'Write in accordance with the {ctx.guideline_code} reporting guideline.'
        )

    label = '写作依据（报告规范条目，照它写，不要抄它）' if lang == ZH else (
        'Requirement to satisfy (write to it; do not copy it)'
    )

    return f'{label}\n{head}\n{body}'.strip()


def _verdict_block(ctx: AssistContext, lang: str) -> str:
    """
    把第三步对这一条的判定拼成一段。没判过就返回空串。

    :param ctx: 上下文
    :param lang: 语言
    :return: 一段文字，或空串
    """
    if ctx.verdict not in ('vague', 'missing'):
        return ''
    if lang == ZH:
        head = '第三步校验判定：' + ('描述模糊' if ctx.verdict == 'vague' else '未报告')
        tail = f'（{ctx.verdict_reason.strip()}）' if ctx.verdict_reason.strip() else ''
        return f'{head}{tail}。改写要正面解决这个问题。'
    head = 'Step-3 verdict: ' + ('vague' if ctx.verdict == 'vague' else 'not reported')
    tail = f' ({ctx.verdict_reason.strip()})' if ctx.verdict_reason.strip() else ''

    return f'{head}{tail}. Your rewrite must address it directly.'


def build_messages(action: str, ctx: AssistContext, style: str = '', keywords: str = '', locale: str = ZH) -> list[dict]:
    """
    构造一次改写调用的消息列表

    :param action: continue / polish / translate
    :param ctx: 条目上下文
    :param style: 润色风格，仅 polish 用；不在表内一律按 rigorous
    :param keywords: 续写关键词，仅 continue 用
    :param locale: 界面语言，决定提示词语言与输出语言（translate 例外，固定输出英文）
    :return: [{'role': ..., 'content': ...}, ...]
    :raises ValueError: action 不认识
    """
    lang = EN if locale == EN else ZH
    parts = [_GUARDRAILS[lang], _requirement_block(ctx, lang)]
    verdict = _verdict_block(ctx, lang)
    if verdict:
        parts.append(verdict)

    current = ctx.current_text.strip()
    if action == CONTINUE:
        task = (
            '任务：根据下面的关键词，写出这一条应有的报告段落。已有正文若非空，'
            '在其基础上续写并保持文风一致，不要重复已写过的内容。'
            if lang == ZH
            else 'Task: write the reporting passage this item calls for, based on the keywords below. '
            'If existing text is present, continue from it in the same voice without repeating it.'
        )
        user = (f'关键词：{keywords.strip()}' if lang == ZH else f'Keywords: {keywords.strip()}')
        if current:
            user += ('\n\n已有正文：\n' if lang == ZH else '\n\nExisting text:\n') + current
    elif action == POLISH:
        rule = _STYLE_RULES.get(style or 'rigorous', _STYLE_RULES['rigorous'])[lang]
        task = ('任务：把下面这段正文做学术化润色。' if lang == ZH else 'Task: academically polish the passage below.') + rule
        user = ('待润色正文：\n' if lang == ZH else 'Passage to polish:\n') + current
    elif action == TRANSLATE:
        # 翻译固定输出英文：这个功能存在的理由就是投稿国际期刊
        task = (
            '任务：把下面这段中文正文译成可直接投稿国际期刊的学术英文。'
            '保留全部数据与限定语，术语用国际针刺研究文献的通行译法（如「得气」→ de qi）。'
            '只输出英文译文。'
            if lang == ZH
            else 'Task: translate the passage below into publication-ready academic English, '
            'preserving every data point and qualifier and using the terminology conventional in '
            'international acupuncture research (e.g. de qi). Output the translation only.'
        )
        user = ('待翻译正文：\n' if lang == ZH else 'Passage to translate:\n') + current
    else:
        raise ValueError(f'未知的改写动作: {action}')

    parts.append(task)

    return [
        {'role': 'system', 'content': '\n\n'.join(p for p in parts if p)},
        {'role': 'user', 'content': user.strip()},
    ]


def needs_current_text(action: str) -> bool:
    """
    这个动作是不是必须有已写正文才做得了

    润色与翻译都是**改写已有内容**，没有输入就没有输出；续写只要有关键词即可。
    服务层据此在调模型前就挡下来，省掉一次白花钱的调用。

    :param action: 动作
    :return: 是否必须有正文
    """
    return action in (POLISH, TRANSLATE)
