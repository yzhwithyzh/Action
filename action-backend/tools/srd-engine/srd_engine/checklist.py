"""SRD 清单定义 —— 4 领域 / 12 分组 / 34 条目.

数据源：《系统综述重复性评估-Systematic Review Duplication (SRD).xlsx》表 1
（2026-08 加评分列的版本，条目编号 9 随该版改为 9a）。
中文问题逐字照抄自 Excel，英文为对照翻译。

每条目 0–3 分，领域满分 = 3 × 条目数（见 `DOMAIN_SCORE_MAX`），与 Excel 表 1
的「总分：/24 分」等标注一一对应。评分口径与聚合在 prompts.py / aggregate.py。

本模块是清单的**唯一真源**：条目编号、归属、判定模式、吃哪些 facet 全在这里。
判定口径（dup_when / diff_when / unclear_when）在 criteria/*.yaml。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

CRITERIA_DIR = Path(__file__).parent / 'criteria'

# 「实质上相似」类主观条目 —— 走双证据辩护 + 单裁判（见 DESIGN.md §6）
DEBATE_ITEMS = frozenset({'8c', '8d', '8e', '9a', '10b', '11', '12b'})

# 需要代码取证（算好客观事实塞进提示词，判定权仍在 LLM）
EVIDENCE_ITEMS = frozenset({'3a', '6a', '8b'})


@dataclass(frozen=True)
class Item:
    code: str
    question_zh: str
    question_en: str
    facet_paths: tuple[str, ...]
    judge_mode: str = 'standard'  # standard | debate

    @property
    def has_evidence_card(self) -> bool:
        return self.code in EVIDENCE_ITEMS


@dataclass(frozen=True)
class Group:
    code: str
    name_zh: str
    name_en: str
    items: tuple[Item, ...]


@dataclass(frozen=True)
class Domain:
    seq: int
    name_zh: str
    name_en: str
    is_key: bool
    groups: tuple[Group, ...] = field(default_factory=tuple)

    @property
    def items(self) -> tuple[Item, ...]:
        return tuple(it for g in self.groups for it in g.items)


def _item(code: str, zh: str, en: str, *facets: str) -> Item:
    return Item(
        code=code,
        question_zh=zh,
        question_en=en,
        facet_paths=facets,
        judge_mode='debate' if code in DEBATE_ITEMS else 'standard',
    )


# --------------------------------------------------------------------------- 领域 1（关键）

_D1 = Domain(
    seq=1,
    name_zh='领域 1：研究主题',
    name_en='Domain 1: Research topic',
    is_key=True,
    groups=(
        Group(
            code='1',
            name_zh='确定范围和问题',
            name_en='Defining scope and question',
            items=(
                _item(
                    '1a',
                    '系统综述的研究问题是否基于最新的决策需求而制定？',
                    'Were the review questions developed in response to a current decision-making need?',
                    'topic.decision_need',
                    'topic.research_question',
                ),
                _item(
                    '1b',
                    '这些系统综述的研究目标是否相似？',
                    'Are the objectives of the reviews similar?',
                    'topic.objective',
                    'topic.research_question',
                ),
            ),
        ),
        Group(
            code='2',
            name_zh='纳入标准与合成分组',
            name_en='Eligibility criteria and synthesis groups',
            items=(
                _item(
                    '2a',
                    '各系统综述中纳入的研究人群/患者/问题的特征是否相同？',
                    'Are the characteristics of the populations/patients/problems the same across reviews?',
                    'topic.population',
                ),
                _item(
                    '2b',
                    '各系统综述中纳入研究的干预措施是否相同？',
                    'Are the interventions of the included studies the same across reviews?',
                    'topic.intervention',
                ),
                _item(
                    '2c',
                    '各系统综述中纳入研究的对照措施是否相同？',
                    'Are the comparators of the included studies the same across reviews?',
                    'topic.comparator',
                ),
                _item(
                    '2d',
                    '各系统综述中纳入研究的结局指标是否相同？',
                    'Are the outcomes of the included studies the same across reviews?',
                    'topic.outcomes',
                ),
                _item(
                    '2e',
                    '各系统综述中纳入研究的类型是否相同？',
                    'Are the study designs eligible for inclusion the same across reviews?',
                    'topic.study_designs',
                ),
                _item(
                    '2f',
                    '各系统综述中研究的范围是否相似？',
                    'Is the scope of the reviews similar?',
                    'topic.scope',
                    'topic.population',
                    'topic.study_designs',
                ),
            ),
        ),
    ),
)

# --------------------------------------------------------------------------- 领域 2

_D2 = Domain(
    seq=2,
    name_zh='领域 2：研究方法',
    name_en='Domain 2: Methods',
    is_key=False,
    groups=(
        Group(
            code='3',
            name_zh='检索与筛选研究',
            name_en='Searching and selecting studies',
            items=(
                _item(
                    '3a',
                    '各系统综述是否使用了相同的数据库及其他文献检索来源？',
                    'Did the reviews use the same databases and other information sources?',
                    'method.databases',
                    'method.extra_sources',
                ),
                _item(
                    '3b',
                    '各系统综述的检索策略结构是否相似？',
                    'Is the structure of the search strategies similar across reviews?',
                    'method.search_structure',
                    'method.search_date_range',
                ),
            ),
        ),
        Group(
            code='4',
            name_zh='数据收集',
            name_en='Data collection',
            items=(
                _item(
                    '4a',
                    '两篇系统综述的数据来源是否相似？',
                    'Are the sources of data similar across the two reviews?',
                    'method.data_sources',
                ),
                _item(
                    '4b',
                    '各系统综述提取的数据类型和内容是否相似？',
                    'Are the types and content of extracted data similar across reviews?',
                    'method.extracted_fields',
                ),
            ),
        ),
        Group(
            code='5',
            name_zh='效应指标',
            name_en='Effect measures',
            items=(
                _item(
                    '5a',
                    '对于相同的结局指标，各系统综述的数据类型是否一致？',
                    'For the same outcomes, are the data types consistent across reviews?',
                    'method.data_types',
                    'topic.outcomes',
                ),
                _item(
                    '5b',
                    '对于结局指标，各系统综述选择的效应指标是否相同？',
                    'For the outcomes, are the effect measures chosen by the reviews the same?',
                    'method.effect_measures',
                    'topic.outcomes',
                ),
            ),
        ),
    ),
)

# --------------------------------------------------------------------------- 领域 3（关键）

_D3 = Domain(
    seq=3,
    name_zh='领域 3：研究结果',
    name_en='Domain 3: Results',
    is_key=True,
    groups=(
        Group(
            code='6',
            name_zh='合成准备',
            name_en='Preparing for synthesis',
            items=(
                _item(
                    '6a',
                    '各系统综述纳入研究之间的重叠程度如何？',
                    'What is the degree of overlap in the studies included across the reviews?',
                    'result.included_studies',
                ),
                _item(
                    '6b',
                    '各系统综述是否总结了每项研究的基本特征？',
                    'Did the reviews summarise the key characteristics of each included study?',
                    'result.study_char_table_present',
                ),
                _item(
                    '6c',
                    '各系统综述是否比较了纳入研究的特征，以判断哪些研究足够相似以便进行有意义的合并？',
                    'Did the reviews compare study characteristics to judge which studies were similar '
                    'enough for a meaningful synthesis?',
                    'result.similarity_assessment',
                ),
                _item(
                    '6d',
                    '两篇系统综述是否评估并筛选了可用于合成分析的数据，特别是处理同一研究中可能存在的'
                    '「多重性」问题？',
                    'Did the reviews check and select the data available for synthesis, in particular '
                    'handling multiplicity within a single study?',
                    'result.multiplicity_handling',
                ),
                _item(
                    '6e',
                    '两篇系统综述是否使用了相似的数据合成方法？',
                    'Did the reviews use similar methods of data synthesis?',
                    'result.synthesis_method',
                ),
            ),
        ),
        Group(
            code='7',
            name_zh='Meta 分析',
            name_en='Meta-analysis',
            items=(
                _item(
                    '7a',
                    '各系统综述是否采用相同的方法处理异质性？',
                    'Did the reviews use the same approach to handle heterogeneity?',
                    'result.heterogeneity_methods',
                ),
                _item(
                    '7b',
                    '各系统综述是否采用相同的亚组分析策略？',
                    'Did the reviews use the same subgroup analysis strategy?',
                    'result.subgroups',
                ),
                _item(
                    '7c',
                    '两篇系统综述是否以相同方式处理缺失数据？',
                    'Did the reviews handle missing data in the same way?',
                    'result.missing_data_handling',
                ),
                _item(
                    '7d',
                    '两篇系统综述是否采用相同的敏感性分析策略？',
                    'Did the reviews use the same sensitivity analysis strategy?',
                    'result.sensitivity_analyses',
                ),
            ),
        ),
        Group(
            code='8',
            name_zh='结果解释',
            name_en='Interpretation of results',
            items=(
                _item(
                    '8a',
                    '对于相同的结局，各系统综述是否采用了相同的统计模型？',
                    'For the same outcomes, did the reviews use the same statistical model?',
                    'result.statistical_model',
                    'result.pooled_results',
                ),
                _item(
                    '8b',
                    '对于相同的结局，各系统综述中合并效应估计的方向、大小和置信区间是否相似？',
                    'For the same outcomes, are the direction, magnitude and confidence intervals of the '
                    'pooled effect estimates similar?',
                    'result.pooled_results',
                ),
                _item(
                    '8c',
                    '对于可比较的结局，两篇系统综述对干预效应的方向（有益、无效或有害）和大小给出的'
                    '实质性解释是否相似？',
                    'For comparable outcomes, do the reviews offer substantially similar interpretations of '
                    'the direction (benefit, no effect, harm) and magnitude of the intervention effect?',
                    'result.interpretation',
                    'result.pooled_results',
                ),
                _item(
                    '8d',
                    '各系统综述对结果在不同人群或场景中的适用性和普适性是否做出了实质上相似的判断？',
                    'Did the reviews make substantially similar judgements about the applicability and '
                    'generalisability of the results to other populations or settings?',
                    'result.applicability',
                ),
                _item(
                    '8e',
                    '基于总体证据，各系统综述是否得出了实质上相似的结论，并提出了相似的实践或未来研究建议？',
                    'Based on the overall evidence, did the reviews reach substantially similar conclusions '
                    'and make similar recommendations for practice or future research?',
                    'result.conclusion',
                    'result.future_research',
                ),
            ),
        ),
    ),
)

# --------------------------------------------------------------------------- 领域 4

_D4 = Domain(
    seq=4,
    name_zh='领域 4：研究质量',
    name_en='Domain 4: Quality',
    is_key=False,
    groups=(
        Group(
            code='9',
            name_zh='偏倚和利益冲突',
            name_en='Bias and conflicts of interest',
            items=(
                _item(
                    '9a',
                    '两篇综述是否基于相似信息识别、报告和解释利益冲突及其他潜在偏倚来源，并对其结果的'
                    '潜在影响做出实质上相似的总体判断？',
                    'Did the reviews identify, report and interpret conflicts of interest and other potential '
                    'sources of bias on the basis of similar information, and make substantially similar '
                    'overall judgements about their potential impact on the results?',
                    'quality.coi_disclosure',
                    'quality.funding',
                    'quality.coi_of_included_studies',
                ),
            ),
        ),
        Group(
            code='10',
            name_zh='偏倚风险',
            name_en='Risk of bias',
            items=(
                _item(
                    '10a',
                    '系统综述研究中使用什么方法测量偏倚风险？',
                    'What methods did the reviews use to assess risk of bias?',
                    'quality.rob_tool',
                ),
                _item(
                    '10b',
                    '在评估纳入研究的偏倚风险时，各综述对证据的总体偏倚水平是否做出了实质上相似的判断？',
                    'In assessing risk of bias of the included studies, did the reviews make substantially '
                    'similar judgements about the overall level of bias in the evidence?',
                    'quality.rob_overall_distribution',
                    'quality.rob_tool',
                ),
            ),
        ),
        Group(
            code='11',
            name_zh='缺失结果导致的偏倚',
            name_en='Bias due to missing results',
            items=(
                _item(
                    '11',
                    '在评估因缺失结果导致的偏倚时，两篇综述对于这种偏倚是否以及可能在多大程度上影响了'
                    '研究结果，是否得出了实质上相似的结论？',
                    'In assessing bias due to missing results, did the reviews reach substantially similar '
                    'conclusions about whether and to what extent such bias affected the results?',
                    'quality.missing_outcome_bias_assessment',
                ),
            ),
        ),
        Group(
            code='12',
            name_zh='证据与 GRADE',
            name_en='Evidence and GRADE',
            items=(
                _item(
                    '12a',
                    '系统综述研究中使用什么方法进行证据总结？',
                    'What methods did the reviews use to summarise the evidence?',
                    'quality.certainty_method',
                ),
                _item(
                    '12b',
                    '对于可比较的关键结局，各综述对总体证据总结和证据确定性（例如使用 GRADE）是否做出了'
                    '实质上相似的判断？',
                    'For comparable critical outcomes, did the reviews make substantially similar judgements '
                    'about the overall summary of evidence and its certainty (e.g. using GRADE)?',
                    'quality.grade_ratings',
                    'quality.certainty_method',
                ),
            ),
        ),
    ),
)

DOMAINS: tuple[Domain, ...] = (_D1, _D2, _D3, _D4)
ALL_ITEMS: tuple[Item, ...] = tuple(it for d in DOMAINS for it in d.items)
ITEM_BY_CODE: dict[str, Item] = {it.code: it for it in ALL_ITEMS}
GROUP_OF_ITEM: dict[str, str] = {it.code: g.code for d in DOMAINS for g in d.groups for it in g.items}
DOMAIN_OF_ITEM: dict[str, int] = {it.code: d.seq for d in DOMAINS for it in d.items}

ITEM_COUNT = 34

#: 领域名义满分（3 分 × 条目数），对应 Excel 表 1 里各领域标注的「总分」
DOMAIN_SCORE_MAX: dict[int, int] = {d.seq: 3 * len(d.items) for d in DOMAINS}

assert len(ALL_ITEMS) == ITEM_COUNT, f'清单条目数应为 {ITEM_COUNT}，实际 {len(ALL_ITEMS)}'
assert len({it.code for it in ALL_ITEMS}) == ITEM_COUNT, '条目编号有重复'
# Excel 表 1 白纸黑字写着的四个领域总分，写死在这里当护栏：改清单结构时立刻失败
assert DOMAIN_SCORE_MAX == {1: 24, 2: 18, 3: 42, 4: 18}, f'领域满分与 Excel 不符：{DOMAIN_SCORE_MAX}'


# --------------------------------------------------------------------------- 判定口径


@lru_cache(maxsize=1)
def load_criteria() -> dict[str, dict]:
    """加载 criteria/*.yaml，返回 {条目编号: {dup_when, diff_when, unclear_when, examples}}。"""
    merged: dict[str, dict] = {}
    for path in sorted(CRITERIA_DIR.glob('*.yaml')):
        data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        # 条目编号 9 / 11 在 YAML 里会被解析成 int，统一转回字符串
        merged.update({str(k): v for k, v in data.items()})
    missing = [it.code for it in ALL_ITEMS if it.code not in merged]
    if missing:
        raise ValueError(f'criteria 缺少条目口径：{missing}')
    return merged


def criteria_of(code: str) -> dict:
    return load_criteria()[code]
