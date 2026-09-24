# -*- coding: utf-8 -*-
"""
检索 + 排序 + 覆盖度闸 + Evidence Table（原型）

跑法：python -m tools.lit_retrieve

分词说明：语料 54% 中文，环境里没有 jieba。中文用**字符二元组**、英文用词元，
这是无分词器时中文检索的标准做法，对「便秘」「电针」「上巨虚」这类词命中良好。
"""
from __future__ import annotations

import math
import os
import re
import sys
from collections import Counter, defaultdict

# tools 目录放在 sys.path 末尾。注意：**这解决不了 `common` 的遮蔽**——
# `action-backend/common` 无 __init__.py（PEP 420 命名空间包），`tools/common` 有
# （worker 框架的常规包），而**常规包胜过命名空间包、与路径顺序无关**。
# 所以后端服务不能在 tools 在路径上时做延迟 import，见
# module_action/service/literature_embed_service._arr 上的注释。
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

#: 数据源：有模型抽取结果就用它（生产路径），否则回落助手抽取的那份
_JSONL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lit_out', 'papers.jsonl')
if os.path.exists(_JSONL) and os.path.getsize(_JSONL) > 2000:
    import json

    PAPERS = []
    with open(_JSONL, encoding='utf-8') as _fh:
        for _ln in _fh:
            _ln = _ln.strip()
            if _ln:
                _r = json.loads(_ln)
                if 'error' not in _r:
                    PAPERS.append(_r)
    SOURCE = f'模型抽取 papers.jsonl（{len(PAPERS)} 篇）'
else:
    from lit_out.extracted import PAPERS  # noqa: E402

    SOURCE = f'助手抽取 extracted.py（{len(PAPERS)} 篇）'

CURRENT_YEAR = 2026
#: 覆盖度闸：低于 τ_hard 不生成该段；低于 τ_soft 生成但标低置信
TAU_HARD, TAU_SOFT = 0.08, 0.16
MIN_HITS = 2

# ── 用户输入 ────────────────────────────────────────────────
RESEARCH_TOPIC = '电针治疗慢性功能性便秘的疗效与安全性'

# ── Agent 1：研究问题解析（PICO）。真实系统由 LLM 产出，这里是其输出 ──
PICO = {
    'population': '成人慢性功能性便秘患者',
    'condition': ['慢性功能性便秘', '功能性便秘', '便秘'],
    'intervention': ['电针', '针刺', '针灸'],
    'comparator': ['假针刺', '假电针', '普芦卡必利', '莫沙必利', '乳果糖'],
    'outcomes': ['完全自主排便次数', 'CSBM', '排便次数', '生活质量', 'PAC-QOL', '安全性', '不良反应'],
}

# ── Section Planner：背景五槽位，各带一条子查询 ──
SLOTS = [
    ('S1', '疾病负担与临床重要性', '慢性功能性便秘 患病率 流行病学 疾病负担 生活质量影响'),
    ('S2', '现有疗法及其局限', '功能性便秘 药物治疗 普芦卡必利 莫沙必利 乳果糖 生物反馈 局限 副作用'),
    ('S3', '针刺/电针的既往证据', '电针 针刺 功能性便秘 随机对照 完全自主排便次数 假针刺 疗效'),
    ('S4', '现有证据的不足（研究缺口）', '功能性便秘 针刺 样本量 单中心 随访 假针刺对照 局限 异质性'),
    ('S5', '本研究目的', ''),
]


def tok(text: str) -> list[str]:
    """中文字符二元组 + 英文词元"""
    if not text:
        return []
    t = text.lower()
    out = re.findall(r'[a-z][a-z\-]{2,}|\d{2,}', t)
    cjk = re.findall(r'[一-鿿]+', t)
    for run in cjk:
        out += [run[i:i + 2] for i in range(len(run) - 1)] or [run]
    return out


def doc_text(p: dict) -> str:
    ac = p.get('acupuncture') or {}
    parts = [p.get('title') or '', p.get('abstract') or '', p.get('population') or '',
             ' '.join(p.get('condition') or []), ' '.join(p.get('intervention') or []),
             ' '.join(p.get('comparator') or []), ' '.join(p.get('outcomes') or []),
             ' '.join(p.get('tcm_syndrome') or []), p.get('finding_summary') or '',
             ' '.join(ac.get('points') or []), ac.get('method') or '']
    return ' '.join(parts)


class BM25:
    def __init__(self, docs: list[list[str]], k1=1.5, b=0.75):
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
                if not f:
                    continue
                s += self.idf.get(t, 0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            out.append(s)
        return out


#: 假针刺对照的识别词。**必须按语义识别，不能精确匹配** ——
#: 模型输出的 comparator 是自由描述（「假电针浅刺天枢旁、腹结旁…非经非穴，连接电针仪不通电」），
#: 精确匹配会把 7 篇假针刺对照的研究静默错分到「vs 阳性药」组里，
#: 而 Evidence Table 照样吐出一个看着正常的 INCONSISTENT 判定。踩过一次。
_SHAM = re.compile(r'假针|假电针|安慰|非经非穴|非穴|sham|placebo', re.I)
#: 研究方案的识别。`study_design` 字段不可全信：实测模型把 #540 的 protocol 判成了 rct
_PROTOCOL = re.compile(r'study protocol|研究方案|试验方案|protocol for a', re.I)


def is_sham(comparators: list[str]) -> bool:
    return any(_SHAM.search(str(c)) for c in (comparators or []))


def is_protocol(p: dict) -> bool:
    if p.get('study_design') == 'protocol':
        return True
    return bool(_PROTOCOL.search(f'{p.get("title") or ""} {p.get("abstract") or ""}'))


def is_zh(p: dict) -> bool:
    """按期刊名是否含汉字判中文文献；country 字段模型会写「中国」也会写「China」，不可靠"""
    return bool(re.search(r'[一-鿿]', str(p.get('journal') or '')))


def recency(year: int | None, conf: str) -> float:
    if not year or conf != 'high':
        return 0.0
    return math.exp(-(CURRENT_YEAR - year) / 4)


def main():
    usable = [p for p in PAPERS if not is_protocol(p)]
    dropped_protocol = [p for p in PAPERS if is_protocol(p)]
    docs = [tok(doc_text(p)) for p in usable]
    bm = BM25(docs)

    print('=' * 74)
    print(f'研究方向：{RESEARCH_TOPIC}')
    print(f'数据源：{SOURCE}')
    print('=' * 74)
    print('\n【第1步】研究问题解析（PICO）')
    for k, v in PICO.items():
        print(f'   {k:<12} {v if isinstance(v, str) else " / ".join(v)}')
    print(f'\n   知识库：{len(PAPERS)} 篇（本轮样本）；'
          f'排除研究方案 protocol {len(dropped_protocol)} 篇 → 可用 {len(usable)} 篇')
    for p in dropped_protocol:
        print(f'      · 排除 #{p["id"]} {p["title"][:52]}…（protocol，无结果数据）')

    print('\n【第2步】逐槽位检索 + 覆盖度闸')
    slot_hits: dict[str, list] = {}
    for code, name, q in SLOTS:
        if not q:
            slot_hits[code] = []
            print(f'\n   [{code}] {name}：来自用户输入，不检索')
            continue
        raw = bm.score(tok(q))
        mx = max(raw) or 1.0
        norm = [(usable[i], raw[i] / mx * (max(raw) / 20 if max(raw) < 20 else 1.0)) for i in range(len(usable))]
        # 归一到 0-1：用相对最强命中的比例，再乘以绝对强度因子，避免「全库都不相关但总有个第一名」
        best_abs = max(raw)
        scored = sorted(
            [(usable[i], raw[i] / max(best_abs, 1e-9), raw[i]) for i in range(len(usable))],
            key=lambda x: -x[2])
        # 绝对相关度：BM25 原始分做 sigmoid 压到 0-1，用于覆盖度判定
        rel = [(p, 1 - math.exp(-s / 12), s) for p, r, s in scored]
        top = [x for x in rel if x[2] > 0][:8]
        top1 = top[0][1] if top else 0.0
        hits = len([x for x in top if x[1] >= TAU_HARD])
        status = ('OK' if top1 >= TAU_SOFT and hits >= MIN_HITS
                  else ('LOW' if top1 >= TAU_HARD and hits >= MIN_HITS else 'BLOCKED'))
        slot_hits[code] = [] if status == 'BLOCKED' else top[:6]
        flag = {'OK': '✓ 生成', 'LOW': '△ 生成但标低置信', 'BLOCKED': '✗ 不生成，如实报告覆盖不足'}[status]
        print(f'\n   [{code}] {name}')
        print(f'        最高相关度 {top1:.3f}（τ_soft={TAU_SOFT} τ_hard={TAU_HARD}）· 命中 {hits} 篇 → {flag}')
        for p, r, s in top[:5]:
            yr = p['year'] if p['year'] else '年份未定'
            print(f'          {r:.3f}  #{p["id"]:<4} {str(yr):<9} {p["title"][:56]}')

    print('\n【第3步】核心文献排序（0.65×相关度 + 0.35×近期性，当前年 %d）' % CURRENT_YEAR)
    raw = bm.score(tok(' '.join(PICO['condition'] + PICO['intervention'] + PICO['outcomes'])))
    rows = []
    for i, p in enumerate(usable):
        r = 1 - math.exp(-raw[i] / 12)
        rc = recency(p['year'], p['year_confidence'])
        rows.append((0.65 * r + 0.35 * rc, r, rc, p))
    rows.sort(key=lambda x: -x[0])
    print(f'   {"总分":>6} {"相关":>6} {"近期":>6}  {"年份":<10}{"设计":<7}{"n":>5} {"方向":<14}标题')
    for tot, r, rc, p in rows[:12]:
        yr = str(p['year']) if p['year'] else f'—(低置信)'
        n = p['sample_size'] or '—'
        print(f'   {tot:6.3f} {r:6.3f} {rc:6.3f}  {yr:<10}{p["study_design"]:<7}{str(n):>5} '
              f'{p["effect_direction"]:<14}#{p["id"]} {p["title"][:44]}')

    print('\n【第4步】「近3-5年」窗口')
    for w, label in ((5, '近5年 (2021-2026)'), (3, '近3年 (2023-2026)')):
        inw = [p for p in usable if p['year'] and p['year_confidence'] == 'high' and CURRENT_YEAR - p['year'] <= w]
        topical = [p for p in inw if any('便秘' in c or 'onstipation' in c for c in p['condition'])]
        print(f'   {label}：全库 {len(inw)} 篇，其中便秘相关 {len(topical)} 篇'
              f' → {[("#%d/%s" % (p["id"], p["year"])) for p in topical] or "无"}')
    unknown = [p for p in usable if not p['year'] or p['year_confidence'] != 'high']
    print(f'   年份未定（不参与近期加分、不进推荐位）：{len(unknown)} 篇 '
          f'{[("#%d" % p["id"]) for p in unknown]}')

    print('\n【第5步】Evidence Table（S3 槽位）+ 不一致检测')
    pool = [p for p in usable if any('便秘' in c or 'onstipation' in c.lower() for c in p['condition'])]
    claims = defaultdict(list)
    for p in pool:
        d = p['effect_direction']
        if d == 'unclear':
            claims['C0 效应方向无法判定'].append(p)
        elif is_sham(p['comparator']):
            claims['C1 针刺/电针 vs 假针刺'].append((p, d))
        else:
            claims['C2 针刺/电针 vs 阳性药/常规疗法'].append((p, d))

    for key in ('C1 针刺/电针 vs 假针刺', 'C2 针刺/电针 vs 阳性药/常规疗法'):
        items = claims.get(key, [])
        dirs = Counter(d for _, d in items)
        status = 'INCONSISTENT' if len([k for k in dirs if k in ('positive', 'no_difference', 'negative')]) > 1 else 'CONSISTENT'
        print(f'\n   {key}')
        print(f'      文献 {len(items)} 篇 | 方向分布 {dict(dirs)} | 判定 **{status}**')
        for p, d in items:
            yr = p['year'] or '—'
            print(f'        · #{p["id"]:<4} {str(yr):<6} n={str(p["sample_size"] or "—"):<5} {d:<14} vs {"/".join(p["comparator"])[:22]}')
        if status == 'INCONSISTENT':
            print(f'      → 写作层强制走 mixed-evidence 模板，不许只写阳性结论')
    if claims.get('C0 效应方向无法判定'):
        print(f'\n   C0 效应方向无法判定（不进 Evidence Table，可作背景引用但不可作疗效论据）')
        for p in claims['C0 效应方向无法判定']:
            print(f'        · #{p["id"]} {p["title"][:52]}')

    print('\n【第6步】语料构成披露（本次检索命中的便秘子集）')
    dirs = Counter(p['effect_direction'] for p in pool)
    print(f'   便秘相关 {len(pool)} 篇：阳性 {dirs["positive"]} / 无差异 {dirs["no_difference"]} '
          f'/ 阴性 {dirs["negative"]} / 无法判定 {dirs["unclear"]}')
    print(f'   语种：中文期刊 {len([p for p in pool if is_zh(p)])} 篇 / 英文期刊 {len([p for p in pool if not is_zh(p)])} 篇 · '
          f'国别：{dict(Counter(p["country"] for p in pool))}')
    print(f'   样本量中位数：{sorted([p["sample_size"] for p in pool if p["sample_size"]])[len([p for p in pool if p["sample_size"]]) // 2]}')
    contam = [p for p in PAPERS if p['contamination']]
    print(f'\n   ⚠ 语料质量标记 needs_review：{len(contam)} 篇')
    for p in contam:
        print(f'      · #{p["id"]} {p["contamination_note"][:76]}')


if __name__ == '__main__':
    main()
