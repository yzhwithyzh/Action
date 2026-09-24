"""
针灸文献知识库全量入库：567 篇 PDF → `action_literature` / `action_literature_text`

跑法（工作目录 action-backend/）::

    set LLM_BASE_URL=... & set LLM_MODEL=... & set LLM_KEY=...
    python -m tools.lit_ingest                # 全量，已入库的自动跳过
    python -m tools.lit_ingest --ids 1,2,3    # 只跑指定编号
    python -m tools.lit_ingest --force        # 重抽已入库的

## 三条硬约束（都是实测踩出来的，别删）

1. **NFKC 规范化必须在送模型之前**：99% 的中文文献是全角（``４０例``、``（Ｐ＜０．０５）``）。
2. **`目录.xlsx` 的标题当权威锚放进 prompt**：实测 8/24 篇 PDF 夹带了另一篇论文的正文
   或参考文献（#100 夹带儿童脓毒症的整份参考文献、#118 夹带一篇面瘫论文）。没有锚，
   模型会把夹带内容当成本文来抽。
3. **year 必须给 year_evidence**：首两页平均出现 4 个不同年份（参考文献年、基金年、
   收稿年、作者出生年），不要依据模型会挑一个且从不说自己在猜。

## 断点续跑

按 `corpus_no` 的唯一索引判断，已有记录默认跳过。567 篇一趟 40 分钟，
中途断了直接重跑同一条命令即可。**失败的那些也落库**（`extract_status='failed'`），
不落的话下次重跑会以为没跑过，而真正的失败原因（模型返回什么）就丢了。

## 归一化：模型自由输出的字段要收口

实测教训：模型把 comparator 写成「假电针浅刺天枢旁、腹结旁、上巨虚旁非经非穴，连接电针仪不通电」
这种自由描述，下游按它分组会**静默错分**（7 篇假针刺对照被分进「vs 阳性药」组，
而 Evidence Table 照样吐出一个看着正常的判定）。所以入库前统一收口，见 `_norm_comparator`。
穴位代码同理：实测模型把上巨虚编成 ST39（应为 ST37，ST39 是下巨虚），按对照表校正。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime

import fitz
import httpx
import psycopg2
from openpyxl import load_workbook
from psycopg2.extras import execute_batch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from module_action.service.acupoint_norm import classify_system, normalize_points  # noqa: E402

CORPUS = r'E:\code\广中医Action\567编号版'
MAX_CHARS = 30000
CONCURRENCY = 10
DB = dict(host='127.0.0.1', port=5432, user='postgres', password='123456', dbname='action')

SCHEMA_PROMPT = """你是针刺临床研究文献的元数据抽取器。下面给你一篇论文的正文（已做全角→半角规范化）。

这篇论文的权威标题是：
《{title}》

严格按这个标题判断哪些内容属于本文。**正文里很可能夹带其他论文的片段**（期刊 PDF 跨页所致，
实测发生率约 30%），遇到与该标题无关的内容一律忽略，并在 contamination 里说明。

只输出一个 JSON 对象，不要解释、不要 markdown 围栏。字段如下：

{{
  "year": 出版年(整数)或null,
  "year_evidence": "你判断出版年所依据的正文原文片段(原样照抄，30字以内)",
  "year_confidence": "high" 或 "low",
  "authors": ["作者姓名", ...],
  "journal": "期刊名（用正文中出现的原文名，中文刊用中文名）"或null,
  "country": "国家（统一用中文，如：中国、美国、韩国）"或null,
  "lang": "zh" 或 "en"（本文正文的主要语言）,
  "abstract": "摘要全文(有就照抄，没有就从正文提炼2-4句)",
  "population": "研究对象的具体描述(含年龄/病程等限定)"或null,
  "condition": ["病种"],
  "intervention": ["干预措施"],
  "comparator": ["对照措施"],
  "outcomes": ["结局指标"],
  "tcm_syndrome": ["中医证候"],
  "study_design": "rct|nrct|animal|sr_meta|case_series|protocol|other",
  "sample_size": 总样本量(整数)或null,
  "effect_direction": "positive|negative|no_difference|unclear",
  "finding_summary": "主要结果的一句话概括，含关键数据",
  "acupuncture": {{
    "points": ["穴位，用国际代码如 ST25、SP14、GV20；上巨虚是ST37不是ST39"],
    "meridian": ["经络"],
    "method": "针法(毫针/电针/温针/火针/耳针/头针/腹针/皮内针/针刀等)"或null,
    "frequency": "电针频率"或null,
    "deqi": true/false/null,
    "retention_min": 留针分钟数(整数)或null,
    "sessions": 总治疗次数(整数)或null,
    "course_weeks": 疗程周数(整数)或null
  }},
  "contamination": true/false,
  "contamination_note": "夹带内容的说明"或null
}}

七条硬约束：
1. **抽不到就填 null 或空数组，绝不推断、绝不编造。** 尤其 sample_size 和针灸参数，
   编一个"n=60""留针30分钟"看着完全正常，是最隐蔽的错误。
2. **year 必须有 year_evidence 支撑。** 正文里通常有多个年份（参考文献年、基金年、
   收稿年、作者出生年）。找不到能确定出版年的依据时，year_confidence 填 "low"、year 填 null。
3. **effect_direction 按主要结局判，不按摘要的结论句判。** 摘要常写"疗效显著"而数据是
   终点组间无差异（P>0.05）——这种一律填 no_difference。主要结局阴性、次要结局阳性的，
   也填 no_difference，把两者都写进 finding_summary。
4. **condition / intervention / comparator / outcomes 一律归一成中文简短标签**，
   即使原文是英文。comparator 只写措施名（如"假针刺""普芦卡必利""乳果糖""常规康复"），
   **不要写剂量、给药方式、疗程**——下游要按它分组。
5. **study_design：研究方案填 protocol**（标题或摘要含 "study protocol"/"研究方案"，
   只描述将要开展的试验、没有结果数据），不要填 rct。
6. contamination 只在夹带了**另一篇论文的标题/摘要/正文/参考文献**时填 true；
   期刊的投稿须知、版权声明、广告这类版面附属内容不算。
7. 穴位用标准国际代码，拿不准就写中文名，**不要猜代码**。

正文：
---
{body}
---"""

# ── 归一化 ────────────────────────────────────────────────
# 穴位归一与体系判定统一走 `module_action/service/acupoint_norm.py`（纯函数、只用标准库）。
# **别在这里再维护一张小表** —— 早先这里有个自己的 `_POINT_FIX`，与那边的词表各自演化，
# 结果同一批语料「入库时归一一套、事后补跑 lit_fix_points 又归一另一套」，
# 而两次结果不同这件事在库里看不出来。
#: 对照措施归一：抹掉剂量/给药方式，只留措施名
_COMP_RULES = [
    (r'假针|假电针|安慰|非经非穴|非穴|sham|placebo', '假针刺'),
    (r'普芦卡必利|prucalopride', '普芦卡必利'),
    (r'莫沙必利|mosapride', '莫沙必利'),
    (r'乳果糖|lactulose', '乳果糖'),
    (r'聚乙二醇|PEG|福松', '聚乙二醇'),
    (r'比沙可啶|bisacodyl', '比沙可啶'),
    (r'生物反馈|biofeedback', '生物反馈'),
    (r'经皮电刺激|TES|TEAS', '经皮电刺激'),
    (r'常规康复|康复训练|rehabilitation', '常规康复训练'),
    (r'常规治疗|基础治疗|usual care|standard', '常规治疗'),
    (r'空白|不干预|等待|waiting', '空白对照'),
    (r'西药|药物治疗', '西药'),
]


def _norm_points(raw: list) -> list[str]:
    """穴位归一：中文名有对照表就换成正确代码；代码格式化；未知的原样保留"""
    out, seen = [], set()
    for x in raw or []:
        s = str(x).strip()
        if not s:
            continue
        zh = re.sub(r'[A-Za-z0-9\-（）()]', '', s).strip()
        if zh and zh in _POINT_FIX:
            code = _POINT_FIX[zh]
        else:
            m = _CODE_RE.match(s.upper().replace(' ', ''))
            if m and m.group(1):
                code = f'EX-{m.group(2)}{m.group(3)}'
            elif m:
                code = f'{m.group(4)}{m.group(5)}'
            else:
                code = s
        if code not in seen:
            seen.add(code)
            out.append(code)
    return out


def _norm_comparator(raw: list) -> list[str]:
    """对照归一成短标签。自由描述会让下游分组静默漂移——踩过一次"""
    out, seen = [], set()
    for x in raw or []:
        s = str(x)
        hit = next((label for pat, label in _COMP_RULES if re.search(pat, s, re.I)), None)
        label = hit or re.split(r'[，,（(]', s.strip())[0][:40]
        if label and label not in seen:
            seen.add(label)
            out.append(label)
    return out


_PROTOCOL_RE = re.compile(r'study protocol|研究方案|试验方案|protocol for a', re.I)


def _norm_design(d: str | None, title: str, abstract: str) -> str:
    """研究方案兜底：实测模型会把 protocol 判成 rct，而 protocol 没有结果、不能当疗效证据"""
    d = (d or 'other').strip().lower()
    if _PROTOCOL_RE.search(f'{title} {abstract or ""}'):
        return 'protocol'
    return d if d in {'rct', 'nrct', 'animal', 'sr_meta', 'case_series', 'protocol', 'other'} else 'other'


#: PostgreSQL 的 text 不接受 NUL（0x00），而 pymupdf 从个别 PDF 里抽出来的文本带着它
#: （字体/编码异常的页会吐出 \x00）。NFKC 不会去掉它，落库时才炸在 execute_batch 上，
#: 表现是「跑到第 50 篇突然 ValueError」。顺手把其它 C0 控制字符也清掉，只留 \t \n \r。
_CTRL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


def _clean(s):
    """清掉 NUL 与 C0 控制字符；非字符串原样返回"""
    return _CTRL.sub('', s) if isinstance(s, str) else s


def _j(v) -> str:
    return _CTRL.sub('', json.dumps(v or [], ensure_ascii=False))


def _int(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        m = re.search(r'\d+', v)
        return int(m.group()) if m else None
    return None


# ── 语料读取 ───────────────────────────────────────────────
def load_catalog() -> dict[int, str]:
    wb = load_workbook(os.path.join(CORPUS, '目录.xlsx'), read_only=True, data_only=True)
    out: dict[int, str] = {}
    for row in wb.worksheets[0].iter_rows(min_row=2, values_only=True):
        if row[0] and row[1]:
            try:
                out[int(row[0])] = str(row[1]).strip()
            except (TypeError, ValueError):
                continue
    wb.close()
    return out


def read_pdf(path: str) -> tuple[str, int]:
    d = fitz.open(path)
    text = '\n'.join(d[i].get_text() for i in range(d.page_count))
    pages = d.page_count
    d.close()
    return _clean(unicodedata.normalize('NFKC', re.sub(r'\n{3,}', '\n\n', text))), pages


#: 文本层短于这个字符数就认为是扫描件
SCAN_THRESHOLD = 500
#: OCR 渲染 DPI 与最大页数。150 dpi 的 A4 约 1272×1785，base64 后每页约 1.2MB，
#: 再高只是徒增 token；页数封顶是防一篇几十页的扫描件把请求撑爆
#: OCR 渲染 DPI 阶梯与最大页数。失败就降一档重试（体积减半，通过率明显提高）；
#: 页数封顶是防一篇几十页的扫描件把请求撑爆
OCR_DPI_LADDER, OCR_MAX_PAGES = (150, 110, 90), 12

OCR_PROMPT = """这是一篇中文期刊论文的扫描件第 {i} 页（全文共 {n} 页）。

请把这一页上**全部可见文字**逐字转写成纯文本，按原版面阅读顺序（多栏排版按栏依次转写）。要求：

1. **逐字转写，不要概括、不要翻译、不要补全你认为缺失的内容。**
2. 表格按行转写，单元格之间用空格分隔。
3. 看不清的字用 □ 代替，不要猜。
4. 不要加任何说明、页码标注或 markdown 标记，只输出转写的正文。"""


def render_page(path: str, idx: int, dpi: int) -> str:
    """
    把扫描件的某一页渲成 PNG 的 base64。

    **为什么 OCR 出文本再走原抽取路，而不是让多模态直接抽字段**：抽取那条路上的
    schema、三条硬约束（不编造 / year 必须给依据 / 夹带标记）与 `目录.xlsx` 锚定
    是一整套，换成图片输入就得再维护一份平行的提示词，两边迟早漂移。
    先 OCR 成文本，后面完全复用，且 `full_text` 也有了内容可供检索与人工复核。
    """
    import base64

    d = fitz.open(path)
    b = d[idx].get_pixmap(dpi=dpi).tobytes('png')
    d.close()
    return base64.b64encode(b).decode()


def pdf_pages(path: str) -> int:
    d = fitz.open(path)
    n = d.page_count
    d.close()
    return n


async def ocr_page(client, model, key, url, b64: str, idx: int, total: int) -> str:
    """转写单页。失败返回空串。"""
    content = [{'type': 'text', 'text': OCR_PROMPT.format(i=idx, n=total)},
               {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{b64}'}}]
    for attempt in (1, 2, 3):
        try:
            r = await client.post(url, json={'model': model, 'temperature': 0, 'stream': False,
                                             'messages': [{'role': 'user', 'content': content}]},
                                  headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})
            r.raise_for_status()
            return _clean((r.json()['choices'][0]['message']['content'] or '').strip())
        except Exception as exc:  # noqa: BLE001
            if attempt == 3:
                print(f'    p{idx} OCR 失败: {type(exc).__name__}: {exc}'[:110])
                return ''
            await asyncio.sleep(3 * attempt)
    return ''


async def ocr_one(client, model, key, url, path: str) -> str:
    """
    逐页转写后拼接，失败页降分辨率重试。

    **必须一页一请求**：实测 3 页一起发（base64 合计 3.7MB）时服务端直接断连
    （`RemoteProtocolError: Server disconnected without sending a response`），
    和批量提示词过长是同一个模式 —— 请求体大小有上限，而 base64 图片增长很快。

    **失败要降 DPI 重试，不能只是重发**：实测同一篇里 p2（1.4MB）成功而 p1（1.1MB）
    连试三次都断连，说明不是稳定的大小阈值而是随手率问题，原样重发解决不了。
    降到 110dpi 后体积减半，通过率明显提高。**漏一页的代价不小** —— 首页装着
    标题、作者、摘要，丢了会得到一条 `authors` 为空的记录（实测 #42 就是这样）。
    """
    n = min(pdf_pages(path), OCR_MAX_PAGES)
    parts = []
    for i in range(n):
        txt = ''
        for dpi in OCR_DPI_LADDER:
            txt = await ocr_page(client, model, key, url, render_page(path, i, dpi), i + 1, n)
            if txt:
                if dpi != OCR_DPI_LADDER[0]:
                    print(f'    p{i + 1}/{n} → {len(txt)} 字符（降至 {dpi}dpi 后成功）')
                else:
                    print(f'    p{i + 1}/{n} → {len(txt)} 字符')
                break
        if not txt:
            print(f'    p{i + 1}/{n} → 全部 DPI 均失败，该页缺失')
        else:
            parts.append(txt)
    return '\n\n'.join(parts)


def pick_model() -> tuple[str, str, str, bool]:
    code = os.environ.get('LLM_MODEL')
    key = os.environ.get('LLM_KEY')
    base = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    if not (code and key):
        raise SystemExit('请设置环境变量 LLM_MODEL / LLM_KEY / LLM_BASE_URL')
    url = base.strip().rstrip('/')
    if not url.endswith('/chat/completions'):
        url = url + ('/v3/chat/completions' if url.endswith('/api') else '/chat/completions')
    return code, key, url, 'volces.com' in base


async def extract_one(client, model, key, url, ark, no, title, body, sem):
    prompt = SCHEMA_PROMPT.format(title=title, body=body[:MAX_CHARS])
    payload = {'model': model, 'messages': [{'role': 'user', 'content': prompt}],
               'temperature': 0, 'stream': False}
    if ark:
        payload['thinking'] = {'type': 'disabled'}
    async with sem:
        for attempt in (1, 2, 3):
            try:
                r = await client.post(url, json=payload,
                                      headers={'Authorization': f'Bearer {key}',
                                               'Content-Type': 'application/json'})
                r.raise_for_status()
                raw = (r.json()['choices'][0]['message']['content'] or '').strip()
                fence = re.search(r'```(?:json)?\s*(.+?)\s*```', raw, re.S)
                txt = fence.group(1) if fence else raw
                s, e = txt.find('{'), txt.rfind('}')
                if s < 0 or e <= s:
                    raise ValueError('模型没有返回 JSON')
                return json.loads(txt[s:e + 1])
            except Exception as exc:  # noqa: BLE001
                if attempt == 3:
                    return {'__error__': f'{type(exc).__name__}: {exc}'[:400]}
                await asyncio.sleep(3 * attempt)


#: 文件名里的字面省略号：`...症患者的...研究_柳冰.pdf` 这种是**文件名本身被截断过**，
#: 不是显示省略。照抄进库就是一条中间缺字、外表却完全正常的引文
_ELLIPSIS = re.compile(r'\.{3,}|…')
_NO_PREFIX = re.compile(r'^\s*\d+\s*[.、_-]?\s*')
_TAIL = re.compile(r'(\s*-\s*副本|[_\-—]\s*[一-鿿A-Za-z][一-鿿A-Za-z·\s]{0,12})\s*$')


def orig_title(fname: str) -> str:
    """
    从 PDF 文件名取中文原题（`编号.中文题名_第一作者.pdf`）。取不到可信的返回空串。

    只认「剥掉编号前缀与作者后缀之后仍含汉字」的情况：英文文件名多半就是目录译名的
    另一份拷贝，没有比 `title_en` 更多的信息。带省略号的一律不信 —— 见 `_ELLIPSIS`。
    与 `tools/lit_fix_titles.from_filename` 同一套规则，改一处要同步另一处。
    """
    stem = re.sub(r'\.pdf$', '', fname or '', flags=re.I)
    stem = _TAIL.sub('', _NO_PREFIX.sub('', stem)).strip()
    if not stem or _ELLIPSIS.search(stem) or not re.search(r'[一-鿿]', stem):
        return ''

    return _clean(unicodedata.normalize('NFKC', stem))[:1000]


def to_row(no: int, fname: str, title: str, pages: int, chars: int, model: str, d: dict) -> tuple:
    """
    抽取结果 → 一行。

    **`title` 与 `title_en` 是两件事，别再合成一件。** 传进来的 `title` 是
    `目录.xlsx` 的题名，而那份目录**全是英文**（569 行零汉字）—— 它作为抽取时的
    防夹带锚是称职的，但直接当题名存，296 篇中文文献的引文就成了「中文作者 +
    英文题名 + 中文刊名」，读者既检索不到也引不了。所以目录题名进 `title_en`，
    `title` 存 PDF 文件名里的中文原题（`orig_title()`），取不到时才回落成目录译名，
    由 `python -m tools.lit_fix_titles` 事后补。
    """
    now = datetime.now()
    orig = orig_title(fname) or title
    if '__error__' in d:
        return (no, fname, orig[:1000], title[:1000], None, '', 'low', '[]', '', '', 'zh', None, '',
                '[]', '[]', '[]', '[]', '[]', 'other', None, 'unclear', '', '[]', '[]', '', '',
                None, None, None, None, '', '0', '', 'pending', model, 'failed', d['__error__'][:500],
                now, pages, chars)
    ac = d.get('acupuncture') or {}
    design = _norm_design(d.get('study_design'), title, d.get('abstract'))
    points = normalize_points(ac.get('points'))
    # 体系判定要带上针法：单字脏器名（肝/肾/脾）光看名字判不了是耳穴还是背俞穴
    acu_system = classify_system(points, str(ac.get('method') or ''))
    deqi = ac.get('deqi')
    lang = (d.get('lang') or '').lower()
    lang = lang if lang in ('zh', 'en') else ('zh' if re.search(r'[一-鿿]', str(d.get('journal') or '')) else 'en')
    contam = bool(d.get('contamination'))
    return (
        no, fname, orig[:1000], title[:1000],
        _int(d.get('year')), str(d.get('year_evidence') or '')[:300],
        'high' if str(d.get('year_confidence')) == 'high' and _int(d.get('year')) else 'low',
        _j(d.get('authors')), str(d.get('journal') or '')[:300], str(d.get('country') or '')[:100], lang,
        d.get('abstract') or '', str(d.get('population') or '')[:1000],
        _j(d.get('condition')), _j(d.get('intervention')),
        _j(_norm_comparator(d.get('comparator'))), _j(d.get('outcomes')), _j(d.get('tcm_syndrome')),
        design, _int(d.get('sample_size')),
        str(d.get('effect_direction') or 'unclear'), d.get('finding_summary') or '',
        _j(points), _j(ac.get('meridian')),
        str(ac.get('method') or '')[:200], str(ac.get('frequency') or '')[:200],
        ('1' if deqi else '0') if deqi is not None else None,
        _int(ac.get('retention_min')), _int(ac.get('sessions')), _int(ac.get('course_weeks')),
        acu_system,
        '1' if contam else '0', str(d.get('contamination_note') or '')[:1000],
        'pending' if contam else 'ok',
        model, 'ok', '', now, pages, chars,
    )


COLS = ('corpus_no,file_name,title,title_en,year,year_evidence,year_confidence,authors,journal,country,lang,'
        'abstract,population,condition,intervention,comparator,outcomes,tcm_syndrome,'
        'study_design,sample_size,effect_direction,finding_summary,'
        'acu_points,acu_meridian,acu_method,acu_frequency,acu_deqi,acu_retention_min,acu_sessions,'
        'acu_course_weeks,acu_system,contamination,contamination_note,review_status,'
        'extract_model,extract_status,extract_error,extract_time,pages,text_chars')
UPSERT = f"""insert into action_literature ({COLS}, create_time, update_time)
values ({','.join(['%s'] * 40)}, now(), now())
on conflict (corpus_no) do update set
  {', '.join(f'{c}=excluded.{c}' for c in COLS.split(',') if c != 'corpus_no')},
  update_time = now()"""


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ids', default='')
    ap.add_argument('--force', action='store_true', help='重抽已入库的')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--ocr', action='store_true',
                    help='文本层为空的扫描件先走多模态 OCR 转写，再按同一套 schema 抽取')
    args = ap.parse_args()

    catalog = load_catalog()
    files = sorted(f for f in os.listdir(CORPUS) if f.lower().endswith('.pdf'))
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    cur.execute("select corpus_no from action_literature where extract_status='ok'")
    done = {r[0] for r in cur.fetchall()}

    want = {int(x) for x in args.ids.split(',') if x.strip()} if args.ids else None
    todo = []
    for name in files:
        m = re.match(r'^(\d{1,3})[.\-_ ]', name)
        if not m:
            continue
        no = int(m.group(1))
        if want and no not in want:
            continue
        if no in done and not args.force:
            continue
        todo.append((no, name))
    if args.limit:
        todo = todo[:args.limit]

    model, key, url, ark = pick_model()
    print(f'语料 {len(files)} 篇 · 已入库 {len(done)} 篇 · 本次待跑 {len(todo)} 篇')
    print(f'模型 {model} @ {url}  并发 {CONCURRENCY}\n')
    if not todo:
        cur.close()
        conn.close()
        return

    # 读 PDF（本地，快）；文本层为空的扫描件按需走 OCR
    prepared, skipped, scans = [], [], []
    for no, name in todo:
        try:
            body, pages = read_pdf(os.path.join(CORPUS, name))
        except Exception as exc:  # noqa: BLE001
            skipped.append((no, name, f'PDF解析失败 {type(exc).__name__}'))
            continue
        if len(body) < SCAN_THRESHOLD:
            if args.ocr:
                scans.append((no, name, pages))
            else:
                skipped.append((no, name, f'文本仅{len(body)}字符，疑似扫描件（加 --ocr 走多模态转写）'))
            continue
        prepared.append((no, name, catalog.get(no, name), body, pages))
    for no, name, why in skipped:
        print(f'  跳过 #{no}: {why}')

    if scans:
        print(f'\n扫描件 {len(scans)} 篇，走多模态 OCR 转写后再抽取：')
        async with httpx.AsyncClient(timeout=600) as oc:
            for no, name, pages in scans:
                txt = await ocr_one(oc, model, key, url, os.path.join(CORPUS, name))
                if len(txt) < SCAN_THRESHOLD:
                    skipped.append((no, name, f'OCR 只得到 {len(txt)} 字符，转人工'))
                    print(f'  ✗ #{no} OCR 结果过短（{len(txt)} 字符），跳过')
                    continue
                print(f'  ✓ #{no} OCR {pages} 页 → {len(txt)} 字符')
                prepared.append((no, name, catalog.get(no, name),
                                 unicodedata.normalize('NFKC', txt), pages))
        print()

    sem = asyncio.Semaphore(CONCURRENCY)
    t0 = time.time()
    ok = fail = 0

    def persist(chunk: list[tuple]) -> None:
        """
        一批抽完就落库。

        **不能等全部跑完再写** —— 567 篇一趟近一小时，中途断网/限流会让前面几百篇的钱白花。
        分批提交后重跑即断点续跑。

        **两张表必须在同一个事务里提交**（只在最后 commit 一次）。踩过一次：原先主表
        upsert 后先 commit、再写全文表，结果全文那步抛 NUL 异常，主表 24 行留下了、
        全文丢了；而续跑靠 `extract_status='ok'` 判断，这 24 篇被当成「已完成」永远跳过，
        表现是「主表 566 行、全文表只有 542 行」，且不查是发现不了的。
        """
        execute_batch(cur, UPSERT, [b[0] for b in chunk], page_size=50)
        cur.execute('select corpus_no, lit_id from action_literature where corpus_no = any(%s)',
                    ([b[0][0] for b in chunk],))
        id_map = dict(cur.fetchall())
        execute_batch(cur, 'insert into action_literature_text (lit_id, corpus_no, full_text) '
                           'values (%s,%s,%s) on conflict (lit_id) do update set full_text=excluded.full_text',
                      [(id_map[b[0][0]], b[0][0], b[1]) for b in chunk if b[0][0] in id_map], page_size=20)
        conn.commit()

    CHUNK = 24
    async with httpx.AsyncClient(timeout=300) as client:
        for start in range(0, len(prepared), CHUNK):
            part = prepared[start:start + CHUNK]
            results = await asyncio.gather(*[
                extract_one(client, model, key, url, ark, no, title, body, sem)
                for no, _, title, body, _ in part])
            batch = []
            for (no, name, title, body, pages), d in zip(part, results):
                if '__error__' in d:
                    fail += 1
                    print(f'  ✗ #{no} {d["__error__"][:90]}')
                else:
                    ok += 1
                # 模型回显的字段也过一道 —— 正文虽已清洗，但抽取结果是模型重新生成的
                row = tuple(_clean(x) for x in to_row(no, name, title, pages, len(body), model, d))
                batch.append((row, body))
            persist(batch)
            el = time.time() - t0
            n_done = start + len(part)
            eta = el / max(n_done, 1) * (len(prepared) - n_done)
            print(f'  [{n_done}/{len(prepared)}] 已落库 · 成功{ok} 失败{fail} · '
                  f'用时{el / 60:.1f}min 预计剩余{eta / 60:.1f}min', flush=True)

    dt = time.time() - t0
    print(f'\n完成：成功 {ok} · 失败 {fail} · 跳过 {len(skipped)} · 耗时 {dt / 60:.1f} 分钟')
    cur.execute("""select count(*), count(*) filter (where extract_status='ok'),
                          count(*) filter (where contamination='1'),
                          count(*) filter (where year_confidence='high')
                   from action_literature""")
    tot, sok, contam, hy = cur.fetchone()
    print(f'库内合计 {tot} 篇 · 抽取成功 {sok} · 夹带标记 {contam} · 年份可信 {hy}')
    cur.close()
    conn.close()


if __name__ == '__main__':
    asyncio.run(main())
