-- ----------------------------
-- 资源中心链接（PostgreSQL）
--
-- 首页第④段「资源中心 · 国际报告规范组织与循证枢纽」此前是 action-frontend/pages/index.vue
-- 里写死的 6 个 <a>：域名、logo 路径写在模板中，一句话说明取 i18n 的 index.s055/s057/s059/
-- s061/s063/s065。后果是甲方想增删一个循证枢纽、或某个组织换了域名，都要改前端源码重新
-- 构建（官网是 nitro.preset:'static' 的预渲染站，改文案 = 重新 generate 一次）。
--
-- 本表把这 6 条搬进数据库，中英双语成对存放，前台按 sort_num 顺序渲染，
-- 后台「资源中心管理」页维护。栏目标题（资源中心 / 国际报告规范组织与循证枢纽 / 导语）
-- 仍在 i18n，它不是列表数据。
--
-- 可重复执行。
-- ----------------------------

begin;

drop table if exists action_resource_link;
create table action_resource_link (
    link_id     bigserial,
    name_zh     varchar(200)  not null,
    name_en     varchar(300)  default '',
    summary_zh  varchar(500)  default '',
    summary_en  varchar(800)  default '',
    url         varchar(500)  not null,
    logo_url    varchar(300)  default '',
    sort_num    int4          default 0,
    status      char(1)       default '0',
    del_flag    char(1)       default '0',
    create_by   varchar(64)   default '',
    create_time timestamp(0),
    update_by   varchar(64)   default '',
    update_time timestamp(0),
    remark      varchar(500)  default null,
    primary key (link_id)
);
comment on table  action_resource_link is '官网-资源中心链接';
comment on column action_resource_link.name_zh is '组织/资源名称（中文）；EQUATOR、Cochrane 这类专名两栏填同一串即可';
comment on column action_resource_link.summary_zh is '一句话说明（中文），显示在名称下方';
comment on column action_resource_link.url is '外部地址，前台一律新标签页打开（rel=noopener noreferrer）';
comment on column action_resource_link.logo_url is '标识图地址（阿里云 OSS 公网直链），留空则不画图';
comment on column action_resource_link.sort_num is '卡片显示顺序，越小越靠前';

-- ----------------------------
-- 种子数据（6 行）
--
-- 名称 / 链接 / logo 与迁移前 index.vue 的 6 个 .res-row 逐一对应，
-- 中英说明取自迁移前的 index.s055–s065（zh.json / en.json）。
--
-- logo_url 是 OSS 公网直链，由 `python -m tools.upload_resource_logos` 从
-- action-frontend/public/assets/logo-*.png 传上去后回写到这里（对象键用文件名而非随机串，
-- 所以本文件可重复执行、URL 也可读）。**不要改回 /assets/ 相对路径**：后台「资源中心管理」
-- 页是另一个域，相对路径在那边会 404，列表里一片裂图。
-- 原图仍留在 action-frontend/public/assets/ 下不要删 —— action_news 有 4 条新闻的
-- thumb_url 还指向同一批文件（见 action-website-pg.sql）。
-- ----------------------------
insert into action_resource_link (link_id, name_zh, name_en, summary_zh, summary_en, url, logo_url, sort_num, status, del_flag, create_by, create_time, update_by, update_time, remark) values
(1, 'EQUATOR Network', 'EQUATOR Network', '报告规范国际总枢纽', 'Reporting-guideline hub',
 'https://www.equator-network.org', 'https://action-gmu.oss-cn-guangzhou.aliyuncs.com/site/resource/logo-equator.png', 0, '0', '0', 'migration', current_timestamp, '', null, null),
(2, 'Cochrane', 'Cochrane', '系统综述与循证权威', 'Systematic reviews & evidence',
 'https://www.cochrane.org', 'https://action-gmu.oss-cn-guangzhou.aliyuncs.com/site/resource/logo-cochrane.png', 1, '0', '0', 'migration', current_timestamp, '', null, null),
(3, 'CONSORT & SPIRIT', 'CONSORT & SPIRIT', '试验与方案报告规范', 'Trials & protocols',
 'https://www.consort-spirit.org', 'https://action-gmu.oss-cn-guangzhou.aliyuncs.com/site/resource/logo-consort.png', 2, '0', '0', 'migration', current_timestamp, '', null, null),
(4, 'PRISMA', 'PRISMA', '系统综述与 Meta 分析', 'Systematic reviews & meta-analyses',
 'https://www.prisma-statement.org', 'https://action-gmu.oss-cn-guangzhou.aliyuncs.com/site/resource/logo-prisma.png', 3, '0', '0', 'migration', current_timestamp, '', null, null),
(5, 'ARRIVE', 'ARRIVE', '动物实验报告规范', 'Animal research reporting',
 'https://arriveguidelines.org', 'https://action-gmu.oss-cn-guangzhou.aliyuncs.com/site/resource/logo-arrive.png', 4, '0', '0', 'migration', current_timestamp, '', null, null),
(6, 'CARE', 'CARE', '病例报告规范', 'Case reports',
 'https://www.care-statement.org', 'https://action-gmu.oss-cn-guangzhou.aliyuncs.com/site/resource/logo-care.png', 5, '0', '0', 'migration', current_timestamp, '', null, null),
-- 第 7 条是迁移之后按甲方要求加的，不属于原页面那 6 张卡片。
-- 中英说明留空、无标识图：站点是 SPA，抓不到任何可引用的介绍文字，宁可空着也不替第三方项目编简介。
(7, 'REFORM', 'REFORM', '', '',
 'https://reform-organoid.cn', '', 6, '0', '0', 'migration', current_timestamp, '', null, '中英一句话说明与标识图待补');

select setval('action_resource_link_link_id_seq', 7, true);

commit;
