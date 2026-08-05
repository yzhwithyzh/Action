# SRD 评估引擎 · 技术路线设计 v2

> 目标：把 `方法学评估工具/系统综述重复性评估-Systematic Review Duplication (SRD).xlsx`
> 落地为可运行、**可复算、可审计**的在线工具：导入两篇系统综述 → 逐条目判定是否一致 →
> 领域分级 → 整体判定 + 理由 + 原文引用 → 导出。
>
> v2 变更（依甲方决定）：① 技术栈定为 **LangChain**（不用 agno）；② **34 条目全部由 LLM 判定**，
> 取消 `code / hybrid / descriptive` 分流，代码只负责算分；③ 条目产出统一为 **是否重复 + 理由**。
>
> 版本：v2 设计稿（2026-07-30）。实现前需与方法学专家确认 §4.3 判定口径与 §15 待定项。

## 实现状态（2026-08-05，引擎 0.7.0）

**引擎已实现并可独立运行**，见 [README.md](README.md)。当前为纯引擎、零后端耦合：
不 import 任何后端模块、不碰数据库与 HTTP，`pip install -e .` 后用 `srd` 命令即可跑。
测试 154 个全部通过（聚合、口径、取证、解析、超长兜底、批量判定均可离线验证，不烧 token）。

实现过程中相对本文档的修正，按影响从大到小：

0. **⚠ 条目判定改为 0–3 四档评分（0.7.0，2026-08-05，随新版 Excel）**。
   甲方在 Excel 表 1 加了「评分」列：完全相同 0 分 / 部分相同 1 分 / 部分不同 2 分 /
   完全不同 3 分，并给四个领域标了总分（/24、/18、/42、/18，合计 /102）。
   本文档通篇的三态 `dup / diff / unclear` 相应作废，受影响的条款：

   - §3.2「分数」行、§3.3 的 `verdict` 字段、§4.1 的 `ItemVerdict`、§4.3 的口径 YAML 结构、
     §9 的聚合伪代码、§11.3 的验收指标、§16 的 P0 里程碑描述 —— 一律改读「评分」。
   - 领域百分比的定义从「判 dup 的条目数 ÷ 可评估条目数」改为
     「(可评分满分 − 得分) ÷ 可评分满分」。**两者在只打 0 / 3 分时完全等价**，
     所以 §9 之后的表 2 分箱、表 3 矩阵、`unclear` 剔出分母这些结论一个字都不用改。
   - `criteria/*.yaml` 的 `dup_when` / `diff_when` 就地改读为 **0 分锚点 / 3 分锚点**，
     字段名未改（改名要动 34 条口径，收益只有好看）。1 分与 2 分暂只有一条通用口径
     （「差异会不会改变临床或方法学解读」），写在 `prompts.py` 里 34 条共用，
     **未经方法学专家评审**，是当前最该补的一块（见 §15 待定项）。
   - 条目编号 `9` 随新版 Excel 改为 `9a`。
   - 0.6.0 的历史结果 JSON 会在读取时自动折成 0/3 分，重算百分比与当年逐位一致。

1. **⚠ 判定改为「34 条一次调用」，可靠性阶梯整体删除（0.6.0）**。§5「绝不 34 条一次全给」
   与 §6 的 k=2 投票 + 仲裁 + 双证据辩护**全部被 §11.5 的消融实验推翻**：两种模式的自一致率
   完全相同（都是 95%），76 次调用没有换来更稳的输出，代价却是 76 倍调用、6 倍 token。
   单次评估从 84 次调用降到 **9 次**（8 次抽取 + 1 次判定）。详见 §5 / §6 的顶部批注。

2. **⚠ 引用回查已整体移除（0.4.0，甲方决定）**。本文档多处假定「LLM 给的引用会被程序
   拿回原文核对，定位不到即视为编造」，**这条约束已不存在**：不再校验引用真伪，
   `page` 字段废弃，报告与 CSV 不再显示页码，`--no-verify` 开关删除。
   受影响的条款：§11.2 的「引用可定位率」指标、§11.3 的「引用可定位率 ≥ 95%」验收线、
   §14 风险表里「LLM 编造引用 → 硬门槛」这条缓解措施。`quote` 仍要求逐字，但只供人工复核。

3. **抽取默认喂整篇原文，不再按章节挑**（原 §2.2 的批次章节表降级为 `--extract-scope sections`
   的可选项）。实测：按章节关键词挑正文时，标题识别不准就会静默丢掉关键段落，
   字段填充率 70% vs 全文 87%，unclear 187 → 128。这是本轮唯一被量化验证有效的改动。
   **参考文献段一律剔除**（0.6.0，甲方决定，实测 12 篇平均省 20% 输入）；
   剔除后仍超过 12 万字符才切块分别抽取再合并。

4. **引用字段拆成 `quote` + `quote_zh`**（原 §4.1 只有 `cite_a_zh` / `cite_a_en`）。
   原因是逐字引用必须保持原语言；回查移除后这个拆分仍然保留，供人工复核比对。

5. **并发用 asyncio.Semaphore 而非 `abatch(max_concurrency)`**（原 §8.3）。
   各阶段 schema 与调用形态不一致（抽取 4 种 schema、判定 1 种、辩护是纯文本），
   `abatch` 只约束同构批次，跨阶段总并发仍需自己兜；一个信号量更可预期。

6. **`ENGINE_VERSION` 进抽取缓存 key**（原 §3.2 的唯一键只有 `doc_id + prompt_version + model_code`）。
   抽取行为由引擎代码决定，不纳入就得靠人工纪律。后端接入时表结构需相应加列。

尚未实现：`eval/` 评测脚本与金标准集（§11）、`criteria/*.yaml` 的 few-shot 案例、后端接入（§3/§9）。

---

## 0. 结论摘要

| 决策点 | 结论 |
|---|---|
| 判定单元 | 34 条目**每条都由 LLM 判定**，输出 `重复 / 不重复 / 证据不足` + 理由 + 双篇原文引用。 |
| 分数 | **全部由代码算**。领域百分比 = 该领域判为"重复"的条目数 ÷ 可评估条目数 × 100 → 表 2 分箱 → 表 3 矩阵 → 整体判定。LLM 不碰任何数字。 |
| **调用粒度** | ~~默认一条目一次调用（34 次）~~ → **默认 34 条一次调用**（0.6.0，实测推翻，见 §5 批注）。`per_group` / `per_item` 作为选项保留。 |
| 框架 | **LangChain**：`with_structured_output` 拿 Pydantic、`abatch(max_concurrency)` 控并发、`with_retry` / `with_fallbacks` 兜错、回调推 SSE 进度。见 §8。 |
| 可靠性 | ~~k=2 自一致投票 + 仲裁 + 双证据辩护~~ → **整体删除**（0.6.0，实测自一致率与单次调用相同，见 §6 批注）。剩下的防线只有「少返条目补 unclear」与金标准评测。 |
| 代码的角色 | 只做两件事：**算分**（§7）+ **取证**（§4.4，把"纳入研究交集清单""两篇的合并效应量数值"这类算好的客观事实塞进提示词当证据）。判定权始终在 LLM。 |
| 质量保证 | 先建 **20–30 对金标准综述对**（专家标注），条目级 κ / 领域一致率 / 整体一致率。§11.5 的消融实验已做（2026-08-02），结论推翻了 §5/§6；金标准集**仍未建**，是目前最大的缺口。 |

---

## 1. 需求与约束

### 1.1 来源工具结构（已核对 Excel）

- **表 1 清单**：4 领域 / 12 分组 / **34 条目**
  - 领域 1 研究主题〔**关键**〕：1 确定范围和问题(1a,1b)、2 纳入标准与合成分组(2a–2f) —— 8 条
  - 领域 2 研究方法：3 检索与筛选(3a,3b)、4 数据收集(4a,4b)、5 效应指标(5a,5b) —— 6 条
  - 领域 3 研究结果〔**关键**〕：6 合成准备(6a–6e)、7 Meta 分析(7a–7d)、8 结果解释(8a–8e) —— 14 条
  - 领域 4 研究质量：9 偏倚和利益冲突、10 偏倚风险(10a,10b)、11 缺失结果偏倚、12 证据与 GRADE(12a,12b) —— 6 条
- **表 2 单领域重复程度**：无重复 0–25% / 低重复 26–50% / 中度重复 51–75% / 高度重复 76–100%
- **表 3 整体判定**：关键领域（主题+结果）状态 × 非关键领域（方法+质量）状态查表

### 1.2 百分比语义（v2 已定）

> **领域百分比 = 该领域中判定为"重复/一致"的条目数 ÷ 该领域可评估条目数 × 100**

这条定义让表 2 与表 1 严丝合缝：8 条的领域 1，判"重复"5 条 → 62.5% → **中度重复**。
也解决了 10a / 12a 这类"使用什么方法"的条目——**两篇用同一种方法（都用 GRADE、都用 RoB 2）就是一致，计为重复**，无需特殊处理。v1 设计里的 `descriptive` 分类已删除。

### 1.3 现有代码资产（可直接复用）

| 资产 | 位置 | 说明 |
|---|---|---|
| 三级数据表 | `action-backend/module_action/entity/do/action_do.py` | `ActionSrdAssessment` / `ActionSrdDomain` / `ActionSrdGroup` / `ActionSrdItem`，已含 `level` `pct` `basis_zh/en` `cite_a_zh/en` `cite_b_zh/en` |
| 输出契约 | `.../entity/vo/action_vo.py` | `SrdAssessmentModel` 及子模型 —— 基本就是引擎输出 schema，扩字段即可（§3.3） |
| 读取链路 | `.../dao/action_dao.py` `SrdDao`、`.../service/action_service.py` `SrdService` | `get_sample_assessment` / `get_assessment_by_id` / `get_domains` / `get_groups` / `get_items` |
| 前台页面 | `action-frontend/pages/srd.vue` | 领域环形图、条目表、level 配色已就绪；当前只调 `/srd/sample` |
| 模型注册表 | `action-backend/module_ai/`（表 `ai_model`）、`utils/crypto_util.py` | provider / model_code / base_url / **加密 api_key** / max_tokens / temperature —— **LangChain 复用这张表**，不重建密钥管理 |
| 示例数据 | `action-backend/sql/action-website-pg.sql` | SRD 示例评估（PostgreSQL） |

> `utils/ai_util.py` 的 agno 模型工厂继续服务 AI 对话模块；SRD 引擎不走它，另建 LangChain 工厂（§8.2），两者共用同一张 `ai_model` 表。

### 1.4 关键约束

1. **可复算**：同一对综述 + 同一 `engine_version` / `prompt_version` / `criteria_version` / `model_code` → 同一结论。
2. **可审计**：每条判定必须给出两篇的**逐字原文引用**。
   ~~+ 页码，且引用须能在解析出的原文里回查定位（§14 硬门槛）~~ —— 引用回查与页码已于 0.4.0 移除，
   见「实现状态」第 1 条。现在引用只供人工复核，真伪不再由程序校验。
3. **可推翻**：条目级支持人工覆盖，覆盖后领域/整体判定**自动重算**。
4. **中英双语**：`*_zh` / `*_en` 双份。
5. **成本可控**：单次评估 ≤ ¥3（国产中端模型），墙钟 ≤ 5 min。

---

## 2. 总体架构

```
                        ┌──────────────── 可缓存（按 PDF 内容 hash + prompt_version） ────────────────┐
上传 A.pdf ──► P0 解析 ──►│ P1 单篇结构化抽取（facet extraction，每字段带逐字引用）                  │──► ExtractA
上传 B.pdf ──► P0 解析 ──►│  批次1 主题/PICO  批次2 方法/检索  批次3 结果/Meta  批次4 质量/GRADE      │──► ExtractB
                        └──────────────────────────────────────────────────────────────────────┘
                                                    │
                          ┌─────────────────────────┴──────────────────────────┐
                          │ P2 条目判定（默认 34 条一次调用，见 §5/§6 批注）      │
                          │   输入：34 条的问题 + 判定口径 + A/B 相关 facet 切片   │
                          │        （+ 代码算好的客观证据卡，见 §4.4）           │
                          │   输出：每条 verdict ∈ {dup, diff, unclear}         │
                          │        + 理由(中/英) + A/B 逐字引用 + confidence     │
                          │   少返的条目补 unclear + needs_review，绝不静默       │
                          └─────────────────────────┬──────────────────────────┘
                                                    ▼
                          P3 确定性聚合（纯 Python，零 LLM，可单测）
                            领域 pct = dup 数 ÷ (dup+diff) 数 × 100 → 表 2 分箱 → domain.level
                            表 3 矩阵查表 → overall_level（+ 模板化 overall_reason）
                                                    ▼
                          P4 落库 / SSE 逐条推进度 / 前台渲染 / CSV·PDF 导出 / 人工覆盖重算
```

**为什么不是"一个 Agent 读两篇 PDF 直接出结论"**：34 条判定路径完全已知，固定 DAG 才能做到同输入同输出、失败可重试、成本可预估。这是学术工具的底线要求。
（注意：0.6.0 起 P2 内部是一次调用判完 34 条，但**流水线本身仍是固定 DAG** —— 判定口径、facet 切片、
聚合算法都由代码决定，模型只在 P1/P2 两个位置被调用，且不碰任何数字。）

### 2.1 P0 PDF 解析

`requirements.txt` 目前**无任何 PDF 库**，需新增。

- **PyMuPDF (`pymupdf`)**：文本 + 坐标 + 页码。
  （0.4.0 起页码已不再使用；保留 PyMuPDF 是因为它是解析质量最好的纯 Python 方案。）
- `pdfplumber` 兜底抽表（纳入研究特征表、Meta 结果表）。
- 章节切分：标题启发式（Abstract / Methods / Search / Data extraction / Risk of bias / Results / GRADE / Discussion）。GROBID（Docker）留 v2，v1 不做硬依赖。
- 输出 `ParsedDoc`：`{pages:[{no,text}], sections:[{title,text,page_from,page_to}], tables:[], refs:[]}`。
- **扫描版 PDF**：v1 不支持 OCR，检测到无文本层直接报错（OCR 噪声会污染引用，得不偿失）。

### 2.2 P1 单篇结构化抽取

**不要为每个条目重读全文**——那是 34 次长上下文调用。一次性把每篇抽成结构化 facet，34 条判定都只吃 facet 切片。

4 个批次，每批一次 LLM 调用：

| 批次 | 抽取字段（节选） | 服务的条目 |
|---|---|---|
| B1 主题 | `objective`、`research_question`、`decision_need`、`pico.{population,intervention,comparator,outcomes[]}`、`study_designs[]`、`scope`（地域/年限/语言/设置） | 1a–2f |
| B2 方法 | `databases[]`、`extra_sources[]`（注册库/灰色文献/查引/手检）、`search_date_range`、`search_structure`（概念块数/MeSH/过滤器）、`data_sources[]`、`extracted_fields[]`、`effect_measures[]`、`data_types[]` | 3a–5b |
| B3 结果 | `included_studies[]`（作者+年份+注册号/DOI）、`study_char_table_present`、`similarity_assessment`、`multiplicity_handling`、`synthesis_method`、`heterogeneity_methods[]`、`subgroups[]`、`missing_data_handling`、`sensitivity_analyses[]`、`model`、`pooled_results[]`（结局/measure/point/CI/k/n/I²）、`interpretation`、`applicability`、`conclusion`、`future_research` | 6a–8e |
| B4 质量 | `coi_disclosure`、`funding`、`coi_of_included_studies`、`rob_tool`、`rob_overall_distribution`、`missing_outcome_bias_assessment`、`certainty_method`、`grade_ratings[]` | 9–12b |

每字段强制携带证据：`{value, quote_zh, quote_en, page, section, present: true|false|unclear}`。

**`present:false` 与 `unclear` 必须区分**：
- 两篇都**明确写了"未做敏感性分析"** → 这是**真实的方法一致** → 判 `dup`
- 两篇都**没写清楚** → 证据不足 → 判 `unclear`，剔出分母（§7.3）

**缓存**：`ExtractX` 以 `sha256(pdf) + prompt_version + model_code` 为 key 落库。典型场景是"一篇新综述 vs 库里 N 篇"，缓存把成本降到 1/(N+1)。

---

## 3. 数据模型改造

### 3.1 新增：清单模板表

现有 `action_srd_item` 挂在 `group → domain → assessment` 下（清单随每次评估复制一份，便于冻结当时版本），但缺"模板"来源：

```
action_srd_tpl_domain(tpl_domain_id, seq, name_zh, name_en, is_key, version)
action_srd_tpl_group (tpl_group_id, tpl_domain_id, code, name_zh, name_en, sort_num)
action_srd_tpl_item  (tpl_item_id, tpl_group_id, code, question_zh, question_en,
                      judge_mode,     -- 'standard' | 'debate'   （§6）
                      facet_path,     -- 该条目吃哪些 facet，如 "pico.intervention"
                      criteria_json,  -- 判定口径：dup/diff/unclear 判据 + 案例（§4.3）
                      sort_num, version)
```

### 3.2 新增：文档与抽取缓存

```
action_srd_document(doc_id, uploader_id, file_name, file_path, content_sha256,
                    title_zh, title_en, doi, journal, pub_year,
                    parse_status, parsed_json, page_count, create_time)
action_srd_extraction(extract_id, doc_id, prompt_version, model_code,
                      extract_json, token_in, token_out, create_time)
                      -- unique(doc_id, prompt_version, model_code)
```

### 3.3 扩展现有表

```sql
-- action_srd_assessment
+ doc_a_id, doc_b_id              int
+ job_status                      varchar(16)  -- queued/parsing/extracting/judging/done/failed
+ progress                        int
+ engine_version, prompt_version, criteria_version  varchar(32)
+ model_code                      varchar(64)
+ judge_granularity               varchar(16)  -- 'per_item' | 'per_group'（§5）
+ token_in, token_out, cost_cents int
+ error_msg                       text
+ unclear_count, review_count     int
+ owner_id                        int          -- 访客账号归属（配合 guest_auth_service）
+ finished_time                   datetime

-- action_srd_domain
+ dup_count, diff_count, unclear_count  int    -- 分子/分母透明化，前台可直接展示 "5/8"
+ evidence_sufficient             char(1)      -- 可评估条目 <50% 置 '0'

-- action_srd_item
  level  →  复用为 verdict: 'dup' | 'diff' | 'unclear'    ★ 语义变更，见 §3.4
  pct    →  保留但恒为 100 / 0 / null（前台不再展示条目百分比）
+ confidence                      varchar(8)   -- high/medium/low
+ needs_review                    char(1)
+ evidence_page_a, evidence_page_b  int   ← 0.4.0 起不再产出，接入时可省
+ vote_detail_json                text         -- 每次投票的 verdict + 理由摘要，供审计
+ judge_mode                      varchar(16)
+ override_verdict                varchar(16)  -- 人工覆盖
+ override_reason_zh, override_reason_en  text
+ override_by, override_time
```

### 3.4 前端需同步的语义变更

`srd.vue` 现有 `LV_CLASS = {none, low, mod, high}` 同时用于条目和领域。改造后：

- **领域 / 整体**：继续用 `none / low / mod / high` 四档 + 现有配色环形图 —— **不动**
- **条目**：改为三值徽标 `dup（重复）/ diff（不重复）/ unclear（证据不足）`，建议配色 `dup=cinnabar`、`diff=info`、`unclear=灰`
- 领域卡新增 "重复条目 5/8" 展示（`dup_count / (dup_count + diff_count)`），让百分比来源一眼可见

---

## 4. 条目判定协议

### 4.1 统一输出 schema（LangChain `with_structured_output` 直接绑定）

```python
class ItemVerdict(BaseModel):
    code: str                                   # "2a"
    verdict: Literal['dup', 'diff', 'unclear']  # 重复 / 不重复 / 证据不足
    reason_zh: str                              # ≤200 字，必须点明"相同点"或"关键差异点"，禁止套话
    reason_en: str
    cite_a_zh: str; cite_a_en: str              # 综述A逐字引用
    cite_b_zh: str; cite_b_en: str              # 综述B逐字引用
    evidence_page_a: int | None   # 0.4.0 起恒为 None，接入时可省
    evidence_page_b: int | None
    confidence: Literal['high', 'medium', 'low']
```

### 4.2 为什么是三值而非二值

你要的是"是否一致"，但必须给 `unclear` 留一格——**两篇都没写清楚 ≠ 两篇做法相同**。
若强行二值，所有报告不全的综述都会被系统性推向某一侧，直接污染领域百分比（而百分比就是最终判定的唯一输入）。
`unclear` 的处理：剔出分母、进人工复核队列、在报告里显式列出（§7.3）。

### 4.3 判定口径（`criteria/*.yaml`，每条目一份）

**口径必须写成"可观察的差异描述"**，不能是"很相似 / 较相似"这种同义反复。以 2b 为例：

```yaml
2b:
  question_zh: 各系统综述中纳入研究的干预措施是否相同？
  dup_when: |
    针刺类型（手针/电针/温针/穴位埋线…）、主要穴位方案、剂量参数（疗程/频次/留针时间）
    在临床意义上无实质差异——即一名针灸临床医生会认为两篇在评价"同一种治疗"。
  diff_when: |
    针刺类型不同，或核心穴位组无交集，或剂量差异大到会改变临床解读
    （如 4 周 vs 12 周疗程、每周 1 次 vs 每周 3 次）。
  unclear_when: |
    任一篇未报告干预细节，仅笼统称"针刺治疗"，无法比较。
  examples:                     # 各 1–2 条真实案例，从金标准集里抽（§11）
    - {a: "...", b: "...", verdict: dup,  why: "..."}
    - {a: "...", b: "...", verdict: diff, why: "..."}
```

34 条口径撰写约 3 人天，**这是本项目对准确率贡献最大的一项工作**，优先级高于任何模型或投票策略的调优。

### 4.4 代码取证（只取证，不判定）

三条目的客观事实用代码算好，**作为"证据卡"塞进提示词**，LLM 仍自己下判定：

| 条目 | 代码算什么 | 提示词里长什么样 |
|---|---|---|
| 6a 纳入研究重叠程度 | 两篇 `included_studies[]` 归一化后求交并集（注册号→DOI→作者+年份 三级匹配） | 「客观事实：A 纳入 14 项、B 纳入 11 项，交集 8 项（Jaccard 0.47）。共同研究清单：…」 |
| 8b 合并效应方向/大小/CI | 逐结局比较方向、点估计比值、CI 重叠系数 | 「客观事实：主要结局 VAS，A 为 MD −1.32 (−1.80,−0.84)、B 为 MD −1.15 (−1.66,−0.64)，方向一致，CI 重叠 86%」 |
| 3a 数据库与检索来源 | 标准化词表归一后求交并集 | 「客观事实：A 检索 7 个来源、B 检索 5 个，交集 5 个（PubMed/Embase/CENTRAL/CNKI/WanFang）；A 另检索了试验注册库与灰色文献」 |

理由：LLM 从长文本里"数"纳入研究数量和交集本就不可靠，而这恰恰是重复性最直接的证据。代码只做算术，判定权仍在 LLM——完全符合"每条都由 LLM 判"的要求。
标准化词表放 `srd_engine/vocab/*.yaml`（数据库名、效应指标、研究设计、RoB 工具、合成方法），一次维护全条目共享。

---

## 5. 调用粒度：一条一次 vs 一次全给 ★

> ### ⚠ 本节结论已被推翻（2026-08-02，引擎 0.6.0）
>
> §11.5 要求的消融实验做完后，本节的判断**与实测不符**，默认已改为 **`all`（34 条一次调用）**。
> 4 对 × 34 条目、同一份 facet、只变判定粒度：
>
> | 对照 | 一致率 |
> |---|---|
> | `per_item` 自己重跑两遍 | 95% |
> | `all` 自己重跑两遍 | 95% |
> | `per_item` vs `all` | 90% |
>
> **两种模式的自一致率完全相同**，即 76 次调用并没有换来更稳的输出；跨模式那 5 个百分点
> 与同配置重跑的抖动无法区分。代价却是 76 倍调用、6 倍 token（输入 457k→80k，输出 122k→34k）。
> 另外 `all` 的 `unclear` 反而更少（57→46），一个合理解释是模型能借相邻条目的语境补上单看一条时判不了的情况。
>
> 下面 5.1 表格里对「一次全给」的三条具体指控，实测情况：
> - **「输出 8k tokens、后半段质量断崖」** —— 实测输出 8,570 token 一次返完，**零截断**，34 条全部返回。
> - **「羊群效应」** —— 真实存在，就是那 5 个百分点，但与噪声同量级。提示词里已加明确警示。
> - **「JSON 截断一次全废」** —— 已有防护：少返的条目补成 `unclear + needs_review`，绝不静默。
>
> 仍然成立的部分：`per_item` 确实能逐条重试、逐条推进度。但这属于工程便利，不值 76 倍成本。
> `per_item` / `per_group` 作为选项保留（`--granularity`），不再是默认。
>
> **原文保留如下，以便看出决策依据的演变。**

这是你问的第 3 点。结论：**默认一条目一次调用，绝不 34 条一次全给**。

### 5.1 三种粒度对比

| 方案 | 调用数 | 输入 tokens | 主要风险 |
|---|---|---|---|
| **A. 一次全给**（34 条 1 次） | 1 | ~12k | ❌ 输出要 34 组理由+引用 ≈ 8k tokens，**后半段质量断崖下降**；**羊群效应**（前几条判 dup，后面跟着判 dup）；JSON 截断或格式错一次全废；无法逐条重试；无法逐条投票；进度条只能 0→100 |
| **B. 分组批量**（12 分组 12 次） | 12 | ~50k | 组内 2–6 条，输出可控；同组条目上下文共享、判定更连贯；但组内仍有轻度羊群效应（2a–2f 六条尤其明显），重试粒度是整组 |
| **C. 一条一次**（34 次）✅ | 34 | ~70k | 无羊群、无位置衰减；可逐条重试/投票/超时/推进度；成本略高，但见 §5.2——差距远比想象中小 |

### 5.2 成本差距为什么很小

因为**每条只喂它需要的 facet 切片（1.5–3k），不是整份抽取结果**。C 相对 B 只多约 20k 输入 tokens ≈ **¥0.04**。
再叠加 **prompt caching**（系统提示 + 共享证据前缀命中缓存），差距进一步压缩到可忽略。
**为了省这几分钱去承担羊群效应和整批重跑的风险，不划算。**

### 5.3 并发与耗时

`abatch(max_concurrency=8)`：34 条 ÷ 8 ≈ 5 轮 × 6–10s ≈ **30–60 秒**。
一次全给反而是**单条长输出**，串行生成 8k tokens 往往要 60–120 秒 —— **C 的墙钟时间通常比 A 还短**。

### 5.4 实现上留开关

`judge_granularity ∈ {per_item, per_group}` 存进 `action_srd_assessment`：

- `per_item`（默认）：标准评估
- `per_group`：试用/预览配额下的"快速模式"，12 次调用，成本约 6 折

§11 的消融实验会在金标准集上实测两者条目级 κ 差多少，用数据决定是否保留快速模式。

---

## 6. 可靠性策略

> ### ⚠ 本节描述的可靠性阶梯已整体删除（2026-08-02，引擎 0.6.0）
>
> k=2 自一致投票、分歧仲裁、7 条主观条目的「双证据辩护 + 单裁判」**全部移除**，
> 连同 `k_votes` / `vote_temperature` / `enable_debate` 三个配置项与
> `arbiter_messages` / `advocate_messages` / `referee_messages` 三套提示词。
>
> 推翻依据同 §5 的消融实验：**阶梯模式与单次调用的自一致率完全相同（都是 95%）**。
> 也就是说这套阶梯没有让输出更稳 —— 它自己重跑一遍照样变 5%，而判定不稳是这个任务的
> 固有属性（实测同一对文献四次运行，整体判定完全一致的只有 2/4）。
> 本节末尾估算的「P2 阶段约 82 次调用」现在是 **1 次**，整个引擎从 84 次降到 **9 次**。
>
> 保留下来的可靠性手段只有两条，都不额外花调用：
> - 模型少返条目 → 补成 `unclear + needs_review`（`judge.judge_batch`）
> - `VoteRecord` 留痕，供审计查看模型给出的判定与理由
>
> 本节末尾的「升级路径」仍然有效，且**更重要了**：判定准不准现在完全没有程序侧防线，
> 只能靠 §11 的金标准集回答。5% 的自然抖动意味着，没有金标准时任何「A 比 B 好」的判断都站不住。
>
> **原文保留如下。**

关于上一轮"严格 + 宽松双 LLM"的讨论，结论保留：不采用那个形式（合并规则无依据、误差同向平均不消偏、分歧信号恒为真而失效），改用下面的阶梯，并按"全部 LLM 判定"重新划分：

```
27 条常规条目  judge_mode = 'standard'
   同一提示词 + 同一判定口径，temperature=0.3，k=2
   ├─ 两票一致            → 采纳，confidence=high
   └─ 两票分歧            → 第 3 次仲裁调用（temperature=0，附前两次的理由摘要）
                            仲裁后 confidence=medium；仲裁仍摇摆 → unclear + needs_review

 7 条主观条目  judge_mode = 'debate'   （8c, 8d, 8e, 9, 10b, 11, 12b）
   这 7 条原文措辞都是「**实质上相似**」，口径无法写成可判定规则，且全部落在会拉动最终结论的位置。
   ├─ 辩方甲「求同」：只找并逐字引用两篇实质相同之处，禁止给结论
   ├─ 辩方乙「求异」：只找并逐字引用两篇实质不同之处，禁止给结论
   └─ 裁判：拿到两侧证据 + 判定口径，唯一负责给 verdict（temperature=0）
   ——「严格/宽松」的非对称性放在**证据搜集**上，不放在**评分标准**上：
     宽松者的价值是"别漏掉相似证据"，严格者的价值是"别漏掉差异证据"，
     而评分标准必须唯一且绑定口径，否则结果无法解释、无法复算。
```

P2 阶段调用数：27×2 + 约 7 次仲裁 + 7×3 = **约 82 次**。

**升级路径**（若金标准评测显示某类条目 κ < 0.6）：① 改判定口径 → ② 补该条目 few-shot 真实案例 → ③ 换更强模型 → ④ 才考虑**不同厂商**模型交叉投票（误差近似独立，比同模型双提示词有意义）。

---

## 7. 聚合算法（纯代码，零 LLM）

### 7.1 条目 → 领域

```python
def domain_score(items):
    dup     = [i for i in items if i.effective_verdict == 'dup']      # 人工覆盖优先
    diff    = [i for i in items if i.effective_verdict == 'diff']
    denom = len(dup) + len(diff)
    if denom == 0:
        return None, 0, False                      # 全部证据不足
    pct = round(100 * len(dup) / denom)
    return level_of(pct), pct, denom >= len(items) * 0.5

def level_of(pct):                                 # 表 2
    return 'none' if pct <= 25 else 'low' if pct <= 50 else 'mod' if pct <= 75 else 'high'
```

- **条目等权**（就是数个数）。加权会让"百分比"不再等于"条目占比"，破坏可解释性，除非专家明确要求（§15.1）。
- **边界提醒**：8 条的领域，5/8 = 62.5%（中度）、4/8 = 50%（低）—— **一条之差就跳档**。领域 pct 落在分箱边界 ±5 分内时标注"临界，建议人工复核"。

### 7.2 领域 → 整体（表 3 矩阵）

```python
KEY    = (domain1.level, domain3.level)     # 研究主题、研究结果
NONKEY = (domain2.level, domain4.level)     # 研究方法、研究质量

def key_state(a, b):
    s = {a, b}
    if s == {'none'}:                 return 'both_none'
    if s <= {'none', 'low'}:          return 'both_low'
    if 'high' in s or s == {'mod'}:   return 'both_mod_or_high'
    return 'one_mod'

def nonkey_col(a, b):
    if {a, b} <= {'none', 'low'}:     return 0        # 两个非关键领域均为"低重复"
    if 'high' in {a, b}:              return 2        # 含"高度重复"
    return 1 if [a, b].count('mod') == 1 else 2       # 一个中度 / 两个中度

MATRIX = {                                  # 行 = 关键领域状态
    'both_none':        ('none', 'low',  'mod'),
    'both_low':         ('low',  'low',  'mod'),
    'one_mod':          ('mod',  'mod',  'high'),
    'both_mod_or_high': ('high', 'high', 'high'),
}
overall_level = MATRIX[key_state(*KEY)][nonkey_col(*NONKEY)]
```

- `overall_pct` 仅作展示（四领域 dup 条目总占比），**不参与判定**。判定只走矩阵，才能对着 Excel 表 3 逐格验证。
- `overall_reason_zh/en` 由**模板生成**（"关键领域『研究主题』62% 中度重复、『研究结果』79% 高度重复；非关键领域…… 按表 3 判定为**高度重复**"），不用 LLM 写，保证文字与判定永远一致。
- 表 3 共 16 格，`tests/test_aggregate.py` **逐格断言**。

### 7.3 证据不足的处理

| 情况 | 处理 |
|---|---|
| 条目 `unclear` | 剔出分母，`unclear_count++`，进人工复核队列。**绝不当作 dup** —— 两篇都没写清楚不等于两篇做法相同 |
| 领域可评估条目 < 50% | `evidence_sufficient='0'`，前台该领域标"证据不足"，整体判定照算但结果页顶部显著警示 |
| 关键领域证据不足 | 整体判定标 `provisional`，导出报告首页加"须人工复核后方可引用"横幅 |
| 两篇均**明确报告**"未做某项" | 判 `dup`（真实的方法一致），依赖 §2.2 的 `present:false` vs `unclear` 区分 |

---

## 8. LangChain 技术方案

### 8.1 依赖（新增到 `requirements.txt`）

```
langchain-core>=0.3.60          # Runnable / with_structured_output / abatch /回调
langchain-openai>=0.3           # 覆盖 OpenAI 及全部 OpenAI 兼容端点（DeepSeek/Qwen/Kimi/SiliconFlow/vLLM…）
langchain-anthropic>=0.3        # 可选：Claude
langchain-google-genai>=2.1     # 可选：Gemini
pymupdf>=1.24                   # PDF 解析
pdfplumber>=0.11                # 表格兜底
```

**版本兼容核查（已确认当前 venv）**：`openai 2.17.0` / `anthropic 0.78.0` / `pydantic 2.13.4` / `tenacity 9.1.4` / Python 3.13。`langchain-core` 依赖 `pydantic>=2`、`tenacity>=8.1,<10` ✅。
**安装时须确认 `langchain-openai` 的 `openai` pin 兼容 2.17.0**；若冲突，锁到支持 openai 2.x 的版本，或该模块改走 OpenAI 兼容 HTTP 直连。
LangChain 会与现有 agno 共存（agno 服务 AI 对话模块），两者共享 openai/anthropic SDK —— **装完必须跑一次现有 AI 对话回归**（§14）。

### 8.2 模型工厂（复用现有 `ai_model` 表，不重建密钥管理）

```python
# srd_engine/adapters/langchain_client.py
_LC_REGISTRY = {
    'OpenAI':    lambda c: ChatOpenAI(model=c.model_code, api_key=c.key, base_url=c.base_url, ...),
    'DeepSeek':  lambda c: ChatOpenAI(model=c.model_code, api_key=c.key,
                                      base_url=c.base_url or 'https://api.deepseek.com/v1', ...),
    'DashScope': lambda c: ChatOpenAI(..., base_url='https://dashscope.aliyuncs.com/compatible-mode/v1'),
    'Anthropic': lambda c: ChatAnthropic(model=c.model_code, api_key=c.key, ...),
    'Google':    lambda c: ChatGoogleGenerativeAI(model=c.model_code, google_api_key=c.key, ...),
    # 其余国产厂商绝大多数是 OpenAI 兼容端点 → 统一走 ChatOpenAI + base_url
}
```

API key 走现有 `CryptoUtil.decrypt(model_config.api_key)` 解密，**永不下发前端**。

### 8.3 链的组装

```python
judge_llm = (
    make_chat_model(model_cfg, temperature=0.3)
      .with_structured_output(ItemVerdict, method='json_schema')     # 结构化输出
)
judge_chain = (ITEM_PROMPT | judge_llm).with_retry(
    stop_after_attempt=3, wait_exponential_jitter=True
).with_fallbacks([backup_chain])            # 主模型不可用时切备用模型

# 34 条并发，LangChain 原生控并发
verdicts = await judge_chain.abatch(
    [item_input(it, extract_a, extract_b) for it in checklist],
    config={'max_concurrency': 8, 'callbacks': [progress_cb, usage_cb]},
)
```

- **结构化输出**：`with_structured_output(..., method='json_schema')`；不支持的模型降级 `function_calling`，再不行降 `json_mode` + 手动 pydantic 校验。
- **并发**：`abatch` + `max_concurrency`，不用自己写信号量。
- **重试/兜底**：`with_retry` + `with_fallbacks`，条目级隔离，一条失败不牵连全局。
- **进度**：自定义 `AsyncCallbackHandler`，在 `on_chain_end` 把 `{code, verdict}` 推给 SSE。
- **Token 统计**：回调里累加 `response_metadata.token_usage` 写回 `action_srd_assessment`。
- **不用 LangGraph**：流程是 P1→P2→P3 直线 DAG，无循环无条件分支，LCEL 足够；引入 LangGraph 只增复杂度。
- **不用 deepagents**：它解决开放式自主规划，与"可复算"直接冲突。

### 8.4 工程结构

```
tools/srd-engine/
├─ DESIGN.md                  # 本文档
├─ pyproject.toml             # 独立包，可 pip install -e，便于专家离线批量验证
├─ srd_engine/
│  ├─ checklist.py            # 34 条目定义 + judge_mode + facet_path（唯一真源）
│  ├─ criteria/*.yaml         # 34 条判定口径 + few-shot 案例（§4.3）
│  ├─ schemas.py              # ExtractDoc / ItemVerdict / AssessmentResult（pydantic）
│  ├─ prompts/                # 抽取×4 + 判定 + 求同 + 求异 + 仲裁，各带 VERSION 常量
│  ├─ evidence.py             # §4.4 代码取证：研究清单交并集 / 效应量比较 / 数据库集合
│  ├─ vocab/*.yaml            # 数据库名、效应指标、研究设计、RoB 工具同义词表
│  ├─ aggregate.py            # 表 2 分箱 + 表 3 矩阵（零 LLM，纯单测）
│  ├─ pdf.py                  # PyMuPDF 解析 + 章节切分
│  ├─ pipeline.py             # P1→P2→P3 编排（LCEL）
│  ├─ adapters/langchain_client.py   # 模型工厂（唯一碰 LangChain 的入口）
│  └─ cli.py                  # srd assess a.pdf b.pdf --model xxx --out result.json
├─ eval/
│  ├─ gold/                   # 20–30 对金标准（专家标注 JSON）
│  └─ run_eval.py             # 条目级 κ / 领域一致率 / 整体一致率 + 消融实验
└─ tests/                     # aggregate（表 3 全 16 格）+ evidence + 解析 单测
```

引擎**不 import 任何后端模块**，后端只做 HTTP / 鉴权 / 任务编排 / 落库 / SSE。这样 `cli.py` 能脱离 FastAPI 和数据库直接跑，方法学专家才能自己批量验证，评测循环才转得起来。

---

## 9. API 契约与前端

```
POST   /srd/documents               上传 PDF → {docId, title, pageCount, parseStatus}
GET    /srd/documents/{id}/studies  抽取到的纳入研究清单（供人工确认，§14）
PUT    /srd/documents/{id}/studies  人工修正清单
POST   /srd/assessments             {docAId, docBId, modelCode?, granularity?} → 202 {assessmentId}
GET    /srd/assessments/{id}/stream SSE：{stage, progress, itemCode, verdict}
GET    /srd/assessments/{id}        完整结果（SrdAssessmentModel + 新字段）
PUT    /srd/assessments/{id}/items/{itemId}   人工覆盖 → 服务端重算领域/整体
GET    /srd/assessments/{id}/export?format=csv|pdf
GET    /srd/assessments             我的评估历史（owner_id，配合 guest_auth_service）
GET    /srd/sample                  保留（未登录访客看示例）
```

前端 `srd.vue` 改动：上传区 + SSE 进度条 + 条目表徽标改三值（§3.4）+ 领域卡显示 "5/8" + 人工覆盖抽屉 + 导出。环形图、双语 `pick`、配色系统全部保留。

---

## 10. 成本 / 并发 / 配额（估算，需实测校正）

单次评估（两篇均未缓存，`per_item` 模式，中端模型如 DeepSeek-V3 / GPT-4.1-mini 级）：

| 阶段 | 调用数 | 输入 tokens | 输出 tokens |
|---|---|---|---|
| P1 抽取 | 2 篇 × 4 批 = 8 | ~200k | ~16k |
| P2 常规判定（27×2 + 约 7 次仲裁） | 61 | ~155k | ~31k |
| P2 辩护+裁判（7×3） | 21 | ~55k | ~16k |
| **合计** | **~90** | **~410k** | **~63k** |

- 中端模型（¥2/M in、¥8/M out）≈ **¥1.3/次**；Claude Sonnet 级 ≈ **¥13/次**
- 命中抽取缓存（"一篇 vs 库里 N 篇"）→ **~¥0.6/次**
- `per_group` 快速模式 ≈ **¥0.8/次**
- 8 并发墙钟：P1 约 60–90s + P2 约 40–70s ≈ **2–3 min**
- 配额：访客默认 3 次/日、并发 1；模型只暴露管理端白名单（`ai_model` 表）
- 失败重试：条目级独立重试 2 次（指数退避）；P1 失败保留已解析结果，可续跑

---

## 11. 质量验证（不做这步，前面全是空谈）

1. **建金标准**：方法学专家标注 **20–30 对**综述（覆盖四档：明确重复 / 部分重复 / 同主题不同方法 / 不同主题），每对给出 34 条目的 `dup/diff/unclear` + 领域档位 + 整体档位。**这是整个项目最有价值的资产**。
2. **指标**：
   - 条目级：**Cohen's κ**（三值）+ 准确率 + **假阴性率**（该判 dup 却判 diff）
   - 领域级 / 整体级：一致率 + 混淆矩阵，**重点盯低估重复的假阴性**——漏判重复综述比误判代价高得多
   - 抽取级：facet 字段准确率（~~引用可定位率~~ —— 引用回查已于 0.4.0 移除，该指标失效）
3. **验收线（建议，待专家确认）**：条目级 κ ≥ 0.65；整体判定 ±1 档一致率 ≥ 90%。
   （原「引用可定位率 ≥ 95%」随回查移除而作废；引用真伪现在完全依赖模型，
   若日后要重新度量，只能靠金标准集里的人工核对。）
4. **回归**：`eval/run_eval.py` 进 CI（用录制的 LLM 响应，不烧 token），prompt / 口径 / 矩阵任何改动都必须跑，报表进 PR。
5. **消融实验**（用数据回答两个悬而未决的问题，成本很低，务必做）：
   - **粒度**：`per_item` vs `per_group` vs `一次全给` —— 验证 §5 的判断
   - **投票**：`k=1` vs `k=2+仲裁` vs `辩护+裁判` —— 验证 §6 的判断
   - 30 对 × 5 种配置 ≈ 150 次评估，中端模型约 ¥200，一晚上跑完

---

## 12. 人工在环与可追溯

- 每条目展示：verdict 徽标 + 理由 + **A/B 逐字引用（可点击跳原 PDF 页）** + confidence + 判定方式（standard/debate）+ 投票明细（展开可见 k 次判定各自结论）
- `needs_review` 条目集中在结果页顶部"待复核 (N)"入口，一键逐条处理
- 人工覆盖立即触发 `aggregate` 重算，审计日志留 `override_by / time / reason`
- 导出报告尾页固定附：`engine_version` / `prompt_version` / `criteria_version` / `model_code` / `granularity` / 评估时间 / 被覆盖条目清单 —— **让结果可被第三方复核，这是学术工具与"AI 玩具"的分界线**

---

## 13. 实施阶段

| 阶段 | 内容 | 产出 | 预估 |
|---|---|---|---|
| **P0 骨架** | `checklist.py` 34 条目 + `aggregate.py` + 表 3 全 16 格单测 | 无需 LLM 即可跑通"给定 34 条 dup/diff → 整体判定" | 1.5 人天 |
| **P1 判定口径** | `criteria/*.yaml` 34 条口径 + 反例（**准确率的主要来源**） | 专家可评审的口径文档 | 3 人天 |
| **P2 抽取层** | `pdf.py` + 4 个抽取 prompt + LangChain 工厂 + 缓存表 | `srd extract a.pdf` → ExtractDoc JSON | 4 人天 |
| **P3 判定层** | 判定/求同/求异/仲裁 prompt + 投票阶梯 + `evidence.py` + LCEL 编排 | `srd assess a.pdf b.pdf` → 完整 JSON | 4 人天 |
| **P4 评测** | 5 对金标准先行 + `run_eval.py` + 消融实验 → 定粒度/投票/模型 | 评测报表，口径 v1 定稿 | 2.5 人天（专家标注工时另算） |
| **P5 后端接入** | alembic 迁移 + 模板数据 SQL + API + SSE + 配额 + 导出 | 接口联调完成 | 4 人天 |
| **P6 前端** | `srd.vue` 上传/进度/三值徽标/复核/覆盖/导出 | 上线 | 3 人天 |

合计 **22 人天**（与报价单「六、方法学评估工具」口径一致）。**P4 的专家标注工时需单独排**，它是准确率的前提，不是可选项。

---

## 14. 主要风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| **LLM 编造引用** | 结论不可审计，学术风险最高 | ~~**硬门槛**：引用串必须能在 `ParsedDoc.text` 中回查定位~~ —— **该缓解措施已于 0.4.0 移除**（甲方决定「就看模型的能力」）。此风险目前**无程序侧防护**，只能靠人工复核与金标准评测（§11）发现 |
| 纳入研究清单抽不全 | 6a 判定失真，而它是重复性最直接的证据 | 人工确认 UI + 与文中报告的 k 值交叉校验 + 支持手工粘贴清单 |
| 领域百分比在分箱边界抖动 | 一条之差跳档（5/8 vs 4/8） | 边界 ±5 分标"临界"，强制提示人工复核该领域 |
| `unclear` 比例过高 | 分母缩小，百分比不稳 | 领域可评估 <50% 标"证据不足"；报告显式列出 unclear 条目 |
| **LangChain 与 agno SDK 版本冲突** | 现有 AI 对话模块可能被带崩 | 装依赖后跑 AI 对话回归；必要时 SRD 引擎独立虚拟环境 / 独立服务 |
| 扫描版或异常排版 PDF | 解析失败 | v1 明确不支持扫描版；提供"手工填 facet"降级入口 |
| 口径未经专家确认就上线 | 判定标准无权威性 | P4 结束前不对外开放，先内部试用 |
| 用户误当诊断性结论 | 学术误用 | 结果页与导出件固定声明"辅助工具，结论须由方法学专家确认" |

---

## 15. 待确认（需方法学专家拍板）

1. **条目等权**是否可接受？（本设计：等权，百分比 = 重复条目占比，最易解释。若要给 6a/8b 加权，百分比就不再等于条目占比，需重新定义表 2 语义。）
2. **`unclear` 剔出分母**是否认可？还是应计入分母按"不重复"处理（更保守，会系统性压低重复度）。
3. 表 3 中「关键领域一个"无重复"一个"高度重复"」这类混合情形，Excel 未穷举——本设计归入 `both_mod_or_high`（含 high 即取最严），是否认可？
4. **验收线**（§11.3：κ ≥ 0.65、整体 ±1 档一致率 ≥ 90%）是否可接受。
5. 7 条 `debate` 条目的划分（8c / 8d / 8e / 9 / 10b / 11 / 12b）是否恰当，是否有其他条目也应升级为辩护模式。
