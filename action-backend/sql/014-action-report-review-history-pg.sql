-- ----------------------------
-- 014 · 第三步校验历史（PostgreSQL）
--
-- 【为什么要这一份】010 建的那两张表只服务一件事：给第四步的工作清单当输入。于是它有两个
-- 洞，而这两个洞在「刷新一下页面，刚跑完的校验就没了」这件事上撞成了同一个：
--
--   ① **只有 draft 路线才有记录**。用户从外部粘贴稿件跑校验——那恰恰是第三步的主用户
--      （已经写好稿的人第 2 步整个用不上）——库里一个字都没有。
--   ② **落库发生在前端轮到 completed 的那一刻**（前端 POST /report-reviews）。所以最该
--      被记下来的那批任务永远记不到：跑失败的、被停掉的、用户中途关掉页面的。
--      要追「昨天那次校验为什么挂了」，除了翻 worker 日志按时间猜，没有别的入口。
--
-- 本份把这两张表从「第四步的输入管道」扩成「第三步的任务台账 + 结果快照」：
-- 提交那一刻就落一行 pending，轮询与历史列表负责对账到终态。draft 路线仍然照旧
-- 从这里取最近一次判定，只是它现在是这张表的一个子集（draft_id is not null）而已。
--
-- 【隐私口径变了，这是本份最该被读到的一段】010 的文件头写着「不存稿件正文，也不存
-- evidence」，依据是 `assistant.rvHint` 里那句对用户的承诺：「稿件只在校验期间流转，
-- 不会入库」。要做可回看的历史，这条守不住了——判定里的 `evidence` 就是稿件的逐字片段，
-- 而 evidence 脱离正文又是没用的孤立碎片（点不回原文那一行去核）。要么两个都不存、
-- 回看时只剩「第12条 描述模糊」没有原文定位，要么两个一起存。
--
-- 甲方选了后者。所以 `assistant.rvHint` 那句承诺**已同步改写**（见
-- sql/015-action-site-text-review-history-pg.sql）——先改代码后改文案就是把承诺变成谎话，
-- 这两份必须一起上。作为对价，删除做成了**真删正文**：
-- `del_flag='2'` 的同时把 manuscript 与 evidence 物理清空，只留台账那几列
-- （session_id / 状态 / 错误 / 计数 / 时间）。排障要的是后者，隐私风险在前者，
-- 一刀切在这里最省事——用户点了「删除」就是真的没了，不是列表里看不见了。
--
-- 跑在 `010-action-report-review-pg.sql` 之后。
--
-- 【为什么没有 drop】同 008/010：编号增量是运维会反复重跑的东西，而这两张表挂着用户的
-- 校验历史，drop 一次就没了。一律 if not exists / if exists。
-- ----------------------------

begin;

-- ----------------------------
-- 1、action_report_review：从「一次草稿校验」扩成「一次校验任务」
-- ----------------------------

-- 外部粘贴的稿件没有草稿可挂。**这一列改可空是整份的枢纽**：不改，第三步的主用户
-- （已写好稿、直接来校验的人）就永远进不了这张表，历史也就只对一半用户存在
alter table action_report_review alter column draft_id drop not null;

-- 规范代号冗余存一份：历史列表要显示「依据哪份规范」，而 guideline_id 指向的那行
-- 可能在后台被删（规范目录是可编辑的）。删了之后 join 不出名字，列表就成了一排无名记录
alter table action_report_review add column if not exists guideline_code varchar(64)  default '';

-- 任务台账。存量行一律按 completed 补——它们本来就是「跑完才落库」的产物
alter table action_report_review add column if not exists run_status     varchar(16)  default 'completed';
alter table action_report_review add column if not exists error_msg      varchar(500) default '';
alter table action_report_review add column if not exists progress       int          default 0;
-- 出结果的模型，排障第一现场：同一份稿件换个模型判出两样结果时，这一列是唯一的分辨依据
alter table action_report_review add column if not exists models         varchar(200) default '';
alter table action_report_review add column if not exists locale         varchar(2)   default 'zh';
alter table action_report_review add column if not exists char_count     int          default 0;
alter table action_report_review add column if not exists item_total     int          default 0;
alter table action_report_review add column if not exists completeness   int          default 0;
alter table action_report_review add column if not exists truncated      char(1)      default '0';
alter table action_report_review add column if not exists finish_time    timestamp;

-- 稿件正文。**新口径的核心，与 015 的文案改写绑定发布**（理由见文件头）
alter table action_report_review add column if not exists manuscript     text;

-- 全稿逻辑一致性与术语标准化的结果，整块存 JSON。
-- **刻意不规范化成第三张表**：它的读取模式只有「整份取回渲染」一种，从来不按字段查；
-- 而它的形状（checks[] → findings[]）跟着引擎 `engine/consistency.py` 的规则表走，
-- 引擎加一条规则就要改一次表结构的话，这层迟早会与引擎漂移。JSON 在这里是对的抽象。
alter table action_report_review add column if not exists consistency    text;

comment on column action_report_review.draft_id is '被校验的草稿id；外部粘贴的稿件为空';
comment on column action_report_review.guideline_code is '报告规范代号（冗余存，规范被删后列表仍可读）';
comment on column action_report_review.run_status is '任务状态（pending/running/completed/failed/stopped）';
comment on column action_report_review.error_msg is '失败原因';
comment on column action_report_review.progress is '进度百分比0-100';
comment on column action_report_review.models is '实际出结果的模型，排障用';
comment on column action_report_review.locale is '判定语言（zh/en）';
comment on column action_report_review.char_count is '稿件字符数';
comment on column action_report_review.item_total is '该规范的条目总数';
comment on column action_report_review.completeness is '完整度百分比0-100';
comment on column action_report_review.truncated is '稿件是否被截断（0否 1是）';
comment on column action_report_review.finish_time is '任务到终态的时间';
comment on column action_report_review.manuscript is '稿件正文；删除记录时物理清空';
comment on column action_report_review.consistency is '全稿一致性判定结果（JSON）';

-- 历史列表的查询形状：某个访客最近 N 条
create index if not exists idx_action_report_review_user on action_report_review (user_id, review_id desc);
-- 轮询与对账按 session_id 找记录
create index if not exists idx_action_report_review_session on action_report_review (session_id);

-- ----------------------------
-- 2、action_report_review_item：加原文引用
-- ----------------------------

-- 判定引用的稿件原文片段（引擎侧已截到 200 字符）。**单存它没有意义**——
-- 不存正文的话这就是一句无法回到上下文的孤立引文，所以它与 manuscript 是一对，
-- 要么都在，要么都清空
alter table action_report_review_item add column if not exists evidence text;

comment on column action_report_review_item.evidence is '判定引用的稿件原文片段；删除记录时物理清空';

commit;

-- 核对：
--   select run_status, count(*) from action_report_review group by run_status;
--   select r.review_id, r.run_status, r.guideline_code, r.draft_id, r.completeness,
--          length(coalesce(r.manuscript,'')) as ms_len, count(i.id) as verdicts
--     from action_report_review r left join action_report_review_item i on i.review_id = r.review_id
--    group by r.review_id order by r.review_id desc limit 10;
