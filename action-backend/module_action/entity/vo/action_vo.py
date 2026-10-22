import html
import re
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel
from pydantic_validation_decorator import NotBlank, Size, Xss

from exceptions.exception import ModelValidatorException

DupLevel = Literal['none', 'low', 'mod', 'high']


class ActionBaseModel(BaseModel):
    """
    官网模块公共配置：出入参一律驼峰，支持从 ORM 对象构造
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)


# ---------------------------------------------------------------- 新闻动态


class NewsModel(ActionBaseModel):
    """
    官网新闻动态
    """

    news_id: int | None = Field(default=None, description='新闻id')
    category_zh: str | None = Field(default=None, description='分类（中文）')
    category_en: str | None = Field(default=None, description='分类（英文）')
    title_zh: str | None = Field(default=None, description='标题（中文）')
    title_en: str | None = Field(default=None, description='标题（英文）')
    summary_zh: str | None = Field(default=None, description='摘要（中文）')
    summary_en: str | None = Field(default=None, description='摘要（英文）')
    content_zh: str | None = Field(default=None, description='正文（中文）')
    content_en: str | None = Field(default=None, description='正文（英文）')
    thumb_url: str | None = Field(default=None, description='缩略图地址')
    link_url: str | None = Field(default=None, description='跳转链接（站内路由或外部URL）')
    is_external: Literal['0', '1'] | None = Field(default=None, description='是否外部链接（0否 1是）')
    publish_date: date | None = Field(default=None, description='发布日期')
    is_top: Literal['0', '1'] | None = Field(default=None, description='是否置顶（0否 1是）')
    sort_num: int | None = Field(default=None, description='显示顺序')
    status: Literal['0', '1'] | None = Field(default=None, description='状态（0正常 1停用）')
    create_by: str | None = Field(default=None, description='创建者')
    create_time: datetime | None = Field(default=None, description='创建时间')
    update_by: str | None = Field(default=None, description='更新者')
    update_time: datetime | None = Field(default=None, description='更新时间')
    remark: str | None = Field(default=None, description='备注')

    @Xss(field_name='title_zh', message='标题不能包含脚本字符')
    @NotBlank(field_name='title_zh', message='中文标题不能为空')
    @Size(field_name='title_zh', min_length=0, max_length=300, message='中文标题不能超过300个字符')
    def get_title_zh(self) -> str | None:
        return self.title_zh

    def validate_fields(self) -> None:
        self.get_title_zh()


class NewsQueryModel(NewsModel):
    """
    新闻不分页查询模型
    """

    begin_time: str | None = Field(default=None, description='开始时间')
    end_time: str | None = Field(default=None, description='结束时间')


class NewsPageQueryModel(NewsQueryModel):
    """
    新闻分页查询模型
    """

    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


class DeleteNewsModel(BaseModel):
    """
    删除新闻模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    news_ids: str = Field(description='需要删除的新闻id，多个以逗号分隔')


# ---------------------------------------------------------------- 团队成员


class TeamMemberModel(ActionBaseModel):
    """
    官网团队成员

    简介分三层，前台各用各的：summary 上卡片、bio 与 contribution 上详情页。
    """

    member_id: int | None = Field(default=None, description='成员id')
    group_key: Literal['board', 'core'] | None = Field(
        default=None, description='所属组（board国际顾问委员会 core核心执行团队）'
    )
    name_zh: str | None = Field(default=None, description='姓名（中文）')
    name_en: str | None = Field(default=None, description='姓名（英文）')
    honorific: str | None = Field(default=None, description='称谓（Prof./Dr.）')
    title_zh: str | None = Field(default=None, description='职称/头衔（中文）')
    title_en: str | None = Field(default=None, description='职称/头衔（英文）')
    affiliation_zh: str | None = Field(default=None, description='所属机构（中文）')
    affiliation_en: str | None = Field(default=None, description='所属机构（英文）')
    role_zh: str | None = Field(default=None, description='在 ACTION 中的角色（中文）')
    role_en: str | None = Field(default=None, description='在 ACTION 中的角色（英文）')
    expertise_zh: str | None = Field(default=None, description='研究方向标签（中文，顿号分隔）')
    expertise_en: str | None = Field(default=None, description='研究方向标签（英文，分号分隔）')
    summary_zh: str | None = Field(default=None, description='一句话简介（中文）')
    summary_en: str | None = Field(default=None, description='一句话简介（英文）')
    bio_zh: str | None = Field(default=None, description='详细履历（中文）')
    bio_en: str | None = Field(default=None, description='详细履历（英文）')
    contribution_zh: str | None = Field(default=None, description='对 ACTION 的贡献（中文）')
    contribution_en: str | None = Field(default=None, description='对 ACTION 的贡献（英文）')
    avatar_url: str | None = Field(default=None, description='头像地址')
    homepage_url: str | None = Field(default=None, description='个人主页/学术档案链接')
    email: str | None = Field(default=None, description='联系邮箱')
    sort_num: int | None = Field(default=None, description='组内显示顺序')
    status: Literal['0', '1'] | None = Field(default=None, description='状态（0正常 1停用）')
    create_by: str | None = Field(default=None, description='创建者')
    create_time: datetime | None = Field(default=None, description='创建时间')
    update_by: str | None = Field(default=None, description='更新者')
    update_time: datetime | None = Field(default=None, description='更新时间')
    remark: str | None = Field(default=None, description='备注')

    @Xss(field_name='name_zh', message='姓名不能包含脚本字符')
    @NotBlank(field_name='name_zh', message='中文姓名不能为空')
    @Size(field_name='name_zh', min_length=0, max_length=200, message='中文姓名不能超过200个字符')
    def get_name_zh(self) -> str | None:
        return self.name_zh

    def validate_fields(self) -> None:
        self.get_name_zh()


class TeamMemberQueryModel(TeamMemberModel):
    """
    团队成员查询模型
    """

    keyword: str | None = Field(default=None, description='按姓名/机构/简介模糊搜索')


class TeamMemberPageQueryModel(TeamMemberQueryModel):
    """
    团队成员分页查询模型
    """

    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


class DeleteTeamMemberModel(BaseModel):
    """
    删除团队成员模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    member_ids: str = Field(description='需要删除的成员id，多个以逗号分隔')


# ---------------------------------------------------------------- 资源中心链接


class ResourceLinkModel(ActionBaseModel):
    """
    官网资源中心链接

    首页「国际报告规范组织与循证枢纽」一段的外链卡片。EQUATOR、Cochrane 这类专名
    中英两栏填同一串即可，`nameEn` 留空时前台按 `useBilingual` 的规则回落中文。
    """

    link_id: int | None = Field(default=None, description='资源id')
    name_zh: str | None = Field(default=None, description='名称（中文）')
    name_en: str | None = Field(default=None, description='名称（英文）')
    summary_zh: str | None = Field(default=None, description='一句话说明（中文）')
    summary_en: str | None = Field(default=None, description='一句话说明（英文）')
    url: str | None = Field(default=None, description='外部地址（前台一律新标签页打开）')
    logo_url: str | None = Field(default=None, description='标识图地址，留空则前台不画图')
    sort_num: int | None = Field(default=None, description='卡片显示顺序')
    status: Literal['0', '1'] | None = Field(default=None, description='状态（0正常 1停用）')
    create_by: str | None = Field(default=None, description='创建者')
    create_time: datetime | None = Field(default=None, description='创建时间')
    update_by: str | None = Field(default=None, description='更新者')
    update_time: datetime | None = Field(default=None, description='更新时间')
    remark: str | None = Field(default=None, description='备注')

    @Xss(field_name='name_zh', message='名称不能包含脚本字符')
    @NotBlank(field_name='name_zh', message='中文名称不能为空')
    @Size(field_name='name_zh', min_length=0, max_length=200, message='中文名称不能超过200个字符')
    def get_name_zh(self) -> str | None:
        return self.name_zh

    @NotBlank(field_name='url', message='链接地址不能为空')
    @Size(field_name='url', min_length=0, max_length=500, message='链接地址不能超过500个字符')
    def get_url(self) -> str | None:
        return self.url

    @field_validator('url')
    @classmethod
    def check_url(cls, v: str | None) -> str | None:
        """
        只收 http(s) 绝对地址。

        这个值直接进前台 `<a href>` 且带 `target="_blank"`，放开协议等于把
        `javascript:` 之类的注入面留给后台文本框；站内路径也不该走这里 ——
        本段陈列的就是外部组织与循证枢纽。
        """
        if v is None or v == '':
            return v
        url = v.strip()
        if not re.match(r'^https?://\S+$', url):
            raise ModelValidatorException(message='链接地址必须是以 http:// 或 https:// 开头的完整外部地址')

        return url

    def validate_fields(self) -> None:
        self.get_name_zh()
        self.get_url()


class ResourceLinkQueryModel(ResourceLinkModel):
    """
    资源中心链接查询模型
    """

    keyword: str | None = Field(default=None, description='按名称/说明/地址模糊搜索')


class ResourceLinkPageQueryModel(ResourceLinkQueryModel):
    """
    资源中心链接分页查询模型
    """

    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


class DeleteResourceLinkModel(BaseModel):
    """
    删除资源中心链接模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    link_ids: str = Field(description='需要删除的资源id，多个以逗号分隔')


# ---------------------------------------------------------------- 成果发表

#: 一篇论文最多录多少位作者 / 机构 / 关键词。上限不是为了省空间，是为了让「解析出来的
#: 一坨脏数据」在入库前就撞墙 —— PDF 解析偶尔会把参考文献整段当成作者名塞回来
MAX_PUBLICATION_AUTHORS = 300
MAX_PUBLICATION_AFFILIATIONS = 100
MAX_PUBLICATION_KEYWORDS = 50
#: 摘要上限。正式期刊摘要在 3000 字符内，给到 2 万是留给带结构化小标题的长摘要
MAX_PUBLICATION_ABSTRACT_CHARS = 20000


def _assert_http_url(value: str | None, field_label: str) -> str | None:
    """
    校验「会直接进 `<a href>` / `<img src>` / `<iframe src>` 的地址」只收 http(s) 绝对地址

    与 `ResourceLinkModel.check_url` 同一个理由：这些值是后台文本框写进来、
    原样吐给公开页面的，放开协议等于把 `javascript:` 的注入面留在后台。
    站内相对路径也不放 —— 后台与官网是两个域，相对路径在后台预览时必然 404。

    :param value: 待校验地址
    :param field_label: 报错时显示的字段名
    :return: 去掉首尾空白的地址
    :raise ModelValidatorException: 不是 http(s) 绝对地址
    """
    if value is None or value.strip() == '':
        return ''
    url = value.strip()
    if not re.match(r'^https?://\S+$', url):
        raise ModelValidatorException(message=f'{field_label}必须是以 http:// 或 https:// 开头的完整地址')

    return url


class PublicationAuthorModel(ActionBaseModel):
    """
    一位作者

    `affiliation_index` 是 `PublicationModel.affiliations` 的**下标**（0 开始），
    前台按它渲染姓名右上角的机构角标。没标机构时为 None，不是 0 ——
    0 是「第 1 个机构」，兜底成 0 会给每位作者凭空挂上第一家单位。
    """

    #: 与本模块其余模型不同，这一对额外开了 `populate_by_name`：这两个模型除了
    #: 接 HTTP 入参，还要在服务层用 **snake_case 字段名**直接构造（解析层产出的字典、
    #: 从库里 JSON 列读回来的字典）。pydantic v2 在只有 alias 时对多余的 snake_case 键
    #: 是**静默忽略**而不是报错 —— 不开这个开关，`PublicationModel(**fields)`
    #: 会安静地得到一个所有字段都是 None 的空模型，且没有任何异常提示。
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(default='', description='姓名（发表原文，逐字）')
    affiliation_index: int | None = Field(default=None, description='所属机构在 affiliations 中的下标，未标注时为 None')


class PublicationModel(ActionBaseModel):
    """
    官网成果发表（论文）

    **没有 `*_zh`/`*_en` 双语列，这是有意的**：标题/作者/期刊/摘要是发表原文，
    同时也是引用信息，译一遍就既检索不到也引用不了，中英两种界面显示的都是它。
    页面上的栏目标题与按钮文字仍走 i18n + `action_site_text`。

    `authors` / `affiliations` / `keywords` 在库里是 JSON 文本，
    转换由 `PublicationService` 成对完成，本模型对外一律是结构化的列表。
    """

    #: 理由见 PublicationAuthorModel 上那段注释（服务层要用 snake_case 直接构造）
    model_config = ConfigDict(populate_by_name=True)

    publication_id: int | None = Field(default=None, description='成果id')
    title: str | None = Field(default=None, description='论文标题（发表原文）')
    authors: list[PublicationAuthorModel] | None = Field(default=None, description='作者列表，顺序即署名顺序')
    affiliations: list[str] | None = Field(default=None, description='机构列表，下标对应作者的 affiliationIndex')
    abstract: str | None = Field(default=None, description='摘要（纯文本）')
    keywords: list[str] | None = Field(default=None, description='关键词列表')
    journal: str | None = Field(default=None, description='期刊名称')
    volume: str | None = Field(default=None, description='卷')
    issue: str | None = Field(default=None, description='期')
    pages: str | None = Field(default=None, description='页码')
    publication_year: int | None = Field(default=None, description='发表年份')
    doi: str | None = Field(default=None, description='DOI')
    source_url: str | None = Field(default=None, description='出版社/期刊页面地址')
    pdf_url: str | None = Field(default=None, description='PDF 全文地址')
    cover_image_url: str | None = Field(default=None, description='配图/封面地址')
    citation_text: str | None = Field(default=None, description='引用文本，留空则由后端自动生成')
    sort_num: int | None = Field(default=None, description='同年内的显示顺序')
    status: Literal['0', '1'] | None = Field(default=None, description='状态（0正常 1停用）')
    create_by: str | None = Field(default=None, description='创建者')
    create_time: datetime | None = Field(default=None, description='创建时间')
    update_by: str | None = Field(default=None, description='更新者')
    update_time: datetime | None = Field(default=None, description='更新时间')
    remark: str | None = Field(default=None, description='备注')

    @field_validator('doi')
    @classmethod
    def check_doi(cls, v: str | None) -> str | None:
        """
        DOI 收敛成裸标识符（`10.xxxx/yyyy`），不收整条 URL。

        前台是 `https://doi.org/` + 本列拼出来的链接，存成 `https://doi.org/10.x/y`
        会拼出 `https://doi.org/https://doi.org/10.x/y` 这种死链。后台粘整条链接是常态，
        所以这里就地剥掉前缀，而不是报错让用户自己删。
        """
        if not v:
            return v
        doi = re.sub(r'^\s*(?:https?://)?(?:dx\.)?doi\.org/', '', v.strip(), flags=re.IGNORECASE)
        doi = re.sub(r'^\s*doi:\s*', '', doi, flags=re.IGNORECASE).strip()

        return doi

    @field_validator('source_url')
    @classmethod
    def check_source_url(cls, v: str | None) -> str | None:
        return _assert_http_url(v, '原文链接')

    @field_validator('pdf_url')
    @classmethod
    def check_pdf_url(cls, v: str | None) -> str | None:
        return _assert_http_url(v, 'PDF 全文地址')

    @field_validator('cover_image_url')
    @classmethod
    def check_cover_image_url(cls, v: str | None) -> str | None:
        return _assert_http_url(v, '配图地址')

    @field_validator('authors')
    @classmethod
    def check_authors(cls, v: list[PublicationAuthorModel] | None) -> list[PublicationAuthorModel] | None:
        """空姓名的行直接丢掉（后台点了「添加作者」又没填），并卡一道条数上限。"""
        if v is None:
            return v
        rows = [a for a in v if (a.name or '').strip()]
        if len(rows) > MAX_PUBLICATION_AUTHORS:
            raise ModelValidatorException(message=f'作者不能超过 {MAX_PUBLICATION_AUTHORS} 位')
        for author in rows:
            author.name = author.name.strip()

        return rows

    @field_validator('affiliations', 'keywords')
    @classmethod
    def check_str_list(cls, v: list[str] | None) -> list[str] | None:
        """同上：去空、去首尾空白。上限分别在下面的 validate_fields 里报得更具体。"""
        if v is None:
            return v

        return [s.strip() for s in v if s and s.strip()]

    @Xss(field_name='title', message='标题不能包含脚本字符')
    @NotBlank(field_name='title', message='标题不能为空')
    @Size(field_name='title', min_length=0, max_length=500, message='标题不能超过500个字符')
    def get_title(self) -> str | None:
        return self.title

    @Size(field_name='journal', min_length=0, max_length=300, message='期刊名称不能超过300个字符')
    def get_journal(self) -> str | None:
        return self.journal

    def validate_fields(self) -> None:
        self.get_title()
        self.get_journal()
        if self.abstract and len(self.abstract) > MAX_PUBLICATION_ABSTRACT_CHARS:
            raise ModelValidatorException(message=f'摘要不能超过 {MAX_PUBLICATION_ABSTRACT_CHARS} 个字符')
        if self.affiliations and len(self.affiliations) > MAX_PUBLICATION_AFFILIATIONS:
            raise ModelValidatorException(message=f'机构不能超过 {MAX_PUBLICATION_AFFILIATIONS} 个')
        if self.keywords and len(self.keywords) > MAX_PUBLICATION_KEYWORDS:
            raise ModelValidatorException(message=f'关键词不能超过 {MAX_PUBLICATION_KEYWORDS} 个')
        # 机构下标越界 = 前台渲染出一个指不到任何机构的角标。后台是「删机构时重排下标」的，
        # 但接口不能假定调用方做过这件事
        limit = len(self.affiliations or [])
        for author in self.authors or []:
            if author.affiliation_index is not None and not 0 <= author.affiliation_index < limit:
                raise ModelValidatorException(message=f'作者「{author.name}」挂的机构序号超出机构列表范围')


class PublicationQueryModel(ActionBaseModel):
    """
    成果发表查询模型

    **不继承 `PublicationModel`**（其余几张表的 QueryModel 都是那么写的）：这个模型
    要以 `Annotated[..., Query()]` 的形式当查询参数用，而 FastAPI 的查询参数模型只支持
    标量与标量数组 —— 继承过来的 `authors: list[PublicationAuthorModel]` 不是那样的东西。
    查询能用到的本来也就这几个字段。
    """

    title: str | None = Field(default=None, description='按标题模糊搜索')
    doi: str | None = Field(default=None, description='按 DOI 模糊搜索')
    status: Literal['0', '1'] | None = Field(default=None, description='状态（0正常 1停用）')
    keyword: str | None = Field(default=None, description='按标题/作者/期刊/关键词/DOI 模糊搜索')
    year: int | None = Field(default=None, description='按发表年份过滤')


class PublicationPageQueryModel(PublicationQueryModel):
    """
    成果发表分页查询模型
    """

    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


class PublicationYearModel(BaseModel):
    """
    年份词表的一行（官网列表页的年份下拉）
    """

    model_config = ConfigDict(alias_generator=to_camel)

    year: int | None = Field(default=None, description='发表年份，未标注年份的记录为 None')
    count: int = Field(default=0, description='该年份下已发布的成果数')


class PublicationParseModel(BaseModel):
    """
    「按 DOI 解析」的入参

    只认 DOI 与 doi.org 链接，**不做任意 URL 抓网页**：那是让服务器去 GET 调用方给的
    地址，等于把后台文本框变成 SSRF 入口（内网元数据服务、127.0.0.1 上的其它服务）。
    Crossref 是固定的一个外部主机，且只吐结构化元数据，没有这层风险。
    """

    model_config = ConfigDict(alias_generator=to_camel)

    source: str = Field(description='DOI 或包含 DOI 的链接（如 https://doi.org/10.1016/j.ctim.2024.103041）')


class DeletePublicationModel(BaseModel):
    """
    删除成果发表模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    publication_ids: str = Field(description='需要删除的成果id，多个以逗号分隔')


# ---------------------------------------------------------------- 站点文案


# 文案里允许出现的标签。原始 i18n 词条用到的是 span/b/i（排版强调）与 svg/circle/path（行内小图标），
# 另加 <a>：页脚的 ICP 备案号按工信部要求必须是指向 beian.miit.gov.cn 的可点链接，
# 这类「链接就长在一句话中间」的场景没法拆成 action_resource_link 那样的专表。
# 白名单就按实照列，不多放一个。放开等于把「后台文本框」变成「往公开页面注入任意 HTML」的口子 ——
# 这些文案是以 v-html 渲染的（nuxt.config.ts 的 escapeHtml: false），不是被转义的纯文本。
ALLOWED_TEXT_TAGS = frozenset(
    {'a', 'span', 'b', 'i', 'em', 'strong', 'br', 'sup', 'sub', 'small', 'svg', 'circle', 'path'}
)

# 事件处理属性（onclick/onload/onerror…）。svg 在白名单里，没有这一道就等于放行 <svg onload=...>。
_EVENT_ATTR_RE = re.compile(r'\son[a-z]+\s*=', re.IGNORECASE)
# 伪协议兜底。真正拦 <a href> 的是下面的 _HREF_RE + _SAFE_HREF_RE，这条只多挡一层裸文本形态。
_BAD_SCHEME_RE = re.compile(r'(javascript|vbscript|data)\s*:', re.IGNORECASE)
_TAG_NAME_RE = re.compile(r'<\s*/?\s*([a-zA-Z][a-zA-Z0-9]*)')
# 取出每个 href 的值（双引号/单引号/裸值三种写法）
_HREF_RE = re.compile(r'href\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))', re.IGNORECASE)
# href 只放行这几种：站外 http(s) 绝对地址、站内绝对路径、锚点、邮件。
# 协议相对地址（//evil.com）不放 —— 它长得像路径，实际是跳站外。
_SAFE_HREF_RE = re.compile(r'^(?:https?://[^/]|/(?!/)|#|mailto:)', re.IGNORECASE)


def assert_safe_markup(value: str | None, field_label: str) -> None:
    """
    校验文案里的 HTML 只用了白名单标签，且不含事件属性与危险链接

    :param value: 待校验文案
    :param field_label: 报错时显示的字段名
    :return: None
    :raise ModelValidatorException: 命中任一禁止项
    """
    if not value or '<' not in value:
        return
    for tag in _TAG_NAME_RE.findall(value):
        if tag.lower() not in ALLOWED_TEXT_TAGS:
            raise ModelValidatorException(
                message=f'{field_label}含不允许的标签 <{tag}>，可用标签：' + '、'.join(sorted(ALLOWED_TEXT_TAGS))
            )
    if _EVENT_ATTR_RE.search(value):
        raise ModelValidatorException(message=f'{field_label}不能包含 on... 事件属性')
    for quoted, single, bare in _HREF_RE.findall(value):
        # 先解 HTML 实体再判：&#106;avascript:… 在浏览器里会还原成 javascript:，只匹配原文等于没判
        href = html.unescape(quoted or single or bare)
        # 去掉浏览器解析 URL 时会忽略的空白与控制字符（java\tscript: 同样是可执行的）
        href = re.sub(r'[\x00-\x20\x7f]', '', href)
        if not _SAFE_HREF_RE.match(href):
            raise ModelValidatorException(
                message=f'{field_label}的链接地址不合法：只能是 http(s):// 开头的完整网址、/ 开头的站内路径、#锚点或 mailto:'
            )
    if _BAD_SCHEME_RE.search(value):
        raise ModelValidatorException(message=f'{field_label}不能包含 javascript:/vbscript:/data: 伪协议')


class SiteTextModel(ActionBaseModel):
    """
    官网站点文案

    `textKey` 是前端模板里 `$t()` 的参数，由代码定义，后台不可增删也不可改键；
    可改的只有 `textZh` / `textEn`。`defaultZh` / `defaultEn` 是代码里的原始文案，只读，
    供后台对照与「还原默认」用。
    """

    text_id: int | None = Field(default=None, description='文案id')
    text_key: str | None = Field(default=None, description='i18n 键，如 index.s052')
    page_key: str | None = Field(default=None, description='所属分组（= text_key 首段）')
    page_label: str | None = Field(default=None, description='分组中文名')
    text_zh: str | None = Field(default=None, description='当前生效的中文文案')
    text_en: str | None = Field(default=None, description='当前生效的英文文案')
    default_zh: str | None = Field(default=None, description='代码里的中文默认值（只读）')
    default_en: str | None = Field(default=None, description='代码里的英文默认值（只读）')
    has_markup: Literal['0', '1'] | None = Field(default=None, description='默认值里含HTML标签（0否 1是）')
    sort_num: int | None = Field(default=None, description='显示顺序')
    create_by: str | None = Field(default=None, description='创建者')
    create_time: datetime | None = Field(default=None, description='创建时间')
    update_by: str | None = Field(default=None, description='更新者')
    update_time: datetime | None = Field(default=None, description='更新时间')
    remark: str | None = Field(default=None, description='备注')

    @field_validator('text_zh', 'text_en')
    @classmethod
    def check_markup(cls, v: str | None, info: Any) -> str | None:
        """
        文案落地后走 v-html，必须过标签白名单

        :param v: 待校验文案
        :param info: 字段上下文
        :return: 原值
        """
        assert_safe_markup(v, '中文文案' if info.field_name == 'text_zh' else '英文文案')

        return v

    @Size(field_name='text_zh', min_length=0, max_length=5000, message='中文文案不能超过5000个字符')
    def get_text_zh(self) -> str | None:
        return self.text_zh

    @Size(field_name='text_en', min_length=0, max_length=5000, message='英文文案不能超过5000个字符')
    def get_text_en(self) -> str | None:
        return self.text_en

    def validate_fields(self) -> None:
        self.get_text_zh()
        self.get_text_en()


class SiteTextQueryModel(SiteTextModel):
    """
    站点文案查询模型
    """

    keyword: str | None = Field(default=None, description='按键名/中英文案模糊搜索')
    only_changed: bool | None = Field(default=None, description='只看与默认值不同的（即后台改过的）')


class SiteTextPageQueryModel(SiteTextQueryModel):
    """
    站点文案分页查询模型
    """

    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=20, description='每页记录数')


class SiteTextOverridesModel(BaseModel):
    """
    官网公开接口的文案覆盖包

    只含**与默认值不同**的词条，键为完整 i18n 键（如 `index.s052`），前台在 i18n 之上 merge。
    一条都没改时两个字典都是空的 —— 这正是常态，也是它敢挂在每个页面上的原因。
    """

    model_config = ConfigDict(alias_generator=to_camel)

    zh: dict[str, str] = Field(default_factory=dict, description='中文覆盖项')
    en: dict[str, str] = Field(default_factory=dict, description='英文覆盖项')


class SiteTextGroupModel(ActionBaseModel):
    """
    站点文案分组（后台筛选下拉用）
    """

    page_key: str = Field(description='分组键（= text_key 首段）')
    page_label: str = Field(description='分组中文名')
    total: int = Field(description='该组词条总数')
    changed: int = Field(description='该组被改过的条数')


class SiteRebuildStateModel(BaseModel):
    """
    官网重新生成的执行状态
    """

    model_config = ConfigDict(alias_generator=to_camel)

    status: Literal['idle', 'running', 'success', 'failed', 'disabled'] = Field(description='当前状态')
    message: str = Field(default='', description='人类可读的说明或错误摘要')
    started_at: str = Field(default='', description='本次开始时间')
    finished_at: str = Field(default='', description='本次结束时间')
    started_by: str = Field(default='', description='触发人')


# ---------------------------------------------------------------- 报告规范目录


class GuidelineModel(ActionBaseModel):
    """
    官网报告规范目录
    """

    guideline_id: int | None = Field(default=None, description='规范id')
    code: str | None = Field(default=None, description='规范代号')
    name_zh: str | None = Field(default=None, description='名称（中文）')
    name_en: str | None = Field(default=None, description='名称（英文）')
    study_type: str | None = Field(
        default=None, description='适用研究类型（取 action_guideline_category.cat_key，写接口会校验存在）'
    )
    summary_zh: str | None = Field(default=None, description='简介（中文）')
    summary_en: str | None = Field(default=None, description='简介（英文）')
    version_zh: str | None = Field(default=None, description='版本（中文）')
    version_en: str | None = Field(default=None, description='版本（英文）')
    file_url_zh: str | None = Field(
        default=None, description='中文版下载地址（文件存阿里云 OSS，由后台上传；初始为空串）'
    )
    file_url_en: str | None = Field(
        default=None, description='英文版下载地址（文件存阿里云 OSS，由后台上传；初始为空串）'
    )
    external_url: str | None = Field(default=None, description='外部官方链接（如已发表共识的 DOI 或官方站点）')
    logo_url: str | None = Field(default=None, description='标识图地址')
    release_state: Literal['open', 'beta', 'soon'] | None = Field(default=None, description='开放状态')
    sort_num: int | None = Field(default=None, description='显示顺序')
    status: Literal['0', '1'] | None = Field(default=None, description='状态（0正常 1停用）')
    create_by: str | None = Field(default=None, description='创建者')
    create_time: datetime | None = Field(default=None, description='创建时间')
    update_by: str | None = Field(default=None, description='更新者')
    update_time: datetime | None = Field(default=None, description='更新时间')
    remark: str | None = Field(default=None, description='备注')

    @Xss(field_name='name_zh', message='名称不能包含脚本字符')
    @NotBlank(field_name='name_zh', message='中文名称不能为空')
    @Size(field_name='name_zh', min_length=0, max_length=300, message='中文名称不能超过300个字符')
    def get_name_zh(self) -> str | None:
        return self.name_zh

    @NotBlank(field_name='code', message='规范代号不能为空')
    @Size(field_name='code', min_length=0, max_length=64, message='规范代号不能超过64个字符')
    def get_code(self) -> str | None:
        return self.code

    def validate_fields(self) -> None:
        self.get_code()
        self.get_name_zh()


class GuidelineQueryModel(GuidelineModel):
    """
    报告规范查询模型
    """

    keyword: str | None = Field(default=None, description='按代号/名称/简介模糊搜索')


class GuidelinePageQueryModel(GuidelineQueryModel):
    """
    报告规范分页查询模型
    """

    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


class DeleteGuidelineModel(BaseModel):
    """
    删除报告规范模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    guideline_ids: str = Field(description='需要删除的规范id，多个以逗号分隔')


# ---------------------------------------------------------------- 报告规范分类


class GuidelineCategoryModel(ActionBaseModel):
    """
    官网报告规范分类

    规范页第①段筛选条的词表。`cat_key` 即 `GuidelineModel.study_type` 的取值域，
    前台按它把规范归到各个 chip 下，卡片上的「研究设计」标签也取本表的中英名称。
    """

    cat_id: int | None = Field(default=None, description='分类id')
    cat_key: str | None = Field(default=None, description='分类标识（取值即 action_guideline.study_type）')
    name_zh: str | None = Field(default=None, description='名称（中文）')
    name_en: str | None = Field(default=None, description='名称（英文）')
    icon_paths: str | None = Field(default=None, description='卡片图标的 SVG path d 属性，一行一条')
    sort_num: int | None = Field(default=None, description='筛选条中的显示顺序')
    status: Literal['0', '1'] | None = Field(default=None, description='状态（0正常 1停用）')
    create_by: str | None = Field(default=None, description='创建者')
    create_time: datetime | None = Field(default=None, description='创建时间')
    update_by: str | None = Field(default=None, description='更新者')
    update_time: datetime | None = Field(default=None, description='更新时间')
    remark: str | None = Field(default=None, description='备注')

    @Xss(field_name='name_zh', message='名称不能包含脚本字符')
    @NotBlank(field_name='name_zh', message='中文名称不能为空')
    @Size(field_name='name_zh', min_length=0, max_length=200, message='中文名称不能超过200个字符')
    def get_name_zh(self) -> str | None:
        return self.name_zh

    @NotBlank(field_name='cat_key', message='分类标识不能为空')
    @Size(field_name='cat_key', min_length=0, max_length=32, message='分类标识不能超过32个字符')
    def get_cat_key(self) -> str | None:
        return self.cat_key

    @field_validator('cat_key')
    @classmethod
    def check_cat_key(cls, v: str | None) -> str | None:
        """
        分类标识要进 URL 查询参数、也要当前端的 chip key 用，限死小写字母/数字/下划线/连字符。
        放开会让「同一个分类大小写写岔」变成两个筛不到一起的 chip。
        """
        if v is None or v == '':
            return v
        key = v.strip()
        if not re.fullmatch(r'[a-z0-9_-]+', key):
            raise ModelValidatorException(message='分类标识只能包含小写字母、数字、下划线与连字符')

        return key

    def validate_fields(self) -> None:
        self.get_cat_key()
        self.get_name_zh()


class GuidelineCategoryQueryModel(GuidelineCategoryModel):
    """
    报告规范分类查询模型
    """

    keyword: str | None = Field(default=None, description='按标识/名称模糊搜索')


class GuidelineCategoryPageQueryModel(GuidelineCategoryQueryModel):
    """
    报告规范分类分页查询模型
    """

    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


class DeleteGuidelineCategoryModel(BaseModel):
    """
    删除报告规范分类模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    cat_ids: str = Field(description='需要删除的分类id，多个以逗号分隔')


# ---------------------------------------------------------------- 规范 checklist 条目


class GuidelineItemModel(ActionBaseModel):
    """
    报告规范 checklist 条目

    一份规范可能含多张清单表（如 RCT = CONSORT 主表 + 摘要表 + STRICTA 表），
    part_no/part_zh/part_en 保留出处；页面按 sort_num 合并成一条流水清单。
    """

    item_id: int | None = Field(default=None, description='条目id')
    guideline_id: int | None = Field(default=None, description='所属规范id')
    part_no: int | None = Field(default=None, description='所属清单表序号')
    part_zh: str | None = Field(default=None, description='清单表标题（中文）')
    part_en: str | None = Field(default=None, description='清单表标题（英文）')
    domain_zh: str | None = Field(default=None, description='章节/主题/领域（中文）')
    domain_en: str | None = Field(default=None, description='章节/主题/领域（英文）')
    item_no_zh: str | None = Field(default=None, description='条目号（中文）')
    item_no_en: str | None = Field(default=None, description='条目号（英文）')
    content_zh: str | None = Field(default=None, description='条目内容（中文）')
    content_en: str | None = Field(default=None, description='条目内容（英文）')
    ext_label_zh: str | None = Field(default=None, description='扩展列列名（中文）')
    ext_label_en: str | None = Field(default=None, description='扩展列列名（英文）')
    extension_zh: str | None = Field(default=None, description='扩展/对照条目内容（中文）')
    extension_en: str | None = Field(default=None, description='扩展/对照条目内容（英文）')
    example_zh: str | None = Field(default=None, description='条目示例/范例（中文）')
    example_en: str | None = Field(default=None, description='条目示例/范例（英文）')
    require_level: Literal['0', '1'] | None = Field(default=None, description='填写要求（0必填 1条件填写/选填）')
    sort_num: int | None = Field(default=None, description='规范内显示顺序')
    status: Literal['0', '1'] | None = Field(default=None, description='状态（0正常 1停用）')
    create_by: str | None = Field(default=None, description='创建者')
    create_time: datetime | None = Field(default=None, description='创建时间')
    update_by: str | None = Field(default=None, description='更新者')
    update_time: datetime | None = Field(default=None, description='更新时间')
    remark: str | None = Field(default=None, description='备注')

    @Xss(field_name='content_zh', message='条目内容不能包含脚本字符')
    @NotBlank(field_name='content_zh', message='条目中文内容不能为空')
    def get_content_zh(self) -> str | None:
        return self.content_zh

    @Size(field_name='item_no_zh', min_length=0, max_length=64, message='条目号不能超过64个字符')
    def get_item_no_zh(self) -> str | None:
        return self.item_no_zh

    def validate_fields(self) -> None:
        self.get_content_zh()
        self.get_item_no_zh()


class GuidelineItemQueryModel(GuidelineItemModel):
    """
    规范条目查询模型
    """

    guideline_code: str | None = Field(default=None, description='规范代号（按代号取条目，公开接口用）')
    keyword: str | None = Field(default=None, description='按条目内容/领域模糊搜索')


class GuidelineItemPageQueryModel(GuidelineItemQueryModel):
    """
    规范条目分页查询模型
    """

    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


class DeleteGuidelineItemModel(BaseModel):
    """
    删除规范条目模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    item_ids: str = Field(description='需要删除的条目id，多个以逗号分隔')


# ---------------------------------------------------------------- checklist 逐条校验（报告助手第三步）

#: 校验任务的状态取值域。与 `tools/common` 的任务状态、SRD 的 `SrdRunStatus` 同一套词
ReviewRunStatus = Literal['pending', 'running', 'completed', 'failed', 'stopped']

#: 校验记录的用途。`import` 那一次跑完会回填草稿条目，`check` 不会
ReviewPurpose = Literal['check', 'import']

#: 稿件字数下限，与 worker 的 `MIN_MANUSCRIPT_CHARS` 对齐。低于这个数判不出东西，
#: 白跑几十次模型调用 —— 第三步的粘贴口与第二步的导入口共用它
MIN_MANUSCRIPT_CHARS = 200
#: 稿件字数上限，与算法的 max_chars 对齐。超出直接回绝而不是默默截断
MAX_MANUSCRIPT_CHARS = 300000


class ChecklistReviewSubmitModel(BaseModel):
    """
    提交稿件做 checklist 逐条校验

    公开接口的入参，字段约束直接写在 Field 上（与 CollabRequestSubmitModel 一致，由 pydantic
    自动校验，不走 @ValidateFields）。

    014 起稿件正文**随任务台账一并落库**，用户可按历史回看、也可随时删除（删除是真删正文）。
    口径变更的理由见 `sql/014-action-report-review-history-pg.sql` 的文件头。
    """

    model_config = ConfigDict(alias_generator=to_camel)

    guideline_code: str = Field(min_length=1, max_length=64, description='规范代号，如 STRICTA')
    manuscript: str = Field(
        min_length=MIN_MANUSCRIPT_CHARS, max_length=MAX_MANUSCRIPT_CHARS, description='稿件全文'
    )
    locale: Literal['zh', 'en'] = Field(default='zh', description='条目与结论使用的语言')
    #: 稿件来自第二步那份初稿时带上，第四步的工作清单据此认领这次判定。
    #: 外部粘贴的稿件不带 —— 它没有草稿可挂，但**照样进历史**（这是 014 与旧口径的分野）
    draft_id: int | None = Field(default=None, description='稿件所属草稿id，仅当稿件来自第二步初稿时带')


class ChecklistReviewSubmitResultModel(BaseModel):
    """
    提交后的回执

    **`reviewId` 是这次改造的关键**：任务一提交台账就已落库，前端拿着它就能在刷新之后
    重新找回这次校验 —— 014 之前提交只回一个 session_id，而它只活在前端内存里，
    刷一下页面这次任务就再也找不回来了（Redis 里明明还躺着结果）。
    """

    model_config = ConfigDict(alias_generator=to_camel)

    session_id: str = Field(description='worker任务id')
    review_id: int = Field(description='校验记录id')


class ChecklistReviewStateModel(BaseModel):
    """
    校验任务的轮询快照

    `status` 与进度来自 worker，`reviewId` 来自业务库 —— 轮询接口在拿到终态的那一刻
    顺手把结果落库（同 SRD，理由见 `ChecklistReviewService.review_state_services`）。
    """

    model_config = ConfigDict(alias_generator=to_camel)

    session_id: str = Field(description='任务id')
    review_id: int | None = Field(default=None, description='校验记录id')
    status: str = Field(description='pending/running/completed/failed/stopped')
    progress_current: int = Field(default=0, description='当前进度')
    progress_total: int = Field(default=100, description='进度总量')
    message: str = Field(default='', description='当前阶段说明')
    error: str = Field(default='', description='失败原因')
    result: dict | None = Field(default=None, description='完成后的判定结果')


# ---------------------------------------------------------------- 报告草稿（报告助手第二步）
#
# 草稿正文是用户未发表的研究内容，只进业务库、不进 OSS（那个桶整桶公共读）。
# 与第三步刻意不落稿件的取舍不同：第三步的稿件是过路数据，这里的草稿是用户
# 明确要求存下来的东西，不存反而是丢数据。

#: 单条条目正文的上限。checklist 一条应答通常几十到几百字，两万字符足够一条写成小节；
#: 不设上限的话，一次保存就能往库里灌任意大小的文本
MAX_DRAFT_ITEM_CHARS = 20000
#: 一次保存最多带多少条。现有最长的规范 SPIRIT 是 79 条，200 是留足余量的硬闸。
#: 这个数直接决定单次请求体的上限（200 × 20000 字符 ≈ 4MB），而保存是自动触发的高频接口，
#: 定得越松、被拒的那些条目就越是「先完整解析一遍再丢掉」的纯开销
MAX_DRAFT_ITEMS = 200


class ReportDraftItemModel(ActionBaseModel):
    """
    草稿里一条 checklist 条目的正文
    """

    item_id: int = Field(description='所应答的 checklist 条目id')
    content: str = Field(default='', max_length=MAX_DRAFT_ITEM_CHARS, description='用户为该条目写的正文')


class ReportDraftModel(ActionBaseModel):
    """
    报告草稿

    列表与详情共用：列表不带 items（一份草稿几十条正文，列表页不需要），详情带。
    完成度四个计数由服务层现算 —— 存冗余计数就要在每次保存、每次后台改条目
    填写要求时同步维护，算一遍的成本远低于维护一致性的成本。
    """

    draft_id: int | None = Field(default=None, description='草稿id')
    guideline_id: int | None = Field(default=None, description='所依据的报告规范id')
    guideline_code: str | None = Field(default=None, description='规范代号，如 STRICTA')
    study_type_key: str | None = Field(default=None, description='第一步判定的研究类型')
    title: str | None = Field(default=None, description='草稿名称')
    #: 导入的草稿（带原稿）。第四步「整篇成文」会整篇重写原稿，前端据此先确认一次；第五步据此默认导出原稿写回
    has_source: bool = Field(default=False, description='是否导入的草稿')
    #: 纳入的清单表。**空 = 全部纳入**（老草稿、新草稿的默认值）。下面四个完成度计数只算纳入的表
    parts: list[int] = Field(default_factory=list, description='纳入的清单表序号（part_no），空=全部纳入')
    items: list[ReportDraftItemModel] = Field(default_factory=list, description='逐条目正文（仅详情返回）')
    item_total: int = Field(default=0, description='该规范（纳入的清单表内）的条目总数')
    filled_count: int = Field(default=0, description='已填写的条目数')
    required_total: int = Field(default=0, description='必填条目数')
    required_filled: int = Field(default=0, description='已填写的必填条目数')
    create_time: datetime | None = Field(default=None, description='创建时间')
    update_time: datetime | None = Field(default=None, description='更新时间')


class ReportDraftCreateModel(BaseModel):
    """
    新建草稿的入参
    """

    model_config = ConfigDict(alias_generator=to_camel)

    guideline_code: str = Field(min_length=1, max_length=64, description='规范代号，如 STRICTA')
    study_type_key: str = Field(default='', max_length=32, description='第一步判定的研究类型，仅作留档')
    title: str = Field(default='', max_length=300, description='草稿名称，留空由后端起一个')


class DraftImportResultModel(BaseModel):
    """
    导入已有稿件的回执

    导入是**异步**的：建草稿与存原稿是同步完成的（所以立刻有 `draftId`），而「哪些条目
    被覆盖了」要跑一遍条目映射，那是几分钟级的 worker 任务，前端拿 `sessionId` 轮询。

    轮询走的就是第三步那个口（`GET /checklist-review/{session_id}`）—— 导入与校验是
    同一套 worker、同一个引擎、同一张结果表，区别只在 `purpose='import'` 时跑完会
    **回填草稿条目**。
    """

    model_config = ConfigDict(alias_generator=to_camel)

    draft_id: int = Field(description='新建的草稿id')
    session_id: str = Field(description='条目映射任务id，用它轮询进度')
    review_id: int = Field(description='映射任务的记录id')
    source_name: str = Field(default='', description='原始文件名')
    source_lines: int = Field(default=0, description='原稿有效行数')
    char_count: int = Field(default=0, description='原稿字符数')


class ReportDraftSaveModel(BaseModel):
    """
    保存草稿的入参

    **整体覆盖语义**：传进来的 items 就是这份草稿的全部正文，没带上的条目会被清空。
    前端每次都提交完整的编辑态，不做增量 patch —— 增量在「用户删掉了一条内容」
    这件事上无法与「这次没带这条」区分开。
    """

    model_config = ConfigDict(alias_generator=to_camel)

    title: str = Field(default='', max_length=300, description='草稿名称')
    items: list[ReportDraftItemModel] = Field(
        default_factory=list, max_length=MAX_DRAFT_ITEMS, description='逐条目正文（整体覆盖）'
    )
    #: 纳入的清单表。**不传 = 这次不改**（与 items 的整体覆盖语义不同：自动保存每次都带 items，
    #: 而选用哪几张表是另一个动作，不该被一次没带它的保存冲掉）。**传空列表 = 全部纳入**
    parts: list[int] | None = Field(default=None, max_length=20, description='纳入的清单表序号；不传=不改')


class ReportDraftComposeModel(BaseModel):
    """
    合成出来的报告初稿
    """

    model_config = ConfigDict(alias_generator=to_camel)

    draft_id: int = Field(description='草稿id')
    text: str = Field(description='初稿正文（纯文本，可直接送第三步校验）')
    char_count: int = Field(default=0, description='正文字符数')
    missing_required: int = Field(default=0, description='仍未填写的必填条目数')
    #: 以下只对导入的草稿有意义：初稿是从原稿出发、把改过的条目写回原处生成的（manuscript_rebuild）
    from_source: bool = Field(default=False, description='是否按原稿重建（导入的草稿）')
    keeps_layout: bool = Field(default=False, description='是否保留了原稿的图片、表格与样式（有原文件才能）')
    replaced: int = Field(default=0, description='原位替换的条目数')
    inserted: int = Field(default=0, description='插入的新条目数（导入时没找到位置）')
    appended: int = Field(default=0, description='与未改条目共用段落或位于表格中、改为追加的条目数')
    removed: int = Field(default=0, description='被清空、原段落已删的条目数')
    images: int = Field(default=0, description='稿件中的图片数')
    tables: int = Field(default=0, description='稿件中的表格数')


# ---------------------------------------------------------------- 第三步判定 · 第四步改写

#: 逐条判定的取值域。与 `tools/checklist_worker_tool` 的输出、前台的三档色阶一一对应
VerdictStatus = Literal['reported', 'vague', 'missing']

#: 第四步能对一条条目做的三件事。
#: continue 续写（据关键词补完这一条）· polish 润色（改写已有正文）· translate 中译英
AssistAction = Literal['continue', 'polish', 'translate', 'refine']

#: 润色风格。与前台那组风格 chip 一一对应；续写与翻译不看这个值
AssistStyle = Literal['', 'rigorous', 'concise', 'critical']

#: 单次改写的输入上限。一条 checklist 应答通常几百字，五千字符足够，
#: 同时挡住「把整篇稿子塞进来当 prompt」——那是按 token 计费的
MAX_ASSIST_INPUT_CHARS = 5000


class ReviewVerdictModel(BaseModel):
    """
    一条 checklist 条目的校验判定

    `reason` 是模型对这一条的判断说明，`evidence` 才是稿件里的逐字片段。
    014 起 evidence 随稿件一起落库（口径变更的理由见
    `sql/014-action-report-review-history-pg.sql` 的文件头）。
    """

    model_config = ConfigDict(alias_generator=to_camel)

    item_id: int = Field(description='checklist条目id')
    status: VerdictStatus = Field(description='判定（reported / vague / missing）')
    reason: str = Field(default='', max_length=2000, description='判定说明（模型的判断，不是稿件摘抄）')
    evidence: str = Field(default='', max_length=500, description='判定引用的稿件原文片段')
    lines: str = Field(default='', max_length=200, description='报告于第几行，逗号分隔')
    located: str = Field(
        default='', max_length=8, description='引文回原文核对：yes / partial / no / 空（no 时前台提示人工核对）'
    )


class ReportReviewModel(ActionBaseModel):
    """
    一次校验记录

    两处在用，字段各取所需：**第四步的工作清单**只看 verdicts 里的 status/reason，
    **第三步的历史回看**还要 manuscript 与 evidence 才能还原整屏。
    """

    review_id: int | None = Field(default=None, description='校验记录id')
    draft_id: int | None = Field(default=None, description='被校验的草稿id；外部粘贴的稿件为空')
    guideline_id: int | None = Field(default=None, description='所依据的报告规范id')
    guideline_code: str = Field(default='', description='报告规范代号')
    session_id: str = Field(default='', description='worker会话id，仅供排障对账')
    run_status: ReviewRunStatus = Field(default='completed', description='任务状态')
    error_msg: str = Field(default='', description='失败原因')
    progress: int = Field(default=0, description='进度百分比0-100')
    models: str = Field(default='', description='实际出结果的模型')
    locale: str = Field(default='zh', description='判定语言（zh/en）')
    char_count: int = Field(default=0, description='稿件字符数')
    item_total: int = Field(default=0, description='该规范的条目总数')
    completeness: int = Field(default=0, description='完整度百分比0-100')
    reported: int = Field(default=0, description='已报告条目数')
    vague: int = Field(default=0, description='描述模糊条目数')
    missing: int = Field(default=0, description='未报告条目数')
    line_count: int = Field(default=0, description='稿件行数')
    truncated: bool = Field(default=False, description='稿件是否被截断')
    manuscript: str = Field(default='', description='稿件正文（仅详情返回；已删除的记录为空）')
    #: 全稿一致性结果原样透传（库里存的就是引擎那份 JSON）。**不在这里定死结构** ——
    #: 它的形状跟着 `engine/consistency.py` 的规则表走，写成 Model 就要跟着引擎版本改一遍
    consistency: dict | None = Field(default=None, description='全稿一致性判定结果')
    errors: list[str] = Field(
        default_factory=list, description='部分判定未完成的说明；非空时前台提示「部分判定未完成，建议重新校验」'
    )
    verdicts: list[ReviewVerdictModel] = Field(default_factory=list, description='逐条判定')
    create_time: datetime | None = Field(default=None, description='提交时间')
    finish_time: datetime | None = Field(default=None, description='完成时间')


class ReportReviewHistoryModel(ActionBaseModel):
    """
    「我的校验历史」列表行

    **不带 verdicts，更不带 manuscript**：一次校验最多 282 条判定加一整篇稿件，
    列表页一条都用不上，带上等于每次开页面拉几 MB。点开某一条时才走详情口。
    """

    review_id: int | None = Field(default=None, description='校验记录id')
    session_id: str = Field(default='', description='worker会话id，仅供排障对账')
    draft_id: int | None = Field(default=None, description='被校验的草稿id；外部粘贴的稿件为空')
    guideline_code: str = Field(default='', description='报告规范代号')
    run_status: ReviewRunStatus = Field(default='pending', description='任务状态')
    error_msg: str = Field(default='', description='失败原因')
    progress: int = Field(default=0, description='进度百分比0-100')
    char_count: int = Field(default=0, description='稿件字符数')
    item_total: int = Field(default=0, description='该规范的条目总数')
    completeness: int = Field(default=0, description='完整度百分比0-100')
    reported: int = Field(default=0, description='已报告条目数')
    vague: int = Field(default=0, description='描述模糊条目数')
    missing: int = Field(default=0, description='未报告条目数')
    create_time: datetime | None = Field(default=None, description='提交时间')
    finish_time: datetime | None = Field(default=None, description='完成时间')


class AssistRequestModel(BaseModel):
    """
    第四步：续写 / 润色 / 中译英

    ## 两种模式，`draft_id` 有没有决定走哪条

    **独立模式（默认）**：用户自己填关键词或粘一段正文，`guideline_code` 只用来告诉模型
    「按哪份规范写」。这是《智能报告辅助工具.docx》第 4 节的字面形态 —— 那一节四项功能
    （续写 / 背景生成 / 润色 / 翻译）的输入全都是用户直接给的，没有一项依赖第二步的草稿
    或第三步的判定。**曾经强制要求 draft_id + item_id 是个设计错误**：文档那句「遵循
    STRICTA 条目规范」要的是「知道按哪份规范写」，而那个信息第一步就给了；把它读成
    「必须站在某一条上」，就把已经写好稿、直接来第三步的用户整个挡在了第四步之外。

    **草稿模式**：带上 `draft_id` + `item_id`，条目要求、已写正文、第三步对这一条的判定
    都由服务层从库里取，改完还能「采用」写回草稿条目。这是有草稿时的快捷方式，不是前提。

    ## 安全边界

    `text` 是用户自己手打/粘贴的内容，收进来没有问题；**不能收的是「按 id 去库里捞」的
    那一类入参**（`draft_id` / `item_id` 仍旧只用来查，且查之前校验归属）——
    前端能指定 id 就意味着能拿别人的草稿当 prompt。条目要求也一律从库里取、不由前端传，
    否则它会变成一个可伪造的任意指令注入口。
    """

    model_config = ConfigDict(alias_generator=to_camel)

    draft_id: int | None = Field(default=None, description='所属草稿id；独立模式不传')
    item_id: int | None = Field(default=None, description='要改写的 checklist 条目id；独立模式可不传')
    guideline_code: str = Field(default='', max_length=64, description='按哪份规范写，取自第一步')
    #: 独立模式下待润色/翻译的正文，或续写时已有的半句。草稿模式下忽略（正文从库里取）
    text: str = Field(default='', max_length=MAX_ASSIST_INPUT_CHARS, description='用户自己给的正文')
    action: AssistAction = Field(description='续写 / 润色 / 中译英')
    style: AssistStyle = Field(default='', description='润色风格，仅 action=polish 时有意义')
    keywords: str = Field(default='', max_length=500, description='续写关键词，仅 action=continue 时有意义')
    #: 第二步「AI 完善」旁那个输入框：作者自己补充的事实与修改要求。仅 action=refine 时有意义
    instruction: str = Field(default='', max_length=1000, description='作者补充意见，仅 action=refine 时有意义')

    @model_validator(mode='after')
    def check_mode(self) -> 'AssistRequestModel':
        """
        草稿模式必须两个 id 齐全 —— 只给 draft_id 不给 item_id 无从知道改哪一条。

        独立模式两个都不给；只给 item_id（不给 draft_id）是允许的：那表示
        「照第一步那份规范的第 N 条来写」，条目要求照样从库里取，只是没有草稿可写回。
        """
        if self.draft_id is not None and self.item_id is None:
            raise ValueError('带 draftId 时必须同时给 itemId')

        return self


class AssistResultModel(BaseModel):
    """
    改写结果。**不直接落库** —— 由用户在第四步看过之后显式「采用」，才走写回接口
    """

    model_config = ConfigDict(alias_generator=to_camel)

    item_id: int = Field(description='对应的 checklist 条目id')
    action: str = Field(description='本次执行的动作')
    text: str = Field(description='改写后的正文')
    model_label: str = Field(default='', description='实际出结果的模型，便于排障')
    #: 草稿模式下的「AI 优化」（action=refine）结果会作为一条建议入库（sql/053），这里回它的 id；
    #: 采用走 `/report-drafts/{id}/suggestions/apply`，与一键优化的建议同一条路
    suggestion_id: int | None = Field(default=None, description='入库的建议id（仅草稿模式的 refine）')


class AssistApplyModel(BaseModel):
    """
    把第四步的改写结果写回第二步的草稿条目
    """

    model_config = ConfigDict(alias_generator=to_camel)

    draft_id: int = Field(description='所属草稿id')
    item_id: int = Field(description='要写回的 checklist 条目id')
    content: str = Field(default='', max_length=MAX_DRAFT_ITEM_CHARS, description='写回的正文')


# ---------------------------------------------------------------- 第四步：逐条建议 · 一键优化 · 整篇成文（sql/053）

#: 一次一键优化最多几条。与 worker 的 MAX_REFINE_ITEMS 对齐
MAX_REFINE_BATCH = 200


class SuggestionModel(ActionBaseModel):
    """
    一条优化建议

    `stale` 由服务端现算：生成建议时这一条的正文（base_text）与当前正文不一致 ——
    用户在建议生成之后又手改过它，这时采用会冲掉手改的字，所以不让采用。
    """

    suggestion_id: int = Field(description='建议id')
    item_id: int = Field(description='条目id')
    run_id: int | None = Field(default=None, description='来自哪次一键优化；单条优化为空')
    content: str = Field(default='', description='建议正文')
    #: 生成时这一条的正文。前端拿它与编辑态比，未保存的手改也能当场判出「已过时」
    base_text: str = Field(default='', description='生成建议时这一条的正文')
    instruction: str = Field(default='', description='作者当时给的补充事实')
    model_label: str = Field(default='', description='出结果的模型')
    status: str = Field(default='pending', description='pending / applied / discarded')
    stale: bool = Field(default=False, description='生成之后这一条又被改过')
    create_time: datetime | None = Field(default=None, description='生成时间')


class RefineBatchSubmitModel(BaseModel):
    """
    一键优化的入参

    要优化哪几条由前端给（它手上就有第三步的问题清单）；后端只认纳入范围内的条目，
    空着又没给补充事实的跳过 —— 模型手里只有条目要求时写出来的是一段满屏【待补充】的空壳。
    """

    model_config = ConfigDict(alias_generator=to_camel)

    item_ids: list[int] = Field(min_length=1, max_length=MAX_REFINE_BATCH, description='要优化的条目id')
    #: 条目id → 作者在第四步写下的补充事实（可选）
    instructions: dict[int, str] = Field(default_factory=dict, description='逐条的补充事实')


class RenderSubmitModel(BaseModel):
    """
    整篇成文的入参。`domain` 非空时只重写这一章（其余章节沿用上一次的成文）
    """

    model_config = ConfigDict(alias_generator=to_camel)

    domain: str = Field(default='', max_length=500, description='只重写这一章；空 = 整篇')


class AiSubmitResultModel(BaseModel):
    """提交回执"""

    model_config = ConfigDict(alias_generator=to_camel)

    run_id: int = Field(description='任务记录id')
    session_id: str = Field(description='worker 任务id，轮询用')
    item_total: int = Field(default=0, description='条目数 / 章节数')
    skipped: list[int] = Field(default_factory=list, description='一键优化里因为空着又没给要点而跳过的条目id')
    too_long: list[int] = Field(default_factory=list, description='一键优化里因为正文超长而跳过的条目id')
    ignored: int = Field(default=0, description='不在纳入范围内、被忽略的条目数')


class AiRunStateModel(BaseModel):
    """一次 AI 任务的轮询快照"""

    model_config = ConfigDict(alias_generator=to_camel)

    run_id: int = Field(description='任务记录id')
    session_id: str = Field(description='worker 任务id')
    kind: str = Field(description='refine / render')
    run_status: str = Field(description='pending / running / completed / failed / stopped')
    progress: int = Field(default=0, description='进度百分比')
    phase: str = Field(default='', description='当前阶段（render 为章节名）')
    error_msg: str = Field(default='', description='失败原因')
    item_total: int = Field(default=0, description='条目数 / 章节数')
    done_count: int = Field(default=0, description='产出建议的条目数 / 核对通过的章节数')
    failed_count: int = Field(default=0, description='一键优化里没生成成的条数')
    skipped_count: int = Field(default=0, description='一键优化里因为空着又没给要点而跳过的条数')
    too_long_count: int = Field(default=0, description='一键优化里因为正文超长而跳过的条数')
    unchanged_count: int = Field(default=0, description='一键优化里模型判定已满足要求、原样返回而不出建议的条数')
    ignored_count: int = Field(default=0, description='一键优化里因为已不在纳入范围内而忽略的条数')


class RenderSectionModel(BaseModel):
    """成文的一节（2026-10 起是模型定的提纲里的一个小节）"""

    model_config = ConfigDict(alias_generator=to_camel)

    domain: str = Field(description='小节标题（不分小节的部分就是部分名），也是这一节的键')
    part: str = Field(default='', description='所属一级部分（如「2 方法」）；改版前的成文为空')
    paragraphs: list[dict] = Field(default_factory=list, description='[{text, itemIds}]')
    ok: bool = Field(default=True, description='代码核对是否通过')
    issues: list[dict] = Field(default_factory=list, description='[{kind, values}]')
    error: str = Field(default='', description='这一章没写成的原因')
    stale: bool = Field(default=False, description='成文之后这一章的条目又被改过')


class RenderModel(BaseModel):
    """最近一次整篇成文"""

    model_config = ConfigDict(alias_generator=to_camel)

    run_id: int = Field(description='任务记录id')
    lang: str = Field(default='zh', description='成文语言')
    title: str = Field(default='', description='论文题目（照录作者写的题目条目）；没有就空')
    sections: list[RenderSectionModel] = Field(default_factory=list, description='各节')
    model_label: str = Field(default='', description='出结果的模型')
    create_time: datetime | None = Field(default=None, description='生成时间')


class ReportAiStateModel(BaseModel):
    """打开草稿时第四步要的全部状态：在跑的任务 · 最近的成文 · 逐条建议"""

    model_config = ConfigDict(alias_generator=to_camel)

    live: AiRunStateModel | None = Field(default=None, description='这份草稿在跑的任务（刷新后接回轮询用）')
    render: RenderModel | None = Field(default=None, description='最近一次跑完的整篇成文')
    suggestions: list[SuggestionModel] = Field(default_factory=list, description='逐条建议（新的在后）')


class SuggestionApplyModel(BaseModel):
    """采用建议。`mode=append` 只在采用单条时有意义（追加到现有正文末尾）"""

    model_config = ConfigDict(alias_generator=to_camel)

    ids: list[int] = Field(min_length=1, max_length=MAX_REFINE_BATCH, description='建议id')
    mode: Literal['replace', 'append'] = Field(default='replace', description='覆盖 / 追加')


class SuggestionApplyResultModel(BaseModel):
    """采用结果。过时的那几条**跳过并如实返回**，不静默覆盖"""

    model_config = ConfigDict(alias_generator=to_camel)

    applied: dict[int, str] = Field(default_factory=dict, description='条目id → 写回后的正文')
    stale: list[int] = Field(default_factory=list, description='因为已过时而跳过的建议id')


class SuggestionDiscardModel(BaseModel):
    """放弃建议"""

    model_config = ConfigDict(alias_generator=to_camel)

    ids: list[int] = Field(min_length=1, max_length=MAX_REFINE_BATCH, description='建议id')



#: 留痕事件的取值域。**枚举而不是自由文本**：前端能传任意字符串就等于绕过了
#: 「稿件不入库」那条承诺，人读的句子由前端按 i18n 渲染，库里只存这个键
TrailEvent = Literal['submitted', 'judged', 'cross', 'failed', 'applied', 'rendered']

#: 一次列表最多回多少条留痕
MAX_TRAIL_ROWS = 50


class TrailAddModel(BaseModel):
    """
    追加一条留痕

    **除 `note` 外全是数字与枚举**。`note` 仅供系统诊断（worker 的失败原因），
    接口层限长 300 字符，**前端不得往里塞用户稿件内容** —— 那正是这张表刻意避开的东西。
    """

    model_config = ConfigDict(alias_generator=to_camel)

    event: TrailEvent = Field(description='事件类型')
    draft_id: int | None = Field(default=None, description='关联草稿id；外部稿件不传')
    guideline_code: str = Field(default='', max_length=64, description='报告规范代号')
    actor: str = Field(default='', max_length=200, description='执行者：用户名或模型标识')
    item_id: int | None = Field(default=None, description='event=applied 时被写回的条目id')
    total: int | None = Field(default=None, ge=0, description='判定条目总数')
    reported: int | None = Field(default=None, ge=0, description='已报告条目数')
    vague: int | None = Field(default=None, ge=0, description='描述模糊条目数')
    missing: int | None = Field(default=None, ge=0, description='未报告条目数')
    completeness: int | None = Field(default=None, ge=0, le=100, description='完整性百分比')
    char_count: int | None = Field(default=None, ge=0, description='稿件字符数（只记长度）')
    note: str = Field(default='', max_length=300, description='系统诊断信息，不得写入稿件内容')


class TrailModel(ActionBaseModel):
    """
    一条留痕（出参）
    """

    trail_id: int | None = Field(default=None, description='留痕id')
    draft_id: int | None = Field(default=None, description='关联草稿id')
    guideline_code: str = Field(default='', description='报告规范代号')
    event: str = Field(default='', description='事件类型')
    actor: str = Field(default='', description='执行者')
    item_id: int | None = Field(default=None, description='被写回的条目id')
    total: int | None = Field(default=None, description='判定条目总数')
    reported: int | None = Field(default=None, description='已报告条目数')
    vague: int | None = Field(default=None, description='描述模糊条目数')
    missing: int | None = Field(default=None, description='未报告条目数')
    completeness: int | None = Field(default=None, description='完整性百分比')
    char_count: int | None = Field(default=None, description='稿件字符数')
    note: str = Field(default='', description='系统诊断信息')
    create_time: datetime | None = Field(default=None, description='发生时间')

# ---------------------------------------------------------------- 研究类型


class StudyTypeStatModel(ActionBaseModel):
    """
    研究类型的统计方法推荐条目
    """

    text_zh: str | None = Field(default=None, description='推荐说明（中文）')
    text_en: str | None = Field(default=None, description='推荐说明（英文）')


class ChecklistOptionModel(ActionBaseModel):
    """
    第二步「用哪份规范写」的一个选项（按 id 现取的规范当前代号与名称）

    `item_count` 是启用中的条目数：0 条的规范照样列出（后台挂了就该看得见），
    前台据此标「条目待录入」，不让人点进去才发现是空的。
    """

    guideline_id: int = Field(description='规范id')
    code: str = Field(description='规范当前代号（第二步按它取 checklist、草稿按它分开列）')
    name_zh: str | None = Field(default=None, description='规范名称（中文）')
    name_en: str | None = Field(default=None, description='规范名称（英文）')
    item_count: int = Field(default=0, description='启用中的 checklist 条目数')


class StudyTypeModel(ActionBaseModel):
    """
    研究类型（含关联规范与统计推荐）
    """

    type_id: int | None = Field(default=None, description='类型id')
    type_key: str | None = Field(default=None, description='类型标识')
    name_zh: str | None = Field(default=None, description='名称（中文）')
    name_en: str | None = Field(default=None, description='名称（英文）')
    hot_guideline: str | None = Field(default=None, description='重点推荐规范代号（按 id 现取的当前代号）')
    hot_guideline_id: int | None = Field(default=None, description='重点推荐规范id')
    sort_num: int | None = Field(default=None, description='显示顺序')
    tip_zh: str | None = Field(default=None, description='专属提示（中文）')
    tip_en: str | None = Field(default=None, description='专属提示（英文）')
    status: str | None = Field(default=None, description='状态（0正常 1停用）')
    alt_guideline_ids: list[int] = Field(default_factory=list, description='第二步可切换的其他规范id（sql/056）')
    checklist_options: list[ChecklistOptionModel] = Field(
        default_factory=list, description='第二步可选的规范：重点推荐那份在前，其后按 alt_guideline_ids 顺序'
    )
    guidelines: list[str] = Field(default_factory=list, description='关联规范代号列表')
    stats: list[StudyTypeStatModel] = Field(default_factory=list, description='统计方法推荐')


class StudyTypePageQueryModel(StudyTypeModel):
    """
    研究类型列表查询入参
    """

    keyword: str | None = Field(default=None, description='按标识或名称模糊搜索')


class StudyTypeSaveModel(BaseModel):
    """
    研究类型的新增/编辑入参（后台「研究类型管理」）

    ## 三个字段各有各的下游，改错了症状完全不同

    - **`type_key` 是分支问卷的「判定结果」**。sql/041 起第一步不再是「一行一个按钮」，
      而是 `action_wizard_question/option` 那棵树，树的叶子选项用 `result_type_key` 指到这里。
      所以新加的类型要在「分支问卷」里挂到某个选项上才会被用户选到；改键时服务层会连带
      改掉选项上的引用，删类型时有选项引用就拦下。
    - **`hot_guideline_id` 决定第二步展开哪份 checklist**，必须指向一份存在的 `action_guideline`
      —— 指错了前台第二步展不开，用户只会看到一片空白。这条是硬闸。**按 id 不按代号**：
      代号在「规范目录管理」里可改，2026-08 改过一次，按字符串挂的研究类型全部指空（sql/048）。
      出参的 `hot_guideline` 是按 id 现取的当前代号，入参里不收它。
    - **`alt_guideline_ids` 是第二步还能切换到的其他规范**（sql/056，如 RCT 的 TIDieR-A），同样按 id 挂、
      同样拦不存在的。一份草稿只对应一份规范，切换规范 = 换一份草稿。
    - **`guidelines` 只是展示标签**，不是外键。库里现有「针灸专属条目」「针刺检索策略」
      「GRADE 证据分级」这类值在 `action_guideline` 里根本不存在，它们是给用户看的说明文字。
      所以这一栏不校验，只按顺序存。

    ## 两张子表是整体覆盖

    `guidelines` 与 `stats` 传进来是什么就是什么，没带上的行会被删掉 —— 与第二步草稿
    保存同一种语义：「这次没带这条」与「用户删掉了这条」必须得到同一个结果。
    """

    model_config = ConfigDict(alias_generator=to_camel)

    type_id: int | None = Field(default=None, description='类型id，新增时不传')
    type_key: str = Field(min_length=1, max_length=32, pattern=r'^[a-z][a-z0-9_]*$', description='类型标识')
    name_zh: str = Field(min_length=1, max_length=100, description='名称（中文）')
    name_en: str = Field(default='', max_length=200, description='名称（英文）')
    hot_guideline_id: int | None = Field(default=None, description='重点推荐规范id，留空=不展开 checklist')
    alt_guideline_ids: list[int] = Field(
        default_factory=list, max_length=10, description='第二步可切换的其他规范id（与重点推荐那份重复的会被剔掉）'
    )
    sort_num: int | None = Field(default=None, ge=0, description='显示顺序，留空排到末尾')
    status: Literal['0', '1'] = Field(default='0', description='状态（0正常 1停用）')
    tip_zh: str = Field(default='', max_length=1000, description='专属提示（中文）')
    tip_en: str = Field(default='', max_length=2000, description='专属提示（英文）')
    guidelines: list[str] = Field(default_factory=list, max_length=20, description='关联规范代号（展示标签，整体覆盖）')
    stats: list[StudyTypeStatModel] = Field(default_factory=list, max_length=20, description='统计方法推荐（整体覆盖）')


class WizardOptionModel(ActionBaseModel):
    """
    分支问卷的一个选项（出参与入参共用）

    `next_question_id` 与 `result_type_key` **二选一**：前者选了之后接着弹出下一题，
    后者到此判定为这一类研究。两者都填含义不明，两者都空是一条死路 —— 保存时都会被拒。
    """

    # 服务层要用 snake_case 直接构造（从 ORM 行装出参）；只有 alias 时多余的 snake_case 键
    # 会被**静默忽略**，得到一个字段全默认的空模型（同 PublicationModel 那个坑）
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    option_id: int | None = Field(default=None, description='选项id')
    opt_key: str = Field(
        min_length=1, max_length=32, pattern=r'^[A-Za-z0-9_]+$',
        description='选项标识，同一题内唯一；进 URL（?path=A.y.y），所以不许带点号',
    )
    label_zh: str = Field(min_length=1, max_length=200, description='选项文字（中文）')
    label_en: str = Field(default='', max_length=300, description='选项文字（英文）')
    next_question_id: int | None = Field(default=None, description='下一题id')
    result_type_key: str = Field(default='', max_length=32, description='判定的研究类型标识')
    tip_zh: str = Field(default='', max_length=1000, description='选中时额外显示的提示（中文）')
    tip_en: str = Field(default='', max_length=2000, description='选中时额外显示的提示（英文）')


class WizardQuestionModel(ActionBaseModel):
    """
    分支问卷的一道题，连同它的选项（出参；后台保存也用它，选项整体覆盖）
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    question_id: int | None = Field(default=None, description='问题id，新增时不传')
    q_key: str = Field(
        min_length=1, max_length=32, pattern=r'^[a-z][a-z0-9_]*$', description='问题标识，仅后台辨认用'
    )
    text_zh: str = Field(min_length=1, max_length=300, description='题干（中文）')
    text_en: str = Field(default='', max_length=500, description='题干（英文）')
    is_root: Literal['0', '1'] = Field(default='0', description='是否第一题（全表唯一）')
    sort_num: int | None = Field(default=None, ge=0, description='后台列表顺序')
    options: list[WizardOptionModel] = Field(default_factory=list, max_length=30, description='选项（整体覆盖）')


# ---------------------------------------------------------------- CFIR


class CfirStrategyModel(ActionBaseModel):
    """
    CFIR 构念对应的实施策略
    """

    strategy_id: int | None = Field(default=None, description='策略id')
    name_zh: str | None = Field(default=None, description='策略名称（中文）')
    name_en: str | None = Field(default=None, description='策略名称（英文）')
    detail_zh: str | None = Field(default=None, description='策略说明（中文）')
    detail_en: str | None = Field(default=None, description='策略说明（英文）')
    source_zh: str | None = Field(default=None, description='来源（中文）')
    source_en: str | None = Field(default=None, description='来源（英文）')


class CfirElementModel(ActionBaseModel):
    """
    CFIR 构念下的子条目（①②… 与 ①-1…，children 装下一级）
    """

    element_id: int | None = Field(default=None, description='子条目id')
    label: str | None = Field(default=None, description='编号')
    name_zh: str | None = Field(default=None, description='名称（中文）')
    name_en: str | None = Field(default=None, description='名称（英文）')
    concept_zh: str | None = Field(default=None, description='概念（中文）')
    concept_en: str | None = Field(default=None, description='概念（英文）')
    example_zh: str | None = Field(default=None, description='示例（中文，一行一条）')
    example_en: str | None = Field(default=None, description='示例（英文，一行一条）')
    origin_zh: str | None = Field(default=None, description='与原版CFIR的对应关系（中文）')
    origin_en: str | None = Field(default=None, description='与原版CFIR的对应关系（英文）')
    source: str | None = Field(default=None, description='文献来源')
    children: list['CfirElementModel'] = Field(default_factory=list, description='下一级子条目')


class CfirConstructModel(ActionBaseModel):
    """
    CFIR 构念（障碍点）
    """

    construct_id: int | None = Field(default=None, description='构念id')
    code: str | None = Field(default=None, description='构念标识')
    name_zh: str | None = Field(default=None, description='名称（中文）')
    name_en: str | None = Field(default=None, description='名称（英文）')
    hint_zh: str | None = Field(default=None, description='释义（中文）')
    hint_en: str | None = Field(default=None, description='释义（英文）')
    concept_zh: str | None = Field(default=None, description='概念（中文）')
    concept_en: str | None = Field(default=None, description='概念（英文）')
    example_zh: str | None = Field(default=None, description='示例（中文，一行一条）')
    example_en: str | None = Field(default=None, description='示例（英文，一行一条）')
    origin_zh: str | None = Field(default=None, description='与原版CFIR的对应关系（中文）')
    origin_en: str | None = Field(default=None, description='与原版CFIR的对应关系（英文）')
    source: str | None = Field(default=None, description='文献来源')
    severity: Literal['h', 'm', 'l'] | None = Field(default=None, description='严重度')
    elements: list[CfirElementModel] = Field(default_factory=list, description='子条目')
    strategies: list[CfirStrategyModel] = Field(default_factory=list, description='应对策略')


class CfirDomainModel(ActionBaseModel):
    """
    CFIR 领域
    """

    domain_id: int | None = Field(default=None, description='领域id')
    seq: int | None = Field(default=None, description='领域序号')
    name_zh: str | None = Field(default=None, description='名称（中文）')
    name_en: str | None = Field(default=None, description='名称（英文）')
    intro_zh: str | None = Field(default=None, description='维度说明（中文）')
    intro_en: str | None = Field(default=None, description='维度说明（英文）')
    constructs: list[CfirConstructModel] = Field(default_factory=list, description='构念列表')


class CfirReferenceModel(ActionBaseModel):
    """
    CFIR 针刺版框架参考文献
    """

    ref_no: int | None = Field(default=None, description='文献序号')
    citation: str | None = Field(default=None, description='引用文本')


# ---------------------------------------------------------------- ERIC / RE-AIM


class EricCategoryModel(ActionBaseModel):
    """
    ERIC 策略分类
    """

    cat_key: str | None = Field(default=None, description='分类标识')
    name_zh: str | None = Field(default=None, description='名称（中文）')
    name_en: str | None = Field(default=None, description='名称（英文）')


class EricStrategyModel(ActionBaseModel):
    """
    ERIC 实施策略
    """

    eric_id: int | None = Field(default=None, description='策略id')
    category: str | None = Field(default=None, description='策略分类标识')
    name_zh: str | None = Field(default=None, description='名称（中文）')
    name_en: str | None = Field(default=None, description='名称（英文）')
    detail_zh: str | None = Field(default=None, description='说明（中文）')
    detail_en: str | None = Field(default=None, description='说明（英文）')
    map_zh: str | None = Field(default=None, description='对应CFIR构念（中文）')
    map_en: str | None = Field(default=None, description='对应CFIR构念（英文）')


class ReaimDimensionModel(ActionBaseModel):
    """
    RE-AIM 维度
    """

    dim_id: int | None = Field(default=None, description='维度id')
    letter: str | None = Field(default=None, description='维度首字母')
    name_zh: str | None = Field(default=None, description='名称（中文）')
    name_en: str | None = Field(default=None, description='名称（英文）')
    sub_title: str | None = Field(default=None, description='副标题')
    definition_zh: str | None = Field(default=None, description='定义（中文）')
    definition_en: str | None = Field(default=None, description='定义（英文）')
    measure_zh: str | None = Field(default=None, description='测量指标（中文）')
    measure_en: str | None = Field(default=None, description='测量指标（英文）')
    score_text: str | None = Field(default=None, description='示例得分')


# ---------------------------------------------------------------- SRD

#: 条目评分（新版 Excel 表 1 的四列 + 引擎自己的第五态）。
#: **分越高越重复**：3 完全相同 / 2 部分相同 / 1 部分不同 / 0 完全不同 / unclear 证据不足。
#: 与领域、整体的「重复百分比」同向（引擎 0.8.0 起）。
#: **注意甲方 Excel 表 1 的表头写的是相反的「完全相同 0 分」** —— 拿那张表核对时会读反，
#: 以引擎 `srd_engine/schemas.py` 的 RATING_LABEL_* 为准。
SrdRating = Literal['0', '1', '2', '3', 'unclear']

#: 任务状态，取值与 tools/common/task_store.py 的 STATUS_* 一致
SrdRunStatus = Literal['pending', 'running', 'completed', 'failed', 'stopped']


class SrdItemModel(ActionBaseModel):
    """
    SRD 评估条目

    条目层只有评分，没有「重复程度」与百分比 —— 后者是领域与整体才有的量，
    由这些分数按 `srd-engine/aggregate.py` 的公式算出。
    """

    item_id: int | None = Field(default=None, description='条目id')
    code: str | None = Field(default=None, description='条目编号')
    question_zh: str | None = Field(default=None, description='评估问题（中文）')
    question_en: str | None = Field(default=None, description='评估问题（英文）')
    rating: SrdRating | None = Field(default=None, description='条目评分')
    score: int | None = Field(default=None, description='评分对应分数0-3；证据不足为空')
    confidence: str | None = Field(default=None, description='判定把握（high/medium/low）')
    needs_review: Literal['0', '1'] | None = Field(default=None, description='是否需人工复核')
    review_note: str | None = Field(default=None, description='复核提示')
    evidence_card: str | None = Field(default=None, description='代码算出的客观事实')
    basis_zh: str | None = Field(default=None, description='判定依据（中文）')
    basis_en: str | None = Field(default=None, description='判定依据（英文）')
    cite_a_zh: str | None = Field(default=None, description='综述A原文引用（中文）')
    cite_a_en: str | None = Field(default=None, description='综述A原文引用（英文）')
    cite_b_zh: str | None = Field(default=None, description='综述B原文引用（中文）')
    cite_b_en: str | None = Field(default=None, description='综述B原文引用（英文）')


class SrdGroupModel(ActionBaseModel):
    """
    SRD 评估条目分组
    """

    group_id: int | None = Field(default=None, description='分组id')
    code: str | None = Field(default=None, description='分组编号')
    name_zh: str | None = Field(default=None, description='名称（中文）')
    name_en: str | None = Field(default=None, description='名称（英文）')
    items: list[SrdItemModel] = Field(default_factory=list, description='条目列表')


class SrdDomainModel(ActionBaseModel):
    """
    SRD 评估领域
    """

    domain_id: int | None = Field(default=None, description='领域id')
    seq: int | None = Field(default=None, description='领域序号')
    name_zh: str | None = Field(default=None, description='名称（中文）')
    name_en: str | None = Field(default=None, description='名称（英文）')
    is_key: Literal['0', '1'] | None = Field(default=None, description='是否关键领域')
    level: DupLevel | None = Field(default=None, description='重复程度')
    pct: int | None = Field(default=None, description='重复度百分比')
    score_sum: int | None = Field(default=None, description='领域得分（分越高越重复）')
    score_max: int | None = Field(default=None, description='可评分条目满分=3×可评分条目数')
    score_max_full: int | None = Field(default=None, description='名义满分=3×条目数')
    dup_count: int | None = Field(default=None, description='偏重复条目数（评分0/1）')
    diff_count: int | None = Field(default=None, description='偏不同条目数（评分2/3）')
    unclear_count: int | None = Field(default=None, description='证据不足条目数')
    evidence_sufficient: Literal['0', '1'] | None = Field(default=None, description='证据是否充分')
    near_boundary: Literal['0', '1'] | None = Field(default=None, description='是否临近分箱边界')
    groups: list[SrdGroupModel] = Field(default_factory=list, description='分组列表')


class SrdAssessmentModel(ActionBaseModel):
    """
    SRD 系统综述重复性评估（含完整层级）
    """

    assessment_id: int | None = Field(default=None, description='评估id')
    session_id: str | None = Field(default=None, description='worker任务id')
    run_status: SrdRunStatus | None = Field(default=None, description='任务状态')
    progress: int | None = Field(default=None, description='进度百分比0-100')
    error_msg: str | None = Field(default=None, description='失败原因')
    file_a_name: str | None = Field(default=None, description='综述A上传文件名')
    file_b_name: str | None = Field(default=None, description='综述B上传文件名')
    review_a_title_zh: str | None = Field(default=None, description='综述A标题（中文）')
    review_a_title_en: str | None = Field(default=None, description='综述A标题（英文）')
    review_b_title_zh: str | None = Field(default=None, description='综述B标题（中文）')
    review_b_title_en: str | None = Field(default=None, description='综述B标题（英文）')
    overall_level: DupLevel | None = Field(default=None, description='整体判定')
    overall_pct: int | None = Field(default=None, description='整体重复度百分比')
    overall_score_sum: int | None = Field(default=None, description='整体得分')
    overall_score_max: int | None = Field(default=None, description='可评分条目满分')
    overall_score_max_full: int | None = Field(default=None, description='名义满分（102）')
    overall_reason_zh: str | None = Field(default=None, description='整体判定理由（中文）')
    overall_reason_en: str | None = Field(default=None, description='整体判定理由（英文）')
    provisional: Literal['0', '1'] | None = Field(default=None, description='关键领域证据不足，结论仅供参考')
    unclear_count: int | None = Field(default=None, description='证据不足条目数')
    review_count: int | None = Field(default=None, description='待人工复核条目数')
    model_name: str | None = Field(default=None, description='判定所用模型')
    engine_version: str | None = Field(default=None, description='引擎版本')
    llm_calls: int | None = Field(default=None, description='模型调用次数')
    seconds: float | None = Field(default=None, description='耗时（秒）')
    create_time: datetime | None = Field(default=None, description='提交时间')
    finish_time: datetime | None = Field(default=None, description='完成时间')
    is_sample: Literal['0', '1'] | None = Field(default=None, description='是否示例数据')
    domains: list[SrdDomainModel] = Field(default_factory=list, description='领域列表')


class SrdHistoryModel(ActionBaseModel):
    """
    「我的评估历史」列表行 —— 只带列表要显示的字段，不带 34 条目明细
    """

    assessment_id: int | None = Field(default=None, description='评估id')
    session_id: str | None = Field(default=None, description='worker任务id')
    run_status: SrdRunStatus | None = Field(default=None, description='任务状态')
    progress: int | None = Field(default=None, description='进度百分比0-100')
    error_msg: str | None = Field(default=None, description='失败原因')
    review_a_title_zh: str | None = Field(default=None, description='综述A标题（中文）')
    review_a_title_en: str | None = Field(default=None, description='综述A标题（英文）')
    review_b_title_zh: str | None = Field(default=None, description='综述B标题（中文）')
    review_b_title_en: str | None = Field(default=None, description='综述B标题（英文）')
    overall_level: DupLevel | None = Field(default=None, description='整体判定')
    overall_pct: int | None = Field(default=None, description='整体重复度百分比')
    overall_score_sum: int | None = Field(default=None, description='整体得分')
    overall_score_max: int | None = Field(default=None, description='可评分条目满分')
    provisional: Literal['0', '1'] | None = Field(default=None, description='结论是否仅供参考')
    create_time: datetime | None = Field(default=None, description='提交时间')
    finish_time: datetime | None = Field(default=None, description='完成时间')


class SrdRunStateModel(ActionBaseModel):
    """
    评估任务的轮询快照

    任务跑完那一刻由轮询接口把引擎结果落库，所以 `assessmentId` 一定有值 ——
    前端拿到 completed 后直接按 id 取详情，不必再解一遍 worker 的摘要。
    """

    session_id: str = Field(description='任务id')
    assessment_id: int | None = Field(default=None, description='评估记录id')
    run_status: SrdRunStatus = Field(description='任务状态')
    progress: int = Field(default=0, description='进度百分比0-100')
    message: str = Field(default='', description='当前阶段说明')
    error_msg: str = Field(default='', description='失败原因')


# ---------------------------------------------------------------- 协作申请


class CollabRequestModel(ActionBaseModel):
    """
    协作与专家咨询申请
    """

    request_id: int | None = Field(default=None, description='申请id')
    request_type: Literal['consult', 'collab', 'feedback'] | None = Field(default=None, description='申请类型')
    applicant: str | None = Field(default=None, description='申请人')
    organization: str | None = Field(default=None, description='所属机构')
    email: str | None = Field(default=None, description='邮箱')
    phone: str | None = Field(default=None, description='联系电话')
    topic: str | None = Field(default=None, description='主题')
    content: str | None = Field(default=None, description='正文')
    source_lang: Literal['zh', 'en'] | None = Field(default=None, description='提交时界面语言')
    source_ip: str | None = Field(default=None, description='来源ip')
    handle_status: Literal['0', '1', '2', '3'] | None = Field(default=None, description='处理状态')
    handle_by: str | None = Field(default=None, description='处理人')
    handle_time: datetime | None = Field(default=None, description='处理时间')
    handle_remark: str | None = Field(default=None, description='处理备注')
    create_time: datetime | None = Field(default=None, description='提交时间')


class CollabRequestSubmitModel(BaseModel):
    """
    官网表单提交入参

    公开接口，字段独立定义而非复用 CollabRequestModel：
    避免调用方伪造 handle_status / handle_by 等仅后台可写的字段。
    """

    model_config = ConfigDict(alias_generator=to_camel)

    request_type: Literal['consult', 'collab', 'feedback'] = Field(default='consult', description='申请类型')
    applicant: str = Field(min_length=1, max_length=100, description='申请人')
    organization: str | None = Field(default=None, max_length=300, description='所属机构')
    email: EmailStr = Field(description='邮箱')
    phone: str | None = Field(default=None, max_length=50, description='联系电话')
    topic: str | None = Field(default=None, max_length=300, description='主题')
    content: str = Field(min_length=1, max_length=5000, description='正文')
    source_lang: Literal['zh', 'en'] = Field(default='zh', description='提交时界面语言')


class CollabRequestPageQueryModel(CollabRequestModel):
    """
    协作申请分页查询模型
    """

    begin_time: str | None = Field(default=None, description='开始时间')
    end_time: str | None = Field(default=None, description='结束时间')
    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


# ---------------------------------------------------------------- 官网访客账号
#
# 以下入参一律用裸 BaseModel 独立定义，不复用 UserModel / ActionBaseModel：
# 这些是完全公开的匿名接口，复用完整实体等于让调用方有机会伪造 userType、status、
# delFlag 等仅服务端可写的字段。
#
# 文本字段的 @Xss / 非空白校验必须落在本层：UserModel 上的同类校验器只在显式调用
# validate_fields() 时才跑，而访客注册走的 UserService.add_user_services 从不调用它。

# bcrypt 限制的是密码的 UTF-8 字节数而非字符数：25 个中文就是 75 字节，
# max_length=50（字符）完全拦不住，落到 bcrypt.hashpw/checkpw 会抛 ValueError
# 变成 500，且兜底 handler 会把英文原文回给匿名调用方。必须在入参层按字节拦。
BCRYPT_MAX_PASSWORD_BYTES = 72


def _reject_oversize_password(password: str | None, field_label: str) -> None:
    """
    校验密码的UTF-8字节长度不超过bcrypt上限

    :param password: 待校验的密码，None表示未提供
    :param field_label: 出错提示里使用的字段名称
    :return: None
    """
    if password is not None and len(password.encode('utf-8')) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ModelValidatorException(message=f'{field_label}长度不能超过{BCRYPT_MAX_PASSWORD_BYTES}个字节')


def _strip_optional_text(value: str | None) -> str | None:
    """
    去除可选自由文本两端空白，纯空白视为未填写

    :param value: 原始文本
    :return: 归一化后的文本，纯空白或空串返回None
    """
    if value is None:
        return None
    stripped = value.strip()

    return stripped or None


class GuestEmailCodeModel(BaseModel):
    """
    官网访客-发送邮箱验证码入参
    """

    model_config = ConfigDict(alias_generator=to_camel)

    email: EmailStr = Field(max_length=50, description='邮箱')
    scene: Literal['register', 'login', 'reset'] = Field(description='验证码场景（register注册 login登录 reset找回密码）')
    # 这一项是邮件正文选语言用的，与注册/登录入参不同，必须保留
    source_lang: Literal['zh', 'en'] = Field(default='zh', description='提交时界面语言')


class GuestRegisterModel(BaseModel):
    """
    官网访客-注册入参
    """

    model_config = ConfigDict(alias_generator=to_camel)

    email: EmailStr = Field(max_length=50, description='邮箱')
    code: str = Field(min_length=6, max_length=6, pattern=r'^\d{6}$', description='邮箱验证码')
    # 用户名写入 sys_user.nick_name（String(30)），登录标识始终是邮箱
    username: str = Field(min_length=1, max_length=30, description='用户名')
    institution: str | None = Field(default=None, max_length=300, description='所属机构')
    position: str | None = Field(default=None, max_length=100, description='职位')
    password: str = Field(min_length=6, max_length=50, description='密码')
    confirm_password: str = Field(min_length=6, max_length=50, description='确认密码')

    @field_validator('username', mode='after')
    @classmethod
    def strip_username(cls, value: str) -> str:
        """
        去除用户名两端空白，纯空白交由下方 NotBlank 拦截

        :param value: 原始用户名
        :return: 去除两端空白后的用户名
        """
        return value.strip()

    @field_validator('institution', 'position', mode='after')
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        """
        机构与职位去空白，纯空白按未填写处理

        :param value: 原始文本
        :return: 归一化后的文本
        """
        return _strip_optional_text(value)

    @model_validator(mode='after')
    @Xss(field_name='username', message='用户名不能包含脚本字符')
    @NotBlank(field_name='username', message='用户名不能为空')
    @Size(field_name='username', min_length=0, max_length=30, message='用户名长度不能超过30个字符')
    @Xss(field_name='institution', message='所属机构不能包含脚本字符')
    @Size(field_name='institution', min_length=0, max_length=300, message='所属机构长度不能超过300个字符')
    @Xss(field_name='position', message='职位不能包含脚本字符')
    @Size(field_name='position', min_length=0, max_length=100, message='职位长度不能超过100个字符')
    def check_text_fields(self) -> 'GuestRegisterModel':
        """
        校验自由文本字段（脚本字符、空白、长度）

        :return: 校验通过的入参对象
        """
        return self

    @model_validator(mode='after')
    def check_password(self) -> 'GuestRegisterModel':
        """
        校验密码字节长度不超过bcrypt上限

        :return: 校验通过的入参对象
        """
        _reject_oversize_password(self.password, '密码')
        _reject_oversize_password(self.confirm_password, '确认密码')

        return self


class GuestLoginModel(BaseModel):
    """
    官网访客-登录入参

    验证码登录与密码登录二选一，两者都传或都不传都视为非法入参。
    """

    model_config = ConfigDict(alias_generator=to_camel)

    email: EmailStr = Field(max_length=50, description='邮箱')
    code: str | None = Field(default=None, min_length=6, max_length=6, pattern=r'^\d{6}$', description='邮箱验证码')
    password: str | None = Field(default=None, min_length=1, max_length=50, description='密码')

    @model_validator(mode='after')
    def check_credential(self) -> 'GuestLoginModel':
        """
        校验验证码与密码恰好提供其中一项，并校验密码字节长度

        :return: 校验通过的入参对象
        """
        if bool(self.code) == bool(self.password):
            raise ModelValidatorException(message='请提供验证码或密码其中一项')
        # 登录路径同样要在入参层拦超长密码：否则 bcrypt.checkpw 抛 ValueError，
        # 「邮箱不存在」返回业务错误而「邮箱存在」返回 500，状态码本身就成了枚举信号
        _reject_oversize_password(self.password, '密码')

        return self


class GuestPasswordResetModel(BaseModel):
    """
    官网访客-找回密码入参（凭邮箱验证码重设密码）
    """

    model_config = ConfigDict(alias_generator=to_camel)

    email: EmailStr = Field(max_length=50, description='邮箱')
    code: str = Field(min_length=6, max_length=6, pattern=r'^\d{6}$', description='邮箱验证码')
    password: str = Field(min_length=6, max_length=50, description='新密码')
    confirm_password: str = Field(min_length=6, max_length=50, description='确认新密码')

    @model_validator(mode='after')
    def check_password(self) -> 'GuestPasswordResetModel':
        """
        校验密码字节长度不超过bcrypt上限

        :return: 校验通过的入参对象
        """
        _reject_oversize_password(self.password, '密码')
        _reject_oversize_password(self.confirm_password, '确认密码')

        return self


class GuestProfileUpdateModel(BaseModel):
    """
    官网访客-修改资料入参

    邮箱不在这里：它是登录标识，改邮箱要验证新邮箱归属，是另一件事。
    三项都是整体覆盖语义（表单总是三项一起提交），机构/职位留空即清空。
    """

    model_config = ConfigDict(alias_generator=to_camel)

    username: str = Field(min_length=1, max_length=30, description='用户名')
    institution: str | None = Field(default=None, max_length=300, description='所属机构')
    position: str | None = Field(default=None, max_length=100, description='职位')

    @field_validator('username', mode='after')
    @classmethod
    def strip_username(cls, value: str) -> str:
        """
        去除用户名两端空白，纯空白交由下方 NotBlank 拦截

        :param value: 原始用户名
        :return: 去除两端空白后的用户名
        """
        return value.strip()

    @field_validator('institution', 'position', mode='after')
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        """
        机构与职位去空白，纯空白按未填写处理

        :param value: 原始文本
        :return: 归一化后的文本
        """
        return _strip_optional_text(value)

    # 文案与注册那份逐字一致：前端 `BACKEND_MESSAGE_KEYS` 按完整字符串映射，一份文案一个键
    @model_validator(mode='after')
    @Xss(field_name='username', message='用户名不能包含脚本字符')
    @NotBlank(field_name='username', message='用户名不能为空')
    @Size(field_name='username', min_length=0, max_length=30, message='用户名长度不能超过30个字符')
    @Xss(field_name='institution', message='所属机构不能包含脚本字符')
    @Size(field_name='institution', min_length=0, max_length=300, message='所属机构长度不能超过300个字符')
    @Xss(field_name='position', message='职位不能包含脚本字符')
    @Size(field_name='position', min_length=0, max_length=100, message='职位长度不能超过100个字符')
    def check_text_fields(self) -> 'GuestProfileUpdateModel':
        """
        校验自由文本字段（脚本字符、空白、长度）

        :return: 校验通过的入参对象
        """
        return self


class GuestPasswordChangeModel(BaseModel):
    """
    官网访客-修改密码入参（已登录，凭原密码）
    """

    model_config = ConfigDict(alias_generator=to_camel)

    # 原密码不卡 6 位下限：老账号的密码规则可能变过，同登录侧
    old_password: str = Field(min_length=1, max_length=50, description='原密码')
    password: str = Field(min_length=6, max_length=50, description='新密码')
    confirm_password: str = Field(min_length=6, max_length=50, description='确认新密码')

    @model_validator(mode='after')
    def check_password(self) -> 'GuestPasswordChangeModel':
        """
        校验密码字节长度不超过bcrypt上限

        :return: 校验通过的入参对象
        """
        _reject_oversize_password(self.old_password, '原密码')
        _reject_oversize_password(self.password, '密码')
        _reject_oversize_password(self.confirm_password, '确认密码')

        return self


class GuestPublicInfoModel(BaseModel):
    """
    官网访客-对外暴露的访客信息

    刻意不含 user_id：内部身份识别用 GuestInfoModel，接口响应体一律用本模型，
    避免把 sys_user 的自增主键泄露给官网调用方。
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    email: str = Field(description='邮箱')
    username: str = Field(description='用户名')
    institution: str | None = Field(default=None, description='所属机构')
    position: str | None = Field(default=None, description='职位')


class GuestInfoModel(GuestPublicInfoModel):
    """
    官网访客-当前登录访客信息（内部使用，含用户id）
    """

    user_id: int = Field(description='用户id')

    def to_public(self) -> GuestPublicInfoModel:
        """
        转为对外返回体（剥掉user_id）

        :return: 对外访客信息
        """
        return GuestPublicInfoModel(
            email=self.email,
            username=self.username,
            institution=self.institution,
            position=self.position,
        )


class GuestTokenModel(BaseModel):
    """
    官网访客-登录/注册成功后的令牌信息
    """

    model_config = ConfigDict(alias_generator=to_camel)

    token: str = Field(description='访客令牌')
    guest: GuestPublicInfoModel = Field(description='访客信息')


class GuestAdminModel(ActionBaseModel):
    """
    后台「访客管理」的访客行

    只挑后台要看的那几列，**不含 password / user_name**：user_name 是 guest_ + 随机串的占位，
    对管理员没有意义；password 哈希不该出现在任何出参里。
    四个计数是该访客名下未删除的工作（报告草稿 / SRD 评估 / 稿件校验 / 背景生成）。
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    user_id: int | None = Field(default=None, description='用户id')
    email: str | None = Field(default=None, description='邮箱（登录标识）')
    nick_name: str | None = Field(default=None, description='用户名')
    institution: str | None = Field(default=None, description='所属机构')
    position: str | None = Field(default=None, description='职位')
    status: str | None = Field(default=None, description='账号状态（0正常 1停用；NULL 按正常）')
    login_ip: str | None = Field(default=None, description='最后登录IP')
    login_date: datetime | None = Field(default=None, description='最后登录时间')
    pwd_update_date: datetime | None = Field(default=None, description='密码最后更新时间')
    create_time: datetime | None = Field(default=None, description='注册时间')
    draft_count: int = Field(default=0, description='报告草稿数')
    srd_count: int = Field(default=0, description='SRD 评估数')
    review_count: int = Field(default=0, description='稿件校验数')
    background_count: int = Field(default=0, description='背景生成数')


class GuestAdminPageQueryModel(ActionBaseModel):
    """
    访客分页查询模型

    理由同 LiteratureModel：含下划线的字段在服务层可能按 snake_case 构造，必须开 populate_by_name。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    keyword: str | None = Field(default=None, description='邮箱 / 用户名 / 机构 / 职位关键词')
    status: Literal['0', '1'] | None = Field(default=None, description='账号状态')
    begin_time: str | None = Field(default=None, description='注册时间起（yyyy-MM-dd）')
    end_time: str | None = Field(default=None, description='注册时间止（yyyy-MM-dd）')
    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


class GuestStatusModel(BaseModel):
    """
    访客停用 / 启用（窄接口，只收这两个值）
    """

    model_config = ConfigDict(alias_generator=to_camel)

    user_id: int = Field(description='用户id')
    status: Literal['0', '1'] = Field(description='账号状态（0正常 1停用）')

# ---------------------------------------------------------------- 针灸文献知识库

#: 研究设计取值。**protocol 是研究方案、没有结果数据，不得作疗效证据**——
#: 实测模型会把它判成 rct，入库时由 `tools/lit_ingest._norm_design` 按标题兜底改判
StudyDesign = Literal['rct', 'nrct', 'animal', 'sr_meta', 'case_series', 'protocol', 'other']
#: 效应方向。**按主要结局判，不按摘要结论句判** —— 中文文献摘要常写「疗效显著」
#: 而数据是终点组间无差异（P>0.05），跟着摘要走会让不一致检测整个失效
EffectDirection = Literal['positive', 'negative', 'no_difference', 'unclear']
#: 人工复核状态。语料是机器抽取的，复核是这张表的主要人工工作
ReviewStatus = Literal['pending', 'ok', 'fixed', 'rejected']


class LiteratureModel(ActionBaseModel):
    """
    针灸文献知识库条目

    **这些记录是机器从 PDF 抽取的产物，不是人工录入的。** 后台页面的主要工作是
    「复核与修正」而非「新增」——一条记录必须对应一个真实的 PDF（`corpus_no` 唯一），
    手工凭空建一条会得到一份没有原文可核的元数据，所以写接口只开编辑不开新增。

    列表接口刻意不返回 `abstract` / `finding_summary` / `year_evidence`
    （`LiteratureService._LIST_OMIT`）：一页 20 条摘要就是几万字没人看的文本，
    详情接口才给全。

    `authors` / `condition` / `comparator` 等在库里是 JSON 文本，转换收在
    `LiteratureService._encode` / `_decode`，DAO 与控制器都不认识这件事。
    """

    #: 额外开 `populate_by_name`，同 `PublicationModel`：这几个模型除了接 HTTP 入参，
    #: 还要在服务层与 tools/ 脚本里用 **snake_case 字段名**直接构造。pydantic v2 在只有
    #: alias 时对 snake_case 键是**静默忽略**而不是报错 —— 不开这个开关，
    #: `LiteratureStatsModel(no_difference=92)` 会安静地得到 0，
    #: `LiteraturePageQueryModel(condition_group='失眠')` 会安静地不筛选（实测两处都中招）。
    model_config = ConfigDict(populate_by_name=True)


    lit_id: int | None = Field(default=None, description='文献id')
    corpus_no: int | None = Field(default=None, description='语料编号（对应 PDF 文件，唯一）')
    file_name: str | None = Field(default=None, description='PDF 文件名')
    title: str | None = Field(default=None, description='原文题名（原语言照录），引用输出用它')
    title_en: str | None = Field(default=None, description='英文题名，取自目录.xlsx；英文文献与 title 同值')

    year: int | None = Field(default=None, description='出版年')
    year_evidence: str | None = Field(default=None, description='判定出版年所依据的原文片段')
    year_confidence: Literal['high', 'low'] | None = Field(default=None, description='年份可信度')
    authors: list[str] | None = Field(default=None, description='作者，顺序即署名顺序')
    journal: str | None = Field(default=None, description='期刊名')
    country: str | None = Field(default=None, description='国家')
    lang: Literal['zh', 'en'] | None = Field(default=None, description='文献语言')

    abstract: str | None = Field(default=None, description='摘要')
    population: str | None = Field(default=None, description='研究对象')
    condition: list[str] | None = Field(default=None, description='病种（归一化中文标签）')
    condition_norm: list[str] | None = Field(default=None, description='规范病种名')
    condition_group: list[str] | None = Field(default=None, description='上位病种类目，覆盖度按它算')
    intervention: list[str] | None = Field(default=None, description='干预措施')
    comparator: list[str] | None = Field(default=None, description='对照措施（短标签）')
    outcomes: list[str] | None = Field(default=None, description='结局指标')
    tcm_syndrome: list[str] | None = Field(default=None, description='中医证候')

    study_design: StudyDesign | None = Field(default=None, description='研究设计')
    sample_size: int | None = Field(default=None, description='总样本量')
    effect_direction: EffectDirection | None = Field(default=None, description='效应方向，按主要结局判')
    finding_summary: str | None = Field(default=None, description='主要结果概括')

    acu_points: list[str] | None = Field(default=None, description='穴位，国际代码优先')
    acu_meridian: list[str] | None = Field(default=None, description='经络')
    acu_method: str | None = Field(default=None, description='针法')
    acu_frequency: str | None = Field(default=None, description='电针频率')
    acu_deqi: Literal['0', '1'] | None = Field(default=None, description='是否报告得气')
    acu_retention_min: int | None = Field(default=None, description='留针分钟数')
    acu_sessions: int | None = Field(default=None, description='总治疗次数')
    acu_course_weeks: int | None = Field(default=None, description='疗程周数')

    contamination: Literal['0', '1'] | None = Field(default=None, description='PDF 是否夹带其他论文内容')
    contamination_note: str | None = Field(default=None, description='夹带说明')
    contam_kind: str | None = Field(default=None, description='夹带形态')
    clean_status: str | None = Field(default=None, description='切除结果')
    clean_ratio: int | None = Field(default=None, description='切除后保留百分比')
    intruders: list[str] | None = Field(default=None, description='混入的其他论文标题')
    truncated: Literal['0', '1'] | None = Field(default=None, description='本文后半截不在本 PDF 里')
    review_status: ReviewStatus | None = Field(default=None, description='人工复核状态')
    review_by: str | None = Field(default=None, description='复核人')
    review_time: datetime | None = Field(default=None, description='复核时间')

    extract_model: str | None = Field(default=None, description='抽取所用模型')
    extract_status: str | None = Field(default=None, description='抽取状态')
    extract_error: str | None = Field(default=None, description='抽取失败原因')
    extract_time: datetime | None = Field(default=None, description='抽取时间')
    pages: int | None = Field(default=None, description='PDF 页数')
    text_chars: int | None = Field(default=None, description='正文字符数')

    status: Literal['0', '1'] | None = Field(default=None, description='状态（0正常 1停用，停用即不进检索）')
    create_by: str | None = Field(default=None, description='创建者')
    create_time: datetime | None = Field(default=None, description='创建时间')
    update_by: str | None = Field(default=None, description='更新者')
    update_time: datetime | None = Field(default=None, description='更新时间')
    remark: str | None = Field(default=None, description='备注')

    @Size(field_name='title', min_length=0, max_length=1000, message='标题不能超过1000个字符')
    def get_title(self) -> str | None:
        return self.title

    @field_validator('year')
    @classmethod
    def check_year(cls, v: int | None) -> int | None:
        """出版年落在合理区间。手工改到 1800 或 2999 只可能是笔误"""
        if v is not None and not (1900 <= v <= datetime.now().year + 1):
            raise ModelValidatorException(message=f'出版年应在 1900-{datetime.now().year + 1} 之间')
        return v

    def validate_fields(self) -> None:
        self.get_title()


class LiteratureTextModel(ActionBaseModel):
    """
    文献全文。**只在详情页按需拉取**，不进列表接口 —— 单篇中位 1.8 万字符
    """

    #: 理由见 LiteratureModel 上那段注释
    model_config = ConfigDict(populate_by_name=True)


    lit_id: int | None = Field(default=None, description='文献id')
    corpus_no: int | None = Field(default=None, description='语料编号')
    full_text: str | None = Field(default=None, description='PDF 原始正文')
    clean_text: str | None = Field(default=None, description='切除夹带后的正文；为空表示无须切除')


class LiteratureQueryModel(ActionBaseModel):
    """
    文献查询模型

    `quality` 是几个质量标记的合并筛选项，专为「复核」这条主线设计：
    contaminated 夹带未处理 / truncated 正文截断 / lowYear 年份存疑 /
    needReview 待复核（以上任一 + review_status=pending）
    """

    #: 理由见 LiteratureModel 上那段注释
    model_config = ConfigDict(populate_by_name=True)


    keyword: str | None = Field(default=None, description='标题/期刊/作者/摘要关键词')
    corpus_no: int | None = Field(default=None, description='语料编号')
    condition_group: str | None = Field(default=None, description='病种上位类目')
    study_design: str | None = Field(default=None, description='研究设计')
    effect_direction: str | None = Field(default=None, description='效应方向')
    lang: str | None = Field(default=None, description='文献语言')
    review_status: str | None = Field(default=None, description='复核状态')
    quality: str | None = Field(default=None, description='质量标记筛选')
    year_begin: int | None = Field(default=None, description='出版年起')
    year_end: int | None = Field(default=None, description='出版年止')
    status: str | None = Field(default=None, description='状态')


class LiteraturePageQueryModel(LiteratureQueryModel):
    """
    文献分页查询模型
    """

    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=20, description='每页记录数')


class LiteratureReviewModel(BaseModel):
    """
    复核操作模型

    复核是这张表的主要人工工作，**单开一个窄接口而不是复用编辑接口**：
    编辑接口收整个 `LiteratureModel`，前端漏传一个字段就会把它清空；
    而复核只改三个值，收窄入参等于把这类事故挡在门外。
    """

    model_config = ConfigDict(alias_generator=to_camel)

    lit_ids: str = Field(description='文献id，多个以逗号分隔')
    review_status: ReviewStatus = Field(description='复核结果')
    remark: str | None = Field(default=None, description='复核备注')


class LiteratureStatsModel(ActionBaseModel):
    """
    语料统计。后台页面顶部的概览卡片，也是「语料构成披露」的数据来源
    """

    #: 理由见 LiteratureModel 上那段注释
    model_config = ConfigDict(populate_by_name=True)


    total: int = Field(default=0, description='文献总数')
    usable: int = Field(default=0, description='启用中')
    zh: int = Field(default=0, description='中文文献')
    en: int = Field(default=0, description='英文文献')
    recent5: int = Field(default=0, description='近5年')
    positive: int = Field(default=0, description='阳性结果')
    no_difference: int = Field(default=0, description='无差异')
    negative: int = Field(default=0, description='阴性结果')
    unclear: int = Field(default=0, description='方向无法判定')
    contaminated: int = Field(default=0, description='PDF 夹带其他论文内容')
    truncated: int = Field(default=0, description='正文截断')
    low_year: int = Field(default=0, description='年份存疑')
    pending: int = Field(default=0, description='待复核')
    designs: list[dict[str, Any]] = Field(default_factory=list, description='研究设计分布')
    groups: list[dict[str, Any]] = Field(default_factory=list, description='病种类目 Top')


class DeleteLiteratureModel(BaseModel):
    """
    删除文献模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    lit_ids: str = Field(description='需要删除的文献id，多个以逗号分隔')


# ---------------------------------------------------------------- 背景与讨论智能生成

#: 研究方向的长度。太短检索不出东西，太长是把整段摘要粘进来了
MIN_BG_TOPIC_CHARS = 4
MAX_BG_TOPIC_CHARS = 200

BgRunStatus = Literal['pending', 'running', 'completed', 'failed', 'stopped']


class BackgroundSubmitModel(BaseModel):
    """
    提交一次背景生成

    **只收研究方向与两个可选提示，不收任何「按 id 去库里捞」的入参** ——
    同 `AssistRequestModel` 的安全边界：前端能指定 id 就意味着能拿别人的东西当 prompt。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    topic: str = Field(min_length=MIN_BG_TOPIC_CHARS, max_length=MAX_BG_TOPIC_CHARS, description='研究方向')
    guideline_code: str = Field(default='', max_length=64, description='按哪份规范写，取自第一步')
    condition_group: str = Field(default='', max_length=200, description='指定病种类目；留空由系统推断')
    locale: Literal['zh', 'en'] = Field(default='zh', description='生成语言')


class BackgroundSubmitResultModel(ActionBaseModel):
    """提交结果。**runId 要存下来**：刷新页面后靠它从历史里找回这次生成"""

    #: 这三个出参模型都额外开 `populate_by_name`：它们除了接 HTTP 入参，还要在服务层
    #: 用 snake_case 字段名直接构造。pydantic v2 在只有 alias 时对多余的 snake_case 键是
    #: **静默忽略**而不是报错 —— 不开这个开关会安静地得到一个字段全是默认值的空模型
    #: （同 `PublicationModel` 的理由，那次是 `LiteratureStatsModel(no_difference=92)` → 0）
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    run_id: int = Field(description='任务记录id')
    session_id: str = Field(description='worker 任务id，轮询用')


class BackgroundStateModel(ActionBaseModel):
    """
    一次生成的状态与结果

    `result` 只在 `completed` 时有值。**`retrieve_mode` 必须一路传到前端**：
    `bm25` 表示向量检索不可用、已降级（实测 P@5 由 0.94 掉到 0.73），
    这是质的变化而用户完全看不出来，不报出来就是欺骗。
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    run_id: int = Field(description='任务记录id')
    session_id: str = Field(description='worker 任务id')
    topic: str = Field(description='研究方向')
    run_status: BgRunStatus = Field(description='任务状态')
    progress: int = Field(default=0, description='进度百分比')
    phase: str = Field(default='', description='当前阶段 pico/search/write/verify')
    error_msg: str = Field(default='', description='失败原因')
    retrieve_mode: str = Field(default='', description='检索模式；bm25 表示已降级')
    model_label: str = Field(default='', description='出结果的模型')
    slot_total: int = Field(default=0, description='段落总数')
    slot_blocked: int = Field(default=0, description='覆盖不足未生成的段落数')
    ref_count: int = Field(default=0, description='参考文献条数')
    partial_count: int = Field(default=0, description='引证核验待复核处数')
    create_time: datetime | None = Field(default=None, description='提交时间')
    finish_time: datetime | None = Field(default=None, description='结束时间')
    result: dict[str, Any] | None = Field(default=None, description='完整结果，仅 completed 时有值')


class BackgroundHistoryModel(ActionBaseModel):
    """
    历史列表项。**不带 result** —— 一次结果几千字，列表页一个字都用不上
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    run_id: int = Field(description='任务记录id')
    session_id: str = Field(description='worker 任务id')
    topic: str = Field(description='研究方向')
    condition_group: str = Field(default='', description='命中的病种类目')
    run_status: BgRunStatus = Field(description='任务状态')
    progress: int = Field(default=0, description='进度百分比')
    error_msg: str = Field(default='', description='失败原因')
    slot_total: int = Field(default=0, description='段落总数')
    slot_blocked: int = Field(default=0, description='覆盖不足未生成的段落数')
    ref_count: int = Field(default=0, description='参考文献条数')
    partial_count: int = Field(default=0, description='引证核验待复核处数')
    retrieve_mode: str = Field(default='', description='检索模式')
    create_time: datetime | None = Field(default=None, description='提交时间')
    finish_time: datetime | None = Field(default=None, description='结束时间')
