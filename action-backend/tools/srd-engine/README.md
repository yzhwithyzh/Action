# srd-engine

SRD（Systematic Review Duplication，系统综述重复性评估）引擎。
给定两篇系统综述 → 34 条目逐条由 LLM 打 0–3 分 → 代码按表 2 / 表 3 算出领域与整体判定。

技术路线与方法学依据见 [DESIGN.md](DESIGN.md)。

> **0.7.1**：整体判定理由（`overall_reason_zh/en`）只讲查表这一步，不再逐领域复述
> 「得分 13/24（重复度 46%）低重复」—— 同一份报告里领域小节本来就逐个列着，
> 抄第二遍只会把「怎么得出这个结论的」埋进一段数字里。判定逻辑一字未动，
> 但缓存键含 `ENGINE_VERSION`，升版本即全量重抽一次。

## 条目评分（0.7.0 起）

新版 Excel 表 1 给每个条目加了一列评分，引擎照搬这四档（**0.8.0 起分数方向已翻转**）：

| 分 | 含义 | 说明 |
|---|---|---|
| 3 | 完全相同 | 满足该条目的「3 分锚点」，没有可观察的差异 |
| 2 | 部分相同 | 主体一致，差异**不会改变**临床或方法学解读 |
| 1 | 部分不同 | 存在**会改变**解读的实质差异，但仍有明确共同部分 |
| 0 | 完全不同 | 满足该条目的「0 分锚点」，没有实质共同点 |
| —  | 证据不足 | 引擎自己的第五态 `unclear`：不计分，也不进分母 |

> ⚠️ **甲方 Excel 表 1 的表头写的是相反的「完全相同 0 分 … 完全不同 3 分」。**
> 0.7.x 照抄了那张表；0.8.0 按甲方后来的定稿改成「分数即相似度」。拿那份 xlsx 来核会读反，
> 口径的唯一真源是 `srd_engine/schemas.py` 的 `RATING_LABEL_*`。

- **分越高越重复**，与百分比方向一致（0.7.x 是相反的，读老结果时注意）。
- 领域满分 = 3 × 条目数 → 领域1 /24、领域2 /18、领域3 /42、领域4 /18，合计 **/102**
  （`checklist.py` 里对这四个数有断言，改清单结构会立刻失败）。
- 领域重复百分比 = 得分 ÷ 可评分满分 × 100，之后照旧走表 2 分箱、表 3 查表。
- **与 0.7.x 兼容**：分数方向与百分比公式一起翻，净效果是
  **pct / level / overall_level 一格不动** —— 同一次评估在两版下结论完全相同。
  0.7.x 的结果 JSON 读进来会按 `engine_version` 自动翻转
  （`AssessmentResult` 上的 `_accept_legacy_rating`）；库里的存量数据走
  `sql/013-action-srd-score-flip-pg.sql`。
- **与 0.6.0 兼容**：老口径是「dup 条数 ÷ (dup + diff)」。全部条目只打 3 或 0 分时，
  新公式退化成完全相同的数值；0.6.0 的历史结果 JSON 读进来会自动折成 3/0 分
  （`ItemResult` 上的 `_accept_legacy_verdict`），重算百分比与当年一致。
- 3 分与 2 分折成旧的 `dup`、1 分与 0 分折成 `diff`，仅供展示与前端兼容，
  **不参与百分比计算** —— 否则 2 分与 3 分就没区别了。
  （这层映射在翻转下**不变**：0↔3、1↔2 对调后恰好还落在原来那一侧。）
- 2 分 / 1 分目前只有一条通用口径（差异会不会改变临床或方法学解读），写在
  `prompts.py` 的系统提示词里，34 个条目共用；逐条的专属锚点待金标准集建立后再回填到
  `criteria/*.yaml` 的 `score_note`。**这两档未经方法学专家评审，人工复核时请重点看。**

条目编号也随新版 Excel 改了一处：原来的 `9` 现在是 `9a`。

## 当前状态

**纯引擎，零后端耦合**。本包不 import 任何后端模块，不碰数据库、不碰 HTTP，
可以 `pip install -e .` 后用 CLI 独立跑。后端接入是后续独立的一步（见文末「后端接入契约」）。

已实现：

| 模块 | 职责 | 是否需要 LLM |
|---|---|---|
| `checklist.py` + `criteria/*.yaml` | 34 条目清单与判定口径（唯一真源） | 否 |
| `aggregate.py` | 表 2 分箱 + 表 3 矩阵 → 领域与整体判定 | 否 |
| `evidence.py` + `vocab/*.yaml` | 3a/6a/8b 的客观事实计算（Jaccard、CCA、效应量比较） | 否 |
| `pdf.py` | PDF/文本解析、章节切分 | 否 |
| `extract.py` | P1 单篇 facet 抽取（4 批次并发 + 缓存 + 剔参考文献 + 超长兜底） | 是 |
| `judge.py` | P2 条目判定：默认 34 条一次调用；少返条目补 unclear | 是 |
| `pipeline.py` | P0→P3 编排 + 进度回调 | 是 |
| `report.py` / `cli.py` | 文本报告、CSV 导出、命令行 | 否 |

测试 148 个，其中聚合、口径、取证、解析、超长兜底、批量判定全部可离线跑（不烧 token）。

**单次评估 9 次调用**：8 次抽取（每篇 4 批次）+ 1 次判定（34 条一次给）。

## 安装

```bash
cd tools/srd-engine
pip install -e ".[pdf,dev]"          # 需要 Anthropic / Gemini 时再加 ".[anthropic,google]"
```

依赖：`pydantic` `pyyaml` `langchain-core` `langchain-openai`，PDF 解析额外需 `pymupdf`。

> 注意：本项目后端已装 `agno`，两者共享 `openai` / `anthropic` SDK。
> 若后续把引擎装进后端环境，务必先跑一遍现有 AI 对话回归（DESIGN.md §14）。
> 引擎本身不依赖后端，也可以放在独立虚拟环境或独立服务里跑。

## 配置

```bash
export SRD_PROVIDER=DeepSeek        # OpenAI / DeepSeek / DashScope / Anthropic / Google / …
export SRD_MODEL=deepseek-chat
export SRD_API_KEY=sk-xxx
export SRD_BASE_URL=                # 留空则用 provider 默认端点
export SRD_MAX_TOKENS=              # 可选，输出上限
```

绝大多数国产厂商是 OpenAI 兼容端点，统一走 `ChatOpenAI` + `base_url`，
`adapters/langchain_client.py` 里有内置的默认 base_url 表。

## 用法

```bash
# 不调模型，纯离线
srd checklist                          # 看 34 条目清单（标出主观条目与带证据卡的条目）
srd criteria 2b                        # 看某条目的判定口径
srd aggregate examples/verdicts-sample.json   # 由条目判定直接算领域/整体
srd parse review-a.pdf                 # 看解析出的章节结构

# 调模型
srd extract review-a.pdf -o a.facet.json      # 只跑单篇抽取（结果可复用）
srd assess review-a.pdf review-b.pdf -o result.json --csv result.csv -v
srd assess a.facet.json b.facet.json -o result.json    # 用已抽好的 facet，跳过解析与抽取

# 常用开关
srd assess a.pdf b.pdf --cache .srd-cache        # 开抽取缓存（「一篇 vs 库里 N 篇」场景必开）
srd assess a.pdf b.pdf --granularity per_group   # 12 次调用；per_item 则 34 次。都不推荐，见下
srd assess a.pdf b.pdf --extract-scope sections  # 只喂命中的章节（不推荐，见下）
```

`srd aggregate` 的输入就是一份 `{"1a": "0", "1b": "3", ...}`（也照收 0.6.0 的
`{"1a": "dup", ...}` 老文件），方法学专家不用碰模型就能验证「条目评分 → 整体结论」
这条链路和 Excel 是否一致。

### 批量跑一个目录（run_batch.py）

```bash
python run_batch.py                       # 跑 系统综述/ 下全部 A/B 配对，已有结果的跳过
python run_batch.py 1 2 3 --force         # 只跑指定编号并覆盖
python run_batch.py --from-db             # 模型改从 ai_models 表取（与 worker 同源，密钥不落 shell）
python run_batch.py --granularity per_group --concurrency 3 --timeout 600
python export_excel.py out-0.7.0          # 把结果导成人工核对用的 Excel
```

`--granularity per_group`（12 次调用 / 对）在**输出慢或单次输出上限低的模型**上比默认的
`all`（34 条一次）稳得多：`all` 一次要吐约 1.7 万 token，实测某些国产端点会直接超时或截断，
截断的条目全部降级成 unclear。换模型时记得同时换 `--out` 与 `--cache`。

### 跑之前先确认输入是干净的

```bash
for f in 系统综述/*.pdf; do python -c "
from srd_engine import pdf; d = pdf.parse('$f'); print(len(d.full_text), d.sha256[:8], '$f')"; done
```

字符数为 0 是扫描版；**两个不同编号的文件 sha 相同**说明目录里有重名同文，
配对会变成「自己跟自己比」；文件名与内容对不上的也只有这样才看得出来
（本目录实测 `7B` 的文件名写着 constipation，内容其实是 `1A` 那篇 depression）。

## 四条设计约束（改代码前先读）

1. **判定默认一次调用判完 34 条**（`judge_granularity='all'`）。
   DESIGN.md §5/§6 原设计是「一条目一次调用 + k=2 投票 + 分歧仲裁 + 7 条主观条目双证据辩护」，
   共 76 次调用。§11.5 的消融实验做完后该设计被推翻（4 对 × 34 条目实测）：

   | 对照 | 一致率 |
   |---|---|
   | `per_item` 自己重跑两遍 | 95% |
   | `all` 自己重跑两遍 | 95% |
   | `per_item` vs `all` | 90% |

   **两种模式的自一致率完全相同**，即 76 次调用没有换来更稳的输出；跨模式那 5 个百分点
   与同配置重跑的抖动无法区分。代价却是 76 倍调用、6 倍 token。故可靠性阶梯整体删除。
   `--granularity per_group|per_item` 作为选项保留，不推荐。

2. **分数只由代码算**。`aggregate.py` 是唯一决定最终结论的地方，零 LLM。
   领域百分比 = 判为 `dup` 的条目数 ÷ (`dup` + `diff`)，`unclear` 剔出分母。
   表 3 的 16 格在 `tests/test_aggregate.py` 逐格断言。

3. **抽取默认喂整篇原文**（`extract_scope='full'`）。
   这是实测唯一被量化验证有效的改动：按章节关键词挑正文喂给模型时，只要标题识别不准
   就会静默丢掉关键段落（实测 2B 的 method 批次只喂进 602 字符，而全文里
   PubMed/Embase/CNKI 都写着）。三轮对照：分章节 70% 字段填充率 vs 全文 87%，
   unclear 从 187 降到 128。`--extract-scope sections` 保留但不推荐。

4. **`present='no'` 与 `present='unclear'` 不可混同**。
   两篇都明确写了「未做敏感性分析」是**方法一致**（判 `dup`）；
   两篇都没写清楚是**证据不足**（判 `unclear`，剔出分母）。
   抽取提示词、判定提示词、聚合三处都依赖这个区分。

5. **一条都没评出来时不查表**，`overall_level` 判成 `None`。
   部分领域证据不足时按「无重复」参与查表是刻意的（`_effective_level` + `provisional` 标记）；
   但四个领域**全部**没有可评分条目时，这条规则会凭空凑出一个 `none` ——
   而 `none` 在前台就是「无重复」，跟「两篇综述毫无重复」长得一模一样。
   实测踩过：判定输出被截断，34 条全 unclear，报告以「无重复」收尾。
   现在这种结果没有档位、有一句「无法判定」的理由，worker 侧还会把任务判失败。

## 抽取的正文处理

1. **参考文献段一律剔除** —— 找最后一个独占一行的 `References` / `参考文献` 标题，砍到文末。
   它对 34 个条目的判定没有贡献，却占全文 17%–33%（实测 12 篇里 11 篇命中，合计省 20% 输入）。
   刻意做得粗糙（连附录一起砍也接受）；砍超过 60% 判为认错，放弃（实测 5A 就走了这条）。
2. **剔除后仍超过 12 万字符才分块** —— 按行边界、按「剩余字符 ÷ 剩余块数」均摊切块，
   每块单独抽取后合并。常规期刊综述走不到这一步。
   合并规则：列表跨全部块取并集，facet 取 `yes > no > unclear`。
   分块时提示词会追加「你看到的不是完整文献，找不到就填 unclear，绝不可填 no」，
   合并时 `present='no'` 必须带引用否则降级 —— 这两道是分块路径上仅有的假 dup 防线。

两步都会记进 `warnings` 并随 facet 落盘，绝不静默。

3. **失败或抽空的批次补跑**（0.7.0，`MAX_EXTRACT_ROUNDS = 3`）—— 有些 OpenAI 兼容端点
   在长输入下会「HTTP 200 + 合法结构 + 字段全空」，不报错也不重试。对一篇真实的系统综述
   来说整批 facet 全空不可能是真相，`is_empty_facets` 认出来后重跑该批次。

   **抽取失败的代价被放大几十倍**，所以这里比判定层更值得重试：一篇抽一次、34 条判定
   都吃这一份 facet，`result` 批次空掉，这篇参与的**每一对**配对的 14 个条目全判 unclear。
   实测 10 对那轮 6 次抽空里第 2 轮救回 3 次，剩下 3 次直接造成 90 条 unclear（占一半）。

4. **残缺的 facet 绝不写缓存**（0.7.0）—— `ExtractDoc.failed_batches` 非空时
   `prepare_extract` 不落盘，命中了这种旧缓存也丢掉重抽。
   不做这层的话，一次抽取失败会被永久固化：后面所有配对命中缓存直接复用空壳，
   **再也不会重抽**（实测 5B/9B/10B 是同一篇，它一次失败污染了 3 对）。

## 对不老实的模型端点的三层兜底（0.7.0）

用国产 OpenAI 兼容端点跑这套流程时踩到的坑，都在 `adapters/langchain_client.py`
与 `judge.py` 里就地兜住了，而不是让它们变成一份「什么都没判出来」的报告：

| 症状 | 兜底 |
|---|---|
| `response_format.type: json_schema is not supported by this model`（400） | 按 `METHOD_ORDER` 逐级降到 `function_calling` → `json_mode` → `text`，结果**按模型粘住**（见下） |
| 模型不回填条目编号 `code` | 返回条数与题目条数一致时按顺序对位，并把「按返回顺序对位」写进 `review_note` 留痕 |
| 抽取批次返回空壳 | 补跑（见上），且残缺的 facet 不写缓存 |
| **JSON 解析不出来 / 不符合 schema** | 抛 `StructuredParseError` 进重试梯子（见下） |

前两条都是「换模型也没用、重试也没用」的确定性错误，所以不能靠 `FailoverConfig` 的
冻结切换解决 —— 那只对限流/欠费/5xx 有意义。

### 结构化输出方式按模型定

`ModelConfig.structured_method` 决定这个模型从哪种方式起步，取值即 `METHOD_ORDER`：

| 方式 | 谁来保证结构 |
|---|---|
| `json_schema` | 服务端按 JSON Schema 约束解码，最稳，默认起点 |
| `function_calling` | 走工具调用，兼容面最广 |
| `json_mode` | 只保证是合法 JSON，字段对不对得自己验（所以会把 Schema 写进提示词） |
| `text` | 纯文本 + 自己抠 JSON（剥围栏、截首尾大括号），什么都不保证，最后一档兜底 |

留空＝运行时探测：从 `json_schema` 起，撞到「不支持」就降一级重试。

两个刻意的设计：

- **按模型记，不按 runner 记**。池子里可能混着不同厂商，A 只支持 `function_calling`
  不代表 B 也不支持 `json_schema` —— 拿 A 的结论套 B 会把好模型白白降级。
- **降级只降一级、且按「本次实际用的方式」对账**（`_demote_method` 的 `failed` 参数）。
  抽取是并发发出去的，十几个请求会同时撞上同一堵墙；不对账的话一次错误降一级，
  一口气从 `json_schema` 掉到 `text`。

探测很贵：它是拿一个**真实请求**去撞的，而抽取阶段的请求带着整篇综述正文，
实测撞一次要几分钟。所以 `resolved_methods()` 把结论交出去，worker 侧回写
`ai_models.structured_method`，下个任务直接命中。

### 解析失败为什么要单独说

`_dispatch` 那条重试/切换梯子是**靠捕异常驱动**的，而解析失败没有异常：
HTTP 200，LangChain 把它塞进 `parsing_error` 字段。所以它天然会绕过整条梯子 ——
0.7.0 之前的写法是调用返回后事后读一下这个字段就返回错误，一次都不重试。
代价在判定侧最明显：`judge_batch` 拿不到对象就把**整组条目**降级成 unclear，
`per_group` 一次废 5 条，`all` 模式一次废 34 条。

现在 `structured()` 在 `run()` 里就把它抛成 `StructuredParseError`，和 429、5xx 走同一条路
（原地重试 `max_retries` 次 → 换模型 → …）。

**而且重试不是原样重发** —— 这一点对解析失败是决定性的：抽取与判定都跑在
`temperature=0` 上，同一份提示词再问一遍多半原样再错一遍，盲重试等于白烧 token。
所以下一次会把上次的输出与解析报错追加成一条纠错消息（`repair_message`）：

```
解析器报错：Invalid json output: {"code": "8c", "reason_zh": "两篇对干预效应…
你上一次的输出：--- 开始 --- …（留头留尾，中间省略）… --- 结束 ---
重新输出时务必做到：… 3. 如果上次是被截断的，请把每个字段写得更精简，保证 JSON 完整闭合 …
```

第 3 条是唯一能让**截断**自愈的路子：34 条判定一次要吐约 1.7 万 token，撞上单次输出
上限就断在半路，只有让模型自己把理由与引用写短才出得来。原始任务消息原封不动地留着，
纠错只追加不替换，避免它借着纠错改判断。

另外两点：

- `classify_error` **先按异常类型判掉它，再扫关键词** —— 它的消息里裹着模型的原始输出，
  综述正文出现「限流」「敏感」都不奇怪，扫关键词会把它错判成换模型或直接判死。
- 失败那次的 token 照样记账（`_count` 在抛之前调），否则用量统计会偏低。

> **注意**：0.4.0 起**不再回查引用是否真在原文中**（甲方决定「就看模型的能力」），
> `page` 字段一并废弃，报告与 CSV 不再显示页码。`quote` 仍要求逐字，供人工复核用。
> DESIGN.md §11.2 的「引用可定位率 ≥ 95%」验收指标随之失效。

## 版本号

`config.py` 里三个常量必须随改动手动升版本，否则历史结果无法解释：

- `ENGINE_VERSION` —— 代码逻辑（聚合算法、判定粒度、抽取行为）。**同时是抽取缓存 key 的一部分**，
  升它会让全部历史缓存失效并重抽，这是刻意的：抽取行为由引擎代码决定，不纳入 key
  就得靠「改引擎时记得顺手改提示词」这种人工纪律。
- `PROMPT_VERSION` —— `prompts.py`（同样是抽取缓存的 key 之一）
- `CRITERIA_VERSION` —— `criteria/*.yaml` 判定口径

## 待补（DESIGN.md §11）

- `criteria/*.yaml` 的 `examples` 字段为空，待金标准集建立后回填 few-shot 案例
- `eval/` 评测脚本（条目级 κ / 领域一致率 / 消融实验）尚未实现，需要先有专家标注的金标准对
- 判定口径 v1 未经方法学专家评审，DESIGN.md §15 列了 5 个待拍板问题

## 后端接入契约（后续一步，暂不实现）

接入时后端只需做四件事，引擎侧零改动：

1. **注入模型**：从 `ai_models` 表取配置、`CryptoUtil.decrypt` 解出 key，构造 `ModelConfig` 传进去。
   给**一组** `ModelConfig` 就会启用「粘性 + 出错切换」：撞到限流/欠费/鉴权/5xx 时冻结当前模型
   （默认 5 分钟，`FailoverConfig` 可调）并切下一个。冻结状态存哪由调用方决定 ——
   传 `health=` 就用共享存储（worker 传的是 Redis 实现，多进程共用），不传就是进程内存。
   `ai_models` 的主键要塞进 `ModelConfig.ref`：同一个 provider/model 可能是两个账号，
   各有各的并发额度，冻结必须按账号算。
2. **接进度**：`assess(..., on_progress=fn)`，`fn(stage, done, total, detail)` 转成 SSE 事件。
3. **落库**：`AssessmentResult` 的层级与现有 `action_srd_assessment / domain / group / item` 一一对应，
   需新增的字段见 DESIGN.md §3.3。抽取缓存表的唯一键需含 `engine_version`（见「版本号」）。
4. **人工覆盖重算**：改 `ItemResult.override_verdict` 后重新调 `aggregate(result)` 即可，不必重跑 LLM。

引擎不认识 FastAPI、SQLAlchemy、HTTP、鉴权。换掉 LangChain 也只需重写
`adapters/langchain_client.py` 一个文件。
