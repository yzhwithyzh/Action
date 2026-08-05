"""P0：PDF/文本解析（纯代码，无 LLM）.

**引用回查已于 0.4.0 移除**（甲方决定）：不再校验模型给的引用是否真在原文里，
`page` 字段一并废弃。相应地本模块不再依赖 difflib，也不再有模糊匹配。
`normalize` 保留，章节切分与 clean 模块仍在用。
"""

from __future__ import annotations

import hashlib
import os
import re
import unicodedata
from pathlib import Path

from srd_engine.schemas import ParsedDoc, ParsedPage, ParsedSection

# 章节标题识别：常见的系统综述结构标题
_SECTION_PATTERNS = [
    r'abstract',
    r'background',
    r'introduction',
    r'methods?',
    r'eligibility criteria',
    r'inclusion criteria',
    r'search strateg(y|ies)',
    r'information sources',
    r'study selection',
    r'data (collection|extraction)',
    r'data items',
    r'effect measures',
    r'risk of bias',
    r'synthesis methods',
    r'certainty (assessment|of evidence)',
    r'grade',
    r'results?',
    r'study characteristics',
    r'meta-?analys[ei]s',
    r'subgroup analys[ei]s',
    r'sensitivity analys[ei]s',
    r'publication bias',
    r'discussion',
    r'limitations?',
    r'conclusions?',
    r'funding',
    r'(conflicts?|declaration) of interest',
    r'references',
    r'摘要', r'前言', r'背景', r'资料与方法', r'方法', r'检索策略', r'纳入(与排除)?标准',
    r'数据提取', r'质量评价', r'偏倚风险', r'统计(学)?(处理|分析|方法)', r'结果',
    r'亚组分析', r'敏感性分析', r'发表偏倚', r'讨论', r'局限性', r'结论', r'利益冲突', r'参考文献',
]
# 章节标题的最大长度
MAX_HEADING_LEN = 60

_SECTION_RE = re.compile(
    r'^\s*(?:\d+(?:\.\d+)*[.、)]?\s*)?(' + '|'.join(_SECTION_PATTERNS) + r')\s*[:：]?\s*$',
    re.IGNORECASE,
)


#: Windows 的经典 260 字符路径上限。超过它，os.stat / open / PyMuPDF 全都会报
#: 「系统找不到指定的路径」——文件明明在、`iterdir()` 也列得出来，就是打不开。
_WINDOWS_MAX_PATH = 260


def long_path(path: str | Path) -> str:
    """Windows 上把超长路径转成 `\\\\?\\` 扩展前缀形式，其他平台原样返回。

    甲方给的文献文件名动辄两百多字符（整个标题当文件名，还带「- 副本」），
    加上目录前缀就顶破 260 —— 实测有 3 篇因此完全读不进来，而报错信息
    （FileNotFoundError）会把人往「文件不见了」的方向带，排查成本极高。
    """
    text = str(path)
    if os.name != 'nt' or text.startswith('\\\\?\\'):
        return text
    absolute = os.path.abspath(text)
    return f'\\\\?\\{absolute}' if len(absolute) >= _WINDOWS_MAX_PATH else absolute


def sha256_of(path: str | Path) -> str:
    # 用内置 open 而不是 Path.read_bytes：Path 会把 `\\?\` 前缀规范化掉，超长路径又打不开了
    with open(long_path(path), 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def normalize(text: str) -> str:
    """引用比对用的归一化：全角转半角、去连字断行、压缩空白、转小写。"""
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'-\s*\n\s*', '', text)          # 断行连字符
    text = re.sub('[\u200b\u200c\u200d\ufeff]', '', text)  # 零宽字符
    text = re.sub(r'\s+', ' ', text)
    return text.strip().lower()


def parse(path: str | Path) -> ParsedDoc:
    """按扩展名分派：.pdf 走 PyMuPDF，其余按纯文本处理（便于无 PDF 时做离线验证）。"""
    path = Path(path)
    if path.suffix.lower() == '.pdf':
        return parse_pdf(path)
    return parse_text(path)


def parse_pdf(path: str | Path) -> ParsedDoc:
    try:
        import pymupdf  # noqa: PLC0415
    except ImportError:  # pragma: no cover - 环境相关
        try:
            import fitz as pymupdf  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError('需要 PyMuPDF：pip install "srd-engine[pdf]"') from exc

    path = Path(path)
    pages: list[ParsedPage] = []
    with pymupdf.open(long_path(path)) as doc:
        for i, page in enumerate(doc, start=1):
            pages.append(ParsedPage(no=i, text=page.get_text('text')))

    if not any(p.text.strip() for p in pages):
        raise ValueError(
            f'{path.name}：未提取到任何文本层，可能是扫描版 PDF。'
            f'本引擎不支持 OCR（OCR 噪声会污染逐字引用），请提供可复制文本的 PDF。'
        )

    return ParsedDoc(
        source=str(path),
        sha256=sha256_of(path),
        page_count=len(pages),
        pages=pages,
        sections=split_sections(pages),
    )


def parse_text(path: str | Path) -> ParsedDoc:
    """纯文本兜底：用 \f（换页符）分页，没有就整篇当一页。"""
    path = Path(path)
    raw = path.read_text(encoding='utf-8', errors='replace')
    chunks = raw.split('\f') if '\f' in raw else [raw]
    pages = [ParsedPage(no=i, text=c) for i, c in enumerate(chunks, start=1)]
    return ParsedDoc(
        source=str(path),
        sha256=hashlib.sha256(raw.encode('utf-8')).hexdigest(),
        page_count=len(pages),
        pages=pages,
        sections=split_sections(pages),
    )


def split_sections(pages: list[ParsedPage]) -> list[ParsedSection]:
    """按标题启发式切章节。切不出来时整篇作为一个 Full text 章节返回。"""
    marks: list[tuple[str, int, int]] = []  # (title, page_no, line_index_global)
    lines: list[tuple[str, int]] = []
    for page in pages:
        lines.extend((line, page.no) for line in page.text.splitlines())
    for idx, (line, page_no) in enumerate(lines):
        stripped = line.strip()
        if 0 < len(stripped) <= MAX_HEADING_LEN and _SECTION_RE.match(stripped):
            marks.append((stripped, page_no, idx))

    if not marks:
        text = '\n'.join(line for line, _ in lines)
        return [ParsedSection(title='Full text', text=text, page_from=pages[0].no if pages else 1,
                              page_to=pages[-1].no if pages else 1)]

    sections: list[ParsedSection] = []
    for i, (title, page_no, start) in enumerate(marks):
        end = marks[i + 1][2] if i + 1 < len(marks) else len(lines)
        body = '\n'.join(line for line, _ in lines[start + 1 : end])
        page_to = lines[end - 1][1] if end > start else page_no
        sections.append(ParsedSection(title=title, text=body, page_from=page_no, page_to=page_to))
    return sections
