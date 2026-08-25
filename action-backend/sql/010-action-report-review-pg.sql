-- ----------------------------
-- 010 · 第三步判定结果落库（PostgreSQL）
--
-- 【为什么要这两张表】第四步「AI 辅助撰写」原先是一屏静态演示，对前三步状态的引用次数是 0
-- ——既没有输入也没有输出。照《智能报告辅助工具.docx》第 4 节的字面写法实现出来（一个关键词框
-- → AI 续写一段），它**依然**是独立的：不知道你在写哪份稿、依据哪份规范、哪几条没写好。
-- 文档自己那句「遵循 STRICTA 条目规范」就露了馅——遵循哪一条？这句话只有在「你正站在某一条上」
-- 时才有意义。
--
-- 所以第四步改成一张**工作清单**：从第三步的判定拉进来「这几条描述模糊 / 这几条未报告」，
-- 逐条给续写与润色，确认后写回 `action_report_draft_item`。链路由此闭合成
-- 2（填）→ 3（判）→ 4（改）→ 2（回写），而不是一条断掉的直线。
-- 这两张表就是 3 与 4 之间那段缺失的管道。
--
-- 【隐私：只有来自第二步的稿件才落库】第三步对用户的承诺写在 `assistant.rvHint` 里
-- ——「稿件只在校验期间流转，不会入库」。所以落库有一道硬闸：**仅当被校验的稿件就是第二步
-- 合成的那份初稿时才写**（前端 `reviewFromDraft`、后端再校验一次 draft_id 归属）。
-- 用户从外部粘贴/上传的稿件，判定结果一律不落库——那会把承诺变成谎话。
-- 这道闸同时也是业务上的必然：写回的目标是草稿条目，没有草稿就无处可写。
--
-- 因此本表里不存稿件正文，也不存 `evidence`（判定引用的原文片段）：
-- 落库场景下那些内容本来就在 `action_report_draft_item` 里躺着，存第二份只是徒增泄漏面。
-- `reason` 存的是模型对该条目的判断说明，不是稿件摘抄。
--
-- 跑在 `008-action-report-draft-pg.sql` 之后（依赖 action_report_draft）。
--
-- 【为什么没有 drop】同 008：编号增量是运维会反复重跑的东西，而这两张表挂着用户的
-- 校验历史，drop 一次就没了。一律 if not exists。
-- ----------------------------

begin;

-- ----------------------------
-- 1、一次校验
-- ----------------------------
create table if not exists action_report_review (
    review_id    serial      primary key,
    draft_id     int         not null,
    user_id      bigint      not null,
    guideline_id int,
    session_id   varchar(64) default '',
    reported     int         default 0,
    vague        int         default 0,
    missing      int         default 0,
    line_count   int         default 0,
    del_flag     char(1)     default '0',
    create_time  timestamp
);

comment on table  action_report_review is '官网-报告助手第三步校验记录';
comment on column action_report_review.review_id is '校验记录id';
comment on column action_report_review.draft_id is '被校验的草稿id（action_report_draft.draft_id）';
comment on column action_report_review.user_id is '归属访客用户id（sys_user.user_id）';
comment on column action_report_review.guideline_id is '所依据的报告规范id';
comment on column action_report_review.session_id is 'worker 会话id，仅供排障对账';
comment on column action_report_review.reported is '已报告条目数';
comment on column action_report_review.vague is '描述模糊条目数';
comment on column action_report_review.missing is '未报告条目数';
comment on column action_report_review.line_count is '稿件行数';
comment on column action_report_review.del_flag is '删除标志（0存在 2删除）';

-- 工作清单永远取「这份草稿最近一次校验」，这个索引就是那条查询的形状
create index if not exists idx_action_report_review_draft on action_report_review (draft_id, review_id desc);

-- ----------------------------
-- 2、逐条判定
--
-- 一条 checklist 条目一行。**只存判定，不存稿件原文**，理由见文件头。
-- ----------------------------
create table if not exists action_report_review_item (
    id        serial      primary key,
    review_id int         not null,
    item_id   int         not null,
    status    varchar(16) not null,
    reason    text,
    lines     varchar(200) default ''
);

comment on table  action_report_review_item is '官网-报告助手第三步逐条判定';
comment on column action_report_review_item.review_id is '所属校验记录id';
comment on column action_report_review_item.item_id is 'checklist条目id（action_guideline_item.item_id）';
comment on column action_report_review_item.status is '判定（reported已报告 vague描述模糊 missing未报告）';
comment on column action_report_review_item.reason is '判定说明（模型的判断，不是稿件摘抄）';
comment on column action_report_review_item.lines is '报告于第几行，逗号分隔';

create index if not exists idx_action_report_review_item on action_report_review_item (review_id);

-- 同一次校验里一条目只该有一条判定；重复写入是 bug，让唯一索引当场拦住
create unique index if not exists uk_action_report_review_item on action_report_review_item (review_id, item_id);

commit;

-- 核对：
--   select r.review_id, r.draft_id, r.reported, r.vague, r.missing, count(i.id)
--     from action_report_review r left join action_report_review_item i on i.review_id = r.review_id
--    group by r.review_id order by r.review_id desc limit 10;
