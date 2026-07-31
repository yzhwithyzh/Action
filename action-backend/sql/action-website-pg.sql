-- ============================================================================
-- ACTION 官网内容模块（module_action）建表脚本 · PostgreSQL
--
-- 本文件是 action_* 表结构与种子数据的【唯一权威来源】。
-- 历史上曾有人绕过它直接 ALTER 线上库并灌数据，导致文件与库脱节、种子无法复现；
-- 今后任何结构或种子变更都必须先改这里，再同步到库与 ORM（module_action/entity/do）。
--
-- 数据来源：根目录静态页面内联脚本中的演示数据，迁移入库后由 action-admin 维护。
-- action_guideline 的 6 条依据 action-frontend/pages/guidelines.vue 与 i18n 文案编写。
-- 报告规范的下载文件存阿里云 OSS、由后台上传，故 file_url_zh / file_url_en 初始为空串。
-- 命名约定沿用 RuoYi：下划线小写、审计四字段（create_by/create_time/update_by/update_time）、
-- status 用 char(1)（0 正常 1 停用）、del_flag 用 char(1)（0 存在 2 删除）。
-- 双语字段一律 *_zh / *_en 成对出现，对应 PRODUCT.md 的「双语平权」要求。
--
-- ⚠ 本文件对非空库是【破坏性】的：每张表前都有 drop table if exists，
--   直接在已投产的库上执行会连同后台维护的内容与用户提交的合作申请一起销毁
--   （action_collab_request 无种子、不可复现）。只应在空库或明确要重建时执行。
--   同理，末尾「序列水位」分节也不可单独补跑到已有数据的库上。
-- ============================================================================

-- 本文件为无 BOM UTF-8 且含大量中文。显式声明客户端编码，避免在 Windows 控制台
-- （默认代码页 936）下把 UTF-8 字节按 GBK 解释，造成中文静默乱码入库。
set client_encoding = 'UTF8';
set standard_conforming_strings = on;

-- ----------------------------
-- 1、新闻动态
-- ----------------------------
drop table if exists action_news;
create table action_news (
    news_id       bigserial,
    category_zh   varchar(50)   default '',
    category_en   varchar(50)   default '',
    title_zh      varchar(300)  not null,
    title_en      varchar(500)  default '',
    summary_zh    text,
    summary_en    text,
    content_zh    text,
    content_en    text,
    thumb_url     varchar(300)  default '',
    publish_date  date,
    is_top        char(1)       default '0',
    sort_num      int4          default 0,
    status        char(1)       default '0',
    del_flag      char(1)       default '0',
    create_by     varchar(64)   default '',
    create_time   timestamp(0),
    update_by     varchar(64)   default '',
    update_time   timestamp(0),
    remark        varchar(500)  default null,
    link_url      varchar(500)  default '',
    is_external   char(1)       default '0',
    primary key (news_id)
);
comment on table  action_news is '官网-新闻动态';
comment on column action_news.news_id is '新闻id';
comment on column action_news.category_zh is '分类（中文）';
comment on column action_news.category_en is '分类（英文）';
comment on column action_news.title_zh is '标题（中文）';
comment on column action_news.title_en is '标题（英文）';
comment on column action_news.summary_zh is '摘要（中文）';
comment on column action_news.summary_en is '摘要（英文）';
comment on column action_news.content_zh is '正文（中文）';
comment on column action_news.content_en is '正文（英文）';
comment on column action_news.thumb_url is '缩略图地址';
comment on column action_news.publish_date is '发布日期';
comment on column action_news.is_top is '是否置顶（0否 1是）';
comment on column action_news.sort_num is '显示顺序';
comment on column action_news.status is '状态（0正常 1停用）';
comment on column action_news.del_flag is '删除标志（0存在 2删除）';
comment on column action_news.link_url is '跳转链接（站内路由或外部URL）';
comment on column action_news.is_external is '是否外部链接（0否 1是）';
create index idx_action_news_pub on action_news (status, del_flag, publish_date desc);

-- action_news 种子数据（11 行）
insert into action_news (news_id, category_zh, category_en, title_zh, title_en, summary_zh, summary_en, content_zh, content_en, thumb_url, publish_date, is_top, sort_num, status, del_flag, create_by, create_time, update_by, update_time, remark, link_url, is_external) values (1, 'ACTION 小组动态', 'ACTION team', '针刺报告规范体系上线在线预览与下载', 'The acupuncture reporting-guideline system goes online for preview & download', '覆盖 STRICTA / SPIRIT / PRISMA / CARE / RIGHT / ARRIVE 六类规范，含条目清单、中英双语下载与版本管理。', 'Six study-design guideline sets (STRICTA, SPIRIT, PRISMA, CARE, RIGHT, ARRIVE) with checklists, bilingual documents and version management.', NULL, NULL, '/assets/news-guideline.png', '2026-07-01', '0', 0, '0', '0', 'migration', '2026-07-28 20:17:23', '', '2026-07-28 20:17:23', '原站精度为年月（2026-07），入库补为当月1日；原链接 guidelines.html', '/guidelines', '0');
insert into action_news (news_id, category_zh, category_en, title_zh, title_en, summary_zh, summary_en, content_zh, content_en, thumb_url, publish_date, is_top, sort_num, status, del_flag, create_by, create_time, update_by, update_time, remark, link_url, is_external) values (2, 'ACTION 小组动态', 'ACTION team', '方法学评估工具「系统综述重复性评估 SRD」上线', 'Methodology tool “Systematic Review Duplication (SRD)” launches', '导入两篇系统综述，逐条 AI 评估重复程度，输出可导出报告。', 'Import two systematic reviews for an AI-assisted, item-by-item duplication assessment with an exportable report.', NULL, NULL, '/assets/news-platform.png', '2026-07-01', '0', 1, '0', '0', 'migration', '2026-07-28 20:17:23', '', '2026-07-28 20:17:23', '原站精度为年月（2026-07），入库补为当月1日；原链接 srd.html', '/srd', '0');
insert into action_news (news_id, category_zh, category_en, title_zh, title_en, summary_zh, summary_en, content_zh, content_en, thumb_url, publish_date, is_top, sort_num, status, del_flag, create_by, create_time, update_by, update_time, remark, link_url, is_external) values (3, 'ACTION 小组动态', 'ACTION team', '报告助手进入内测', 'Reporting assistant enters closed beta', '五步向导：研究类型匹配、在线模板、内容校验、AI 辅助撰写、导出分享。', 'A five-step wizard: study-type matching, online templates, content validation, AI writing help and export/sharing.', NULL, NULL, '/assets/news-platform.png', '2026-06-01', '0', 2, '0', '0', 'migration', '2026-07-28 20:17:23', '', '2026-07-28 20:17:23', '原站精度为年月（2026-06），入库补为当月1日；原链接 assistant.html', '/assistant', '0');
insert into action_news (news_id, category_zh, category_en, title_zh, title_en, summary_zh, summary_en, content_zh, content_en, thumb_url, publish_date, is_top, sort_num, status, del_flag, create_by, create_time, update_by, update_time, remark, link_url, is_external) values (5, 'ACTION 小组动态', 'ACTION team', '实施科学工具 CFIR / ERIC / RE-AIM 针刺适配版内测', 'Implementation-science tools (CFIR / ERIC / RE-AIM) for acupuncture in beta', '以针刺适配 CFIR 评估障碍、ERIC 匹配策略、RE-AIM 评价转化。', 'Assess barriers with an acupuncture-adapted CFIR, match strategies via ERIC, evaluate translation with RE-AIM.', NULL, NULL, '/assets/news-guideline.png', '2026-06-01', '0', 4, '0', '0', 'migration', '2026-07-28 20:17:23', '', '2026-07-28 20:17:23', '原站精度为年月（2026-06），入库补为当月1日；原链接 implementation.html', '/implementation', '0');
insert into action_news (news_id, category_zh, category_en, title_zh, title_en, summary_zh, summary_en, content_zh, content_en, thumb_url, publish_date, is_top, sort_num, status, del_flag, create_by, create_time, update_by, update_time, remark, link_url, is_external) values (6, 'ACTION 小组动态', 'ACTION team', '国际顾问委员会完成首轮方法学评审', 'International advisory board completes first methodological review', '中韩循证医学、指南方法学与针灸临床专家完成对 ACTION 规范与工具的首轮联合评审。', 'Experts in evidence-based medicine, guideline methodology and acupuncture from China and the Republic of Korea reviewed ACTION’s guidelines and tools.', NULL, NULL, '/assets/news-collab.png', '2026-05-01', '0', 5, '0', '0', 'migration', '2026-07-28 20:17:23', '', '2026-07-28 20:17:23', '原站精度为年月（2026-05），入库补为当月1日；原链接 collaborate.html', '/collaborate', '0');
insert into action_news (news_id, category_zh, category_en, title_zh, title_en, summary_zh, summary_en, content_zh, content_en, thumb_url, publish_date, is_top, sort_num, status, del_flag, create_by, create_time, update_by, update_time, remark, link_url, is_external) values (4, '领域新闻', 'Field news', 'CARE 针刺病例报告扩展规范发表（BMJ EBM）', 'CARE extension for acupuncture case reports published (BMJ EBM)', '30 条目、13 领域，将 CARE 声明扩展至针刺病例报告。', 'A 30-item, 13-domain guideline extending the CARE statement to acupuncture case reports.', NULL, NULL, '/assets/logo-care.png', '2025-06-01', '0', 3, '0', '0', 'migration', '2026-07-28 20:17:23', '', '2026-07-28 20:17:23', '原站精度为年月（2025-06），入库补为当月1日；原链接 https://www.care-statement.org', 'https://www.care-statement.org', '1');
insert into action_news (news_id, category_zh, category_en, title_zh, title_en, summary_zh, summary_en, content_zh, content_en, thumb_url, publish_date, is_top, sort_num, status, del_flag, create_by, create_time, update_by, update_time, remark, link_url, is_external) values (7, '领域新闻', 'Field news', 'CONSORT 与 SPIRIT：试验与方案报告基准', 'CONSORT & SPIRIT: the trial and protocol reporting baselines', 'STRICTA 与 SPIRIT-TCM 针刺扩展所依据的国际声明。', 'The statements that STRICTA and SPIRIT-TCM extend for acupuncture trials and protocols.', NULL, NULL, '/assets/logo-consort.png', NULL, '0', 6, '0', '0', 'migration', '2026-07-28 20:17:23', '', '2026-07-28 20:17:23', '原站精度为年月（），入库补为当月1日；原链接 https://www.consort-spirit.org', 'https://www.consort-spirit.org', '1');
insert into action_news (news_id, category_zh, category_en, title_zh, title_en, summary_zh, summary_en, content_zh, content_en, thumb_url, publish_date, is_top, sort_num, status, del_flag, create_by, create_time, update_by, update_time, remark, link_url, is_external) values (8, '领域新闻', 'Field news', 'PRISMA 2020：证据合成的报告框架', 'PRISMA 2020: reporting framework for evidence synthesis', '支撑针刺 PRISMA 扩展的系统综述报告标准。', 'The systematic-review reporting standard underpinning PRISMA for Acupuncture.', NULL, NULL, '/assets/logo-prisma.png', NULL, '0', 7, '0', '0', 'migration', '2026-07-28 20:17:23', '', '2026-07-28 20:17:23', '原站精度为年月（），入库补为当月1日；原链接 https://www.prisma-statement.org', 'https://www.prisma-statement.org', '1');
insert into action_news (news_id, category_zh, category_en, title_zh, title_en, summary_zh, summary_en, content_zh, content_en, thumb_url, publish_date, is_top, sort_num, status, del_flag, create_by, create_time, update_by, update_time, remark, link_url, is_external) values (9, '领域新闻', 'Field news', 'ARRIVE 2.0：活体动物研究报告标准', 'ARRIVE 2.0: reporting standard for in vivo research', '支撑针刺机制研究的动物实验报告标准。', 'The reporting standard for animal studies that underpin acupuncture mechanism research.', NULL, NULL, '/assets/logo-arrive.png', NULL, '0', 8, '0', '0', 'migration', '2026-07-28 20:17:23', '', '2026-07-28 20:17:23', '原站精度为年月（），入库补为当月1日；原链接 https://arriveguidelines.org', 'https://arriveguidelines.org', '1');
insert into action_news (news_id, category_zh, category_en, title_zh, title_en, summary_zh, summary_en, content_zh, content_en, thumb_url, publish_date, is_top, sort_num, status, del_flag, create_by, create_time, update_by, update_time, remark, link_url, is_external) values (10, '领域新闻', 'Field news', 'EQUATOR Network：报告规范国际总枢纽', 'EQUATOR Network: the global reporting-guideline hub', 'ACTION 规范制定所遵循的方法学与注册枢纽。', 'The methodology and registry that ACTION’s guideline development follows.', NULL, NULL, '/assets/logo-equator.png', NULL, '0', 9, '0', '0', 'migration', '2026-07-28 20:17:23', '', '2026-07-28 20:17:23', '原站精度为年月（），入库补为当月1日；原链接 https://www.equator-network.org', 'https://www.equator-network.org', '1');
insert into action_news (news_id, category_zh, category_en, title_zh, title_en, summary_zh, summary_en, content_zh, content_en, thumb_url, publish_date, is_top, sort_num, status, del_flag, create_by, create_time, update_by, update_time, remark, link_url, is_external) values (11, '领域新闻', 'Field news', 'Cochrane：针灸系统综述与循证证据', 'Cochrane: systematic reviews & evidence in acupuncture', '针灸相关高质量证据合成的重要来源。', 'A leading source of high-quality evidence syntheses relevant to acupuncture.', NULL, NULL, '/assets/logo-cochrane.png', NULL, '0', 10, '0', '0', 'migration', '2026-07-28 20:17:23', '', '2026-07-28 20:17:23', '原站精度为年月（），入库补为当月1日；原链接 https://www.cochrane.org', 'https://www.cochrane.org', '1');

-- ----------------------------
-- 2、报告规范目录
-- ----------------------------
drop table if exists action_guideline;
create table action_guideline (
    guideline_id  bigserial,
    code          varchar(64)   not null,
    name_zh       varchar(300)  not null,
    name_en       varchar(500)  default '',
    study_type    varchar(64)   default '',
    summary_zh    text,
    summary_en    text,
    version       varchar(64)   default '',
    file_url_zh   varchar(500)  default '',
    file_url_en   varchar(500)  default '',
    external_url  varchar(500)  default '',
    logo_url      varchar(300)  default '',
    release_state varchar(32)   default 'open',
    sort_num      int4          default 0,
    status        char(1)       default '0',
    del_flag      char(1)       default '0',
    create_by     varchar(64)   default '',
    create_time   timestamp(0),
    update_by     varchar(64)   default '',
    update_time   timestamp(0),
    remark        varchar(500)  default null,
    primary key (guideline_id)
);
comment on table  action_guideline is '官网-报告规范目录';
comment on column action_guideline.code is '规范代号（CONSORT/STRICTA/SPIRIT…）';
comment on column action_guideline.study_type is '适用研究类型（rct/nrct/protocol/case/sr/obs/guideline/animal）';
comment on column action_guideline.release_state is '开放状态（open开放 beta内测 soon即将上线）';
comment on column action_guideline.file_url_zh is '中文版下载地址（文件存阿里云 OSS，由后台上传；初始为空串）';
comment on column action_guideline.file_url_en is '英文版下载地址（文件存阿里云 OSS，由后台上传；初始为空串）';
comment on column action_guideline.external_url is '外部官方链接（如已发表共识的 DOI 或官方站点）';
create unique index uk_action_guideline_code on action_guideline (lower(code)) where del_flag = '0';

-- action_guideline 种子数据（6 行）
insert into action_guideline (guideline_id, code, name_zh, name_en, study_type, summary_zh, summary_en, version, file_url_zh, file_url_en, external_url, logo_url, release_state, sort_num, status, del_flag, create_by, create_time, update_by, update_time, remark) values (1, 'STRICTA', 'STRICTA（针刺临床试验干预措施报告标准）', 'STRICTA (Standards for Reporting Interventions in Clinical Trials of Acupuncture)', 'rct', 'STRICTA（针刺临床试验干预措施报告标准）是 CONSORT 的官方扩展，规定 RCT 中针刺干预应如何报告：针刺理论依据、针刺细节（选穴、深度、得气反应）、治疗方案、联合干预、施术者背景，以及对照/对照措施的设置。', 'STRICTA (Standards for Reporting Interventions in Clinical Trials of Acupuncture) is a CONSORT extension. It specifies how acupuncture interventions should be reported in RCTs: acupuncture rationale, needling details (points, depth, response sought), treatment regimen, co-interventions, practitioner background and control/comparator.', '2010 修订 · 6 领域 / 17 条目', '', '', '', '', 'open', 0, '0', '0', 'migration', '2026-07-28 22:48:34', '', null, null);
insert into action_guideline (guideline_id, code, name_zh, name_en, study_type, summary_zh, summary_en, version, file_url_zh, file_url_en, external_url, logo_url, release_state, sort_num, status, del_flag, create_by, create_time, update_by, update_time, remark) values (2, 'SPIRIT', 'SPIRIT-TCM Extension 2018（中医药临床试验方案标准条目）', 'SPIRIT-TCM Extension 2018', 'protocol', 'SPIRIT-TCM Extension 2018 在 SPIRIT 声明（干预性试验方案标准条目）基础上针对中医药（含针刺）适配，规定试验方案在开始前需预先明确的内容，使计划中的方法在实施前即透明可核。', 'The SPIRIT-TCM Extension 2018 adapts the SPIRIT statement (Standard Protocol Items: Recommendations for Interventional Trials) for traditional Chinese medicine, including acupuncture. It guides what a trial protocol must pre-specify, so the planned methods are transparent before the trial begins.', '2018 扩展版', '', '', '', '', 'open', 1, '0', '0', 'migration', '2026-07-28 22:48:34', '', null, null);
insert into action_guideline (guideline_id, code, name_zh, name_en, study_type, summary_zh, summary_en, version, file_url_zh, file_url_en, external_url, logo_url, release_state, sort_num, status, del_flag, create_by, create_time, update_by, update_time, remark) values (3, 'PRISMA', 'PRISMA for Acupuncture（针刺系统综述与 Meta 分析报告规范）', 'PRISMA for Acupuncture', 'sr', 'PRISMA for Acupuncture 为综合针刺证据的系统综述与 Meta 分析提供报告条目，重点回应证据合成中如何处理针刺特有属性（干预细节、辨证分型、假针/安慰对照等）。', 'PRISMA for Acupuncture provides reporting items for systematic reviews and meta-analyses that synthesise acupuncture evidence, addressing how acupuncture-specific characteristics (intervention details, syndrome differentiation, sham/placebo controls) should be handled in evidence synthesis.', '现行清单', '', '', '', '/assets/logo-prisma.png', 'open', 2, '0', '0', 'migration', '2026-07-28 22:48:34', '', null, null);
insert into action_guideline (guideline_id, code, name_zh, name_en, study_type, summary_zh, summary_en, version, file_url_zh, file_url_en, external_url, logo_url, release_state, sort_num, status, del_flag, create_by, create_time, update_by, update_time, remark) values (4, 'CARE', 'CARE for Acupuncture（针刺病例报告规范）', 'CARE for Acupuncture', 'case', 'CARE for Acupuncture 将 CARE（病例报告）声明扩展至针刺病例报告与病例系列。它依循 EQUATOR 方法学、由国际多学科专家组制定，补齐了通用病例报告规范所缺失的针刺细节：针具类型、选穴与操作、辨证分型、得气与不良事件。', 'CARE for Acupuncture extends the CARE (CAse REport) statement to acupuncture case reports and case series. Developed under the EQUATOR methodology by an international, multidisciplinary panel, it adds the acupuncture-specific detail that generic case-report guidance omits — needle type, point selection and operation, syndrome differentiation, de qi, and adverse events.', 'v1.0 · 13 领域 / 30 条目', '', '', 'https://doi.org/10.1136/bmjebm-2025-113641', '/assets/logo-care.png', 'open', 3, '0', '0', 'migration', '2026-07-28 22:48:34', '', null, null);
insert into action_guideline (guideline_id, code, name_zh, name_en, study_type, summary_zh, summary_en, version, file_url_zh, file_url_en, external_url, logo_url, release_state, sort_num, status, del_flag, create_by, create_time, update_by, update_time, remark) values (5, 'RIGHT', 'RIGHT for Acupuncture（针刺临床实践指南报告规范）', 'RIGHT for Acupuncture', 'guideline', 'RIGHT for Acupuncture 将 RIGHT（卫生实践指南报告条目）声明扩展至含针刺推荐的临床实践指南，使指南制定者透明报告证据基础、推荐强度与针刺相关细节。', 'RIGHT for Acupuncture extends the RIGHT (Reporting Items for practice Guidelines in HealThcare) statement to clinical practice guidelines that include acupuncture recommendations, so guideline developers report the evidence base, recommendation strength and acupuncture specifics transparently.', '现行版', '', '', '', '', 'open', 4, '0', '0', 'migration', '2026-07-28 22:48:34', '', null, null);
insert into action_guideline (guideline_id, code, name_zh, name_en, study_type, summary_zh, summary_en, version, file_url_zh, file_url_en, external_url, logo_url, release_state, sort_num, status, del_flag, create_by, create_time, update_by, update_time, remark) values (6, 'ARRIVE', 'ARRIVE 2.0（活体动物实验报告规范）', 'ARRIVE 2.0 (Animal Research: Reporting of In Vivo Experiments)', 'animal', 'ARRIVE 2.0（活体动物实验报告规范）规范动物研究的报告，是支撑针刺科学的机制与临床前研究基础。其「核心 10 项」与推荐条目覆盖研究设计、样本量、随机化、盲法、结局指标与统计分析。', 'ARRIVE 2.0 (Animal Research: Reporting of In Vivo Experiments) governs the reporting of animal studies — the mechanism and pre-clinical research that underpins acupuncture science. The ''Essential 10'' plus the recommended set cover study design, sample size, randomisation, blinding, outcome measures and statistics.', '2.0 版（2020）', '', '', '', '/assets/logo-arrive.png', 'open', 5, '0', '0', 'migration', '2026-07-28 22:48:34', '', null, null);

-- ----------------------------
-- 3、研究类型（报告助手：类型 -> 规范 + 统计推荐）
-- ----------------------------
drop table if exists action_study_type;
create table action_study_type (
    type_id       bigserial,
    type_key      varchar(32)   not null,
    name_zh       varchar(200)  not null,
    name_en       varchar(300)  default '',
    hot_guideline varchar(64)   default '',
    sort_num      int4          default 0,
    status        char(1)       default '0',
    create_by     varchar(64)   default '',
    create_time   timestamp(0),
    update_by     varchar(64)   default '',
    update_time   timestamp(0),
    primary key (type_id)
);
comment on table  action_study_type is '官网-研究类型';
comment on column action_study_type.type_key is '类型标识（rct/nrct/case/sr/obs）';
comment on column action_study_type.hot_guideline is '重点推荐规范代号';
create unique index uk_action_study_type_key on action_study_type (type_key);

-- action_study_type 种子数据（5 行）
insert into action_study_type (type_id, type_key, name_zh, name_en, hot_guideline, sort_num, status, create_by, create_time, update_by, update_time) values (1, 'rct', '随机对照试验 RCT', 'Randomised Controlled Trial', 'STRICTA', 0, '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_study_type (type_id, type_key, name_zh, name_en, hot_guideline, sort_num, status, create_by, create_time, update_by, update_time) values (2, 'nrct', '非随机对照试验', 'Non-randomised controlled trial', 'STRICTA', 1, '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_study_type (type_id, type_key, name_zh, name_en, hot_guideline, sort_num, status, create_by, create_time, update_by, update_time) values (3, 'case', '病例报告 / 系列', 'Case report / series', 'CARE', 2, '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_study_type (type_id, type_key, name_zh, name_en, hot_guideline, sort_num, status, create_by, create_time, update_by, update_time) values (4, 'sr', '系统评价 / Meta 分析', 'Systematic review / Meta-analysis', 'PRISMA', 3, '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_study_type (type_id, type_key, name_zh, name_en, hot_guideline, sort_num, status, create_by, create_time, update_by, update_time) values (5, 'obs', '观察性研究', 'Observational study', 'STROBE', 4, '0', 'migration', '2026-07-28 20:06:51', '', NULL);

drop table if exists action_study_type_guideline;
create table action_study_type_guideline (
    id            bigserial,
    type_id       bigint        not null,
    guideline_code varchar(64)  not null,
    sort_num      int4          default 0,
    primary key (id)
);
comment on table action_study_type_guideline is '官网-研究类型与报告规范关联';
create index idx_astg_type on action_study_type_guideline (type_id);

-- action_study_type_guideline 种子数据（10 行）
insert into action_study_type_guideline (id, type_id, guideline_code, sort_num) values (1, 1, 'CONSORT', 0);
insert into action_study_type_guideline (id, type_id, guideline_code, sort_num) values (2, 1, 'STRICTA', 1);
insert into action_study_type_guideline (id, type_id, guideline_code, sort_num) values (3, 1, 'SPIRIT', 2);
insert into action_study_type_guideline (id, type_id, guideline_code, sort_num) values (4, 2, 'STRICTA', 0);
insert into action_study_type_guideline (id, type_id, guideline_code, sort_num) values (5, 2, 'TREND', 1);
insert into action_study_type_guideline (id, type_id, guideline_code, sort_num) values (6, 3, 'CARE', 0);
insert into action_study_type_guideline (id, type_id, guideline_code, sort_num) values (7, 3, '针刺专病条目', 1);
insert into action_study_type_guideline (id, type_id, guideline_code, sort_num) values (8, 4, 'PRISMA', 0);
insert into action_study_type_guideline (id, type_id, guideline_code, sort_num) values (9, 4, '针刺检索策略', 1);
insert into action_study_type_guideline (id, type_id, guideline_code, sort_num) values (10, 5, 'STROBE', 0);

drop table if exists action_study_type_stat;
create table action_study_type_stat (
    id            bigserial,
    type_id       bigint        not null,
    text_zh       varchar(500)  not null,
    text_en       varchar(800)  default '',
    sort_num      int4          default 0,
    primary key (id)
);
comment on table action_study_type_stat is '官网-研究类型统计方法推荐';
create index idx_asts_type on action_study_type_stat (type_id);

-- action_study_type_stat 种子数据（14 行）
insert into action_study_type_stat (id, type_id, text_zh, text_en, sort_num) values (1, 1, '组间比较：t 检验 / Mann–Whitney U 检验', 'Between-group: t-test / Mann–Whitney U', 0);
insert into action_study_type_stat (id, type_id, text_zh, text_en, sort_num) values (2, 1, '分类资料：卡方 / Fisher 检验', 'Categorical: chi-square / Fisher', 1);
insert into action_study_type_stat (id, type_id, text_zh, text_en, sort_num) values (3, 1, '重复测量：混合效应模型 / GEE', 'Repeated measures: mixed models / GEE', 2);
insert into action_study_type_stat (id, type_id, text_zh, text_en, sort_num) values (4, 2, '组间比较并校正混杂：协方差分析 / 倾向评分', 'Adjusted comparison: ANCOVA / propensity score', 0);
insert into action_study_type_stat (id, type_id, text_zh, text_en, sort_num) values (5, 2, '分类资料：卡方检验', 'Categorical: chi-square', 1);
insert into action_study_type_stat (id, type_id, text_zh, text_en, sort_num) values (6, 2, '敏感性分析：多因素回归', 'Sensitivity: multivariable regression', 2);
insert into action_study_type_stat (id, type_id, text_zh, text_en, sort_num) values (7, 3, '以描述性统计为主，通常无需推断统计', 'Descriptive statistics; inferential tests usually not required', 0);
insert into action_study_type_stat (id, type_id, text_zh, text_en, sort_num) values (8, 3, '时间线与转归的可视化呈现', 'Visualise timeline and outcomes', 1);
insert into action_study_type_stat (id, type_id, text_zh, text_en, sort_num) values (9, 4, '合并效应：随机 / 固定效应模型', 'Pooled effect: random / fixed-effects model', 0);
insert into action_study_type_stat (id, type_id, text_zh, text_en, sort_num) values (10, 4, '异质性：I² 与 Q 检验', 'Heterogeneity: I² and Q-test', 1);
insert into action_study_type_stat (id, type_id, text_zh, text_en, sort_num) values (11, 4, '发表偏倚：漏斗图 / Egger 检验', 'Publication bias: funnel plot / Egger', 2);
insert into action_study_type_stat (id, type_id, text_zh, text_en, sort_num) values (12, 5, '多因素回归：Logistic / Cox 模型', 'Multivariable regression: Logistic / Cox', 0);
insert into action_study_type_stat (id, type_id, text_zh, text_en, sort_num) values (13, 5, '混杂校正：分层 / 倾向评分', 'Confounding: stratification / propensity score', 1);
insert into action_study_type_stat (id, type_id, text_zh, text_en, sort_num) values (14, 5, '分类资料：卡方检验', 'Categorical: chi-square', 2);

-- ----------------------------
-- 4、CFIR 针刺版：领域 -> 构念 -> 应对策略
-- ----------------------------
drop table if exists action_cfir_domain;
create table action_cfir_domain (
    domain_id     bigserial,
    seq           int4          not null,
    name_zh       varchar(200)  not null,
    name_en       varchar(300)  default '',
    status        char(1)       default '0',
    create_by     varchar(64)   default '',
    create_time   timestamp(0),
    update_by     varchar(64)   default '',
    update_time   timestamp(0),
    primary key (domain_id)
);
comment on table  action_cfir_domain is '官网-CFIR领域';
comment on column action_cfir_domain.seq is '领域序号';

-- action_cfir_domain 种子数据（5 行）
insert into action_cfir_domain (domain_id, seq, name_zh, name_en, status, create_by, create_time, update_by, update_time) values (1, 1, '创新（针刺疗法）', 'Innovation', '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_cfir_domain (domain_id, seq, name_zh, name_en, status, create_by, create_time, update_by, update_time) values (2, 2, '外部环境', 'Outer Setting', '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_cfir_domain (domain_id, seq, name_zh, name_en, status, create_by, create_time, update_by, update_time) values (3, 3, '内部环境', 'Inner Setting', '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_cfir_domain (domain_id, seq, name_zh, name_en, status, create_by, create_time, update_by, update_time) values (4, 4, '个人', 'Individuals', '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_cfir_domain (domain_id, seq, name_zh, name_en, status, create_by, create_time, update_by, update_time) values (5, 5, '实施过程', 'Implementation Process', '0', 'migration', '2026-07-28 20:06:51', '', NULL);

drop table if exists action_cfir_construct;
create table action_cfir_construct (
    construct_id  bigserial,
    domain_id     bigint        not null,
    code          varchar(64)   not null,
    name_zh       varchar(200)  not null,
    name_en       varchar(300)  default '',
    hint_zh       varchar(800)  default '',
    hint_en       varchar(1000) default '',
    severity      char(1)       default 'm',
    sort_num      int4          default 0,
    primary key (construct_id)
);
comment on table  action_cfir_construct is '官网-CFIR构念（障碍点）';
comment on column action_cfir_construct.severity is '严重度（h高 m中 l低）';
create index idx_acc_domain on action_cfir_construct (domain_id);

-- action_cfir_construct 种子数据（21 行）
insert into action_cfir_construct (construct_id, domain_id, code, name_zh, name_en, hint_zh, hint_en, severity, sort_num) values (1, 1, 'evidence', '证据来源', 'Evidence source', '证据数量与质量、团队名誉与影响力', 'Volume/quality of evidence, team reputation & impact', 'm', 0);
insert into action_cfir_construct (construct_id, domain_id, code, name_zh, name_en, hint_zh, hint_en, severity, sort_num) values (2, 1, 'character', '针刺特性', 'Innovation characteristics', '复杂性高、可调整、标准化不足', 'High complexity, adaptable, under-standardised', 'h', 1);
insert into action_cfir_construct (construct_id, domain_id, code, name_zh, name_en, hint_zh, hint_en, severity, sort_num) values (3, 1, 'cost', '经济花费', 'Cost', '器械与技术成本', 'Equipment & technique cost', 'm', 2);
insert into action_cfir_construct (construct_id, domain_id, code, name_zh, name_en, hint_zh, hint_en, severity, sort_num) values (4, 2, 'accept', '针刺接受度', 'Acupuncture acceptance', '当地社会与患者对针刺的接受度', 'Local public & patient acceptance', 'm', 0);
insert into action_cfir_construct (construct_id, domain_id, code, name_zh, name_en, hint_zh, hint_en, severity, sort_num) values (5, 2, 'localcond', '当地针刺条件', 'Local conditions', '当地医疗条件与社会支持', 'Local care conditions & social support', 'l', 1);
insert into action_cfir_construct (construct_id, domain_id, code, name_zh, name_en, hint_zh, hint_en, severity, sort_num) values (6, 2, 'collab', '跨学科协作', 'Cross-disciplinary collaboration', '转诊网络、跨学科会诊、学术联盟', 'Referral networks, MDT, academic alliances', 'h', 2);
insert into action_cfir_construct (construct_id, domain_id, code, name_zh, name_en, hint_zh, hint_en, severity, sort_num) values (7, 2, 'policy', '外部政策与激励', 'External policy & incentives', '政策法规、专家指南、外部资金', 'Policy, expert guidelines, external funding', 'm', 3);
insert into action_cfir_construct (construct_id, domain_id, code, name_zh, name_en, hint_zh, hint_en, severity, sort_num) values (8, 2, 'pressure', '外部压力', 'External pressure', '同行、公众舆论、绩效压力', 'Peer, public-opinion, performance pressure', 'l', 4);
insert into action_cfir_construct (construct_id, domain_id, code, name_zh, name_en, hint_zh, hint_en, severity, sort_num) values (9, 3, 'resource', '针刺资源可及性', 'Resource availability', '资金、场所、材料与设备', 'Funding, space, materials & equipment', 'h', 0);
insert into action_cfir_construct (construct_id, domain_id, code, name_zh, name_en, hint_zh, hint_en, severity, sort_num) values (10, 3, 'fit', '关系与情景适配', 'Relations & context fit', '关系网络、临床情境、患者生活情境', 'Networks, clinical & patient-life context', 'm', 1);
insert into action_cfir_construct (construct_id, domain_id, code, name_zh, name_en, hint_zh, hint_en, severity, sort_num) values (11, 3, 'comm', '沟通交流', 'Communication', '医患沟通、跨科沟通', 'Patient–clinician & cross-department', 'm', 2);
insert into action_cfir_construct (construct_id, domain_id, code, name_zh, name_en, hint_zh, hint_en, severity, sort_num) values (12, 3, 'culture', '专业与组织文化', 'Professional & org culture', '价值观、以患者为中心、从业者福祉', 'Values, patient-centredness, staff wellbeing', 'm', 3);
insert into action_cfir_construct (construct_id, domain_id, code, name_zh, name_en, hint_zh, hint_en, severity, sort_num) values (13, 3, 'knowledge', '针刺知识与信息获取', 'Knowledge & access to information', '实施指导与培训不足', 'Insufficient guidance & training', 'h', 4);
insert into action_cfir_construct (construct_id, domain_id, code, name_zh, name_en, hint_zh, hint_en, severity, sort_num) values (14, 4, 'role', '角色定位', 'Roles', '管理者、负责人、专家、带教、质控、患者家属', 'Managers, leads, experts, mentors, QC, patients', 'm', 0);
insert into action_cfir_construct (construct_id, domain_id, code, name_zh, name_en, hint_zh, hint_en, severity, sort_num) values (15, 4, 'implementer', '实施者特征', 'Implementer characteristics', '能力、机会、动力、专业发展需求', 'Capability, opportunity, motivation, development', 'h', 1);
insert into action_cfir_construct (construct_id, domain_id, code, name_zh, name_en, hint_zh, hint_en, severity, sort_num) values (16, 4, 'recipient', '接受者特征', 'Recipient characteristics', '健康需求、认知理解、耐受配合、治疗动力', 'Health need, understanding, tolerance, motivation', 'm', 2);
insert into action_cfir_construct (construct_id, domain_id, code, name_zh, name_en, hint_zh, hint_en, severity, sort_num) values (17, 5, 'team', '团队组建', 'Team assembly', '多角色协作团队与职责边界', 'Multi-role team & role boundaries', 'm', 0);
insert into action_cfir_construct (construct_id, domain_id, code, name_zh, name_en, hint_zh, hint_en, severity, sort_num) values (18, 5, 'assess', '需求与环境评估', 'Needs & context assessment', '患者/医生需求、障碍与促进因素', 'Patient/clinician needs, barriers & facilitators', 'h', 1);
insert into action_cfir_construct (construct_id, domain_id, code, name_zh, name_en, hint_zh, hint_en, severity, sort_num) values (19, 5, 'plan', '方案制定', 'Planning', '职责、步骤、短期目标与成功指标', 'Roles, steps, short-term goals & metrics', 'm', 2);
insert into action_cfir_construct (construct_id, domain_id, code, name_zh, name_en, hint_zh, hint_en, severity, sort_num) values (20, 5, 'adjust', '动态调整', 'Dynamic adaptation', '依反馈动态调整策略', 'Adapt strategies from feedback', 'm', 3);
insert into action_cfir_construct (construct_id, domain_id, code, name_zh, name_en, hint_zh, hint_en, severity, sort_num) values (21, 5, 'feedback', '疗效反馈与评价', 'Outcome feedback', '即时主观与远期客观疗效', 'Immediate subjective & long-term objective outcomes', 'm', 4);

drop table if exists action_cfir_strategy;
create table action_cfir_strategy (
    strategy_id   bigserial,
    construct_id  bigint        not null,
    name_zh       varchar(300)  not null,
    name_en       varchar(500)  default '',
    detail_zh     text,
    detail_en     text,
    source_zh     varchar(300)  default '',
    source_en     varchar(500)  default '',
    sort_num      int4          default 0,
    primary key (strategy_id)
);
comment on table action_cfir_strategy is '官网-CFIR构念对应的实施策略';
create index idx_acs_construct on action_cfir_strategy (construct_id);

-- action_cfir_strategy 种子数据（21 行）
insert into action_cfir_strategy (strategy_id, construct_id, name_zh, name_en, detail_zh, detail_en, source_zh, source_en, sort_num) values (1, 1, '汇总并补强高质量证据', 'Consolidate & strengthen evidence', '以系统评价与真实世界研究补强疗效与安全性证据链。', 'Strengthen efficacy/safety evidence via systematic reviews and real-world studies.', 'ERIC·本地需求评估 / 学术合作', '', 0);
insert into action_cfir_strategy (strategy_id, construct_id, name_zh, name_en, detail_zh, detail_en, source_zh, source_en, sort_num) values (2, 2, '制定标准化操作方案（SOP）', 'Develop standardised SOPs', '将复杂手法拆解为可复制步骤，并保留必要的可调整空间。', 'Break complex techniques into reproducible steps while keeping needed adaptability.', 'ERIC·制作教育材料 / 提升可适应性', '', 0);
insert into action_cfir_strategy (strategy_id, construct_id, name_zh, name_en, detail_zh, detail_en, source_zh, source_en, sort_num) values (3, 3, '优化成本并争取资金', 'Optimise cost, secure funding', '争取医保或专项资金，优化耗材与流程成本。', 'Pursue insurance/dedicated funding; optimise consumable and process costs.', 'ERIC·获取新资金 / 调整激励结构', '', 0);
insert into action_cfir_strategy (strategy_id, construct_id, name_zh, name_en, detail_zh, detail_en, source_zh, source_en, sort_num) values (4, 4, '公众科普与患者教育', 'Public & patient education', '通过科普与患教提升社会与患者对针刺的接受度。', 'Raise acceptance through outreach and patient education.', 'ERIC·患者宣教 / 让患者积极参与', '', 0);
insert into action_cfir_strategy (strategy_id, construct_id, name_zh, name_en, detail_zh, detail_en, source_zh, source_en, sort_num) values (5, 5, '配置诊疗条件与社会支持', 'Provision conditions & support', '改善场所设备，并链接社会支持资源。', 'Improve facilities/equipment and link social-support resources.', 'ERIC·改变物理结构与设备', '', 0);
insert into action_cfir_strategy (strategy_id, construct_id, name_zh, name_en, detail_zh, detail_en, source_zh, source_en, sort_num) values (6, 6, '建立转诊网络与多学科会诊', 'Build referral network & MDT', '与西医等科室建立转诊与联合会诊机制。', 'Set up referral and joint-consultation mechanisms with other departments.', 'ERIC·组建联盟 / 促进临床数据传递', '', 0);
insert into action_cfir_strategy (strategy_id, construct_id, name_zh, name_en, detail_zh, detail_en, source_zh, source_en, sort_num) values (7, 7, '对接政策与激励', 'Engage policy & incentives', '争取政策支持、专家指南背书与外部资金。', 'Secure policy support, guideline endorsement and external funding.', 'ERIC·获取新资金 / 使用顾问委员会', '', 0);
insert into action_cfir_strategy (strategy_id, construct_id, name_zh, name_en, detail_zh, detail_en, source_zh, source_en, sort_num) values (8, 8, '引入标杆与同行学习', 'Benchmarking & peer learning', '建立学习共同体、公开绩效，形成良性外部压力。', 'Create learning collaboratives and transparent performance to build positive pressure.', 'ERIC·创建学习协作组 / 使用大众媒体', '', 0);
insert into action_cfir_strategy (strategy_id, construct_id, name_zh, name_en, detail_zh, detail_en, source_zh, source_en, sort_num) values (9, 9, '保障资金、场所与设备', 'Secure funding, space, equipment', '配置资金、诊疗场所与设备及安全防护条件。', 'Provision funding, treatment space, equipment and safety measures.', 'ERIC·改变物理结构与设备 / 获取新资金', '', 0);
insert into action_cfir_strategy (strategy_id, construct_id, name_zh, name_en, detail_zh, detail_en, source_zh, source_en, sort_num) values (10, 10, '优化临床流程嵌入', 'Embed into clinical workflow', '将针刺嵌入现有诊疗流程，并适配患者生活情境。', 'Embed acupuncture into existing workflows and fit patients’ life context.', 'ERIC·提升可适应性 / 量身定制策略', '', 0);
insert into action_cfir_strategy (strategy_id, construct_id, name_zh, name_en, detail_zh, detail_en, source_zh, source_en, sort_num) values (11, 11, '建立常态化沟通机制', 'Establish communication routines', '建立医患与跨科的常态化沟通与信息传递。', 'Set up routine patient and cross-department communication and data relay.', 'ERIC·促进临床数据传递 / 组织团队会议', '', 0);
insert into action_cfir_strategy (strategy_id, construct_id, name_zh, name_en, detail_zh, detail_en, source_zh, source_en, sort_num) values (12, 12, '培育以患者为中心的文化', 'Cultivate patient-centred culture', '树立冠军与意见领袖，培育支持性专业文化。', 'Identify champions and opinion leaders; grow a supportive culture.', 'ERIC·识别并培养冠军 / 告知意见领袖', '', 0);
insert into action_cfir_strategy (strategy_id, construct_id, name_zh, name_en, detail_zh, detail_en, source_zh, source_en, sort_num) values (13, 13, '规范化培训与临床带教', 'Standardised training & mentoring', '开展规范化培训、持续督导与临床带教。', 'Deliver standardised training, ongoing supervision and clinical mentoring.', 'ERIC·教育会议 / 持续培训 / 教育材料', '', 0);
insert into action_cfir_strategy (strategy_id, construct_id, name_zh, name_en, detail_zh, detail_en, source_zh, source_en, sort_num) values (14, 14, '明确角色并设立冠军', 'Clarify roles, appoint champions', '明确各角色职责边界，培养实施冠军与带头人。', 'Define role boundaries; develop implementation champions and leaders.', 'ERIC·识别并培养冠军 / 准备实施团队', '', 0);
insert into action_cfir_strategy (strategy_id, construct_id, name_zh, name_en, detail_zh, detail_en, source_zh, source_en, sort_num) values (15, 15, '持续培训与激励认同', 'Ongoing training & motivation', '以培训、督导、审计反馈与激励提升能力与动力。', 'Raise capability and motivation via training, supervision, audit-feedback and incentives.', 'ERIC·持续培训 / 临床督导 / 审计与反馈', '', 0);
insert into action_cfir_strategy (strategy_id, construct_id, name_zh, name_en, detail_zh, detail_en, source_zh, source_en, sort_num) values (16, 16, '患者教育与依从支持', 'Patient education & adherence', '加强患教与依从性支持，提升配合度与治疗动力。', 'Strengthen patient education and adherence support to boost engagement.', 'ERIC·让患者积极参与 / 患者宣教', '', 0);
insert into action_cfir_strategy (strategy_id, construct_id, name_zh, name_en, detail_zh, detail_en, source_zh, source_en, sort_num) values (17, 17, '组建多角色实施团队', 'Assemble a multi-role team', '明确职责与跨科机制，组建针刺实施团队。', 'Define responsibilities and cross-department mechanisms; form the team.', 'ERIC·准备实施团队', '', 0);
insert into action_cfir_strategy (strategy_id, construct_id, name_zh, name_en, detail_zh, detail_en, source_zh, source_en, sort_num) values (18, 18, '开展本地需求与障碍评估', 'Local needs & barrier assessment', '系统识别障碍与促进因素，指导策略选择。', 'Systematically identify barriers/facilitators to guide strategy selection.', 'ERIC·本地需求评估 / 评估可实施性', '', 0);
insert into action_cfir_strategy (strategy_id, construct_id, name_zh, name_en, detail_zh, detail_en, source_zh, source_en, sort_num) values (19, 19, '制定实施蓝图与目标', 'Build an implementation blueprint', '明确职责、步骤与短期目标，预设成功指标。', 'Specify roles, steps, short-term goals and success metrics.', 'ERIC·制定正式实施蓝图', '', 0);
insert into action_cfir_strategy (strategy_id, construct_id, name_zh, name_en, detail_zh, detail_en, source_zh, source_en, sort_num) values (20, 20, '建立审计反馈与持续改进', 'Audit-feedback & continuous improvement', '依反馈动态调整策略，形成 PDCA 改进循环。', 'Adapt strategies from feedback in a PDCA improvement loop.', 'ERIC·审计与反馈 / 定期复盘', '', 0);
insert into action_cfir_strategy (strategy_id, construct_id, name_zh, name_en, detail_zh, detail_en, source_zh, source_en, sort_num) values (21, 21, '建立疗效监测与反馈', 'Outcome monitoring & feedback', '建立即时与远期疗效的监测与反馈工具。', 'Set up tools to monitor and feed back short- and long-term outcomes.', 'ERIC·开发质量监测工具', '', 0);

-- ----------------------------
-- 5、ERIC 策略库
-- ----------------------------
drop table if exists action_eric_strategy;
create table action_eric_strategy (
    eric_id       bigserial,
    category      varchar(64)   not null,
    name_zh       varchar(300)  not null,
    name_en       varchar(500)  default '',
    detail_zh     text,
    detail_en     text,
    map_zh        varchar(300)  default '',
    map_en        varchar(500)  default '',
    sort_num      int4          default 0,
    status        char(1)       default '0',
    create_by     varchar(64)   default '',
    create_time   timestamp(0),
    update_by     varchar(64)   default '',
    update_time   timestamp(0),
    primary key (eric_id)
);
comment on table  action_eric_strategy is '官网-ERIC实施策略库';
comment on column action_eric_strategy.category is '策略分类标识';
comment on column action_eric_strategy.map_zh is '对应CFIR构念（中文）';
create index idx_aes_cat on action_eric_strategy (category);

-- action_eric_strategy 种子数据（15 行）
insert into action_eric_strategy (eric_id, category, name_zh, name_en, detail_zh, detail_en, map_zh, map_en, sort_num, status, create_by, create_time, update_by, update_time) values (1, 'train', '开展针刺规范化培训', 'Conduct standardised acupuncture training', '对年轻医生与进修医生进行操作规范与安全培训。', 'Train junior and visiting clinicians in technique and safety.', '知识获取 · 实施者特征', 'Knowledge · Implementers', 0, '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_eric_strategy (eric_id, category, name_zh, name_en, detail_zh, detail_en, map_zh, map_en, sort_num, status, create_by, create_time, update_by, update_time) values (2, 'train', '制作标准化操作手册与教育材料', 'Develop SOP manuals & educational materials', '把复杂手法固化为可复制的操作手册与图示。', 'Turn complex techniques into reproducible manuals and visuals.', '针刺特性 · 知识获取', 'Innovation · Knowledge', 1, '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_eric_strategy (eric_id, category, name_zh, name_en, detail_zh, detail_en, map_zh, map_en, sort_num, status, create_by, create_time, update_by, update_time) values (3, 'train', '建立临床带教与督导制度', 'Provide clinical mentoring & supervision', '资深医师一对一带教，定期督导与反馈。', 'Senior-led mentoring with periodic supervision and feedback.', '知识获取 · 实施者特征', 'Knowledge · Implementers', 2, '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_eric_strategy (eric_id, category, name_zh, name_en, detail_zh, detail_en, map_zh, map_en, sort_num, status, create_by, create_time, update_by, update_time) values (4, 'collab', '组建多学科转诊网络', 'Build a multidisciplinary referral network', '与相关科室建立稳定的转诊与协作关系。', 'Establish stable referral and collaboration with other departments.', '跨学科协作', 'Collaboration', 3, '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_eric_strategy (eric_id, category, name_zh, name_en, detail_zh, detail_en, map_zh, map_en, sort_num, status, create_by, create_time, update_by, update_time) values (5, 'collab', '促进跨科临床数据与信息传递', 'Facilitate relay of clinical data across teams', '打通跨科的病情与疗效信息传递渠道。', 'Open channels for cross-team clinical and outcome data.', '沟通交流 · 跨学科协作', 'Communication · Collaboration', 4, '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_eric_strategy (eric_id, category, name_zh, name_en, detail_zh, detail_en, map_zh, map_en, sort_num, status, create_by, create_time, update_by, update_time) values (6, 'policy', '争取政策支持与外部资金', 'Access policy support & external funding', '对接政策法规、专家指南与专项/科研资金。', 'Engage policy, guidelines and dedicated/research funding.', '外部政策与激励 · 经济花费', 'Policy · Cost', 5, '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_eric_strategy (eric_id, category, name_zh, name_en, detail_zh, detail_en, map_zh, map_en, sort_num, status, create_by, create_time, update_by, update_time) values (7, 'policy', '调整绩效激励结构', 'Alter incentive & performance structures', '把针刺实施纳入绩效与激励，形成正向驱动。', 'Include acupuncture delivery in incentives to drive uptake.', '外部压力 · 外部政策', 'Pressure · Policy', 6, '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_eric_strategy (eric_id, category, name_zh, name_en, detail_zh, detail_en, map_zh, map_en, sort_num, status, create_by, create_time, update_by, update_time) values (8, 'plan', '开展本地需求与障碍评估', 'Conduct local needs & barrier assessment', '系统识别障碍与促进因素，作为策略输入。', 'Systematically identify barriers/facilitators as strategy input.', '需求与环境评估', 'Assessment', 7, '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_eric_strategy (eric_id, category, name_zh, name_en, detail_zh, detail_en, map_zh, map_en, sort_num, status, create_by, create_time, update_by, update_time) values (9, 'plan', '制定正式实施蓝图', 'Develop a formal implementation blueprint', '明确职责、步骤、时间表与成功指标。', 'Define roles, steps, timeline and success metrics.', '方案制定 · 团队组建', 'Planning · Team', 8, '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_eric_strategy (eric_id, category, name_zh, name_en, detail_zh, detail_en, map_zh, map_en, sort_num, status, create_by, create_time, update_by, update_time) values (10, 'qi', '建立审计与反馈循环', 'Audit and provide feedback', '定期审计执行与疗效，反馈驱动改进。', 'Periodically audit delivery and outcomes to drive improvement.', '动态调整 · 疗效反馈', 'Adaptation · Feedback', 9, '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_eric_strategy (eric_id, category, name_zh, name_en, detail_zh, detail_en, map_zh, map_en, sort_num, status, create_by, create_time, update_by, update_time) values (11, 'qi', '开发疗效质量监测工具', 'Develop outcome-monitoring tools', '建立即时与远期疗效的监测量表与看板。', 'Build scales/dashboards for short- and long-term outcomes.', '疗效反馈', 'Feedback', 10, '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_eric_strategy (eric_id, category, name_zh, name_en, detail_zh, detail_en, map_zh, map_en, sort_num, status, create_by, create_time, update_by, update_time) values (12, 'patient', '患者宣教并促其积极参与', 'Prepare patients to be active participants', '缓解针具顾虑，提升依从性与治疗动力。', 'Ease needle concerns; boost adherence and motivation.', '接受者特征 · 针刺接受度', 'Recipients · Acceptance', 11, '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_eric_strategy (eric_id, category, name_zh, name_en, detail_zh, detail_en, map_zh, map_en, sort_num, status, create_by, create_time, update_by, update_time) values (13, 'resource', '改善诊疗场所与设备配置', 'Change physical structure & equipment', '配置诊疗场所、针具设备与安全防护条件。', 'Provision space, needling equipment and safety measures.', '资源可及性 · 当地条件', 'Resources · Local conditions', 12, '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_eric_strategy (eric_id, category, name_zh, name_en, detail_zh, detail_en, map_zh, map_en, sort_num, status, create_by, create_time, update_by, update_time) values (14, 'culture', '识别并培养实施冠军', 'Identify and prepare champions', '发掘并支持推动针刺落地的关键人物。', 'Find and support key people who drive adoption.', '组织文化 · 角色定位', 'Culture · Roles', 13, '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_eric_strategy (eric_id, category, name_zh, name_en, detail_zh, detail_en, map_zh, map_en, sort_num, status, create_by, create_time, update_by, update_time) values (15, 'culture', '告知并动员本地意见领袖', 'Inform & mobilise local opinion leaders', '借助学术带头人影响同行态度与接受度。', 'Leverage opinion leaders to shift peer attitudes.', '组织文化 · 针刺接受度', 'Culture · Acceptance', 14, '0', 'migration', '2026-07-28 20:06:51', '', NULL);

drop table if exists action_eric_category;
create table action_eric_category (
    id            bigserial,
    cat_key       varchar(64)   not null,
    name_zh       varchar(200)  not null,
    name_en       varchar(300)  default '',
    sort_num      int4          default 0,
    primary key (id)
);
comment on table action_eric_category is '官网-ERIC策略分类';
create unique index uk_aec_key on action_eric_category (cat_key);

-- action_eric_category 种子数据（9 行）
insert into action_eric_category (id, cat_key, name_zh, name_en, sort_num) values (1, 'all', '全部', 'All', 0);
insert into action_eric_category (id, cat_key, name_zh, name_en, sort_num) values (2, 'train', '培训与能力', 'Training', 1);
insert into action_eric_category (id, cat_key, name_zh, name_en, sort_num) values (3, 'collab', '协作与网络', 'Collaboration', 2);
insert into action_eric_category (id, cat_key, name_zh, name_en, sort_num) values (4, 'policy', '政策与激励', 'Policy & incentives', 3);
insert into action_eric_category (id, cat_key, name_zh, name_en, sort_num) values (5, 'plan', '评估与规划', 'Assess & plan', 4);
insert into action_eric_category (id, cat_key, name_zh, name_en, sort_num) values (6, 'qi', '质控与反馈', 'Monitoring', 5);
insert into action_eric_category (id, cat_key, name_zh, name_en, sort_num) values (7, 'patient', '患者参与', 'Patient', 6);
insert into action_eric_category (id, cat_key, name_zh, name_en, sort_num) values (8, 'resource', '资源与环境', 'Resources', 7);
insert into action_eric_category (id, cat_key, name_zh, name_en, sort_num) values (9, 'culture', '领导与文化', 'Leadership', 8);

-- ----------------------------
-- 6、RE-AIM 维度
-- ----------------------------
drop table if exists action_reaim_dimension;
create table action_reaim_dimension (
    dim_id        bigserial,
    letter        char(1)       not null,
    name_zh       varchar(100)  not null,
    name_en       varchar(200)  default '',
    sub_title     varchar(200)  default '',
    definition_zh varchar(800)  default '',
    definition_en varchar(1000) default '',
    measure_zh    varchar(800)  default '',
    measure_en    varchar(1000) default '',
    score_text    varchar(32)   default '',
    sort_num      int4          default 0,
    status        char(1)       default '0',
    create_by     varchar(64)   default '',
    create_time   timestamp(0),
    update_by     varchar(64)   default '',
    update_time   timestamp(0),
    primary key (dim_id)
);
comment on table  action_reaim_dimension is '官网-RE-AIM维度';
comment on column action_reaim_dimension.letter is '维度首字母（R/E/A/I/M）';

-- action_reaim_dimension 种子数据（5 行）
insert into action_reaim_dimension (dim_id, letter, name_zh, name_en, sub_title, definition_zh, definition_en, measure_zh, measure_en, score_text, sort_num, status, create_by, create_time, update_by, update_time) values (1, 'R', '触及', 'Reach', 'Reach', '触及目标人群的比例与代表性。', 'Proportion and representativeness of the target population reached.', '门诊针刺覆盖率、目标病种触及率、拒绝率。', 'Outpatient coverage, target-condition reach, refusal rate.', '68%', 0, '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_reaim_dimension (dim_id, letter, name_zh, name_en, sub_title, definition_zh, definition_en, measure_zh, measure_en, score_text, sort_num, status, create_by, create_time, update_by, update_time) values (2, 'E', '有效性', 'Effectiveness', 'Effectiveness', '干预的疗效、不良反应与生活质量影响。', 'Efficacy, adverse events and quality-of-life impact.', '疼痛缓解率、AE 发生率、生活质量评分变化。', 'Pain-relief rate, AE rate, QoL change.', '中—高', 1, '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_reaim_dimension (dim_id, letter, name_zh, name_en, sub_title, definition_zh, definition_en, measure_zh, measure_en, score_text, sort_num, status, create_by, create_time, update_by, update_time) values (3, 'A', '采纳', 'Adoption', 'Adoption', '采纳该项目的机构、科室与医生比例。', 'Share of settings, departments and clinicians adopting it.', '开展针刺的科室占比、参与医生比例。', 'Share of departments/clinicians delivering acupuncture.', '中', 2, '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_reaim_dimension (dim_id, letter, name_zh, name_en, sub_title, definition_zh, definition_en, measure_zh, measure_en, score_text, sort_num, status, create_by, create_time, update_by, update_time) values (4, 'I', '实施', 'Implementation', 'Implementation', '实施保真度、一致性与成本。', 'Fidelity, consistency and cost of delivery.', 'SOP 依从率、按方案完成率、单次成本。', 'SOP adherence, per-protocol completion, unit cost.', '中—高', 3, '0', 'migration', '2026-07-28 20:06:51', '', NULL);
insert into action_reaim_dimension (dim_id, letter, name_zh, name_en, sub_title, definition_zh, definition_en, measure_zh, measure_en, score_text, sort_num, status, create_by, create_time, update_by, update_time) values (5, 'M', '维持', 'Maintenance', 'Maintenance', '项目的长期维持与制度化程度。', 'Long-term sustainment and institutionalisation.', '6 个月后持续开展率、是否纳入常规诊疗。', '6-month continuation, inclusion in routine care.', '待提升', 4, '0', 'migration', '2026-07-28 20:06:51', '', NULL);

-- ----------------------------
-- 7、SRD 系统综述重复性评估
-- ----------------------------
drop table if exists action_srd_assessment;
create table action_srd_assessment (
    assessment_id   bigserial,
    review_a_title_zh varchar(600) not null,
    review_a_title_en varchar(900) default '',
    review_b_title_zh varchar(600) not null,
    review_b_title_en varchar(900) default '',
    overall_level   varchar(16)   default 'mod',
    overall_pct     int4          default 0,
    overall_reason_zh text,
    overall_reason_en text,
    is_sample       char(1)       default '1',
    status          char(1)       default '0',
    del_flag        char(1)       default '0',
    create_by       varchar(64)   default '',
    create_time     timestamp(0),
    update_by       varchar(64)   default '',
    update_time     timestamp(0),
    primary key (assessment_id)
);
comment on table  action_srd_assessment is '官网-SRD系统综述重复性评估';
comment on column action_srd_assessment.overall_level is '整体判定（none无 low低 mod中 high高）';
comment on column action_srd_assessment.overall_pct is '整体重复度百分比';
comment on column action_srd_assessment.is_sample is '是否示例数据（0否 1是）';

-- action_srd_assessment 种子数据（1 行）
insert into action_srd_assessment (assessment_id, review_a_title_zh, review_a_title_en, review_b_title_zh, review_b_title_en, overall_level, overall_pct, overall_reason_zh, overall_reason_en, is_sample, status, del_flag, create_by, create_time, update_by, update_time) values (1, '针刺治疗慢性紧张型头痛的疗效与安全性：系统综述与 Meta 分析', 'Acupuncture for chronic tension-type headache: a systematic review and meta-analysis', '针灸对慢性紧张型头痛的效果：随机对照试验的系统评价', 'Effectiveness of acupuncture for chronic tension-type headache: a systematic review of RCTs', 'mod', 55, '两篇综述在研究主题上高度接近、在结果解释上部分重合，但方法与质量评估存在差异。判定为中度重复：存在显著重叠，建议人工复核纳入研究清单与合并策略后再决定是否合并或撤稿。', 'The two reviews are closely aligned on topic and partly overlap on results interpretation, while methods and quality appraisal differ. Verdict: Moderate duplication — substantial overlap; manual review of the included-study lists and pooling strategy is advised before deciding on merging or retraction.', '1', '0', '0', 'migration', '2026-07-28 20:06:51', '', NULL);

drop table if exists action_srd_domain;
create table action_srd_domain (
    domain_id     bigserial,
    assessment_id bigint        not null,
    seq           int4          not null,
    name_zh       varchar(200)  not null,
    name_en       varchar(300)  default '',
    is_key        char(1)       default '0',
    level         varchar(16)   default 'mod',
    pct           int4          default 0,
    primary key (domain_id)
);
comment on table  action_srd_domain is '官网-SRD评估领域';
comment on column action_srd_domain.is_key is '是否关键领域（0否 1是）';
create index idx_asd_assessment on action_srd_domain (assessment_id);

-- action_srd_domain 种子数据（4 行）
insert into action_srd_domain (domain_id, assessment_id, seq, name_zh, name_en, is_key, level, pct) values (1, 1, 1, '研究主题', 'Study topic', '1', 'mod', 63);
insert into action_srd_domain (domain_id, assessment_id, seq, name_zh, name_en, is_key, level, pct) values (2, 1, 2, '研究方法', 'Study methods', '0', 'low', 38);
insert into action_srd_domain (domain_id, assessment_id, seq, name_zh, name_en, is_key, level, pct) values (3, 1, 3, '研究结果', 'Study results', '1', 'low', 42);
insert into action_srd_domain (domain_id, assessment_id, seq, name_zh, name_en, is_key, level, pct) values (4, 1, 4, '研究质量', 'Study quality', '0', 'low', 30);

drop table if exists action_srd_group;
create table action_srd_group (
    group_id      bigserial,
    domain_id     bigint        not null,
    code          varchar(32)   default '',
    name_zh       varchar(300)  not null,
    name_en       varchar(500)  default '',
    sort_num      int4          default 0,
    primary key (group_id)
);
comment on table action_srd_group is '官网-SRD评估条目分组';
create index idx_asg_domain on action_srd_group (domain_id);

-- action_srd_group 种子数据（12 行）
insert into action_srd_group (group_id, domain_id, code, name_zh, name_en, sort_num) values (1, 1, '1', '确定范围和问题', 'Scope & research question', 0);
insert into action_srd_group (group_id, domain_id, code, name_zh, name_en, sort_num) values (2, 1, '2', '纳入标准与合成分组', 'Eligibility & synthesis grouping', 1);
insert into action_srd_group (group_id, domain_id, code, name_zh, name_en, sort_num) values (3, 2, '3', '检索与筛选研究', 'Searching & screening', 0);
insert into action_srd_group (group_id, domain_id, code, name_zh, name_en, sort_num) values (4, 2, '4', '数据收集', 'Data collection', 1);
insert into action_srd_group (group_id, domain_id, code, name_zh, name_en, sort_num) values (5, 2, '5', '效应指标', 'Effect measures', 2);
insert into action_srd_group (group_id, domain_id, code, name_zh, name_en, sort_num) values (6, 3, '6', '合成准备', 'Preparing for synthesis', 0);
insert into action_srd_group (group_id, domain_id, code, name_zh, name_en, sort_num) values (7, 3, '7', 'Meta 分析', 'Meta-analysis', 1);
insert into action_srd_group (group_id, domain_id, code, name_zh, name_en, sort_num) values (8, 3, '8', '结果解释', 'Interpretation of results', 2);
insert into action_srd_group (group_id, domain_id, code, name_zh, name_en, sort_num) values (9, 4, '9', '偏倚和利益冲突', 'Bias & conflicts of interest', 0);
insert into action_srd_group (group_id, domain_id, code, name_zh, name_en, sort_num) values (10, 4, '10', '偏倚风险', 'Risk of bias', 1);
insert into action_srd_group (group_id, domain_id, code, name_zh, name_en, sort_num) values (11, 4, '11', '缺失结果导致的偏倚', 'Bias from missing results', 2);
insert into action_srd_group (group_id, domain_id, code, name_zh, name_en, sort_num) values (12, 4, '12', '证据与 GRADE', 'Evidence & GRADE', 3);

drop table if exists action_srd_item;
create table action_srd_item (
    item_id       bigserial,
    group_id      bigint        not null,
    code          varchar(32)   default '',
    question_zh   text          not null,
    question_en   text,
    level         varchar(16)   default 'mod',
    pct           int4          default 0,
    basis_zh      text,
    basis_en      text,
    cite_a_zh     text,
    cite_a_en     text,
    cite_b_zh     text,
    cite_b_en     text,
    sort_num      int4          default 0,
    primary key (item_id)
);
comment on table  action_srd_item is '官网-SRD评估条目';
comment on column action_srd_item.basis_zh is '判定依据（中文）';
comment on column action_srd_item.cite_a_zh is '综述A原文引用（中文）';
comment on column action_srd_item.cite_b_zh is '综述B原文引用（中文）';
create index idx_asi_group on action_srd_item (group_id);

-- action_srd_item 种子数据（34 行）
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (1, 1, '1a', '系统综述的研究问题是否基于最新的决策需求而制定？', 'Is the research question framed around a current decision need?', 'mod', 60, '两篇均以“慢性紧张型头痛的针刺疗效”为决策问题，动机表述接近。', 'Both frame the decision question as acupuncture efficacy for chronic TTH, with near-identical motivation.', '前言：针对慢性紧张型头痛缺乏高质量证据而开展。', 'Intro: undertaken due to limited high-quality evidence for chronic TTH.', '背景：现有指南对针灸推荐证据不足，需系统评价。', 'Background: guideline evidence for acupuncture insufficient, review needed.', 0);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (2, 1, '1b', '这些系统综述的研究目标是否相似？', 'Are the review objectives similar?', 'high', 82, '研究目标几乎一致：评估针刺相较假针/常规治疗的疗效与安全性。', 'Objectives near-identical: efficacy and safety of acupuncture vs sham/usual care.', '目的：评价针刺对发作频率与疼痛强度的影响。', 'Aim: effect of acupuncture on attack frequency and pain intensity.', '目的：评估针灸对头痛频率、强度及生活质量的疗效。', 'Aim: acupuncture effect on frequency, intensity and quality of life.', 1);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (3, 2, '2a', '各系统综述中纳入的研究人群/患者/问题的特征是否相同？', 'Are the populations/patients/problems the same?', 'high', 85, '均为成人慢性紧张型头痛患者（ICHD 诊断标准）。', 'Both include adults with chronic TTH per ICHD criteria.', '纳入：≥18 岁，符合 ICHD-3 慢性 TTH。', 'Include: ≥18y, ICHD-3 chronic TTH.', '纳入：成人慢性紧张型头痛，病程≥3 个月。', 'Include: adult chronic TTH, ≥3 months.', 0);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (4, 2, '2b', '各系统综述中纳入研究的干预措施是否相同？', 'Are the interventions the same?', 'high', 80, '干预均为体针/电针，穴位方案相近。', 'Interventions are body/electro-acupuncture with similar point protocols.', '干预：手针与电针，主穴风池、太阳。', 'Intervention: manual & electro-acupuncture, GB20/EX-HN5.', '干预：针刺（含电针），常用风池、百会。', 'Intervention: acupuncture incl. electro, GB20/GV20.', 1);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (5, 2, '2c', '各系统综述中纳入研究的对照措施是否相同？', 'Are the comparators the same?', 'mod', 58, 'A 含假针与等待对照，B 仅假针与常规治疗，对照范围部分不同。', 'A includes sham and waitlist; B only sham and usual care — partly different.', '对照：假针、等待名单、常规护理。', 'Comparators: sham, waitlist, usual care.', '对照：假针与常规治疗。', 'Comparators: sham and usual care.', 2);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (6, 2, '2d', '各系统综述中纳入研究的结局指标是否相同？', 'Are the outcomes the same?', 'mod', 62, '主要结局均为头痛频率；次要结局 A 含 MIDAS，B 含 SF-36，部分不同。', 'Primary outcome frequency in both; secondary differ (A: MIDAS, B: SF-36).', '结局：月头痛天数、疼痛强度、MIDAS。', 'Outcomes: monthly headache days, intensity, MIDAS.', '结局：头痛频率、VAS、SF-36。', 'Outcomes: frequency, VAS, SF-36.', 3);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (7, 2, '2e', '各系统综述中纳入研究的类型是否相同？', 'Are the study designs the same?', 'mod', 70, '两篇均仅纳入 RCT。', 'Both restrict to RCTs.', '设计：仅随机对照试验。', 'Design: RCTs only.', '设计：随机对照试验（含准随机除外）。', 'Design: RCTs (quasi-randomised excluded).', 4);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (8, 2, '2f', '各系统综述中研究的范围是否相似？', 'Is the scope of the reviews similar?', 'low', 45, 'B 额外纳入亚洲地区非英文 RCT，范围较 A 更广。', 'B additionally includes non-English Asian RCTs — broader than A.', '范围：英文文献，1990–2021。', 'Scope: English literature, 1990–2021.', '范围：多语种，含中文数据库，1990–2023。', 'Scope: multi-language incl. Chinese DBs, 1990–2023.', 5);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (9, 3, '3a', '各系统综述是否使用了相同的数据库及其他文献检索来源？', 'Same databases and search sources?', 'low', 40, '共用 PubMed/Embase/Cochrane，但 B 另检索 CNKI、万方等中文库。', 'Share PubMed/Embase/Cochrane; B adds CNKI, Wanfang.', '检索：PubMed、Embase、Cochrane CENTRAL。', 'Search: PubMed, Embase, Cochrane CENTRAL.', '检索：上述三库 + CNKI、万方、维普。', 'Search: the three + CNKI, Wanfang, VIP.', 0);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (10, 3, '3b', '各系统综述的检索策略结构是否相似？', 'Similar search-strategy structure?', 'low', 44, '检索式主题词相近，但布尔组合与限定项不同。', 'Similar MeSH terms but different Boolean structure and limits.', '策略：acupuncture AND tension-type headache。', 'Strategy: acupuncture AND tension-type headache.', '策略：针灸/针刺 AND 头痛 AND 随机。', 'Strategy: acupuncture AND headache AND random*.', 1);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (11, 4, '4a', '两篇系统综述的数据来源是否相似？', 'Similar data sources?', 'mod', 55, '均从纳入 RCT 全文提取，部分作者邮件补充数据来源相同。', 'Both extract from included RCT full texts; some author-contact data overlap.', '数据：全文 + 补充材料。', 'Data: full text + supplements.', '数据：全文 + 作者补充 + 试验注册。', 'Data: full text + author contact + registries.', 0);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (12, 4, '4b', '各系统综述提取的数据类型和内容是否相似？', 'Similar extracted data types?', 'low', 42, 'A 提取效应量与置信区间，B 额外提取穴位与疗程细节。', 'A extracts effect sizes/CIs; B also extracts point and dose detail.', '提取：样本量、均值±SD、AE。', 'Extracted: n, mean±SD, AEs.', '提取：上述 + 选穴、频次、疗程。', 'Extracted: above + points, frequency, course.', 1);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (13, 5, '5a', '对于相同的结局指标，各系统综述的数据类型是否一致？', 'Same data type for shared outcomes?', 'low', 36, '头痛频率 A 用连续型 MD，B 部分用二分类应答率。', 'For frequency, A uses continuous MD; B partly uses responder RR.', '指标：MD（连续型）。', 'Measure: MD (continuous).', '指标：MD 与 RR 混合。', 'Measure: mix of MD and RR.', 0);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (14, 5, '5b', '对于结局指标，各系统综述选择的效应指标是否相同？', 'Same chosen effect measures?', 'none', 22, '效应指标选择差异较大，合并口径不一致。', 'Effect-measure choices differ notably; pooling metrics inconsistent.', '合并：SMD 随机效应。', 'Pooling: SMD random-effects.', '合并：MD 与 RR 分别合并。', 'Pooling: MD and RR separately.', 1);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (15, 6, '6a', '各系统综述纳入研究之间的重叠程度如何？', 'Overlap among included studies?', 'mod', 57, '两篇纳入 RCT 交集约 60%（12/20 与 12/18 重合）。', '~60% of included RCTs overlap (12/20 vs 12/18).', '纳入 20 项 RCT。', '20 RCTs included.', '纳入 18 项 RCT，其中 12 项与 A 相同。', '18 RCTs; 12 shared with A.', 0);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (16, 6, '6b', '各系统综述是否总结了每项研究的基本特征？', 'Summarised each study’s characteristics?', 'low', 40, '均有特征表，但字段与分组方式不同。', 'Both provide characteristics tables with different fields/grouping.', '特征表：国家、样本、干预、对照。', 'Table: country, n, intervention, control.', '特征表：含中医证型与疗程分层。', 'Table: adds TCM pattern and course strata.', 1);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (17, 6, '6c', '各系统综述是否比较了纳入研究的特征以判断可否合并？', 'Compared characteristics to judge poolability?', 'low', 38, 'A 明确判断合并合理性，B 以叙述为主。', 'A explicitly judges poolability; B is largely narrative.', '依临床与方法学异质性判断可合并。', 'Poolability judged on clinical/methodological heterogeneity.', '以叙述方式讨论差异。', 'Differences discussed narratively.', 2);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (18, 6, '6d', '两篇是否评估并筛选可用于合成的数据（多重性问题）？', 'Screened data for synthesis (multiplicity)?', 'none', 20, 'A 处理了多臂/多时点多重性，B 未明确说明。', 'A handles multi-arm/time-point multiplicity; B unclear.', '多臂试验合并共享对照组样本。', 'Multi-arm: shared control split.', '未报告多重性处理。', 'No multiplicity handling reported.', 3);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (19, 6, '6e', '两篇是否使用了相似的数据合成方法？', 'Similar synthesis methods?', 'mod', 52, '均以随机效应 Meta 分析为主，模型细节不同。', 'Both mainly random-effects meta-analysis; model details differ.', '随机效应（DerSimonian–Laird）。', 'Random-effects (DerSimonian–Laird).', '随机效应（REML）+ 亚组叙述。', 'Random-effects (REML) + subgroup narrative.', 4);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (20, 7, '7a', '各系统综述是否采用相同的方法处理异质性？', 'Same handling of heterogeneity?', 'low', 41, '均报告 I²，但阈值解读与处理不同。', 'Both report I² but interpret/handle thresholds differently.', 'I²>50% 触发亚组分析。', 'I²>50% triggers subgroup analysis.', 'I²>75% 改用叙述合成。', 'I²>75% switches to narrative synthesis.', 0);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (21, 7, '7b', '各系统综述是否采用相同的亚组分析策略？', 'Same subgroup strategy?', 'low', 35, 'A 按对照类型，B 按穴位方案，亚组维度不同。', 'A subgroups by comparator; B by point protocol.', '亚组：假针 vs 常规治疗。', 'Subgroup: sham vs usual care.', '亚组：手针 vs 电针。', 'Subgroup: manual vs electro.', 1);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (22, 7, '7c', '两篇是否以相同方式处理缺失数据？', 'Same handling of missing data?', 'none', 18, 'A 作者联系补齐，B 采用可得病例分析。', 'A contacts authors; B uses available-case analysis.', '缺失：作者补充或插补。', 'Missing: author contact/imputation.', '缺失：仅分析可得数据。', 'Missing: available-case only.', 2);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (23, 7, '7d', '两篇是否采用相同的敏感性分析策略？', 'Same sensitivity-analysis strategy?', 'low', 33, '均做偏倚风险敏感性分析，纳入/排除标准不同。', 'Both run risk-of-bias sensitivity analyses with different criteria.', '敏感性：排除高偏倚研究。', 'Sensitivity: exclude high-RoB studies.', '敏感性：排除小样本与非英文。', 'Sensitivity: exclude small/non-English.', 3);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (24, 8, '8a', '对于相同的结局，各系统综述是否采用了相同的统计模型？', 'Same statistical model for shared outcomes?', 'low', 44, '主要结局均随机效应，但 B 加入贝叶斯灵敏度分析。', 'Random-effects for primary in both; B adds Bayesian sensitivity.', '频率主义随机效应。', 'Frequentist random-effects.', '频率主义 + 贝叶斯复核。', 'Frequentist + Bayesian check.', 0);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (25, 8, '8b', '对于相同结局，合并效应的方向、大小和置信区间是否相似？', 'Similar pooled effect direction, size and CI?', 'mod', 66, '头痛频率均显著获益且方向一致，效应量接近（SMD≈-0.5）。', 'Both show significant benefit, same direction, SMD≈-0.5.', 'SMD -0.52（95%CI -0.78,-0.26）。', 'SMD -0.52 (95%CI -0.78,-0.26).', 'SMD -0.48（95%CI -0.71,-0.25）。', 'SMD -0.48 (95%CI -0.71,-0.25).', 1);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (26, 8, '8c', '对于可比结局，对干预效应方向和大小的实质性解释是否相似？', 'Similar substantive interpretation of effect?', 'mod', 60, '均判断针刺“中等程度获益、临床意义可能有限”，措辞相近。', 'Both conclude moderate benefit of possibly limited clinical significance.', '解释：统计显著但临床意义待定。', 'Interpretation: significant but clinical value uncertain.', '解释：有益但效应中等，需谨慎。', 'Interpretation: beneficial yet moderate, cautious.', 2);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (27, 8, '8d', '对结果在不同人群/场景的适用性判断是否实质相似？', 'Similar judgement on applicability?', 'low', 40, 'A 强调西方门诊适用，B 侧重亚洲人群，外推侧重不同。', 'A stresses Western outpatient; B emphasises Asian populations.', '适用：西方初级保健。', 'Applicability: Western primary care.', '适用：东亚门诊为主。', 'Applicability: mainly East-Asian clinics.', 3);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (28, 8, '8e', '基于总体证据，结论及实践/未来研究建议是否实质相似？', 'Similar conclusions and recommendations?', 'low', 47, '均建议开展更大样本 RCT；A 呼吁标准化假针，B 呼吁长期随访。', 'Both call for larger RCTs; A urges standardised sham, B long-term follow-up.', '建议：需高质量大样本 RCT。', 'Rec: high-quality large RCTs needed.', '建议：需长期随访与经济学评价。', 'Rec: long-term follow-up and economics.', 4);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (29, 9, '9', '两篇是否基于相似信息识别、报告并解释利益冲突及潜在偏倚，且对结果影响判断实质相似？', 'Similar COI/bias identification and impact judgement?', 'low', 34, '均声明无利益冲突；对盲法缺失导致的偏倚讨论深度不同。', 'Both declare no COI; depth of bias discussion (blinding) differs.', 'COI：无；讨论施针者不可盲。', 'COI: none; notes practitioner non-blinding.', 'COI：无；较少展开偏倚影响。', 'COI: none; limited bias-impact discussion.', 0);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (30, 10, '10a', '系统综述研究中使用什么方法测量偏倚风险？', 'What risk-of-bias tool was used?', 'low', 38, 'A 用 RoB 2.0，B 用旧版 Cochrane 工具，评估工具不同。', 'A uses RoB 2.0; B uses the older Cochrane tool.', '工具：Cochrane RoB 2.0。', 'Tool: Cochrane RoB 2.0.', '工具：Cochrane 2011 版。', 'Tool: Cochrane 2011.', 0);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (31, 10, '10b', '评估纳入研究偏倚风险时，对证据总体偏倚水平的判断是否实质相似？', 'Similar overall RoB judgement?', 'none', 24, 'A 判总体“中等偏倚”，B 判“较高偏倚”，结论方向不同。', 'A rates overall moderate RoB; B rates high — differing conclusions.', '总体：中等偏倚风险。', 'Overall: moderate RoB.', '总体：偏倚风险较高。', 'Overall: high RoB.', 1);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (32, 11, '11', '评估缺失结果偏倚时，对其是否及在多大程度上影响结果的结论是否实质相似？', 'Similar conclusion on missing-result bias impact?', 'none', 19, 'A 用漏斗图与 Egger 检验，B 未评估报告偏倚。', 'A uses funnel plot/Egger; B does not assess reporting bias.', '漏斗图对称，Egger p=0.21。', 'Funnel symmetric, Egger p=0.21.', '未评估发表偏倚。', 'Publication bias not assessed.', 0);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (33, 12, '12a', '系统综述研究中使用什么方法进行证据总结？', 'What method summarised the evidence?', 'low', 36, 'A 使用 GRADE 并制作 SoF 表，B 仅定性总结。', 'A applies GRADE with a SoF table; B summarises qualitatively.', 'GRADE + 证据概要表。', 'GRADE + Summary-of-Findings.', '定性证据总结，无 GRADE。', 'Qualitative summary, no GRADE.', 0);
insert into action_srd_item (item_id, group_id, code, question_zh, question_en, level, pct, basis_zh, basis_en, cite_a_zh, cite_a_en, cite_b_zh, cite_b_en, sort_num) values (34, 12, '12b', '对可比关键结局，证据确定性判断（如 GRADE）是否实质相似？', 'Similar certainty (GRADE) judgement for key outcomes?', 'low', 32, 'A 定为“低确定性”，B 未分级，无法直接对齐。', 'A rates low certainty; B ungraded, not directly comparable.', '确定性：低（降级：偏倚、不精确）。', 'Certainty: low (RoB, imprecision).', '未使用 GRADE 分级。', 'No GRADE rating.', 1);

-- ----------------------------
-- 8、协作与专家咨询申请（官网表单提交）
-- ----------------------------
drop table if exists action_collab_request;
create table action_collab_request (
    request_id    bigserial,
    request_type  varchar(32)   default 'consult',
    applicant     varchar(100)  not null,
    organization  varchar(300)  default '',
    email         varchar(200)  not null,
    phone         varchar(50)   default '',
    topic         varchar(300)  default '',
    content       text,
    source_lang   varchar(8)    default 'zh',
    source_ip     varchar(128)  default '',
    handle_status char(1)       default '0',
    handle_by     varchar(64)   default '',
    handle_time   timestamp(0),
    handle_remark varchar(1000) default '',
    del_flag      char(1)       default '0',
    create_time   timestamp(0),
    primary key (request_id)
);
comment on table  action_collab_request is '官网-协作与专家咨询申请';
comment on column action_collab_request.request_type is '申请类型（consult专家咨询 collab机构协作 feedback反馈）';
comment on column action_collab_request.handle_status is '处理状态（0待处理 1处理中 2已回复 3已关闭）';
comment on column action_collab_request.source_lang is '提交时的界面语言（zh/en）';
create index idx_acr_status on action_collab_request (handle_status, del_flag, create_time desc);

-- ----------------------------
-- 10、访客档案（官网 guest 账号的机构/职位扩展）
--
-- 官网访客账号的主表是 sys_user（user_type='01' 标记访客，见 sql/ruoyi-fastapi-pg.sql），
-- 本表只存后台用户表没有、而官网注册需要的「所属机构 / 职位」两项自由文本。
-- user_id 一对一关联 sys_user.user_id，用唯一索引兜住重复写入。
-- 本节排在「9、序列水位」之前，是为了让序列水位始终是文件的最后一节。
-- ----------------------------
drop table if exists action_guest_profile;
create table action_guest_profile (
    profile_id  bigserial,
    user_id     bigint       not null,
    institution varchar(300) default '',
    position    varchar(100) default '',
    del_flag    char(1)      default '0',
    create_time timestamp(0),
    update_time timestamp(0),
    primary key (profile_id)
);
comment on table  action_guest_profile is '官网-访客档案';
comment on column action_guest_profile.profile_id is '档案id';
comment on column action_guest_profile.user_id is '关联的用户id（sys_user.user_id，user_type=01）';
comment on column action_guest_profile.institution is '所属机构（注册时用户自由填写）';
comment on column action_guest_profile.position is '职位（注册时用户自由填写）';
comment on column action_guest_profile.del_flag is '删除标志（0存在 2删除）';
comment on column action_guest_profile.create_time is '创建时间';
comment on column action_guest_profile.update_time is '更新时间';
create unique index uk_agp_user_id on action_guest_profile (user_id);

-- ----------------------------
-- 9、序列水位
--
-- 上方种子数据显式写入主键，不推进序列的话，后台第一次新增就会主键冲突。
-- 有数据的表取 max(pk) 且 is_called=true；action_collab_request 与
-- action_guest_profile 无种子，用 is_called=false 使首次 nextval 返回 1。
-- ----------------------------
select setval('action_news_news_id_seq', 11, true);
select setval('action_guideline_guideline_id_seq', 6, true);
select setval('action_study_type_type_id_seq', 5, true);
select setval('action_study_type_guideline_id_seq', 10, true);
select setval('action_study_type_stat_id_seq', 14, true);
select setval('action_cfir_domain_domain_id_seq', 5, true);
select setval('action_cfir_construct_construct_id_seq', 21, true);
select setval('action_cfir_strategy_strategy_id_seq', 21, true);
select setval('action_eric_strategy_eric_id_seq', 15, true);
select setval('action_eric_category_id_seq', 9, true);
select setval('action_reaim_dimension_dim_id_seq', 5, true);
select setval('action_srd_assessment_assessment_id_seq', 1, true);
select setval('action_srd_domain_domain_id_seq', 4, true);
select setval('action_srd_group_group_id_seq', 12, true);
select setval('action_srd_item_item_id_seq', 34, true);
select setval('action_collab_request_request_id_seq', 1, false);
select setval('action_guest_profile_profile_id_seq', 1, false);
