-- ----------------------------
-- 001 · 站点文案增量：SRD 结果页的「导出 Excel / 显示中文译文」一批（PostgreSQL）
--
-- 【文件名的序号】本目录此前按功能命名，看不出先后。从这份起，**增量 SQL 一律
-- `NNN-` 前缀**，编号只增不减，序号最大的就是最新的一份。全量文件（如
-- `action-site-text-pg.sql`、`action-website-pg.sql`）不编号 —— 它们是可反复执行的
-- 快照，没有先后可言。
--
-- 【什么时候需要这份文件】`action_site_text` 是 i18n 词条的**可编辑副本**：
-- 前端加了新的 `$t()` 键，键不进这张表，官网照样显示（会回落到 i18n JSON 的默认值），
-- 但后台「站点文案管理」页里看不见、也就改不了。所以前端每加一批词条，都要同步进来。
--
-- 【与 `action-site-text-pg.sql` 的关系】那份是 `python -m tools.extract_site_texts`
-- 生成的**全量同步**（938 条，可反复执行，已含本文件的内容）。两条路择一即可：
--   · 全量：直接跑 `action-site-text-pg.sql`，顺带把所有词条的 sort_num 校准一遍；
--   · 增量：跑本文件，只动下面这 12 行，不扫全表。
-- 两者对「后台已改过的文案」的处理一致 —— 见下面 on conflict 里的 case，
-- 人工覆盖过的 text_* 原样保留，只刷新 default_*。
--
-- 【本次变更】
--   新增 5 条：srd.citeEmpty / showTrans / exportXlsx / exporting / exportFilename
--   删除 1 条：srd.metaLine（结果卡片上「模型 · 调用次数 · 用时 · 引擎版本」那行已撤，
--              键在前端删掉了，库里这行成了孤儿）
--   校准 6 条：新键插在 srd 组中间，其后 6 条词条的 sort_num 顺移（只影响后台列表排序）
-- ----------------------------

begin;

-- ----------------------------
-- 1、下线已删除的词条
--
-- 走软删除而不是 delete：唯一索引是 `where del_flag = '0'` 的部分索引，软删后同名键
-- 仍可重新插入；DAO 的每一处查询（含官网公开接口 `/action/site/texts`）都带
-- `del_flag = '0'`，所以软删即刻生效。哪天这行文案要回来，改回 '0' 就是。
-- ----------------------------
update action_site_text
   set del_flag = '1',
       update_by = 'migration',
       update_time = now()
 where text_key = 'srd.metaLine'
   and del_flag = '0';

-- ----------------------------
-- 2、新增词条
--
-- 列与 on conflict 子句照抄 `tools/extract_site_texts.py` 的生成结果，逐字一致 ——
-- 两条路径对同一批键的写入语义必须完全相同，否则「先跑增量再跑全量」和反过来跑
-- 会得到不同的结果。
--
-- text_* 与 default_* 插入时同值 = 「未改动」。公开接口只下发
-- `text_* <> default_*` 的行，所以这 5 条插进来之后官网的覆盖包一个字节都不会变大。
-- ----------------------------
insert into action_site_text
    (text_key, page_key, page_label, text_zh, text_en, default_zh, default_en, has_markup, sort_num)
values
('srd.citeEmpty', 'srd', 'SRD 重复性评估', '未找到可引用的原文', 'No quotable passage found', '未找到可引用的原文', 'No quotable passage found', '0', 927),
('srd.showTrans', 'srd', 'SRD 重复性评估', '显示中文译文', 'Show Chinese translation', '显示中文译文', 'Show Chinese translation', '0', 928),
('srd.exportXlsx', 'srd', 'SRD 重复性评估', '导出 Excel', 'Export to Excel', '导出 Excel', 'Export to Excel', '0', 929),
('srd.exporting', 'srd', 'SRD 重复性评估', '正在生成…', 'Preparing…', '正在生成…', 'Preparing…', '0', 930),
('srd.exportFilename', 'srd', 'SRD 重复性评估', 'SRD重复性评估', 'SRD-duplication-assessment', 'SRD重复性评估', 'SRD-duplication-assessment', '0', 931)
on conflict (text_key) where del_flag = '0' do update set
    page_key   = excluded.page_key,
    page_label = excluded.page_label,
    has_markup = excluded.has_markup,
    sort_num   = excluded.sort_num,
    -- 后台没改过（当前值 = 旧默认值）的行，跟着新默认值走；改过的原样保留。
    -- 少了这个 case，前端改一句默认文案后，所有未被人工覆盖的行都会突然「变成已改动」，
    -- 并把旧文案当作覆盖项吐给前台 —— 等于代码里的修改永远上不了线。
    text_zh = case when action_site_text.text_zh is not distinct from action_site_text.default_zh
                   then excluded.default_zh else action_site_text.text_zh end,
    text_en = case when action_site_text.text_en is not distinct from action_site_text.default_en
                   then excluded.default_en else action_site_text.text_en end,
    default_zh = excluded.default_zh,
    default_en = excluded.default_en;

-- ----------------------------
-- 3、校准顺移的 sort_num
--
-- sort_num 是按 zh.json 的书写顺序生成的全局序号（后台列表按它排，大体等同页面从上
-- 到下）。新键插在 srd 组中间，其后这 6 条各自后移。**只影响后台列表的排序**，
-- 不改则这 6 条会和新键挤在相邻的号段里，找起来别扭而已，不会影响官网。
-- ----------------------------
update action_site_text set sort_num = 932 where text_key = 'srd.histRefresh'       and del_flag = '0';
update action_site_text set sort_num = 933 where text_key = 'srd.histView'          and del_flag = '0';
update action_site_text set sort_num = 934 where text_key = 'srd.histDelete'        and del_flag = '0';
update action_site_text set sort_num = 935 where text_key = 'srd.histNeedLogin'     and del_flag = '0';
update action_site_text set sort_num = 936 where text_key = 'srd.histConfirmDelete' and del_flag = '0';
update action_site_text set sort_num = 937 where text_key = 'srd.lvlUnknown'        and del_flag = '0';

commit;

-- 共 5 条新增、1 条下线、6 条排序校准
