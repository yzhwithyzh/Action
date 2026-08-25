-- ----------------------------
-- 015 · 站点文案增量：第三步校验历史 + 改写稿件留存的承诺（PostgreSQL）
--
-- 【什么时候需要这份文件】`action_site_text` 是 i18n 词条的**可编辑副本**：
-- 前端加了新的 `$t()` 键，键不进这张表，官网照样显示（回落到 i18n JSON 的默认值），
-- 但后台「站点文案管理」页里看不见、也就改不了。所以前端每加一批词条都要同步进来。
--
-- 【本次变更】
--
--   ① 新增 13 条 `assistant.rvHist*` —— 第三步的「校验历史」区。
--
--   ② **改写 `assistant.rvHint`**，这一条是本文件存在的真正理由。
--      它原先写的是「稿件只在校验期间流转，不会入库」。014 让稿件与逐条 evidence
--      随任务台账一起落库（否则历史点开只剩「第12条 描述模糊」，没有原文可回溯），
--      那句话就成了谎话。**代码与文案必须同一批上线** —— 先上 014 再补这份，
--      中间那段时间页面上挂着的就是一句假承诺。
--
--      新文案如实说明：稿件与结果存在你的账号下、可在「校验历史」里回看、
--      删除记录时正文一并清除（后端 `soft_delete_review_dao` 是真删正文，不是只置 del_flag）。
--
-- 【为什么这里要强制冲掉人工覆盖】`rvHint` 用的是 `case when 当前值 = 旧默认值` 那套
-- 常规写法，**没有**强制覆盖。理由与 013 翻转评分标签那次相反：那次是**键的所指变了**
-- （3 分从「完全不同」变成「完全相同」），留着旧覆盖等于把标签挂反；这次键的所指没变，
-- 仍旧是「这个输入框该怎么用」的说明。若甲方此前手改过这句话，那是他们自己的措辞，
-- 冲掉反而是越权 —— 但**改动隐私口径后要提醒他们复核这一条**，
-- 后台「站点文案管理」搜 `rvHint` 即可。
--
-- 列与 on conflict 子句照抄 `tools/extract_site_texts.py` 的生成结果，逐字一致 ——
-- 两条路径对同一批键的写入语义必须完全相同，否则「先跑增量再跑全量」和反过来跑
-- 会得到不同的结果。
--
-- 【sort_num】取值与重跑生成器后的 `action-site-text-pg.sql` **逐条对齐**（rvHint 334、
-- rvHist* 353–365），不是随手接在表尾。sort_num 虽只影响后台列表的显示顺序、不影响任何
-- 前台取数，但 `on conflict` 里写着 `sort_num = excluded.sort_num` —— 两份不一致就意味着
-- 「先增量后全量」与反过来跑得到的表不同，而这正是这套增量/全量并行机制要避免的事。
-- 新键插在 assistant 组中间，其后词条的 sort_num 在全量文件里已顺移；本增量不校准那部分。
-- ----------------------------

begin;

insert into action_site_text
    (text_key, page_key, page_label, text_zh, text_en, default_zh, default_en, has_markup, sort_num)
values
('assistant.rvHint', 'assistant', '报告助手', '把稿件正文粘贴到这里（正文即可，不必带参考文献）。系统会给每一行编号，逐条核对第二步展开的 checklist，并回填「报告于第几行」或「未报告的原因」。稿件与判定结果会保存在你的账号下，供你在下方「校验历史」里回看；删除记录时稿件正文会一并清除。', 'Paste the body of your manuscript here (references are not needed). Every line is numbered, then checked item by item against the checklist expanded in step 2, filling in “reported on line N” or the reason it is missing. The manuscript and its results are saved under your account so you can reopen them from “Check history” below; deleting a record also erases the manuscript.', '把稿件正文粘贴到这里（正文即可，不必带参考文献）。系统会给每一行编号，逐条核对第二步展开的 checklist，并回填「报告于第几行」或「未报告的原因」。稿件与判定结果会保存在你的账号下，供你在下方「校验历史」里回看；删除记录时稿件正文会一并清除。', 'Paste the body of your manuscript here (references are not needed). Every line is numbered, then checked item by item against the checklist expanded in step 2, filling in “reported on line N” or the reason it is missing. The manuscript and its results are saved under your account so you can reopen them from “Check history” below; deleting a record also erases the manuscript.', '0', 334),
('assistant.rvHistTitle', 'assistant', '报告助手', '校验历史', 'Check history', '校验历史', 'Check history', '0', 353),
('assistant.rvHistDesc', 'assistant', '报告助手', '每次提交都会留下一条记录，关掉页面或刷新之后仍可在这里点开回看，跑失败的也在。删除会连同稿件正文一并清除。', 'Every submission leaves a record here, so you can reopen a result after closing or refreshing the page — failed runs included. Deleting a record also erases the stored manuscript.', '每次提交都会留下一条记录，关掉页面或刷新之后仍可在这里点开回看，跑失败的也在。删除会连同稿件正文一并清除。', 'Every submission leaves a record here, so you can reopen a result after closing or refreshing the page — failed runs included. Deleting a record also erases the stored manuscript.', '0', 354),
('assistant.rvHistRefresh', 'assistant', '报告助手', '刷新', 'Refresh', '刷新', 'Refresh', '0', 355),
('assistant.rvHistEmpty', 'assistant', '报告助手', '还没有校验记录。提交一次校验后，这里会留下可回看的结果。', 'No checks yet. Once you run one, the result stays here for you to reopen.', '还没有校验记录。提交一次校验后，这里会留下可回看的结果。', 'No checks yet. Once you run one, the result stays here for you to reopen.', '0', 356),
('assistant.rvHistChars', 'assistant', '报告助手', '{n} 字', '{n} chars', '{n} 字', '{n} chars', '0', 357),
('assistant.rvHistView', 'assistant', '报告助手', '查看', 'View', '查看', 'View', '0', 358),
('assistant.rvHistDelete', 'assistant', '报告助手', '删除这条记录', 'Delete this record', '删除这条记录', 'Delete this record', '0', 359),
('assistant.rvHistConfirmDelete', 'assistant', '报告助手', '删除后，这次校验的稿件正文与原文引用会被一并清除，不可恢复。确定删除吗？', 'Deleting this record also erases the manuscript and the quoted excerpts stored with it. This cannot be undone. Delete it?', '删除后，这次校验的稿件正文与原文引用会被一并清除，不可恢复。确定删除吗？', 'Deleting this record also erases the manuscript and the quoted excerpts stored with it. This cannot be undone. Delete it?', '0', 360),
('assistant.rvHistQueued', 'assistant', '报告助手', '排队中', 'Queued', '排队中', 'Queued', '0', 361),
('assistant.rvHistRunning', 'assistant', '报告助手', '校验中 ', 'Checking ', '校验中 ', 'Checking ', '0', 362),
('assistant.rvHistDone', 'assistant', '报告助手', '已完成', 'Completed', '已完成', 'Completed', '0', 363),
('assistant.rvHistFailed', 'assistant', '报告助手', '失败', 'Failed', '失败', 'Failed', '0', 364),
('assistant.rvHistStopped', 'assistant', '报告助手', '已停止', 'Stopped', '已停止', 'Stopped', '0', 365)
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

-- 新增 13 条（assistant.rvHist*），改写 1 条（assistant.rvHint）—— insert 共 14 行
--
-- 核对隐私文案有没有落到位（这句话现在必须与实现一致）：
--   select text_key, text_zh from action_site_text where text_key = 'assistant.rvHint';
