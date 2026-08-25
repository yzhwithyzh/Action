-- ----------------------------
-- 官网-成果发表（PostgreSQL）
--
-- 官网「成果发表」页（`pages/publications.vue` 列表 + `pages/publication/[id].vue` 详情）
-- 的唯一数据源，后台「成果发表管理」页维护。
--
-- 【为什么这几列不做中英双语】全库其余内容表都是 `*_zh` / `*_en` 成对，这张表**刻意不是**：
-- 一篇论文的标题、作者署名、期刊名、摘要是**发表时的原文**，它们同时也是引用信息 ——
-- 把 "Acupuncture for chronic pain" 译成中文再显示，读者拿这一串既检索不到也引用不了。
-- 所以 title/journal/abstract/authors 一律**照发表原样存一份**（中文期刊的论文就存中文），
-- 前台中英两种界面显示的都是它。页面上的栏目标题、按钮、字段名那些**版面文字**照旧走
-- i18n + `action_site_text`，与本表无关。
--
-- 【authors / affiliations / keywords 为什么是 JSON 文本而不是子表或 jsonb】
--   · 作者顺序就是署名顺序，是有学术含义的数据，任何会重排的存储形态都不能用；
--   · 作者与机构是「一篇论文内部的结构」，没有任何跨论文的查询/统计需求（不按作者检索、
--     不做作者主页），拆子表只是徒增两次 join 与一套级联维护；
--   · 存 text 而不是 jsonb：这两列永远整体读写、从不在库内按字段查，jsonb 的检索能力用不上，
--     而 text 让「这一列存的就是接口出参那串 JSON」这件事一眼可见。
-- 结构见 module_action/entity/vo/action_vo.py 的 PublicationModel：
--   authors      [{"name": "Zhang San", "affiliationIndex": 0}, ...]   affiliationIndex 可为 null
--   affiliations ["Guangzhou University of Chinese Medicine", ...]     下标即上面的 affiliationIndex
--   keywords     ["acupuncture", "chronic pain", ...]
--
-- 【status 的取值与参考实现相反，别看串】本表沿用全库口径 `0 正常 / 1 停用`
-- （后台的 sys_normal_disable 字典、公开接口的 only_published 都按这个走）。
--
-- 可重复执行。
-- ----------------------------

begin;

drop table if exists action_publication;
create table action_publication (
    publication_id   bigserial,
    title            varchar(500)  not null,
    authors          text,
    affiliations     text,
    abstract         text,
    keywords         text,
    journal          varchar(300)  default '',
    volume           varchar(50)   default '',
    issue            varchar(50)   default '',
    pages            varchar(50)   default '',
    publication_year int4,
    doi              varchar(200)  default '',
    source_url       varchar(500)  default '',
    pdf_url          varchar(500)  default '',
    cover_image_url  varchar(300)  default '',
    citation_text    text,
    sort_num         int4          default 0,
    status           char(1)       default '0',
    del_flag         char(1)       default '0',
    create_by        varchar(64)   default '',
    create_time      timestamp(0),
    update_by        varchar(64)   default '',
    update_time      timestamp(0),
    remark           varchar(500)  default null,
    primary key (publication_id)
);
comment on table  action_publication is '官网-成果发表';
comment on column action_publication.title is '论文标题（发表原文，逐字，不翻译）';
comment on column action_publication.authors is '作者 JSON 数组，顺序即署名顺序：[{"name":..,"affiliationIndex":0}]';
comment on column action_publication.affiliations is '机构 JSON 数组，下标对应 authors[].affiliationIndex';
comment on column action_publication.abstract is '摘要（发表原文纯文本）';
comment on column action_publication.keywords is '关键词 JSON 数组';
comment on column action_publication.journal is '期刊名称';
comment on column action_publication.volume is '卷';
comment on column action_publication.issue is '期';
comment on column action_publication.pages is '页码，如 145-152 或 102619';
comment on column action_publication.publication_year is '发表年份，列表页按它分组，为空时归入「未标注年份」';
comment on column action_publication.doi is 'DOI，如 10.1016/j.ctim.2024.103041；前台拼成 https://doi.org/ 链接';
comment on column action_publication.source_url is '出版社/期刊页面地址，前台「阅读原文」按钮，仅收 http(s)';
comment on column action_publication.pdf_url is 'PDF 全文地址（阿里云 OSS 公网直链），留空则前台不显示下载按钮';
comment on column action_publication.cover_image_url is '配图/封面地址（OSS 公网直链），留空则详情页用纯色页头';
comment on column action_publication.citation_text is '引用文本，留空时由后端按字段自动拼一条';
comment on column action_publication.sort_num is '同年内的显示顺序，越小越靠前';
comment on column action_publication.status is '状态（0正常 1停用），停用后不在官网列表与详情中出现';

-- 列表页永远是「按年倒序 + 年内按 sort_num」，且只取 status='0' del_flag='0'
create index if not exists idx_action_publication_year
    on action_publication (publication_year desc, sort_num, publication_id);

-- 后台按 DOI 查重的唯一入口。**不建唯一约束**：预印本与正式版、勘误与原文共用一个 DOI
-- 的情况真实存在，唯一约束会把这类记录挡在门外，而查重是人该做的判断
create index if not exists idx_action_publication_doi
    on action_publication (doi);

commit;

-- 无种子数据：这张表装的是甲方自己的发表成果，没人能替他们编。
-- 官网列表页有空态文案（`publications.empty`），后台录第一条之前不会开天窗。
