-- ----------------------------
-- 官网-团队成员（国际顾问委员会 / 核心执行团队）（PostgreSQL）
--
-- 数据来源：《ACTION网站及其材料/About us/How we are organised(2).docx》（2026-08 更新版），
-- 该版为每位成员补了头像与详细履历。头像已抽出并压缩到 action-frontend/public/team/*.jpg，
-- 本表只存相对路径，换图直接替换同名文件或在后台改 avatar_url。
--
-- 顾问委员会的 Akihiko Ozaki 来自更后一版《How we are organised(3).docx》，
-- 按该文档的排列插在 Myeong Soo Lee 之后（board 组 sort_num 2，其后各位顺延）。
--
-- 成员的日常增删改走后台「团队成员管理」页面（action:teamMember:*），不要手改本文件。
--
-- 关于 name_zh：docx 与仓库里其余材料通篇只给了拉丁文姓名，没有一处中文名可核对。
-- 9 位中国籍成员的 name_zh 是按「机构 + 研究方向 + 拼音」推断填入的，**请甲方逐条核对**，
-- 有出入时直接在后台「团队成员管理」页改。
-- 4 位韩国籍成员（Myeong Soo Lee / Ye-seul Lee / Changsop Yang / Tae-Hun Kim）不译：
-- 예슬(Ye-seul) 本身没有对应汉字，其余三位的汉字名同样无从确认；
-- 中文学术站对外籍学者保留罗马字姓名是通行做法。
-- 日籍的 Akihiko Ozaki 同理保留罗马字（其汉字名与所在医院的汉字写法在材料里都没有出处，
-- 按读音倒推等于替甲方拍板）；甲方若给出汉字名，直接在后台「团队成员管理」页改。
-- ----------------------------

begin;

drop table if exists action_team_member;

create table action_team_member (
    member_id       serial       primary key,
    group_key       varchar(32)  not null default 'board',
    name_zh         varchar(200) not null,
    name_en         varchar(200) default '',
    honorific       varchar(32)  default '',
    title_zh        varchar(300) default '',
    title_en        varchar(500) default '',
    affiliation_zh  varchar(500) default '',
    affiliation_en  varchar(800) default '',
    role_zh         varchar(300) default '',
    role_en         varchar(500) default '',
    expertise_zh    varchar(500) default '',
    expertise_en    varchar(800) default '',
    summary_zh      text,
    summary_en      text,
    bio_zh          text,
    bio_en          text,
    contribution_zh text,
    contribution_en text,
    avatar_url      varchar(300) default '',
    homepage_url    varchar(500) default '',
    email           varchar(200) default '',
    sort_num        int          default 0,
    status          char(1)      default '0',
    del_flag        char(1)      default '0',
    create_by       varchar(64)  default '',
    create_time     timestamp,
    update_by       varchar(64)  default '',
    update_time     timestamp,
    remark          varchar(500)
);

comment on table action_team_member is '官网-团队成员';
comment on column action_team_member.member_id is '成员id';
comment on column action_team_member.group_key is '所属组（board国际顾问委员会 core核心执行团队）';
comment on column action_team_member.name_zh is '姓名（中文；docx 未给中文名时与英文一致，由后台补录）';
comment on column action_team_member.name_en is '姓名（英文）';
comment on column action_team_member.honorific is '称谓（Prof./Dr.，与姓名分开存，便于排版）';
comment on column action_team_member.title_zh is '职称/头衔（中文）';
comment on column action_team_member.title_en is '职称/头衔（英文）';
comment on column action_team_member.affiliation_zh is '所属机构（中文）';
comment on column action_team_member.affiliation_en is '所属机构（英文）';
comment on column action_team_member.role_zh is '在 ACTION 中的角色（中文）';
comment on column action_team_member.role_en is '在 ACTION 中的角色（英文）';
comment on column action_team_member.expertise_zh is '研究方向标签（中文，顿号分隔）';
comment on column action_team_member.expertise_en is '研究方向标签（英文，分号分隔）';
comment on column action_team_member.summary_zh is '一句话简介（中文，列表卡片用）';
comment on column action_team_member.summary_en is '一句话简介（英文，列表卡片用）';
comment on column action_team_member.bio_zh is '详细履历（中文，详情页用）';
comment on column action_team_member.bio_en is '详细履历（英文，详情页用）';
comment on column action_team_member.contribution_zh is '对 ACTION 的贡献（中文，详情页单独成块）';
comment on column action_team_member.contribution_en is '对 ACTION 的贡献（英文，详情页单独成块）';
comment on column action_team_member.avatar_url is '头像地址（站内相对路径或外链）';
comment on column action_team_member.homepage_url is '个人主页/学术档案链接';
comment on column action_team_member.email is '联系邮箱（留空则前台不展示）';
comment on column action_team_member.sort_num is '组内显示顺序';
comment on column action_team_member.status is '状态（0正常 1停用）';
comment on column action_team_member.del_flag is '删除标志（0存在 2删除）';

create index idx_atm_group on action_team_member (group_key, sort_num);

-- ---------------------------------------------------------------- 国际顾问委员会

insert into action_team_member (group_key, name_zh, name_en, honorific, title_zh, title_en, affiliation_zh, affiliation_en, role_zh, role_en, expertise_zh, expertise_en, summary_zh, summary_en, bio_zh, bio_en, contribution_zh, contribution_en, avatar_url, sort_num, status, del_flag, create_by, create_time)
values
('board', 'Myeong Soo Lee', 'Myeong Soo Lee', 'Prof.',
 '首席研究员', 'Principal Researcher',
 '韩国韩医学研究院（KIOM）', 'Korea Institute of Oriental Medicine, Republic of Korea',
 '方法学指导', 'Methodology guidance',
 '系统评价、假针刺对照设计、临床指南制订', 'Systematic review; Sham-controlled trial design; Clinical guideline development',
 'WHO 传统医学咨询组核心专家、G-I-N 亚洲指导委员会委员，循证针灸领域的世界级学者，发表同行评议论文 650 余篇，h 指数 64。',
 'Core expert of the WHO Traditional Medicine Advisory Group and the G-I-N Asia Steering Committee; a world-leading authority in evidence-based acupuncture with 650+ peer-reviewed papers and an h-index of 64.',
 'Myeong Soo Lee 教授现任韩国韩医学研究院首席研究员，并在中国、新加坡与美国多所知名大学担任荣誉教授。作为 WHO 传统医学咨询组与 G-I-N 亚洲指导委员会的核心专家，他是循证针灸领域的世界级学者。已发表同行评议论文 650 余篇，h 指数 64，专长于系统评价、假针刺对照试验设计与临床指南制订。',
 'Prof. Myeong Soo Lee serves as Principal Researcher at the Korea Institute of Oriental Medicine and holds honorary professorships at prestigious universities across China, Singapore and the US. A core expert of the WHO Traditional Medicine Advisory Group and G-I-N Asia Steering Committee, he is a world-leading expert in evidence-based acupuncture. He has published more than 650 peer-reviewed papers with an h-index of 64, specializing in systematic reviews, sham-controlled trial design and clinical guideline formulation.',
 '作为 RIGHT 工作组核心成员，他为 ACTION 提供顶级方法学指导，支持针刺报告规范与证据评价工具的建设，并推动标准化临床研究规范在全球范围的普及。',
 'As a key member of the RIGHT Working Group, he delivers top-tier methodological guidance to ACTION, supporting the construction of acupuncture reporting standards, evidence assessment tools and global popularization of standardized clinical research norms.',
 'https://action-gmu.oss-cn-guangzhou.aliyuncs.com/site/team/myeong-soo-lee.jpg', 1, '0', '0', 'migration', current_timestamp),

('board', 'Akihiko Ozaki', 'Akihiko Ozaki', 'Prof.',
 '乳腺与甲状腺中心主任（医学博士）', 'Director, Breast & Thyroid Center, MD, PhD',
 '日本福岛 Jyoban 医院', 'Jyoban Hospital, Fukushima, Japan',
 'AI 研究伦理与研究透明化', 'AI research ethics & research transparency',
 '卫生政策、研究透明化、利益冲突治理、灾难医学、AI 临床支持系统',
 'Health policy; Research transparency; Conflict-of-interest governance; Disaster medicine; AI-based clinical support systems',
 '日本 Yen For Docs 数据库创建者，在 The Lancet、BMJ Evidence-Based Medicine 等期刊发表同行评议论文 426 余篇，并参与研制生成式 AI 医学研究报告规范 GAMER。',
 'Founder of the Yen For Docs database; author of 426+ peer-reviewed papers in journals including The Lancet and BMJ Evidence-Based Medicine, and co-developer of the GAMER reporting guideline for generative AI in medical research.',
 'Akihiko Ozaki 教授，医学博士，现任日本福岛 Jyoban 医院乳腺与甲状腺中心主任。他是一位兼具临床实践与公共卫生双重专长的医师科学家，核心研究涵盖卫生政策、研究透明化、利益冲突治理、灾难医学以及基于 AI 的临床支持系统研发。他创建了 Yen For Docs 数据库——该数据库系统分析日本医药企业向医疗从业者的支付情况，在日本全国范围内广受认可。他已在 The Lancet、BMJ Evidence-Based Medicine 等期刊发表同行评议论文 426 余篇，并参与研制了面向医学研究中生成式 AI 的报告规范 GAMER。',
 'Prof. Akihiko Ozaki, MD, PhD, serves as Director of the Breast & Thyroid Center at Jyoban Hospital, Fukushima, Japan. A physician-researcher with dual expertise in clinical practice and public health, his core research covers health policy, research transparency, conflicts of interest governance, disaster medicine, and the development of AI-based clinical support systems. He is the founder of Yen For Docs, a nationally recognized database systematically analyzing industry payments to healthcare professionals in Japan. He has published over 426 peer-reviewed papers in journals including The Lancet and BMJ Evidence-Based Medicine, and co-developed the GAMER reporting guideline for generative AI in medical research.',
 '作为 ACTION 的国际顾问，他在 AI 研究伦理、报告标准化与研究透明化治理方面提供权威指导，进一步夯实平台智能研究工具的方法学严谨性与伦理框架。',
 'As an international advisor to ACTION, he provides authoritative guidance on AI research ethics, reporting standardization and research transparency governance, further strengthening the methodological rigor and ethical framework of the platform''s intelligent research tools.',
 'https://action-gmu.oss-cn-guangzhou.aliyuncs.com/site/team/akihiko-ozaki.jpg', 2, '0', '0', 'migration', current_timestamp),

('board', '刘存志', 'Cunzhi Liu', 'Prof.',
 '副校长', 'Vice President',
 '北京中医药大学', 'Beijing University of Chinese Medicine',
 '临床疗效评价', 'Clinical efficacy evaluation',
 '针刺临床疗效评价、作用机制研究', 'Acupuncture clinical efficacy evaluation; Mechanistic research',
 '国家杰出青年科学基金获得者、岐黄学者，在 JAMA Internal Medicine 等期刊发表高影响力论文 300 余篇，被公认为全球最具影响力的针灸科学家之一。',
 'Awarded the National Science Fund for Distinguished Young Scholars and the Qihuang Scholar title; author of 300+ high-impact articles in journals such as JAMA Internal Medicine and recognised as one of the world''s most influential acupuncture scientists.',
 'Cunzhi Liu 教授现任北京中医药大学副校长，国家杰出青年科学基金获得者、岐黄学者，是针灸领域的顶尖学者。其研究聚焦针刺临床疗效评价及其作用机制，已在 JAMA Internal Medicine 等期刊发表高影响力论文 300 余篇，被公认为全球最具影响力的针灸科学家之一。',
 'Prof. Cunzhi Liu, Vice President of Beijing University of Chinese Medicine, is a top-tier acupuncture scholar awarded the National Science Fund for Distinguished Young Scholars and the Qihuang Scholar title. His research focuses on acupuncture clinical efficacy evaluation and underlying mechanisms. He has published over 300 high-impact articles in journals like JAMA Internal Medicine and is recognized as one of the world''s most influential acupuncture scientists.',
 '他领衔针灸疗效评价重点实验室，为 ACTION 的真实世界临床证据库、案例示范模块，以及报告规范在国内针刺试验中的落地应用提供坚实的学术支撑。',
 'Leading the Key Laboratory for Acupuncture Therapy Evaluation, he provides solid academic backing for ACTION''s real-world clinical evidence library, case demonstration modules and the application of standardized reporting specifications in domestic acupuncture trials.',
 'https://action-gmu.oss-cn-guangzhou.aliyuncs.com/site/team/cunzhi-liu.jpg', 3, '0', '0', 'migration', current_timestamp),

('board', '闫世艳', 'Shiyan Yan', 'Prof.',
 '研究员、博士生导师', 'Researcher and doctoral supervisor',
 '北京中医药大学', 'Beijing University of Chinese Medicine',
 '试验设计与统计核查', 'Trial design & statistical verification',
 '针刺临床疗效评价、创新试验设计、统计方法学、报告规范研制', 'Clinical efficacy evaluation; Innovative trial design; Statistical methodology; Reporting-standard development',
 '斯坦福大学数据科学访问学者，主持国家级课题 11 项，发表学术论文 160 余篇，是针刺方法学研究的学术骨干。',
 'Visiting scholar in data science at Stanford University; has led 11 national-level projects and published 160+ academic papers as an academic backbone of acupuncture methodology research.',
 'Shiyan Yan 教授系北京中医药大学研究员、博士生导师，斯坦福大学数据科学访问学者，是针刺方法学研究的学术骨干。其核心研究方向为针刺临床疗效评价、创新试验设计、统计方法学以及针刺研究报告规范的研制。已主持国家级课题 11 项，发表学术论文 160 余篇，并担任多家权威针灸期刊编委。',
 'Prof. Shiyan Yan is a researcher and doctoral supervisor at Beijing University of Chinese Medicine, a visiting scholar in data science at Stanford University, and an academic backbone of acupuncture methodology research. Her core research focuses on acupuncture clinical efficacy evaluation, innovative trial design, statistical methodologies and the development of acupuncture research reporting standards. She has presided over 11 national-level projects, published more than 160 academic papers and acts as an editorial board member for multiple authoritative acupuncture journals.',
 '她为 ACTION 智能平台贡献临床统计核查与试验设计规范方面的专业能力，赋能平台的报告质量自动核查工具与针刺临床研究标准化写作模板。',
 'For the ACTION intelligent platform, she contributes professional expertise in clinical statistical verification and trial design norms, empowering the platform''s automatic reporting quality checking tools and standardized writing templates for acupuncture clinical studies.',
 'https://action-gmu.oss-cn-guangzhou.aliyuncs.com/site/team/shiyan-yan.jpg', 4, '0', '0', 'migration', current_timestamp),

('board', '卢立明', 'Liming Lu', 'Prof.',
 '针灸大数据实验室负责人', 'Head, Acupuncture Big Data Lab',
 '广州中医药大学', 'Guangzhou University of Chinese Medicine',
 '报告规范与工具转化', 'Reporting standards & tool translation',
 '针刺方法学、证据图谱、报告规范研制', 'Acupuncture methodology; Evidence mapping; Reporting-guideline development',
 '国际知名针刺方法学家，主持研制全球首个针灸临床实践指南报告规范 RIGHT for Acupuncture，入选斯坦福「全球前 2% 顶尖科学家」榜单。',
 'Internationally acclaimed acupuncture methodologist who developed RIGHT for Acupuncture, the world''s first reporting guideline for acupuncture clinical practice guidelines; listed among Stanford''s World''s Top 2% Scientists.',
 'Liming Lu 教授现任广州中医药大学针灸大数据实验室负责人，是国际知名的针刺方法学家。他主持研制了全球首个针灸临床实践指南报告规范 RIGHT for Acupuncture，该规范构成 ACTION 的核心规范基础。他入选斯坦福大学「全球前 2% 顶尖科学家」榜单，发表同行评议成果 300 余篇，其中包括被《时代》周刊报道的针灸证据图谱这一标志性成果。',
 'Prof. Liming Lu heads the Acupuncture Big Data Lab at Guangzhou University of Chinese Medicine and is an internationally acclaimed acupuncture methodologist. He developed RIGHT for Acupuncture, the world''s first reporting guideline for acupuncture clinical practice guidelines, which forms the core normative foundation of ACTION. Listed in Stanford''s World''s Top 2% Scientists, he has released over 300 peer-reviewed works, including a landmark acupuncture evidence map covered by TIME Magazine.',
 '他为 ACTION 的智能写作模板、报告质量自动核查工具，以及研究规范向临床日常与期刊编辑实践的转化提供核心专业支持。',
 'He contributes core expertise to ACTION''s intelligent writing templates, automatic reporting quality inspection tools and the translation of research standards into routine clinical and journal editorial practice.',
 'https://action-gmu.oss-cn-guangzhou.aliyuncs.com/site/team/liming-lu.jpg', 5, '0', '0', 'migration', current_timestamp),

('board', '于林', 'Lin Yu', 'Prof.',
 '院长、教授、博士生导师', 'President, professor and doctoral supervisor',
 '广州医科大学附属中医医院（广州市针灸医院）', 'The Affiliated Hospital of Traditional Chinese Medicine of Guangzhou Medical University (Guangzhou Hospital of Acupuncture)',
 '基层转化与临床适用性', 'Grassroots translation & clinical applicability',
 '中西医结合精神障碍诊治、针灸技术基层推广与转化应用', 'Integrated Chinese-Western treatment of mental disorders; Grassroots promotion and translation of acupuncture',
 '广州市针灸临床医学研究所所长，中西医结合治疗精神障碍领域的学科带头人，长期推动针灸技术的基层推广与转化应用。',
 'Director of the Guangzhou Institute of Acupuncture Clinical Medicine and a leading expert in the integrated Chinese-Western treatment of mental disorders, with long-standing work on grassroots promotion and translational application of acupuncture technology.',
 'Lin Yu 教授现任广州医科大学附属中医医院（广州市针灸医院）院长，教授、博士生导师，兼任广州市针灸临床医学研究所所长。他是中西医结合治疗精神障碍领域的学科带头人，长期推动针灸技术的基层推广与转化应用。',
 'Prof. Lin Yu is the President of the Affiliated Hospital of Traditional Chinese Medicine of Guangzhou Medical University (Guangzhou Hospital of Acupuncture), professor and doctoral supervisor, and director of the Guangzhou Institute of Acupuncture Clinical Medicine. He is a leading expert in the integrated Chinese-Western medicine treatment of mental disorders, and has long promoted the grassroots promotion and translational application of acupuncture technology.',
 '他在针刺报告规范的真实世界适用性与基层转化价值方面，为 ACTION 提供临床实践层面的指导。',
 'He provides clinical practice guidance for ACTION on the real-world applicability and grassroots transformation value of acupuncture reporting standards.',
 'https://action-gmu.oss-cn-guangzhou.aliyuncs.com/site/team/lin-yu.jpg', 6, '0', '0', 'migration', current_timestamp),

('board', '陈全福', 'Quanfu Chen', 'Prof.',
 '副院长、主任医师、博士生导师', 'Vice President, chief physician and doctoral supervisor',
 '广州医科大学附属中医医院', 'The Affiliated TCM Hospital of Guangzhou Medical University',
 '针药并用研究规范', 'Standards for acupuncture-herbal research',
 '中西医结合心血管与危重症、针药并用、临床质量管理', 'Integrated cardiovascular and critical care medicine; Acupuncture-herbal combined therapy; Clinical quality management',
 '医学博士、心血管临床 PI，师从国医大师张大宁教授与吴以岭院士，全国中医临床优秀人才，学术特色为针药并用。',
 'MD and cardiovascular clinical PI, mentored by national TCM master Prof. Zhang Daning and Academician Wu Yiling; one of China''s outstanding national clinical TCM talents, with acupuncture-herbal combined therapy as his core academic characteristic.',
 'Quanfu Chen 教授，医学博士，主任医师、博士生导师，现任广州医科大学附属中医医院副院长兼心血管临床 PI。他师从国医大师张大宁教授与吴以岭院士，是全国中医临床优秀人才，并在多个国家级与省级中西医结合专业委员会担任学术领导职务。其研究集中于中西医结合心血管与危重症医学，以针药并用为核心学术特色；同时运用行为心理学与认知神经科学推进临床质量管理。',
 'Prof. Quanfu Chen, MD, chief physician and doctoral supervisor, is Vice President and Cardiovascular Clinical PI at The Affiliated TCM Hospital of Guangzhou Medical University. He received mentorship from national TCM master Prof. Zhang Daning and Academician Wu Yiling, and is one of China''s outstanding national clinical TCM talents. He holds leading academic positions in numerous national and provincial integrated medicine committees. His research concentrates on integrated Chinese-Western cardiovascular and critical care medicine, with core academic characteristics of acupuncture-herbal combined therapy. He also applies behavioral psychology and cognitive neuroscience to advance clinical quality management.',
 '他以务实的临床洞察支持 ACTION，帮助规范真实世界中针药并用研究方案的设计与报告。',
 'He supports ACTION with practical clinical insights for standardizing real-world acupuncture and herbal combined research protocols.',
 'https://action-gmu.oss-cn-guangzhou.aliyuncs.com/site/team/quanfu-chen.jpg', 7, '0', '0', 'migration', current_timestamp);

-- ---------------------------------------------------------------- 核心执行团队

insert into action_team_member (group_key, name_zh, name_en, honorific, title_zh, title_en, affiliation_zh, affiliation_en, role_zh, role_en, expertise_zh, expertise_en, summary_zh, summary_en, bio_zh, bio_en, contribution_zh, contribution_en, avatar_url, sort_num, status, del_flag, create_by, create_time)
values
('core', '段玉婷', 'Yuting Duan', 'Dr.',
 '', '',
 '', '',
 '报告规范研制', 'Reporting-guideline development',
 '循证医学、中医药研究、报告质量与研究透明化', 'Evidence-based medicine; TCM research; Reporting quality and research transparency',
 '曾任职于中国 EQUATOR 中心，主导研制 CARE-acupuncture，并参与研制 RIGHT-acupuncture，两者均已被 EQUATOR 协作网与 RIGHT 官方网站正式收录。',
 'Formerly with the Chinese EQUATOR Centre; led the development of CARE-acupuncture and co-developed RIGHT-acupuncture, both officially listed by the EQUATOR Network and the official RIGHT website.',
 'Yuting Duan 博士专长于循证医学与中医药研究。她曾任职于中国 EQUATOR 中心，在循证研究与临床试验标准化方面积累了丰富经验。其研究聚焦临床研究的报告质量、患者结局、数据共享、研究透明化与可重复性。',
 'Dr. Yuting Duan specializes in evidence-based medicine and traditional Chinese medicine research. She previously worked at the Chinese EQUATOR Centre, where she accumulated extensive experience in evidence-based research and the standardization of clinical trials. Her research focuses on the reporting quality of clinical studies, patient outcomes, data sharing, research transparency, and reproducibility.',
 '她主导研制了 CARE-acupuncture，并参与研制 RIGHT-acupuncture，两项规范均已被 EQUATOR 协作网与 RIGHT 官方网站正式收录。',
 'She led the development of CARE-acupuncture and co-developed RIGHT-acupuncture, both of which have been officially included in the EQUATOR Network and the official RIGHT website.',
 'https://action-gmu.oss-cn-guangzhou.aliyuncs.com/site/team/yuting-duan.jpg', 1, '0', '0', 'migration', current_timestamp),

('core', 'Ye-seul Lee', 'Ye-seul Lee', 'Dr.',
 '研究型医师（MD/KMD、MPH、PhD）', 'Research physician, MD (KMD), MPH, PhD',
 '韩国 Jaseng 医疗财团 · Jaseng 脊椎关节研究所', 'Jaseng Spine and Joint Research Institute, Jaseng Medical Foundation, Republic of Korea',
 '数字化临床分析', 'Digital clinical analytics',
 '数据驱动的传统与整合医学、真实世界证据、预测分析、临床方法学', 'Data-driven traditional and integrative medicine; Real-world evidence; Predictive analytics; Clinical methodology',
 '多家国际期刊副主编与栏目编辑，针灸研究学会（SAR）「AI 与数字健康」特别兴趣组联合主席，三度获 SAR 杰出研究者奖。',
 'Associate editor and section editor for multiple international journals, co-chair of the AI & Digital Health SIG of the Society for Acupuncture Research, and a three-time winner of the SAR Outstanding Researcher Award.',
 'Ye-seul Lee 博士（MD/KMD、MPH、PhD）现任韩国 Jaseng 医疗财团 Jaseng 脊椎关节研究所研究型医师。其研究聚焦数据驱动的传统与整合医学、真实世界证据、预测分析与临床方法学，尤其关注脊柱与肌肉骨骼疾病。她担任多家国际期刊的副主编与栏目编辑，并任针灸研究学会（SAR）「AI 与数字健康」特别兴趣组联合主席。其研究成果发表于《世界卫生组织公报》及循证医学顶级期刊，三度获得 SAR 杰出研究者奖，并主持了一项获 WHO 认可的传统医学创新项目。',
 'Dr. Ye-seul Lee, MD (KMD), MPH, PhD works as a research physician at Jaseng Spine and Joint Research Institute, Jaseng Medical Foundation, Republic of Korea. Her research centers on data-driven traditional and integrative medicine, real-world evidence, predictive analytics and clinical methodology, with a special focus on spinal and musculoskeletal disorders. She serves as associate editor and section editor for multiple international journals, and co-chairs the AI & Digital Health Special Interest Group of the Society for Acupuncture Research. Her studies are published in Bulletin of the World Health Organization and top evidence-based medicine journals. She won the SAR Outstanding Researcher Award three times and led a WHO recognized traditional medicine innovation project.',
 '作为 ACTION 顾问，她在数字化临床分析、AI 辅助针刺研究与真实世界证据标准化方面提供独到的专业支持。',
 'As an ACTION advisor, she offers unique expertise in digital clinical analysis, AI-assisted acupuncture research and real-world evidence standardization.',
 'https://action-gmu.oss-cn-guangzhou.aliyuncs.com/site/team/ye-seul-lee.jpg', 2, '0', '0', 'migration', current_timestamp),

('core', 'Changsop Yang', 'Changsop Yang', 'Dr.',
 '首席研究员、兼职教授', 'Principal Researcher; adjunct professor',
 '韩国韩医学研究院（KIOM）· 又石大学', 'Korea Institute of Oriental Medicine; Woosuk University',
 '试验设计与国际标准化', 'Trial design & international standardisation',
 '临床试验设计、中药新药研发、激光针灸、证据合成、传统医学国际标准化', 'Clinical trial design; Herbal medicine development; Laser acupuncture; Evidence synthesis; International standardisation of traditional medicine',
 '持有韩医师与内科专科医师执照，曾领导韩医学研究院临床研究协调团队，在 Frontiers in Pharmacology、PLOS One 等期刊发表多项高质量试验方案。',
 'Holds full Korean Medicine physician and internal medicine specialist licenses; formerly led KIOM''s Clinical Research Coordinating Team and has published multiple high-quality trial protocols in journals including Frontiers in Pharmacology and PLOS One.',
 'Changsop Yang 博士现任韩国韩医学研究院首席研究员、又石大学兼职教授，持有韩医师执照与内科专科医师执照。其核心研究涵盖临床试验设计、中药新药研发、激光针灸疗法、证据合成以及传统医学的国际标准化。他曾领导该院临床研究协调团队，在 Frontiers in Pharmacology、Frontiers in Medicine、PLOS One 等期刊发表多项高质量试验方案，并参与了全球传统医学结局证据图谱这一标志性项目。',
 'Dr. Changsop Yang is a Principal Researcher at the Korea Institute of Oriental Medicine and an adjunct professor at Woosuk University, holding full Korean Medicine physician and internal medicine specialist licenses. His core research covers clinical trial design, herbal medicine development, laser acupuncture therapy, evidence synthesis and international standardization of traditional medicine. He once led the institute''s Clinical Research Coordinating Team and has published multiple high-quality trial protocols in journals including Frontiers in Pharmacology, Frontiers in Medicine and PLOS One. He also participated in the landmark evidence mapping project for global traditional medicine outcomes.',
 '他为标准化针刺试验设计以及全球传统医学规范框架的建设提供专业的方法学支持。',
 'He delivers professional methodological support for standardized acupuncture trial design and the construction of global traditional medicine normative frameworks.',
 'https://action-gmu.oss-cn-guangzhou.aliyuncs.com/site/team/changsop-yang.jpg', 3, '0', '0', 'migration', current_timestamp),

('core', '石林', 'Lin Shi', 'Dr.',
 '', '',
 '', '',
 '方法学负责人', 'Methodology Lead',
 '实施科学、循证医学、报告规范研制、证据转化', 'Implementation science; Evidence-based medicine; Reporting-guideline development; Evidence translation',
 'ACTION 平台方法学负责人，主持实施科学理论框架的本土化、针刺报告规范体系的建立与平台智能研究工具的学术架构设计。',
 'Methodology Lead of the ACTION platform, overseeing localisation of implementation-science frameworks, the acupuncture reporting-standard system and the academic architecture of the platform''s intelligent research tools.',
 'Lin Shi 博士专长于实施科学与循证医学。作为 ACTION 平台的方法学负责人，他主持实施科学理论框架的本土化、针刺标准化报告体系的建立以及平台智能研究工具的学术架构设计。作为核心研制者，他发起多项针刺专用报告规范，覆盖从方案设计、干预实施到结果记录的针刺试验全生命周期。相关研究发表于 The Lancet Infectious Diseases、BMJ Evidence-Based Medicine 等国际知名期刊。',
 'Dr. Lin Shi specializes in implementation science and evidence-based medicine. Serving as the Methodology Lead of the ACTION platform, he oversees the localization of implementation science theoretical frameworks, the establishment of standardized acupuncture reporting systems, and the academic architecture design of the platform''s intelligent research tools. As a core developer, he has initiated multiple acupuncture-specific reporting guidelines to standardize the full lifecycle of acupuncture trials covering protocol design, intervention delivery and result documentation. He has published multiple studies in world-renowned journals such as The Lancet Infectious Diseases and BMJ Evidence-Based Medicine.',
 '他以实施科学理论为驱动，致力于将高质量临床研究证据转化为真实世界的临床实践，推动证据转化的可持续落地，为 ACTION 平台的学术使命提供坚实支撑。',
 'Driven by implementation science theories, he devotes himself to translating high-quality clinical research evidence into real-world clinical practice and advancing the sustainable implementation of evidence translation, strongly underpinning the academic mission of the ACTION platform.',
 'https://action-gmu.oss-cn-guangzhou.aliyuncs.com/site/team/lin-shi.jpg', 4, '0', '0', 'migration', current_timestamp),

('core', 'Tae-Hun Kim', 'Tae-Hun Kim', 'Prof.',
 '教授、韩医临床试验中心主任', 'Professor and Director, Korean Medicine Clinical Trial Center',
 '庆熙大学韩方医院', 'Kyung Hee University Korean Medicine Hospital',
 '试验方法学与偏倚评估', 'Trial methodology & risk-of-bias assessment',
 '循证韩医学、针刺试验方法学、系统评价、实施科学、临床实践指南', 'Evidence-based Korean medicine; Acupuncture trial methodology; Systematic review; Implementation science; Clinical practice guidelines',
 '长期主持国内外研究项目以提升针刺研究的严谨性与透明度，担任众多国际期刊编委与审稿专家。',
 'Leads national and international research projects to enhance the rigour and transparency of acupuncture studies; serves as editorial board member and peer reviewer for numerous global journals.',
 'Tae-Hun Kim 教授现任庆熙大学韩方医院教授兼韩医临床试验中心主任。其研究聚焦循证韩医学、针刺试验方法学、系统评价、实施科学与临床实践指南制订。他在主持国内外研究项目、提升针刺研究严谨性与透明度方面经验丰富，并担任多家国际期刊的编委与审稿专家。',
 'Prof. Tae-Hun Kim serves as a professor and Director of the Korean Medicine Clinical Trial Center at Kyung Hee University Korean Medicine Hospital. His research centers on evidence-based Korean medicine, acupuncture trial methodology, systematic reviews, implementation science and clinical practice guideline development. He has rich experience leading national and international research projects to enhance the rigor and transparency of acupuncture studies, and acts as an editorial board member and peer reviewer for numerous global journals.',
 '他与亚洲、欧洲与北美的学者广泛合作，为 ACTION 的试验设计、偏倚风险评估与报告规范落地等模块提供权威指导，提升平台在全球针刺临床研究标准化方面的能力。',
 'Collaborating widely with scholars across Asia, Europe and North America, he provides authoritative guidance for ACTION''s modules of trial design, bias risk assessment and reporting standard implementation, boosting the platform''s capacity to standardize global acupuncture clinical research.',
 'https://action-gmu.oss-cn-guangzhou.aliyuncs.com/site/team/tae-hun-kim.jpg', 5, '0', '0', 'migration', current_timestamp),

('core', '聂德慧', 'Dehui Nie', 'Dr.',
 '针灸推拿学博士', 'PhD in Acupuncture and Tuina',
 '广州中医药大学', 'Guangzhou University of Chinese Medicine',
 '试验实施与质量控制', 'Trial conduct & quality control',
 '针刺临床研究、针刺疗效评价、多中心 RCT 质量控制', 'Acupuncture clinical research; Efficacy evaluation; Multicentre RCT quality control',
 '持有医师资格并接受过 GCP 培训，熟悉多中心随机对照试验的设计、实施与质量控制流程。',
 'Holds a physician qualification and Good Clinical Practice training; familiar with the design, conduct and quality-control processes of multicentre randomised controlled trials.',
 'Dehui Nie 博士毕业于广州中医药大学，获针灸推拿学博士学位，主要从事针刺临床研究与针刺疗效评价工作。她持有医师资格并接受过 GCP（药物临床试验质量管理规范）培训，熟悉多中心随机对照试验的设计、实施与质量控制流程。在临床研究中，她具备研究方案设计、随机与盲法实施、针刺干预标准化、病例报告表设计、标准操作规程制订以及临床研究质量控制等方面的经验。',
 'Dr. Dehui Nie graduated from Guangzhou University of Chinese Medicine with a doctoral degree in Acupuncture and Tuina. Her work mainly focuses on acupuncture clinical research and the evaluation of acupuncture efficacy. She holds a physician qualification and has received Good Clinical Practice training, and is familiar with the design, implementation, and quality control processes of multicenter randomized controlled trials. In clinical research, she has experience in study protocol design, randomization and blinding implementation, standardization of acupuncture interventions, case report form design, standard operating procedure development, and clinical research quality control.',
 '她致力于通过标准化的研究设计与严谨的实施过程，提升针刺临床证据的质量。',
 'She is committed to improving the quality of clinical evidence for acupuncture through standardized study design and rigorous implementation.',
 'https://action-gmu.oss-cn-guangzhou.aliyuncs.com/site/team/dehui-nie.jpg', 6, '0', '0', 'migration', current_timestamp),

('core', '陈亮亮', 'Liangliang Chen', 'Dr.',
 '博士，清华大学博士后', 'PhD; postdoctoral training at Tsinghua University',
 '', '',
 '中医药循证评价', 'Evidence-based TCM evaluation',
 '中医药循证临床评价、气候变化相关健康风险的中医药应对', 'Evidence-based clinical evaluation of TCM; TCM-adapted solutions for climate-change-related health risks',
 '中山大学博士、清华大学博士后，以第一或通讯作者在 Science Bulletin（IF=21.5）等高影响力期刊发表论文 11 篇，合著领域专著 2 部。',
 'PhD from Sun Yat-sen University with postdoctoral training at Tsinghua University; 11 first- or corresponding-author papers in high-impact journals including Science Bulletin (IF=21.5) and two co-authored field monographs.',
 'Liangliang Chen 博士毕业于中山大学，并在清华大学完成博士后研究。其研究聚焦中医药的循证临床评价，以及针对气候变化相关健康风险的中医药应对方案研制。',
 'Dr. Liangliang Chen received his Ph.D. from Sun Yat-sen University and completed postdoctoral training at Tsinghua University. His research focuses on evidence-based clinical evaluation of traditional Chinese medicine (TCM) and developing TCM-adapted solutions for climate change-related health risks.',
 '他以第一或通讯作者在 Science Bulletin（IF=21.5）等高影响力期刊发表论文 11 篇，合著领域专著 2 部，主持科研项目，并积极参与国际学术交流、多次受邀作大会口头报告。',
 'He has published 11 papers as first or corresponding author in high-impact journals including Science Bulletin (IF=21.5), co-authored 2 field monographs, led research grants, and actively engages in international academic exchanges with invited oral presentations.',
 'https://action-gmu.oss-cn-guangzhou.aliyuncs.com/site/team/liangliang-chen.jpg', 7, '0', '0', 'migration', current_timestamp);

commit;
