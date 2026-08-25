-- ----------------------------
-- SRD 系统综述重复性评估：从「一份写死的示例」升级为「可真跑、可留档、可回看」
--
-- 增量脚本，跑在 action-website-pg.sql 之后（那四张表在那里建的）。
--
-- 改了三件事：
--   1. action_srd_assessment 从纯展示表变成**任务记录表**：多出 session_id / user_id /
--      run_status 这一组运行态字段，以及引擎给出的评分与版本三件套。
--      示例行（is_sample='1'）不属于任何用户，run_status 直接置 completed。
--   2. 三层都补上评分口径（0–3 分，**分越高越重复**）。这是新版 Excel 表 1 的列，
--      引擎 0.7.0 起按它算领域与整体百分比，见 tools/srd-engine/README.md。
--   3. action_srd_item 的 level / pct **删掉**：条目层只有评分，没有「重复程度」与百分比。
--      原示例那两列是迁移期手写的，留着就是个只有示例行才有值的半死字段。
--      示例的条目评分由原 pct 折算（rating = round(3 × pct/100)），
--      领域与整体的分数、百分比、档位随之按 aggregate.py 的同一套公式重算，
--      所以示例现在与方法说明面板里的算法是自洽的（改数据时请一并重算，别手填）。
--
-- 本文件的示例数据已是**引擎 0.8.0 的方向**（3 分完全相同 … 0 分完全不同）。
-- 甲方 Excel 表 1 的表头写的是相反的「完全相同 0 分」，拿那张表来核会读反 ——
-- 口径的唯一真源是 tools/srd-engine/srd_engine/schemas.py 的 RATING_LABEL_*。
-- 已经执行过本文件旧版的库，用 sql/013-action-srd-score-flip-pg.sql 翻转存量数据。
-- ----------------------------

-- ---------------------------------------------------------------- 1. 评估（任务记录）

alter table action_srd_assessment add column if not exists session_id  varchar(64);
alter table action_srd_assessment add column if not exists user_id     bigint;
alter table action_srd_assessment add column if not exists run_status  varchar(16) default 'completed';
alter table action_srd_assessment add column if not exists progress    int4        default 0;
alter table action_srd_assessment add column if not exists error_msg   varchar(500) default '';
alter table action_srd_assessment add column if not exists file_a_name varchar(255) default '';
alter table action_srd_assessment add column if not exists file_b_name varchar(255) default '';
alter table action_srd_assessment add column if not exists overall_score_sum      int4 default 0;
alter table action_srd_assessment add column if not exists overall_score_max      int4 default 0;
alter table action_srd_assessment add column if not exists overall_score_max_full int4 default 0;
alter table action_srd_assessment add column if not exists provisional   char(1)     default '0';
alter table action_srd_assessment add column if not exists unclear_count int4        default 0;
alter table action_srd_assessment add column if not exists review_count  int4        default 0;
alter table action_srd_assessment add column if not exists model_name    varchar(200) default '';
alter table action_srd_assessment add column if not exists engine_version  varchar(64) default '';
alter table action_srd_assessment add column if not exists prompt_version  varchar(64) default '';
alter table action_srd_assessment add column if not exists criteria_version varchar(64) default '';
alter table action_srd_assessment add column if not exists llm_calls   int4 default 0;
alter table action_srd_assessment add column if not exists token_in    int4 default 0;
alter table action_srd_assessment add column if not exists token_out   int4 default 0;
alter table action_srd_assessment add column if not exists seconds     numeric(10,1) default 0;
alter table action_srd_assessment add column if not exists finish_time timestamp(0);

comment on column action_srd_assessment.session_id is 'worker 任务id（srd_worker_tool 的 session_id），示例行为空';
comment on column action_srd_assessment.user_id is '发起评估的访客 user_id，示例行为空';
comment on column action_srd_assessment.run_status is '任务状态（pending/running/completed/failed/stopped）';
comment on column action_srd_assessment.progress is '进度百分比 0-100';
comment on column action_srd_assessment.overall_score_sum is '整体得分（0–3 分/条，分越高越重复）';
comment on column action_srd_assessment.overall_score_max is '可评分条目的满分 = 3 × 可评分条目数';
comment on column action_srd_assessment.overall_score_max_full is '名义满分 = 3 × 34 = 102';
comment on column action_srd_assessment.provisional is '关键领域证据不足，结论仅供参考（0否 1是）';
comment on column action_srd_assessment.seconds is '本次评估耗时（秒）';

-- session_id 唯一：轮询接口靠它做落库幂等，重复行会让「同一次评估」出现两条历史
create unique index if not exists idx_asa_session on action_srd_assessment (session_id)
    where session_id is not null;
-- 「我的评估历史」的取数路径
create index if not exists idx_asa_user on action_srd_assessment (user_id, assessment_id desc);

-- 判定列不要默认值。原 DDL 给 level / overall_level 写了 default 'mod'，
-- 而 SQLAlchemy 对「有默认值的列」会把显式传入的 None 当成「没给值」直接从 INSERT 里省掉 ——
-- 于是一条刚排队的任务、和一个全领域证据不足（level 真的是 null）的结果，
-- 都会被静默写成「中度重复」。「没得判」和「中度重复」是两件事，必须能区分。
alter table action_srd_assessment alter column overall_level drop default;

-- ---------------------------------------------------------------- 2. 领域

alter table action_srd_domain alter column level drop default;   -- 理由同上
alter table action_srd_domain add column if not exists score_sum      int4 default 0;
alter table action_srd_domain add column if not exists score_max      int4 default 0;
alter table action_srd_domain add column if not exists score_max_full int4 default 0;
alter table action_srd_domain add column if not exists dup_count      int4 default 0;
alter table action_srd_domain add column if not exists diff_count     int4 default 0;
alter table action_srd_domain add column if not exists unclear_count  int4 default 0;
alter table action_srd_domain add column if not exists evidence_sufficient char(1) default '1';
alter table action_srd_domain add column if not exists near_boundary       char(1) default '0';

comment on column action_srd_domain.score_max is '可评分条目满分 = 3 × 可评分条目数（证据不足的条目剔出分母）';
comment on column action_srd_domain.score_max_full is '名义满分 = 3 × 条目数（领域1 /24、2 /18、3 /42、4 /18）';
comment on column action_srd_domain.evidence_sufficient is '证据是否充分（0否 1是），关键领域为否时整体结论标 provisional';
comment on column action_srd_domain.near_boundary is '百分比落在分箱边界 ±5 内，提示人工复核（0否 1是）';

-- ---------------------------------------------------------------- 3. 条目

alter table action_srd_item add column if not exists rating       varchar(8) default 'unclear';
alter table action_srd_item add column if not exists score        int4;
alter table action_srd_item add column if not exists confidence   varchar(16) default 'medium';
alter table action_srd_item add column if not exists needs_review char(1)     default '0';
alter table action_srd_item add column if not exists review_note  varchar(500) default '';
alter table action_srd_item add column if not exists evidence_card text;

comment on column action_srd_item.rating is '条目评分（3完全相同 2部分相同 1部分不同 0完全不同 unclear证据不足）';
comment on column action_srd_item.score is '评分对应的分数 0–3；证据不足为 null，不进分子也不进分母';
comment on column action_srd_item.needs_review is '是否需人工复核（0否 1是）';
comment on column action_srd_item.evidence_card is '代码算出的客观事实（3a/6a/8b 三条有）';

-- ---------------------------------------------------------------- 4. 示例数据回填
--
-- 条目评分由原 pct 折算，领域/整体按 aggregate.py 的公式重算：
--   重复百分比 = 得分 ÷ 满分 × 100（0.8.0 起同向），之后走表 2 分箱、表 3 查表。
-- 结果：领域 1 mod 67%、领域 2 low 39%、领域 3 low 43%、领域 4 low 33%，
--       表 3 行「其中一个为中度重复」× 列「均为低重复及以下」→ 整体仍是**中度重复**，
--       所以示例原有的中英文判定理由不用改。
--
-- 分数是 0.8.0 方向的：3 = 完全相同（最重复）… 0 = 完全不同。
-- dup_count / diff_count 在翻转下**不变** —— 3/2 归 dup、1/0 归 diff，
-- 翻转把 0↔3、1↔2 对调，恰好还落在原来那一侧。

update action_srd_item set rating = '3', score = 3 where item_id in (3);
update action_srd_item set rating = '2', score = 2 where item_id in (1, 2, 4, 5, 6, 7, 11, 15, 19, 25, 26);
update action_srd_item set rating = '1', score = 1 where item_id in (
    8, 9, 10, 12, 13, 14, 16, 17, 18, 20, 21, 22, 23, 24, 27, 28, 29, 30, 31, 32, 33, 34
);
update action_srd_item set confidence = 'high', needs_review = '0', review_note = '', evidence_card = ''
    where item_id between 1 and 34;
-- 新版 Excel 把条目 9 改成 9a（见 srd-engine/checklist.py 的注释），示例跟着改
update action_srd_item set code = '9a' where item_id = 29 and code = '9';

alter table action_srd_item drop column if exists level;
alter table action_srd_item drop column if exists pct;

update action_srd_domain set score_sum = 16, score_max = 24, score_max_full = 24,
    pct = 67, level = 'mod', dup_count = 7,  diff_count = 1,  unclear_count = 0 where domain_id = 1;
update action_srd_domain set score_sum =  7, score_max = 18, score_max_full = 18,
    pct = 39, level = 'low', dup_count = 1,  diff_count = 5,  unclear_count = 0 where domain_id = 2;
update action_srd_domain set score_sum = 18, score_max = 42, score_max_full = 42,
    pct = 43, level = 'low', dup_count = 4,  diff_count = 10, unclear_count = 0 where domain_id = 3;
update action_srd_domain set score_sum =  6, score_max = 18, score_max_full = 18,
    pct = 33, level = 'low', dup_count = 0,  diff_count = 6,  unclear_count = 0 where domain_id = 4;
update action_srd_domain set evidence_sufficient = '1', near_boundary = '0' where assessment_id = 1;

update action_srd_assessment set
    overall_pct = 46, overall_level = 'mod',
    overall_score_sum = 47, overall_score_max = 102, overall_score_max_full = 102,
    provisional = '0', unclear_count = 0, review_count = 0,
    run_status = 'completed', progress = 100,
    model_name = '', engine_version = 'srd-engine/0.8.0', prompt_version = '', criteria_version = ''
where assessment_id = 1;

-- 存量行（只有示例那一条）没有 session_id / user_id，保持 null 即可：
-- 示例是所有人可见的公共数据，不属于任何访客。
