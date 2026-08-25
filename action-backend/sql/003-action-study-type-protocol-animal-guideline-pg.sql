-- ----------------------------
-- 003 · 报告助手第一步问卷补三种研究类型：试验方案 / 动物实验 / 临床实践指南（PostgreSQL）
--
-- 【为什么要这份文件】`action_guideline_item` 里已经有 282 条 checklist，但报告助手第一步
-- 的问卷只有 4 个选项（干预性试验 / 病例报告 / 系统评价 / 观察性研究），于是
--
--     SPIRIT   79 条（临床试验方案 Protocol）
--     RIGHT    42 条（临床实践指南）
--     ARRIVE   21 条（动物实验）
--
-- 共 142 条 —— 超过总量一半 —— 在报告助手里**没有任何路径能走到**，第二步展不开、
-- 第三步也就校验不了。这三类在 `ACTION网站及其材料/针刺报告规范/` 下各有独立素材目录，
-- 也各自在规范目录页里陈列着，唯独助手里到不了。本文件把它们补进问卷词表。
--
-- 【为什么不是改分类表】`action_study_type` 与 `action_guideline_category` 是两套词表，
-- 用途不同、刻意不合并（见 CLAUDE.md）：前者是**问卷词表**（研究者自认的类型 → 规范 +
-- 统计推荐），后者是**规范目录的陈列分类**。这次是给问卷词表加行，不是把两张表并到一起。
-- 三个新 type_key 与分类表的 cat_key 取同样的字面量（protocol / animal / guideline），
-- 只是为了让两边对同一类东西的叫法一致，不构成外键关系。
--
-- 【可反复执行】
--   · `action_study_type` 走 `on conflict (type_key)`，改了文案重跑即可；
--   · 关联表与统计表没有唯一索引，所以先按 type_key 删掉这三类的旧行再插，
--     不做 upsert —— 那两张表是「一类研究对应一组行」的整体，逐行 upsert 反而
--     会在减少行数时留下删不掉的残行。
--
-- 【serial 的坑】全量文件 `action-website-pg.sql` 里这三张表都是显式写 id 插入的，
-- 序列因此**从来没有前进过**（还停在 1）。所以这里先把三条序列 setval 到当前最大值，
-- 再用不带 id 的 insert —— 否则不论是本文件还是将来后台新增，第一条就撞主键。
-- ----------------------------

begin;

-- ----------------------------
-- 0、把 serial 序列校准到当前最大值（全量文件显式插 id，序列一直停在 1）
-- ----------------------------
select setval(pg_get_serial_sequence('action_study_type', 'type_id'),
              coalesce((select max(type_id) from action_study_type), 1));
select setval(pg_get_serial_sequence('action_study_type_guideline', 'id'),
              coalesce((select max(id) from action_study_type_guideline), 1));
select setval(pg_get_serial_sequence('action_study_type_stat', 'id'),
              coalesce((select max(id) from action_study_type_stat), 1));

-- ----------------------------
-- 1、问卷词表新增三类
--
-- hot_guideline 决定第二步展开哪份 checklist，**必须是 action_guideline.code 且该规范下
-- 真的有条目**，否则第二步只会显示「条目尚未录入」。这三份分别是 79 / 21 / 42 条。
-- ----------------------------
insert into action_study_type (type_key, name_zh, name_en, hot_guideline, sort_num, status, create_by, create_time)
values
('protocol', '临床试验方案 Protocol', 'Clinical trial protocol', 'SPIRIT', 5, '0', 'migration', now()),
('animal',   '动物实验',             'Animal experiment',       'ARRIVE', 6, '0', 'migration', now()),
('guideline','临床实践指南',         'Clinical practice guideline', 'RIGHT', 7, '0', 'migration', now())
on conflict (type_key) do update set
    name_zh       = excluded.name_zh,
    name_en       = excluded.name_en,
    hot_guideline = excluded.hot_guideline,
    sort_num      = excluded.sort_num,
    status        = excluded.status,
    update_by     = 'migration',
    update_time   = now();

-- ----------------------------
-- 2、挂载的报告规范（第一步右侧那排 chip；hot_guideline 那个会显示成朱砂色）
--
-- guideline_code 是自由文本、不是外键 —— 现有种子里就有「针刺专病条目」「针刺检索策略」
-- 这类不是规范代号的条目，它们只作为提示词出现在 chip 上。
-- ----------------------------
delete from action_study_type_guideline
 where type_id in (select type_id from action_study_type where type_key in ('protocol', 'animal', 'guideline'));

insert into action_study_type_guideline (type_id, guideline_code, sort_num)
select t.type_id, v.code, v.sort_num
  from (values
        ('protocol', 'SPIRIT', 0),
        -- 方案里的针刺干预细节仍要按 STRICTA 写，不因为是「方案」就免了
        ('protocol', 'STRICTA', 1),
        ('animal',   'ARRIVE', 0),
        ('guideline','RIGHT', 0),
        ('guideline','GRADE 证据分级', 1)
       ) as v(type_key, code, sort_num)
  join action_study_type t on t.type_key = v.type_key;

-- ----------------------------
-- 3、统计方法推荐（第一步右侧「推荐统计方法」那几行）
-- ----------------------------
delete from action_study_type_stat
 where type_id in (select type_id from action_study_type where type_key in ('protocol', 'animal', 'guideline'));

insert into action_study_type_stat (type_id, text_zh, text_en, sort_num)
select t.type_id, v.zh, v.en, v.sort_num
  from (values
        ('protocol', '预先设定主要结局的组间比较方法（t 检验 / 秩和检验）',
                     'Pre-specify the primary-outcome comparison (t-test / rank-sum)', 0),
        ('protocol', '预先给出样本量计算参数与把握度',
                     'Pre-specify sample-size parameters and power', 1),
        ('protocol', '预先规定缺失数据处理与 ITT / PP 分析集',
                     'Pre-specify missing-data handling and ITT / PP analysis sets', 2),
        ('animal',   '组间比较：单因素 / 双因素方差分析 + 事后多重比较',
                     'Between-group: one-/two-way ANOVA with post-hoc tests', 0),
        ('animal',   '小样本优先非参数检验（Kruskal–Wallis）',
                     'Small samples: prefer non-parametric tests (Kruskal–Wallis)', 1),
        ('animal',   '须报告随机分组、盲法与每组动物数（ARRIVE 核心 10 项）',
                     'Report randomisation, blinding and n per group (ARRIVE Essential 10)', 2),
        ('guideline','一般不做原始统计分析，重在证据质量分级（GRADE）',
                     'Usually no primary analysis; grade the certainty of evidence (GRADE)', 0),
        ('guideline','若含 Meta 分析，合并方法按 PRISMA 报告',
                     'If a meta-analysis is included, report pooling per PRISMA', 1),
        ('guideline','推荐强度与证据体的一致性须明确说明',
                     'State the link between recommendation strength and the evidence body', 2)
       ) as v(type_key, zh, en, sort_num)
  join action_study_type t on t.type_key = v.type_key;

commit;

-- 新增 3 类研究类型、5 条规范挂载、9 条统计推荐
-- 报告助手可达的 checklist 条目数：140 → 282（SPIRIT 79 + RIGHT 42 + ARRIVE 21 接通）
