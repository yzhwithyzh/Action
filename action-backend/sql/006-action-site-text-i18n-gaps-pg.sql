-- ----------------------------
-- 006 · 站点文案增量：首页模块卡片标签 + 一批漏掉 i18n 的无障碍文案（PostgreSQL）
--
-- 【什么时候需要这份文件】`action_site_text` 是 i18n 词条的**可编辑副本**：
-- 前端加了新的 `$t()` 键，键不进这张表，官网照样显示（会回落到 i18n JSON 的默认值），
-- 但后台「站点文案管理」页里看不见、也就改不了。所以前端每加一批词条，都要同步进来。
--
-- 【与 `action-site-text-pg.sql` 的关系】那份是 `python -m tools.extract_site_texts`
-- 生成的**全量同步**（1001 条，可反复执行，已含本文件的内容）。两条路择一即可：
--   · 全量：直接跑 `action-site-text-pg.sql`，顺带把所有词条的 sort_num 校准一遍；
--   · 增量：跑本文件，只动下面这 34 行，不扫全表。
--
-- 【本次变更】新增 34 条，全是「本来就该能切语言、却漏了」的文案，分两批：
--
-- ① index.modTag.*（21 条）—— 首页「一个平台，四类能力」五张模块卡片下方那排小标签
--    （`RCT · CONSORT/STRICTA`、`在线模板`…）。原先是 `pages/index.vue` 模板里写死的
--    中文 `<li>`，切到英文界面纹丝不动。它们带 `aria-hidden="true"`、是装饰性标签而
--    不是数据，所以既没走 i18n、也没进这张表 —— 整页都能切语言，只有这一排不动。
--    键名分组即卡片：gl=报告规范体系 / as=报告助手 / im=实施科学 /
--    sr=方法学评估(SRD) / co=协作与咨询；序号即卡片内的显示顺序。
--    **加标签要同时改 `pages/index.vue` 的 `MOD_TAGS`** —— 那个数组只存键名，
--    决定渲染哪几枚、按什么顺序（vue-i18n 的消息里存不了数组，见该处注释）。
--
-- ② 无障碍与占位文案（13 条）—— `aria-label` / `placeholder` / mailto 主题。
--    这类文案**屏幕上不显示或只在空输入框里显示**，所以整站切成英文时没人看得出
--    它们还是中文：读屏器会念中文、英文访客点「Support ACTION」弹出的邮件主题行是中文。
--      index.previewAria              首页 Hero 里那张 role=img 界面预览图的说明
--      about.mailSubject{Support,Contact} / collaborate.mailSubject
--                                     三个 mailto 的 subject（前台用 encodeURIComponent 编码）
--      collaborate.{subjectPh,questionPh}
--                                     咨询表单两个输入框的占位提示（英文原取自已废弃的
--                                     `data-en-ph` 属性 —— 静态站时代用 JS 切 placeholder 的
--                                     遗留物，早已无人读取，本次一并删掉）
--      implementation.{modesAria,ericFilterAria,lblContext,contextPh}
--      guidelines.pilotFactsAria / news.filterAria / newsDetail.crumbAria
--
--    同批还**删掉了 6 个多余的 `aria-label`**（collaborate 表单的类型/主题/描述/姓名/
--    邮箱/单位）：这些控件都已有 `<label for>` 指着，而 aria-label 的优先级高于
--    `<label>`，挂上等于把可见标签整个替换掉 —— 原先挂的还是写死的中文。
--    它们不需要词条，故不在下面的清单里。
--
-- 【sort_num】新键插在各自分组中间，其后词条的 sort_num 在全量文件里已顺移。
-- 本增量不校准 —— sort_num 只影响后台列表的显示顺序，不影响任何前台取数。
-- ----------------------------

begin;

-- 列与 on conflict 子句照抄 `tools/extract_site_texts.py` 的生成结果，逐字一致 ——
-- 两条路径对同一批键的写入语义必须完全相同，否则「先跑增量再跑全量」和反过来跑
-- 会得到不同的结果。
insert into action_site_text
    (text_key, page_key, page_label, text_zh, text_en, default_zh, default_en, has_markup, sort_num)
values
('index.previewAria', 'index', '首页', '报告助手界面预览：选择研究类型为随机对照试验，自动挂载 CONSORT、STRICTA、SPIRIT 规范，逐条校验报告完整性清单，当前完整性 82%。', 'Preview of the reporting assistant: with ''randomised controlled trial'' selected as the study type, the CONSORT, STRICTA and SPIRIT guidelines are loaded automatically and the reporting-completeness checklist is verified item by item; completeness is currently 82%.', '报告助手界面预览：选择研究类型为随机对照试验，自动挂载 CONSORT、STRICTA、SPIRIT 规范，逐条校验报告完整性清单，当前完整性 82%。', 'Preview of the reporting assistant: with ''randomised controlled trial'' selected as the study type, the CONSORT, STRICTA and SPIRIT guidelines are loaded automatically and the reporting-completeness checklist is verified item by item; completeness is currently 82%.', '0', 130),
('index.modTag.gl1', 'index', '首页', 'RCT · CONSORT/STRICTA', 'RCT · CONSORT/STRICTA', 'RCT · CONSORT/STRICTA', 'RCT · CONSORT/STRICTA', '0', 162),
('index.modTag.gl2', 'index', '首页', '方案 · SPIRIT', 'Protocol · SPIRIT', '方案 · SPIRIT', 'Protocol · SPIRIT', '0', 163),
('index.modTag.gl3', 'index', '首页', '系统综述 · PRISMA', 'Systematic review · PRISMA', '系统综述 · PRISMA', 'Systematic review · PRISMA', '0', 164),
('index.modTag.gl4', 'index', '首页', '病例 · CARE', 'Case report · CARE', '病例 · CARE', 'Case report · CARE', '0', 165),
('index.modTag.gl5', 'index', '首页', '指南 · RIGHT', 'Guideline · RIGHT', '指南 · RIGHT', 'Guideline · RIGHT', '0', 166),
('index.modTag.gl6', 'index', '首页', '动物 · ARRIVE', 'Animal study · ARRIVE', '动物 · ARRIVE', 'Animal study · ARRIVE', '0', 167),
('index.modTag.as1', 'index', '首页', '研究类型匹配', 'Study-type matching', '研究类型匹配', 'Study-type matching', '0', 168),
('index.modTag.as2', 'index', '首页', '在线模板', 'Online templates', '在线模板', 'Online templates', '0', 169),
('index.modTag.as3', 'index', '首页', '内容校验', 'Content checking', '内容校验', 'Content checking', '0', 170),
('index.modTag.as4', 'index', '首页', 'AI 辅助撰写', 'AI-assisted writing', 'AI 辅助撰写', 'AI-assisted writing', '0', 171),
('index.modTag.as5', 'index', '首页', '导出分享', 'Export & share', '导出分享', 'Export & share', '0', 172),
('index.modTag.im1', 'index', '首页', 'CFIR 评估优化', 'CFIR assessment', 'CFIR 评估优化', 'CFIR assessment', '0', 173),
('index.modTag.im2', 'index', '首页', 'ERIC 策略匹配', 'ERIC strategy matching', 'ERIC 策略匹配', 'ERIC strategy matching', '0', 174),
('index.modTag.im3', 'index', '首页', 'RE-AIM 转化评价', 'RE-AIM evaluation', 'RE-AIM 转化评价', 'RE-AIM evaluation', '0', 175),
('index.modTag.sr1', 'index', '首页', 'SRD 重复性评估', 'SRD duplication assessment', 'SRD 重复性评估', 'SRD duplication assessment', '0', 176),
('index.modTag.sr2', 'index', '首页', '逐条比对', 'Item-by-item comparison', '逐条比对', 'Item-by-item comparison', '0', 177),
('index.modTag.sr3', 'index', '首页', '整体判定', 'Overall judgement', '整体判定', 'Overall judgement', '0', 178),
('index.modTag.sr4', 'index', '首页', '导出表格', 'Excel export', '导出表格', 'Excel export', '0', 179),
('index.modTag.co1', 'index', '首页', '专家咨询通道', 'Expert consultation', '专家咨询通道', 'Expert consultation', '0', 180),
('index.modTag.co2', 'index', '首页', '用户交流论坛', 'User forum', '用户交流论坛', 'User forum', '0', 181),
('index.modTag.co3', 'index', '首页', '机构合作网络', 'Institutional network', '机构合作网络', 'Institutional network', '0', 182),
('about.mailSubjectSupport', 'about', '关于我们', '支持 / 参与 ACTION', 'Supporting / joining ACTION', '支持 / 参与 ACTION', 'Supporting / joining ACTION', '0', 278),
('about.mailSubjectContact', 'about', '关于我们', 'ACTION 咨询', 'ACTION enquiry', 'ACTION 咨询', 'ACTION enquiry', '0', 279),
('collaborate.subjectPh', 'collaborate', '协作与联系', '例如：假针参数应如何报告', 'e.g. How to report sham-needle parameters', '例如：假针参数应如何报告', 'e.g. How to report sham-needle parameters', '0', 577),
('collaborate.questionPh', 'collaborate', '协作与联系', '请描述你的研究背景与需要协助的具体问题……', 'Describe your study background and the specific question you need help with…', '请描述你的研究背景与需要协助的具体问题……', 'Describe your study background and the specific question you need help with…', '0', 578),
('collaborate.mailSubject', 'collaborate', '协作与联系', 'ACTION 机构合作 / 参与咨询', 'ACTION institutional collaboration / consultation', 'ACTION 机构合作 / 参与咨询', 'ACTION institutional collaboration / consultation', '0', 579),
('guidelines.pilotFactsAria', 'guidelines', '报告规范目录', '试点测试关键数字', 'Pilot-test key figures', '试点测试关键数字', 'Pilot-test key figures', '0', 759),
('implementation.modesAria', 'implementation', '实施性研究', 'CFIR 使用模式', 'CFIR usage mode', 'CFIR 使用模式', 'CFIR usage mode', '0', 802),
('implementation.ericFilterAria', 'implementation', '实施性研究', '按类别筛选策略', 'Filter strategies by category', '按类别筛选策略', 'Filter strategies by category', '0', 803),
('implementation.lblContext', 'implementation', '实施性研究', '情境描述', 'Context description', '情境描述', 'Context description', '0', 804),
('implementation.contextPh', 'implementation', '实施性研究', '例如：我科室想在门诊常规开展针刺镇痛，但年轻医生操作不规范、缺乏标准化培训；西医科室转诊意愿低；医院对针刺项目没有绩效激励；患者对针具有顾虑、依从性差……', 'e.g. We want to offer acupuncture analgesia routinely in our outpatient clinic, but junior clinicians'' technique varies and there is no standardised training; referral from Western-medicine departments is low; the hospital offers no performance incentive for acupuncture; patients are wary of needles and adherence is poor…', '例如：我科室想在门诊常规开展针刺镇痛，但年轻医生操作不规范、缺乏标准化培训；西医科室转诊意愿低；医院对针刺项目没有绩效激励；患者对针具有顾虑、依从性差……', 'e.g. We want to offer acupuncture analgesia routinely in our outpatient clinic, but junior clinicians'' technique varies and there is no standardised training; referral from Western-medicine departments is low; the hospital offers no performance incentive for acupuncture; patients are wary of needles and adherence is poor…', '0', 805),
('news.filterAria', 'news', '新闻动态', '按标签筛选新闻', 'Filter news by tag', '按标签筛选新闻', 'Filter news by tag', '0', 860),
('newsDetail.crumbAria', 'newsDetail', '新闻详情', '面包屑导航', 'Breadcrumb', '面包屑导航', 'Breadcrumb', '0', 881)
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

-- 新增 34 条
