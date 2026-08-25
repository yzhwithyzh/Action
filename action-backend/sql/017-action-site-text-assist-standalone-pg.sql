-- ----------------------------
-- 017 · 站点文案增量：第四步解耦成独立可用（PostgreSQL）
--
-- 【什么时候需要这份文件】`action_site_text` 是 i18n 词条的**可编辑副本**：
-- 前端加了新的 `$t()` 键，键不进这张表，官网照样显示（回落到 i18n JSON 的默认值），
-- 但后台「站点文案管理」页里看不见、也就改不了。所以前端每加一批词条都要同步进来。
--
-- 【本次变更】新增 17 条 `assistant.wkSolo* / wkCopy*`，改写 3 条（s087 / wkNeedDraft /
-- wkNeedReview）。改写那三条是本文件的重点 —— **它们的语义变了，不只是措辞**。
--
-- 【为什么第四步要解耦】《智能报告辅助工具.docx》第 4 节四项功能（续写 / 背景生成 /
-- 润色 / 翻译）的输入**全是用户直接给的**：关键词、研究方向、要润色的那段话、要翻译的摘要。
-- 没有一项依赖第二步的草稿或第三步的判定。
--
-- 此前的实现强制要求 draft_id + item_id，依据是文档那句「遵循 STRICTA 条目规范」——
-- 遵循哪一条？得先站在某一条上。**那个推理是错的**：这句话要的是「知道按哪份规范写」，
-- 而那个信息第一步就给了。把「需要规范」读成「需要具体条目」，再推出「需要草稿和判定」，
-- 实际效果是把已经写好稿、直接来第三步的用户（文档意义上最主要的一类）整个挡在第四步之外
-- —— 表现就是「第三步跑完 79 条判定、64 条待办，第四步一个字都出不来」。
--
-- 所以 s087 从「第三步判定的工作清单」改成「直接用就行，清单是额外的」；
-- wkNeedDraft / wkNeedReview 从**拦路的空状态**改成**下半段的一句说明**
-- （原文「这一步才知道要改什么」在新版里是假的 —— 上面的面板照常可用）。
--
-- 列与 on conflict 子句照抄 `tools/extract_site_texts.py` 的生成结果，逐字一致 ——
-- 两条路径对同一批键的写入语义必须完全相同，否则「先跑增量再跑全量」和反过来跑
-- 会得到不同的结果。
--
-- 【sort_num】取值与重跑生成器后的 `action-site-text-pg.sql` 逐条对齐。
-- `on conflict` 里写着 `sort_num = excluded.sort_num`，两份不一致就意味着
-- 「先增量后全量」与反过来跑得到的表不同。
-- ----------------------------

begin;

insert into action_site_text
    (text_key, page_key, page_label, text_zh, text_en, default_zh, default_en, has_markup, sort_num)
values
('assistant.s087', 'assistant', '报告助手', '给报告文字做续写、润色与中译英。**直接用就行**：填几个关键词或粘一段正文即可，不必先建草稿、也不必先跑校验。若你在第二步填过草稿并跑过第三步，下方还会额外列出判为「描述模糊 / 未报告」的条目，改完可一键写回对应条目。', 'Draft, polish and translate report prose. **Usable on its own** — just give a few keywords or paste a passage; no draft and no prior check required. If you did fill in a draft in step 2 and ran step 3, the items judged “vague” or “not reported” are also listed below, and your edits can be written straight back to them.', '给报告文字做续写、润色与中译英。**直接用就行**：填几个关键词或粘一段正文即可，不必先建草稿、也不必先跑校验。若你在第二步填过草稿并跑过第三步，下方还会额外列出判为「描述模糊 / 未报告」的条目，改完可一键写回对应条目。', 'Draft, polish and translate report prose. **Usable on its own** — just give a few keywords or paste a passage; no draft and no prior check required. If you did fill in a draft in step 2 and ran step 3, the items judged “vague” or “not reported” are also listed below, and your edits can be written straight back to them.', '0', 392),
('assistant.wkNeedDraft', 'assistant', '报告助手', '你还没有草稿。上面的功能照常可用；若在第二步对着 checklist 填几条，这里会额外多出一张「哪几条待改」的清单。', 'You have no draft yet. Everything above works regardless; fill in a few checklist items in step 2 and a list of “what still needs work” will appear here as well.', '你还没有草稿。上面的功能照常可用；若在第二步对着 checklist 填几条，这里会额外多出一张「哪几条待改」的清单。', 'You have no draft yet. Everything above works regardless; fill in a few checklist items in step 2 and a list of “what still needs work” will appear here as well.', '0', 479),
('assistant.wkNeedReview', 'assistant', '报告助手', '这份草稿还没跑过校验。上面的功能照常可用；跑完第三步，需要改的条目会额外列到这里，改完可一键写回。', 'This draft has not been checked yet. Everything above works regardless; once step 3 finishes, the items needing work are also listed here and can be written straight back.', '这份草稿还没跑过校验。上面的功能照常可用；跑完第三步，需要改的条目会额外列到这里，改完可一键写回。', 'This draft has not been checked yet. Everything above works regardless; once step 3 finishes, the items needing work are also listed here and can be written straight back.', '0', 480),
('assistant.wkSoloTab.continue', 'assistant', '报告助手', '续写', 'Draft', '续写', 'Draft', '0', 497),
('assistant.wkSoloTab.polish', 'assistant', '报告助手', '润色', 'Polish', '润色', 'Polish', '0', 498),
('assistant.wkSoloTab.translate', 'assistant', '报告助手', '中译英', 'To English', '中译英', 'To English', '0', 499),
('assistant.wkSoloGuideline', 'assistant', '报告助手', '按 {code} 规范', 'Following {code}', '按 {code} 规范', 'Following {code}', '0', 500),
('assistant.wkSoloLead.continue', 'assistant', '报告助手', '给几个关键词，生成这一段应有的报告文字。已有半句的话贴在下面，会顺着往下写。', 'Give a few keywords and get the passage this section calls for. Paste any half-written text below and it will be continued.', '给几个关键词，生成这一段应有的报告文字。已有半句的话贴在下面，会顺着往下写。', 'Give a few keywords and get the passage this section calls for. Paste any half-written text below and it will be continued.', '0', 501),
('assistant.wkSoloLead.polish', 'assistant', '报告助手', '把要润色的正文贴在下面，选一种风格。数据与限定语一律保留，只改表达。', 'Paste the passage to polish below and pick a style. Every data point and qualifier is kept — only the wording changes.', '把要润色的正文贴在下面，选一种风格。数据与限定语一律保留，只改表达。', 'Paste the passage to polish below and pick a style. Every data point and qualifier is kept — only the wording changes.', '0', 502),
('assistant.wkSoloLead.translate', 'assistant', '报告助手', '把要投稿国际期刊的中文正文贴在下面，译成学术英文。术语用国际针刺研究文献的通行译法。', 'Paste the Chinese passage below to get publication-ready academic English, using the terminology conventional in international acupuncture research.', '把要投稿国际期刊的中文正文贴在下面，译成学术英文。术语用国际针刺研究文献的通行译法。', 'Paste the Chinese passage below to get publication-ready academic English, using the terminology conventional in international acupuncture research.', '0', 503),
('assistant.wkSoloKwPh', 'assistant', '报告助手', '例如：电针，疏密波，2/100 Hz，留针 30 分钟', 'e.g. electroacupuncture, dense-disperse wave, 2/100 Hz, 30 min retention', '例如：电针，疏密波，2/100 Hz，留针 30 分钟', 'e.g. electroacupuncture, dense-disperse wave, 2/100 Hz, 30 min retention', '0', 504),
('assistant.wkSoloKwLabel', 'assistant', '报告助手', '续写关键词', 'Keywords', '续写关键词', 'Keywords', '0', 505),
('assistant.wkSoloTextPh', 'assistant', '报告助手', '把要改的正文粘贴到这里……', 'Paste the passage to work on…', '把要改的正文粘贴到这里……', 'Paste the passage to work on…', '0', 506),
('assistant.wkSoloTextOptPh', 'assistant', '报告助手', '（选填）已经写了半句的话贴在这里，会顺着往下写……', '(optional) Paste any half-written text here and it will be continued…', '（选填）已经写了半句的话贴在这里，会顺着往下写……', '(optional) Paste any half-written text here and it will be continued…', '0', 507),
('assistant.wkSoloTextLabel', 'assistant', '报告助手', '正文', 'Passage', '正文', 'Passage', '0', 508),
('assistant.wkSoloChars', 'assistant', '报告助手', '{n} / {max} 字符', '{n} / {max} chars', '{n} / {max} 字符', '{n} / {max} chars', '0', 509),
('assistant.wkSoloRun', 'assistant', '报告助手', '生成', 'Generate', '生成', 'Generate', '0', 510),
('assistant.wkCopy', 'assistant', '报告助手', '复制', 'Copy', '复制', 'Copy', '0', 511),
('assistant.wkCopied', 'assistant', '报告助手', '已复制', 'Copied', '已复制', 'Copied', '0', 512),
('assistant.wkCopyFailed', 'assistant', '报告助手', '复制失败，请手动选中上面的文字。', 'Copy failed — please select the text above manually.', '复制失败，请手动选中上面的文字。', 'Copy failed — please select the text above manually.', '0', 513)
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

-- 新增 17 条（assistant.wkSolo* / wkCopy*），改写 3 条（s087 / wkNeedDraft / wkNeedReview）
--
-- 核对改写的那三条有没有落到位：
--   select text_key, text_zh from action_site_text
--    where text_key in ('assistant.s087', 'assistant.wkNeedDraft', 'assistant.wkNeedReview');
