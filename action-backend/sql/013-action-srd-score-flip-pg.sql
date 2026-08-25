-- ----------------------------
-- 增量：把 SRD 存量评估的条目评分翻到引擎 0.8.0 的方向
--
-- 0.7.x 沿用甲方 Excel 表 1 表头的口径「完全相同 0 分 … 完全不同 3 分」（分越低越重复）；
-- 0.8.0 定稿改为「分数即相似度」：**3 分完全相同、0 分完全不同，分越高越重复**，
-- 重复百分比随之由 `(满分−得分)/满分` 改为 `得分/满分`。
--
-- **两处一起改的净效果是结论一格不动**：pct / level / overall_level / 判定理由全部不变，
-- 翻转只重新标注了分数这一层。所以本文件只动 rating / score / score_sum 三个量，
-- 不碰任何判定结果 —— 谁要是顺手把 pct 也翻了，历史结论就真的反过来了。
--
-- 同理 dup_count / diff_count 也不动：3/2 归 dup、1/0 归 diff，
-- 翻转把 0↔3、1↔2 对调，恰好还落在原来那一侧。
--
-- ## 幂等
--
-- 翻转是自逆运算，跑两遍就翻回去了，所以必须有闸。闸是 `engine_version`：
-- 只翻 0.6.x / 0.7.x 产出的评估，翻完给版本号**追加**一句 `(scores flipped to 0.8.0)`。
-- 追加而不是改写，是因为这一列记的是「哪个引擎算出来的」，那是事实，不该被迁移抹掉；
-- 追加的这句记的是「这行后来被翻过」，两件事都要留。
--
-- 版本号为空的行（早期落库时没记）一并翻：那个年代只可能是老方向。
-- 已经是 0.8.0 的行、以及带了 flipped 标记的行都不动。
--
-- 可重复执行。
-- ----------------------------

begin;

-- 先把要处理的评估圈出来，后面三步都引用它 —— 三步必须用同一个集合，
-- 否则第一步改完版本号，第二步就圈不到同一批行了（条目翻了、领域没翻）。
create temporary table _srd_flip_targets on commit drop as
select assessment_id
  from action_srd_assessment
 where coalesce(engine_version, '') not like '%flipped to 0.8.0%'
   and (
       coalesce(engine_version, '') = ''
       or engine_version like 'srd-engine/0.6%'
       or engine_version like 'srd-engine/0.7%'
   );

-- 1. 条目：rating 与 score 取补（unclear 不动 —— 它不是一个分数）
update action_srd_item it
   set rating = case it.rating
                    when '0' then '3'
                    when '1' then '2'
                    when '2' then '1'
                    when '3' then '0'
                    else it.rating
                end,
       score  = case when it.score is null then null else 3 - it.score end
  from action_srd_group g
  join action_srd_domain d on d.domain_id = g.domain_id
 where it.group_id = g.group_id
   and d.assessment_id in (select assessment_id from _srd_flip_targets);

-- 2. 领域：得分取补。分母用 score_max（可评分满分）而不是 score_max_full ——
--    证据不足的条目本来就不在分子分母里，拿名义满分取补会凭空多出它们那几分。
update action_srd_domain d
   set score_sum = coalesce(d.score_max, 0) - coalesce(d.score_sum, 0)
 where d.assessment_id in (select assessment_id from _srd_flip_targets);

-- 3. 整体：同上，并给版本号追加翻转标记（这一步必须最后做，它就是幂等闸本身）
update action_srd_assessment a
   set overall_score_sum = coalesce(a.overall_score_max, 0) - coalesce(a.overall_score_sum, 0),
       engine_version    = case
                               when coalesce(a.engine_version, '') = ''
                                   then '(scores flipped to 0.8.0)'
                               else a.engine_version || ' (scores flipped to 0.8.0)'
                           end,
       update_time       = now()
 where a.assessment_id in (select assessment_id from _srd_flip_targets);

comment on column action_srd_item.rating is '条目评分（3完全相同 2部分相同 1部分不同 0完全不同 unclear证据不足）';
comment on column action_srd_item.score is '评分对应分数0-3，分越高越重复；证据不足为空，不进分子分母';
comment on column action_srd_domain.score_sum is '领域得分（分越高越重复）';
comment on column action_srd_assessment.overall_score_sum is '整体得分（0–3 分/条，分越高越重复）';

-- ---------------------------------------------------------------- 站点文案：还原被翻转的档位词条
--
-- `srd.rt0`–`srd.rt3` 这四对键**互换了含义**（rt0 从「完全相同」变成「完全不同」），
-- 这在站点文案表里是个特例：平时改默认文案时，后台的人工覆盖 `text_*` 该原样保留
-- （那是「代码改了措辞、人家的定制不该被冲掉」）。但这里键的所指变了，留着覆盖
-- 就等于**把 3 分那一档标成「完全不同」**，比没人改过还糟 —— 而且页面照常渲染，
-- 只有对着分数看的人才会发现。
--
-- 所以对这几个键强制还原成新默认值（即 `text_* := default_*`）。
-- 前提是 action-site-text-pg.sql 的新版已经执行过（它把 default_* 刷成了翻转后的文案）；
-- 顺序反了的话这一步会把旧默认值抄进 text_*，重跑一次即可修正。
update action_site_text
   set text_zh     = default_zh,
       text_en     = default_en,
       update_time = now(),
       remark      = '评分方向翻转（引擎 0.8.0），档位词条含义对调，已还原默认'
 where text_key in ('srd.rt0', 'srd.rt1', 'srd.rt2', 'srd.rt3',
                    'srd.rt0Desc', 'srd.rt1Desc', 'srd.rt2Desc', 'srd.rt3Desc',
                    'srd.scoreFormula', 'srd.scoreTitle')
   and (text_zh is distinct from default_zh or text_en is distinct from default_en);

commit;
