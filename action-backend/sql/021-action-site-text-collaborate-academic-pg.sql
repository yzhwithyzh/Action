-- ----------------------------
-- 021 · 站点文案增量：协作页第①段从「专家咨询」改写为「学术协作申请」（PostgreSQL）
--
-- 【什么时候需要这份文件】`action_site_text` 是 i18n 词条的**可编辑副本**。前端改了默认
-- 文案而库里不同步，后台「站点文案管理」里看到的仍是旧文案；且生成器那句 `case`
-- （后台没改过的行才跟着新默认走）会把旧文案当成「人工覆盖项」吐给前台，
-- 等于代码里的这次改写永远上不了线。
--
-- 【本次变更】改写 29 条，删键 1 条（`collaborate.s023`，见文件末尾）。左栏 14 条
-- （`s002`–`s015`）+ 右栏表单 15 条（`s016`–`s022` / `s032` / `s033` / `s037` / `s038`
-- 与四条散键）。没有新增键。
--
-- 语义变化（不只是措辞，逐条核对时别按旧标题理解）：
--   s002  「专家咨询通道」→「学术协作申请」：这一段的定位从「向专家提问」翻成
--          「向 ACTION 提合作申请」。**页面标题 `collaborate._title` 与顶部导航
--          `nav.collaborate` 仍写着「专家咨询」，甲方那两张批注图没有涉及**，
--          确认后另开一份增量改，不要在这里顺手改掉。
--   s004  「可咨询领域」→「可合作方向」：甲方批注图未标这一行，是随下面 5 张卡片
--          改的口径 —— 卡片内容已经全部是合作方向，标题留「可咨询领域」就对不上了。
--   s005–s014  5 张卡片整体换成 5 个合作方向（报告规范共建 / 临床研究合作 /
--          实施科学转化 / 学术会议论坛 / 其他）。**第 5 张的描述 s014 甲方没给**，
--          现文案是补写的占位（空着的话卡片会缺一行、视觉上像没加载出来），待甲方定稿。
--   s015   脚注从「由国际顾问委员会指导」改成「由顾问委员会与执行团队共同评审合作申请」。
--
-- **右侧表单跟着改了口径**：「咨询领域」→「合作方向」，chip 从 6 个（方法学与设计 /
-- 统计分析 / 针灸临床 / 报告规范 / 实施科学 / 其他）换成 5 个，与左栏五张卡片一一对应
-- —— 左栏就是这组 chip 的图例，条数或口径对不上时用户会在 chip 里找不到刚读到的方向。
-- 顺带把「提交咨询」「咨询主题」和那句「仅用于本次咨询的回复与统计」一并改成合作口径。
--
-- **这一改会动到落库的值**：chip 的 `data-v` 是**提交进后端 `content` 的固定中文值**
-- （`pages/collaborate.vue` 的 `submit` 把它拼成正文第一行），改版后新记录里写的是
-- 「合作方向: 报告规范共建」，旧记录仍是「咨询领域: 方法学与设计」。两批**不会自动对齐**，
-- 按领域统计时要认两套词面。没做数据迁移是因为旧记录里那句话是用户当时看到的问法，
-- 改写它等于篡改工单原文。
--
-- 同理 `pages/collaborate.vue` 把提交的 `requestType` 从 `'consult'` 改成了 `'collab'`
-- （后端 Literal 本来就有这一档，服务层不按它分支）—— 这是改版前后两批记录唯一
-- **结构化**的分界，留着 'consult' 的话两批语义不同的申请会混成一堆再也拆不开。
--
-- 列与 on conflict 子句照抄 `tools/extract_site_texts.py` 的生成结果，逐字一致 ——
-- 两条路径对同一批键的写入语义必须完全相同，否则「先跑增量再跑全量」和反过来跑
-- 会得到不同的结果。
--
-- 【sort_num】取值与重跑生成器后的 `action-site-text-pg.sql` 逐条对齐。
-- ----------------------------

begin;

insert into action_site_text
    (text_key, page_key, page_label, text_zh, text_en, default_zh, default_en, has_markup, sort_num)
values
('collaborate.s002', 'collaborate', '协作与联系', '学术协作申请', 'Academic Collaboration Application', '学术协作申请', 'Academic Collaboration Application', '0', 547),
('collaborate.s003', 'collaborate', '协作与联系', '诚邀全球学者与机构开展对等学术合作，ACTION 国际顾问委员会与执行团队将对合作申请进行评估对接，合作范围涵盖针刺报告规范、实施科学研究、国际联合临床试验、学术交流推广等方向。', 'We sincerely invite scholars and institutions worldwide for equal academic partnerships. The ACTION International Advisory Committee and Executive Team will review and follow up on applications. Potential cooperation covers acupuncture reporting guidelines, implementation science research, international joint clinical trials, and academic exchange.', '诚邀全球学者与机构开展对等学术合作，ACTION 国际顾问委员会与执行团队将对合作申请进行评估对接，合作范围涵盖针刺报告规范、实施科学研究、国际联合临床试验、学术交流推广等方向。', 'We sincerely invite scholars and institutions worldwide for equal academic partnerships. The ACTION International Advisory Committee and Executive Team will review and follow up on applications. Potential cooperation covers acupuncture reporting guidelines, implementation science research, international joint clinical trials, and academic exchange.', '0', 548),
('collaborate.s004', 'collaborate', '协作与联系', '可合作方向', 'Areas of collaboration', '可合作方向', 'Areas of collaboration', '0', 549),
('collaborate.s005', 'collaborate', '协作与联系', '针刺报告规范共建', 'Co-development of Acupuncture Reporting Guidelines', '针刺报告规范共建', 'Co-development of Acupuncture Reporting Guidelines', '0', 550),
('collaborate.s006', 'collaborate', '协作与联系', '开展针刺相关报告指南开发、条目修订、本土化推广等工作。', 'Develop, revise and locally adapt reporting standards for acupuncture research.', '开展针刺相关报告指南开发、条目修订、本土化推广等工作。', 'Develop, revise and locally adapt reporting standards for acupuncture research.', '0', 551),
('collaborate.s007', 'collaborate', '协作与联系', '针刺临床研究合作', 'Joint Acupuncture Clinical Research Projects', '针刺临床研究合作', 'Joint Acupuncture Clinical Research Projects', '0', 552),
('collaborate.s008', 'collaborate', '协作与联系', '洽谈多中心针刺临床试验、真实世界研究、系统综述等针刺临床研究项目。', 'Negotiate multi-centre acupuncture trials, real-world studies, systematic reviews and other joint research programmes.', '洽谈多中心针刺临床试验、真实世界研究、系统综述等针刺临床研究项目。', 'Negotiate multi-centre acupuncture trials, real-world studies, systematic reviews and other joint research programmes.', '0', 553),
('collaborate.s009', 'collaborate', '协作与联系', '实施科学转化研究合作', 'Collaboration on Implementation Science Transformation Research', '实施科学转化研究合作', 'Collaboration on Implementation Science Transformation Research', '0', 554),
('collaborate.s010', 'collaborate', '协作与联系', '围绕实施科学理论，推进针刺研究证据向临床场景落地转化研究。', 'Translate high-quality acupuncture evidence into real-world clinical practice guided by implementation science theories.', '围绕实施科学理论，推进针刺研究证据向临床场景落地转化研究。', 'Translate high-quality acupuncture evidence into real-world clinical practice guided by implementation science theories.', '0', 555),
('collaborate.s011', 'collaborate', '协作与联系', '学术会议、论坛合作', 'Academic Exchange & Platform Dissemination', '学术会议、论坛合作', 'Academic Exchange & Platform Dissemination', '0', 556),
('collaborate.s012', 'collaborate', '协作与联系', '国际学术会议合作、联合论坛举办、ACTION 平台资源国际传播推广。', 'Co-host international conferences and forums, and promote ACTION resources globally.', '国际学术会议合作、联合论坛举办、ACTION 平台资源国际传播推广。', 'Co-host international conferences and forums, and promote ACTION resources globally.', '0', 557),
('collaborate.s013', 'collaborate', '协作与联系', '其他学术合作', 'Other academic collaborations', '其他学术合作', 'Other academic collaborations', '0', 558),
('collaborate.s014', 'collaborate', '协作与联系', '其他有助于推动针刺研究规范化的学术合作形式，欢迎来函洽谈。', 'Any other academic collaboration that advances standardised acupuncture research — proposals are welcome.', '其他有助于推动针刺研究规范化的学术合作形式，欢迎来函洽谈。', 'Any other academic collaboration that advances standardised acupuncture research — proposals are welcome.', '0', 559),
('collaborate.s015', 'collaborate', '协作与联系', '<b>由 ACTION 国际顾问委员会与执行团队共同评审合作申请。</b>汇聚中韩针刺研究、循证医学、方法学与实施科学领域专家，共同推动全球针刺科研标准化发展。', '<b>All applications are reviewed by the ACTION International Advisory Committee and Executive Team.</b> Experts from China and the Republic of Korea specialising in acupuncture research, evidence-based medicine, methodology and implementation science work together to advance standardised global acupuncture research.', '<b>由 ACTION 国际顾问委员会与执行团队共同评审合作申请。</b>汇聚中韩针刺研究、循证医学、方法学与实施科学领域专家，共同推动全球针刺科研标准化发展。', '<b>All applications are reviewed by the ACTION International Advisory Committee and Executive Team.</b> Experts from China and the Republic of Korea specialising in acupuncture research, evidence-based medicine, methodology and implementation science work together to advance standardised global acupuncture research.', '1', 560),
('collaborate.s016', 'collaborate', '协作与联系', '提交合作申请', 'Submit an application', '提交合作申请', 'Submit an application', '0', 561),
('collaborate.s017', 'collaborate', '协作与联系', '合作方向 <span class="rq">*</span>', 'Area of collaboration <span class=''rq''>*</span>', '合作方向 <span class="rq">*</span>', 'Area of collaboration <span class=''rq''>*</span>', '1', 562),
('collaborate.s018', 'collaborate', '协作与联系', '报告规范共建', 'Reporting guidelines', '报告规范共建', 'Reporting guidelines', '0', 563),
('collaborate.s019', 'collaborate', '协作与联系', '临床研究合作', 'Clinical research', '临床研究合作', 'Clinical research', '0', 564),
('collaborate.s020', 'collaborate', '协作与联系', '实施科学转化', 'Implementation science', '实施科学转化', 'Implementation science', '0', 565),
('collaborate.s021', 'collaborate', '协作与联系', '学术会议与论坛', 'Conferences & forums', '学术会议与论坛', 'Conferences & forums', '0', 566),
('collaborate.s022', 'collaborate', '协作与联系', '其他', 'Other', '其他', 'Other', '0', 567),
('collaborate.s032', 'collaborate', '协作与联系', '合作主题 <span class="rq">*</span>', 'Proposal subject <span class=''rq''>*</span>', '合作主题 <span class="rq">*</span>', 'Proposal subject <span class=''rq''>*</span>', '1', 576),
('collaborate.s033', 'collaborate', '协作与联系', '详细描述 <span class="rq">*</span>', 'Details <span class=''rq''>*</span>', '详细描述 <span class="rq">*</span>', 'Details <span class=''rq''>*</span>', '1', 577),
('collaborate.s037', 'collaborate', '协作与联系', '提交后将安全存入 ACTION 平台，仅用于本次合作申请的评估、对接与统计；我们会在 3–5 个工作日内通过邮件与你联系。', 'Your application is stored securely on the ACTION platform and used only to assess and follow up this proposal, and for aggregate statistics. We will email you within 3–5 working days.', '提交后将安全存入 ACTION 平台，仅用于本次合作申请的评估、对接与统计；我们会在 3–5 个工作日内通过邮件与你联系。', 'Your application is stored securely on the ACTION platform and used only to assess and follow up this proposal, and for aggregate statistics. We will email you within 3–5 working days.', '0', 581),
('collaborate.s038', 'collaborate', '协作与联系', '提交合作申请 <span class="arrow" aria-hidden="true">→</span>', 'Submit application', '提交合作申请 <span class="arrow" aria-hidden="true">→</span>', 'Submit application', '1', 582),
('collaborate.areaRequired', 'collaborate', '协作与联系', '请选择合作方向。', 'Please choose an area of collaboration.', '请选择合作方向。', 'Please choose an area of collaboration.', '0', 653),
('collaborate.lblArea', 'collaborate', '协作与联系', '合作方向', 'Area of collaboration', '合作方向', 'Area of collaboration', '0', 655),
('collaborate.subjectPh', 'collaborate', '协作与联系', '例如：拟联合开展多中心针刺 RCT', 'e.g. Proposal for a multi-centre acupuncture RCT', '例如：拟联合开展多中心针刺 RCT', 'e.g. Proposal for a multi-centre acupuncture RCT', '0', 657),
('collaborate.questionPh', 'collaborate', '协作与联系', '请描述你的机构背景、合作设想与预期分工……', 'Describe your institution, what you propose, and how you envisage the division of work…', '请描述你的机构背景、合作设想与预期分工……', 'Describe your institution, what you propose, and how you envisage the division of work…', '0', 658)
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

-- chip 从 6 个减到 5 个，`collaborate.s023`（「其他」）在前端已删。生成脚本**不自动删行**
-- （改错一次就是一段文案凭空消失），所以这里手工软删一次：不删的话后台「站点文案管理」
-- 里会并排躺着两条「其他」（s022 与 s023），改哪条都可能是白改 —— s023 已经没有任何
-- `$t()` 在读它。软删而非物理删：`on conflict` 挂的是 `where del_flag = '0'` 的偏索引，
-- 这个键哪天回来还能重新插一行。
update action_site_text
   set del_flag = '2', update_time = current_timestamp, remark = '协作页改版：合作方向 chip 由 6 个减为 5 个，此键已无引用'
 where text_key = 'collaborate.s023' and del_flag = '0';

commit;

-- 改写 29 条（左栏 s002–s015 + 右栏表单 15 条），软删 1 条（s023），无新增。
--
-- 【sort_num 会差 1】s023 一删，全量快照里排在它之后的行整体前移了一位，而本文件只重设
-- 了自己那 29 条的 sort_num。这只影响后台列表的显示顺序（个别位置会出现重号），
-- 不影响任何前台取值。要对齐就跑一次 `sql/action-site-text-pg.sql` —— 那是可反复执行的
-- 全量快照。**不要在这里写 `sort_num = sort_num - 1` 的批量位移**：那条语句只在
-- 「库正好停在删 s023 之前的那一版」时才成立，跑早跑晚都会把顺序拧乱。
--
-- 核对：
--   select text_key, del_flag, text_zh from action_site_text
--    where page_key = 'collaborate' order by sort_num;
--   -- s023 应为 del_flag='2'，s018–s022 应是五个合作方向
--
-- 若某条在后台被人工改过，上面的 case 会保留人工值 —— 这一段是整体改写口径，
-- 保留下来的旧覆盖项会和新上下文对不上。执行后按上面那条 select 逐条看一眼，
-- 发现还留着旧文案的行，在后台点「还原默认」即可。
