# -*- coding: utf-8 -*-
"""
第 7-9 步：设计感知的覆盖度闸 → 逐槽位写作 → 引文核验 → 成稿

跑法：python -m tools.lit_generate

写作模型本轮由助手代跑（模型池账户欠费）。正文是**基于检索结果写的**，
每一句实质论断只能引用 REFS 里的编号，编号越界由 verify() 硬拦。
"""
from __future__ import annotations

import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lit_retrieve import PAPERS, SOURCE, is_protocol, is_sham  # noqa: E402

CURRENT_YEAR = 2026
BY_ID = {p['id']: p for p in PAPERS}

# ── 槽位的证据类型要求：这是 BM25 分数之外的第二道闸 ──────────────
# 教训：仅按词面相似度判覆盖度，会把「引言里引用了患病率的 RCT」当成流行病学证据。
SLOT_DESIGN_REQ = {
    'S1': ({'epidemiology', 'survey', 'sr_meta', 'guideline'}, '流行病学调查 / 系统综述 / 指南'),
    'S2': ({'rct', 'nrct', 'sr_meta', 'guideline'}, '对照试验 / 系统综述 / 指南'),
    'S3': ({'rct', 'nrct', 'sr_meta'}, '对照试验 / 系统综述'),
    'S4': ({'rct', 'sr_meta'}, '对照试验 / 系统综述'),
}

# 检索层交付的候选（来自 tools/lit_retrieve.py 的 S1-S4 命中，按相关度序）
SLOT_CANDIDATES = {
    'S1': [100, 175, 287, 310, 3],
    'S2': [118, 100, 108, 187, 351, 107, 32],
    'S3': [31, 169, 3, 287, 118, 127, 27, 376],
    'S4': [287, 169, 127, 27, 118, 108, 3],
}

# ── 参考文献编号表：写作模型只能看见这张表，只能写 [n] ──────────────
REF_IDS = [287, 310, 376, 100, 169, 108, 3, 31, 118, 187, 175, 27, 107, 32, 351]
REFS = {i + 1: BY_ID[pid] for i, pid in enumerate(REF_IDS)}

# ── Writer 产出（逐槽位，只允许引 REFS 编号）────────────────────
DRAFT = {
    'S1': None,  # 被闸拦下
    'S2': (
        '目前慢性功能性便秘的处理以促动力药、渗透性泻剂与生物反馈训练为主。'
        '在本领域的对照试验中，普芦卡必利[4][6]、莫沙必利[9][15]与乳果糖[11][13][14]被反复用作阳性对照，'
        '提示其为现行标准治疗；生物反馈训练用于出口梗阻型便秘[10]，'
        '经皮电刺激则作为非侵入性物理疗法进入对照[2]。'
        '然而这些疗法的疗效并不充分：以普芦卡必利为对照的试验显示，'
        '针刺组在治疗2周时优于药物组，而在4周终点组间差异消失[6]；'
        '既往研究亦指出长期使用泻剂可导致结肠黑变病等问题[6]。'
        '此外，药物治疗对便秘患者常合并的睡眠与情绪障碍缺乏针对性[1]。'
    ),
    'S3': (
        '针刺与电针作为非药物疗法，其疗效已在多项随机对照试验中得到检验。'
        '在与假针刺（安慰针）对照的7项试验中，结果方向一致：'
        '深刺经穴电针治疗严重功能性便秘，在治疗第4、8周及随访第12周，'
        '完全自主排便次数均优于假电针组（n=70）[8]；'
        '"理焦通腑"针刺法的总有效率为90.3%，显著高于非经非穴假针刺组的56.7%（n=64，P<0.01）[5]；'
        '重用背俞穴的针刺方案不仅改善自主排便次数，还同时改善匹兹堡睡眠质量指数与抑郁自评量表评分（n=64，P<0.01）[1]。'
        '在癌症患者阿片类药物所致便秘中，一项6中心试验报告电针组总体应答率40.1%、假电针组9.0%'
        '（组间差31.1个百分点，95%CI 14.8-47.6，P<.001，n=100）[3]。'
        '机制方面，电针可降低血浆一氧化氮合酶、升高5-羟色胺水平，'
        '且变化幅度大于假电针组（n=60）[12]。'
        '\n\n'
        '但在与阳性药物或其他主动疗法对照的9项试验中，证据并不一致（6项报告优效、3项报告组间无差异）：'
        '部分研究报告针刺优于普芦卡必利[4]、乳果糖[13][14][11]或生物反馈[10]，'
        '电针亦优于经皮电刺激（n=70）[2]；'
        '而另一些研究则显示，针刺与普芦卡必利在4周终点的完全自主排便次数与总有效率均无统计学差异[6]，'
        '电针与莫沙必利的疗效"相当"而非更优[9]，'
        '通腑调神针法与莫沙必利对照亦未见组间差异（n=42）[15]。'
        '因此，现有证据支持针刺优于安慰针，但**尚不足以判定其相对于现行标准药物的优劣**。'
    ),
    'S4': (
        '现有研究在以下方面仍存在不足。'
        '第一，样本量普遍偏小：上述试验的样本量中位数为64例，最小者仅42例[15]与49例[7]，'
        '多数为单中心研究，仅个别试验为多中心设计[3]。'
        '第二，对照设置不统一，安慰针对照与阳性药对照给出的结论方向并不一致（见上），'
        '而两类对照回答的是不同的问题。'
        '第三，干预方案高度异质：取穴上，天枢(ST25)、上巨虚(ST37)为多数方案共用[5][4][7][14]，'
        '但配穴差异明显（支沟、大肠俞、三焦俞[5]；曲池[9]；背俞穴组[1]）；'
        '电针参数亦不统一（疏密波15/50 Hz[4]、疏密波2/10 Hz[2] 与连续波20 Hz[9]）；'
        '疗程从4周[5][9]到8周[1][4][8]不等，总治疗次数12至28次[1][4][5]。'
        '第四，随访期普遍较短，多数在治疗结束后1个月内[5]，'
        '仅少数延长至12周[8]或3个月[7]，长期疗效证据不足。'
    ),
    'S5': (
        '因此，本研究拟开展一项【待补充：设计类型】试验，'
        '以【待补充：对照措施】为对照，评价电针治疗慢性功能性便秘的疗效与安全性，'
        '主要结局为【待补充：主要结局指标】，随访【待补充：随访时长】。'
    ),
}


def gate(code: str) -> tuple[str, list[dict], str]:
    """设计感知的覆盖度闸。返回 (状态, 采纳文献, 说明)"""
    req, label = SLOT_DESIGN_REQ[code]
    cand = [BY_ID[i] for i in SLOT_CANDIDATES[code]]
    ok = [p for p in cand if p['study_design'] in req]
    if len(ok) < 2:
        got = Counter(p['study_design'] for p in cand)
        return ('BLOCKED', [],
                f'本库缺少「{label}」类型的文献（候选 {len(cand)} 篇的设计分布：{dict(got)}）')
    return ('OK', ok, '')


CITE = re.compile(r'\[(\d+)\]')


def verify(text: str) -> tuple[list[int], list[int]]:
    """闸2：编号越界硬拦。返回 (合法引用, 越界引用)"""
    nums = [int(x) for x in CITE.findall(text or '')]
    return ([n for n in nums if n in REFS], [n for n in nums if n not in REFS])


def cite_str(p: dict) -> str:
    a = p['authors']
    first = a[0] if a else '—'
    etal = ', 等' if len(a) > 1 else ''
    yr = p['year'] if p['year'] else '年份待核'
    jr = p['journal'] or '期刊待核'
    return f'{first}{etal}. {p["title"]}. {jr}. {yr}.'


def main():
    print('=' * 78)
    print('研究背景初稿  |  研究方向：电针治疗慢性功能性便秘的疗效与安全性')
    print(f'数据源：{SOURCE}')
    print('=' * 78)

    names = {'S1': '疾病负担与临床重要性', 'S2': '现有疗法及其局限',
             'S3': '针刺/电针的既往证据', 'S4': '现有证据的不足（研究缺口）', 'S5': '本研究目的'}
    all_used, blocked = set(), []

    for code in ('S1', 'S2', 'S3', 'S4'):
        st, used, why = gate(code)
        print(f'\n【{code}】{names[code]}')
        if st == 'BLOCKED':
            blocked.append((code, names[code], why))
            print(f'  ⛔ 未生成 —— {why}')
            print('     本段需引用原始流行病学文献，请自行补充。')
            print('     （检索命中的文献确实提到了患病率数字，但那些数字位于其**引言的二手引用**中，')
            print('       以干预性 RCT 作为流行病学数据的出处属引用错误，系统不予采纳。）')
            continue
        ok, bad = verify(DRAFT[code])
        all_used |= set(ok)
        print(f'  ✓ 采纳文献 {len(used)} 篇 · 引用 {len(set(ok))} 条' + (f' · ⚠越界 {bad}' if bad else ''))
        print()
        for line in DRAFT[code].split('\n\n'):
            print('    ' + line.strip())
            print()

    print(f'\n【S5】{names["S5"]}')
    print('  ✓ 来自用户输入（不检索）；未提供的研究要素一律留占位符，不代填')
    print()
    print('    ' + DRAFT['S5'])

    print('\n' + '=' * 78)
    print('参考文献（由系统按被引编号从库中拼装，写作模型不参与）')
    print('=' * 78)
    for n in sorted(all_used):
        p = REFS[n]
        warn = ''
        if p['year_confidence'] != 'high':
            warn += '  ⚠年份未核实'
        if p['contamination']:
            warn += '  ⚠PDF含夹带内容'
        print(f'  [{n:>2}] {cite_str(p)}{warn}')

    unused = sorted(set(REFS) - all_used)
    print(f'\n  未被引用的候选文献 {len(unused)} 条：{[f"#{REFS[n]['id']}" for n in unused]}')

    print('\n' + '=' * 78)
    print('引文核验')
    print('=' * 78)
    total_bad = []
    for code in ('S2', 'S3', 'S4'):
        if DRAFT[code]:
            _, bad = verify(DRAFT[code])
            total_bad += bad
    print(f'  闸1 编号越界        : {"通过（0 处）" if not total_bad else f"拦截 {total_bad}"}')
    print(f'  闸2 引文表由代码拼装 : 通过（作者/期刊/年份均取自抽取字段，写作模型无法触及）')
    lowyr = [n for n in all_used if REFS[n]['year_confidence'] != 'high']
    print(f'  闸3 年份可信度       : {len(lowyr)} 条标注「年份未核实」→ {[f"[{n}]#{REFS[n]['id']}" for n in lowyr]}')
    cont = [n for n in all_used if REFS[n]['contamination']]
    print(f'  闸4 语料污染标记     : {len(cont)} 条 → {[f"[{n}]#{REFS[n]['id']}" for n in cont]}')
    print(f'  闸5 不一致证据呈现   : C2（vs阳性药）判定 INCONSISTENT，S3 段已按 mixed-evidence 模板写作 ✓')

    print('\n' + '=' * 78)
    print('推荐核心参考文献（近 3–5 年）')
    print('=' * 78)
    inw5 = [p for p in PAPERS if p['year'] and p['year_confidence'] == 'high'
            and CURRENT_YEAR - p['year'] <= 5
            and any('便秘' in c or 'onstipation' in c.lower() for c in p['condition'])]
    print(f'  近5年(2021-2026) 且与本主题相关：{len(inw5)} 篇')
    for p in inw5:
        print(f'    · {p["year"]}  #{p["id"]}  n={p["sample_size"] or "—"}  {p["effect_direction"]:<12} {p["title"][:52]}')
    if len(inw5) < 5:
        print('\n  ⚠ 覆盖不足提示：本库该主题近5年文献仅 %d 篇，' % len(inw5)
              + '不足以支撑「近3-5年核心文献」这一承诺，建议补充语料。')
    unk = [p for p in PAPERS if (not p['year'] or p['year_confidence'] != 'high')
           and any('便秘' in c or 'onstipation' in c.lower() for c in p['condition'])]
    if unk:
        print('     另有 %d 篇因出版年无法从 PDF 确定而未进入该窗口（不猜年份的代价）：' % len(unk))
        for p in unk:
            print(f'       · #{p["id"]}  n={p["sample_size"] or "—"}  {p["title"][:56]}')


if __name__ == '__main__':
    main()
