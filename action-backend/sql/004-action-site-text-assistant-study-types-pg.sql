-- ----------------------------
-- 004 · 站点文案增量：报告助手第一步的研究类型选项，以及两处「别把演示当功能」的措辞（PostgreSQL）
--
-- 【什么时候需要这份文件】`action_site_text` 是 i18n 词条的**可编辑副本**：
-- 前端加了新的 `$t()` 键，键不进这张表，官网照样显示（会回落到 i18n JSON 的默认值），
-- 但后台「站点文案管理」页里看不见、也就改不了。所以前端每加一批词条，都要同步进来。
--
-- 【与 `action-site-text-pg.sql` 的关系】那份是 `python -m tools.extract_site_texts`
-- 生成的**全量同步**（967 条，可反复执行，已含本文件的内容）。两条路择一即可：
--   · 全量：直接跑 `action-site-text-pg.sql`，顺带把所有词条的 sort_num 校准一遍；
--   · 增量：跑本文件，只动下面这 11 行，不扫全表。
--
-- 【本次变更】
--
--   下线 4 条：assistant.s017 / s018 / s019 / s020
--     配合 `003-action-study-type-protocol-animal-guideline-pg.sql`：第一步的问卷从
--     4 个选项扩到 7 个（补上试验方案 / 动物实验 / 临床实践指南，接通 SPIRIT 79 +
--     RIGHT 42 + ARRIVE 21 共 142 条原先走不到的 checklist）。原来四个选项各占一个
--     sNNN 键，现在整组改成按 type_key 取文案。旧键在前端已无人引用，**必须下线**——
--     留着的话它们会继续出现在后台「站点文案管理」里，看上去还是那四个选项的文案，
--     改了却毫无反应，比看不见更难查。
--
--   新增 9 条：
--     assistant.typeOpt.{trial,case,sr,obs,protocol,animal,guideline}
--       七个选项的文案。**键的后缀 = `action_study_type.type_key`** —— 往那张表里加
--       研究类型时，这里要同步加一条，否则新选项在页面上会显示成键名本身。
--       前四条内容与被下线的 s017–s020 逐字相同，只是换了键。
--     assistant.rvNoItems
--       匹配到的规范一条 checklist 条目都没有时，第三步给出的说明。眼下只有 STROBE
--       会走到（仓库里没有它的中英素材）。原先这种情况按钮照样可点，要等提交到后端
--       才报错 —— 条目数是第二步就摆在眼前的，没理由让人写完整篇稿件再吃一个报错。
--     assistant.betaStep4
--       第四步的「界面演示」角标，与第五步的 s119 同一种。
--
--   改默认 2 条（后台若已人工改过，下面的 case 会保留人工版本，只刷新 default_*）：
--     assistant.s048  「数据联动」→「数据联动（规划中）」。第二步展示的是只读的
--                     checklist 条目清单，根本没有「自动填入结果部分」的承载体，
--                     原文案是在承诺一个不存在的功能。
--     assistant.s101  文献列表是写死的 4 条，原文案「由内置针灸知识库自动推荐」
--                     读起来像真在跑；改成先说明这是示例。
--
-- 【sort_num】新键插在 assistant 组中间，其后词条的 sort_num 在全量文件里已顺移。
-- 本增量不校准 —— sort_num 只影响后台列表的显示顺序，不影响任何前台取数。
-- ----------------------------

begin;

-- ----------------------------
-- 1、下线已删除的词条
--
-- 走软删除而不是 delete：唯一索引是 `where del_flag = '0'` 的部分索引，软删后同名键
-- 仍可重新插入；DAO 的每一处查询（含官网公开接口 `/action/site/texts`）都带
-- `del_flag = '0'`，所以软删即刻生效。哪天这几行文案要回来，改回 '0' 就是。
-- ----------------------------
update action_site_text
   set del_flag = '1',
       update_by = 'migration',
       update_time = now()
 where text_key in ('assistant.s017', 'assistant.s018', 'assistant.s019', 'assistant.s020')
   and del_flag = '0';

-- ----------------------------
-- 2、新增与更新词条
--
-- 列与 on conflict 子句照抄 `tools/extract_site_texts.py` 的生成结果，逐字一致 ——
-- 两条路径对同一批键的写入语义必须完全相同，否则「先跑增量再跑全量」和反过来跑
-- 会得到不同的结果。
-- ----------------------------
insert into action_site_text
    (text_key, page_key, page_label, text_zh, text_en, default_zh, default_en, has_markup, sort_num)
values
('assistant.typeOpt.trial', 'assistant', '报告助手', '干预性试验', 'Interventional trial', '干预性试验', 'Interventional trial', '0', 287),
('assistant.typeOpt.case', 'assistant', '报告助手', '病例报告 / 系列', 'Case report/series', '病例报告 / 系列', 'Case report/series', '0', 288),
('assistant.typeOpt.sr', 'assistant', '报告助手', '系统评价 / Meta', 'Systematic review / Meta', '系统评价 / Meta', 'Systematic review / Meta', '0', 289),
('assistant.typeOpt.obs', 'assistant', '报告助手', '观察性研究', 'Observational', '观察性研究', 'Observational', '0', 290),
('assistant.typeOpt.protocol', 'assistant', '报告助手', '临床试验方案', 'Trial protocol', '临床试验方案', 'Trial protocol', '0', 291),
('assistant.typeOpt.animal', 'assistant', '报告助手', '动物实验', 'Animal experiment', '动物实验', 'Animal experiment', '0', 292),
('assistant.typeOpt.guideline', 'assistant', '报告助手', '临床实践指南', 'Practice guideline', '临床实践指南', 'Practice guideline', '0', 293),
('assistant.s048', 'assistant', '报告助手', '<b>数据联动（规划中）。</b>后续将支持导入课题组既往基线表或 Excel 原始数据，自动填入模板的结果部分。', '<b>Data linkage (planned).</b> Importing an existing baseline table or raw Excel data to auto-fill the results section is on the roadmap.', '<b>数据联动（规划中）。</b>后续将支持导入课题组既往基线表或 Excel 原始数据，自动填入模板的结果部分。', '<b>Data linkage (planned).</b> Importing an existing baseline table or raw Excel data to auto-fill the results section is on the roadmap.', '1', 305),
('assistant.rvNoItems', 'assistant', '报告助手', '{code} 尚未录入 checklist 条目，暂时无法校验。可先在第一步换一种研究类型。', 'No checklist items have been entered for {code} yet, so it cannot be checked. Try another study type in step 1.', '{code} 尚未录入 checklist 条目，暂时无法校验。可先在第一步换一种研究类型。', 'No checklist items have been entered for {code} yet, so it cannot be checked. Try another study type in step 1.', '0', 324),
('assistant.s101', 'assistant', '报告助手', '以上为示例文献。正式版由内置针灸知识库按研究方向自动推荐，以近 3–5 年核心文献为主，并保留领域内的奠基性规范文献；引用前务必核验。', 'The references above are samples. In the live version they are recommended from the built-in acupuncture knowledge base by research topic — mainly core papers from the last 3–5 years, plus the foundational reporting standards of the field; always verify before citing.', '以上为示例文献。正式版由内置针灸知识库按研究方向自动推荐，以近 3–5 年核心文献为主，并保留领域内的奠基性规范文献；引用前务必核验。', 'The references above are samples. In the live version they are recommended from the built-in acupuncture knowledge base by research topic — mainly core papers from the last 3–5 years, plus the foundational reporting standards of the field; always verify before citing.', '0', 375),
('assistant.betaStep4', 'assistant', '报告助手', '界面演示 · 本步骤的续写、润色与文献推荐均为示例内容，工具内测中', 'Interface preview · the continuation, polishing and reference suggestions on this step are sample content; the tool is in closed beta', '界面演示 · 本步骤的续写、润色与文献推荐均为示例内容，工具内测中', 'Interface preview · the continuation, polishing and reference suggestions on this step are sample content; the tool is in closed beta', '0', 376)
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

-- 下线 4 条，新增 9 条，改默认 2 条
