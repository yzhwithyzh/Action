"""把「一个 DOI」或「一份 PDF」变成一份可核对的论文元数据草稿（纯函数，可离线单测）。

和 `manuscript_parse` / `report_assist_prompt` / `srd_export_service` 同一种分层：
**输入是字符串或已经拿到手的 JSON，输出还是数据，中间不碰数据库、不发请求、不读配置**。
真正发请求那一层在 `publication_meta_service.py`，单测见 `tools/tests/test_publication_parse.py`。

## 为什么只认 DOI，不做「粘一个网址就抓」

参考实现里那个按钮叫「来源URL」，语义是「把这个地址抓回来解析」。**这里刻意收窄成 DOI**：
让服务器去 GET 一个由调用方给定的地址就是 SSRF —— 后台任一有编辑权限的账号，
都能借此探测内网、打到 169.254.169.254 的云元数据服务或本机上的其它端口。
而 DOI 走的是 Crossref 一个固定主机、只吐结构化元数据，没有这层风险，
覆盖面也够：正式期刊论文几乎都有 DOI，doi.org 链接、`doi:10.x/y`、
出版社页面地址里嵌的 DOI 都能就地抠出来。

抠不出 DOI 时**如实报错让用户手填**，不去猜、不去抓那个网址。

## 为什么 Crossref 之后还要查一次 PubMed

**Crossref 拿不到关键词，摘要也时有时无** —— 这不是偶发，是它的数据模型决定的：

· **关键词：Crossref 根本没有这个字段。** 它有的 `subject` 是**期刊级学科分类**
  （「Complementary and alternative medicine」这种），不是论文的作者关键词；而且
  Crossref 已在 2023 年起把 `subject` 从 API 出参里撤下，实测现在一律是 `[]`。
· **摘要：出版社存了才有。** Springer / BMC / PLOS 一般存；**Elsevier、JAMA、BMJ 不存**
  —— 针刺领域常投的 Complementary Therapies in Medicine、J Integr Med 都在后一档，
  所以只靠 Crossref 的话，摘要多数时候是空的。

PubMed 两样都有（`<AbstractText>` 与作者 `<Keyword>`，没有作者关键词时还有 MeSH 主题词），
生物医学论文覆盖率极高，正好补上。**只补空的那几项，不覆盖 Crossref 已经给出的值** ——
作者、卷期页这些以出版社登记的为准。

## 为什么 PDF 那条要过模型

PDF 首页的版式千差万别（作者与机构常常靠上标数字关联、摘要有无小标题、
中文刊与英文刊的字段顺序都不同），正则抽出来的东西只在自己那几份样本上好使。
这条路本来就是「先填个八九不离十，再由人核对」，模型的容错正好对上；
它产出的每一个字段都会显示在后台表单里等人过目，没有任何一条会直接见公众。
"""

from __future__ import annotations

import json
import re
from typing import Any

#: 送进模型的 PDF 正文长度上限。元数据全在首页（标题/作者/机构/摘要/关键词/期刊卷期页），
#: 多送的正文只是烧钱，还会把注意力从首页拉走
MAX_PDF_PROMPT_CHARS = 6000

#: DOI 的通用形态：`10.` + 注册机构号 + `/` + 后缀。后缀里几乎什么字符都可能有，
#: 所以按「一直吃到空白或常见的收尾标点」来断
_DOI_RE = re.compile(r'\b(10\.\d{4,9}/[^\s"\'<>,;]+)', re.IGNORECASE)
#: 结尾的标点不属于 DOI —— 从正文里粘出来的常带着句号或右括号。
#: 全角那几个必须列上：中文论文里的 DOI 后面跟的是「。」不是「.」，漏了会让 Crossref 404
_DOI_TRAIL = '.,;:)]}>。，；：）】」』、'
#: `https://doi.org/` / `dx.doi.org/` / `doi:` 前缀。与 `PublicationModel.check_doi`
#: 同一套口径 —— 那一层是入库前的兜底，这一层是解析时就地剥干净
_DOI_PREFIX_RE = re.compile(r'^\s*(?:(?:https?://)?(?:dx\.)?doi\.org/|doi:\s*)', re.IGNORECASE)

#: JATS 摘要里的 XML 标签（Crossref 的 abstract 是一段 JATS，不是纯文本）
_XML_TAG_RE = re.compile(r'<[^>]+>')
#: 结构化摘要的小标题在 JATS 里是 <jats:title>Background</jats:title>，
#: 去标签后会和正文粘成一坨，先给它补个冒号与换行
_JATS_TITLE_RE = re.compile(r'<jats:title>(.*?)</jats:title>', re.IGNORECASE | re.DOTALL)
_WS_RE = re.compile(r'[ \t ]+')
_BLANK_RUN_RE = re.compile(r'\n{3,}')

#: 模型可能把 JSON 裹在 ```json 围栏里，也可能前后带一句「好的，以下是……」
_FENCE_RE = re.compile(r'```(?:json)?\s*(.*?)```', re.DOTALL)

#: 引用里列到第几位作者为止，超出写 et al.。3 是绝大多数期刊的下限口径
_CITATION_AUTHOR_LIMIT = 3
#: 年份的合理区间。超出这个范围的多半是页码或样本量被当成年份填了回来
_MIN_YEAR = 1800
_MAX_YEAR = 2100


def extract_doi(source: str) -> str:
    """
    从一串输入里抠出 DOI

    认这几种：裸 DOI（`10.1016/j.ctim.2024.103041`）、`doi:10.x/y`、
    `https://doi.org/10.x/y`、以及出版社页面地址里嵌着 DOI 的（ScienceDirect、Springer 等）。

    :param source: 用户粘进来的那一串
    :return: DOI，抠不出时返回空串
    """
    match = _DOI_RE.search(source or '')
    if not match:
        return ''

    return match.group(1).rstrip(_DOI_TRAIL)


def strip_jats(abstract: str | None) -> str:
    """
    把 Crossref 的 JATS 摘要转成纯文本

    结构化摘要（Background / Methods / Results / Conclusion）的小标题在 JATS 里是
    独立标签，直接去标签会把「BackgroundAcupuncture has been…」粘成一句，
    所以先把小标题拎出来单独成行。

    :param abstract: Crossref 的 abstract 字段
    :return: 纯文本摘要
    """
    if not abstract:
        return ''
    text = _JATS_TITLE_RE.sub(lambda m: f'\n{m.group(1).strip()}：', abstract)
    text = _XML_TAG_RE.sub('', text)
    # Crossref 的摘要里 &amp; / &lt; 很常见
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
    text = _WS_RE.sub(' ', text)
    text = '\n'.join(line.strip() for line in text.splitlines())
    text = _BLANK_RUN_RE.sub('\n\n', text).strip()
    # Crossref 的摘要开头常常就是一个「Abstract」标题，留着等于在摘要框里写「摘要」
    return re.sub(r'^(abstract|摘要)[:：]?\s*', '', text, flags=re.IGNORECASE)


def _author_name(author: dict[str, Any]) -> str:
    """
    拼一位作者的显示名

    Crossref 给的是 given / family 两段（机构作者只有 name）。按「Given Family」拼，
    与论文署名顺序一致；两段都没有时退回 name。

    :param author: Crossref 的一位作者
    :return: 姓名，拼不出时空串
    """
    given = (author.get('given') or '').strip()
    family = (author.get('family') or '').strip()
    if given or family:
        return ' '.join(p for p in (given, family) if p)

    return (author.get('name') or '').strip()


def _issued_year(message: dict[str, Any]) -> int | None:
    """
    取发表年份

    Crossref 有四个日期字段，含义不同：`published-print` 是纸刊出版、`published-online`
    是在线先发、`issued` 是最早公开的那个日期、`created` 是记录建档时间。
    按「印刷 → 在线 → issued」取，这与期刊引用里写的年份一致；`created` 不取
    （它是 Crossref 自己的时间，与论文无关）。

    :param message: Crossref 的 message 对象
    :return: 年份，取不到时 None
    """
    for key in ('published-print', 'published-online', 'published', 'issued'):
        parts = ((message.get(key) or {}).get('date-parts') or [[]])[0]
        if parts and isinstance(parts[0], int):
            return parts[0]

    return None


def _first(value: Any) -> str:
    """Crossref 里 title / container-title 这类字段是**数组**，取第一个。"""
    if isinstance(value, list):
        return str(value[0]).strip() if value else ''

    return str(value or '').strip()


def from_crossref(message: dict[str, Any]) -> dict[str, Any]:
    """
    把 Crossref 的 `message` 对象映射成 `PublicationModel` 的字段

    :param message: `https://api.crossref.org/works/{doi}` 出参里的 message
    :return: 字段字典（snake_case，与 PublicationModel 同名），未给出的字段一律留空
    """
    affiliations: list[str] = []
    authors: list[dict[str, Any]] = []
    for raw in message.get('author') or []:
        if not isinstance(raw, dict):
            continue
        name = _author_name(raw)
        if not name:
            continue
        index: int | None = None
        for affil in raw.get('affiliation') or []:
            label = (affil or {}).get('name', '').strip() if isinstance(affil, dict) else ''
            if not label:
                continue
            # 同一家单位会在每位作者下重复出现，去重后用下标关联
            if label not in affiliations:
                affiliations.append(label)
            index = affiliations.index(label)
            break
        authors.append({'name': name, 'affiliation_index': index})

    return {
        'title': _first(message.get('title')),
        'authors': authors,
        'affiliations': affiliations,
        # 出版社存了才有。Elsevier / JAMA / BMJ 一律没有，那时由 PubMed 兜底（见模块注释）
        'abstract': strip_jats(message.get('abstract')),
        # **不映射 Crossref 的 subject**：那是期刊级学科分类（「Complementary and alternative
        # medicine」），不是论文的作者关键词，填进关键词框是错的；何况 Crossref 2023 年起
        # 已把这个字段从出参撤下，实测一律 `[]` —— 留着只会让人以为「有时能解析出关键词」。
        # 关键词这一项由 PubMed 补
        'keywords': [],
        'journal': _first(message.get('container-title')),
        'volume': str(message.get('volume') or '').strip(),
        'issue': str(message.get('issue') or '').strip(),
        'pages': str(message.get('page') or '').strip(),
        'publication_year': _issued_year(message),
        'doi': str(message.get('DOI') or '').strip(),
        'source_url': str(message.get('URL') or '').strip(),
    }


def parse_pubmed_xml(xml_text: str) -> dict[str, Any]:
    """
    从 PubMed efetch 的 XML 里取摘要与关键词

    只取这两样：标题、作者、卷期页一律以 Crossref（出版社登记值）为准，
    这里补的是 Crossref 结构上就给不了的那部分。

    用标准库的 ElementTree 而不是正则：`<AbstractText>` 里会内嵌 `<i>` `<sup>`
    这类排版标签，正则取文本会把它们连内容一起吃掉或留下半截标签。
    ElementTree **不展开外部实体**（Python 的实现里 DTD 只解析内部子集），
    所以拿它读一份外部 XML 没有 XXE 面。

    :param xml_text: efetch 返回的 XML 全文
    :return: {'abstract': str, 'keywords': list[str], 'keywords_source': 'keyword'|'mesh'|'',
              'pmid': str}；解析不出时各项为空，**不抛异常**（这是兜底路径，不该把主路带崩）
    """
    from xml.etree import ElementTree as ET  # noqa: PLC0415  只有走到兜底才需要，不拖累进程启动

    empty: dict[str, Any] = {'abstract': '', 'keywords': [], 'keywords_source': '', 'pmid': ''}
    try:
        root = ET.fromstring(xml_text or '')
    except ET.ParseError:
        return empty

    article = root.find('.//PubmedArticle')
    if article is None:
        return empty

    pmid_node = article.find('.//PMID')
    pmid = (pmid_node.text or '').strip() if pmid_node is not None else ''

    # 结构化摘要：每个 AbstractText 带 Label（BACKGROUND / METHODS / RESULTS…），
    # 不把 Label 拎出来单独成行的话，去标签后会粘成「BACKGROUNDAcupuncture has…」
    # —— 与 strip_jats 对 JATS 小标题的处理是同一套口径
    paragraphs: list[str] = []
    for node in article.findall('.//Abstract/AbstractText'):
        # itertext 把内嵌的 <i>/<sup> 里的文字也带出来
        text = _WS_RE.sub(' ', ''.join(node.itertext())).strip()
        if not text:
            continue
        label = (node.get('Label') or '').strip()
        paragraphs.append(f'{label}：{text}' if label else text)

    # 作者关键词优先。KeywordList 挂在 MedlineCitation 下（与 Article 平级），
    # 层级容易记错，所以用 .// 通配而不是写死路径
    keywords = [k for k in (_node_text(n) for n in article.findall('.//KeywordList/Keyword')) if k]
    source = 'keyword' if keywords else ''
    if not keywords:
        # 没有作者关键词时回落 MeSH 主题词。**来源要标出来**：MeSH 是索引员事后打的
        # 受控词，不是作者写的关键词，展示前该让管理员知道这回事
        keywords = [k for k in (_node_text(n) for n in article.findall('.//MeshHeading/DescriptorName')) if k]
        source = 'mesh' if keywords else ''

    return {
        'abstract': '\n\n'.join(paragraphs).strip(),
        'keywords': _dedupe_keep_order(keywords),
        'keywords_source': source,
        'pmid': pmid,
    }


def _node_text(node: Any) -> str:
    """取一个节点的纯文本（含内嵌标签里的文字），压掉多余空白。"""
    return _WS_RE.sub(' ', ''.join(node.itertext())).strip()


def _dedupe_keep_order(values: list[str]) -> list[str]:
    """去重但保序 —— MeSH 里同一个词会因主/次标题重复出现。"""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)

    return out


def build_citation_text(fields: dict[str, Any]) -> str:
    """
    按字段拼一条引用文本（温哥华格式的常见写法）

    形如：`Zhang S, Li W, Chen H, et al. Title. Journal. 2024;12(3):145-152. doi:10.x/y`
    后台留空「引用文本」时由这条兜底，填了就以填的为准 —— 各刊要求的格式不同，
    自动拼的这条只是个够用的默认值，不该覆盖人工写的。

    :param fields: 与 PublicationModel 同名的字段字典
    :return: 引用文本；连标题都没有时返回空串
    """
    parts: list[str] = []
    authors = [str((a or {}).get('name', '')).strip() for a in (fields.get('authors') or [])]
    authors = [a for a in authors if a]
    if authors:
        head = ', '.join(authors[:_CITATION_AUTHOR_LIMIT])
        parts.append(f'{head}{", et al" if len(authors) > _CITATION_AUTHOR_LIMIT else ""}.')
    title = str(fields.get('title') or '').strip()
    if title:
        parts.append(title if title.endswith(('.', '?', '!', '。', '？', '！')) else f'{title}.')
    journal = str(fields.get('journal') or '').strip()
    if journal:
        segment = journal
        if fields.get('publication_year'):
            segment += f'. {fields["publication_year"]}'
        if fields.get('volume'):
            segment += f';{fields["volume"]}'
            if fields.get('issue'):
                segment += f'({fields["issue"]})'
        if fields.get('pages'):
            segment += f':{fields["pages"]}'
        parts.append(f'{segment}.')
    elif fields.get('publication_year'):
        # 没有期刊名（会议摘要、预印本）时年份也别丢
        parts.append(f'{fields["publication_year"]}.')
    if fields.get('doi'):
        parts.append(f'doi:{fields["doi"]}')

    return ' '.join(parts).strip()


#: 让模型只做「抄」这一件事。三条硬约束与 `report_assist_prompt` 同源：
#: 不编造、拿不准就留空、只回 JSON。这是学术成果列表，凭空多出一位作者或一个卷期
#: 是学术诚信问题，不是文案问题
_PDF_SYSTEM = """你是一个文献元数据抽取器。用户会给你一篇学术论文 PDF 的开头部分文字，\
你要从中抄出这篇论文的元数据，以 JSON 返回。

严格遵守：
1. 只抄原文里确实出现的内容，**一个字都不要编**。拿不准或原文没有的字段一律留空（字符串留 ""，数组留 []，数字留 null）。
2. 保持原文语言与逐字写法：英文论文就是英文，中文论文就是中文，不要翻译、不要改写、不要补标点。
3. 只输出 JSON 对象本身，不要加解释、不要加 ``` 代码围栏。

JSON 字段：
{
  "title": "论文标题",
  "authors": [{"name": "作者姓名", "affiliationIndex": 0}],
  "affiliations": ["机构全称"],
  "abstract": "摘要正文（不含 Abstract 这个词本身）",
  "keywords": ["关键词"],
  "journal": "期刊名称",
  "volume": "卷",
  "issue": "期",
  "pages": "页码",
  "publicationYear": 2024,
  "doi": "10.xxxx/yyyy"
}

affiliationIndex 是该作者所属机构在 affiliations 数组中的下标（从 0 开始）；\
原文没有用上标数字标注作者与机构的对应关系时，一律填 null，不要猜。"""


def build_pdf_messages(text: str) -> list[dict[str, str]]:
    """
    拼 PDF 元数据抽取的对话消息

    :param text: `manuscript_parse.parse_manuscript` 抽出来的正文
    :return: OpenAI 兼容的 messages
    """
    head = (text or '')[:MAX_PDF_PROMPT_CHARS]

    return [
        {'role': 'system', 'content': _PDF_SYSTEM},
        {'role': 'user', 'content': f'以下是论文 PDF 开头部分的文字：\n\n{head}'},
    ]


def _coerce_authors(raw: Any, affiliation_count: int) -> list[dict[str, Any]]:
    """
    把模型给的 authors 收成合法形状

    模型偶尔会直接给一个字符串数组（`["Zhang San", "Li Si"]`），也偶尔会把
    affiliationIndex 给成越界的数或字符串。这里一律收敛，**越界就当没标**
    —— 挂错单位比不挂单位更糟。

    :param raw: 模型给的 authors
    :param affiliation_count: 机构数量，用于判定下标是否越界
    :return: 规范化后的作者列表
    """
    out: list[dict[str, Any]] = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, str):
            name, index = item.strip(), None
        elif isinstance(item, dict):
            name = str(item.get('name') or item.get('姓名') or '').strip()
            index = item.get('affiliationIndex', item.get('affiliation_index'))
        else:
            continue
        if not name:
            continue
        if isinstance(index, str) and index.strip().isdigit():
            index = int(index)
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < affiliation_count:
            index = None
        out.append({'name': name, 'affiliation_index': index})

    return out


def _clean_text(raw: Any) -> str:
    """
    收一个文本字段：转成串、去首尾空白，并把不间断空格换成普通空格

    NBSP（`\\u00a0`）从 PDF 里抄出来很常见（实测就有一条标题里带着它）。它在页面上
    **看不出来**，却会让检索、复制引用、按标题查重全部失灵 —— 用户只会觉得
    「明明一模一样怎么搜不到」。这一步是唯一能在入库前把它掐掉的地方。

    :param raw: 模型给的值
    :return: 干净的字符串
    """
    # _WS_RE 的字符类里就含  ，一次 sub 同时做了「压空白」与「换掉 NBSP」两件事
    return _WS_RE.sub(' ', str(raw or '')).strip()


def _coerce_str_list(raw: Any) -> list[str]:
    """把模型给的字符串数组收干净；给成一整串（逗号/分号分隔）时就地拆开。"""
    if isinstance(raw, str):
        return [s.strip() for s in re.split(r'[;；,，]', raw) if s.strip()]

    return [str(s).strip() for s in raw if str(s).strip()] if isinstance(raw, list) else []


def _coerce_year(raw: Any) -> int | None:
    """年份收成 int，明显不像年份的（4 位以外、超出 1800–2100）当没给。"""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        year = raw
    elif isinstance(raw, str):
        match = re.search(r'(1[89]\d{2}|20\d{2}|2100)', raw)
        if not match:
            return None
        year = int(match.group(1))
    else:
        return None

    return year if _MIN_YEAR <= year <= _MAX_YEAR else None


def parse_ai_json(raw: str) -> dict[str, Any]:
    """
    把模型返回的那段文字解析成 `PublicationModel` 的字段

    容错三件事：去掉 ``` 围栏、截取第一个 `{` 到最后一个 `}`、字段名大小写与
    驼峰/下划线两种写法都认。解析不出来时**抛异常而不是返回空字典** ——
    空字典会被后台渲染成「解析成功但什么都没填」，用户会以为这篇 PDF 里真的没有元数据。

    :param raw: 模型返回的正文
    :return: 字段字典（snake_case）
    :raise ValueError: 拿不到合法 JSON
    """
    text = (raw or '').strip()
    fence = _FENCE_RE.search(text)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find('{'), text.rfind('}')
    if start < 0 or end <= start:
        raise ValueError('模型没有返回 JSON')
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f'模型返回的 JSON 无法解析：{e}') from e
    if not isinstance(data, dict):
        raise ValueError('模型返回的不是 JSON 对象')

    def pick(*names: str) -> Any:
        for name in names:
            if name in data:
                return data[name]

        return None

    affiliations = _coerce_str_list(pick('affiliations', 'affiliation'))
    raw_doi = str(pick('doi') or '').strip()

    return {
        'title': _clean_text(pick('title')),
        'authors': _coerce_authors(pick('authors'), len(affiliations)),
        'affiliations': affiliations,
        'abstract': _clean_text(pick('abstract')),
        'keywords': _coerce_str_list(pick('keywords')),
        'journal': _clean_text(pick('journal', 'container_title', 'containerTitle')),
        'volume': _clean_text(pick('volume')),
        'issue': _clean_text(pick('issue')),
        'pages': _clean_text(pick('pages', 'page')),
        'publication_year': _coerce_year(pick('publicationYear', 'publication_year', 'year')),
        # 先按标准形态抠；抠不出时只剥前缀原样留下 —— DOI 的注册机构号理论上是 4-9 位，
        # 但真出现一个不合规的，也该原样填回表单让人看见，而不是安静地清空
        'doi': extract_doi(raw_doi) or _DOI_PREFIX_RE.sub('', raw_doi).strip().rstrip(_DOI_TRAIL),
    }
