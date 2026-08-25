-- ----------------------------
-- 报告规范分类（PostgreSQL）
--
-- 官网 /guidelines 页第①段「分类导航」的筛选条此前写死在 action-frontend/pages/guidelines.vue：
-- 一张 CAT_OF 硬映射表把 action_guideline.study_type 折算成 7 个 chip，标签另取 i18n 的
-- guidelines.s005–s010。后果是后台新增一份规范时，只要 study_type 不在那 6 个键里就会掉进
-- 'all' —— 任何 chip 都筛不出来，卡片上的「研究设计」标签还是空白。库里的 STROBE
-- （study_type = 'obs'，见 action-checklist-pg.sql）现在就是这个状态。
--
-- 本表把那套词表搬进数据库，**cat_key 直接复用 action_guideline.study_type 既有的取值**
-- （见 action-website-pg.sql 第 118 行的列注释），因此不需要给 action_guideline 加列、
-- 也不需要回填。前台 chip 与卡片标签都读本表，后台新增规范时从下拉里选，选不出表外的值。
--
-- 与 action_study_type 的分工：那张表是**报告助手第一步的问卷词表**（类型 → 规范 + 统计推荐），
-- 只该出现受访者会自认的 5 种研究类型；本表是**规范目录的陈列分类**，还要容纳 protocol /
-- guideline / animal 这些「不是研究类型、但确实是一类规范」的格子。两者用途不同，不合并。
--
-- 可重复执行。
-- ----------------------------

begin;

drop table if exists action_guideline_category;
create table action_guideline_category (
    cat_id      bigserial,
    cat_key     varchar(32)   not null,
    name_zh     varchar(200)  not null,
    name_en     varchar(300)  default '',
    icon_paths  text,
    sort_num    int4          default 0,
    status      char(1)       default '0',
    del_flag    char(1)       default '0',
    create_by   varchar(64)   default '',
    create_time timestamp(0),
    update_by   varchar(64)   default '',
    update_time timestamp(0),
    remark      varchar(500)  default null,
    primary key (cat_id)
);
comment on table  action_guideline_category is '官网-报告规范分类';
comment on column action_guideline_category.cat_key is '分类标识，取值即 action_guideline.study_type（rct/nrct/protocol/sr/case/obs/guideline/animal）';
comment on column action_guideline_category.name_zh is '名称（中文），前台 chip 与卡片「研究设计」标签共用';
comment on column action_guideline_category.icon_paths is '卡片图标的 SVG path d 属性，一行一条；留空则前台不画图标';
comment on column action_guideline_category.sort_num is '筛选条中的显示顺序（「全部」恒排第一，不入库）';

-- cat_key 是 action_guideline.study_type 的取值域，重复了前台就会出现两个同名 chip
create unique index uk_action_guideline_category_key on action_guideline_category (cat_key) where del_flag = '0';

-- ----------------------------
-- 种子数据（8 行）
--
-- 前 6 行的 cat_key / 顺序 / 中英名称与迁移前 guidelines.vue 的 CAT_OF + guidelines.s005–s010
-- 逐一对应（'review' → 'sr'、'cpg' → 'guideline' 是把 chip 键改回 study_type 既有取值，
-- 页面观感不变）；后 2 行 nrct / obs 是原先根本没有 chip、因而永远筛不出来的两类，补齐。
-- icon_paths 即迁移前 guidelines.vue 里 ICON 常量的那几条 path。
-- ----------------------------
insert into action_guideline_category (cat_id, cat_key, name_zh, name_en, icon_paths, sort_num, status, del_flag, create_by, create_time, update_by, update_time, remark) values
(1, 'rct', '随机对照试验', 'RCT',
 E'M4 5h16M4 5v14M4 19h16\nM8 15l3-4 2 2 3-5', 0, '0', '0', 'migration', current_timestamp, '', null, null),
(2, 'protocol', '试验方案', 'Protocol',
 E'M8 3h6l4 4v14H6V5\nM8 3v4H4\nM9 13h6M9 17h4', 1, '0', '0', 'migration', current_timestamp, '', null, null),
(3, 'sr', '系统综述', 'Reviews',
 E'M12 3v18\nM5 8l7-5 7 5\nM5 8v8l7 5 7-5V8', 2, '0', '0', 'migration', current_timestamp, '', null, null),
(4, 'case', '病例报告', 'Case report',
 E'M7 3h7l4 4v14H6V4\nM14 3v4h4\nM12 11v6M9 14h6', 3, '0', '0', 'migration', current_timestamp, '', null, null),
(5, 'guideline', '实践指南', 'Guideline',
 E'M12 3l8 4v6c0 4.5-3.2 7-8 8-4.8-1-8-3.5-8-8V7z\nM9 12l2 2 4-4', 4, '0', '0', 'migration', current_timestamp, '', null, null),
(6, 'animal', '动物实验', 'Animal',
 E'M4 20c0-3 2-5 4-5s4 2 4 5\nM15 8c2 0 4 1.5 4 4s-2 4-4 4\nM17 12h.01', 5, '0', '0', 'migration', current_timestamp, '', null, null),
(7, 'nrct', '非随机对照试验', 'Non-randomised trial',
 E'M4 5h16M4 5v14M4 19h16\nM8 16l3-3 2 2 3-4', 6, '0', '0', 'migration', current_timestamp, '', null, '原筛选条没有这一格，与 action_study_type 的 nrct 同义'),
(8, 'obs', '观察性研究', 'Observational study',
 E'M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6z\nM12 9.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z', 7, '0', '0', 'migration', current_timestamp, '', null, '库里的 STROBE 属这一类，原筛选条没有这一格所以一直筛不出来');

select setval('action_guideline_category_cat_id_seq', 8, true);

commit;

-- ----------------------------
-- 自检：下面这句应当返回 0 行。
-- 有行说明库里存在 study_type 落在分类表之外的规范 —— 那份规范在前台既筛不出来、
-- 也没有「研究设计」标签，需要去后台「规范目录管理」页把它的分类改成表内的值，
-- 或在「规范分类管理」页把缺的分类补上。
-- ----------------------------
-- select g.guideline_id, g.code, g.study_type
--   from action_guideline g
--   left join action_guideline_category c
--     on c.cat_key = g.study_type and c.del_flag = '0'
--  where g.del_flag = '0' and coalesce(g.study_type, '') <> '' and c.cat_id is null;
