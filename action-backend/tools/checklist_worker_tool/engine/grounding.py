"""引文回原文定位（纯函数，不调模型）。

**行号只从这里来。** 模型看到的稿件不带行号、输出里也没有行号字段，它只负责逐字照抄原文；
「这段话在第几行」由本模块在原文里查出来。原因：让模型报行号，它会报错、会编
（实测 qwen3.8-flash 吐过等差数列一样的行号），而且错了看不出来；行号只在系统内部用
（前台「在原文中查看」的高亮、导入回填按行取段落、一致性判「两处不同位置」），
由代码查出来的位置换什么模型都一样。

**查不到就没有位置，不猜。** 引文在原文里找不到时 `lines=[]`、`located='no'`，前台提示人工核对；
判定本身（reported/vague/missing、warn/issue 的定级规则）不因为「找没找到」而被推翻。
这条纪律是量出来的：用精确子串去核 deepseek 的输出，55 条「对不上」里 37 条是「……」拼接
的多处真实原文、10 条是删节、2 条是英文稿给了中文译文、剩下 6 条逐条看过也都不是编造 ——
朴素核对会把好模型 20%–45% 的正确判定误判成「证据不实」。所以：

- 先切：按省略号、分号拆段；整段找不到时再退到引号里的内容（模型爱写「文题“……”未含随机」
  这种夹叙夹引）。先整段、后引号：原文本身带引号时（采用“平补平泻”手法……）不能只核那四个字；
- 再比：先在归一化全文里找精确子串（跨行也认，PDF 常把一句话断在两行），
  找不到再按字符 n-gram 覆盖率做模糊比对，容忍空格、全半角、标点差异；
- **同一段话在原文里出现多处，全部标出**（最多 `MAX_POSITIONS` 处）。摘要和方法里各写一遍
  「每组 30 例」很常见，没有模型行号可以帮忙挑，替它猜一处不如都摆出来；
- 稿件里几乎没有这种文字（中文引文 × 纯英文稿）→ 判「无从核对」，不判「对不上」；
- 过短的片段（归一化后不足 `MIN_QUOTE_CHARS`）不核；不足 `MIN_FUZZY_CHARS` 的只做精确匹配
  —— 「足三里穴」这种穴名短，但一致性的术语规则就靠它定位，模糊比对四个字没有意义。

`GroundResult.fabricated`（所有引文在全文里连相似的都没有）只作模型准入评测的指标：
拿 4 篇真实论文 × 3 个模型校准时，qwen 被它标出的 12 条**全是「第74-86行前言部分介绍了……」
这种用概述代替引文**的写法 —— 条目本身判对了，拿它降级就是误伤。

校准结果（引文能定位的比例，2026-09）：deepseek 213/229 · qwen3.7-plus 206/226 ·
qwen3.8-flash 198/226；同一批数据用精确子串去核，deepseek 只有 55%–90%。
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

#: 归一化后短于这个长度的片段不核（一两个字到处都是）
MIN_QUOTE_CHARS = 2
#: 归一化后短于这个长度的片段只做精确匹配，不做模糊比对
MIN_FUZZY_CHARS = 6
#: 模糊比对的覆盖率达到这个值即认为「找到了」
FUZZY_OK = 0.75
#: 模糊比对里与最高分相差不超过这个值的位置视为并列，一起标出
FUZZY_TIE = 0.05
#: 所有可核对引文在全文任何位置的最佳覆盖率都不超过这个值，才标 fabricated（只作评测指标）
FABRICATED_MAX_COVERAGE = 0.35
#: 模糊比对时一个候选窗口最多跨几行（PDF 硬换行会把一句话拆开）
MAX_SPAN_LINES = 3
#: 同一段引文最多标出几处位置。常见短语全文到处都是，标太多等于没标
MAX_POSITIONS = 5
#: 稿件里某种文字**既**少于 MIN_SCRIPT_CHARS 个、**又**不到全部文字的 MIN_SCRIPT_SHARE，
#: 才认为这份稿件「没有这种文字」：这种文字的引文核不了（中文引文 × 纯英文稿），判 skip 而不是 miss。
#: 两个条件缺一不可 ——
#: - 只看「哪种文字占多数」：中文稿带英文摘要时，编造的英文引文会被判成核不了、逃过提示；
#: - 只看绝对数量：篇幅短的中文稿汉字不到 200 个，中文引文也全被判成核不了（单测踩到过）
MIN_SCRIPT_CHARS = 200
MIN_SCRIPT_SHARE = 0.1
#: 覆盖率到这个值就不必再往下多拼一行了
_FULL_COVERAGE = 0.999

#: 引文分段：省略号的各种写法、中英文分号、换行
_SPLIT_RE = re.compile(r'……|…|\.{3,}|。{2,}|；|;|\n')
#: 引号里的内容。**不含 ASCII 单引号**：英文里它是撇号（patients' consent），不是引号
_QUOTED_RE = re.compile(r'[“"「『‘]([^”"」』’]{4,})[”"」』’]')
_CJK_RE = re.compile(r'[㐀-鿿]')
_LATIN_RE = re.compile(r'[a-zA-Z]')
_DIGITS_RE = re.compile(r'\d+')

#: 核对结论
LOCATED_YES = 'yes'  # 可核对的引文全部在原文找到
LOCATED_PARTIAL = 'partial'  # 找到一部分
LOCATED_NO = 'no'  # 可核对的引文一段都没找到 —— 前台提示「未能在原文中自动定位」
LOCATED_NONE = 'none'  # 根本没给引文 —— 前台提示「未提供原文依据」
LOCATED_NA = ''  # 给了引文但都核不了（太短、语种对不上）；以及 missing 判定 —— 不提示


def normalize(text: str) -> str:
    """全角转半角、转小写、只留字母数字与汉字。

    标点与空白全部去掉：PDF 抽出来的「2022 年3 月」与模型照抄的「2022年3月」
    是同一段原文，差别只在空格。
    """
    text = unicodedata.normalize('NFKC', text or '').lower()

    return ''.join(ch for ch in text if ch.isalnum())


def script_of(text: str) -> str:
    """粗判一段引文的文字体系：'cjk' / 'latin' / ''。"""
    cjk = len(_CJK_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))
    if not cjk and not latin:
        return ''

    return 'cjk' if cjk * 3 >= latin else 'latin'


def split_quotes(raw: str | list[str]) -> list[str]:
    """把模型给的引文按省略号、分号拆成可以逐段核对的片段。

    新的输出结构本来就是短引文列表，但模型仍可能在单条里用省略号拼接，所以每一条照样过一遍。
    引号里的内容**不在这里提取**：先拿整段去找，找不到才退到引号里（见 `Grounder.locate`）。
    """
    parts = raw if isinstance(raw, list) else [raw]
    out: list[str] = []
    for part in parts:
        for seg in _SPLIT_RE.split(str(part or '')):
            piece = seg.strip(' 　"“”「」『』‘’')
            if piece:
                out.append(piece)

    return out


def _gram_size(text: str) -> int:
    """n-gram 的 n：汉字用 2（一个词常就两个字），拉丁文用 3（2 太宽松，到处都能凑上）。"""
    return 2 if script_of(text) == 'cjk' else 3


def _grams(text: str, n: int) -> set[str]:
    """字符 n-gram。**n 由引文决定、原文行跟着用同一个 n** —— 两边各按自己的文字体系选 n
    的话，一段中英混排的引文（「完全自主排便次数(complete spontaneous…)」）去比一行纯英文，
    一边切 2-gram、一边切 3-gram，覆盖率被压到 0.27，真实引文被判成疑似编造。踩过一次。
    """
    if len(text) < n:
        return {text} if text else set()

    return {text[i : i + n] for i in range(len(text) - n + 1)}


@dataclass
class QuoteHit:
    """单段引文的核对结果。"""

    quote: str
    #: 'exact' 精确子串 / 'fuzzy' 模糊命中 / 'miss' 没找到 / 'skip' 无从核对
    kind: str
    #: 每处出现覆盖的行号区间（一段话可能跨行），按原文顺序，最多 MAX_POSITIONS 处
    spans: list[list[int]] = field(default_factory=list)
    #: 全文中最相似位置的覆盖率（0–1）；skip 时为 None
    coverage: float | None = None

    @property
    def lines(self) -> list[int]:
        """所有出现位置合起来的行号。"""
        return sorted({no for span in self.spans for no in span})


@dataclass
class GroundResult:
    """一条判定（或一条发现）的核对结论。"""

    located: str = LOCATED_NA
    #: 找到的位置（所有找到的引文、所有出现处合起来）。没找到的引文不贡献行号，**不沿用模型的任何数字**
    lines: list[int] = field(default_factory=list)
    #: 所有可核对引文在全文里连相似的都没有（多半是用概述代替了引文）。只作评测指标，不改判定
    fabricated: bool = False
    hits: list[QuoteHit] = field(default_factory=list)


class Grounder:
    """针对一份稿件的核对器。建一次、核多次（一次校验有几十上百条判定）。"""

    def __init__(self, line_texts: dict[int, str]) -> None:
        """:param line_texts: 行号 → 该行原文，必须来自 `audit.line_map`（全仓「第 N 行」的唯一定义）"""
        self.line_nos = sorted(line_texts)
        self.norm_lines = {no: normalize(line_texts[no]) for no in self.line_nos}
        #: 两种切法都备好，比对时按引文的 n 取
        self.gram_lines = {n: {no: _grams(t, n) for no, t in self.norm_lines.items()} for n in (2, 3)}
        # 归一化全文 + 每个字符属于哪一行：精确匹配要能跨行（PDF 把一句话断成两行）
        buf: list[str] = []
        owner: list[int] = []
        for no in self.line_nos:
            t = self.norm_lines[no]
            buf.append(t)
            owner.extend([no] * len(t))
        self.full = ''.join(buf)
        self.owner = owner
        raw = ''.join(line_texts[no] for no in self.line_nos)
        #: 稿件里每种文字的字符数，用来判断「这种文字的引文核不核得了」
        self.script_chars = {'cjk': len(_CJK_RE.findall(raw)), 'latin': len(_LATIN_RE.findall(raw))}

    # ------------------------------------------------------------------ 单段

    def _has_digits(self, digits: list[str], lines: list[int]) -> bool:
        """引文里的每一串数字，都原样出现在这几行（归一化后拼起来）里。"""
        if not digits:
            return True
        text = ''.join(self.norm_lines[no] for no in lines)

        return all(d in text for d in digits)

    def _script_absent(self, script: str) -> bool:
        """这份稿件里是不是几乎没有这种文字（阈值与理由见 MIN_SCRIPT_CHARS）。"""
        if not script:
            return False
        count = self.script_chars.get(script, 0)
        total = sum(self.script_chars.values())

        return count < MIN_SCRIPT_CHARS and count < total * MIN_SCRIPT_SHARE

    def _exact(self, qn: str) -> list[list[int]]:
        """所有精确出现位置（按原文顺序，最多 MAX_POSITIONS 处），每处给出覆盖的行号区间。"""
        spans: list[list[int]] = []
        start = self.full.find(qn)
        while start >= 0 and len(spans) < MAX_POSITIONS:
            first, last = self.owner[start], self.owner[start + len(qn) - 1]
            spans.append([no for no in self.line_nos if first <= no <= last])
            # 从这一处的末尾之后接着找，同一处不会因为自身重叠被数两次
            start = self.full.find(qn, start + len(qn))

        return spans

    def _fuzzy(self, qn: str) -> tuple[float, list[list[int]]]:
        """模糊比对：返回最高覆盖率，以及所有与最高分并列（差 ≤ FUZZY_TIE）的互不重叠的位置。

        覆盖率 = 引文的 n-gram 里有多少出现在候选行中（集合口径，不看顺序与次数）。
        只算「引文被覆盖了多少」而不是双向相似度：候选行比引文长很正常（引文是摘一句），
        不该因为那一行还写了别的内容就扣分。已知局限：不看字序，主语对调的句子也能达标
        （deferred-work C1）。

        **数字必须原样出现**：引文里的每一串数字都要在候选行里找得到，否则这个位置不算。
        覆盖率对数字几乎不敏感 ——「第 300 行」与「第 30 行」只差一个 2-gram，覆盖率 0.94；
        「每组 30 例」与「每组 31 例」同理。而一致性检查找的恰恰是「每周 3 次 vs 每周 2 次」
        这种只差数字的矛盾：不设这道闸，模型抄错一个数字的引文就会被定位到另一处，
        凭空凑出「两处矛盾」（单测踩到过）。样本量、疗程、p 值这些数字也正是证据的核心。

        每个起始行取「覆盖率最高、且行数最少」的那个候选窗口；再按覆盖率从高到低贪心挑出
        互不重叠的窗口，避免同一处被相邻的几个起始行重复报出来。

        复杂度是 行数 × MAX_SPAN_LINES 次集合运算；精确匹配命中时根本不会走到这里。
        实测（2026-09）：813 行 / 2 万字的稿件核 147 条判定 0.14s，645 行 / 3.3 万字核 159 条 0.19s
        —— 与几十次模型调用相比可以忽略，不值得为它加索引。
        """
        n = _gram_size(qn)
        q = _grams(qn, n)
        if not q:
            return 0.0, []
        grams = self.gram_lines[n]
        nos = self.line_nos
        digits = _DIGITS_RE.findall(qn)
        #: 全文最高覆盖率（不管数字对不对），只用于 fabricated 判断
        overall = 0.0
        # (覆盖率, 起始下标, 窗口行号)
        candidates: list[tuple[float, int, list[int]]] = []
        for i in range(len(nos)):
            # 窗口必须从一行与引文有交集的行开始：否则「前面垫两行无关内容 + 真正命中的那行」
            # 与单独那一行覆盖率相同，又因为起始行靠前而胜出，位置里就混进了两行不相干的原文
            # （回填时会一起带进草稿）。单测踩到过：命中第 32 行，报出来的是 [30, 31, 32]
            if q.isdisjoint(grams[nos[i]]):
                continue
            acc: set[str] = set()
            best_here, best_lines = 0.0, []
            for span in range(MAX_SPAN_LINES):
                if i + span >= len(nos):
                    break
                acc |= grams[nos[i + span]]
                cov = len(q & acc) / len(q)
                if cov > best_here:  # 严格大于：同分时保留行数更少的窗口
                    best_here, best_lines = cov, nos[i : i + span + 1]
                if cov >= _FULL_COVERAGE:
                    break
            overall = max(overall, best_here)
            if best_here > 0 and self._has_digits(digits, best_lines):
                candidates.append((best_here, i, list(best_lines)))
        if not candidates:
            return overall, []

        best = max(c[0] for c in candidates)
        floor = max(FUZZY_OK, best - FUZZY_TIE)
        picked: list[list[int]] = []
        taken: set[int] = set()
        for cov, _, lines in sorted(candidates, key=lambda c: (-c[0], c[1])):
            if cov < floor or len(picked) >= MAX_POSITIONS:
                break
            if taken.isdisjoint(lines):
                picked.append(lines)
                taken.update(lines)

        return best, sorted(picked)

    def _locate_one(self, quote: str) -> QuoteHit:
        """核对单个片段：太短 → skip；精确 → exact；模糊 → fuzzy；否则 miss / skip（语种不符）。"""
        qn = normalize(quote)
        if len(qn) < MIN_QUOTE_CHARS:
            return QuoteHit(quote, 'skip')

        spans = self._exact(qn)
        if spans:
            return QuoteHit(quote, 'exact', spans, 1.0)
        if len(qn) < MIN_FUZZY_CHARS:
            return QuoteHit(quote, 'miss', coverage=0.0)

        cov, fuzzy_spans = self._fuzzy(qn)
        if fuzzy_spans:
            return QuoteHit(quote, 'fuzzy', fuzzy_spans, round(cov, 3))
        # 稿件里几乎没有这种文字（中文引文 × 纯英文稿）：没找到不代表是编的，只是核不了
        if self._script_absent(script_of(quote)):
            return QuoteHit(quote, 'skip', coverage=round(cov, 3))

        return QuoteHit(quote, 'miss', coverage=round(cov, 3))

    def locate(self, quote: str) -> list[QuoteHit]:
        """核对一段引文，依次尝试：

        1. 整段去找（`_locate_one`）：太短 → skip；精确子串（归一化后比，能跨行）→ exact；
           模糊比对（连续 1–MAX_SPAN_LINES 行的 n-gram 覆盖率 ≥ FUZZY_OK）→ fuzzy；
        2. 整段没找到、而里面有引号时，退到引号里的内容逐个去找 ——
           模型写的是「文题“基于表面肌电图观察针刺”未含随机」这种夹叙夹引时，真正的引文在引号里；
        3. 仍然没有：稿件里几乎没有这种文字 → skip（核不了，不是编的）；否则 → miss。

        :return: 通常一个结果；走到第 2 步时每个引号片段一个结果
        """
        whole = self._locate_one(quote)
        if whole.kind in ('exact', 'fuzzy'):
            return [whole]
        inner = [self._locate_one(q) for q in _QUOTED_RE.findall(quote)]
        found = [h for h in inner if h.kind in ('exact', 'fuzzy')]

        return found or [whole]

    # ------------------------------------------------------------------ 整条

    def ground(self, quotes: str | list[str]) -> GroundResult:
        """核对一条判定的全部引文，给出核对结论与原文位置。

        先把引文拆成若干段（`split_quotes`），每段单独 `locate`，再按下表汇总
        （「可核对」= 不是 skip，即长度够、语种对得上）::

            给的引文          可核对的段    找到的段      located    返回的行号
            ────────         ─────────    ────────     ───────    ────────────────
            没给                —            —          none       []
            给了                0 段         —          ''(NA)     []
            给了                n 段         全部找到     yes        找到的位置
            给了                n 段         部分找到     partial    找到的那几段的位置
            给了                n 段         一段没找到   no         []；另判 fabricated

        行号只来自找到的引文；没找到的那几段一个行号都不贡献。

        :param quotes: 模型给的引文（列表或一段拼接文字都行）
        """
        segments = split_quotes(quotes)
        if not segments:
            return GroundResult(LOCATED_NONE)

        hits = [hit for seg in segments for hit in self.locate(seg)]
        checkable = [h for h in hits if h.kind != 'skip']
        found = [h for h in checkable if h.kind in ('exact', 'fuzzy')]

        if not checkable:
            return GroundResult(LOCATED_NA, [], False, hits)

        lines = sorted({no for h in found for no in h.lines})
        if len(found) == len(checkable):
            return GroundResult(LOCATED_YES, lines, False, hits)
        if found:
            return GroundResult(LOCATED_PARTIAL, lines, False, hits)

        fabricated = all((h.coverage or 0.0) <= FABRICATED_MAX_COVERAGE for h in checkable)

        return GroundResult(LOCATED_NO, [], fabricated, hits)
