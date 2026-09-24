"""
穴位编码归一与体系判定（纯函数，只用标准库）

被 `tools/lit_ingest.py`（入库时归一）与讨论生成（判定两项研究取穴是否可比）共用。

**只用标准库、不 import 本项目任何模块**：`tools/` 下的脚本会把 tools 目录放进
`sys.path`，而 `tools/common` 是常规包、`action-backend/common` 是命名空间包 ——
常规包胜过命名空间包且与顺序无关，所以但凡这里牵出一条通向 `common` 的 import 链，
`tools/lit_ingest.py` 就会炸在 `No module named 'common.vo'`。见
`literature_embed_service._arr` 上的注释。

## 为什么要归一

实测全库 679 种穴位写法、3513 次出现，其中：

- 标准国际代码 234 种 / 2834 次（81%）
- **EX 系丢了连字符** 29 种 / 161 次（`EXHN3` 查不到，标准写法是 `EX-HN3`）
- **别名代码** 34 种 / 65 次（`DU20` 与 `GV20` 是同一个百会）
- 非代码（中文名、耳穴、解剖点等）382 种 / 453 次

不归一的后果：同一个穴位算成两个，穴位共现网络与「两项研究取穴是否相同」的判断都会错。
而后者正是讨论生成解释「为什么我的结果与文献不一致」的主要依据。

## 为什么要判体系

`#482` 用的是蒙医的「顶会穴/赫依穴/心穴」，`#205` 用的是长圆针的解剖定位点
（「合阳次/成骨次/阳陵次」），`#142` 用的是耳针的 `Cingulate Gyrus/OMEGA2`。
这些与十四经穴**不在同一个坐标系里**，硬比会得出「取穴完全不同」这种既正确又无用的结论。
正确的说法是「两项研究使用了不同的穴位体系，取穴不具可比性」。

**耳穴的 `CO`/`TF`/`AT`/`AH`/`HX`/`TG` 不是经脉别名**（`CO` 是耳甲，不是任脉）——
实测它们只出现在耳针论文里，且与 `TG2p`/`AH6a` 这类明确的 ISO 耳穴编码同现。
把 `CO` 映射成 `CV` 会是一个真实的错误。
"""

from __future__ import annotations

import re

#: 十四经的标准国际代码前缀（WHO 标准经穴命名）
MERIDIAN_PREFIX = ('LU', 'LI', 'ST', 'SP', 'HT', 'SI', 'BL', 'KI', 'PC', 'TE', 'GB', 'LR', 'CV', 'GV')
#: 经外奇穴的部位码
EX_PART = ('HN', 'CA', 'B', 'UE', 'LE')
#: 别名 → 标准码。**只收真正的经脉别名**：DU=督脉、REN/RN=任脉、SJ/TB/TH=三焦、
#: P=心包、H=心、LIV/LV=肝、K=肾、UB=膀胱。
#: 刻意不含 CO/TF/AT/AH/HX/TG —— 那些是耳穴分区码，映射过去就是错的
ALIAS = {
    'DU': 'GV', 'REN': 'CV', 'RN': 'CV', 'CO NCEPTION': 'CV',
    'SJ': 'TE', 'TB': 'TE', 'TH': 'TE', 'SAN JIAO': 'TE',
    'P': 'PC', 'H': 'HT', 'LIV': 'LR', 'LV': 'LR', 'K': 'KI', 'UB': 'BL',
}
#: 耳穴分区码（WHO/ISO 耳穴命名法）：HX 耳轮 · SF 耳舟 · AH 对耳轮 · TF 三角窝 ·
#: TG 耳屏 · AT 对耳屏 · CO 耳甲 · LO 耳垂 · P 耳背（这里不收 P，与心包经冲突）
AURICULAR_PREFIX = ('HX', 'SF', 'AH', 'TF', 'TG', 'AT', 'CO', 'LO')
#: 头针标准线（WHO 头皮针命名）
SCALP_PREFIX = ('MS',)

_STD_RE = re.compile(rf'^({"|".join(MERIDIAN_PREFIX)})(\d{{1,3}})$')
_EX_RE = re.compile(rf'^EX-?({"|".join(EX_PART)})(\d{{1,3}})$')
_ALIAS_RE = re.compile(rf'^({"|".join(sorted(ALIAS, key=len, reverse=True))})(\d{{1,3}})$')
_AUR_RE = re.compile(rf'^({"|".join(AURICULAR_PREFIX)})(\d{{1,3}}[a-z]?)$', re.I)
_SCALP_RE = re.compile(rf'^({"|".join(SCALP_PREFIX)})(\d{{1,3}})$', re.I)

#: 常见穴位中文名 → 标准码。实测模型会把上巨虚编成 ST39（那是下巨虚），
#: 也常常直接写中文名，这张表把两种情况一起收口
ZH_TO_CODE = {
    '上巨虚': 'ST37', '下巨虚': 'ST39', '足三里': 'ST36', '天枢': 'ST25', '犊鼻': 'ST35',
    '梁丘': 'ST34', '滑肉门': 'ST24', '外陵': 'ST26', '丰隆': 'ST40', '地仓': 'ST4',
    '腹结': 'SP14', '大横': 'SP15', '三阴交': 'SP6', '阴陵泉': 'SP9', '血海': 'SP10', '公孙': 'SP4',
    '百会': 'GV20', '印堂': 'EX-HN3', '神庭': 'GV24', '大椎': 'GV14', '水沟': 'GV26',
    '人中': 'GV26', '素髎': 'GV25', '哑门': 'GV15',
    '中脘': 'CV12', '下脘': 'CV10', '气海': 'CV6', '关元': 'CV4', '膻中': 'CV17',
    '中极': 'CV3', '廉泉': 'CV23', '天突': 'CV22',
    '内关': 'PC6', '间使': 'PC5', '大陵': 'PC7', '中冲': 'PC9', '劳宫': 'PC8',
    '太冲': 'LR3', '行间': 'LR2', '章门': 'LR13', '曲泉': 'LR8',
    '合谷': 'LI4', '曲池': 'LI11', '迎香': 'LI20', '手三里': 'LI10',
    '支沟': 'TE6', '外关': 'TE5', '中渚': 'TE3', '翳风': 'TE17',
    '大肠俞': 'BL25', '肾俞': 'BL23', '脾俞': 'BL20', '心俞': 'BL15', '三焦俞': 'BL22',
    '肝俞': 'BL18', '膈俞': 'BL17', '肺俞': 'BL13', '厥阴俞': 'BL14', '胃俞': 'BL21',
    '承山': 'BL57', '委中': 'BL40', '次髎': 'BL32', '中髎': 'BL33', '睛明': 'BL1',
    '申脉': 'BL62', '昆仑': 'BL60',
    '环跳': 'GB30', '风池': 'GB20', '悬钟': 'GB39', '阳陵泉': 'GB34', '本神': 'GB13',
    '率谷': 'GB8', '足临泣': 'GB41', '头临泣': 'GB15',
    '神门': 'HT7', '通里': 'HT5', '阴郄': 'HT6', '极泉': 'HT1',
    '太溪': 'KI3', '照海': 'KI6', '复溜': 'KI7', '涌泉': 'KI1',
    '尺泽': 'LU5', '列缺': 'LU7',
    '太阳': 'EX-HN5', '四神聪': 'EX-HN1', '安眠': 'EX-HN22', '球后': 'EX-HN7',
    '夹脊': 'EX-B2', '夹脊穴': 'EX-B2', '华佗夹脊': 'EX-B2', '八风': 'EX-LE10', '八邪': 'EX-UE9',
    '子宫': 'EX-CA1', '鹤顶': 'EX-LE2', '金津': 'EX-HN12', '玉液': 'EX-HN13',
    '内膝眼': 'EX-LE4', '膝眼': 'EX-LE5', '胆囊': 'EX-LE6', '阑尾': 'EX-LE7',
    '上睛明': 'EX-HN', '定喘': 'EX-B1', '腰眼': 'EX-B7', '十七椎': 'EX-B8',
    '牵正': 'EX-HN', '翳明': 'EX-HN14', '上迎香': 'EX-HN8', '鱼腰': 'EX-HN4',
    '印堂穴': 'EX-HN3', '四神聪穴': 'EX-HN1',
}

#: 头针的分区/线命名（焦氏头针与 WHO 标准头穴线）。这类名字里的「区/线/带」是体系标志，
#: 但不能光看这三个字 —— 「顶会穴」「言语一区」都含不了这个规则，所以按首词白名单匹配
_SCALP_HEAD = (
    '顶颞', '额中', '额旁', '颞前', '颞后', '枕上', '枕下', '顶中', '顶旁',
    '运动区', '感觉区', '舞蹈', '震颤', '晕听', '言语', '足运感', '视区', '平衡区',
    '血管舒缩', '生殖区', '胃区', '胸腔区', '晕区', '眩晕区', '供血', '宁神', '乳突',
)

#: 明确属于非经穴体系的中文/英文名（判体系用，不做代码映射）
_AURICULAR_ZH = ('耳穴', '耳神门', '耳零点', '交感', '皮质下', '内分泌', '耳尖')
_AURICULAR_EN = ('shen men', 'shenmen', 'point zero', 'omega', 'cingulate', 'thalamus',
                 'hypothalamus', 'auricular', 'ear ')
_SCALP_ZH = ('三针', '头针', '舌三针', '颞三针', '四神针', '智三针', '定神针')
_ASHI = ('阿是', '压痛点', 'ashi', '筋结', '结筋')


def normalize_point(raw: str) -> str:
    """
    单个穴位归一到标准写法。**认不出来的原样返回，绝不猜**

    :param raw: 原始写法
    :return: 标准码或原样字符串
    """
    s = str(raw or '').strip()
    if not s:
        return ''
    # 中文名优先（可能带括号注释，如「BL17（膈俞）」先剥壳）
    core = re.sub(r'[（(].*?[)）]', '', s).strip()
    if core in ZH_TO_CODE:
        return ZH_TO_CODE[core]
    zh = re.sub(r'[A-Za-z0-9\-\s（）()]', '', s).strip()
    if zh and zh in ZH_TO_CODE:
        return ZH_TO_CODE[zh]

    up = re.sub(r'\s+', '', core).upper()
    m = _STD_RE.match(up)
    if m:
        return f'{m.group(1)}{int(m.group(2))}'
    m = _EX_RE.match(up)
    if m:
        # EX 系必须带连字符：EXHN3 不是标准写法，查不到
        return f'EX-{m.group(1)}{int(m.group(2))}'
    m = _AUR_RE.match(up)
    if m:
        # 耳穴：前缀统一大写，但**后缀字母必须保持小写** —— ISO 耳穴命名里
        # `AH6a` / `AH6b` 是对耳轮上脚的两个不同分区，大写成 AH6A 就不是标准写法了。
        # 所以从原串（而非已 upper 的 up）里取后缀
        raw_core = re.sub(r'\s+', '', core)
        suffix = raw_core[len(m.group(1)):]
        return f'{m.group(1).upper()}{suffix}'
    m = _SCALP_RE.match(up)
    if m:
        return f'{m.group(1).upper()}{int(m.group(2))}'
    m = _ALIAS_RE.match(up)
    if m:
        return f'{ALIAS[m.group(1)]}{int(m.group(2))}'

    return s


def normalize_points(raw: list | None) -> list[str]:
    """整份取穴归一并去重，保持原顺序（取穴顺序在部分流派里有含义）"""
    out, seen = [], set()
    for x in raw or []:
        v = normalize_point(x)
        if v and v not in seen:
            seen.add(v)
            out.append(v)

    return out


#: 耳穴的中文名。**单字脏器名（肝/肾/脾/心/肺）光看名字判不了** ——
#: 它既可能是耳穴分区，也可能是「肝俞」之类的简写。所以这些只在 `method`
#: 明确是耳针时才认，见 `point_system` 的 `method` 参数
_AURICULAR_AMBIG = ('肝', '肾', '脾', '心', '肺', '胃', '大肠', '小肠', '膀胱', '胆',
                    '子宫', '卵巢', '内分泌', '皮质下', '丘脑', '额', '颞', '枕', '缘中')
_METHOD_AURICULAR = ('耳针', '耳穴', '耳压', '耳廓', 'auricular', 'ear')
_METHOD_SCALP = ('头针', '头皮针', 'scalp')


def point_system(point: str, method: str = '') -> str:
    """
    单个穴位属于哪个体系

    :param point: 归一后的穴位
    :param method: 该研究的针法（`acu_method`）。**单字脏器名必须靠它才判得了** ——
        「肝」既可能是耳穴分区也可能是肝俞的简写，光看名字无解；给了针法就有解。
        不传则这类名字落到 other，宁可保守。
    :return: meridian / auricular / scalp / ashi / other
    """
    s = str(point or '').strip()
    if not s:
        return 'other'
    up = s.upper()
    if _STD_RE.match(up) or _EX_RE.match(up.replace('-', '')) or up.startswith('EX-'):
        return 'meridian'
    if _AUR_RE.match(up):
        return 'auricular'
    if _SCALP_RE.match(up):
        return 'scalp'
    low, m = s.lower(), (method or '').lower()
    if any(k in s for k in _AURICULAR_ZH) or any(k in low for k in _AURICULAR_EN):
        return 'auricular'
    if any(k in s for k in _SCALP_ZH) or s.startswith(_SCALP_HEAD):
        return 'scalp'
    if any(k in s for k in _ASHI) or any(k in low for k in _ASHI):
        return 'ashi'
    # 针法给了才敢认的两类
    if any(k in m for k in _METHOD_AURICULAR) and s in _AURICULAR_AMBIG:
        return 'auricular'
    if any(k in m for k in _METHOD_SCALP) and re.search(r'[区线带]$', s):
        return 'scalp'

    return 'other'


def classify_system(points: list | None, method: str = '') -> str:
    """
    整份取穴属于哪个体系，供讨论生成判断两项研究「取穴是否可比」。

    **`mixed` 不是「没判出来」，是真实存在的一档**：实测 #536 同时用了经穴
    （PC6/ST36/GV20）与耳穴（CO4/TF4/AH6a）。把它归进任一单一体系都会误导比较。

    `ashi` 单独一档而不并进 meridian：阿是穴是「按压痛点取穴」，位置因人而异，
    两项都用阿是穴不代表取穴相同。

    :param points: 归一后的取穴列表
    :param method: 该研究的针法，用于消解单字脏器名等歧义
    :return: meridian / auricular / scalp / ashi / other / mixed / ''（无取穴）
    """
    kinds = [point_system(p, method) for p in (points or []) if str(p).strip()]
    if not kinds:
        return ''
    # 阿是穴常与经穴同用（「循经取穴 + 阿是穴」），不因为多了它就判成 mixed
    core = [k for k in kinds if k != 'ashi']
    if not core:
        return 'ashi'
    uniq = set(core)
    if len(uniq) == 1:
        return next(iter(uniq))
    # **少量 other 不足以判 mixed**：other 里混着「我这张表没收录的穴名」，
    # 把「29 个经穴 + 1 个不认识的名字」判成 mixed 会让它在讨论生成里被判定为
    # 「与其它研究取穴不可比」——而那是错的，代价是丢掉一条本可用的比较。
    # 所以只有当非 other 的体系本身就多于一种、或 other 占比过半时才判 mixed。
    named = [k for k in core if k != 'other']
    if len(set(named)) > 1:
        return 'mixed'
    if named and len(named) >= len(core) * 0.5:
        return named[0]

    return 'mixed' if named else 'other'


def comparable(a: list | None, b: list | None) -> bool:
    """
    两项研究的取穴是否具有可比性（同一体系才谈得上「取穴异同」）

    :return: 同体系且都有取穴时为 True
    """
    sa, sb = classify_system(a), classify_system(b)

    return bool(sa) and sa == sb and sa != 'mixed'
