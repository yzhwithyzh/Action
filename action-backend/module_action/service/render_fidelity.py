"""
「整篇成文」的代码核对（纯函数，可离线单测，见 `tools/tests/test_report_render.py`）。

模型被要求「只用素材里的事实、数字逐字照抄、占位原样保留、每条都写进去」，但这几条
**不靠模型自觉** —— 每一章写完由这里核一遍，不通过的那一章在页面上标出来并说明原因。
核对只标记、不自动重跑：重跑同样可能出错，而原因摆在用户面前，他决定是改素材还是重新生成。

四项，按严重程度：

1. **多出来的数字**：正文里有、素材里没有。这是编造数据的直接信号（`n=120, p=0.03`），最要命
2. **丢掉的数字**：素材里有、正文里没有。作者写下的数据没进论文
3. **占位变少**：【待补充】被删掉或被模型「填」上了
4. **漏写的条目**：已填的素材，没有任何一段标注取材于它
5. **穴位代码**：多出来或丢掉的（ST36、LI4、EX-HN3 …），与数字分开报 —— 改错一个穴位是方法学错误

数字先做 NFKC：中文稿里全角数字（`４０例`）是常态，不归一化的话同一个数会被判成一增一减。
小数点后的尾零不去掉（`0.50` 与 `0.5` 在论文里不是一回事，报出来让人看一眼）。
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

_NUM = re.compile(r'(?<![A-Za-z0-9.])\d+(?:\.\d+)?')
#: 穴位代码：十四经缩写 + 序号（ST36 / LI4 / GV20 / PC6，含 TE/SJ、LR/LV、GV/DU、CV/RN 两套写法），
#: 以及奇穴 EX-HN3 这类。**只认经脉缩写**：泛化成「1–3 个大写字母 + 数字」会把 SF36、IL6、CD4、
#: HAMD17 这些量表与指标名当成穴位，误报一多用户就学会忽略它，真改错的穴位也跟着被忽略。
#: 边界用「前后不是字母数字」而不是 `\b`：Python 的 `\b` 把汉字算作单词字符，
#: 「足三里ST36」里「里」和「S」之间没有词边界，`\b` 写法在中文稿里根本认不出来
_MERIDIANS = 'LU|LI|ST|SP|HT|SI|BL|KI|PC|TE|SJ|GB|LR|LV|GV|DU|CV|RN'
#: 写法容差：经脉缩写与序号之间允许**一个**空格或连字符（ST 36、GV-20），大小写不论（St36）。
#: 只认半角空格不认 `\s`：换行两边的字母与数字不是一个代码。全小写又隔着空格的（「li 4」「du 2」）
#: 在英文稿里多半是巧合，不认（`_acu_iter`）
_ACU = re.compile(
    rf'(?<![A-Za-z0-9])(?:EX([- ]?)([A-Z]{{1,3}})[- ]?(\d{{1,2}})|({_MERIDIANS})([- ]?)(\d{{1,2}}))(?![A-Za-z0-9])',
    re.I,
)
#: 千分位：`1,200` 与 `1200` 是同一个数。不先去掉的话会被拆成 1 和 200，同时报「多出 1200」「丢掉 200」
_THOUSANDS = re.compile(r'(?<=\d),(?=\d{3}(?!\d))')
#: 同一条经的两套缩写（国标与 WHO 写法混用很常见），比较前归一，互换不算改错
_SYNONYM = {'LV': 'LR', 'SJ': 'TE', 'DU': 'GV', 'RN': 'CV'}
_PLACEHOLDER = re.compile(r'【待补充[^】]*】|\[to be completed[^\]]*\]', re.I)


def _norm(text: str) -> str:
    return unicodedata.normalize('NFKC', text or '')


def _acu_iter(text: str) -> Iterator[tuple[re.Match[str], str]]:
    """逐个认出穴位代码 → (匹配, 归一后的代码)。text 须已 NFKC"""
    for m in _ACU.finditer(text):
        ex_sep, ex_area, ex_no, meridian, sep, no = m.groups()
        letters, gap = ('EX' + ex_area, ex_sep) if ex_area else (meridian, sep)
        if gap == ' ' and m.group(0)[: len(letters) + 1].replace(' ', '').islower():
            continue
        if ex_area:
            yield m, f'EX-{ex_area.upper()}{int(ex_no)}'
        else:
            code = meridian.upper()
            yield m, f'{_SYNONYM.get(code, code)}{int(no)}'


def numbers(text: str) -> Counter[str]:
    """正文里的数字（不含穴位代码里的序号 —— 那一层单独核）"""
    t = _norm(text)
    spans = [m.span() for m, _code in _acu_iter(t)]
    for start, end in reversed(spans):
        t = f'{t[:start]} {t[end:]}'
    t = _THOUSANDS.sub('', t)

    return Counter(_NUM.findall(t))


def acupoints(text: str) -> set[str]:
    """正文里的穴位代码，归一成 `ST36` / `EX-HN3` 这种写法"""
    return {code for _m, code in _acu_iter(_norm(text))}


def placeholders(text: str) -> int:
    return len(_PLACEHOLDER.findall(_norm(text)))


@dataclass(frozen=True)
class Issue:
    """一项核对不通过。`values` 是具体的数字 / 代码 / 条目号，页面上照列"""

    kind: str
    values: tuple[str, ...] = ()


@dataclass(frozen=True)
class SectionCheck:
    ok: bool
    issues: tuple[Issue, ...] = field(default_factory=tuple)


def check_section(
    sources: Sequence[tuple[int, str, str, bool]],
    paragraphs: Iterable[tuple[str, Sequence[int]]],
) -> SectionCheck:
    """
    核一章

    :param sources: 素材 [(条目id, 条目号, 正文, 是否占位)]
    :param paragraphs: 成文段落 [(正文, 取材的条目id)]
    :return: 核对结果
    """
    paras = list(paragraphs)
    src_text = '\n'.join(text for _id, _no, text, _ph in sources)
    out_text = '\n'.join(text for text, _ids in paras)
    issues: list[Issue] = []

    src_n, out_n = numbers(src_text), numbers(out_text)
    # 按「出现过没有」比，不按次数：同一个数在素材里写两遍、正文合并成一处是对的
    added = sorted(set(out_n) - set(src_n), key=_num_key)
    dropped = sorted(set(src_n) - set(out_n), key=_num_key)
    if added:
        issues.append(Issue('addedNumbers', tuple(added)))
    if dropped:
        issues.append(Issue('droppedNumbers', tuple(dropped)))

    if placeholders(out_text) < placeholders(src_text):
        issues.append(Issue('droppedPlaceholders', (str(placeholders(src_text) - placeholders(out_text)),)))

    covered = {i for _text, ids in paras for i in ids}
    missing = [no or str(item_id) for item_id, no, text, ph in sources if not ph and text.strip() and item_id not in covered]
    if missing:
        issues.append(Issue('uncoveredItems', tuple(missing)))

    src_a, out_a = acupoints(src_text), acupoints(out_text)
    if out_a - src_a:
        issues.append(Issue('addedAcupoints', tuple(sorted(out_a - src_a))))
    if src_a - out_a:
        issues.append(Issue('droppedAcupoints', tuple(sorted(src_a - out_a))))

    return SectionCheck(ok=not issues, issues=tuple(issues))


def _num_key(s: str) -> tuple[float, str]:
    try:
        return (float(s), s)
    except ValueError:
        return (0.0, s)
