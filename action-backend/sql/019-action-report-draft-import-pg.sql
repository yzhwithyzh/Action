-- ----------------------------
-- 019 · 第二步导入已有稿件（PostgreSQL）
--
-- 【补的是哪个洞】助手服务两类人，而**导入口一直只在第三步**：已经写好稿的人把稿子粘进
-- 第三步，拿回一份**只读**的判定，然后就没有然后了 ——
--   · 第四步没有草稿条目可写回；
--   · 第五步的数据源是草稿，于是整个导不出；
--   · 下次再来还得重新粘一遍。
-- 而「哪些条目没覆盖」这件事，第三步其实**已经算出来了**（逐条 reported/vague/missing
-- 加行号）。缺的只是把这份结果落成一份可继续加工的草稿。
--
-- 所以导入挪到第二步：上传稿件 → 建草稿 → 跑一次条目映射（复用第三步那套 worker 与引擎，
-- 不新造算法）→ 按行号从原稿还原段落回填条目框。**空框就是「没导入的条目」**。
--
-- 【为什么原稿要单独存一列，而不是拆碎了完事】拆解必然重组：一句话常同时答好几条
-- （「随机分为两组，每组 48 例」同时答随机化、样本量、分组），而讨论、致谢、参考文献
-- 不对应任何条目、落不进任何框。若草稿条目成了唯一真相，第五步导出拼回来的
-- **就不是用户写的那篇稿子了** —— 章节顺序被打散、没对应条目的段落凭空消失。
-- 对一份要投出去的论文，这是不能接受的。
--
-- 因此「两份并存」：`source_text` 是原稿（导出正文以它为准），条目框是**对照与改写的工作面**。
-- 两者服务不同用途，谁也不是谁的副本。
-- ----------------------------

begin;

-- ----------------------------
-- 1、草稿记下它是从哪篇稿子导入的
-- ----------------------------

-- 原稿全文。**导出正文以它为准**（见文件头）；逐条填出来的草稿这一列为空，
-- 那种情况下导出仍旧按条目合成，两条路各走各的
alter table action_report_draft add column if not exists source_text  text;
alter table action_report_draft add column if not exists source_name  varchar(255) default '';
-- 原稿有效行数（引擎口径：空行不占号）。存它是为了让前台在不拉原文的情况下
-- 也能显示「导入 N 行」，列表页用得上
alter table action_report_draft add column if not exists source_lines int          default 0;

comment on column action_report_draft.source_text is '导入的原稿全文；导出正文以它为准，逐条填的草稿为空';
comment on column action_report_draft.source_name is '导入时的原始文件名';
comment on column action_report_draft.source_lines is '原稿有效行数（引擎口径，空行不占号）';

-- ----------------------------
-- 2、校验记录分用途
--
-- 同一套 worker、同一个引擎、同一张结果表，但**只有导入那一次跑完才回填草稿条目**。
-- 不分用途的话，用户之后每复查一次，回填就把他在第二步的编辑整个盖掉一遍 ——
-- 那是没人要求过的数据丢失，而且发生得悄无声息（判定看起来一切正常）。
-- ----------------------------
alter table action_report_review add column if not exists purpose varchar(16) default 'check';

comment on column action_report_review.purpose is '用途（check 逐条校验 / import 导入并回填草稿）';

commit;

-- 核对：
--   select d.draft_id, d.title, d.source_name, d.source_lines,
--          length(coalesce(d.source_text,'')) src_len,
--          (select count(*) from action_report_draft_item i
--            where i.draft_id = d.draft_id and coalesce(i.content,'') <> '') filled
--     from action_report_draft d where d.del_flag = '0' order by d.draft_id desc limit 10;
--   select purpose, count(*) from action_report_review group by purpose;
