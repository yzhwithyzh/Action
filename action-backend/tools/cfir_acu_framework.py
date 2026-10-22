"""针刺版 CFIR 框架 —— 官网「实施科学」页 CFIR 工具的领域 / 构念 / 子条目 / 参考文献的唯一数据源。

素材：《ACTION网站及其材料/实施科学与针刺研究/针刺CFIR框架+原版CFIR框架(1).docx》表 1「针刺版 CFIR 框架」
（5 个维度，构念下还有二级 ①② 与三级 ①-1 子条目，每条带概念、示例、文献来源）与文末 20 篇参考文献。

- 中文的名称 / 概念 / 示例逐字照录 docx（只去掉「例如：」前缀，多条示例各占一行）；
  英文是对中文的翻译，**待甲方核对**
- `source` 是 docx「来源」栏里的文献角标（如 `Chen et al. [1]`），号码对应 `REFERENCES`；
  「合并原CFIR中A、B构念」这类说明的是与原版 CFIR 的对应关系，进 `origin_*`，不是文献
- docx 的两处笔误照改：「Ec et al.[19]」→ Ee（文献 [19] 第一作者 Ee C）；
  「Cao et al.[12]」原样保留 —— 文献 [12] 是曾雪琴等、Cao 是 [11]，两种改法都说得通，**待甲方核对**
- 构念对齐 docx：补「医院/科室影响力」「评估针刺实施因素」「参与」三条（原库里没有），
  并按 docx 改名（经济花费 → 成本效益、关系与情景适配 → 关系与配合 等）。
  构念的 `code` 与已有的 21 条一一对应，`severity` 与应对策略沿用库里的（`hint_*` 按子条目重写），
  新增的三条另配一条策略（`NEW_STRATEGIES`，按 ERIC 策略名写，同已有策略的写法）

用法（工作目录 action-backend/）：
    python -m tools.cfir_acu_framework        # 写 sql/059-action-cfir-acu-elements-pg.sql
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

OUT_SQL = Path(__file__).resolve().parents[1] / 'sql' / '059-action-cfir-acu-elements-pg.sql'


def el(
    label: str,
    zh: str,
    en: str,
    concept: tuple[str, str] = ('', ''),
    examples: list[tuple[str, str]] | None = None,
    source: str = '',
    origin: tuple[str, str] = ('', ''),
    children: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        'label': label,
        'name_zh': zh,
        'name_en': en,
        'concept_zh': concept[0],
        'concept_en': concept[1],
        'example_zh': '\n'.join(x[0] for x in examples or []),
        'example_en': '\n'.join(x[1] for x in examples or []),
        'source': source,
        'origin_zh': origin[0],
        'origin_en': origin[1],
        'children': children or [],
    }


def con(code: str, zh: str, en: str, hint: tuple[str, str], sort_num: int, **kw: Any) -> dict[str, Any]:
    """构念：字段同子条目，另带 code / hint / sort_num。label 不用（前台按 sort_num 编 A、B…）。"""
    row = el('', zh, en, **kw)
    row.update(code=code, hint_zh=hint[0], hint_en=hint[1], sort_num=sort_num)

    return row


O_MERGE = '合并原CFIR中{}构念', 'Merges original CFIR constructs {}'
O_RENAME = '原CFIR中{}构念名修改', 'Renamed from original CFIR construct {}'


def merged(letters_zh: str, letters_en: str) -> tuple[str, str]:
    return O_MERGE[0].format(letters_zh), O_MERGE[1].format(letters_en)


def renamed(letter: str) -> tuple[str, str]:
    return O_RENAME[0].format(letter), O_RENAME[1].format(letter)


# domain seq -> (name_zh, name_en, intro_zh, intro_en)
DOMAINS: dict[int, tuple[str, str, str, str]] = {
    1: ('针刺疗法', 'Acupuncture Therapy', '针刺疗法的特点对针刺实施的影响因素',
        'How the characteristics of acupuncture itself influence its implementation'),
    2: ('外部因素', 'Outer Setting', '针刺在科室或团队之外的影响因素',
        'Factors outside the department or team that influence acupuncture implementation'),
    3: ('内部因素', 'Inner Setting', '针刺在科室或团队内的影响因素',
        'Factors within the department or team that influence acupuncture implementation'),
    4: ('个人', 'Individuals', '参与针刺实施的个体角色，以及实施者与接受者的特征',
        'The roles involved in acupuncture implementation, and the characteristics of those delivering and receiving it'),
    5: ('实施过程', 'Implementation Process', '针刺在实施过程的影响因素',
        'Factors in the implementation process of acupuncture'),
}


CONSTRUCTS: dict[int, list[dict[str, Any]]] = {
    # ------------------------------------------------------------------ 1 针刺疗法
    1: [
        con('evidence', '证据来源', 'Evidence Source',
            ('影响因子、被引率、团队名誉、证据质量、共识与医案', 'Impact factor, citations, team reputation, evidence quality, consensus & case records'), 0,
            concept=('支持针刺疗法有效性的科学证据的强度、质量及其在学术界的影响力。',
                     'The strength and quality of the scientific evidence supporting the effectiveness of acupuncture, and its influence in the academic community.'),
            examples=[('高质量针刺文献的发表，可以提高针刺的影响力，更多的医生推荐、选择针刺作为治疗方案，从而促进了针刺的实施。',
                       'Publication of high-quality acupuncture studies raises the profile of acupuncture, so that more physicians recommend and choose it as a treatment, which promotes its implementation.')],
            origin=merged('A、B', 'A and B'),
            children=[
                el('①', '影响因子', 'Journal impact factor',
                   ('发表针刺相关研究的学术期刊的影响因子及其在学科领域内的排名分区。',
                    'The impact factor of the journals publishing acupuncture research, and their ranking quartile within the discipline.'),
                   [('影响因子及分区越高的文献，传播率越广，医生阅读后会学习其针刺方案，从而促进了针刺的实施。',
                     'Papers in journals with higher impact factors and quartiles reach a wider readership; physicians who read them adopt their acupuncture protocols, which promotes implementation.')],
                   'Chen et al. [1]'),
                el('②', '被引率', 'Citation rate',
                   ('针刺研究论文被其他学术文献引用的频率。',
                    'How often acupuncture research papers are cited by other academic literature.'),
                   [('被引率越高的文献，传播率越广，医生阅读后会学习其针刺方案，患者了解后会尝试针刺治疗，从而促进了针刺的实施。',
                     'More highly cited papers spread more widely: physicians learn their protocols and patients who hear of them try acupuncture, which promotes implementation.')],
                   'Chen et al. [1]'),
                el('③', '证据提供团队的名誉', 'Reputation of the evidence-producing team',
                   ('开展针刺研究并产生证据的研究团队在学术界的声望、信誉和既往研究质量记录。',
                    'The standing, credibility and track record of research quality of the team that conducts the acupuncture research and produces the evidence.'),
                   [('研究团队的声望越高，所做的研究成果越有说服力，针灸医生可参考其研究内容运用在临床治疗中，从而促进了针刺实施。',
                     "The more reputable the team, the more persuasive its findings; acupuncturists can draw on its research in clinical practice, which promotes implementation.")],
                   'Chen et al. [1]'),
                el('④', '证据质量', 'Quality of evidence',
                   ('支持针刺疗法的研究证据的方法学严谨性和可靠性。',
                    'The methodological rigour and reliability of the research evidence supporting acupuncture.'),
                   [('证据质量越高的文献，越容易被针灸医生所认可，从而促进针刺的实施。',
                     'Higher-quality evidence is more readily accepted by acupuncturists, which promotes implementation.')],
                   'Chen et al. [1]'),
                el('⑤', '专家共识/团体标准', 'Expert consensus / group standards',
                   ('支持针刺疗法的专家共识或团体标准。',
                    'Expert consensus statements or group (association) standards supporting acupuncture.')),
                el('⑥', '名医医案/临床经验', 'Case records & clinical experience of eminent physicians',
                   ('支持针刺疗法的名医医案或临床经验。',
                    'Case records or clinical experience of eminent physicians supporting acupuncture.')),
            ]),
        con('character', '针刺特性', 'Characteristics of Acupuncture',
            ('优势、可调整性、可试用性、复杂性、创新性、组合性', 'Advantages, adaptability, trialability, complexity, innovativeness, combinability'), 1,
            concept=('针刺疗法的特有性质。', 'The distinctive properties of acupuncture as a therapy.'),
            origin=merged('C、D、E、F、G', 'C, D, E, F and G'),
            children=[
                el('①', '优势', 'Relative advantage', children=[
                    el('①-1', '有效性', 'Effectiveness',
                       ('针刺针对优势病种的治疗效果。', 'The therapeutic effect of acupuncture on the conditions it is best suited to.'),
                       [('对于一些针刺优势病种，疗效很好，越来越多这类疾病的患者会选择针刺治疗，从而促进针刺的实施。',
                         'For conditions where acupuncture works well, more and more patients choose it, which promotes implementation.')],
                       'Li et al. [2]; Zhang et al. [3]'),
                    el('①-2', '安全性', 'Safety',
                       ('针刺治疗过程中不良反应的发生频率、严重程度。',
                        'The frequency and severity of adverse reactions during acupuncture treatment.'),
                       [('针刺治疗中出现不良反应（如晕针、气胸等），影响了患者的治疗体验，出现了医患纠纷，从而阻碍了针刺的实施。',
                         'Adverse events during treatment (e.g. needle syncope, pneumothorax) spoil the patient experience and lead to disputes, which hinders implementation.')],
                       'Li et al. [2]'),
                    el('①-3', '便捷性', 'Convenience',
                       ('针刺治疗在实施过程中的方便程度，包括治疗周期的长短、单次治疗所需时间、针具和操作方法的特殊要求等。',
                        'How convenient acupuncture is to deliver, including the length of the treatment course, the time each session takes, and any special requirements for needles and techniques.'),
                       [('针刺的治疗周期较长，与患者的生活安排有冲突，从而阻碍了针刺的实施。',
                         "A long treatment course conflicts with patients' daily schedules, which hinders implementation."),
                        ('针刺器具的便捷，对场所要求不高，操作便捷，提高了针刺的实施效率。',
                         'Needles are portable, the setting requirements are modest and the procedure is simple, which makes implementation more efficient.')],
                       'Tippens et al. [4]'),
                    el('①-4', '可接受度', 'Acceptability',
                       ('患者对针刺治疗的接受意愿，包括每次治疗使用的穴位数量是否适中、针具和针法是否让患者感到舒适、治疗流程是否符合患者预期等。',
                        "Patients' willingness to accept acupuncture, including whether the number of points per session is moderate, whether the needles and techniques feel comfortable, and whether the procedure meets their expectations."),
                       [('患者害怕针具，即使他的疾病通过针刺治疗会有很好的疗效，但仍不愿意尝试针刺，从而阻碍了针刺的实施和推广。',
                         'A patient afraid of needles will not try acupuncture even when it would work well for their condition, which hinders implementation and dissemination.'),
                        ('治疗时穴位数量选取的多少，会影响针刺的实施。',
                         'The number of points used per session affects implementation.')],
                       'Corbett et al. [5]'),
                ]),
                el('②', '可调整性', 'Adaptability',
                   ('为满足临床需求，针刺疗法可被调整、定制或优化。',
                    'Acupuncture can be adjusted, tailored or refined to meet clinical needs.'),
                   [('医生根据患者实际情况调整针刺方案，可以促进针刺的实施。',
                     "Physicians adjusting the protocol to the patient's circumstances promotes implementation.")],
                   children=[
                       el('②-1', '时间', 'Timing',
                          ('包括留针时间、治疗周期的长短、治疗频率的多少等。',
                           'Including needle retention time, length of the treatment course and treatment frequency.'),
                          [('针刺治疗频率的高低，会影响到患者的生活工作，从而影响针刺的实施。',
                            "How often treatment is given affects patients' life and work, and thus implementation.")],
                          'Mao et al. [6]'),
                       el('②-2', '个人', 'Individual',
                          ('即根据患者的年龄、体质、病情严重程度、疼痛耐受度等因素进行个性化定制。',
                           "Personalisation according to the patient's age, constitution, disease severity, pain tolerance and similar factors."),
                          [('根据患者疼痛耐受度调整针刺手法，从而促进针刺的实施。',
                            "Adjusting needling technique to the patient's pain tolerance promotes implementation.")],
                          'Roberts et al. [7]'),
                       el('②-3', '地域', 'Region',
                          ('针刺方案根据不同地域的气候特点、文化习惯等进行调整的能力。',
                           'The capacity to adjust acupuncture protocols to the climate and cultural habits of different regions.'),
                          [('根据当地气候特点调整穴位处方、针刺手法，从而促进针刺的实施。',
                            'Adjusting point prescriptions and techniques to the local climate promotes implementation.')],
                          'Roberts et al. [7]'),
                   ]),
                el('③', '可试用性', 'Trialability',
                   ('允许患者“按次执行、随时停止”的特征。',
                    'The feature that lets patients proceed session by session and stop at any time.'),
                   [('对于初次针刺的患者，可以先尝试几个穴位，如果不能耐受则立刻取针结束，这一特点促进了针刺的实施。',
                     'A first-time patient can try a few points and have the needles removed at once if they cannot tolerate them; this promotes implementation.')],
                   'Roberts et al. [7]'),
                el('④', '复杂性', 'Complexity',
                   ('针刺疗法的操作复杂程度。包括：穴位处方多样、操作步骤和环节较多、治疗周期较长、每次治疗时长等。',
                    'How complex acupuncture is to deliver, including varied point prescriptions, many procedural steps, a long treatment course and the length of each session.'),
                   [('穴位处方的多样性，会影响针刺的实施。',
                     'The variety of point prescriptions affects implementation.')],
                   'Li et al. [2]'),
                el('⑤', '创新性', 'Innovativeness', children=[
                    el('⑤-1', '针具创新', 'Needle innovation',
                       ('新型针具的研发和应用。', 'Development and application of new types of needles.'),
                       [('针刀、刃针等新型针具的应用，会提高针刺的疗效，促进针刺的实施。',
                         'New instruments such as acupotomy and blade needles improve outcomes and promote implementation.')],
                       origin=('原CFIR中G构念的延伸', 'Extension of original CFIR construct G')),
                    el('⑤-2', '针法创新', 'Technique innovation',
                       ('新的针刺操作技术或方法的开发。', 'Development of new needling techniques or methods.'),
                       [('浮针等新型针法的出现，提高针刺的疗效，促进针刺的实施。',
                         'New techniques such as Fu’s subcutaneous needling improve outcomes and promote implementation.')],
                       origin=('原CFIR中G构念的延伸', 'Extension of original CFIR construct G')),
                ]),
                el('⑥', '组合性', 'Combinability',
                   ('针刺疗法与其他治疗方法联合应用的程度。',
                    'The extent to which acupuncture is combined with other treatments.'),
                   [('针刺与其他治疗联合，起到1+1>2的效果，促进针刺的实施。',
                     'Combining acupuncture with other treatments produces a synergistic (1 + 1 > 2) effect and promotes implementation.')],
                   'Zheng et al. [8]'),
            ]),
        con('cost', '成本效益', 'Cost-effectiveness',
            ('器械耗材成本与患者治疗花费', 'Equipment & consumable costs, patient treatment costs'), 2,
            concept=('实施针刺疗法所需的成本效益，包括针具、电针仪、消毒设备等器械耗材的购置和维护成本，以及患者治疗花费。',
                     'The cost-effectiveness of delivering acupuncture, including the purchase and maintenance of needles, electroacupuncture devices, sterilisation equipment and other consumables, and the cost of treatment to patients.'),
            examples=[('针刺相关耗材较为低廉，促进针刺疗法的开展。',
                       'Acupuncture consumables are relatively cheap, which favours its delivery.'),
                      ('患者治疗费用昂贵，不利于针刺的实施。',
                       'High treatment costs for patients hinder implementation.')],
            source='Tippens et al. [4]'),
    ],
    # ------------------------------------------------------------------ 2 外部因素
    2: [
        con('accept', '针刺接受度', 'Acceptance of Acupuncture',
            ('当地非针刺医生与普通百姓对针刺的接受度', 'Acceptance among local non-acupuncture physicians and the public'), 0,
            concept=('当地非针刺医生、普通百姓对针刺的接受度。',
                     'How accepting local non-acupuncture physicians and the general public are of acupuncture.'),
            examples=[('当地西医医生对针刺接受度高，推荐患者针刺治疗，促进了针刺的实施。',
                       'Local Western-medicine physicians who accept acupuncture refer patients to it, which promotes implementation.')],
            source='Zheng et al. [8]'),
        con('localcond', '当地针刺条件', 'Local Conditions for Acupuncture',
            ('当地医疗条件与社会支持', 'Local care conditions & social support'), 1,
            concept=('当地对针刺所能提供的医疗条件、社会支持等。',
                     'The medical conditions and social support available locally for acupuncture.'),
            examples=[('当地中医氛围浓厚，有足够的医疗条件开展针刺治疗，促进了针刺的实施。',
                       'A strong local TCM culture and adequate facilities for acupuncture promote implementation.')],
            source='Tippens et al. [4]'),
        con('collab', '跨学科协作', 'Interdisciplinary Collaboration',
            ('转诊网络、跨学科会诊、学术联盟', 'Referral networks, MDT, academic alliances'), 2,
            concept=('针刺与西医等多学科协作，包括转诊网络、跨学科会诊、学术联盟等。',
                     'Collaboration between acupuncture and Western medicine and other disciplines, including referral networks, interdisciplinary consultation and academic alliances.'),
            examples=[('针灸科与其他科室会诊流程完善，促进了针刺的实施。',
                       'A well-established consultation process between the acupuncture department and other departments promotes implementation.')],
            source='Garland et al. [9]'),
        con('policy', '外部政策与激励措施', 'External Policies & Incentives',
            ('政策法规、专家指南、外部资金', 'Policy, expert guidelines, external funding'), 3,
            concept=('政策法规、专家指南、外部资金（如国家补助、科研补助）等支持针刺的实施和推广。',
                     'Policies and regulations, expert guidelines and external funding (e.g. government subsidies, research grants) that support the implementation and dissemination of acupuncture.'),
            examples=[('国家大力支持中医药发展，促进了针刺的实施。',
                       'Strong national support for Chinese medicine promotes implementation.')],
            origin=merged('E、F', 'E and F')),
        con('pressure', '外部压力', 'External Pressure',
            ('同行压力、绩效压力', 'Peer pressure, performance pressure'), 4,
            concept=('外部压力驱使针刺的实施和/或推广。',
                     'External pressures that drive the implementation and/or dissemination of acupuncture.'),
            origin=('原CFIR中G构念', 'Original CFIR construct G'),
            children=[
                el('①', '同行压力', 'Peer pressure',
                   ('来自同行的模仿或竞争压力，主要包括中医同行和西医同行，他们通常己经存在竞争优势（如疗效）。',
                    'Pressure to imitate or compete with peers — mainly Chinese-medicine and Western-medicine peers, who often already hold a competitive advantage (e.g. efficacy).'),
                   [('中医同行对该疾病治疗疗效更好，患者选择其他治疗方案，阻碍了针刺的实施和推广。',
                     'When TCM peers treat the condition more effectively, patients choose other treatments, which hinders implementation and dissemination.')],
                   'Norheim et al. [10]'),
                el('②', '绩效压力', 'Performance pressure',
                   ('绩效指标驱动针刺的实施和/或推广。',
                    'Performance indicators that drive the implementation and/or dissemination of acupuncture.'),
                   [('医院对针刺开展有绩效考核，从而促进了针刺的实施。',
                     'Hospital performance appraisal of acupuncture services promotes implementation.')],
                   origin=('原CFIR中G构念', 'Original CFIR construct G')),
            ]),
        con('influence', '医院/科室影响力', 'Hospital / Department Reputation',
            ('医院、科室的针刺诊疗水平与影响力', 'Acupuncture expertise and reputation of the hospital or department'), 5,
            concept=('医院/科室的针刺诊疗水平与影响力。',
                     'The level of acupuncture care and the reputation of the hospital or department.'),
            examples=[('患者选择针刺治疗会考量医院、科室整体的针刺诊疗水平。',
                       "Patients weigh the overall acupuncture expertise of the hospital and department when choosing acupuncture.")]),
    ],
    # ------------------------------------------------------------------ 3 内部因素
    3: [
        con('resource', '针刺资源可及性', 'Accessibility of Acupuncture Resources',
            ('资金、场所、材料与设备', 'Funding, space, materials & equipment'), 0,
            concept=('诊室环境、操作设备的配置等可支持针刺的功能表现。',
                     'Clinic environment, equipment and other provisions that support the delivery of acupuncture.'),
            origin=merged('A、J', 'A and J'),
            children=[
                el('①', '资金', 'Funding',
                   ('具备针刺实施和推广的资金。', 'Funding available for implementing and disseminating acupuncture.'),
                   [('科室有足够的资金开展义诊、宣传等工作，促进针刺的实施。',
                     'Enough departmental funding for free clinics and publicity promotes implementation.')],
                   'Cao et al. [12]'),
                el('②', '场所', 'Space',
                   ('具备针刺实施和推广的诊疗场所。', 'Treatment space available for implementing and disseminating acupuncture.'),
                   [('科室能提供环境良好的诊室，促进针刺的实施。',
                     'A department able to provide well-equipped treatment rooms promotes implementation.')],
                   'Wang et al. [13]'),
                el('③', '材料与设备', 'Materials & equipment',
                   ('具备针刺实施和推广的设备配置及安全防护条件。',
                    'Equipment and safety-protection provisions for implementing and disseminating acupuncture.'),
                   [('科室能提供完整的针刺工具，对医务人员有较好的安全防护措施，促进了针刺的实施。',
                     'A full set of acupuncture tools and good safety protection for staff promote implementation.')],
                   'Cao et al. [12]'),
            ]),
        con('fit', '关系与配合', 'Relationships & Coordination',
            ('人际关系、临床工作配合', 'Interpersonal relations, fit with clinical workflow'), 1,
            concept=('科室内部人际关系和谐程度、合作频率，针刺治疗与日常工作流程、患者的生活节奏协调程度。',
                     "How harmonious and collaborative relationships within the department are, and how well acupuncture fits daily workflows and patients' routines."),
            origin=merged('B、F', 'B and F'),
            children=[
                el('①', '人际关系', 'Interpersonal relationships',
                   ('科室内部人际关系的和谐程度、合作频率。',
                    'How harmonious relationships within the department are and how often staff collaborate.'),
                   [('科室内部人际关系和谐，相互合作，有利于针刺的实施。',
                     'Harmonious, cooperative relationships within the department favour implementation.')],
                   'Garland et al. [9]'),
                el('②', '临床工作配合', 'Fit with clinical work',
                   ('科室现有的工作流程、排班节奏、管理制度的平衡程度。',
                    "How well the department's existing workflows, rostering and management rules are balanced."),
                   [('科室对于医生出诊安排的合理程度，是否影响医生的休息时间，从而影响针刺的实施。',
                     "Whether clinic scheduling is reasonable and respects physicians' rest time affects implementation.")],
                   'Harrison et al. [14]'),
            ]),
        con('comm', '沟通交流', 'Communication',
            ('治疗前、中、后的医患沟通', 'Patient–physician communication before, during and after treatment'), 2,
            concept=('针灸医生与患者及家属之间的信息交流的程度，包括治疗前的知情同意与方案解释、治疗中的即时反馈与调整沟通、治疗后的随访与健康指导等全过程。',
                     'The extent of communication between acupuncturists and patients and their families throughout care: informed consent and explanation of the plan before treatment, real-time feedback and adjustment during treatment, and follow-up and health guidance afterwards.'),
            examples=[('医生与患者充分讲述治疗方案，治疗中即时沟通调整，治疗后随访，促进了针刺的实施。',
                       'Physicians fully explaining the plan, adjusting through real-time communication during treatment and following up afterwards promotes implementation.')],
            source='Zanardelli et al. [15]',
            origin=('原CFIR中C构念', 'Original CFIR construct C')),
        con('culture', '专业与组织文化', 'Professional & Organisational Culture',
            ('以患者为中心、从业者福祉与专业成长', 'Patient-centredness, practitioner wellbeing & professional growth'), 3,
            concept=('医院及科室内部所共有的价值观、信念、行为规范及专业认同感。',
                     'The values, beliefs, behavioural norms and professional identity shared within the hospital and department.'),
            origin=renamed('D'),
            children=[
                el('①', '以患者为中心', 'Patient-centredness',
                   ('将“以患者为中心”作为治疗理念。', 'Adopting patient-centredness as the guiding philosophy of treatment.'),
                   [('始终将患者放在首位，尊重患者意愿，从而促进针刺的实施。',
                     "Always putting patients first and respecting their wishes promotes implementation.")],
                   'Li et al. [16]'),
                el('②', '从业者福祉与专业成长文化', 'Culture of practitioner wellbeing & professional growth',
                   ('关注医务人员的职业安全、身心健康。',
                    'Attention to the occupational safety and physical and mental health of medical staff.'),
                   [('定期安排医务人员体检，从而促进了针刺的实施。',
                     'Regular health check-ups for staff promote implementation.')],
                   'Zhang et al. [3]'),
            ]),
        con('knowledge', '针刺知识和信息获取', 'Access to Acupuncture Knowledge & Information',
            ('实施指导与培训', 'Guidance & training for implementation'), 4,
            concept=('开展针刺实施和推广的指导和/或培训。',
                     'Guidance and/or training for implementing and disseminating acupuncture.'),
            examples=[('定期安排科室内的医生外出进修学习，促进了针刺的实施和开展。',
                       'Regularly sending department physicians on external training promotes implementation.')],
            origin=('原CFIR中K构念', 'Original CFIR construct K')),
    ],
    # ------------------------------------------------------------------ 4 个人
    4: [
        con('role', '角色亚领域', 'Roles Subdomain',
            ('政策制定者、管理者、专家、质控、实施小组、协作人员、科普宣传员、患者家属',
             'Policymakers, managers, experts, QC, implementation team, collaborators, educators, patients & families'), 0,
            concept=('记录用于针刺中的个体角色的定位。', 'Identifies the roles individuals play in acupuncture implementation.'),
            children=[
                el('A', '政策制定者', 'Policymakers',
                   ('国家级/省级政策制定者，包括国家中医药管理局局长、卫健委主任等。',
                    'National or provincial policymakers, such as the head of the National Administration of Traditional Chinese Medicine or directors of health commissions.'),
                   origin=renamed('A')),
                el('B', '院级/科级管理者', 'Hospital- / department-level managers',
                   ('在医院或科室层面拥有高级决策权力的个体，包括分管院长、针灸科主任、医务处处长等。',
                    'Individuals with senior decision-making authority at hospital or department level, such as the vice-president in charge, the head of the acupuncture department or the director of medical affairs.'),
                   origin=renamed('B')),
                el('C', '针刺领域专家/学术带头人', 'Acupuncture experts / academic leaders',
                   ('在针刺专业领域内具有较高学术声望和影响力的个体，其观点、态度和行为对同行（尤其是年轻医生）具有非正式的引导作用。',
                    'Individuals with high academic standing and influence in acupuncture, whose views, attitudes and behaviour informally guide peers (especially younger physicians).'),
                   origin=renamed('C')),
                el('D', '针刺质控专员', 'Acupuncture quality-control officers',
                   ('负责监督针刺操作流程的规范性、患者安全及治疗质量的个体，包括院感、医务科职员等。',
                    'Individuals who oversee procedural compliance, patient safety and treatment quality, such as infection-control and medical-affairs staff.'),
                   origin=renamed('E')),
                el('E', '实施小组成员', 'Implementation team members',
                   ('直接参与针刺治疗实施的临床工作人员。', 'Clinical staff directly involved in delivering acupuncture.'),
                   origin=renamed('F'),
                   children=[
                       el('①', '针灸医生', 'Acupuncturists',
                          ('直接执行针刺操作的执业医师，是针刺治疗的核心实施者。',
                           'Licensed physicians who perform the needling; the core deliverers of acupuncture.')),
                       el('②', '辅助人员', 'Support staff',
                          ('协助针灸医生完成治疗的护士、技师等，负责患者接待、体位摆放、针具准备、起针、环境维护等辅助工作。',
                           'Nurses, technicians and others who assist acupuncturists — receiving patients, positioning, preparing needles, removing needles and maintaining the environment.')),
                   ]),
                el('F', '多学科协作人员', 'Multidisciplinary collaborators',
                   ('不直接执行针刺操作，但在针刺实施过程中提供协作支持的临床人员，通过转诊推荐、联合评估、共管患者等方式参与针刺实施。',
                    'Clinicians who do not needle but support implementation through referral, joint assessment and shared patient management.'),
                   origin=renamed('G')),
                el('G', '科普宣传员', 'Health educators / promoters',
                   ('直接或间接向潜在患者群体、社会公众或医务人员推广针刺疗法的个体，旨在提升公众对针刺的认知度与接受度。',
                    'Individuals who directly or indirectly promote acupuncture to potential patients, the public or medical staff, to raise awareness and acceptance.'),
                   origin=renamed('H')),
                el('H', '患者及其家属', 'Patients & their families',
                   ('接受针刺治疗的患者及家属。', 'Patients receiving acupuncture and their families.'),
                   origin=renamed('I')),
            ]),
        con('implementer', '实施者特征', 'Implementer Characteristics',
            ('专业发展需求、能力、实施机会', 'Professional development needs, capability, opportunity'), 1,
            concept=('特征亚领域：实施者的特征。', 'Characteristics subdomain: characteristics of those delivering acupuncture.'),
            children=[
                el('A', '专业发展需求', 'Professional development needs',
                   ('实施者在针刺专业实践中感到的自身不足或发展诉求，并可通过进一步实施针刺来解决。',
                    'Gaps or development goals implementers perceive in their acupuncture practice that can be addressed by delivering more acupuncture.'),
                   [('医生对于新学的针刺手法不够熟练，可以在治疗患者时进行练习精进，从而促进了针刺的实施。',
                     'A physician not yet fluent in a newly learned technique can refine it while treating patients, which promotes implementation.')],
                   origin=renamed('A')),
                el('B', '能力', 'Capability',
                   ('实施者完成针刺操作及相关临床工作所需具备的知识、技能与素养。',
                    'The knowledge, skills and competencies implementers need for needling and related clinical work.'),
                   origin=('原CFIR中B构念名', 'Original CFIR construct B'),
                   children=[
                       el('①', '理论知识', 'Theoretical knowledge',
                          ('实施者完成针刺操作及相关临床工作所需的认知性知识与理论功底。',
                           'The cognitive knowledge and theoretical grounding needed for needling and related clinical work.'),
                          [('医生对中医经典、针灸基础知识的掌握程度，影响了针刺的实施。',
                            "Physicians' command of the TCM classics and acupuncture fundamentals affects implementation.")],
                          'Bao et al. [17]'),
                       el('②', '操作技能', 'Practical skills',
                          ('实施者完成针刺操作所需的实践性技术能力。', 'The hands-on technical ability needed to perform needling.'),
                          [('医生对针刺手法、穴位定位等熟练程度，影响了针刺的实施。',
                            "Physicians' proficiency in needling techniques and point location affects implementation.")],
                          'Zheng et al. [8]'),
                   ]),
                el('C', '实施机会', 'Opportunity',
                   ('实施者完成针刺实施工作所需的外部条件可得性，包括是否有患者来源、是否有时间安排、是否有机会参加培训和科研项目等。',
                    'Availability of the external conditions implementers need, including a patient source, time in the schedule, and chances to join training and research projects.'),
                   [('医生是否有足够的患者来源，会影响到针刺的实施。',
                     'Whether physicians have enough patients affects implementation.')],
                   origin=renamed('C')),
            ]),
        con('recipient', '接受者特征', 'Recipient Characteristics',
            ('健康需求、能力、治疗动力、生活配合', 'Health need, capability, motivation, fit with daily life'), 2,
            concept=('特征亚领域：接受者的特征。', 'Characteristics subdomain: characteristics of those receiving acupuncture.'),
            children=[
                el('A', '健康需求', 'Health needs',
                   ('接受者在身心健康方面存在的不足或困扰，并可通过接受针刺治疗来解决。',
                    "Physical or mental health problems of recipients that acupuncture can address."),
                   [('患者长期饱受疾病的困扰，需要通过针刺治疗，从而促进了针刺的实施。',
                     'Patients long troubled by illness who need acupuncture drive its implementation.')],
                   origin=renamed('A')),
                el('B', '能力', 'Capability',
                   ('接受者理解和配合针刺治疗的能力。', "Recipients' ability to understand and cooperate with acupuncture."),
                   origin=('原CFIR中B构念名', 'Original CFIR construct B'),
                   children=[
                       el('①', '认知理解', 'Understanding',
                          ('接受者理解针刺治疗原理、过程及预期效果的知识基础与认知能力。',
                           'The knowledge and cognitive ability recipients need to understand how acupuncture works, what it involves and what to expect.'),
                          [('患者对针刺治疗原理的理解程度，会影响针刺的实施。',
                            "Patients' understanding of how acupuncture works affects implementation.")],
                          'Schapira et al. [18]'),
                       el('②', '耐受配合', 'Tolerance & cooperation',
                          ('接受者对针刺的耐受程度。', "Recipients' tolerance of needling."),
                          [('患者对针刺的耐受程度，会影响针刺的实施。',
                            "Patients' tolerance of needling affects implementation.")],
                          'Ee et al. [19]'),
                   ]),
                el('C', '治疗动力', 'Motivation for treatment',
                   ('接受者主动寻求、持续参与针刺治疗的内在驱动力。',
                    'The inner drive that leads recipients to seek out and keep up acupuncture treatment.'),
                   [('患者受朋友、病友的影响，接受针刺治疗，从而影响了针刺的实施。',
                     'Patients who take up acupuncture on the advice of friends or fellow patients affect implementation.'),
                    ('患者感受到针刺带来的疗效后，坚持针刺治疗，促进了针刺的实施。',
                     'Patients who feel the benefit and persist with treatment promote implementation.')],
                   origin=renamed('C')),
                el('D', '患者生活配合', 'Fit with patients’ daily life',
                   ('针刺治疗与患者日常生活节奏、学习工作时间安排的匹配程度。',
                    "How well acupuncture fits patients' daily routines and study or work schedules."),
                   [('针刺治疗会占用患者大量工作时间，打乱了生活节奏，影响了针刺的实施。',
                     "Treatment that takes up much of a patient's working time and disrupts their routine affects implementation.")],
                   'Li et al. [2]'),
            ]),
    ],
    # ------------------------------------------------------------------ 5 实施过程
    5: [
        con('team', '组建针刺实施团队', 'Assembling the Implementation Team',
            ('多角色协作团队与职责边界', 'Multi-role team & role boundaries'), 0,
            concept=('为实施针刺而组建的多角色协作团队，团队组建需明确各角色职责边界，建立跨科室沟通机制，确保针刺实施的专业性与协作性。',
                     'A multi-role collaborative team formed to implement acupuncture, with clear role boundaries and cross-department communication mechanisms to keep implementation professional and coordinated.'),
            examples=[('组建多角色针刺团队，明确职责，建立完善的会诊流程，从而促进了针刺的实施。',
                       'Forming a multi-role acupuncture team with clear responsibilities and a sound consultation process promotes implementation.')],
            origin=renamed('A')),
        con('assess', '评估针刺治疗需求', 'Assessing Treatment Needs',
            ('患者需求、医生需求', 'Patient needs, physician needs'), 1,
            concept=('收集与分析针刺实施相关各方（患者和医生）的优先需求、偏好和预期。',
                     'Collecting and analysing the priorities, preferences and expectations of those involved in acupuncture implementation (patients and physicians).'),
            origin=renamed('B'),
            children=[
                el('①', '评估患者需求', 'Assessing patient needs',
                   ('了解患者的症状特点、对针具的恐惧程度、对治疗时间的可及性等。',
                    "Understanding patients' symptoms, fear of needles, availability for treatment and the like."),
                   [('了解患者需求，距离远近，从而影响了针刺的实施。',
                     "Understanding patients' needs, such as how far they live from the clinic, affects implementation.")],
                   'Williams et al. [20]'),
                el('②', '评估医生需求', 'Assessing physician needs',
                   ('了解医生对针刺操作培训的需求、对标准化方案的意见等。',
                    "Understanding physicians' training needs and their views on standardised protocols."),
                   [('了解医生是否有外出进修的需求，精进技术，从而影响针刺的实施。',
                     'Finding out whether physicians want external training to refine their skills affects implementation.')],
                   'Zhang et al. [3]'),
            ]),
        con('factors', '评估针刺实施因素', 'Assessing Implementation Determinants',
            ('识别障碍因素与促进因素', 'Identify barriers & facilitators'), 2,
            concept=('收集信息以识别和评估与针刺实施和推广相关的障碍因素和促进因素。',
                     'Collecting information to identify and assess barriers and facilitators to implementing and disseminating acupuncture.'),
            examples=[('针对影响针刺实施的问题进行收集，定期开会讨论解决，从而影响了针刺的实施。',
                       'Collecting problems that affect implementation and discussing solutions at regular meetings affects implementation.')],
            origin=renamed('C')),
        con('plan', '制定针刺实施方案', 'Developing the Implementation Plan',
            ('职责、步骤、短期目标与成功指标', 'Roles, steps, short-term goals & metrics'), 3,
            concept=('制定明确的针刺实施方案。', 'Developing a clear acupuncture implementation plan.'),
            origin=renamed('D')),
        con('adjust', '动态调整策略', 'Dynamic Strategy Adaptation',
            ('依患者反馈与临床观察调整策略', 'Adapt strategies from feedback & observation'), 4,
            concept=('在针刺实施过程中，根据患者反馈、临床观察及环境变化，主动调整实施策略。',
                     'Proactively adjusting implementation strategies during implementation in response to patient feedback, clinical observation and changes in context.'),
            examples=[('在针刺过程中，对于患者的反馈及时进行调整针刺强度，从而影响了针刺实施。',
                       'Promptly adjusting needling intensity in response to patient feedback during treatment affects implementation.')],
            origin=merged('E、I', 'E and I')),
        con('engage', '参与', 'Engaging',
            ('动员推广者与患者及家属参与', 'Engage promoters, patients & families'), 5,
            concept=('吸引和鼓励各方主体积极加入针刺实施过程。',
                     'Attracting and encouraging all stakeholders to take an active part in implementing acupuncture.'),
            origin=('原CFIR中F构念名', 'Original CFIR construct F'),
            children=[
                el('①', '创新推广者', 'Innovation deliverers / promoters',
                   ('吸引和鼓励非针刺医生推广针刺治疗。', 'Attracting and encouraging non-acupuncture physicians to promote acupuncture.'),
                   origin=('原CFIR中F构念名', 'Original CFIR construct F')),
                el('②', '创新接受者', 'Innovation recipients',
                   ('吸引和鼓励患者及家属参与针刺治疗。', 'Attracting and encouraging patients and their families to take part in acupuncture treatment.'),
                   origin=('原CFIR中F构念名', 'Original CFIR construct F')),
            ]),
        con('feedback', '疗效反馈与评价', 'Outcome Feedback & Evaluation',
            ('疗效反馈、满意度', 'Outcome feedback, satisfaction'), 6,
            concept=('收集和讨论关于针刺治疗效果的定性与定量信息。',
                     'Collecting and discussing qualitative and quantitative information on the outcomes of acupuncture treatment.'),
            origin=renamed('H'),
            children=[
                el('①', '疗效反馈', 'Outcome feedback',
                   ('患者接受针刺治疗后主观/客观疗效反馈，用于判断疗效、指导后续治疗决策。',
                    'Subjective and objective outcome feedback after treatment, used to judge efficacy and guide subsequent treatment decisions.'),
                   [('根据患者当下的反馈，调整治疗方案，从而影响了针刺实施。',
                     "Adjusting the treatment plan to the patient's immediate feedback affects implementation.")],
                   'Zanardelli et al. [15]'),
                el('②', '满意度', 'Satisfaction',
                   ('包括医护服务满意度、医生工作量反馈、医院效益评价三方内容。',
                    'Covers satisfaction with care, feedback on physician workload, and evaluation of hospital benefit.')),
            ]),
    ],
}

# 新增三条构念各配一条策略（已有构念的策略沿用库里的，不动）
# code -> (name_zh, name_en, detail_zh, detail_en, source_zh, source_en)
NEW_STRATEGIES: dict[str, tuple[str, str, str, str, str, str]] = {
    'influence': ('打造特色专科与学术品牌', 'Build a distinctive specialty & academic brand',
                  '依托优势病种建设特色专科，借学术会议与科普传播提升医院/科室针刺诊疗的知名度。',
                  'Build a specialty around conditions acupuncture treats well, and raise its profile through academic meetings and public outreach.',
                  'ERIC·使用大众媒体 / 组建联盟', 'ERIC · Use mass media / Build a coalition'),
    'factors': ('系统识别障碍与促进因素', 'Systematically map barriers & facilitators',
                '用 CFIR 访谈提纲或问卷收集信息，定期开会复盘，按优先级排出待解决的障碍。',
                'Collect information with CFIR-based interview guides or surveys, review at regular meetings and prioritise the barriers to tackle.',
                'ERIC·评估可实施性与障碍 / 组织团队会议', 'ERIC · Assess for readiness & barriers / Conduct team meetings'),
    'engage': ('动员推广者与患者共同参与', 'Mobilise promoters and patients',
               '联络非针刺科室医生作为推广者，开展患者宣教与病友交流，鼓励患者及家属参与治疗决策。',
               'Recruit physicians from other departments as promoters, run patient education and peer exchange, and involve patients and families in treatment decisions.',
               'ERIC·告知意见领袖 / 让患者积极参与', 'ERIC · Inform local opinion leaders / Involve patients'),
}

# docx 文末参考文献，号码即 source 里的角标
REFERENCES: list[str] = [
    '陈少宗, 张擎宇, 李爱华, 等. 针灸的国际传播与针灸的实用价值、科学价值. 医学与哲学, 2024, 45(09): 74-78.',
    'Li H, Doorenbos AZ, Choi H, et al. Administrator, Provider, and Staff Perspectives on Implementing Acupuncture in Medically Underserved Breast Cancer Survivors. Cancer Nurs, Published online April 15, 2025.',
    "Zhang NM, Daly D, Terblanche M, et al. Doctors' and Nurses' Attitudes of Acupuncture and Acupressure use in Perioperative Care: An Australian National Survey. Pain Manag Nurs, 2022, 23(6): 800-810.",
    'Tippens KM, Chao MT, Connelly E, et al. Patient perspectives on care received at community acupuncture clinics: a qualitative thematic analysis. BMC Complement Altern Med, 2013, 13: 293.',
    "Corbett L, Prestwich S. A questionnaire survey to determine patient's knowledge, opinions and experience of acupuncture in an NHS GP practice. Acupunct Med, 2011, 29(4): 315-316.",
    'Mao JJ, Tan T, Li SQ, et al. Attitudes and barriers towards participation in an acupuncture trial among breast cancer patients: a survey study. BMC Complement Altern Med, 2014, 14: 7.',
    'Roberts K, Dowell A, Nie JB. Utilising acupuncture for mental health; a mixed-methods approach to understanding the awareness and experience of general practitioners and acupuncturists. Complement Ther Clin Pract, 2020, 39: 101114.',
    "Zheng Z, Stelmach WS, Ma J, et al. Health professionals' attitudes towards acupuncture/acupressure for post-operative nausea and vomiting: a survey and implications for implementation. Acupunct Med, 2023, 41(1): 16-26.",
    'Garland SN, Trevino K, Liou KT, et al. Multi-stakeholder perspectives on managing insomnia in cancer survivors: recommendations to reduce barriers and translate patient-centered research into practice. J Cancer Surviv, 2021, 15(6): 951-960.',
    'Norheim AJ, Fønnebø V. A survey of acupuncture patients: results from a questionnaire among a random sample in the general population in Norway. Complement Ther Med, 2000, 8(3): 187-192.',
    'Cao X, Liao Y, Wu X, et al. Willingness to use acupuncture: Knowledge, attitudes, beliefs, and practices among allergic rhinitis patients. Medicine (Baltimore), 2023, 102(39): e35297.',
    '曾雪琴, 于伟, 黄宵. 社区居民对中医药适宜技术的利用状况及其影响因素研究. 中国当代医药, 2021, 28(34): 184-187.',
    '王丽雯, 吴碧玉, 陈连珠. 中医医疗技术的感染预防及原因分析. 中国卫生标准管理, 2021, 12(18): 120-123.',
    'Harrison JD, Reddy S, Liu R, Adler SR, et al. Implementing an Inpatient Acupuncture Service for Pain and Symptom Management: Identifying Opportunities and Challenges. J Altern Complement Med, 2019, 25(5): 503-508.',
    "Zanardelli I, Robinson N. Factors that influence patients' decisions to discontinue with an acupuncture service—A qualitative study. Eur J Integr Med, 2019, 25: 92-99.",
    'Li XL, Cao HJ, Zhang YJ, et al. Attitude and willingness of attendance for participating in or completing acupuncture trials: a cross-sectional study. Patient Prefer Adherence, 2018, 13: 53-61.',
    'Bao T, Li Q, DeRito JL, et al. Barriers to Acupuncture Use Among Breast Cancer Survivors: A Cross-Sectional Analysis. Integr Cancer Ther, 2018, 17(3): 854-859.',
    'Schapira MM, Mackenzie ER, Lam R, et al. Breast cancer survivors willingness to participate in an acupuncture clinical trial: a qualitative study. Support Care Cancer, 2014, 22(5): 1207-1215.',
    'Ee C, Singleton AC, de Manincor M, et al. A Qualitative Study Exploring Feasibility and Acceptability of Acupuncture, Yoga, and Mindfulness Meditation for Managing Weight After Breast Cancer. Integr Cancer Ther, 2022, 21: 15347354221099540.',
    "Williams H, Sweet L, Graham K. Acupuncture during pregnancy and the perinatal period: Women's attitudes, beliefs and practices. Women Birth, 2020, 33(3): e286-e294.",
]

# 新增构念的初始严重度（已有的 21 条沿用库里的）
NEW_SEVERITY = {'influence': 'l', 'factors': 'm', 'engage': 'm'}
EXISTING_CODES = {
    'evidence', 'character', 'cost', 'accept', 'localcond', 'collab', 'policy', 'pressure', 'resource', 'fit',
    'comm', 'culture', 'knowledge', 'role', 'implementer', 'recipient', 'team', 'assess', 'plan', 'adjust', 'feedback',
}


def _q(v: str | int | None) -> str:
    if v is None:
        return 'null'
    if isinstance(v, int):
        return str(v)

    return "'" + v.replace("'", "''") + "'"


_TEXT_COLS = ('concept_zh', 'concept_en', 'example_zh', 'example_en', 'origin_zh', 'origin_en', 'source')


def _domain_lines() -> list[str]:
    return [
        f'update action_cfir_domain set name_zh = {_q(zh)}, name_en = {_q(en)}, intro_zh = {_q(iz)}, intro_en = {_q(ie)}, '
        f"update_by = 'cfir_acu', update_time = current_timestamp where seq = {seq};"
        for seq, (zh, en, iz, ie) in DOMAINS.items()
    ]


def _construct_lines() -> list[str]:
    lines = []
    for seq, cons in CONSTRUCTS.items():
        for c in cons:
            sets = ', '.join(
                f'{k} = {_q(c[k])}'
                for k in ('name_zh', 'name_en', 'hint_zh', 'hint_en', *_TEXT_COLS)
            )
            if c['code'] in EXISTING_CODES:
                lines.append(
                    f"update action_cfir_construct set domain_id = (select domain_id from action_cfir_domain where seq = {seq}), "
                    f"{sets}, sort_num = {c['sort_num']} where code = {_q(c['code'])};"
                )
            else:
                cols = ('code', 'name_zh', 'name_en', 'hint_zh', 'hint_en', *_TEXT_COLS)
                vals = ', '.join(_q(c[k]) for k in cols)
                lines.append(
                    f'insert into action_cfir_construct (domain_id, {", ".join(cols)}, severity, sort_num) '
                    f'select (select domain_id from action_cfir_domain where seq = {seq}), {vals}, '
                    f"{_q(NEW_SEVERITY[c['code']])}, {c['sort_num']} "
                    f"where not exists (select 1 from action_cfir_construct where code = {_q(c['code'])});"
                )
                lines.append(f"update action_cfir_construct set {sets}, sort_num = {c['sort_num']} where code = {_q(c['code'])};")

    return lines


def _strategy_lines() -> list[str]:
    lines = []
    for code, (nz, ne, dz, de, sz, se) in NEW_STRATEGIES.items():
        lines.append(
            'insert into action_cfir_strategy (construct_id, name_zh, name_en, detail_zh, detail_en, source_zh, source_en, sort_num) '
            f'select c.construct_id, {_q(nz)}, {_q(ne)}, {_q(dz)}, {_q(de)}, {_q(sz)}, {_q(se)}, 0 '
            f'from action_cfir_construct c where c.code = {_q(code)} '
            'and not exists (select 1 from action_cfir_strategy s where s.construct_id = c.construct_id);'
        )

    return lines


def elements() -> list[dict[str, Any]]:
    """展平成带显式 element_id / parent_id 的行（id 从 1 起连续编，父先于子）。"""
    out: list[dict[str, Any]] = []

    def walk(code: str, items: list[dict[str, Any]], parent: int | None) -> None:
        for sort_num, item in enumerate(items):
            eid = len(out) + 1
            out.append({**item, 'element_id': eid, 'parent_id': parent, 'code': code, 'sort_num': sort_num})
            walk(code, item['children'], eid)

    for cons in CONSTRUCTS.values():
        for c in cons:
            walk(c['code'], c['children'], None)

    return out


def _element_lines() -> list[str]:
    cols = ('label', 'name_zh', 'name_en', *_TEXT_COLS)
    lines = []
    for e in elements():
        vals = ', '.join(_q(e[k]) for k in cols)
        lines.append(
            f'insert into action_cfir_element (element_id, construct_id, parent_id, {", ".join(cols)}, sort_num) '
            f"select {e['element_id']}, construct_id, {_q(e['parent_id'])}, {vals}, {e['sort_num']} "
            f"from action_cfir_construct where code = {_q(e['code'])};"
        )

    return lines


def _reference_lines() -> list[str]:
    return [
        f'insert into action_cfir_reference (ref_no, citation) values ({i}, {_q(c)});'
        for i, c in enumerate(REFERENCES, 1)
    ]


HEADER = """-- ----------------------------
-- 059 · 实施科学 CFIR：按《针刺CFIR框架+原版CFIR框架》补全二、三级子条目与参考文献（PostgreSQL）
--
-- 由 tools/cfir_acu_framework.py 生成，请勿手改 —— 改内容就改那个脚本再重跑。
--
-- 原先每个构念只有一句短释义（如「证据来源：证据数量与质量、团队名誉与影响力」），
-- docx 里构念之下的 ①②… 与 ①-1… 子条目、概念、示例、文献来源都没入库。
--
-- 【加了什么】
--   action_cfir_domain     + intro_zh/en（维度说明，如「针刺疗法的特点对针刺实施的影响因素」）
--   action_cfir_construct  + concept_* / example_* / origin_*（与原版 CFIR 的对应关系）/ source（文献角标）
--   action_cfir_element    新表，构念下的子条目，parent_id 自引用装第三级
--   action_cfir_reference  新表，docx 文末 20 篇参考文献，source 里的 [n] 指向它
-- 【改了什么】构念按 docx 对齐：补「医院/科室影响力」「评估针刺实施因素」「参与」三条（各配一条策略），
--   改名若干（经济花费 → 成本效益 等）。已有构念的 severity 与应对策略不动。
-- 【可反复执行】子条目与参考文献先删后插；构念按 code 更新，新构念 not exists 才插。
-- ----------------------------

begin;

alter table action_cfir_domain add column if not exists intro_zh varchar(300) default '';
alter table action_cfir_domain add column if not exists intro_en varchar(500) default '';
comment on column action_cfir_domain.intro_zh is '维度说明（中文）';
comment on column action_cfir_domain.intro_en is '维度说明（英文）';

alter table action_cfir_construct add column if not exists concept_zh text;
alter table action_cfir_construct add column if not exists concept_en text;
alter table action_cfir_construct add column if not exists example_zh text;
alter table action_cfir_construct add column if not exists example_en text;
alter table action_cfir_construct add column if not exists origin_zh varchar(200) default '';
alter table action_cfir_construct add column if not exists origin_en varchar(300) default '';
alter table action_cfir_construct add column if not exists source varchar(300) default '';
comment on column action_cfir_construct.concept_zh is '概念（中文）';
comment on column action_cfir_construct.concept_en is '概念（英文）';
comment on column action_cfir_construct.example_zh is '示例（中文，一行一条）';
comment on column action_cfir_construct.example_en is '示例（英文，一行一条）';
comment on column action_cfir_construct.origin_zh is '与原版CFIR的对应关系（中文）';
comment on column action_cfir_construct.origin_en is '与原版CFIR的对应关系（英文）';
comment on column action_cfir_construct.source is '文献来源（角标对应 action_cfir_reference.ref_no）';

create table if not exists action_cfir_element (
    element_id   serial primary key,
    construct_id integer not null,
    parent_id    integer,
    label        varchar(16) default '',
    name_zh      varchar(200) not null,
    name_en      varchar(300) default '',
    concept_zh   text,
    concept_en   text,
    example_zh   text,
    example_en   text,
    origin_zh    varchar(200) default '',
    origin_en    varchar(300) default '',
    source       varchar(300) default '',
    sort_num     integer default 0
);
comment on table action_cfir_element is '官网-CFIR构念子条目';
comment on column action_cfir_element.construct_id is '所属构念id';
comment on column action_cfir_element.parent_id is '上级子条目id（空 = 构念下的第一级）';
comment on column action_cfir_element.label is '编号（①、①-1、A …）';
create index if not exists idx_action_cfir_element_construct on action_cfir_element (construct_id);

create table if not exists action_cfir_reference (
    ref_no   integer primary key,
    citation text not null
);
comment on table action_cfir_reference is '官网-CFIR针刺版框架参考文献';

"""

FOOTER = """
select setval(pg_get_serial_sequence('action_cfir_element', 'element_id'), (select max(element_id) from action_cfir_element));
select setval(pg_get_serial_sequence('action_cfir_construct', 'construct_id'), (select max(construct_id) from action_cfir_construct));
select setval(pg_get_serial_sequence('action_cfir_strategy', 'strategy_id'), (select max(strategy_id) from action_cfir_strategy));

commit;

-- 核对：
-- select count(*) from action_cfir_construct;                       -- 24
-- select count(*), count(*) filter (where parent_id is not null) from action_cfir_element;
-- select count(*) from action_cfir_reference;                       -- 20
"""


def main() -> None:
    els = elements()
    body = [
        '-- 维度',
        *_domain_lines(),
        '',
        '-- 构念',
        *_construct_lines(),
        '',
        '-- 新构念的应对策略',
        *_strategy_lines(),
        '',
        f'-- 子条目（{len(els)} 条）',
        'delete from action_cfir_element;',
        *_element_lines(),
        '',
        f'-- 参考文献（{len(REFERENCES)} 篇）',
        'delete from action_cfir_reference;',
        *_reference_lines(),
    ]
    OUT_SQL.write_text(HEADER + '\n'.join(body) + '\n' + FOOTER, encoding='utf-8')
    n_cons = sum(len(v) for v in CONSTRUCTS.values())
    print(f'{n_cons} 个构念 · {len(els)} 个子条目 · {len(REFERENCES)} 篇文献 -> {OUT_SQL.name}')


if __name__ == '__main__':
    main()
