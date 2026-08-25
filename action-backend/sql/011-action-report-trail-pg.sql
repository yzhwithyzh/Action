-- ----------------------------
-- 011 · 报告助手操作留痕（PostgreSQL）
--
-- 【为什么要这张表】《智能报告辅助工具.docx》3.4 要求「校验过程保留操作日志，确保关键数据
-- 修改有迹可循」。此前 `trail` 只是前端内存里的 8 条记录，刷新即失，实际不可追溯。
--
-- 【记什么：只记事件元数据，绝不记稿件内容】第三步对用户的承诺写在 `assistant.rvHint`
-- ——「稿件只在校验期间流转，不会入库」。留痕如果存渲染好的句子，那句子里迟早会混进正文片段
-- （「已提交稿件：本研究纳入 120 例……」），承诺就绕过去了。所以本表**只存结构化的数字与枚举**：
-- 事件类型、条目计数、字符数、规范代号。人读的那句话由前端按 i18n 渲染，库里没有它。
-- 唯一的自由文本是 `note`，**仅供系统诊断**（worker 的失败原因），接口层限长并且前端不许
-- 往里塞用户内容。
--
-- 【为什么第四步的写回也要留痕】「关键数据修改有迹可循」最字面的落点其实在这儿：
-- 第四步把模型生成的文字写回 `action_report_draft_item`，那是真正的数据修改。
-- 一篇稿子里哪几段来自模型、什么时候被采纳的，是这套工具最该说得清的一件事
-- —— 投稿时被问起「AI 参与了多少」，这张表就是答案。
--
-- 跑在 `008-action-report-draft-pg.sql` 之后。
--
-- 【为什么没有 drop】同 008/010：编号增量运维会反复重跑，而这张表是审计记录，
-- drop 一次就等于把「有迹可循」这件事本身抹掉。一律 if not exists。
-- ----------------------------

begin;

create table if not exists action_report_trail (
    trail_id       serial      primary key,
    user_id        bigint      not null,
    draft_id       int,
    guideline_code varchar(64) default '',
    event          varchar(32) not null,
    actor          varchar(200) default '',
    item_id        int,
    total          int,
    reported       int,
    vague          int,
    missing        int,
    completeness   int,
    char_count     int,
    note           varchar(300) default '',
    create_time    timestamp
);

comment on table  action_report_trail is '官网-报告助手操作留痕（只记事件元数据，不记稿件内容）';
comment on column action_report_trail.trail_id is '留痕id';
comment on column action_report_trail.user_id is '操作人（sys_user.user_id）';
comment on column action_report_trail.draft_id is '关联草稿id；外部粘贴的稿件没有草稿，此列为空';
comment on column action_report_trail.guideline_code is '所依据的报告规范代号';
comment on column action_report_trail.event is '事件（submitted提交校验 judged逐条判定 cross全稿一致性 failed失败 applied采纳改写）';
comment on column action_report_trail.actor is '执行者：用户名，或出结果的模型标识';
comment on column action_report_trail.item_id is 'event=applied 时，被写回的 checklist 条目id';
comment on column action_report_trail.total is '判定条目总数';
comment on column action_report_trail.reported is '已报告条目数';
comment on column action_report_trail.vague is '描述模糊条目数';
comment on column action_report_trail.missing is '未报告条目数';
comment on column action_report_trail.completeness is '完整性百分比';
comment on column action_report_trail.char_count is '稿件字符数（只记长度，不记内容）';
comment on column action_report_trail.note is '系统诊断信息（如 worker 失败原因）。**不得写入用户稿件内容**';

-- 列表按「我的 + 最近的在前」取，这个索引就是那条查询的形状
create index if not exists idx_action_report_trail_user on action_report_trail (user_id, trail_id desc);
create index if not exists idx_action_report_trail_draft on action_report_trail (draft_id, trail_id desc);

commit;

-- 核对：
--   select event, count(*) from action_report_trail group by event order by 2 desc;
--   -- 「哪几段来自模型」：
--   select create_time, item_id, actor from action_report_trail
--    where draft_id = ? and event = 'applied' order by trail_id desc;
