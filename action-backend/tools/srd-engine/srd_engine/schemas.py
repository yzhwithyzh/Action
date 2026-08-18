"""引擎全部数据结构.

分三层：
1. ParsedDoc      —— PDF 解析产物（纯代码，无 LLM）
2. ExtractDoc     —— 单篇结构化抽取产物 facet（P1，可缓存）
3. ItemVerdict / AssessmentResult —— 评分与聚合产物（P2 / P3）

关于评分（0.7.0 起对应新版 Excel 表 1 的「评分」四列，0.8.0 起方向翻转）：
每个条目的判定结果是 **0/1/2/3 四档评分**，**分越高越重复**
（3 = 完全相同，0 = 完全不同），另有引擎自己的 `unclear`
（证据不足，不计分也不进分母）。领域与整体的重复百分比一律由分数算，
不再由「dup 条数占比」算 —— 见 `aggregate.py`。

**0.8.0 翻转了分数方向**：Excel 表 1 原表头写的是「完全相同 0 分 … 完全不同 3 分」，
甲方定稿改为「分数即相似度」，故 0.8.0 起 rating 键与分数仍相等，但两端的标签对调。
翻转只动 rating/score 这一层：领域与整体的 `pct`/`level`/`overall_level` 数值**完全不变**
（旧公式 `(满分−得分)/满分` 与新公式 `得分/满分` 在得分取补后恒等），
所以历史结果只需把每条目的 rating 换成 `3−rating`、领域 score_sum 换成 `score_max−score_sum`，
结论不会有任何一格改变。读 0.7.x 的 `result.json` 见下方 `_accept_legacy_rating`。

关于引用字段的约定（重要）：
- `quote`    应为**原文逐字**。0.4.0 起不再回查校验（甲方决定），仅供人工核对。
- `quote_zh` 是 quote 的中文翻译，仅供展示；原文若本就是中文，两者相同。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Presence = Literal['yes', 'no', 'unclear']
Verdict = Literal['dup', 'diff', 'unclear']
Level = Literal['none', 'low', 'mod', 'high']
Confidence = Literal['high', 'medium', 'low']

#: 条目评分 —— 对应 Excel 表 1 的「评分」四列，外加引擎自己的「证据不足」。
#: 刻意用字符串枚举而不是 `int | None`：结构化输出里 nullable 整数在多家厂商上会静默降级，
#: 而单一字符串枚举是所有 json_schema 实现都吃得下的最小公分母。
Rating = Literal['0', '1', '2', '3', 'unclear']

#: 单条目满分。领域满分 = 3 × 条目数（Excel：领域1 /24、领域2 /18、领域3 /42、领域4 /18）。
SCORE_PER_ITEM = 3

#: 评分 → 分数。**rating 键就是分数本身**（0.8.0 翻转的是标签，不是这层映射）。
#: unclear 没有分数，既不进分子也不进分母（见 aggregate.py）。
RATING_SCORE: dict[str, int | None] = {'0': 0, '1': 1, '2': 2, '3': 3, 'unclear': None}

#: 分越高越重复：3 分是「完全相同」这一端，0 分是「完全不同」那一端。
RATING_LABEL_ZH: dict[str, str] = {
    '3': '完全相同',
    '2': '部分相同',
    '1': '部分不同',
    '0': '完全不同',
    'unclear': '证据不足',
}
RATING_LABEL_EN: dict[str, str] = {
    '3': 'identical',
    '2': 'partly the same',
    '1': 'partly different',
    '0': 'completely different',
    'unclear': 'insufficient evidence',
}

#: 评分 → 旧的三态判定。3/2 偏「重复」，1/0 偏「不重复」。
#: 这层映射只为兼容既有的 CSV / 报告 / 前端展示，**不参与百分比计算** ——
#: 百分比一律由分数算（aggregate.py），否则 2 分与 3 分、1 分与 0 分就没区别了。
RATING_VERDICT: dict[str, Verdict] = {
    '3': 'dup', '2': 'dup', '1': 'diff', '0': 'diff', 'unclear': 'unclear',
}

#: 0.7.x → 0.8.0 的分数翻转。**只对 rating 有效，unclear 原样穿过。**
LEGACY_RATING_FLIP: dict[str, str] = {'0': '3', '1': '2', '2': '1', '3': '0', 'unclear': 'unclear'}


def flip_rating(rating: str) -> str:
    """0.7.x 的 rating → 0.8.0 的 rating（`3 − r`，unclear 不动）。

    迁移历史数据与读老 `result.json` 都走这里，别在各处手抄 `3 - int(r)` ——
    抄漏一处的表现是「某条目分数对不上标签」，而这两个值在页面上离得很远，很难对出来。
    """
    return LEGACY_RATING_FLIP.get(rating, 'unclear')


# --------------------------------------------------------------------------- 1. 解析层


class ParsedPage(BaseModel):
    no: int
    text: str


class ParsedSection(BaseModel):
    title: str
    text: str
    page_from: int
    page_to: int


class ParsedDoc(BaseModel):
    """PDF 解析产物。`full_text` 是引用回查的唯一依据。"""

    source: str = ''
    sha256: str = ''
    page_count: int = 0
    pages: list[ParsedPage] = Field(default_factory=list)
    sections: list[ParsedSection] = Field(default_factory=list)

    @property
    def full_text(self) -> str:
        return '\n'.join(p.text for p in self.pages)

    def section_text(self, *keywords: str, fallback_all: bool = True) -> str:
        """按标题关键词取章节正文；命中不到时按需回退全文。"""
        keys = [k.lower() for k in keywords]
        hits = [s for s in self.sections if any(k in s.title.lower() for k in keys)]
        if hits:
            return '\n\n'.join(f'## {s.title}\n{s.text}' for s in hits)
        return self.full_text if fallback_all else ''


# --------------------------------------------------------------------------- 2. 抽取层

# 说明：facet 字段刻意拆成 TextFacet / ListFacet 两个具体类型而不用泛型 Union，
# 因为部分厂商的 json_schema 结构化输出对 anyOf/泛型支持很差，会静默降级或报错。


class TextFacet(BaseModel):
    value: str = Field(default='', description='抽取到的内容；原文未提及则留空')
    quote: str = Field(default='', description='原文逐字引用（保持原语言，不要翻译、不要改写）')
    quote_zh: str = Field(default='', description='上述引用的中文翻译；原文即中文则照抄')
    section: str = Field(default='', description='引用所在章节标题')
    present: Presence = Field(default='unclear', description='yes=明确报告 no=明确说明未做 unclear=未提及/含糊')


class ListFacet(BaseModel):
    value: list[str] = Field(default_factory=list, description='抽取到的条目列表；原文未提及则留空数组')
    quote: str = Field(default='', description='原文逐字引用（保持原语言，不要翻译、不要改写）')
    quote_zh: str = Field(default='', description='上述引用的中文翻译；原文即中文则照抄')
    section: str = Field(default='', description='引用所在章节标题')
    present: Presence = Field(default='unclear', description='yes=明确报告 no=明确说明未做 unclear=未提及/含糊')


class IncludedStudy(BaseModel):
    """纳入研究。`evidence.py` 做跨篇比对时的归一优先级：registry_id > doi > (first_author, year)。"""

    first_author: str = Field(default='', description='第一作者姓氏')
    year: int | None = Field(default=None, description='发表年份')
    registry_id: str = Field(default='', description='试验注册号，如 NCT03123456 / ChiCTR-xxx')
    doi: str = Field(default='', description='DOI')
    label: str = Field(default='', description='原文中的引用标签，如 "Zhang 2019"')


class PooledResult(BaseModel):
    outcome: str = Field(default='', description='结局名称，如 VAS 疼痛评分')
    measure: str = Field(default='', description='效应指标：MD/SMD/RR/OR/HR/RD')
    point: float | None = Field(default=None, description='合并效应点估计')
    ci_low: float | None = None
    ci_high: float | None = None
    k: int | None = Field(default=None, description='纳入该合并的研究数')
    n: int | None = Field(default=None, description='总样本量')
    i2: float | None = Field(default=None, description='I² 百分数，如 62.0')
    model: str = Field(default='', description='fixed / random，若原文说明')


class GradeRating(BaseModel):
    outcome: str = ''
    rating: str = Field(default='', description='high / moderate / low / very low')
    downgrade_reasons: list[str] = Field(default_factory=list)


class TopicFacets(BaseModel):
    """批次 B1：研究主题（服务条目 1a–2f）。"""

    objective: TextFacet = Field(default_factory=TextFacet, description='综述的研究目标')
    research_question: TextFacet = Field(default_factory=TextFacet, description='研究问题（PICO 式表述）')
    decision_need: TextFacet = Field(
        default_factory=TextFacet, description='是否说明本综述回应了何种最新的决策/临床需求'
    )
    population: TextFacet = Field(default_factory=TextFacet, description='纳入人群/患者特征')
    intervention: TextFacet = Field(default_factory=TextFacet, description='干预措施及其剂量参数')
    comparator: TextFacet = Field(default_factory=TextFacet, description='对照措施')
    outcomes: ListFacet = Field(default_factory=ListFacet, description='结局指标列表')
    study_designs: ListFacet = Field(default_factory=ListFacet, description='纳入的研究设计类型，如 RCT')
    scope: TextFacet = Field(default_factory=TextFacet, description='范围限制：地域/年限/语言/医疗场景')


class MethodFacets(BaseModel):
    """批次 B2：研究方法（服务条目 3a–5b）。"""

    databases: ListFacet = Field(default_factory=ListFacet, description='检索的电子数据库')
    extra_sources: ListFacet = Field(
        default_factory=ListFacet, description='其他检索来源：试验注册库/灰色文献/手检/查引/会议摘要'
    )
    search_date_range: TextFacet = Field(default_factory=TextFacet, description='检索时间范围')
    search_structure: TextFacet = Field(
        default_factory=TextFacet, description='检索式结构：概念块数量、是否使用主题词(MeSH)、是否使用研究设计过滤器'
    )
    data_sources: ListFacet = Field(
        default_factory=ListFacet, description='数据来源：已发表全文/试验注册记录/向作者索取/个体患者数据'
    )
    extracted_fields: ListFacet = Field(default_factory=ListFacet, description='提取的数据条目类型')
    effect_measures: ListFacet = Field(default_factory=ListFacet, description='使用的效应指标：MD/SMD/RR/OR/HR/RD')
    data_types: ListFacet = Field(default_factory=ListFacet, description='结局的数据类型：二分类/连续/计数/生存/等级')


class ResultFacets(BaseModel):
    """批次 B3：研究结果（服务条目 6a–8e）。"""

    included_studies: list[IncludedStudy] = Field(default_factory=list, description='全部纳入研究，尽量完整')
    included_count_reported: int | None = Field(default=None, description='原文自述的纳入研究数，用于交叉校验')
    study_char_table_present: TextFacet = Field(
        default_factory=TextFacet, description='是否有纳入研究基本特征汇总表/段落'
    )
    similarity_assessment: TextFacet = Field(
        default_factory=TextFacet, description='是否比较各研究特征以判断可否合并'
    )
    multiplicity_handling: TextFacet = Field(
        default_factory=TextFacet, description='如何处理同一研究的多重性（多臂/多时点/多量表）'
    )
    synthesis_method: TextFacet = Field(
        default_factory=TextFacet, description='数据合成方法：meta 分析/叙述性综合/SWiM/vote counting'
    )
    heterogeneity_methods: ListFacet = Field(
        default_factory=ListFacet, description='异质性处理方法：I²/Q 检验/τ²/预测区间/随机效应'
    )
    subgroups: ListFacet = Field(default_factory=ListFacet, description='亚组分析变量')
    missing_data_handling: TextFacet = Field(default_factory=TextFacet, description='缺失数据处理方式')
    sensitivity_analyses: ListFacet = Field(default_factory=ListFacet, description='敏感性分析策略')
    statistical_model: TextFacet = Field(default_factory=TextFacet, description='统计模型：固定/随机效应及估计方法')
    pooled_results: list[PooledResult] = Field(default_factory=list, description='各结局的合并效应量')
    interpretation: TextFacet = Field(
        default_factory=TextFacet, description='对干预效应方向（有益/无效/有害）与大小的实质性解释'
    )
    applicability: TextFacet = Field(default_factory=TextFacet, description='结果在不同人群/场景的适用性与普适性判断')
    conclusion: TextFacet = Field(default_factory=TextFacet, description='总体结论')
    future_research: TextFacet = Field(default_factory=TextFacet, description='实践建议与未来研究建议')


class QualityFacets(BaseModel):
    """批次 B4：研究质量（服务条目 9–12b）。"""

    coi_disclosure: TextFacet = Field(default_factory=TextFacet, description='本综述作者的利益冲突声明')
    funding: TextFacet = Field(default_factory=TextFacet, description='本综述的资助来源')
    coi_of_included_studies: TextFacet = Field(
        default_factory=TextFacet, description='是否识别并报告纳入研究的利益冲突/其他偏倚来源及其影响判断'
    )
    rob_tool: TextFacet = Field(default_factory=TextFacet, description='偏倚风险评估工具：RoB 2/ROBINS-I/RoB 1/JBI/NOS')
    rob_overall_distribution: TextFacet = Field(
        default_factory=TextFacet, description='纳入研究偏倚风险的总体分布与对证据总体偏倚水平的判断'
    )
    missing_outcome_bias_assessment: TextFacet = Field(
        default_factory=TextFacet, description='对缺失结果导致偏倚（发表偏倚/选择性报告）的评估与结论'
    )
    certainty_method: TextFacet = Field(default_factory=TextFacet, description='证据总结方法：是否使用 GRADE')
    grade_ratings: list[GradeRating] = Field(default_factory=list, description='各关键结局的证据确定性分级')


class ExtractDoc(BaseModel):
    """一篇综述的完整 facet。以 sha256 + prompt_version + model 为 key 缓存。"""

    source: str = ''
    sha256: str = ''
    title: str = ''
    prompt_version: str = ''
    model: str = ''
    topic: TopicFacets = Field(default_factory=TopicFacets)
    method: MethodFacets = Field(default_factory=MethodFacets)
    result: ResultFacets = Field(default_factory=ResultFacets)
    quality: QualityFacets = Field(default_factory=QualityFacets)
    token_in: int = 0
    token_out: int = 0
    notes: list[str] = Field(
        default_factory=list,
        description='抽取阶段的告警（如截断）。随 facet 一起缓存，'
                    '否则缓存命中时审计痕迹会全部消失，同一份报告两次跑出两套痕迹',
    )

    @property
    def failed_batches(self) -> list[str]:
        """最终没抽出来的批次（重试过仍失败或全空）。

        判据就是 `notes` 里 `extract.py` 落下的那句 `抽取批次 X 失败…`。
        「重试一轮」那条不算 —— 它记的是过程，重试成功后不会再有失败行。
        """
        return [
            n.split('抽取批次 ')[1].split(' ')[0]
            for n in self.notes
            if n.startswith('抽取批次 ') and ('失败：' in n or '返回空结果' in n)
        ]

    def get_path(self, path: str) -> object | None:
        """按 "topic.intervention" 这样的点号路径取 facet。"""
        node = self
        for part in path.split('.'):
            node = getattr(node, part, None)
            if node is None:
                return None
        return node


# --------------------------------------------------------------------------- 3. 判定层


class ItemVerdict(BaseModel):
    """单条目判定结果 —— 这就是 LLM 被要求填的结构。"""

    rating: Rating = Field(
        description='评分：3=完全相同 2=部分相同 1=部分不同 0=完全不同 unclear=证据不足无法评分'
    )
    reason_zh: str = Field(description='判定理由（中文，≤200字），必须点明具体的相同点或关键差异点，禁止空泛套话')
    reason_en: str = Field(default='', description='判定理由（英文）')
    cite_a: str = Field(default='', description='综述A的原文逐字引用（保持原语言，不要改写）')
    cite_a_zh: str = Field(default='', description='综述A引用的中文翻译')
    cite_b: str = Field(default='', description='综述B的原文逐字引用（保持原语言，不要改写）')
    cite_b_zh: str = Field(default='', description='综述B引用的中文翻译')
    confidence: Confidence = Field(default='medium', description='本次判定的把握程度')


class VoteRecord(BaseModel):
    """一次判定调用的留痕，供审计。"""

    role: str = 'judge'  # judge / arbiter / advocate_same / advocate_diff
    rating: Rating | None = None
    reason_zh: str = ''
    temperature: float = 0.0
    error: str = ''


class ItemResult(BaseModel):
    """条目最终结果（含投票明细与人工覆盖）。"""

    code: str
    group_code: str = ''
    domain_seq: int = 0
    question_zh: str = ''
    question_en: str = ''
    judge_mode: str = 'standard'

    rating: Rating = 'unclear'
    reason_zh: str = ''
    reason_en: str = ''
    cite_a: str = ''
    cite_a_zh: str = ''
    cite_b: str = ''
    cite_b_zh: str = ''
    confidence: Confidence = 'medium'
    needs_review: bool = False
    review_note: str = ''
    votes: list[VoteRecord] = Field(default_factory=list)
    evidence_card: str = Field(default='', description='代码算出的客观事实（若该条目有）')

    override_rating: Rating | None = None
    override_reason_zh: str = ''
    override_by: str = ''

    @model_validator(mode='before')
    @classmethod
    def _accept_legacy_verdict(cls, data: object) -> object:
        """0.6.0 的结果 JSON 只有 `verdict` 没有 `rating`，读进来折成 3/0 分。

        不做这层折算的话，老文件会因为「没有 rating 字段」而静默落到默认值
        `unclear`，整份历史结果变成「全部证据不足」—— 比直接报错更难发现。
        """
        if isinstance(data, dict) and 'rating' not in data and 'verdict' in data:
            data = dict(data)
            legacy = {'dup': '3', 'diff': '0'}
            data['rating'] = legacy.get(data.get('verdict'), 'unclear')
            if data.get('override_verdict'):
                data['override_rating'] = legacy.get(data['override_verdict'], 'unclear')
        return data

    @property
    def effective_rating(self) -> Rating:
        return self.override_rating or self.rating

    @property
    def score(self) -> int | None:
        """本条目得分（0–3）；证据不足时为 None，不参与任何分子分母。"""
        return RATING_SCORE[self.effective_rating]

    @property
    def effective_verdict(self) -> Verdict:
        """折成旧的三态判定，仅供展示与兼容 —— 百分比不走这条路。"""
        return RATING_VERDICT[self.effective_rating]


class GroupResult(BaseModel):
    code: str
    name_zh: str = ''
    name_en: str = ''
    items: list[ItemResult] = Field(default_factory=list)


class DomainResult(BaseModel):
    seq: int
    name_zh: str = ''
    name_en: str = ''
    is_key: bool = False
    groups: list[GroupResult] = Field(default_factory=list)

    level: Level | None = None
    pct: int = 0
    #: 可评分条目的得分合计（分越高越重复）
    score_sum: int = 0
    #: 可评分条目的满分 = 3 × 可评分条目数（证据不足的条目不计入）
    score_max: int = 0
    #: 该领域的名义满分 = 3 × 全部条目数，对应 Excel 的「总分：/24 分」
    score_max_full: int = 0
    dup_count: int = 0
    diff_count: int = 0
    unclear_count: int = 0
    evidence_sufficient: bool = True
    near_boundary: bool = False

    @property
    def items(self) -> list[ItemResult]:
        return [it for g in self.groups for it in g.items]


class AssessmentResult(BaseModel):
    review_a_title: str = ''
    review_b_title: str = ''
    doc_a_sha256: str = ''
    doc_b_sha256: str = ''

    overall_level: Level | None = None
    overall_pct: int = 0
    #: 全部可评分条目的得分合计 / 满分（满分 = 3 × 可评分条目数）
    overall_score_sum: int = 0
    overall_score_max: int = 0
    #: 名义满分 = 3 × 34 = 102，对应 Excel 四个领域总分之和
    overall_score_max_full: int = 0
    overall_reason_zh: str = ''
    overall_reason_en: str = ''
    provisional: bool = Field(default=False, description='关键领域证据不足 → 结论仅供参考')

    domains: list[DomainResult] = Field(default_factory=list)

    engine_version: str = ''
    prompt_version: str = ''
    criteria_version: str = ''
    model: str = ''
    judge_granularity: str = 'all'
    token_in: int = 0
    token_out: int = 0
    llm_calls: int = 0
    unclear_count: int = 0
    review_count: int = 0
    errors: list[str] = Field(default_factory=list)

    @model_validator(mode='before')
    @classmethod
    def _accept_legacy_rating(cls, data: object) -> object:
        """读 0.7.x 的 `result.json` 时把条目评分翻转到 0.8.0 的方向。

        **判据只能是 `engine_version`**：翻转前后的 rating 取值域一模一样（都是
        '0'–'3'），单看一份结果无从分辨方向，只有它自报的版本号能区分。所以这层
        必须挂在 `AssessmentResult` 上而不是 `ItemResult` 上 —— 条目对象看不到版本号。

        领域与整体的 `score_sum` 一并取补（`score_max − score_sum`），`pct`/`level`
        不动：新旧两条公式在得分取补后恒等，翻转不改变任何一格结论。

        0.6.0 及更早只有 `verdict` 没有 `rating`，走 `ItemResult._accept_legacy_verdict`，
        那边直接按新方向折算，不再经过这里（下面 `startswith` 的白名单里没有 0.6）。
        """
        if not isinstance(data, dict):
            return data
        version = str(data.get('engine_version') or '')
        if not version.startswith('srd-engine/0.7'):
            return data

        data = dict(data)
        data['domains'] = [_flip_domain(d) for d in data.get('domains') or []]
        if data.get('overall_score_max') is not None:
            data['overall_score_sum'] = (
                int(data.get('overall_score_max') or 0) - int(data.get('overall_score_sum') or 0)
            )
        return data

    @property
    def items(self) -> list[ItemResult]:
        return [it for d in self.domains for it in d.items]


def _flip_domain(domain: object) -> object:
    """`_accept_legacy_rating` 的领域层：翻转 score_sum 与每个条目的 rating。"""
    if not isinstance(domain, dict):
        return domain
    domain = dict(domain)
    domain['score_sum'] = int(domain.get('score_max') or 0) - int(domain.get('score_sum') or 0)
    domain['groups'] = [_flip_group(g) for g in domain.get('groups') or []]
    return domain


def _flip_group(group: object) -> object:
    if not isinstance(group, dict):
        return group
    group = dict(group)
    group['items'] = [_flip_item(it) for it in group.get('items') or []]
    return group


def _flip_item(item: object) -> object:
    if not isinstance(item, dict):
        return item
    item = dict(item)
    for key in ('rating', 'override_rating'):
        if item.get(key):
            item[key] = flip_rating(str(item[key]))
    # 投票留痕也翻，否则「3 票里 2 票判 0 分」这类审计信息会和最终评分对不上
    item['votes'] = [
        {**v, 'rating': flip_rating(str(v['rating']))}
        if isinstance(v, dict) and v.get('rating')
        else v
        for v in item.get('votes') or []
    ]
    return item
