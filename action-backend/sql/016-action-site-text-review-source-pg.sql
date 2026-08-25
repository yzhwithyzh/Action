-- ----------------------------
-- 016 · 站点文案增量：结果区的稿件原文面板（PostgreSQL）
--
-- 【什么时候需要这份文件】`action_site_text` 是 i18n 词条的**可编辑副本**：
-- 前端加了新的 `$t()` 键，键不进这张表，官网照样显示（回落到 i18n JSON 的默认值），
-- 但后台「站点文案管理」页里看不见、也就改不了。所以前端每加一批词条都要同步进来。
--
-- 【本次变更】新增 4 条 `assistant.rvSrc*` —— 第三步结果区里那块「被校验的稿件原文」。
--
-- 【它补的是 014 的一个半截】014 把稿件存了下来，历史点开时也确实读了回来，但结果区的
-- 输入框是 `v-if="reviewState !== 'done'"` 整块藏起来的 —— 稿件取回来了却没有任何地方
-- 显示它。于是判定里那两样证据都落了空：「报告于第 12 行」这个行号，和 evidence 那段引文，
-- **两样都只有对着原文才核得动**。从历史点开一条三个月前的记录时尤其明显：
-- 满屏判定，却不知道是哪份稿子判出来的。
--
-- 面板默认折叠（多数时候用户只看判定）、带行号（不带行号的话它就只是一堵墙，
-- 行号引用照样落空），判定里的行号引用可点，点了展开并滚到那几行。
--
-- 列与 on conflict 子句照抄 `tools/extract_site_texts.py` 的生成结果，逐字一致 ——
-- 两条路径对同一批键的写入语义必须完全相同，否则「先跑增量再跑全量」和反过来跑
-- 会得到不同的结果。
--
-- 【sort_num】取值与重跑生成器后的 `action-site-text-pg.sql` 逐条对齐（353–356）。
-- `on conflict` 里写着 `sort_num = excluded.sort_num`，两份不一致就意味着
-- 「先增量后全量」与反过来跑得到的表不同。新键插在 assistant 组中间，其后词条
-- （含 015 那批 rvHist*）的 sort_num 在全量文件里已顺移；本增量不校准那部分。
-- ----------------------------

begin;

insert into action_site_text
    (text_key, page_key, page_label, text_zh, text_en, default_zh, default_en, has_markup, sort_num)
values
('assistant.rvSrcShow', 'assistant', '报告助手', '展开被校验的稿件原文', 'Show the manuscript that was checked', '展开被校验的稿件原文', 'Show the manuscript that was checked', '0', 353),
('assistant.rvSrcHide', 'assistant', '报告助手', '收起稿件原文', 'Hide the manuscript', '收起稿件原文', 'Hide the manuscript', '0', 354),
('assistant.rvSrcMeta', 'assistant', '报告助手', '共 {n} 行 · {c} 字', '{n} lines · {c} chars', '共 {n} 行 · {c} 字', '{n} lines · {c} chars', '0', 355),
('assistant.rvSrcJump', 'assistant', '报告助手', '在原文中定位这几行', 'Locate these lines in the manuscript', '在原文中定位这几行', 'Locate these lines in the manuscript', '0', 356)
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

-- 新增 4 条（assistant.rvSrc*）
