-- ----------------------------
-- 007 · checklist 条目增加「填写要求」维度：必填 / 条件填写（PostgreSQL）
--
-- 【为什么要这份文件】《智能报告辅助工具.docx》第 2 节要求第二步是「含**强制填写项（必填）**
-- 和**条件填写项（选填）**的编辑页」，但 `action_guideline_item` 现有 282 条条目没有这个维度
-- ——`extract_checklists.py` 抽的是各规范 docx 的清单表，那些表本身也不带这一列。
-- 没有它，第二步的编辑页就没法告诉研究者「哪几条是必须应答的、哪几条是看情况」，
-- 完成度也算不出分母。
--
-- 【判定口径】报告规范的通例是**条目默认都要应答**，只有明确带「如适用 / if applicable」
-- 这类限定语的才是条件填写项。所以：默认全部 '0'（必填），再按关键词把命中的置 '1'（选填）。
--
-- 【关键词启发式必然有错判】这是刻意接受的：282 条逐条人工标注的成本远高于收益，
-- 而后台「规范条目管理」页面已经加了「填写要求」列，错判的当场可以改。
-- 为了不让重跑本文件把人工修正冲掉，**回填只动 `update_by` 仍是 migration/空的行**
-- ——后台改过的行 `update_by` 是管理员账号，重跑绕开它。这与站点文案同步 SQL 里
-- 那个「后台没改过的才跟着新默认值走」的 case 是同一个思路。
--
-- 【可反复执行】加列用 `if not exists`，回填是幂等的 update。
-- ----------------------------

begin;

-- ----------------------------
-- 1、加列
--
-- 用 char(1) 而不是 boolean：全库的枚举列（status / del_flag / is_sample …）都是 char(1)，
-- ORM 侧也统一按 CHAR(1) 映射，这里跟着走，别为一列引入第二种风格。
-- ----------------------------
alter table action_guideline_item add column if not exists require_level char(1) default '0';

comment on column action_guideline_item.require_level is '填写要求（0必填 1条件填写/选填）';

-- 历史行（加列前就存在的）拿到的是 default，但显式兜一次 null，防止有人手工插过 null
update action_guideline_item set require_level = '0' where require_level is null;

-- ----------------------------
-- 2、按关键词回填条件填写项
--
-- 中英两版条目内容与扩展内容拼在一起判：同一条的中文写「如适用」而英文写
-- 「if applicable」是常态，只判一边会漏掉另一边先入库的那些。
-- `~*` 是大小写不敏感匹配（英文条目里 If applicable / IF APPLICABLE 都出现过）。
-- ----------------------------
update action_guideline_item
   set require_level = '1',
       update_by = 'migration',
       update_time = now()
 where del_flag = '0'
   and require_level = '0'
   and coalesce(update_by, '') in ('', 'migration')
   and (
        coalesce(content_zh, '') || coalesce(extension_zh, '')
            ~ '如适用|若适用|如有|若有|如相关|如涉及|如存在|适用时|如果适用|酌情'
     or coalesce(content_en, '') || coalesce(extension_en, '')
            ~* 'if applicable|where applicable|if relevant|where relevant|if any|if appropriate|as applicable'
   );

commit;

-- 核对回填结果（按规范看看必填/选填的分布，明显不合理就去后台改）：
-- select g.code, i.require_level, count(*)
--   from action_guideline_item i join action_guideline g on g.guideline_id = i.guideline_id
--  where i.del_flag = '0' group by 1, 2 order by 1, 2;
