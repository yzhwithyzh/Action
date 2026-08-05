"""解析与引用回查单测 —— 引用回查是防 LLM 编造的硬门槛。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from srd_engine import pdf as pdf_util
from srd_engine.schemas import ParsedDoc, ParsedPage

if TYPE_CHECKING:
    from pathlib import Path

PAGE1 = """Acupuncture for chronic low back pain: a systematic review

Abstract
This review evaluates the effect of acupuncture on chronic non-specific low back pain.

Methods
We searched PubMed, Embase, the Cochrane Central Register of Controlled Trials (CENTRAL),
CNKI and WanFang from inception to March 2024.
"""

PAGE2 = """Results
Fourteen randomised controlled trials involving 1,832 participants were included.
No sensitivity analysis was performed.

Discussion
The pooled effect favoured acupuncture.
"""


def _doc() -> ParsedDoc:
    pages = [ParsedPage(no=1, text=PAGE1), ParsedPage(no=2, text=PAGE2)]
    return ParsedDoc(source='test', page_count=2, pages=pages, sections=pdf_util.split_sections(pages))


def test_split_sections_finds_standard_headings():
    titles = [s.title.lower() for s in _doc().sections]
    assert 'abstract' in titles
    assert 'methods' in titles
    assert 'results' in titles
    assert 'discussion' in titles


def test_split_sections_falls_back_to_full_text():
    pages = [ParsedPage(no=1, text='no headings here at all, just prose about acupuncture')]
    sections = pdf_util.split_sections(pages)
    assert len(sections) == 1
    assert sections[0].title == 'Full text'


def test_section_text_selects_by_keyword():
    doc = _doc()
    text = doc.section_text('method', fallback_all=False)
    assert 'PubMed' in text
    assert 'Discussion' not in text


def test_section_text_falls_back_when_no_hit():
    doc = _doc()
    assert doc.section_text('nonexistent-heading', fallback_all=True) == doc.full_text
    assert doc.section_text('nonexistent-heading', fallback_all=False) == ''


# --------------------------------------------------------------------------- 引用回查


def test_parse_text_file(tmp_path: Path):
    f = tmp_path / 'review.txt'
    f.write_text(PAGE1 + '\f' + PAGE2, encoding='utf-8')
    doc = pdf_util.parse(f)
    assert doc.page_count == 2
    assert doc.sha256
    assert 'WanFang' in doc.pages[0].text


def test_parse_dispatches_on_suffix(tmp_path: Path):
    f = tmp_path / 'x.md'
    f.write_text('hello', encoding='utf-8')
    assert pdf_util.parse(f).page_count == 1


def test_normalize_removes_hyphenation_across_lines():
    assert 'randomised' in pdf_util.normalize('random-\nised')


# --------------------------------------------------------------------------- Windows 超长路径

EXT_PREFIX = '\\\\?\\'


def test_long_path_adds_the_extended_prefix_only_when_needed(monkeypatch):
    """Windows 上超过 260 字符才加扩展前缀；短路径不动，已带前缀的不再包一层。

    甲方给的文献用整个标题当文件名，加目录前缀顶破 260 后 PyMuPDF 直接报
    FileNotFoundError（实测 3 篇），错误信息会把人往「文件不见了」带。
    """
    monkeypatch.setattr('srd_engine.pdf.os.name', 'nt')
    monkeypatch.setattr('srd_engine.pdf.os.path.abspath', lambda p: 'E:\\x\\' + p)

    assert pdf_util.long_path('short.pdf') == 'E:\\x\\short.pdf'
    assert pdf_util.long_path('a' * 300 + '.pdf').startswith(EXT_PREFIX)
    assert pdf_util.long_path(EXT_PREFIX + 'E:\\already') == EXT_PREFIX + 'E:\\already'


def test_long_path_is_a_noop_off_windows(monkeypatch):
    monkeypatch.setattr('srd_engine.pdf.os.name', 'posix')
    assert pdf_util.long_path('/tmp/' + 'a' * 300) == '/tmp/' + 'a' * 300
