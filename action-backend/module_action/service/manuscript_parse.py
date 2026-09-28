"""
把上传的稿件文件解析成纯文本（纯函数，可离线单测）。

和 `report_assist_prompt` / `srd_export_service` 同一种分层：**输入是字节，输出是字符串，
中间不碰数据库、不碰 HTTP、不读全局配置**。见 `tools/tests/test_manuscript_parse.py`。

## 为什么要有这一层

第三步的「选择文件」此前只做 `file.text()`，也就是**只认纯文本**。用户传一个 .docx 进去，
拿到的是 zip 容器的二进制乱码，然后这堆乱码被当成稿件送去判定 —— 不报错，只是判出一片
「未报告」。而研究者手上的稿件几乎不可能是 .txt。

## 换行是这里最要紧的东西

下游整条链路（判定的「报告于第 N 行」、回填草稿、前台的原文面板）都以**行**为锚点，
而行号的定义是 `engine/audit.py::line_map` —— 空行不占号。所以这里的任务不只是「取出文字」，
更是**把文档的段落结构变成换行**：

· docx：一个 `<w:p>` 就是一段，直接对应一行。表格里的单元格也要取（基线特征表常在表里），
  按行拼成一段，否则整张表的内容会凭空消失。
· pdf：按块取文字。**PDF 没有「段落」这个概念**，只有位置相近的文本块，所以结果天然比
  docx 脏 —— 这也是为什么下面对 pdf 额外做一次「粘回被硬换行切断的句子」。

## 不做 OCR

扫描件 PDF 抽出来是空的，这里如实报错，不去猜。让用户拿到「这份 PDF 没有可提取的文字，
它可能是扫描件」比让他等几分钟再收获一份全是「未报告」的判定要好得多。

## 块（Block）：文字从哪儿来，重建时就改回哪儿去

`read_blocks` 按**文档原本的顺序**把稿件拆成块 —— 段落 / 表格 / 图片，每块记着它贡献了
哪几行文字，docx 还记着对应的 XML 元素。`parse_manuscript` 的纯文本就是这些块的行按序拼起来，
所以「第 N 行」能反查回它在原稿里的位置。「生成初稿」（`manuscript_rebuild`）靠这一点把
条目上的修改写回原稿原处，图片、表格、样式都不动。

**docx 的表格按它在文中的位置出现**（2026-09 之前是统一追加在全文末尾）：只有这样，
表格前后的段落行号才与原稿顺序一致。
"""

from __future__ import annotations

import contextlib
import io
import re
import zipfile
from dataclasses import dataclass, field
from typing import Any

#: 支持的扩展名 → 人读的名字。**白名单而不是黑名单**：这一层会把字节喂给解析库，
#: 放开未知格式等于把解析库的攻击面直接暴露给公网上传口
SUPPORTED = {
    '.txt': '纯文本',
    '.md': 'Markdown',
    '.docx': 'Word 文档',
    '.pdf': 'PDF',
}

#: 连续空行压成一个。docx 里大量空段落很常见，留着会把原文面板撑得很难读
_BLANK_RUN = re.compile(r'\n{3,}')

#: 行尾看起来「话没说完」——用于判断 PDF 里的硬换行要不要粘回去。
#: 中文句子不靠空格分词，PDF 抽出来常常一行一句半，粘错了比不粘更难读，
#: 所以只在**上一行没有句末标点、且下一行不是新段落起头**时才粘
_SENTENCE_END = re.compile(r'[。！？；：.!?;:）)】」』”"\]]\s*$')
_NEW_BLOCK = re.compile(r'^\s*([#\-*•·]|\d+[.、)]|[一二三四五六七八九十]+[、.]|表\s*\d|图\s*\d|Table\s|Figure\s)')


class ManuscriptParseError(Exception):
    """解析失败。消息直接给用户看，所以要说人话、并给出下一步怎么办。"""


@dataclass
class Block:
    """
    稿件里按顺序排列的一块

    :ivar kind: para（段落）/ table（表格）/ image（独立成块的图片，仅 PDF）
    :ivar lines: 这一块贡献给纯文本的行，已去首尾空白、不含空行 —— 行号就按它们依次编
    :ivar el: docx 里对应的 XML 元素，重建时就地修改它
    :ivar image: PDF 图片的字节；ext / width / height 是它的格式与版面尺寸（pt）
    """

    kind: str
    lines: list[str] = field(default_factory=list)
    el: Any = None
    image: bytes = b''
    ext: str = ''
    width: float = 0.0
    height: float = 0.0


#: 比这还小的 PDF 图片多半是分隔线、logo、页眉装饰，不当成图带进初稿
_MIN_IMAGE_PT = 24


def _split(text: str, keep_indent: bool = False) -> list[str]:
    """
    一段文字拆成行。**用 `splitlines` 而不是 `split('\\n')`**：行号的唯一定义
    `engine/audit.py::line_map` 就是这么切的，分页符 `\\f` 之类也算断行，少认一个后面整体错位
    """
    cut = str.rstrip if keep_indent else str.strip
    return [cut(ln) for ln in text.splitlines() if ln.strip()]


def ext_of(filename: str) -> str:
    """取小写扩展名（带点），无扩展名时为空串"""
    return ('.' + filename.rsplit('.', 1)[-1].lower()) if '.' in filename else ''


def blocks_text(blocks: list[Block]) -> str:
    """
    块 → 纯文本：每块的行依次换行拼起来。没有文字的块（空段落、纯图片段落）出一个空行 ——
    它不占行号，只保留原稿的段落间隔，连续的空行最后由 `parse_manuscript` 压成一个
    """
    return '\n'.join('\n'.join(b.lines) if b.lines else '' for b in blocks)


def _from_txt(data: bytes) -> str:
    """
    纯文本 / Markdown

    编码按「utf-8-sig → gbk」顺序试。**gbk 不能省**：中文 Windows 上另存为
    「ANSI」的 txt 就是它，而那恰恰是国内研究者最容易产出的文件。

    **utf-8-sig 必须排第一**：它对不带 BOM 的 utf-8 一样能解，带 BOM 的则把 BOM 剥掉。
    原来 `utf-8` 排在前面，带 BOM 的文件也被它解开、BOM 原样留在正文开头 ——
    记事本另存的 txt 常以「BOM + 空行」开头，那一行在前台（JS）算空行、在引擎（Python）
    曾经不算，行号从那里起整体错一行。

    :param data: 文件字节
    :return: 文本
    """
    for enc in ('utf-8-sig', 'gbk'):
        with contextlib.suppress(UnicodeDecodeError):
            return data.decode(enc)
    # 兜底：用 utf-8 忽略坏字节，总比整份拒收强
    return data.decode('utf-8', errors='ignore')


def open_docx(data: bytes) -> Any:
    """
    打开 docx

    :param data: 文件字节
    :return: python-docx 的 Document
    :raises ManuscriptParseError: 不是有效的 docx
    """
    from docx import Document  # noqa: PLC0415  按需导入，不拖累未用到该功能的进程启动

    try:
        return Document(io.BytesIO(data))
    except (zipfile.BadZipFile, KeyError, ValueError) as e:
        # .doc（97-2003 二进制格式）走到这里的概率最高，单独点名它
        raise ManuscriptParseError('这个 Word 文件打不开。若它是 .doc 格式，请用 Word 另存为 .docx 后重试') from e


def docx_blocks(doc: Any) -> list[Block]:
    """
    Word 文档 → 块，按正文里的原本顺序

    段落与表格都取。**表格不能漏**：基线特征、结局指标这些内容在中文论文里几乎总在表格里，
    漏掉的话会把一整批条目判成「未报告」，而用户明明写了。表格一行拼成一行文字，
    单元格间用全角空格分隔；整行都空的不要。

    正文里的内容控件（`w:sdt`）等其它元素不成块、原样留在文档里 —— 与此前只取
    `doc.paragraphs` 的口径一致。

    :param doc: python-docx 的 Document
    :return: 块列表
    """
    from docx.oxml.ns import qn  # noqa: PLC0415
    from docx.table import Table  # noqa: PLC0415
    from docx.text.paragraph import Paragraph  # noqa: PLC0415

    blocks: list[Block] = []
    for el in doc.element.body.iterchildren():
        if el.tag == qn('w:p'):
            blocks.append(Block('para', _split(Paragraph(el, doc).text), el=el))
        elif el.tag == qn('w:tbl'):
            lines = []
            for row in Table(el, doc).rows:
                cells = [c.text.strip().replace('\n', ' ') for c in row.cells]
                if any(cells):
                    lines.append('　'.join(x for x in cells if x))
            blocks.append(Block('table', [ln for ln in (x.strip() for x in lines) if ln], el=el))

    return blocks


def pdf_blocks(data: bytes) -> list[Block]:
    """
    PDF → 块：重排后的每一段一块，图片按它在页面上的位置夹在中间

    PDF 没有「段落」也没有「表格」，只有位置相近的文字块 —— 表格在这里只剩一行行文字，
    重建初稿时也还原不出表格结构。图片可以原样取出来，所以它们独立成块。

    :param data: 文件字节
    :return: 块列表
    :raises ManuscriptParseError: 不是有效的 PDF，或没有可提取的文字（多半是扫描件）
    """
    import fitz  # noqa: PLC0415  pymupdf，按需导入

    try:
        doc = fitz.open(stream=data, filetype='pdf')
    except Exception as e:
        raise ManuscriptParseError('这个 PDF 打不开，请确认文件没有损坏') from e

    seq: list[str | Block] = []
    try:
        for page in doc:
            for b in page.get_text('dict', sort=True).get('blocks', []):
                if b.get('type') == 1:
                    x0, y0, x1, y1 = b.get('bbox', (0, 0, 0, 0))
                    if b.get('image') and x1 - x0 >= _MIN_IMAGE_PT and y1 - y0 >= _MIN_IMAGE_PT:
                        seq.append(Block('image', image=b['image'], ext=b.get('ext', 'png'), width=x1 - x0, height=y1 - y0))
                    continue
                seq.extend(''.join(sp.get('text', '') for sp in line.get('spans', [])) for line in b.get('lines', []))
    finally:
        doc.close()

    blocks = [x if isinstance(x, Block) else Block('para', [x] if x else []) for x in _reflow(seq)]
    if not any(b.lines for b in blocks):
        raise ManuscriptParseError('这份 PDF 里没有可提取的文字，它可能是扫描件。请改用 Word 文档，或先做文字识别')

    return blocks


def _reflow(seq: list) -> list:
    """
    把 PDF 排版造成的硬换行粘回去；图片块是硬分隔，前后不粘。

    PDF 里一段话是按视觉行断开的，直接拿来编行号的话，「报告于第 12 行」会指向半句话，
    而回填进草稿的也是半句。这里只做**保守**的粘接：上一行没有句末标点、且下一行不像
    新段落起头（不是标题、编号、表图说明）时才粘 —— 粘错比不粘更难读。

    :param seq: 原始行（str）与图片块（Block）的序列
    :return: 重排后的序列，空串表示空行
    """
    out: list = []
    for raw in seq:
        if not isinstance(raw, str):
            out.append(raw)
            continue
        line = raw.strip()
        if not line:
            out.append('')
            continue
        prev = out[-1] if out and isinstance(out[-1], str) else ''
        if prev and not _SENTENCE_END.search(prev) and not _NEW_BLOCK.match(line):
            # 中文之间不加空格，中英之间加一个，避免把英文单词粘成一坨
            sep = '' if _is_cjk(prev[-1]) and _is_cjk(line[0]) else ' '
            out[-1] = f'{prev}{sep}{line}'
        else:
            out.append(line)

    return out


def _reflow_pdf(text: str) -> str:
    """
    纯文本版的重排（单测与旧调用方用），规则同 `_reflow`

    :param text: 逐页拼起来的原始文本
    :return: 重排后的文本
    """
    return '\n'.join(_reflow(text.splitlines()))


def text_blocks(text: str) -> list[Block]:
    """纯文本 / Markdown → 块：一行一块。保留行首缩进（Markdown 的列表层级靠它）"""
    return [Block('para', _split(ln, keep_indent=True)) for ln in text.splitlines()]


def read_blocks(filename: str, data: bytes) -> list[Block]:
    """
    稿件文件 → 块（docx 的块带着活的 XML 元素；要改文档请用 `open_docx` + `docx_blocks`）

    :param filename: 原始文件名，只用来取扩展名
    :param data: 文件字节
    :return: 块列表
    :raises ManuscriptParseError: 格式不支持、文件损坏、或解析出来是空的
    """
    ext = ext_of(filename)
    _check_ext(ext)
    if not data:
        raise ManuscriptParseError('文件是空的')
    if ext == '.pdf':
        return pdf_blocks(data)
    if ext == '.docx':
        return docx_blocks(open_docx(data))

    return text_blocks(_from_txt(data))


def _is_cjk(ch: str) -> bool:
    """这个字符是不是中日韩表意文字（决定粘接时要不要补空格）。"""
    return '一' <= ch <= '鿿' or '　' <= ch <= '〿' or '＀' <= ch <= '￯'


def _check_ext(ext: str) -> None:
    """扩展名白名单"""
    if ext in SUPPORTED:
        return
    allowed = ' / '.join(sorted(SUPPORTED))
    # `.doc` 单独点名：它是这里最常见的一次失败，而「不支持」三个字帮不上忙 ——
    # 用户需要知道的是「用 Word 另存一下就行」
    if ext == '.doc':
        raise ManuscriptParseError('不支持 .doc（Word 97-2003）格式，请用 Word 另存为 .docx 后重试')
    raise ManuscriptParseError(f'不支持的文件格式 {ext or "（无扩展名）"}，请上传 {allowed}')


def parse_manuscript(filename: str, data: bytes) -> str:
    """
    把上传的稿件文件解析成纯文本

    :param filename: 原始文件名，只用来取扩展名
    :param data: 文件字节
    :return: 纯文本（已压掉连续空行、去掉行尾空白）
    :raises ManuscriptParseError: 格式不支持、文件损坏、或解析出来是空的
    """
    text = blocks_text(read_blocks(filename, data))

    # 统一换行、去行尾空白、压掉连续空行
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = '\n'.join(line.rstrip() for line in text.split('\n'))
    text = _BLANK_RUN.sub('\n\n', text).strip()

    if not text:
        raise ManuscriptParseError('没有从这个文件里读到任何文字')

    return text
