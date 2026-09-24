"""
背景生成引擎：研究方向 → 研究背景初稿 + 推荐参考文献

**这里不认识 Redis、不认识 HTTP、不认识业务表**——输入是一个研究方向和一个数据库连接，
输出是一份纯 Python 字典。worker 那层只负责把它接进队列（同 `tools/srd-engine` 与
`tools/checklist_worker_tool/engine` 的分层）。

## 九步

1. PICO 解析                LLM 1 次
2. 逐槽位检索                向量召回 → 重排；向量不可用时退 BM25 并标注降级
3. 覆盖度闸                  分数 + **研究设计**双条件，不合格的槽位如实报告、不生成
4. 核心文献排序              0.65 相关 + 0.35 近期
5. Evidence Table + 不一致检测  代码判定，不靠模型自觉
6. 逐槽位写作                LLM 每槽 1 次，只准引 [n]
7. 编号越界硬拦              正则
8. 引证核验                  LLM 每槽 1 次
9. 参考文献表由代码拼装        模型不参与

## 四道闸缺一不可

模型编造参考文献是这类产品的头号事故，靠提示词说「不要编造」没用：

1. 模型没有机会写引文 —— prompt 里只给编号表
2. 编号越界硬拦 —— **必须认 `[1-8,11]` 这类区间连写**，只认 `\\[(\\d+)\\]` 的话
   越界检查会完全失效（模型写 `[1-99]` 也报 0 处越界）
3. 参考文献表由代码拼装，模型碰不到作者/期刊/年份
4. 引证核验 —— 抓的是最隐蔽的一类：引文真实、数据真实，但**那篇文献不支持这句话**。
   前三道闸对它全部放行

## 覆盖度闸不能只看相关度分数

实测 S1（疾病负担）的候选相关度 0.74–0.83 全部合格，但 12 篇全是干预性 RCT ——
它们只是在**引言里二手引用**了患病率，拿 RCT 当流行病学数据的出处是引用错误。
所以闸有第二个条件：研究设计必须符合该槽位要求。本库没有流行病学文献，
S1 因此永远被拦下并如实报告，**这是正确行为不是缺陷**。
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from typing import Any, Callable

import numpy as np

CURRENT_YEAR_FALLBACK = 2026

#: 覆盖度阈值。**向量余弦与 BM25 压缩分是两个量纲，阈值必须分开** ——
#: 共用一套的表现是「换了检索路径之后，同一个方向忽然从『可写』变成『覆盖不足』」，
#: 而这类偏差看不出来是阈值的问题
TAU = {'vector': (0.30, 0.42), 'bm25': (0.08, 0.16)}
MIN_HITS = 2

#: 槽位对证据类型的要求。这是相关度分数之外的第二道闸
SLOT_DESIGN_REQ: dict[str, set[str]] = {
    'S1': {'sr_meta', 'guideline', 'epidemiology'},
    'S2': {'rct', 'nrct', 'sr_meta'},
    'S3': {'rct', 'nrct', 'sr_meta'},
    'S4': {'rct', 'sr_meta'},
}
SLOT_ORDER = ('S1', 'S2', 'S3', 'S4')

#: 假针刺对照的识别。**必须按语义、且要穷举写法** —— 实测漏过「非效穴浅刺」
#: （只写 `非穴` 匹配不上「非-效-穴」），结果一篇假针刺对照被分进「vs 阳性药」组，
#: 而 Evidence Table 照样吐出一个看着正常的判定
_SHAM = re.compile(r'假针|假电针|假[^,，;；]{0,4}针刺|安慰针|安慰剂针|非经非穴|非效穴|非穴|'
                   r'浅刺非|非治疗穴|旁开非|sham|placebo', re.I)
#: 引用编号。**必须认区间与逗号连写**，理由见模块 docstring 第 2 道闸
_CITE_BLOCK = re.compile(r'\[([\d\s,，\-–~至]+)\]')


def cited_nums(text: str) -> list[int]:
    """从正文里取出全部被引编号，认 [3] / [1,2] / [1-8] / [1-8,11] 各种写法"""
    out: list[int] = []
    for blk in _CITE_BLOCK.findall(text or ''):
        for part in re.split(r'[,，]', blk):
            part = part.strip()
            m = re.fullmatch(r'(\d+)\s*[\-–~至]\s*(\d+)', part)
            if m:
                a, b = int(m.group(1)), int(m.group(2))
                if 0 < a <= b <= a + 60:
                    out += list(range(a, b + 1))
            elif part.isdigit():
                out.append(int(part))

    return out


def jl(raw: Any) -> list:
    if isinstance(raw, list):
        return raw
    try:
        v = json.loads(raw) if raw else []
    except (json.JSONDecodeError, TypeError):
        return []

    return v if isinstance(v, list) else []


# ── 语料 ───────────────────────────────────────────────────────────────
_COLS = ('no title year yconf authors journal lang abstract population condition cgroup '
         'intervention comparator outcomes design n direction finding points method freq '
         'retention sessions weeks contam trunc cstatus acu_system embedding embed_dim embed_model').split()
_SELECT = """select l.corpus_no, l.title, l.year, l.year_confidence, l.authors, l.journal,
                    l.lang, l.abstract, l.population, l.condition, l.condition_group,
                    l.intervention, l.comparator, l.outcomes, l.study_design, l.sample_size,
                    l.effect_direction, l.finding_summary, l.acu_points, l.acu_method,
                    l.acu_frequency, l.acu_retention_min, l.acu_sessions, l.acu_course_weeks,
                    l.contamination, l.truncated, l.clean_status, l.acu_system,
                    l.embedding, l.embed_dim, l.embed_model
             from action_literature l
             where l.status='0' and l.del_flag='0' and l.extract_status='ok'"""


def load_corpus(cur: Any) -> list[dict]:
    """从业务库读语料。**排除 protocol**：研究方案没有结果数据，不能作疗效证据"""
    cur.execute(_SELECT)
    out = []
    for row in cur.fetchall():
        d = dict(zip(_COLS, row))
        for k in ('authors', 'condition', 'cgroup', 'intervention', 'comparator', 'outcomes', 'points'):
            d[k] = jl(d[k])
        if d['design'] != 'protocol':
            out.append(d)

    return out


def doc_text(p: dict) -> str:
    return ' '.join([p['title'] or '', p['abstract'] or '', p['population'] or '',
                     ' '.join(p['condition']), ' '.join(p['cgroup']), ' '.join(p['intervention']),
                     ' '.join(p['comparator']), ' '.join(p['outcomes']), p['finding'] or '',
                     ' '.join(p['points']), p['method'] or ''])


def tok(text: str) -> list[str]:
    """中文字符二元组 + 英文词元。无分词器时中文检索的标准做法"""
    if not text:
        return []
    t = text.lower()
    out = re.findall(r'[a-z][a-z\-]{2,}|\d{2,}', t)
    for run in re.findall(r'[一-鿿]+', t):
        out += [run[i:i + 2] for i in range(len(run) - 1)] or [run]

    return out


class BM25:
    """降级用。实测 P@5 0.730，明显弱于向量的 0.940 —— 只在向量不可用时兜底"""

    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b, self.docs = k1, b, docs
        self.N = len(docs)
        self.avgdl = sum(len(d) for d in docs) / max(self.N, 1)
        self.tf = [Counter(d) for d in docs]
        df: Counter = Counter()
        for d in docs:
            df.update(set(d))
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}

    def score(self, q: list[str]) -> list[float]:
        out = []
        for i, tf in enumerate(self.tf):
            dl, s = len(self.docs[i]), 0.0
            for t in q:
                f = tf.get(t, 0)
                if f:
                    s += self.idf.get(t, 0) * f * (self.k1 + 1) / (
                        f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            out.append(s)

        return out


def rel(raw_score: float) -> float:
    """BM25 原始分压到 0-1，供覆盖度判定与向量余弦共用一套判据形状"""
    return 1 - math.exp(-raw_score / 12)


def recency(p: dict, current_year: int) -> float:
    """近期性。**年份不可信的一律为 0** —— 不猜，也不让它蹭到近期加分"""
    if not p['year'] or p['yconf'] != 'high':
        return 0.0

    return math.exp(-(current_year - p['year']) / 4)


def cite_of(p: dict) -> str:
    """
    参考文献条目。**由代码拼装，模型碰不到** —— 这是第三道闸。

    **`title` 装的是原文题名，不是英文题名**（中文文献即中文题名）。甲方给的
    `目录.xlsx` 全是英文译名，早先直接拿它当题名存，结果 296 篇中文文献的引文成了
    「中文作者 + 英文题名 + 中文刊名」—— 那不是任何一种引用格式，读者据此既检索不到
    原文、投稿时也引不了。译过的题名就不再是引用信息了（同 `action_srd_item.cite_*`
    「原文引用保持原语言」）。英文题名另存 `title_en`，这里不用。

    「等 / et al.」跟着**这条文献自己的语言**走，不跟界面语言走：中文期刊的参考文献表里，
    中文文献用「等」、外文文献用「et al.」，这是排版惯例。
    """
    a = p['authors']
    en = p.get('lang') == 'en'
    first = str(a[0]) if a else '—'
    # `et al` 不带句点：后面紧跟的 `. ` 会把它补上，写 `et al.` 会得到 `et al..`
    etal = (', et al' if en else ', 等') if len(a) > 1 else ''
    journal = p['journal'] or ('Journal unknown' if en else '期刊待核')
    year = p['year'] or ('n.d.' if en else '年份待核')

    return f'{first}{etal}. {p["title"]}. {journal}. {year}.'


def ref_warnings(p: dict) -> list[str]:
    """这条文献的质量标记。**要跟着引文一起显示** —— 用户据此决定要不要核原文"""
    warn = []
    if p['yconf'] != 'high':
        warn.append('year')
    if p['trunc'] == '1':
        warn.append('truncated')
    if p['contam'] == '1' and p['cstatus'] not in ('ok', 'na'):
        warn.append('contaminated')

    return warn
