-- ----------------------------
-- 018 · 站点文案增量：第四步独立面板的「写回草稿」（PostgreSQL）
--
-- 【什么时候需要这份文件】`action_site_text` 是 i18n 词条的**可编辑副本**：
-- 前端加了新的 `$t()` 键，键不进这张表，官网照样显示（回落到 i18n JSON 的默认值），
-- 但后台「站点文案管理」页里看不见、也就改不了。所以前端每加一批词条都要同步进来。
--
-- 【本次变更】新增 8 条 `assistant.wkSave*` —— 017 把第四步解耦成独立可用之后，
-- 生成结果只有「复制」一个去处，用户得手工粘回第二步。这一批是把它接回草稿的那一小段 UI：
-- 选一份草稿 + 选一条条目 → 写入 / 覆盖 / 追加。
--
-- 后端一个字没改：复用 `PUT /report-assist/apply`，它本来就验草稿归属、验条目属于该规范，
-- 并在服务端自己记 `applied` 留痕。
--
-- 【为什么有「覆盖」和「追加」两个动作】写回是整条覆盖。用户选中的条目里可能已经有他自己
-- 写的正文，盲覆盖掉是不能接受的 —— 所以覆盖前先把现有正文摆出来，并给一个「追加到末尾」
-- 的出路。条目为空时只显示「写入这一条」，不摆这两个容易选错的按钮。
--
-- 列与 on conflict 子句照抄 `tools/extract_site_texts.py` 的生成结果，逐字一致 ——
-- 两条路径对同一批键的写入语义必须完全相同，否则「先跑增量再跑全量」和反过来跑
-- 会得到不同的结果。
--
-- 【sort_num】取值与重跑生成器后的 `action-site-text-pg.sql` 逐条对齐（514–521）。
-- ----------------------------

begin;

insert into action_site_text
    (text_key, page_key, page_label, text_zh, text_en, default_zh, default_en, has_markup, sort_num)
values
('assistant.wkSaveTo', 'assistant', '报告助手', '保存到', 'Save to', '保存到', 'Save to', '0', 514),
('assistant.wkSaveItem', 'assistant', '报告助手', '写进哪一条', 'Which item to write into', '写进哪一条', 'Which item to write into', '0', 515),
('assistant.wkSavePickItem', 'assistant', '报告助手', '选择要写进的条目……', 'Choose an item to write into…', '选择要写进的条目……', 'Choose an item to write into…', '0', 516),
('assistant.wkSaveHasText', 'assistant', '报告助手', '该条目已有内容：', 'This item already has text:', '该条目已有内容：', 'This item already has text:', '0', 517),
('assistant.wkSaveWrite', 'assistant', '报告助手', '写入这一条', 'Write into this item', '写入这一条', 'Write into this item', '0', 518),
('assistant.wkSaveReplace', 'assistant', '报告助手', '覆盖这一条', 'Replace this item', '覆盖这一条', 'Replace this item', '0', 519),
('assistant.wkSaveAppend', 'assistant', '报告助手', '追加到末尾', 'Append to the end', '追加到末尾', 'Append to the end', '0', 520),
('assistant.wkSaveDone', 'assistant', '报告助手', '已写入草稿', 'Written to the draft', '已写入草稿', 'Written to the draft', '0', 521)
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

-- 新增 8 条（assistant.wkSave*）
