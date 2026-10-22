"""CONSORT-A 2026（针刺随机对照试验报告规范）的 42 条 checklist —— 规范 1「CONSORT for Acupuncture」的唯一数据源。

素材：《ACTION网站及其材料/写作助手/Revised_Manuscript_IMR_101405_BlueMarked1015（clean）.pdf》
（CONSORT-A 2026: An Extended Reporting Guideline for Acupuncture Randomized Controlled Trials）。

- 条目原文取自文末 Table 1「CONSORT-A checklist」（6 个部分、42 条），`content_en` 逐字照录；
  旁边那栏「CONSORT 2025 checklist item」进 `extension_*`（列名「CONSORT 2025 原条目」），
  与 CARE 那份「CARE 原条目」同一用法。CONSORT-A 没改动的 13 条不重复抄一遍，标「未修订」
- 示例取自正文「Explanation and elaboration」，只有改动过的 29 条有示例（其余 13 条原文就没给，
  留空 = 前台显示「暂无示例」）。`example_en` 是文中引用的已发表试验原文（去掉了文献角标），
  `example_zh` 是它的忠实译文 —— **不是模型编的范文**，数字一个没动（同 sql/035 的纪律：
  示例会被研究者照着抄进论文）
- 中文条目是对英文条目的翻译，**待甲方核对**；术语按国内针刺 RCT 的通行说法
- 原先这里是 CONSORT 2017 非药物扩展 44 条 + 非药物摘要表 17 条 + STRICTA 2010 17 条（三张表 78 条），
  CONSORT-A 把三者并成一张表，所以现在只有 part_no = 1

`require_level`：只把条目本身就是「如适用 / 如相关」才需报告的 4 条（12b / 16b / 17b / 23b）置为
条件填写。**不能交给 action-checklist-pg.sql 末尾那段正则回填** —— CONSORT-A 在必填条目里大量用了
「if applicable / as applicable」修饰子句（1a、6、9、12a……），正则会把它们全判成选填。
所以这里写入时 `update_by='consort_a'`，那段回填只碰 update_by 为空 / migration 的行，自然绕开。

用法（工作目录 action-backend/）：
    python -m tools.consort_a_checklist        # 写 sql/055-action-consort-a-checklist-pg.sql
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

GUIDELINE_ID = 1
OUT_SQL = Path(__file__).resolve().parents[1] / 'sql' / '055-action-consort-a-checklist-pg.sql'

PART_ZH = 'CONSORT-A 2026 针刺随机对照试验报告清单'
PART_EN = 'CONSORT-A 2026 Checklist for Acupuncture Randomised Controlled Trials'
EXT_LABEL_ZH = 'CONSORT 2025 原条目'
EXT_LABEL_EN = 'CONSORT 2025 checklist item'
UNCHANGED_ZH = '未修订（同 CONSORT 2025）'
UNCHANGED_EN = 'Unchanged from CONSORT 2025'

# 每条：(条目号, 领域中, 领域英, 条目中, 条目英, CONSORT 2025 原条目中, 原条目英, 示例中, 示例英, require_level)
# 原条目为 None = CONSORT-A 未修订；示例为空串 = 原文未给示例
_T = tuple[str, str, str, str, str, str | None, str | None, str, str, str]

ITEMS: list[_T] = [
    # ---------------------------------------------------------------- I. 标题和摘要
    (
        '1a', '标题和摘要', 'Title and abstract',
        '在标题中表明本研究为针刺临床试验及随机试验；如适用，注明针刺干预的类型（如针刺、电针、经皮穴位电刺激〔TEAS〕、穴位按压）。',
        'Identification of the study as an acupuncture clinical trial and randomised trial in the title. Specify the type of acupuncture intervention (e.g., acupuncture, electroacupuncture, TEAS, acupressure) if applicable.',
        '在标题中表明为随机试验',
        'Identification as a randomised trial',
        '“针刺与帕金森病患者的睡眠质量：一项随机临床试验”',
        '"Acupuncture and Sleep Quality Among Patients With Parkinson Disease: A Randomized Clinical Trial."',
        '0',
    ),
    (
        '1b', '标题和摘要', 'Title and abstract',
        '以结构式摘要（或包含核心信息的非结构式摘要）概述试验设计、方法（如研究场所、受试者、有明确定义的具体针刺类型）、结果和结论。',
        'Structured summary (or unstructured summary with core information) of trial design, methods (e.g., study setting, participants, specific acupuncture types with clear definitions), results, and conclusions.',
        '试验设计、方法、结果和结论的结构式摘要',
        'Structured summary of the trial design, methods, results, and conclusions',
        '“设计：多中心、两组、随机、假针刺对照试验（中国临床试验注册中心：ChiCTR2200058123）。'
        '场所：中国 6 家美沙酮维持治疗（MMT）门诊。'
        '受试者：65 岁及以下、每日到诊且已接受 MMT 至少 6 周的阿片类物质使用障碍成年患者。'
        '干预：针刺或假针刺，每周 3 次，共 8 周。'
        '测量：2 项主要结局为美沙酮剂量较基线减少 20% 及以上的受试者比例，以及阿片类渴求（以 100 mm 视觉模拟量表〔VAS〕较基线的变化衡量）。'
        '结果：118 名合格受试者中，60 名随机分配至针刺组，58 名随机分配至假针刺组……询问受试者所接受的针刺类型时，各组间无明显差异。'
        '局限性：固定的针刺方案限制了个体化，且停止针刺后仅随访 12 周。'
        '结论：8 周针刺在减少美沙酮剂量和降低阿片类渴求方面优于假针刺。”',
        '"Design: Multicenter, 2-group, randomized, sham-controlled trial. (Chinese Clinical Trial Registry: ChiCTR2200058123). '
        'Setting: 6 MMT clinics in China. '
        'Participants: Adults aged 65 years or younger with opioid use disorder who attended clinic daily and had been using MMT for at least 6 weeks. '
        'Intervention: Acupuncture or sham acupuncture 3 times a week for 8 weeks. '
        'Measurements: The 2 primary outcomes were the proportion of participants who achieved a reduction in methadone dose of 20% or more compared with baseline and opioid craving, which was measured by the change from baseline on a 100-mm visual analogue scale (VAS). '
        'Results: Of 118 eligible participants, 60 were randomly assigned to acupuncture and 58 were randomly assigned to sham acupuncture... There were no notable differences between study groups when participants were asked which type of acupuncture they received. '
        'Limitation: Fixed acupuncture protocol limited personalization and only 12 weeks of follow-up after stopping acupuncture. '
        'Conclusion: Eight weeks of acupuncture were superior to sham acupuncture in reducing methadone dose and decreasing opioid craving."',
        '0',
    ),
    # ---------------------------------------------------------------- II. 开放科学
    (
        '2', '开放科学：试验注册', 'Open science: Trial registration',
        '试验注册机构名称、注册号（附网址）及注册日期。',
        'Name of trial registry, identifying number (with URL) and date of registration.',
        None, None, '', '', '0',
    ),
    (
        '3', '开放科学：试验方案与统计分析计划', 'Open science: Protocol and statistical analysis plan',
        '可获取试验方案与统计分析计划的途径；可获取选穴依据及其相关信息的途径。',
        'Where the trial protocol and statistical analysis plan can be accessed. Where the basis for acupoint selection and its related information can be obtained.',
        '可获取试验方案和统计分析计划的途径',
        'Where the trial protocol and statistical analysis plan can be accessed',
        '“依据传统针刺理论及我们既往的研究，针刺干预方案由针刺专家共识制定。”\n\n'
        '“各穴位的描述，包括定位及进针深度，见补充表 1 与补充图 2。”\n\n'
        '“试验方案与统计分析计划已事先发表，见补充材料 1。”',
        '"According to the traditional acupuncture theory and our previous studies, acupuncture interventions were developed by a consensus of acupuncture experts."\n\n'
        '"Descriptions of the acupoints, including their location and the depth of needle insertion, are shown in Supplement Table 1 and Supplement Figure 2."\n\n'
        '"The protocol and statistical analysis plan have been previously published and are provided in Supplement 1."',
        '0',
    ),
    (
        '4', '开放科学：数据共享', 'Open science: Data sharing',
        '可在何处、以何种方式获取去标识化的受试者个体数据（含数据字典）、统计代码及其他材料。',
        'Where and how the individual de-identified participant data (including data dictionary), statistical code and any other materials can be accessed.',
        None, None, '', '', '0',
    ),
    (
        '5a', '开放科学：资助与利益冲突', 'Open science: Funding and conflicts of interest',
        '资助来源及其他支持（如针具、中药的提供），以及资助方在试验设计、实施、分析和报告中的作用。',
        'Sources of funding and other support (e.g., supply of acupuncture needles, Chinese herbal medicine), and role of funders in the design, conduct, analysis and reporting of the trial.',
        '资助来源及其他支持（如药物的提供），以及资助方在试验设计、实施、分析和报告中的作用',
        'Sources of funding and other support (e.g., supply of drugs), and role of funders in the design, conduct, analysis and reporting of the trial',
        '“资助/支持：本研究由 FAPESP 基金（2018/8117469-5）资助 Rodrigues、Sanches 和 Faisal-Cury 博士。\n'
        '资助方/申办方的作用：资助方未参与研究的设计与实施，数据的收集、管理、分析与解释，稿件的撰写、审阅或批准，以及投稿决定。”',
        '"Funding/Support: This study was supported by FAPESP grant 2018/8117469-5 to Drs Rodrigues, Sanches, and Faisal-Cury.\n'
        'Role of the Funder/Sponsor: The funder had no role in the design and conduct of the study; collection, management, analysis, and interpretation of the data; preparation, review, or approval of the manuscript; and decision to submit the manuscript for publication."',
        '0',
    ),
    (
        '5b', '开放科学：资助与利益冲突', 'Open science: Funding and conflicts of interest',
        '稿件作者的经济利益冲突及其他利益冲突。',
        'Financial and other conflicts of interest of the manuscript authors.',
        None, None, '', '', '0',
    ),
    # ---------------------------------------------------------------- III. 引言
    (
        '6', '引言：背景和理由', 'Introduction: Background and rationale',
        '描述目标病症的临床与科学背景，并依据相关理论框架（视情况包括东亚传统医学证候、经络理论或现代针刺机制）阐明采用针刺干预的理由；所用传统医学术语应与世界卫生组织（WHO）国际标准术语一致。',
        'Describe the clinical and scientific background of the target condition, and justify the rationale for acupuncture intervention based on relevant theoretical frameworks (including traditional East Asian medicine patterns, meridian theory, or modern acupuncture mechanisms, as applicable), using traditional medicine terminology consistent with WHO international standard terminologies.',
        '科学背景和理由',
        'Scientific background and rationale',
        '“肠易激综合征（IBS）是一种常见的肠-脑互动异常……现有治疗针对的是 IBS 的症状，而非其潜在的病理生理机制……既往研究提示针刺治疗 IBS 效果可期。已证实参与针刺治疗 IBS 的可能生物学机制主要包括降低内脏高敏感性和调节肠-脑轴……根据传统经络腧穴理论，穴位分为特异性穴位（SA）与非特异性穴位（NSA），选用特异性穴位可获得更好的疗效。”',
        '"Irritable bowel syndrome (IBS) is a common disorder of gut-brain interaction...Available treatments target IBS symptoms rather than underlying pathophysiological mechanisms...A previous study suggested that acupuncture has promising effects on IBS. The possible biological mechanisms that have been proven to be involved in acupuncture for IBS primarily included reducing visceral hypersensitivity and modulating the gut-brain axis...According to traditional meridian and acupoint theories, acupoints were divided into the specific acupoint (SA) and the nonspecific acupoint (NSA), and the selection of specific points can result in greater efficacy."',
        '0',
    ),
    (
        '7', '引言：目的', 'Introduction: Objectives',
        '明确针刺干预所针对的具体疾病、核心目的及安全性目的。',
        'Clarify the specific disease, core objectives, and safety objectives targeted by acupuncture intervention.',
        '与获益和危害相关的具体目的',
        'Specific objectives related to benefits and harms',
        '“我们开展了一项为期 20 周的随机临床试验，评价针刺作为抗心绞痛治疗的辅助疗法用于慢性稳定型心绞痛（CSA）患者的有效性与安全性。此外，我们还考察了针刺病变所属经脉（DAM）上的穴位是否比针刺非病变经脉（NAM）穴位、假针刺（SA）或不针刺（等待名单〔WL〕）更有效。”',
        '"We conducted a 20-week randomized clinical trial to evaluate the efficacy and safety of acupuncture as adjunctive therapy to antianginal therapies for patients with CSA. Furthermore, we investigated whether acupuncture on the acupoints of the disease-affected meridian (DAM) was more efficacious than acupoints on the nonaffected meridian (NAM), SA, or no acupuncture (wait list [WL])."',
        '0',
    ),
    # ---------------------------------------------------------------- IV. 方法
    (
        '8', '方法：患者与公众参与', 'Methods: Patient and public involvement',
        '患者或公众参与试验设计、实施和报告的详细情况。',
        'Details of patient or public involvement in the design, conduct and reporting of the trial.',
        None, None, '', '', '0',
    ),
    (
        '9', '方法：试验设计', 'Methods: Trial design',
        '描述试验设计，包括试验类型（如平行组、交叉设计）、分配比例及框架（如优效性、等效性、非劣效性、探索性）；阐明针刺干预组与对照组的分组逻辑，以及选择和使用假针刺的理由（如适用）；伦理委员会审批及患者知情同意情况（如适用）。',
        'Description of trial design including type of trial (e.g., parallel group, crossover), allocation ratio, and framework (e.g., superiority, equivalence, non-inferiority, exploratory). Clarify the grouping logic of the acupuncture intervention group and control group, as well as the rationale for selection and application of sham acupuncture (if applicable). Ethics Committee and Patient Informed Consent (if applicable).',
        '描述试验设计，包括试验类型（如平行组、交叉设计）、分配比例及框架（如优效性、等效性、非劣效性、探索性）',
        'Description of trial design including type of trial (e.g., parallel group, crossover), allocation ratio, and framework (e.g., superiority, equivalence, non-inferiority, exploratory)',
        '“研究设计与报告遵循欧洲及中国 CSA 患者管理指南的建议。研究方案经成都中医药大学附属医院伦理审查委员会批准并已发表。患者均签署书面知情同意书。/SA 组参照既往研究采用 2 个固定的假穴位。针刺双侧假穴位，留针 30 分钟，但不诱发得气感。”\n\n'
        '“本研究是一项随机、单盲、三臂临床试验，于 2016 年 6 月 5 日至 2018 年 11 月 15 日在中国 7 个中心开展……试验总周期 24 周，包括 4 周基线评估、随机化后 8 周治疗和 12 周随访。随机化前已取得每位患者的书面知情同意。/非穿透性假针刺施于 4 个双侧非穴位点，均位于背部，且与头痛区域分属不同节段。消毒后使用钝头的 Streitberger 安慰针。/伦理批准：本研究经华中科技大学同济医学院临床试验伦理委员会（2016S009）、武汉市第一医院医学伦理委员会（武卫一医院伦审〔2016〕14 号）、湖北省中医院伦理委员会（HBZY2016-C25-01）、襄阳市第一人民医院伦理委员会（YN20171220）、黄石市第二医院伦理委员会（HEYLWJY1701）及湖北中医药大学伦理委员会（〔2018〕IEC No. 2）批准。试验由独立的试验指导委员会及数据监查与伦理委员会监督。所有患者均签署了书面知情同意书。”',
        '"Study design and reporting were in accordance with the recommendations of the European and Chinese guidelines for the management of patients with CSA. The protocol was approved by the ethics review board of the Hospital of Chengdu University of Traditional Chinese Medicine and was published. Patients provided written informed consent./Two fixed sham acupoints were used in the SA group as in a previous study. Acupuncture needles were inserted at bilateral sham points for 30 minutes but without achieving a deqi sensation."\n\n'
        '"This randomised, single blind, three arm clinical trial was conducted in seven centres in China between 5 June 2016 and 15 November 2018...The total trial period was 24 weeks, including four weeks of baseline assessment, eight weeks of treatment after randomisation, and 12 weeks of follow-up. We obtained written informed consent from each patient before randomisation./Non-penetrating sham acupuncture was performed at four bilateral non-acupuncture points, which were all located on the back and in different segments from the headache area. After sterilisation, Streitberger placebo needles with blunt tip were used./Ethical approval: This study was approved by the Clinical Trial Ethics Committee of Tongji Medical College, Huazhong University of Science and Technology (2016S009), the Medical Ethics Committee of Wuhan No.1 Hospital (WuWeiYiYuanLunShen[2016]14), the Ethics Committee of Hubei Province Hospital of Traditional Chinese Medicine (HBZY2016-C25-01), the Ethics Committee of Xiangyang No.1 Hospital (YN20171220), the Ethics Committee of The Second Hospital of Huangshi (HEYLWJY1701), and the Ethics Committee of Hubei University of Chinese Medicine ([2018] IEC No. 2). The trial was overseen by an independent trial steering committee and data monitoring and ethics committee. All patients gave written informed consent."',
        '0',
    ),
    (
        '10', '方法：试验方案变更', 'Methods: Changes to trial protocol',
        '试验开始后与针刺相关的重大变更（如穴位调整、电针参数修改、针刺频次变化），以及任何未预先设定的结局或分析，并说明原因。',
        'Major acupuncture-related changes to the trial after it commenced (such as acupoint adjustments, electroacupuncture parameter modifications, changes in needling frequency), as well as any outcomes or analyses that were not prespecified, with reason.',
        '试验开始后的重要变更，包括任何未预先设定的结局或分析，并说明原因',
        'Important changes to the trial after it commenced including any outcomes or analyses that were not prespecified, with reason',
        '“若患者自觉病情未见好转，则在后续治疗中调整穴位定位及治疗参数。”',
        '"Point location and treatment variables were changed during subsequent treatment sessions if patients felt they were not progressing."',
        '0',
    ),
    (
        '11', '方法：试验场所', 'Methods: Trial setting',
        '开展试验的场所（如社区、医院）和地点（如国家、研究中心），并按当地地区要求说明试验场所提供针刺服务的相关监管合规情况或执业资质。',
        'Settings (e.g., community, hospital) and locations (e.g., countries, sites) where the trial was conducted, with a note on relevant regulatory compliance or practice qualifications for acupuncture service at the trial venues in line with local regional requirements.',
        '开展试验的场所（如社区、医院）和地点（如国家、研究中心）',
        'Settings (e.g., community, hospital) and locations (e.g., countries, sites) where the trial was conducted',
        '“我们从中国 5 个不同地区临床中心的针灸科和心内科门诊及住院部招募 CSA 患者。”',
        '"We recruited patients with CSA from the outpatient and inpatient units of the departments of acupuncture and cardiology at clinical centers in 5 different regions in China."',
        '0',
    ),
    (
        '12a', '方法：合格标准', 'Methods: Eligibility criteria',
        '受试者的合格标准；如适用，应同时包括西医诊断标准与中医证候（证型）辨证标准。',
        'Eligibility criteria for participants, including both biomedical diagnostic criteria and Chinese medicine syndrome (pattern) differentiation criteria if applicable.',
        '受试者的合格标准',
        'Eligibility criteria for participants',
        '“受试者年龄 45～75 岁，首次缺血性脑卒中后被诊断为失语……合格患者定义为失语严重程度为 0～3 级（BDAE）、失语病程 15～90 天者。排除标准为：非脑卒中所致失语……视听障碍，以及妊娠期和哺乳期妇女。”',
        '"Participants aged 45 to 75 years who received a diagnosis of aphasia after their first ischemic stroke...Eligible patients were defined as those with an aphasia severity of 0 to 3 (BDAE) and an aphasia duration ranging from 15 to 90 days. The exclusion criteria were patients with a diagnosis of aphasia not caused by stroke… audiovisual impairments, and pregnant and lactating women."',
        '0',
    ),
    (
        '12b', '方法：合格标准', 'Methods: Eligibility criteria',
        '如适用，说明针灸师的背景（如针刺培训学时、执业年限、教育背景及相关经验）。如采用传统针刺诊断证型，报告保证诊断可靠性与一致性的方法，并说明选穴依据（如辨证选穴或经验选穴）。',
        'If applicable, specify the background of acupuncturists (e.g., acupuncture training hours, practice history, educational background, and relevant experience). If traditional acupuncture diagnostic patterns are used, report the methods used to ensure diagnostic reliability and consistency, and clarify the basis for acupoint selection (e.g., syndrome differentiation or empirical selection).',
        '如适用，研究中心及干预实施者（如外科医生、物理治疗师）的合格标准',
        'If applicable, eligibility criteria for sites and for individuals delivering the interventions (e.g., surgeons, physiotherapists)',
        '“治疗由 6 名具备资质、经医院认证的针灸师实施，平均（范围）从业 10（5～25）年。研究团队成员（包括针灸师）每约 6 个月在 MD Anderson 与复旦之间互访一次，以此进行质量控制。”',
        '"Treatments were given by 6 qualified, hospital-credentialed acupuncturists with a mean (range) of 10 (5-25) years of experience. Quality control was maintained by having members of the study team, including acupuncturists, from MD Anderson visit Fudan, and vice versa, approximately every 6 months during the study period."',
        '1',
    ),
    (
        '13', '方法：干预措施与对照', 'Methods: Intervention and comparator',
        '充分详细地描述干预措施与对照措施以便重复，包括针刺治疗的流派与治疗原则（如穴位名称、符合 ISO 标准的针具规格、进针角度与深度、留针时间、手法刺激强度或电针参数）。对照措施应明确界定（如空白对照、假针刺对照）；如采用假针刺，说明假针的类型及刺入细节（如非穴位、浅刺）。其他合并干预（如艾灸、中药、生活方式建议、常规西医治疗）也应完整报告。',
        'Intervention and comparator with sufficient details to allow replication, including style and principle of acupuncture treatment (e.g., acupoint names, ISO-certified needle specifications, needling angle and depth, needle retention time, manipulation intensity or electroacupuncture parameters). The comparator should be clearly defined (e.g., blank control, sham acupuncture control). If sham acupuncture is used, specify the type of sham needle and penetration details (e.g., non-acupoints, shallow insertion). Other concurrent interventions (e.g., moxibustion, herbal medicine, lifestyle advice, conventional western medicine) should also be reported in full.',
        '充分详细地描述干预措施与对照措施以便重复；如相关，说明可获取描述干预与对照的其他材料（如干预手册）的途径',
        'Intervention and comparator with sufficient details to allow replication. If relevant, where additional materials describing the intervention and comparator (e.g., intervention manual) can be accessed',
        '“针刺干预使用一次性无菌针灸针（0.25 mm × 40 mm 和 0.25 mm × 75 mm；华佗牌）。MA 按标准醒脑开窍针刺方案实施，进针角度、深度、行针方向与频率及留针时间均固定。MA 组患者针刺 8 个固定穴位：内关（PC6，双侧）、水沟（GV26）、三阴交（SP6，双侧）、极泉（HT1，患侧）、尺泽（LU5，患侧）、委中（BL40，患侧）、廉泉（CV23）及廉泉旁（双侧）。针刺刺激时诱发得气感。SA 组在上述穴位水平方向旁开 1 寸（1 寸约 25 mm，定义为患者拇指指间关节的宽度）处选取 8 个假穴位，均为非穴位、非经络位置。SA 的针刺刺激不诱发得气感。”',
        '"Disposable sterile needles (0.25 mm × 40 mm and 0.25 mm × 75 mm; Hwato) were used for the acupuncture intervention. MA was performed following the standard Xing-Nao Kai-Qiao acupuncture protocol, with a settled needling angle, depth, manipulation direction and frequency, and retention time. Patients in the MA group received acupuncture at 8 fixed acupoints: PC6 (bilateral), GV26, SP6 (bilateral), HT1 (affected side), LU5 (affected side), BL40 (affected side), CV23, and beside CV23 (bilateral). The De Qi sensation was induced during acupuncture stimulation. For SA, 8 sham acupoints, including nonacupoint and nonmeridian locations, were selected in a lateral opening of 1 cun (1 cun is approximately 25 mm and is defined as the width of the interphalangeal joint of the patient\'s thumb) in the horizontal direction. Acupuncture stimulation in SA induced no De Qi sensation."',
        '0',
    ),
    (
        '14', '方法：结局指标', 'Methods: Outcomes',
        '预先设定的主要和次要结局指标，包括具体测量变量（如偏头痛天数的差异）、分析指标（如较基线的变化、终末值、至事件发生时间）、可选报告的与辨证（或传统医学证候）相关的症状和体征、汇总方法（如中位数、比例）以及每项结局的时间点。',
        'Pre-specified primary and secondary outcomes, including the specific measurement variable (e.g., the difference in migraine days), analysis metric (e.g., change from baseline, final value, time to event), optional symptoms and signs related to syndrome differentiation (or traditional medicine patterns), method of aggregation (e.g., median, proportion), and time point for each outcome.',
        '预先设定的主要和次要结局指标，包括具体测量变量（如收缩压）、分析指标（如较基线的变化、终末值、至事件发生时间）、汇总方法（如中位数、比例）以及每项结局的时间点',
        'Pre-specified primary and secondary outcomes, including the specific measurement variable (e.g., systolic blood pressure), analysis metric (e.g., change from baseline, final value, time to event), method of aggregation (e.g., median, proportion), and time point for each outcome',
        '“主要结局——我们纳入基线期每周心绞痛发作至少 2 次的 CSA 患者。随机化后第 16 周时，4 组间每 4 周心绞痛发作频率的变化差异有统计学意义。/次要结局——第 8～16 周各时间点，DAM 组的视觉模拟量表平均（SD）评分均显著低于其他各组。采用西雅图心绞痛量表评估心绞痛相关的躯体功能。于入组后第 1 天及治疗 4 周后进行动态心电图（Holter）监测。/所有患者均被要求填写纸质心绞痛日记。每次 4 周随访时，各中心 2 名设盲的评估者提醒患者门诊就诊时携带日记。”',
        '"Primary Outcome-We included patients with CSA who had angina attacks at least twice per week during the baseline period. Changes in the frequency of angina attacks over 4-week periods differed significantly among the 4 groups at 16 weeks after randomization. /Secondary Outcomes-The mean (SD) visual analog scale score was significantly lower in the DAM group than in the others at each time point from weeks 8 to 16. The Seattle Angina Questionnaire was used to assess the physical function of angina. Holter monitoring was recorded on the first day after enrollment and after 4 weeks of treatment./All patients were instructed to complete an angina diary on paper. At each 4-week follow-up, 2 blinded evaluators at each center reminded patients to take the diary to their outpatient visit."',
        '0',
    ),
    (
        '15', '方法：危害', 'Methods: Harms',
        '界定所有不良事件，包括针刺特有的危害（如晕针、血肿、断针、穴位感染），描述评估不良事件与针刺干预因果关系的方法，并说明治疗期间、治疗后及随访期的系统监测方法与记录程序。',
        'Define all adverse events including acupuncture-specific harms (such as syncope during acupuncture, hematoma, broken needle, and acupoint infection), describe the methods used to assess the causal relationship between adverse events and acupuncture intervention, and explain the systematic monitoring methods and recording procedures during treatment, after treatment, and in the follow-up period.',
        '危害的定义与评估方式（如系统性、非系统性收集）',
        'How harms were defined and assessed (e.g., systematically, non-systematically)',
        '“研究期间记录退出原因及针刺相关不良事件（AE），包括出血、皮下出血、血肿、晕厥、剧烈疼痛和局部感染。”\n\n'
        '“针灸师经过培训，以专业方式为受试者治疗，但将交流限制在简短的寒暄和询问不良事件。”',
        '"Reasons for withdrawal and acupuncture-associated adverse events (AEs), including bleeding, subcutaneous hemorrhage, hematoma, fainting, serious pain, and local infection, were recorded during the study."\n\n'
        '"Acupuncturists were trained to treat participants professionally but to minimize interactions to brief social conversation and asking about adverse events."',
        '0',
    ),
    (
        '16a', '方法：样本量', 'Methods: Sample size',
        '样本量的确定方法，包括支持样本量计算的全部假设。',
        'How sample size was determined, including all assumptions supporting the sample size calculation.',
        None, None, '', '', '0',
    ),
    (
        '16b', '方法：样本量', 'Methods: Sample size',
        '如适用，说明任何期中分析及试验中止准则。',
        'Explanation of any interim analyses and stopping guidelines, if applicable.',
        '说明任何期中分析及中止准则',
        'Explanation of any interim analyses and stopping guidelines',
        '“数据与安全监查委员会章程中包含预先设定的中止规则。由于招募缓慢，2015 年 7 月对全部临床结局进行了一次计划外的无效性分析。委员会的意见已提交研究者，并建议继续招募至资助期结束。”',
        '"The data and safety monitoring committee charter included prespecified stopping rules. Because of slow recruitment, an unplanned futility analysis of all clinical outcomes was undertaken in July 2015. Advice from the committee was presented to the study investigators, and a recommendation was made to continue to the end of funding period for recruitment."',
        '1',
    ),
    (
        '17a', '方法：随机化：序列的产生', 'Methods: Randomisation: Sequence generation',
        '由谁产生随机分配序列及所用的方法。',
        'Who generated the random allocation sequence and the method used.',
        None, None, '', '', '0',
    ),
    (
        '17b', '方法：随机化：序列的产生', 'Methods: Randomisation: Sequence generation',
        '如适用，随机化的类型及任何限制的细节（如区组及区组大小）。',
        'Type of randomization and details of any restriction (such as blocking and block size), if applicable.',
        '随机化的类型及任何限制的细节（如分层、区组及区组大小）',
        'Type of randomisation and details of any restriction (e.g., stratification, blocking and block size)',
        '“基线评估后，由一名独立研究者将合格患者按 2:2:1 的比例随机分配接受手针、假针刺或常规治疗。采用 2:2:1 的比例是为了促进招募并提高患者依从性。通过交互式网络应答系统进行中央随机分配，按中心分层，区组大小为 5。”',
        '"After the baseline assessment, an independent investigator randomised eligible patients in a 2:2:1 ratio to receive manual acupuncture, sham acupuncture, or usual care. We used the 2:2:1 ratio to facilitate recruitment and increase patients\' adherence. Treatments were allocated in a centralised manner via an interactive web response system with stratification by centre and a block size of five."',
        '1',
    ),
    (
        '18', '方法：分配隐藏机制', 'Methods: Allocation concealment mechanism',
        '执行随机分配序列的机制（如中央计算机/电话系统；按顺序编号、不透明、密封的容器），并描述在干预分配前为隐藏序列所采取的步骤。',
        'Mechanism used to implement the random allocation sequence (e.g., central computer/telephone; sequentially numbered, opaque, sealed containers), describing any steps taken to conceal the sequence until interventions were assigned.',
        None, None,
        '“研究设计——通过中央计算机系统，将患者随机分配至 TA、SA 或 SCC 3 组之一。各机构分别采用适应性随机化（最小化法）对患者进行随机分配。为保证各因素在各组间均衡分布并在各中心内保持平衡，患者按分期……（左右侧分别计算并在组间平衡，<10、10～<20、20～<26、26～<30、30～<35、35～<40、40～<50、50～<60 或 ≥60 Gy）、诱导治疗（是或否）及同步化疗（是或否）进行分层。”',
        '"Study Design-Using a centralized computer system, patients were randomized to 1 of 3 groups: TA, SA, or SCC. Patients were randomized separately at each institution by adaptive randomization (minimization). To ensure equal distribution of all factors across all groups and balance at each site, patients were stratified by stage of ... (left and right calculated separately and balanced between groups, <10, 10 to <20, 20 to <26, 26 to <30, 30 to <35, 35 to <40, 40 to <50, 50 to <60, or ≥60 Gy), induction therapy (yes or no), and concurrent chemotherapy (yes or no)."',
        '0',
    ),
    (
        '19', '方法：随机化的实施', 'Methods: Implementation',
        '招募受试者的人员和为受试者分配干预的人员能否接触到随机分配序列。',
        'Whether the personnel who enrolled and those who assigned participants to the interventions had access to the random allocation sequence.',
        None, None, '', '', '0',
    ),
    (
        '20a', '方法：盲法', 'Methods: Blinding',
        '干预分配后对谁实施了盲法（如受试者、结局评估者、数据分析者、针灸师）。由于针灸师通常无法在实践中设盲，应详细说明减少实施偏倚的措施，解释对其他角色设盲的可行性，并描述替代的偏倚控制方案。',
        'Who was blinded after assignment to interventions (e.g., participants, outcome assessors, data analysts, acupuncturist). As blinding of acupuncturists is generally not feasible in practice, detail the measures to reduce performance bias, explain the feasibility of blinding for other roles, and describe alternative bias control schemes.',
        '干预分配后对谁实施了盲法（如受试者、医护人员、结局评估者、数据分析者）',
        'Who was blinded after assignment to interventions (e.g., participants, care providers, outcome assessors, data analysts)',
        '“告知患者本研究的目的是检验 2 种不同的针刺方法，但其中 1 种方法可能并不针对其口干症状。这样的措辞既避免了欺骗，又使患者不知道存在假针刺组。”',
        '"Patients were told that the purpose of the study was to test 2 different acupuncture approaches but that 1 approach might not target their dry mouth symptoms. This language was used to avoid deception while maintaining naiveté as to the existence of a sham group."',
        '0',
    ),
    (
        '20b', '方法：盲法', 'Methods: Blinding',
        '如实施了盲法，描述盲法如何实现以及干预措施之间的相似性；报告维持患者盲态所采取的具体措施，而非仅声明盲法维持成功。',
        'If blinded, describe how blinding was achieved and the similarity between interventions; report specific measures implemented to maintain patient blinding, rather than only stating successful maintenance of blinding.',
        '如实施了盲法，盲法如何实现以及干预措施相似性的描述',
        'If blinded, how blinding was achieved and description of the similarity of interventions',
        '“为保证盲法成功，我们招募未接受过针刺的患者，以非穿透针作为对照，并设计相同的操作流程，使手针组与假针刺组尽可能执行相同的仪式性操作……研究结束时，我们请患者猜测针是否刺入了皮肤。令人满意的是，两个治疗组患者正确猜出自身分组的能力无显著差异。盲法成功表明手针与假针刺之间、假针刺与常规治疗之间的差异是可靠的。”',
        '"To ensure successful blinding, we recruited acupuncture naive patients, used non-penetrating needles as the control, and designed the same procedures to perform the same rituals as far as possible in the manual and sham acupuncture groups...At the end of the study, we asked patients to guess whether they thought the needles penetrated the skin. Satisfyingly, we found no significant difference between the two treatment groups in patients\' ability to correctly guess their allocation status. Successful blinding showed the reliability of the difference between manual acupuncture and sham acupuncture, as well as between sham acupuncture and usual care."',
        '0',
    ),
    (
        '21a', '方法：统计方法', 'Methods: Statistical methods',
        '用于比较组间主要和次要结局的统计方法，包括依据数据类型、随访情况、随访时长选择分析方法，以及随访数据的相应分析方法。',
        'Statistical methods used to compare groups for primary and secondary outcomes, including selection of analytic approaches based on data type, follow-up status, follow-up duration and relevant analytic methods for follow-up data.',
        '用于比较组间主要和次要结局（包括危害）的统计方法',
        'Statistical methods used to compare groups for primary and secondary outcomes, including harms',
        '“检验主要终点时，采用协方差分析检验放疗结束后 1 年的组间治疗差异，并控制基线 XQ 评分和研究机构。具有临床意义的 XQ 评分采用 χ² 检验。探索性分析考察了组别与机构的交互作用。采用 SAS 9.4 版（SAS Institute）的 MIXED 过程，以非结构化协方差类型的重复测量混合模型分析 XQ 评分随时间的变化。”',
        '"To test our primary end point, analysis of covariance was applied to test the treatment difference 1 year after the end of radiation therapy, controlling for baseline XQ score and institution. Clinically relevant XQ scores were examined using χ2 tests. Exploratory analyses examined any group by institute interactions. Mixed-model analyses of repeated measures were used to examine changes in XQ scores over time using the MIXED procedure in SAS statistical software version 9.4 (SAS Institute) with the covariance type unstructured."',
        '0',
    ),
    (
        '21b', '方法：统计方法', 'Methods: Statistical methods',
        '界定每项分析纳入的对象（如全部随机化受试者）及其所在组别。',
        'Definition of who is included in each analysis (e.g., all randomised participants), and in which group.',
        None, None, '', '', '0',
    ),
    (
        '21c', '方法：统计方法', 'Methods: Statistical methods',
        '分析中如何处理缺失数据，尤其应考虑因不耐受针刺而脱落者的填补方法。',
        'How missing data were handled in the analysis, with particular consideration for imputation methods for dropouts due to acupuncture intolerance.',
        '分析中如何处理缺失数据',
        'How missing data were handled in the analysis',
        '“尽管我们预估脱落率为 25%，但 12 个月时的实际脱落率较低，为 15%。我们比较了 12 个月评估时有 XQ 结局的 339 例患者与无 XQ 结局的 60 例患者的基线人口学及医学特征。除缺失数据组入组时 IV 期癌症比例较高外，两组在其他变量上均无差异。”',
        '"Although we estimated a 25% dropout rate, our actual dropout rate at 12 months was lower, at 15%. We compared the baseline demographic and medical characteristics of 339 patients with and 60 patients without XQ outcomes at the 12-month assessment. There were no group differences on any variable except that the group with missing data had a greater proportion of stage IV cancer at study entry."',
        '0',
    ),
    (
        '21d', '方法：统计方法', 'Methods: Statistical methods',
        '其他分析（如亚组分析和敏感性分析）的方法，并区分预先设定的分析与事后分析。',
        'Methods for any additional analyses (e.g., subgroup and sensitivity analyses), distinguishing prespecified from post-hoc.',
        None, None, '', '', '0',
    ),
    # ---------------------------------------------------------------- V. 结果
    (
        '22a', '结果：受试者流程（含流程图）', 'Results: Participant flow, including flow diagram',
        '报告每组随机分配、接受预定针刺干预、完成干预及纳入各分析集的受试者人数，并说明排除原因；另报告参与的针灸师人数及每位针灸师治疗的受试者人数。',
        'For each group, report the numbers of participants randomly assigned, receiving intended acupuncture intervention, completing the intervention, and included in each analysis set, with reasons for exclusions. Additionally, report the number of acupuncturists involved and the number of participants treated per acupuncturist.',
        '各组随机分配、接受预定干预及纳入主要结局分析的受试者人数',
        'For each group, the numbers of participants who were randomly assigned, received intended intervention, and were analysed for the primary outcome',
        '“TA 组共 132 例患者，其中复旦 79 例、MD Anderson 53 例；SA 组 134 例，其中复旦 81 例、MD Anderson 53 例；SCC 组 133 例，其中复旦 80 例、MD Anderson 53 例。/患者特征——各组在年龄、性别、疾病分期、平均肿瘤剂量或治疗类型方面均无差异。基线时，各机构间及各组间对针刺改善放射性口干（RIX）症状的预期无差异；同样，对针刺改善口干症状的预期也未随时间变化。基线 XQ 平均（SD）评分在机构之间存在组间差异，但在机构内部无差异。”',
        '"There was a total of 132 patients in the TA group, including 79 patients at Fudan and 53 patients at MD Anderson; 134 patients in the SA group, including 81 patients at Fudan and 53 patients at MD Anderson; and 133 patients in the SCC group, including 80 patients at Fudan and 53 patients at MD Anderson./Patient Characteristics-There were no group differences in age, sex, disease stage, mean tumor dose, or type of treatment. At baseline, there were no differences between institutions or groups in expectations of acupuncture\'s effect on RIX symptoms. Likewise, there were no changes in expectations of acupuncture\'s effect on xerostomia symptoms over time. There were group differences in mean (SD) XQ scores at baseline between institutions but not within institutions."',
        '0',
    ),
    (
        '22b', '结果：受试者流程（含流程图）', 'Results: Participant flow, including flow diagram',
        '各组随机化后的失访和排除情况及原因。',
        'For each group, losses and exclusions after randomisation, together with reasons.',
        None, None, '', '', '0',
    ),
    (
        '23a', '结果：招募', 'Results: Recruitment',
        '界定招募期以及获益和危害结局随访期的日期。',
        'Dates defining the periods of recruitment and follow-up for outcomes of benefits and harms.',
        None, None, '', '', '0',
    ),
    (
        '23b', '结果：招募', 'Results: Recruitment',
        '如相关，说明试验结束或中止的原因。',
        'If relevant, why the trial ended or was stopped.',
        None, None, '', '', '1',
    ),
    (
        '24a', '结果：干预与对照的实施', 'Results: Intervention and comparator delivery',
        '描述针刺干预与对照措施的实际实施情况，包括选穴及操作的一致性、留针时间或电针参数的偏离、患者依从性、实施保真度评估结果以及干预实施人员。',
        'Describe the acupuncture intervention and comparator as actually delivered, including consistency of acupoint selection and application, deviations in needle retention time or electroacupuncture parameters, patient adherence, fidelity assessment results, and the personnel delivering the intervention.',
        '干预措施与对照措施的实际实施情况（如适用，包括由谁实施干预/对照、受试者依从情况、是否按计划实施〔保真度〕）',
        'Intervention and comparator as they were actually administered (e.g., where appropriate, who delivered the intervention/comparator, how participants adhered, whether they were delivered as intended (fidelity))',
        '“筛查的 1651 例患者中，404 例在基线时入组。1 例患者因基线期末误诊而被错误入组，3 例患者基线后从未接受治疗并失去联系，另有 2 例患者在基线期违反临床方案。”',
        '"Among 1651 patients screened, 404 were enrolled at baseline. One patient was erroneously enrolled because of misdiagnosis at the end of the baseline period, 3 patients never received a treatment and lost contact after baseline, and another 2 patients violated the clinical protocol during the baseline period."',
        '0',
    ),
    (
        '24b', '结果：干预与对照的实施', 'Results: Intervention and comparator delivery',
        '各组在试验期间接受的合并治疗，指出任何可能影响针刺效应的合并干预（如药物治疗、物理治疗、运动方案、中药、其他中医外治疗法或其他方案外干预）。',
        'Concomitant care received during the trial for each group, indicating any concomitant interventions that might influence the acupuncture effect (e.g., pharmacological treatments, physical therapy, exercise programs, herbal medicine, other traditional Chinese medicine physical therapies, or other non-protocol interventions).',
        '各组在试验期间接受的合并治疗',
        'Concomitant care received during the trial for each group',
        '“3 组均记录到多种合并治疗，但仅有 55 例患者（TCA 组 10 例〔3.1%〕、假针刺组 11 例〔3.0%〕、保守治疗组 34 例〔10.4%〕）接受了方案禁止的治疗，如局部注射、穴位按压或局部物理治疗。”',
        '"A broad variety of concomitant treatments were documented in all 3 groups, but only 55 patients (10 in the TCA group [3.1%], 11 in the sham acupuncture group [3.0%], and 34 in the conservative therapy group [10.4%]) received treatment prohibited by the protocol, such as local injections, acupressure, or local physical therapy."',
        '0',
    ),
    (
        '25', '结果：基线资料', 'Results: Baseline data',
        '以表格列出各组的基线人口学与临床特征，可作为补充材料提供。',
        'A table showing baseline demographic and clinical characteristics for each group, which may be presented as supplemental material.',
        '以表格列出各组的基线人口学与临床特征',
        'A table showing baseline demographic and clinical characteristics for each group',
        '“表 1. 基线特征”',
        '"Table 1. Baseline characteristics"',
        '0',
    ),
    (
        '26', '结果：纳入分析的例数、结局与估计', 'Results: Numbers analysed, outcomes and estimation',
        '对每项主要和次要结局，按组报告（可作为补充材料提供）：① 纳入分析的受试者人数；② 在该结局时间点有可用数据的受试者人数；③ 各组结果，以及效应量估计值及其精确度（如 95% 置信区间）；④ 对二分类结局，同时给出绝对效应量和相对效应量。',
        'For each primary and secondary outcome, by group (which may be presented as supplemental material): (1) the number of participants included in the analysis; (2) the number of participants with available data at the outcome time point; (3) result for each group, and the estimated effect size and its precision (such as 95% confidence interval); (4) for binary outcomes, presentation of both absolute and relative effect size.',
        '对每项主要和次要结局，按组报告：① 纳入分析的受试者人数；② 在该结局时间点有可用数据的受试者人数；③ 各组结果，以及效应量估计值及其精确度（如 95% 置信区间）；④ 对二分类结局，同时给出绝对效应量和相对效应量',
        'For each primary and secondary outcome, by group: (1) the number of participants included in the analysis; (2) the number of participants with available data at the outcome time point; (3) result for each group, and the estimated effect size and its precision (such as 95% confidence interval); (4) for binary outcomes, presentation of both absolute and relative effect size',
        '“125 例受试者中的 115 例（92.0%）分配至 MA 组，127 例中的 116 例（91.3%）分配至 SA 组。第 6 周时 WAB 的 AQ 平均（SD）评分 MA 组为 69.66（17.32）（基线至第 6 周平均〔SD〕改善 29.60〔14.07〕分），SA 组为 61.68（17.88）。与 SA 组相比，MA 组 AQ 评分显著提高 7.99 分（95% CI，3.42～12.55 分；P < .001）。第 6 周时 CFCP 平均（SD）评分 MA 组为 167.60（45.08）（基线至第 6 周平均〔SD〕改善 72.68〔39.56〕），SA 组为 144.08（50.52）。与 SA 组相比，MA 组显著提高 23.51 分（95% CI，11.10～35.93 分；P < .001）。在 6 个月随访结束时，MA 组的 AQ（差值 10.34；95% CI，5.75～14.93；P < .001）和 CFCP（差值 27.43；95% CI，14.75～40.10；P < .001）评分同样显著改善。”',
        '"A total of 115 of 125 participants (92.0%) were assigned to the MA group, and 116 of 127 participants (91.3%) were assigned to the SA group. The mean (SD) AQ score of the WAB at week 6 was 69.66 (17.32) in the MA group (mean [SD] improvement between baseline and week 6, 29.60 [14.07] points) and 61.68 (17.88) in the SA group. Compared with the SA group, the MA group had a significant 7.99-point increase (95% CI, 3.42 to 12.55 points; P < .001) in the AQ score. The mean (SD) CFCP scores at week 6 were 167.60 (45.08) in the MA group (mean [SD] improvement between baseline and week 6, 72.68 [39.56]) and 144.08 (50.52) in the SA group. Compared with the SA group, the MA group had a significant 23.51-point increase (95% CI, 11.10 to 35.93 points; P < .001). The MA group also showed significant improvements in AQ (difference, 10.34; 95% CI, 5.75-14.93; P < .001) and CFCP (difference, 27.43; 95% CI, 14.75-40.10; P < .001) scores at the end of follow-up at 6 months."',
        '0',
    ),
    (
        '27', '结果：危害', 'Results: Harms',
        '各组所有危害或非预期事件，包括按类型（治疗相关、器械相关、操作者相关）对针刺相关不良事件（如晕针、血肿、断针、艾灸烫伤、遗留针）进行分类和详细报告，并参照标准化指南区分不良事件与预期的轻微操作反应；报告各类不良事件的发生率、严重程度、处理及转归。',
        'All harms or unintended events in each group, including classification and detailed reporting of acupuncture-related adverse events (such as needle syncope, hematoma, broken needle, moxibustion burn, forgotten needles) by type (treatment-related, device-related, practitioner-related), with reference to standardized guidelines for distinguishing adverse events from expected minor procedural reactions; report the incidence, severity, management and prognosis of each type of adverse event.',
        '各组所有危害或非预期事件',
        'All harms or unintended events in each group',
        '“MD Anderson 报告的不良事件均与针刺无关，复旦仅有 1 例不良事件与针刺相关（耳部 1 个针刺部位疼痛）。总体而言，各组之间及各机构之间报告的不良事件无差异：复旦共报告 185 例不良事件，其中 TA 组 33 例、SA 组 27 例、SCC 组 38 例；MD Anderson 共报告 185 例不良事件，其中 TA 组 24 例、SA 组 39 例、SCC 组 24 例。”',
        '"No adverse events reported at MD Anderson were related to acupuncture, and only 1 adverse event reported at Fudan was related to acupuncture (pain from needling at 1 site in the ear). Overall, there were no differences in adverse events reported between groups or institutions, with 185 adverse events reported at Fudan, including 33 in the TA group, 27 in the SA group, and 38 in the SCC group, and 185 adverse events reported at MD Anderson, including 24 in the TA group, 39 in the SA group, and 24 in the SCC group."',
        '0',
    ),
    (
        '28', '结果：辅助分析', 'Results: Ancillary analyses',
        '所做的其他分析，包括亚组分析和敏感性分析，并区分预先设定的分析与事后分析。',
        'Any other analyses performed, including subgroup and sensitivity analyses, distinguishing pre-specified from post-hoc.',
        None, None, '', '', '0',
    ),
    # ---------------------------------------------------------------- VI. 讨论
    (
        '29', '讨论：解释', 'Discussion: Interpretation',
        '对结果的解释应与报告的发现一致，权衡获益与危害，并考虑其他相关证据。在相关且已预先设定的情况下，作者可选择讨论研究发现与传统针刺理论（如整体调节、辨证论治）的关系，但此类讨论不得超出实证数据；结论应与当代循证医学相衔接，并在适当时与传统针刺理论相联系。',
        'Interpret results consistently with the reported findings, balancing benefits and harms and considering other relevant evidence. Where relevant and pre-specified, authors may optionally discuss how findings relate to traditional acupuncture theories (e.g., holistic regulation, syndrome differentiation and treatment), provided such discussions do not extend beyond empirical data; link conclusions to contemporary evidence-based medicine and, where appropriate, traditional acupuncture theory.',
        '与结果相一致的解释，权衡获益与危害，并考虑其他相关证据',
        'Interpretation consistent with results, balancing benefits and harms, and considering other relevant evidence',
        '“亚组分析进一步显示，与无创伤经历者相比，TECAS 对有创伤经历受试者的应答率改善效果更优，而艾司西酞普兰则无此差异。经皮迷走神经与三叉神经刺激可有效减轻创伤后应激障碍（PTSD）患者急性应激诱发的交感神经反应，并改善 PTSD 合并抑郁。TECAS 可能对心理创伤相关抑郁具有特殊的治疗获益。”',
        '"Subgroup analysis further revealed that TECAS produced the superior efficacy in improving the response rate of the participants who had traumatic experience as compared to those without traumatic experience, but escitalopram did not. Transcutaneous vagal and trigeminal nerve stimulations were effective in reducing acute stress-induced sympathetic response in patients with posttraumatic stress disorder (PTSD) and improving PTSD with comorbid depression. TECAS may have particular therapeutic benefits in the treatment of psychological trauma-associated depression."',
        '0',
    ),
    (
        '30', '讨论：局限性', 'Discussion: Limitations',
        '试验的局限性，涉及潜在偏倚来源、不精确性、可推广性、分析的多重性（如相关）；对于采用假针刺对照的试验，还应说明在缺乏临床前验证的情况下，假针刺并非真正的安慰剂，可能导致干预效应被低估。',
        'Trial limitations, addressing sources of potential bias, imprecision, generalisability, multiplicity of analyses (if relevant), and, for trials using sham acupuncture controls, the potential underestimation of intervention effects due to the non-placebo nature of sham acupuncture, in the absence of preclinical validation.',
        '试验的局限性，涉及潜在偏倚来源、不精确性、可推广性，以及（如相关）分析的多重性',
        'Trial limitations, addressing sources of potential bias, imprecision, generalisability, and, if relevant, multiplicity of analyses',
        '“本试验未能招募到大样本的少数种族和族裔群体受试者。但试验从 30 余家诊所招募受试者，是规模最大的针刺研究之一，提高了结果的可推广性。”',
        '"The trial was unable to recruit a large sample of racially and ethnically underserved participants. Yet it recruited participants from more than 30 clinics, representing one of the largest acupuncture studies, increasing generalizability."',
        '0',
    ),
]


def rows() -> list[dict[str, Any]]:
    """归一化成 action_guideline_item 的列（不含 item_id —— 交给序列分配）。"""
    out = []
    for sort_num, (no, dz, de, cz, ce, oz, oe, xz, xe, req) in enumerate(ITEMS):
        out.append({
            'guideline_id': GUIDELINE_ID,
            'part_no': 1,
            'part_zh': PART_ZH,
            'part_en': PART_EN,
            'domain_zh': dz,
            'domain_en': de,
            'item_no_zh': no,
            'item_no_en': no,
            'content_zh': cz,
            'content_en': ce,
            'ext_label_zh': EXT_LABEL_ZH,
            'ext_label_en': EXT_LABEL_EN,
            'extension_zh': oz if oz is not None else UNCHANGED_ZH,
            'extension_en': oe if oe is not None else UNCHANGED_EN,
            'example_zh': xz,
            'example_en': xe,
            'require_level': req,
            'sort_num': sort_num,
        })

    return out


def _q(v: str | int) -> str:
    if isinstance(v, int):
        return str(v)

    return "'" + v.replace("'", "''") + "'"


_COLS = (
    'guideline_id', 'part_no', 'part_zh', 'part_en', 'domain_zh', 'domain_en', 'item_no_zh', 'item_no_en',
    'content_zh', 'content_en', 'ext_label_zh', 'ext_label_en', 'extension_zh', 'extension_en',
    'example_zh', 'example_en', 'require_level', 'sort_num',
)


def insert_lines() -> list[str]:
    """42 条 insert。全量文件与 055 共用这一段，两条路径落库结果逐字一致。"""
    lines = [f'-- CONSORT-A 2026（{len(ITEMS)} 条，由 tools/consort_a_checklist.py 生成）']
    for r in rows():
        vals = ', '.join(_q(r[c]) for c in _COLS)
        lines.append(
            f'insert into action_guideline_item ({", ".join(_COLS)}, status, del_flag, create_by, create_time, '
            f"update_by, update_time) values ({vals}, '0', '0', 'consort_a', current_timestamp, 'consort_a', current_timestamp);"
        )

    return lines


HEADER = """-- ----------------------------
-- 055 · 规范 1「CONSORT for Acupuncture」的 checklist 换成 CONSORT-A 2026（42 条）（PostgreSQL）
--
-- 由 tools/consort_a_checklist.py 生成，请勿手改 —— 改条目文字走后台「规范条目管理」，
-- 要整批重来就改那个脚本再重跑。
--
-- 【换了什么】原先是三张表 78 条：CONSORT 2017 非药物扩展 44 + 非药物摘要表 17 + STRICTA 2010 17。
-- 甲方给的 CONSORT-A 2026 定稿（写作助手/Revised_Manuscript_IMR_101405_BlueMarked1015（clean）.pdf）
-- 把它们并成一张表 42 条（6 部分），对照栏是 CONSORT 2025 原条目；改动过的 29 条带示例。
-- 旧的 78 条**物理删除**。
--
-- 【对已有草稿】条目 id 全换了，旧草稿里按旧 id 存的正文不会自动搬到新条目上（两版条目
-- 一一对应不上，强行按编号搬会把内容放进不相干的条目）。正文行原样留在库里不删。
-- 草稿的「纳入的清单表」（parts）旧值是 1,2,3 的子集，一律置回空串 = 全部纳入。
--
-- 【require_level】由脚本按条目显式给出，update_by='consort_a' 让全量文件末尾那段
-- 正则回填绕开这些行（CONSORT-A 的必填条目里大量出现 if applicable，正则会误判成选填）。
--
-- 【可反复执行】先删后插。
-- ----------------------------

begin;

delete from action_guideline_item where guideline_id = 1;

update action_report_draft set parts = '' where guideline_id = 1 and coalesce(parts, '') <> '';

"""

FOOTER = """
commit;

-- 核对：
-- select count(*), count(*) filter (where coalesce(example_en, '') <> '') as with_example,
--        count(*) filter (where require_level = '1') as optional
--   from action_guideline_item where guideline_id = 1 and del_flag = '0';   -- 42 / 29 / 4
"""


def main() -> None:
    assert len(ITEMS) == 42, len(ITEMS)
    OUT_SQL.write_text(HEADER + '\n'.join(insert_lines()) + '\n' + FOOTER, encoding='utf-8')
    with_ex = sum(1 for r in ITEMS if r[8])
    print(f'{len(ITEMS)} 条（含示例 {with_ex} 条）-> {OUT_SQL.name}')


if __name__ == '__main__':
    main()
