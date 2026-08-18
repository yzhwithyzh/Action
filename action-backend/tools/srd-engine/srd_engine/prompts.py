"""全部提示词.

刻意用普通函数拼字符串返回 (system, human)，不用 ChatPromptTemplate ——
提示词里有大量 JSON 花括号与中文标点，模板变量转义反而是纯粹的坑。

改动本文件必须同步升 config.PROMPT_VERSION。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from srd_engine.checklist import criteria_of

if TYPE_CHECKING:
    from srd_engine.checklist import Item
    from srd_engine.schemas import ExtractDoc

# --------------------------------------------------------------------------- P1 抽取

_EXTRACT_SYSTEM = """你是系统综述方法学的资料抽取员。你的任务是从一篇系统综述的原文中，
按给定结构逐字段抽取信息。你**不做任何评价、比较或推断**。

铁律：
1. 只填原文明确写了的内容。原文没写的，present 填 "unclear"，value 留空。
2. 原文明确声明「未做某事」（如 "no sensitivity analysis was performed"），
   present 填 "no"，并在 value 里写明未做，quote 引用该声明。
   —— 「明确说了没做」和「没提到」是两回事，绝不可混为一谈。
3. quote 必须是原文的**逐字片段**（30–300 字符），保持原语言、原标点，
   不要翻译、不要改写、不要拼接不相邻的句子 —— 它是人工复核时的唯一依据。
4. quote_zh 填 quote 的中文翻译；原文本就是中文时照抄。
5. 不确定就填 unclear，不要猜。宁可留空，不要编。"""

_EXTRACT_TASK = {
    'topic': '抽取【研究主题】相关字段：研究目标、研究问题、决策需求、PICO 四要素、纳入的研究设计、范围限制。',
    'method': '抽取【研究方法】相关字段：检索的数据库与其他来源、检索时间范围、检索式结构、'
    '数据来源、提取的数据字段、效应指标、结局的数据类型。',
    'result': '抽取【研究结果】相关字段：全部纳入研究的清单（尽可能完整，含作者、年份、注册号/DOI）、'
    '原文自述的纳入研究数、特征汇总、可合并性评估、多重性处理、合成方法、异质性处理、'
    '亚组分析、缺失数据处理、敏感性分析、统计模型、各结局的合并效应量、结果解释、适用性、结论与建议。',
    'quality': '抽取【研究质量】相关字段：本综述的利益冲突与资助、纳入研究的利益冲突、'
    '偏倚风险评估工具与总体分布、缺失结果偏倚评估、证据总结方法、各结局的 GRADE 评级。',
}

_EXTRACT_HINT = {
    'result': '\n注意：included_studies 是本次抽取最重要的字段。请从纳入研究特征表、'
    '森林图标签、参考文献中「纳入研究」小节等处尽量完整地列出，'
    '并把原文自述的纳入研究数填进 included_count_reported 以便程序交叉校验。',
}


# 超长文献被切块时追加的说明。每一块在模型眼里都像一篇完整文献，很容易因为
# 「这块里没有敏感性分析」就填 present='no'；而 no 在判定端等于「两篇都明说没做 = dup」，
# 一个假 no 直接造一个假 dup。这句话是分块路径上唯一的防线。
_FRAGMENT_RULE = """

⚠ 重要：你看到的**不是完整文献**，只是其中一段。
本段里找不到的内容，present 一律填 "unclear"，**绝不可填 "no"**；
只有当你在本段中读到明确的否定陈述时，才可以填 "no"，并在 quote 里引用那句话。"""


def extract_messages(batch: str, title: str, text: str, fragment: bool = False) -> tuple[str, str]:
    task = _EXTRACT_TASK[batch]
    hint = _EXTRACT_HINT.get(batch, '') + (_FRAGMENT_RULE if fragment else '')
    human = f"""{task}{hint}

以下是系统综述《{title or "（标题未知）"}》的原文片段：

--- 原文开始 ---
{text}
--- 原文结束 ---

请按给定的 JSON 结构输出抽取结果。"""
    return _EXTRACT_SYSTEM, human


# --------------------------------------------------------------------------- P2 判定

_JUDGE_SYSTEM = """你是系统综述方法学专家，正在使用 SRD（Systematic Review Duplication，
系统综述重复性评估）工具比较两篇系统综述。

你的任务：针对每个评估条目，给两篇综述在该条目上的一致程度**打一个分**。

评分只有四档（**分越高越重复**，注意方向别反了）：
- "3" 完全相同：两篇在该条目上没有可观察的差异，完全满足该条目「3 分锚点」的描述。
- "2" 部分相同：主体一致，只有细节差异，且这些差异**不会改变**临床解读或方法学解读
  （例如检索了同一批主流数据库，只是一篇多检了一个小型区域库）。
- "1" 部分不同：存在**会改变**临床解读或方法学解读的实质差异，但两篇仍有明确的共同部分，
  不到「完全不同」的地步（例如都限定成人但一篇只收慢性期、另一篇急慢性都收）。
- "0" 完全不同：完全满足该条目「0 分锚点」的描述，两篇在该条目上没有实质共同点。

另有一个非评分取值：
- "unclear" 证据不足：任一篇的相关信息缺失或含糊到无法比较。该条目不计分、也不进分母。

关键规则：
1. 严格按下面每个条目给出的「3 分锚点 / 0 分锚点」判断，中间两档就在这两个锚点之间取，
   判据只有一条：**差异会不会改变临床或方法学解读**。不要用自己另一套直觉标准。
2. **两篇都明确报告「未做某事」属于做法一致，打 3 分**；
   两篇都「没写清楚」则是 unclear。这两种情况完全不同，务必分清。
3. 不要为了显得谨慎就一律打 2 分或 1 分。够得上锚点就打 3 或 0，
   中间档是留给「确实说得清哪里不同、但那点不同不足以（或足以）改变解读」的情形。
4. 引用必须是两篇原文的**逐字片段**，不得改写或翻译（翻译放在 cite_a_zh / cite_b_zh）。
   找不到可引用的原文时，留空并把 confidence 降为 low。
5. 理由必须点出**具体的**相同点或差异点（写出实际内容），并说明为什么落在这一档，
   禁止「两篇较为相似」「存在一定差异」这类无信息的套话。
6. 若提示中给出了「客观事实」，那是程序精确计算的结果，请以它为准，不要自行重新数数或读数。"""


def _facet_block(label: str, extract: ExtractDoc, item: Item) -> str:
    """把该条目需要的 facet 切片渲染成文本。"""
    lines = [f'【综述{label}】']
    for path in item.facet_paths:
        node = extract.get_path(path)
        lines.append(f'· {path}：{_render_facet(node)}')
    return '\n'.join(lines)


def _render_facet(node: object) -> str:
    if node is None:
        return '（无此字段）'
    if isinstance(node, list):
        if not node:
            return '（原文未报告）'
        return '\n    ' + '\n    '.join(_render_one(x) for x in node[:40])
    return _render_one(node)


def _render_one(node: object) -> str:
    present = getattr(node, 'present', None)
    if present == 'no':
        head = f'【原文明确说明未做】{getattr(node, "value", "")}'
    elif present == 'unclear':
        head = '（原文未提及或表述含糊）'
    else:
        value = getattr(node, 'value', None)
        head = str(value) if value is not None else _compact(node)
    quote = getattr(node, 'quote', '')
    if quote:
        head += f'\n      原文："{quote[:400]}"'
    return head


def _compact(node: object) -> str:
    if hasattr(node, 'model_dump'):
        data = {k: v for k, v in node.model_dump().items() if v not in (None, '', [], {})}
        return '; '.join(f'{k}={v}' for k, v in data.items())
    return str(node)


def _criteria_block(code: str) -> str:
    """渲染该条目的评分锚点。

    2 分与 1 分不在这里给 —— 它们由系统提示词里的通用档位定义统一覆盖，
    34 个条目各抄一遍纯属浪费 token，也容易抄出互相打架的口径。

    yaml 里的键名仍是 `dup_when` / `diff_when`（说的是「重复时」/「不同时」，
    与分数方向无关），0.8.0 只改了它们各自挂到哪一端的分数上。
    """
    c = criteria_of(code)
    lines = [
        '【评分锚点】',
        f'3 分（完全相同）当：{c.get("dup_when", "").strip()}',
        f'0 分（完全不同）当：{c.get("diff_when", "").strip()}',
        f'unclear（证据不足）当：{c.get("unclear_when", "").strip()}',
    ]
    if c.get('score_note'):
        lines.append(f'中间档提示：{c["score_note"].strip()}')
    if c.get('note'):
        lines.append(f'补充说明：{c["note"].strip()}')
    lines.extend(
            f'示例：A={ex.get("a", "")} / B={ex.get("b", "")} → {ex.get("rating", ex.get("verdict", ""))}'
            f'（{ex.get("why", "")}）'
        for ex in c.get('examples') or []
    )
    return '\n'.join(lines)


# --------------------------------------------------------------------------- 批量判定

_JUDGE_BATCH_SYSTEM = (
    _JUDGE_SYSTEM
    + """

本次你需要**一次性**评分多个条目。请对每个条目独立打分，逐条给出评分与理由；
**不要因为前面的条目打了 3 分就倾向于后面也打 3 分** —— 这是批量判定唯一的已知风险
（实测跨模式差异 5 个百分点，与同配置重跑的抖动同量级）。
每个条目都必须返回，一条都不能少。"""
)


def judge_batch_messages(
    items: list[Item], extract_a: ExtractDoc, extract_b: ExtractDoc, cards: dict[str, str]
) -> tuple[str, str]:
    blocks = []
    for item in items:
        block = [f'【评估条目 {item.code}】{item.question_zh}', _criteria_block(item.code)]
        if cards.get(item.code):
            block.append(f'【客观事实】\n{cards[item.code]}')
        block.extend((_facet_block('A', extract_a, item), _facet_block('B', extract_b, item)))
        blocks.append('\n'.join(block))
    body = '\n\n========================================\n\n'.join(blocks)
    codes = '、'.join(i.code for i in items)
    return _JUDGE_BATCH_SYSTEM, f'{body}\n\n请依次给出条目 {codes} 的评分，每条独立打分。'
