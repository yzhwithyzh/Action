-- ----------------------------
-- 009 · 站点文案增量：报告助手第二步的可编辑模板（PostgreSQL）
--
-- 【什么时候需要这份文件】`action_site_text` 是 i18n 词条的**可编辑副本**：
-- 前端加了新的 `$t()` 键，键不进这张表，官网照样显示（回落到 i18n JSON 的默认值），
-- 但后台「站点文案管理」页里看不见、也就改不了。所以前端每加一批词条都要同步进来。
--
-- 【与 `action-site-text-pg.sql` 的关系】那份是 `python -m tools.extract_site_texts`
-- 生成的**全量同步**（1024 条，可反复执行，已含本文件的内容）。两条路择一即可：
--   · 全量：直接跑 `action-site-text-pg.sql`，顺带把所有词条的 sort_num 校准一遍；
--   · 增量：跑本文件，只动下面这 26 行，不扫全表。
--
-- 【本次变更】新增 26 条，配合报告助手第二步从「只读展示」改成「可编辑的结构化模板」：
--
--   assistant.tplRequired / tplOptional
--     条目上的「必填 / 选填」角标。来源是 `action_guideline_item.require_level`
--     （见 `007-action-guideline-item-require-level-pg.sql`），文档 2 明确要求区分
--     强制填写项与条件填写项。
--
--   assistant.df*（24 条）
--     草稿工具条、完成度、逐条输入框、针灸字段说明、生成初稿与预览。
--     `df` = draft。这一批里 **dfNeedLogin 与 dfAcuNote 两条最要紧**：前者是未登录时
--     唯一的解释（否则用户只看到一排不能点的输入框），后者说明针灸四项「填一次、
--     生成初稿时自动写进相关条目」，不说的话用户会在每条里重复抄一遍。
--
-- 【sort_num】新键插在 assistant 组中间，其后词条的 sort_num 在全量文件里已顺移。
-- 本增量不校准 —— sort_num 只影响后台列表的显示顺序，不影响任何前台取数。
--
-- 列与 on conflict 子句照抄 `tools/extract_site_texts.py` 的生成结果，逐字一致 ——
-- 两条路径对同一批键的写入语义必须完全相同，否则「先跑增量再跑全量」和反过来跑
-- 会得到不同的结果。
-- ----------------------------

begin;

insert into action_site_text
    (text_key, page_key, page_label, text_zh, text_en, default_zh, default_en, has_markup, sort_num)
values
('assistant.tplRequired', 'assistant', '报告助手', '必填', 'Required', '必填', 'Required', '0', 440),
('assistant.tplOptional', 'assistant', '报告助手', '选填', 'If applicable', '选填', 'If applicable', '0', 441),
('assistant.dfSwitch', 'assistant', '报告助手', '切换草稿', 'Switch draft', '切换草稿', 'Switch draft', '0', 442),
('assistant.dfNew', 'assistant', '报告助手', '新建草稿', 'New draft', '新建草稿', 'New draft', '0', 443),
('assistant.dfSave', 'assistant', '报告助手', '保存', 'Save', '保存', 'Save', '0', 444),
('assistant.dfSaving', 'assistant', '报告助手', '保存中…', 'Saving…', '保存中…', 'Saving…', '0', 445),
('assistant.dfSavedAt', 'assistant', '报告助手', '已保存 {at}', 'Saved {at}', '已保存 {at}', 'Saved {at}', '0', 446),
('assistant.dfUnsaved', 'assistant', '报告助手', '有未保存的改动', 'Unsaved changes', '有未保存的改动', 'Unsaved changes', '0', 447),
('assistant.dfDelete', 'assistant', '报告助手', '删除草稿', 'Delete draft', '删除草稿', 'Delete draft', '0', 448),
('assistant.dfDeleteConfirm', 'assistant', '报告助手', '删除这份草稿？其中已写好的条目正文会一并删除，且无法恢复。', 'Delete this draft? Everything you have written in it will be deleted too, and cannot be recovered.', '删除这份草稿？其中已写好的条目正文会一并删除，且无法恢复。', 'Delete this draft? Everything you have written in it will be deleted too, and cannot be recovered.', '0', 449),
('assistant.dfTooLong', 'assistant', '报告助手', '第 {no} 条正文超过 {max} 字符，请先精简后再保存。', 'Item {no} exceeds {max} characters. Please shorten it before saving.', '第 {no} 条正文超过 {max} 字符，请先精简后再保存。', 'Item {no} exceeds {max} characters. Please shorten it before saving.', '0', 450),
('assistant.dfTooShort', 'assistant', '报告助手', '初稿不足 {min} 字符，第三步无法校验。请再补充几条内容。', 'The draft is under {min} characters, so step 3 cannot check it. Please fill in a few more items.', '初稿不足 {min} 字符，第三步无法校验。请再补充几条内容。', 'The draft is under {min} characters, so step 3 cannot check it. Please fill in a few more items.', '0', 451),
('assistant.dfLogin', 'assistant', '报告助手', '登录后填写', 'Sign in to write', '登录后填写', 'Sign in to write', '0', 452),
('assistant.dfNeedLogin', 'assistant', '报告助手', '登录后可逐条填写并保存报告初稿，内容只属于你的账号；条目清单本身无需登录即可查看。', 'Sign in to fill in and save your draft report item by item — it belongs to your account only. The checklist itself is visible without signing in.', '登录后可逐条填写并保存报告初稿，内容只属于你的账号；条目清单本身无需登录即可查看。', 'Sign in to fill in and save your draft report item by item — it belongs to your account only. The checklist itself is visible without signing in.', '0', 453),
('assistant.dfProgress', 'assistant', '报告助手', '必填完成度', 'Required items done', '必填完成度', 'Required items done', '0', 454),
('assistant.dfTitleLabel', 'assistant', '报告助手', '草稿名称', 'Draft name', '草稿名称', 'Draft name', '0', 455),
('assistant.dfTitlePh', 'assistant', '报告助手', '例如：电针治疗膝骨关节炎随机对照试验', 'e.g. Electroacupuncture for knee osteoarthritis: an RCT', '例如：电针治疗膝骨关节炎随机对照试验', 'e.g. Electroacupuncture for knee osteoarthritis: an RCT', '0', 456),
('assistant.dfItemPh', 'assistant', '报告助手', '按本条的要求写下对应内容……', 'Write the content this item asks for…', '按本条的要求写下对应内容……', 'Write the content this item asks for…', '0', 457),
('assistant.dfAcuNote', 'assistant', '报告助手', '以下几项一次填写，生成初稿时会自动写进相关条目，不必在每条里重复。', 'Fill these in once — they are written into the related items when the draft is generated, so you need not repeat them.', '以下几项一次填写，生成初稿时会自动写进相关条目，不必在每条里重复。', 'Fill these in once — they are written into the related items when the draft is generated, so you need not repeat them.', '0', 458),
('assistant.dfBasisNote', 'assistant', '报告助手', '选穴依据补充说明', 'Point selection notes', '选穴依据补充说明', 'Point selection notes', '0', 459),
('assistant.dfBasisNotePh', 'assistant', '报告助手', '补充说明选穴的依据，如「依据经络辨证，取患侧阳陵泉（GB34）……」', 'Explain the rationale, e.g. “based on meridian differentiation, GB34 on the affected side…”', '补充说明选穴的依据，如「依据经络辨证，取患侧阳陵泉（GB34）……」', 'Explain the rationale, e.g. “based on meridian differentiation, GB34 on the affected side…”', '0', 460),
('assistant.dfCompose', 'assistant', '报告助手', '生成报告初稿', 'Generate draft report', '生成报告初稿', 'Generate draft report', '0', 461),
('assistant.dfComposing', 'assistant', '报告助手', '生成中…', 'Generating…', '生成中…', 'Generating…', '0', 462),
('assistant.dfPreview', 'assistant', '报告助手', '初稿预览', 'Draft preview', '初稿预览', 'Draft preview', '0', 463),
('assistant.dfSendReview', 'assistant', '报告助手', '送入第三步校验', 'Send to step 3', '送入第三步校验', 'Send to step 3', '0', 464),
('assistant.dfMissing', 'assistant', '报告助手', '还有 {n} 条必填未写，已在初稿中标为「待补充」', '{n} required item(s) still empty — marked “to be completed” in the draft', '还有 {n} 条必填未写，已在初稿中标为「待补充」', '{n} required item(s) still empty — marked “to be completed” in the draft', '0', 465)
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

-- 新增 26 条（tplRequired / tplOptional + assistant.df* 24 条）
