-- ----------------------------
-- 002 · 站点文案增量：报告助手第三步「针灸逻辑与术语校验」一批（PostgreSQL）
--
-- 【什么时候需要这份文件】`action_site_text` 是 i18n 词条的**可编辑副本**：
-- 前端加了新的 `$t()` 键，键不进这张表，官网照样显示（会回落到 i18n JSON 的默认值），
-- 但后台「站点文案管理」页里看不见、也就改不了。所以前端每加一批词条，都要同步进来。
--
-- 【与 `action-site-text-pg.sql` 的关系】那份是 `python -m tools.extract_site_texts`
-- 生成的**全量同步**（958 条，可反复执行，已含本文件的内容）。两条路择一即可：
--   · 全量：直接跑 `action-site-text-pg.sql`，顺带把所有词条的 sort_num 校准一遍；
--   · 增量：跑本文件，只动下面这 21 行，不扫全表。
-- 两者对「后台已改过的文案」的处理一致 —— 见下面 on conflict 里的 case，
-- 人工覆盖过的 text_* 原样保留，只刷新 default_*。
--
-- 【本次变更】报告助手第三步在「逐条完整性」之外新增了一层「全稿逻辑一致性 + 术语标准化」
-- 校验（干预/对照是否写混、针刺频次与随访时点是否矛盾、样本量依据与纳入例数是否匹配、
-- 穴位名称是否规范），对应 `tools/checklist_worker_tool/engine/consistency.py`。
--
--   新增 20 条，全部属于 assistant 组：
--     ckTitle / ckDesc                       栏目标题与说明
--     ckRule.{arm,schedule,sample,acupoint}  四条规则名。**键的后缀 = 引擎 RULES 里的
--                                            rule key**，引擎加规则时这里要同步加，
--                                            否则前台只会显示出键名本身
--     ckKind.{logic,term}                    规则分组标签
--     ckStatus.{ok,warn,issue,na,unchecked}  五档状态文案
--     ckEmpty.{ok,na,unchecked}              没有发现时那一行的说明。三档必须各说各的 ——
--                                            「未见问题」「不适用」「没跑完」混为一谈，
--                                            等于把没跑过的检查显示成了合格
--     ckSuggest / ckCapped / ckTruncated     建议前缀、发现过多的截断说明、稿件超长的说明
--     auditCross                             留痕面板里那条全稿校验记录
--
--   改默认 1 条：assistant.s060（第三步面板导语，补上新增的这一层）。后台若已人工改过
--     这一条，下面的 case 会保留人工版本，只刷新 default_zh/default_en。
--
-- 【sort_num】新键插在 assistant 组中间，其后约 600 条词条的 sort_num 在全量文件里
-- 已顺移 20。本增量不校准它们 —— sort_num 只影响后台列表的显示顺序，不影响任何前台取数；
-- 要校准就跑一次全量文件。
-- ----------------------------

begin;

insert into action_site_text
    (text_key, page_key, page_label, text_zh, text_en, default_zh, default_en, has_markup, sort_num)
values
('assistant.s060', 'assistant', '报告助手', '把稿件交给平台逐条核对：每行编号后，按第二步展开的 checklist 逐条判定<b>已报告 / 描述模糊 / 未报告</b>，已报告的回填行号与原文片段，未报告的说明该补什么——投稿时随稿提交的那份表，到这一步就填好了。逐条之外再通读一遍全稿，交叉核对<b>针灸逻辑一致性与术语标准化</b>。', 'Hand the manuscript over for an item-by-item check: every line is numbered, then each checklist item from step 2 is judged <b>reported / vague / not reported</b> — with line numbers and the quoted evidence where it is reported, and what to add where it is not. That is the table journals ask you to submit, filled in. The whole manuscript is then read once more to cross-check <b>acupuncture logic and terminology</b>.', '把稿件交给平台逐条核对：每行编号后，按第二步展开的 checklist 逐条判定<b>已报告 / 描述模糊 / 未报告</b>，已报告的回填行号与原文片段，未报告的说明该补什么——投稿时随稿提交的那份表，到这一步就填好了。逐条之外再通读一遍全稿，交叉核对<b>针灸逻辑一致性与术语标准化</b>。', 'Hand the manuscript over for an item-by-item check: every line is numbered, then each checklist item from step 2 is judged <b>reported / vague / not reported</b> — with line numbers and the quoted evidence where it is reported, and what to add where it is not. That is the table journals ask you to submit, filled in. The whole manuscript is then read once more to cross-check <b>acupuncture logic and terminology</b>.', '1', 310),
('assistant.ckTitle', 'assistant', '报告助手', '针灸逻辑与术语校验', 'Acupuncture logic & terminology checks', '针灸逻辑与术语校验', 'Acupuncture logic & terminology checks', '0', 331),
('assistant.ckDesc', 'assistant', '报告助手', '逐条核对之外，再通读全稿交叉核对四件事：干预与对照有没有写混、针刺频次与随访时点前后是否矛盾、样本量依据与实际纳入例数是否匹配、穴位名称是否用了标准写法。这一层只指路、不改稿，结论请人工复核。', 'Beyond the item-by-item check, the whole manuscript is read once more to cross-check four things: whether the intervention and the control arm have been mixed up, whether needling frequency and follow-up time points contradict each other, whether the sample-size calculation matches the number actually enrolled, and whether acupoint names follow the standard convention. This layer points at problems rather than fixing them — please verify each finding yourself.', '逐条核对之外，再通读全稿交叉核对四件事：干预与对照有没有写混、针刺频次与随访时点前后是否矛盾、样本量依据与实际纳入例数是否匹配、穴位名称是否用了标准写法。这一层只指路、不改稿，结论请人工复核。', 'Beyond the item-by-item check, the whole manuscript is read once more to cross-check four things: whether the intervention and the control arm have been mixed up, whether needling frequency and follow-up time points contradict each other, whether the sample-size calculation matches the number actually enrolled, and whether acupoint names follow the standard convention. This layer points at problems rather than fixing them — please verify each finding yourself.', '0', 332),
('assistant.ckRule.arm', 'assistant', '报告助手', '干预措施与对照组描述是否混淆', 'Intervention and control arm confused with each other', '干预措施与对照组描述是否混淆', 'Intervention and control arm confused with each other', '0', 333),
('assistant.ckRule.schedule', 'assistant', '报告助手', '针刺频次与随访时间点是否前后矛盾', 'Needling frequency contradicts follow-up time points', '针刺频次与随访时间点是否前后矛盾', 'Needling frequency contradicts follow-up time points', '0', 334),
('assistant.ckRule.sample', 'assistant', '报告助手', '样本量计算依据与纳入例数是否匹配', 'Sample-size calculation vs. number enrolled', '样本量计算依据与纳入例数是否匹配', 'Sample-size calculation vs. number enrolled', '0', 335),
('assistant.ckRule.acupoint', 'assistant', '报告助手', '穴位名称是否使用标准写法与编码', 'Acupoint names and standard codes', '穴位名称是否使用标准写法与编码', 'Acupoint names and standard codes', '0', 336),
('assistant.ckKind.logic', 'assistant', '报告助手', '逻辑一致性', 'Logical consistency', '逻辑一致性', 'Logical consistency', '0', 337),
('assistant.ckKind.term', 'assistant', '报告助手', '术语标准化', 'Terminology', '术语标准化', 'Terminology', '0', 338),
('assistant.ckStatus.ok', 'assistant', '报告助手', '未见问题', 'No issue found', '未见问题', 'No issue found', '0', 339),
('assistant.ckStatus.warn', 'assistant', '报告助手', '待核', 'To verify', '待核', 'To verify', '0', 340),
('assistant.ckStatus.issue', 'assistant', '报告助手', '不一致', 'Inconsistent', '不一致', 'Inconsistent', '0', 341),
('assistant.ckStatus.na', 'assistant', '报告助手', '不适用', 'Not applicable', '不适用', 'Not applicable', '0', 342),
('assistant.ckStatus.unchecked', 'assistant', '报告助手', '未完成', 'Not completed', '未完成', 'Not completed', '0', 343),
('assistant.ckEmpty.ok', 'assistant', '报告助手', '通读全稿未发现该类问题。', 'Nothing of this kind was found on a full read of the manuscript.', '通读全稿未发现该类问题。', 'Nothing of this kind was found on a full read of the manuscript.', '0', 344),
('assistant.ckEmpty.na', 'assistant', '报告助手', '本稿件的研究类型不涉及这项检查。', 'This check does not apply to the study design of this manuscript.', '本稿件的研究类型不涉及这项检查。', 'This check does not apply to the study design of this manuscript.', '0', 345),
('assistant.ckEmpty.unchecked', 'assistant', '报告助手', '这项检查没有跑完（模型调用失败）。既不代表有问题，也不代表没问题，请人工核对。', 'This check did not finish (the model call failed). It means neither that there is a problem nor that there is none — please verify manually.', '这项检查没有跑完（模型调用失败）。既不代表有问题，也不代表没问题，请人工核对。', 'This check did not finish (the model call failed). It means neither that there is a problem nor that there is none — please verify manually.', '0', 346),
('assistant.ckSuggest', 'assistant', '报告助手', '建议：', 'Suggestion: ', '建议：', 'Suggestion: ', '0', 347),
('assistant.ckCapped', 'assistant', '报告助手', '同类问题较多，仅列出前 {n} 条。', 'Many findings of this kind; only the first {n} are listed.', '同类问题较多，仅列出前 {n} 条。', 'Many findings of this kind; only the first {n} are listed.', '0', 348),
('assistant.ckTruncated', 'assistant', '报告助手', '稿件超出全稿校验的通读上限，仅通读了前一部分；后半段未参与交叉核对。', 'The manuscript exceeds the reading budget for whole-manuscript checks. Only the first part was read; the remainder was not cross-checked.', '稿件超出全稿校验的通读上限，仅通读了前一部分；后半段未参与交叉核对。', 'The manuscript exceeds the reading budget for whole-manuscript checks. Only the first part was read; the remainder was not cross-checked.', '0', 349),
('assistant.auditCross', 'assistant', '报告助手', '完成全稿交叉核对：不一致 {issue} 项 · 待核 {warn} 项 · 未见问题 {ok} 项', 'Whole-manuscript cross-check complete: {issue} inconsistent · {warn} to verify · {ok} with no issue', '完成全稿交叉核对：不一致 {issue} 项 · 待核 {warn} 项 · 未见问题 {ok} 项', 'Whole-manuscript cross-check complete: {issue} inconsistent · {warn} to verify · {ok} with no issue', '0', 350)
on conflict (text_key) where del_flag = '0' do update set
    page_key   = excluded.page_key,
    page_label = excluded.page_label,
    has_markup = excluded.has_markup,
    sort_num   = excluded.sort_num,
    -- 后台没改过（当前值 = 旧默认值）的行，跟着新默认值走；改过的原样保留。
    -- 这段与全量文件逐字一致，否则「先增量后全量」与反过来跑会得到不同结果。
    text_zh = case when action_site_text.text_zh is not distinct from action_site_text.default_zh
                   then excluded.default_zh else action_site_text.text_zh end,
    text_en = case when action_site_text.text_en is not distinct from action_site_text.default_en
                   then excluded.default_en else action_site_text.text_en end,
    default_zh = excluded.default_zh,
    default_en = excluded.default_en;

commit;

-- 共 21 条词条
