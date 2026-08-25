"""成果发表的元数据抽取：DOI 走 Crossref，PDF 走模型池。

这一层只管 IO（发请求、调模型），映射与清洗全在 `publication_parse`（纯函数、可离线单测）。
产出的一律是**草稿**：直接回给后台表单等人核对，一个字段都不会自己入库。

## 两条路的分工

· **DOI**：正式期刊论文几乎都有，Crossref 给的是出版社登记的权威元数据（作者顺序、
  卷期页、机构），准确度远高于任何抽取。这条是主路。
  Crossref 给不出摘要与关键词时（很常见，原因见 `publication_parse` 的模块注释），
  **按同一个 DOI 再查一次 PubMed 补这两项**。
· **PDF**：预印本、会议摘要、刚接收还没上线的论文没有 DOI，只能从首页文字里抽。
  这条兜底，且明确告诉用户「请核对」。

## PubMed 那一步是「有则更好」，不是主路

它只补 Crossref 结构上给不了的两项，且**任何失败都吞掉**（网络不通、内网没出口、
NCBI 限流、这篇没被 PubMed 收录）—— Crossref 那份草稿已经能用了，
不该因为兜底失败就让整次解析报错。失败只落日志。

## 为什么这两条都不接受任意 URL

见 `publication_parse` 的模块注释：让服务器 GET 调用方给定的地址就是 SSRF。
Crossref 与 NCBI 都是**写死在代码里**的主机，用户输入只作为 DOI 出现
（经过 `extract_doi` 的正则约束，再由 httpx 的 params/`quote` 转义），
不能改主机、不能改协议。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import httpx
from starlette.status import HTTP_200_OK, HTTP_404_NOT_FOUND

from exceptions.exception import ServiceException
from module_action.entity.vo.action_vo import PublicationModel
from module_action.service.ai_assist_service import AiAssistService
from module_action.service.manuscript_parse import ManuscriptParseError, parse_manuscript
from module_action.service.publication_parse import (
    build_citation_text,
    build_pdf_messages,
    extract_doi,
    from_crossref,
    parse_ai_json,
    parse_pubmed_xml,
)
from utils.log_util import logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

#: 联系方式。Crossref 与 NCBI 都要求（或强烈建议）调用方留一个 —— 留了会被分到
#: 响应更快的「polite pool」，出问题时对方也能先来信而不是直接封。与页脚公示的一致
_CONTACT_EMAIL = 'action_acu@163.com'
#: Crossref 的元数据接口。**主机写死**，用户输入只进路径
_CROSSREF_WORK_URL = 'https://api.crossref.org/works/{doi}'
_CROSSREF_UA = f'ACTION-Platform/1.0 (https://action-acu.org; mailto:{_CONTACT_EMAIL})'
_CROSSREF_TIMEOUT = 15.0

#: NCBI E-utilities。**主机同样写死**，DOI 只作为检索词出现
_EUTILS_BASE = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils'
#: NCBI 要求带上 tool 与 email 标识调用方
_EUTILS_IDENT = {'tool': 'ACTION-Platform', 'email': _CONTACT_EMAIL}
#: 兜底路径的超时压得比主路更短：管理员正在页面上等着，为了补一段摘要多等十几秒不值
_PUBMED_TIMEOUT = 8.0

#: PDF 元数据这一步**不限制输出长度**（传 None，`_call_one` 就整个不下发 max_tokens）。
#: 这条的输出长度取决于论文有几位作者、摘要多长，事先根本估不准 —— 原先给 2000 时
#: 撞过一次：一篇 20 位作者的研究列到第 12 位就断了，而截断的现场只报得出
#: 「模型返回的 JSON 无法解析」，根因（额度不够、还被「AI模型管理」里那栏再压低一道）
#: 完全看不出来。抽取任务本身有天然长度，不设限比设一个猜的数字安全
_PDF_MAX_TOKENS = None
#: 抽取要的是「照抄」，温度压到最低
_PDF_TEMPERATURE = 0.0
#: 这一步的超时（`AiAssistService` 的默认 45 秒是给秒级改写定的，这里不够）。
#: 不限输出长度 + 非流式 = 要等模型把整段 JSON（20 位作者 + 整段摘要）写完才回，
#: 实测撞过 ReadTimeout。管理员点了「解析」之后有 loading 遮罩挡着，等一两分钟可接受。
#: **部署在 nginx 后面时记得一并调大 `proxy_read_timeout`**（默认 60 秒），
#: 否则后端还在等、网关先 504 了
_PDF_TIMEOUT_SECONDS = 150.0
#: PDF 体积上限，与 OSS 文档通道一致（30MB）。这条不落 OSS，只在内存里过一道
MAX_PARSE_PDF_SIZE = 30 * 1024 * 1024


class PublicationMetaService:
    """
    成果发表的元数据抽取服务
    """

    @classmethod
    def _to_draft(cls, fields: dict[str, Any]) -> PublicationModel:
        """
        字段字典 → 回给后台表单的草稿

        引用文本在这里就拼好：后台「确定」时后端也会兜一次，但先填出来能让管理员
        在保存前看见并改掉（各刊格式要求不同）。

        :param fields: `publication_parse` 产出的字段字典
        :return: 草稿对象
        """
        fields = dict(fields)
        fields['citation_text'] = build_citation_text(fields)

        return PublicationModel(**fields)

    @classmethod
    async def _fetch_pubmed(cls, doi: str) -> dict[str, Any]:
        """
        按 DOI 查 PubMed，取回摘要与关键词

        两跳：`esearch` 用 `<doi>[DOI]` 检索出 PMID，`efetch` 取那条记录的 XML。

        **任何一步失败都返回空字典、不抛异常** —— 这是兜底路径：内网没出口、NCBI 限流、
        这篇没被 PubMed 收录（中文刊、会议摘要）都很正常，不该让整次解析报错，
        更不该让管理员对着一句「解析失败」发愣，而 Crossref 那份草稿其实已经能用了。

        出参里的 `ok` 区分「查通了但这篇没有」与「压根没查成」：前者该告诉用户去手填，
        后者多半是服务器没有外网出口 —— 两句话对运维的含义完全不同，不能混成一句。

        :param doi: 裸 DOI
        :return: parse_pubmed_xml 的出参，外加 `ok`；查不到或失败时各项为空
        """
        empty: dict[str, Any] = {'abstract': '', 'keywords': [], 'keywords_source': '', 'pmid': '', 'ok': False}
        try:
            async with httpx.AsyncClient(timeout=_PUBMED_TIMEOUT, follow_redirects=True) as client:
                # DOI 只作为检索词进 params，由 httpx 转义；主机是常量
                found = await client.get(
                    f'{_EUTILS_BASE}/esearch.fcgi',
                    params={'db': 'pubmed', 'term': f'{doi}[DOI]', 'retmode': 'json', **_EUTILS_IDENT},
                )
                if found.status_code != HTTP_200_OK:
                    logger.info(f'PubMed esearch 返回 {found.status_code}，跳过摘要补全')

                    return empty
                ids = ((found.json() or {}).get('esearchresult') or {}).get('idlist') or []
                if not ids:
                    # 查通了、这篇确实不在 PubMed（中文刊、会议摘要常见）：ok=True，
                    # 提示语据此说「都没有，请手填」而不是「没查通」
                    logger.info(f'PubMed 未收录 {doi}，跳过摘要补全')

                    return {**empty, 'ok': True}

                detail = await client.get(
                    f'{_EUTILS_BASE}/efetch.fcgi',
                    params={'db': 'pubmed', 'id': ids[0], 'retmode': 'xml', **_EUTILS_IDENT},
                )
                if detail.status_code != HTTP_200_OK:
                    logger.info(f'PubMed efetch 返回 {detail.status_code}，跳过摘要补全')

                    return empty
        except httpx.HTTPError as e:
            # 内网无外网出口时这条每次都会走到，压成 info：它不是故障
            logger.info(f'PubMed 请求失败（{type(e).__name__}），跳过摘要补全')

            return empty

        return {**parse_pubmed_xml(detail.text), 'ok': True}

    @classmethod
    async def parse_doi_services(cls, source: str) -> tuple[PublicationModel, str]:
        """
        按 DOI 拉一份元数据草稿：Crossref 打底，摘要与关键词由 PubMed 补

        :param source: DOI、`doi:10.x/y`、doi.org 链接，或地址里嵌着 DOI 的出版社页面
        :return: (草稿对象, 给管理员看的提示语)。提示语要说清「哪几项没拿到、
            关键词是不是 MeSH」—— 空着而不说明，用户会以为是解析坏了
        :raises ServiceException: 抠不出 DOI、Crossref 查不到、或网络失败
        """
        doi = extract_doi(source or '')
        if not doi:
            raise ServiceException(
                message='没能从这串内容里识别出 DOI。请粘贴 DOI（如 10.1016/j.ctim.2024.103041）'
                '或 doi.org 链接；没有 DOI 的成果请改用「上传 PDF 解析」或手动填写'
            )

        url = _CROSSREF_WORK_URL.format(doi=quote(doi, safe=''))
        try:
            async with httpx.AsyncClient(timeout=_CROSSREF_TIMEOUT, follow_redirects=True) as client:
                response = await client.get(url, headers={'User-Agent': _CROSSREF_UA, 'Accept': 'application/json'})
        except httpx.HTTPError as e:
            logger.warning(f'Crossref 请求失败：{type(e).__name__} {e}')
            raise ServiceException(message='连接 Crossref 失败，请稍后重试或手动填写') from e

        if response.status_code == HTTP_404_NOT_FOUND:
            raise ServiceException(message=f'Crossref 上查不到 DOI {doi}，请核对后重试，或手动填写')
        if response.status_code != HTTP_200_OK:
            logger.warning(f'Crossref 返回 {response.status_code}：{response.text[:300]}')
            raise ServiceException(message=f'Crossref 返回异常（HTTP {response.status_code}），请稍后重试或手动填写')

        message = (response.json() or {}).get('message') or {}
        if not message:
            raise ServiceException(message='Crossref 没有返回这条 DOI 的元数据，请手动填写')

        fields = from_crossref(message)
        if not fields.get('title'):
            # 标题都没有的话，这份草稿填回表单只会误导人
            raise ServiceException(message='Crossref 上这条记录没有标题，请手动填写')
        logger.info(f'Crossref 解析成功：{doi}')

        # Crossref 结构上给不了关键词，摘要也常常没有 —— 缺哪个补哪个，
        # **不覆盖 Crossref 已经给出的值**（出版社登记值优先）
        supplement = (
            await cls._fetch_pubmed(doi)
            if not fields.get('abstract') or not fields.get('keywords')
            else {'abstract': '', 'keywords': [], 'keywords_source': '', 'pmid': '', 'ok': True}
        )
        filled_abstract = False
        if not fields.get('abstract') and supplement.get('abstract'):
            fields['abstract'] = supplement['abstract']
            filled_abstract = True
        keywords_source = ''
        if not fields.get('keywords') and supplement.get('keywords'):
            fields['keywords'] = supplement['keywords']
            keywords_source = supplement.get('keywords_source') or ''
        if supplement.get('pmid'):
            logger.info(f'PubMed 补全（PMID {supplement["pmid"]}）：摘要={filled_abstract} 关键词={keywords_source or "无"}')

        return cls._to_draft(fields), cls._parse_note(
            fields, filled_abstract, keywords_source, pubmed_ok=bool(supplement.get('ok'))
        )

    @classmethod
    def _parse_note(
        cls, fields: dict[str, Any], filled_abstract: bool, keywords_source: str, pubmed_ok: bool = True
    ) -> str:
        """
        拼给管理员看的那句提示

        **缺什么要明说**：摘要与关键词空着时，用户看到的是「解析成功」加两个空框，
        会当成解析坏了 —— 而实际原因是这两项本来就没处拿，该做的是手填或改用 PDF 解析。

        「查通了但没有」与「压根没查通」要分开说：后者多半是服务器没有外网出口，
        那是运维要处理的事，混成一句话会让人一直以为是数据源没有。

        :param fields: 最终的字段字典
        :param filled_abstract: 摘要是不是 PubMed 补的
        :param keywords_source: 关键词来源（keyword=作者关键词 / mesh=MeSH 主题词 / 空=没补上）
        :param pubmed_ok: PubMed 那一跳是否走通（与「有没有查到」无关）
        :return: 提示语
        """
        notes: list[str] = []
        if filled_abstract:
            notes.append('摘要取自 PubMed')
        if keywords_source == 'keyword':
            notes.append('关键词取自 PubMed')
        elif keywords_source == 'mesh':
            # MeSH 是索引员事后打的受控词，不是作者写的关键词，展示前要让管理员知道
            notes.append('关键词为 PubMed 的 MeSH 主题词（非作者关键词），请酌情删改')
        missing = [
            label
            for label, ok in (('摘要', bool(fields.get('abstract'))), ('关键词', bool(fields.get('keywords'))))
            if not ok
        ]
        if missing:
            reason = '（Crossref 与 PubMed 都没有）' if pubmed_ok else '（Crossref 没有，PubMed 这次没连上）'
            notes.append(f'{"与".join(missing)}未能获取{reason}，请手填或改用「按 PDF 解析」')

        return '解析成功，请核对各字段后保存' + ('；' + '；'.join(notes) if notes else '')

    @classmethod
    async def parse_pdf_services(cls, query_db: AsyncSession, filename: str, data: bytes) -> PublicationModel:
        """
        从 PDF 首页文字里抽一份元数据草稿

        :param query_db: orm对象（模型池要查库）
        :param filename: 原始文件名，只用来取扩展名
        :param data: 文件字节
        :return: 草稿对象
        :raises ServiceException: PDF 解析不出文字、模型池不可用、或模型没给出 JSON
        """
        if len(data) > MAX_PARSE_PDF_SIZE:
            raise ServiceException(message=f'PDF 大小不能超过 {MAX_PARSE_PDF_SIZE // 1024 // 1024}MB')
        try:
            text = parse_manuscript(filename, data)
        except ManuscriptParseError as e:
            # 这一层的报错本来就是写给用户看的（含「扫描件请先做文字识别」这类下一步），直接透传
            raise ServiceException(message=str(e)) from e

        raw, model_label = await AiAssistService.complete(
            query_db,
            build_pdf_messages(text),
            max_tokens=_PDF_MAX_TOKENS,
            temperature=_PDF_TEMPERATURE,
            timeout=_PDF_TIMEOUT_SECONDS,
            failure_hint='PDF 元数据解析失败',
        )
        try:
            fields = parse_ai_json(raw)
        except ValueError as e:
            # 落**整段**原始输出，不是 raw[:300]：解析失败的现场只此一份，
            # 截到 300 字符时恰好看不到断在哪（踩过一次，只能靠报错的字符偏移反推）
            logger.warning(f'PDF 元数据解析失败（模型 {model_label}）。原始输出：\n{raw}')
            raise ServiceException(message=f'解析失败（{e}），请手动填写') from e

        if not fields.get('title'):
            raise ServiceException(message='没能从这份 PDF 里读出论文标题，请手动填写')
        logger.info(f'PDF 元数据解析成功（{model_label}）：{fields["title"][:60]}')

        return cls._to_draft(fields)
