-- ----------------------------
-- 022 · 站点文案增量：新增「成果发表」页与详情页（PostgreSQL）
--
-- 【什么时候需要这份文件】`action_site_text` 是 i18n 词条的**可编辑副本**。前端新加的
-- `$t()` 键不同步进这张表，官网照样显示（回落 i18n JSON 的默认值），但后台
-- 「站点文案管理」里搜不到、也就改不了 —— 「明明是页面上的字，后台却找不到」
-- 只可能是漏了这一步。
--
-- 【本次变更】新增 36 条，无改写、无删除：
--   nav.publications / footer.links.publications  顶栏与页脚的入口文字（各 1 条）
--   publications.*        列表页 `pages/publications.vue`（22 条，含空态与分页）
--   publicationDetail.*   详情页 `pages/publication/[id].vue`（12 条）
--
-- **论文本身的标题、作者、期刊、摘要不在这里** —— 那些是 `action_publication` 表里的
-- 内容数据，由后台「成果发表管理」页维护，且一律照发表原文存一份、不做中英两版
-- （详见 `sql/action-publication-pg.sql` 的文件头）。本文件只管版面文字。
--
-- 列与 on conflict 子句照抄 `tools/extract_site_texts.py` 的生成结果，逐字一致 ——
-- 两条路径对同一批键的写入语义必须完全相同，否则「先跑增量再跑全量」和反过来跑
-- 会得到不同的结果。
--
-- 【sort_num】取值与重跑生成器后的 `action-site-text-pg.sql` 逐条对齐。nav 与 footer
-- 那两条插在中间（15 / 31），它们之后的存量行在全量快照里整体后移了一位；
-- 本文件不做位移，只影响后台列表的显示顺序（个别位置会出现重号），不影响任何前台取值。
-- 要对齐就跑一次全量快照 —— 那是可反复执行的。
-- ----------------------------

begin;

insert into action_site_text
    (text_key, page_key, page_label, text_zh, text_en, default_zh, default_en, has_markup, sort_num)
values
('nav.publications', 'nav', '顶部导航', '成果', 'Publications', '成果', 'Publications', '0', 15),
('footer.links.publications', 'footer', '页脚', '成果发表', 'Publications', '成果发表', 'Publications', '0', 31),
('publications.kicker', 'publications', '成果发表', '成果发表', 'Publications', '成果发表', 'Publications', '0', 964),
('publications.title', 'publications', '成果发表', 'ACTION 相关研究成果', 'Research output from ACTION', 'ACTION 相关研究成果', 'Research output from ACTION', '0', 965),
('publications.intro', 'publications', '成果发表', 'ACTION 团队在针刺临床研究方法学、报告规范与实施科学方向发表的论文，按发表年份倒序排列。论文标题、作者与期刊信息均按发表原文呈现，不作翻译。', 'Papers published by the ACTION team on acupuncture clinical research methodology, reporting guidelines and implementation science, listed newest first. Titles, authors and journal details appear exactly as published and are not translated.', 'ACTION 团队在针刺临床研究方法学、报告规范与实施科学方向发表的论文，按发表年份倒序排列。论文标题、作者与期刊信息均按发表原文呈现，不作翻译。', 'Papers published by the ACTION team on acupuncture clinical research methodology, reporting guidelines and implementation science, listed newest first. Titles, authors and journal details appear exactly as published and are not translated.', '0', 966),
('publications.searchPlaceholder', 'publications', '成果发表', '搜索标题、作者、期刊或 DOI', 'Search title, author, journal or DOI', '搜索标题、作者、期刊或 DOI', 'Search title, author, journal or DOI', '0', 967),
('publications.searchAria', 'publications', '成果发表', '搜索成果发表', 'Search publications', '搜索成果发表', 'Search publications', '0', 968),
('publications.allYears', 'publications', '成果发表', '全部年份', 'All years', '全部年份', 'All years', '0', 969),
('publications.noYear', 'publications', '成果发表', '未标注年份', 'Year not stated', '未标注年份', 'Year not stated', '0', 970),
('publications.yearFilterAria', 'publications', '成果发表', '按发表年份筛选', 'Filter by year of publication', '按发表年份筛选', 'Filter by year of publication', '0', 971),
('publications.count', 'publications', '成果发表', '共 {n} 篇', '{n} in total', '共 {n} 篇', '{n} in total', '0', 972),
('publications.viewDetail', 'publications', '成果发表', '查看详情', 'View details', '查看详情', 'View details', '0', 973),
('publications.loading', 'publications', '成果发表', '正在加载…', 'Loading…', '正在加载…', 'Loading…', '0', 974),
('publications.empty', 'publications', '成果发表', '暂无成果发表。', 'No publications yet.', '暂无成果发表。', 'No publications yet.', '0', 975),
('publications.emptyHint', 'publications', '成果发表', '换个关键词或选「全部年份」再试试。', 'Try a different keyword, or select “All years”.', '换个关键词或选「全部年份」再试试。', 'Try a different keyword, or select “All years”.', '0', 976),
('publications.loadError', 'publications', '成果发表', '成果列表加载失败，请稍后重试。', 'The publication list failed to load. Please try again shortly.', '成果列表加载失败，请稍后重试。', 'The publication list failed to load. Please try again shortly.', '0', 977),
('publications.retry', 'publications', '成果发表', '重新加载', 'Reload', '重新加载', 'Reload', '0', 978),
('publications.prevPage', 'publications', '成果发表', '上一页', 'Previous', '上一页', 'Previous', '0', 979),
('publications.nextPage', 'publications', '成果发表', '下一页', 'Next', '下一页', 'Next', '0', 980),
('publications.pageOf', 'publications', '成果发表', '第 {cur} / {all} 页', 'Page {cur} of {all}', '第 {cur} / {all} 页', 'Page {cur} of {all}', '0', 981),
('publications.pagerAria', 'publications', '成果发表', '成果列表分页', 'Publication list pagination', '成果列表分页', 'Publication list pagination', '0', 982),
('publications._title', 'publications', '成果发表', '成果发表 {''|''} ACTION · 针刺临床研究方法学与报告规范', 'Publications {''|''} ACTION · Acupuncture clinical research methodology and reporting', '成果发表 {''|''} ACTION · 针刺临床研究方法学与报告规范', 'Publications {''|''} ACTION · Acupuncture clinical research methodology and reporting', '0', 983),
('publications._desc', 'publications', '成果发表', 'ACTION 团队在针刺临床研究方法学、报告规范与实施科学方向发表的论文列表，含摘要、关键词、DOI 与原文链接。', 'Papers published by the ACTION team on acupuncture clinical research methodology, reporting guidelines and implementation science, with abstracts, keywords, DOIs and links to the original articles.', 'ACTION 团队在针刺临床研究方法学、报告规范与实施科学方向发表的论文列表，含摘要、关键词、DOI 与原文链接。', 'Papers published by the ACTION team on acupuncture clinical research methodology, reporting guidelines and implementation science, with abstracts, keywords, DOIs and links to the original articles.', '0', 984),
('publicationDetail.crumbAria', 'publicationDetail', '成果详情', '面包屑导航', 'Breadcrumb', '面包屑导航', 'Breadcrumb', '0', 985),
('publicationDetail.back', 'publicationDetail', '成果详情', '返回成果发表', 'Back to publications', '返回成果发表', 'Back to publications', '0', 986),
('publicationDetail.affiliations', 'publicationDetail', '成果详情', '作者单位', 'Affiliations', '作者单位', 'Affiliations', '0', 987),
('publicationDetail.abstract', 'publicationDetail', '成果详情', '摘要', 'Abstract', '摘要', 'Abstract', '0', 988),
('publicationDetail.keywords', 'publicationDetail', '成果详情', '关键词', 'Keywords', '关键词', 'Keywords', '0', 989),
('publicationDetail.howToCite', 'publicationDetail', '成果详情', '如何引用', 'How to cite', '如何引用', 'How to cite', '0', 990),
('publicationDetail.copyCitation', 'publicationDetail', '成果详情', '复制引用', 'Copy citation', '复制引用', 'Copy citation', '0', 991),
('publicationDetail.copied', 'publicationDetail', '成果详情', '已复制', 'Copied', '已复制', 'Copied', '0', 992),
('publicationDetail.copyFailed', 'publicationDetail', '成果详情', '复制失败，请手动选中', 'Copy failed — please select the text', '复制失败，请手动选中', 'Copy failed — please select the text', '0', 993),
('publicationDetail.readOnPublisher', 'publicationDetail', '成果详情', '阅读原文', 'Read the original', '阅读原文', 'Read the original', '0', 994),
('publicationDetail.downloadPdf', 'publicationDetail', '成果详情', '下载 PDF 全文', 'Download full text (PDF)', '下载 PDF 全文', 'Download full text (PDF)', '0', 995),
('publicationDetail.notFound', 'publicationDetail', '成果详情', '未找到该成果', 'Publication not found', '未找到该成果', 'Publication not found', '0', 996),
('publicationDetail.notFoundDesc', 'publicationDetail', '成果详情', '它可能已下线或链接有误。请返回成果发表列表查看。', 'It may have been taken offline, or the link is wrong. Head back to the publication list.', '它可能已下线或链接有误。请返回成果发表列表查看。', 'It may have been taken offline, or the link is wrong. Head back to the publication list.', '0', 997)
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

-- 新增 36 条，无改写、无删除。
--
-- 核对：
--   select text_key, text_zh, text_en from action_site_text
--    where page_key in ('publications', 'publicationDetail') order by sort_num;
--   -- 应为 34 条；另有 nav.publications 与 footer.links.publications 两条在各自分组里
