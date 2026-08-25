-- ----------------------------
-- 020 · 站点文案增量：第二步导入已有稿件（PostgreSQL）
--
-- 【什么时候需要这份文件】`action_site_text` 是 i18n 词条的**可编辑副本**：
-- 前端加了新的 `$t()` 键，键不进这张表，官网照样显示（回落到 i18n JSON 的默认值），
-- 但后台「站点文案管理」页里看不见、也就改不了。所以前端每加一批词条都要同步进来。
--
-- 【本次变更】新增 6 条 `assistant.dfImport*` —— 第二步的「导入已有稿件」那条路
-- （建表与接口见 `sql/019-action-report-draft-import-pg.sql`）。
--
-- 【dfImportDone 那句话不是随口写的】它同时交代三件用户必须知道的事：
--   ① 自动填了几条；② 还有几条空着，**空的就是稿件没覆盖到的条目**（这是导入的产出，
--   不是失败）；③ 导出时正文仍以原稿为准 —— 不说这句，用户会以为自己的论文被拆碎了。
-- 改这条文案时三件事一件都不能少。
--
-- 列与 on conflict 子句照抄 `tools/extract_site_texts.py` 的生成结果，逐字一致 ——
-- 两条路径对同一批键的写入语义必须完全相同，否则「先跑增量再跑全量」和反过来跑
-- 会得到不同的结果。
--
-- 【sort_num】取值与重跑生成器后的 `action-site-text-pg.sql` 逐条对齐（428–433）。
-- ----------------------------

begin;

insert into action_site_text
    (text_key, page_key, page_label, text_zh, text_en, default_zh, default_en, has_markup, sort_num)
values
('assistant.dfImport', 'assistant', '报告助手', '导入已有稿件', 'Import a manuscript', '导入已有稿件', 'Import a manuscript', '0', 428),
('assistant.dfImporting', 'assistant', '报告助手', '导入中…', 'Importing…', '导入中…', 'Importing…', '0', 429),
('assistant.dfImportParsing', 'assistant', '报告助手', '正在解析文件…', 'Reading the file…', '正在解析文件…', 'Reading the file…', '0', 430),
('assistant.dfImportMatching', 'assistant', '报告助手', '正在匹配 checklist 条目…', 'Matching checklist items…', '正在匹配 checklist 条目…', 'Matching checklist items…', '0', 431),
('assistant.dfImportFailed', 'assistant', '报告助手', '条目匹配失败。草稿与原稿已保存，你可以逐条填写，或到第三步重新校验。', 'Item matching failed. Your draft and the original manuscript are saved — fill items in yourself, or run the check again in step 3.', '条目匹配失败。草稿与原稿已保存，你可以逐条填写，或到第三步重新校验。', 'Item matching failed. Your draft and the original manuscript are saved — fill items in yourself, or run the check again in step 3.', '0', 432),
('assistant.dfImportDone', 'assistant', '报告助手', '已导入《{name}》：原稿 {lines} 行，自动填入 {filled} 条，{blank} 条还空着——空的就是稿件里没覆盖到的条目。导出时正文仍以你的原稿为准。', 'Imported “{name}”: {lines} lines, {filled} items filled in automatically, {blank} still empty — the empty ones are what the manuscript does not cover. Exports still use your original manuscript as the body text.', '已导入《{name}》：原稿 {lines} 行，自动填入 {filled} 条，{blank} 条还空着——空的就是稿件里没覆盖到的条目。导出时正文仍以你的原稿为准。', 'Imported “{name}”: {lines} lines, {filled} items filled in automatically, {blank} still empty — the empty ones are what the manuscript does not cover. Exports still use your original manuscript as the body text.', '0', 433)
on conflict (text_key) where del_flag = '0' do update set
    page_key   = excluded.page_key,
    page_label = excluded.page_label,
    has_markup = excluded.has_markup,
    sort_num   = excluded.sort_num,
    -- 后台没改过（当前值 = 旧默认值）的行，跟着新默认值走；改过的原样保留。
    text_zh = case when action_site_text.text_zh is not distinct from action_site_text.default_zh
                   then excluded.default_zh else action_site_text.text_zh end,
    text_en = case when action_site_text.text_en is not distinct from action_site_text.default_en
                   then excluded.default_en else action_site_text.text_en end,
    default_zh = excluded.default_zh,
    default_en = excluded.default_en;

commit;

-- 新增 6 条（assistant.dfImport*）
