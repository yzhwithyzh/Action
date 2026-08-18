"""
报告初稿合成的纯算法（报告助手第二步的「一键生成初稿」）。

和 `srd_export_service` 同一种分层：**输入是数据结构，输出是文本，中间不碰数据库、
不碰 HTTP、不读全局配置**，因此可以离线单测（见 `tools/tests/test_report_draft_compose.py`）。
服务层负责把库里的条目与草稿正文喂进来。

## 产出的是「稿件」，不是「填好的清单」

合成结果要能直接送进第三步逐条校验，所以**绝不能把 checklist 的条目要求原文写进正文**：
条目要求长得就像一句合格的报告（「文题能识别是随机临床试验」），把它抄进稿件，
第三步的判定模型会把这句要求本身当成用户报告过的内容，逐条判定整体作废。
同理，未填的必填条目只留一个不含要求原文的占位标记 `【待补充：条目 1a】` ——
既让缺口在正文里看得见，又不会被误判成已报告。

`ComposeItem` 因此**刻意不带条目要求原文**：这条约束不靠自觉遵守，靠数据结构里
根本没有那个值 —— 想让它重新出现在正文里，得先显式把字段加回来。

清单表标题（part）也不进正文：那是「CONSORT 对照检查清单与非药物临床试验扩展版」
这类**表格名**，不是论文章节；章节是 domain（题目和摘要 / 引言 / 方法…）。
所以正文按 domain 分节，跨清单表的同名章节自然合并。

## 针刺参数为什么没有单独的字段

早先这里有一组「针灸特色专属字段」（选穴依据 / 进针手法 / 得气 / 对照措施），
用户填一次，合成时按关键词挂到语义最近的那条条目下面。**已整体撤除**：

库里 6 份规范有 5 份本身就是针刺适配版（STRICTA / SPIRIT-TCM / PRISMA-Acu /
CARE-Acu / RIGHT-Acu），这些内容在 checklist 里各有对应条目；而条目是后台
「规范条目管理」页可增删改的。于是同一件事有了两个来源，其中一个后台还管不到 ——
用户两处都填时，初稿里会把同一段针刺方案输出两遍，正好撞在第三步的一致性检查上。
ARRIVE（通用动物实验规范，21 条零针刺内容）那种真缺口，由后台补条目解决，不由代码解决。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

#: 支持的输出语言
ZH = 'zh'
EN = 'en'


@dataclass(frozen=True)
class ComposeItem:
    """
    合成用到的一条 checklist 条目（服务层从 action_guideline_item 转过来）

    **没有「条目要求原文」这个字段**，理由见模块 docstring。
    """

    item_id: int
    #: 章节/领域，正文按它分节
    domain: str = ''
    #: 条目号（1a / 2b …），只用于占位标记
    item_no: str = ''
    #: '0' 必填 / '1' 条件填写
    require_level: str = '0'


@dataclass(frozen=True)
class ComposeResult:
    """
    合成结果
    """

    text: str
    char_count: int = 0
    #: 仍未填写的必填条目数
    missing_required: int = 0
    #: 已填写的条目数
    filled_count: int = 0


#: 已下线条目正文的兜底小节标题。条目被后台停用/删除后，用户为它写的正文没有章节可归，
#: 但那仍是用户的原话 —— 丢掉它等于交出一份「看起来完整、实际少了几段」的初稿
_ORPHAN_TITLE = {ZH: '其他内容', EN: 'Other content'}
#: 未填必填条目的占位标记。**刻意不含条目要求原文**，理由见模块 docstring
_PLACEHOLDER = {ZH: '【待补充：条目 {no}】', EN: '[To be completed: item {no}]'}
_PLACEHOLDER_NO_NUM = {ZH: '【待补充】', EN: '[To be completed]'}


def compose_draft_text(
    title: str,
    items: Sequence[ComposeItem],
    contents: dict[int, str],
    locale: str = ZH,
    orphan_texts: Sequence[str] = (),
) -> ComposeResult:
    """
    把一份草稿合成为可直接送去校验的报告初稿正文

    :param title: 草稿名称，作为正文首行；留空则不出这一行
    :param items: 该规范的全部启用条目，**必须已按展示顺序排好**
    :param contents: 条目id -> 用户写的正文
    :param locale: 输出语言（zh / en），只影响占位标记与兜底小节标题
    :param orphan_texts: 所属条目已下线的正文，追加到末尾单独成节，绝不丢弃
    :return: 合成结果
    """
    lang = EN if locale == EN else ZH
    filled = {item_id: text.strip() for item_id, text in contents.items() if text and text.strip()}

    lines: list[str] = []
    if title.strip():
        lines.append(title.strip())

    missing_required = 0
    current_domain: str | None = None
    section: list[str] = []

    def flush() -> None:
        """把当前章节收进正文；整节没内容就连标题一起丢掉"""
        if not section:
            return
        if lines:
            lines.append('')
        if current_domain:
            lines.append(current_domain)
        lines.extend(section)
        section.clear()

    for it in items:
        domain = (it.domain or '').strip()
        if domain != current_domain:
            flush()
            current_domain = domain

        body = filled.get(it.item_id, '')
        if body:
            section.append(body)
        elif it.require_level == '0':
            missing_required += 1
            no = (it.item_no or '').strip()
            section.append(_PLACEHOLDER[lang].format(no=no) if no else _PLACEHOLDER_NO_NUM[lang])
        # 选填且没填 —— 直接略过，不留痕迹：条件填写项本就可能不适用于这份研究，
        # 给它留占位行会让初稿被无关的「待补充」淹没

    flush()

    # 条目已被后台停用/删除，但正文还在。**只挪位置，不丢弃** ——
    # 初稿少几段而用户看不出来，比多一个古怪的小标题严重得多
    if orphan_texts:
        if lines:
            lines.append('')
        lines.append(_ORPHAN_TITLE[lang])
        lines.extend(orphan_texts)

    text = '\n'.join(lines).strip()

    return ComposeResult(
        text=text,
        char_count=len(text),
        missing_required=missing_required,
        filled_count=len(filled),
    )
