# checklist_worker_tool —— 报告规范校验 worker

报告助手**第三步**的算力后端，一次任务出两类判定：

1. **逐条完整性**（`engine/audit.py`）—— 「这条报告了没有、报在第几行」，
   也就是投稿时那张 checklist 最后一列要填的东西；
2. **全稿逻辑一致性与术语标准化**（`engine/consistency.py`）—— 「各处对不对得上」：
   干预与对照有没有写混、针刺频次与随访时点是否矛盾、样本量依据与纳入例数是否匹配、
   穴位名称是否用了标准写法。

两类判定分在两个模块，是因为**证据的作用域根本不同**：完整性的证据是局部的，可以切窗并发；
一致性的矛盾天生跨段落（方法在前、结果在后），切窗等于让模型只看半篇找矛盾，既漏又误报。

公共骨架（配置、队列、状态、日志、停止、优雅关闭）见 [`tools/common/README.md`](../common/README.md)，
这里只写本工具特有的部分。

## 跑起来

前台调试：

```bash
cd action-backend
python -m tools.checklist_worker_tool
```

工作目录必须是 `action-backend/`（要用同一份 `.env` 连数据库取条目与模型配置）。

后台常驻，用 `action-backend/` 下那套运维脚本（与 `*_srd_worker.sh` 同一种形态）：

```bash
cd action-backend
cp .env.checklist-worker.example .env.checklist-worker   # 首次：填 Redis / 队列名
APP_ENV=prod ./start_checklist_worker.sh                 # 不传 APP_ENV 就是 dev
./status_checklist_worker.sh                             # 进程 + 队列长度 + 最近日志
./stop_checklist_worker.sh                               # 优雅停，等在跑的校验收尾
./restart_checklist_worker.sh
```

| 文件 | 干什么 |
|------|--------|
| `start_checklist_worker.py` | 真正的入口，等价于 `python -m tools.checklist_worker_tool`，另加 `sys.path` 与 SIGTERM 兜底（Windows 的事件循环装不上 `add_signal_handler`） |
| `_checklist_worker_common.sh` | 路径 / 解释器 / PID 判定，被下面四个脚本 source，不要直接执行 |
| `start`/`stop`/`restart`/`status_checklist_worker.sh` | 后台拉起、优雅停、重启、看状态 |
| `.env.checklist-worker.example` | `CHECKLIST_WORKER_*` 的模板（**纯 KEY=VALUE 的 shell 语法**，不是 `.env.prod` 那种 dotenv 写法） |

两个坑，踩过就明白为什么脚本写成这样：

- **`APP_ENV` 必须显式传成 `--env`**。`config/env.py` 靠命令行参数选 `.env`，光设环境变量会被它
  覆盖回 `dev` —— 表现是「生产机上起了 worker，却在往开发库里查条目」。
- **PID 要核命令行，不能只判进程活着**。worker 崩过之后 PID 会被系统复用，
  只判存活的 stop 脚本会去 kill 一个无关进程。`checklist_is_worker_pid()` 匹配 `checklist_worker`，
  两种起法（本套脚本 / systemd 的 `python -m`）都认得。

**后端进程与 worker 必须拿到同一份 `CHECKLIST_WORKER_REDIS_*` 与 `QUEUE_NAME`**，
否则一个投一条队列、一个守另一条，官网上提交的校验永远排队没人取。
`./status_checklist_worker.sh` 打印的队列长度就是用来验这件事的。

## 投递端 CLI

不开浏览器跑通整条链路（`status` 脚本查队列也是调它）：

```bash
python -m tools.checklist_worker_tool.cli submit draft.txt --guideline STRICTA
python -m tools.checklist_worker_tool.cli logs   <session_id> -f
python -m tools.checklist_worker_tool.cli status <session_id>
python -m tools.checklist_worker_tool.cli stop   <session_id>
python -m tools.checklist_worker_tool.cli queue
```

稿件用 `-` 表示从 stdin 读；`--guideline` 是 `action_guideline.code`。
模型不在这里指定（本工具没有环境变量兜底），`--model-ids` 只能把 `ai_models` 的池子缩小到其中几个。

## 数据从哪来

| 东西 | 来源 |
|------|------|
| checklist 条目 | `action_guideline_item` 表，由 `tools/extract_checklists.py` 从各规范中英文 docx 抽取入库，后台「规范条目管理」页可增删改 |
| 模型 | `ai_models` 表的可用池子，按 `model_sort`「粘性 + 出错切换」（见公共 README 第 4 节）；本工具**不设环境变量兜底**——官网前台在调它，配置必须从后台可见可控 |
| 稿件 | 任务 payload。**worker 这一侧**只在 Redis 队列与进程内存里流转、不写库；但官网后端在提交时已把稿件存进 `action_report_review.manuscript`（014 起，为了校验历史可回看，用户删除记录时物理清空）。worker 的 `results/<sid>.json` 留档里有逐条引文等原文片段，**目前不会被清理** |

## 任务 payload

```json
{
  "session_id": "uuid",
  "guideline_code": "STRICTA",
  "manuscript": "稿件全文……",
  "locale": "zh",
  "engine": {
    "batch_size": 8,
    "max_concurrency": 4,
    "consistency": { "max_chars": 60000, "max_concurrency": 2, "max_findings": 20 }
  },
  "model_ids": [3, 7]
}
```

后端不 import 本工具的内部实现，只用 `TaskClient + CONFIG` 投递与查询，
接口在 `module_action/controller/action_site_controller.py`：

```
POST /action/site/checklist-review            提交，返回 session_id
GET  /action/site/checklist-review/{sid}      轮询状态，完成后 result 里带逐条判定
POST /action/site/checklist-review/{sid}/stop 停止
```

三个接口都要访客登录，提交接口另挂限流 —— 一次校验是几十次模型调用。

## 算法一：逐条完整性（`engine/audit.py`）

```
切窗口 → (条目分批 × 窗口) 并发判定 → 引文回原文定位 → 同条目跨窗口取最优 → 聚合完整度
```

- **不给模型看行号、不让它报行号**：模型看到的是原文本身，只负责逐字照抄引文；
  「在第几行」由 `engine/grounding.py` 在原文里查出来（见下一节）。
- **切窗口**：稿件超过 `window_chars`（默认 6 万字符，与全稿一致性同一个预算）时按行切成
  重叠窗口，常见论文不必切。单行超长时先硬切（窗口里没有行号，劈开一行不影响定位）。
- **取最优**：`reported > vague > missing`；同档位先取引文找到了的，再取有位置的。
  只要有一个窗口找到了证据，这条就算报告了。
- **聚合**：完整度 =（已报告 × 1 + 模糊 × 0.5）/ 总条目数。

几条刻意的保守设定，都有单测盯着（`tools/tests/test_checklist_audit.py`）：

| 情况 | 处理 | 为什么 |
|------|------|--------|
| 模型漏回某条 | 先按解析失败走纠错重试；仍漏的放宽结构再要一次；始终没回的记 `missing` 并挂「模型未返回该条的判定」 | 漏判必须表现为「没报告」，但要和「模型看过、判为没写」分得开 |
| 多窗口时有窗口没判到这条、判到的都说没写 | 记 `missing` 并挂「部分片段未能完成判定」 | 证据可能恰好在没判到的那段 |
| 模型回了不在当批的编号 / 重复编号 | 当作解析失败走纠错重试，**不静默丢弃** | 实测 qwen3.8-flash 发 8 条回 18 条，多出来的是编的，同批其余判定也不可信 |
| 模型把标签写成 `"[a]"`、`" b "` | 去括号去空白转大写照收 | json_mode / text 路径下没有约束解码，不收口的话整批 8 条全变未报告 |
| 一批只有一条 | Schema 仍写 `enum` 而不是 `const` | 有的厂商不认 `const`，会降级结构化输出方式并被回写进 `ai_models` |
| 判了「未报告」却附了引文 | 引文与位置一律清空 | 留着的话导入回填会把不相干的原文填进条目框 |
| 判了「已报告 / 模糊」却一段引文都没给 | 判定不变，标 `located='none'`，前台提示「未附原文依据」 | 见下一节「只打标不改判定」 |
| 引文在原文里找不到 | 判定不变，没有位置，标 `located='no'`，前台提示人工核对 | 同上 |
| 整批判定失败 | 该批按 `missing`，错误进结果的 `errors`，前台顶部提示「部分判定未完成」 | 不能因为一次网络抖动就把结论抬高；也不能让「没判成」看着像「判了没写」 |
| 稿件超 `max_chars` | 截断并在结果里标 `truncated` | 让用户知道后半段没被看过 |

## 换模型时效果不许大起大落

模型池按 `ai_models` 切换，同一份稿子换个模型跑，结论可能差很多（实测见下）。
所以**凡是代码能定的事都不交给模型**，模型只负责语义判断：

| 以前交给模型 | 现在由代码定 | 在哪 |
|------|------|------|
| 条目编号原样回填 | 条目标成批内字母 `[A]`…，Schema 枚举每批相同（缓存才命中得了），越界/重复/漏回走纠错重试，字母由代码换算回主键 | `audit._batch_schema` |
| 行号 | **模型不接触行号**；位置由代码拿引文去原文里查 | `engine/grounding.py` |
| 一致性发现的严重度 `severity` | 模型只交「几段原文 + 是否违反」，按「定位到几处不同位置」定级 | `consistency._severity` |

**位置由代码查**：引文先整段精确匹配（归一化后比，能跨行），找不到再做模糊比对
（字符 n-gram 覆盖率 ≥ 0.75，且**引文里的数字必须原样出现** —— 「第 300 行」与「第 30 行」
覆盖率 0.94，不设这道闸会被定位到别处）。同一段话出现多处时**全部标出**（最多 5 处），
不替模型猜一处。行号是本站给粘贴稿自编的号（空行不计），只在系统内部用（前台「在原文中查看」
的高亮、导入回填按行取段落、一致性判两处），页面上不显示「第 N 行」。

**核对只打标、不改判定**，这条是校准出来的：朴素的精确子串核对会把 deepseek
20%–45% 的正确判定判成「证据不实」（省略号拼接、PDF 分页打断、英文稿给中文译文……）；
改成分段 + 模糊比对后误伤降到 0，但 qwen 被标「完全找不到」的全是**用概述代替引文**、
条目本身判对了的情况，拿它降级就是误伤。细节与数据见 `grounding.py` 文件头。

2026-09 用 4 篇真实论文（中文 RCT ×2、英文 RCT、英文研究方案）实测过三个模型，
改造前的主要问题：qwen3.8-flash 批内条目编号错位、编造等差数列行号；qwen3.7-plus 逐条判定
正常，但全稿一致性 16 项里判了 16 个 `issue`，其中好几条说明里自己写着「逻辑吻合」。
**百炼的 qwen 默认开思考模式**，而思考模式会把条目编号回成 1、2、3…… —— 接这类模型前
要确认思考真的关掉了。开关是 `ai_models.support_reasoning`（后台「支持推理」），非 `Y` 时
worker 按端点下发对应的参数（火山方舟/DeepSeek `thinking`、百炼 qwen `enable_thinking`，
见 `utils/llm_thinking_util.py`）。实测 qwen3.8-flash 默认思考、关掉后推理 token 归零。

## 算法二：全稿一致性与术语（`engine/consistency.py`）

```
按字符预算截断 → 整篇（不切窗）每条规则一次并发请求 → 引文定位 → 代码定级 → 聚合状态
```

四条规则在 `RULES` 里，`key` 就是前台文案的锚点（`assistant.ckRule.<key>`）——
**加规则要同步加 i18n 词条并进 `action_site_text`**，否则前台只会显示出键名本身。

| key | 查什么 |
|-----|--------|
| `arm` | 干预措施与对照组的描述有没有混淆 / 前后打架 |
| `schedule` | 针刺频次、疗程与随访时间点在各处是否一致 |
| `sample` | 样本量计算依据与实际纳入 / 分析例数是否匹配 |
| `acupoint` | 穴位名称是否用了标准穴名 + 国际代码（术语标准化） |

每条规则五档状态，**后两档是这一层最容易骗人的地方，务必分开显示**：

| 状态 | 含义 |
|------|------|
| `ok` | 跑过了，未发现问题 |
| `warn` | 有疑点，需人工确认（逻辑类只定位到一处原文，或引文找不到） |
| `issue` | 逻辑类：两段引文定位到**不同位置**；术语类：定位到一处即可（写错了就是写错了） |
| `na` | 该研究类型不涉及这项检查（系统综述没有自设对照组等），由模型判定 |
| `unchecked` | **没跑成**（模型调用失败）—— 既不是有问题也不是没问题 |

定级由 `_severity` 按上表算，**模型的输出里既没有 severity 也没有行号**：旧结构让它第一个
字段就填 severity，模型逐字生成，先写下「issue」再写说明，于是说明与定级自相矛盾。
现在模型按「原文（quotes）→ 说明 → 建议 → 是否违反（violates）」的顺序填，
`violates=false` 的发现直接丢掉；位置由代码查，查不到的引文不算一处。

保守设定，同样有单测盯着（`tools/tests/test_checklist_consistency.py`）：

| 情况 | 处理 | 为什么 |
|------|------|--------|
| 某条规则请求失败 | 停在 `unchecked`，写进 `errors` | 显示成「未发现问题」等于把没跑过的检查算成合格 |
| 引文在原文里找不到 | 不算一处，逻辑类凑不够两处就是 `warn` | 连原文都对不上的「矛盾」够不上标红 |
| 同一段话引两次 / 一段落在另一段的某个出现处 | 算一处 | 可能是同一个地方，宁可少标红 |
| 模型自己判 `violates=false` | 丢掉 | 它核对下来发现没问题了，列出来只会被显示成问题 |
| `applicable=false` 但列了问题 | 按问题算，不判 `na` | 不许用「不适用」吞掉已经指出来的问题 |
| 发现没有原文、说明、建议中的任何一样 | 丢掉 | 无从核起的「问题」等于噪声 |
| 同类发现超过 `max_findings` | 规则状态按**全部**发现算；截取前把 issue 排到前面；标 `capped` | 先截再算会把后面的 issue 藏掉 |
| 稿件超 `max_chars`（默认 6 万字符） | 按整行截断并标 `truncated`；定位只在模型看到的那部分里查 | 后半段是真没看，不该有引文落进去 |
| 首行本身就超预算（整篇没有换行） | 把这一行硬截到预算长度 | 按整行截会一行都不剩，模型拿着空稿件全判「未发现问题」 |

**全稿校验整体失败不拖垮任务**：逐条完整性已经跑完，为最后这四次请求把几十次调用的结果
作废没有道理 —— 失败时回一个全 `unchecked` 的空壳，任务照常 completed。

算法不认识 Redis / HTTP / 队列，只要一个满足 `Runner` 协议（`structured()`）的调用器；
LLM 适配层（模型池、故障切换、token 计数）复用 `tools/srd-engine` 里的 `LlmRunner` ——
那部分是基础设施不是 SRD 算法，重写一份只会让两处的切换行为漂移。

## 用量与前缀缓存

任务收尾时日志里打一行「调用 N 次 / 输入 X（命中缓存 Y，Z%）/ 输出 W（其中思考 R）」，
同样的数字连同逐模型明细进留档文件的 `usage`。每次调用都带着整篇稿件，
**命中率直接决定输入成本**；厂商不报命中数时记 0，与「没命中」分不开。

2026-09-23 实测（火山方舟 deepseek-v4-flash · function_calling · 一篇 1.9 万字中文 RCT × STRICTA 78 条，
`support_reasoning='N'`）：

```
                  思考开着（worker 当时不认那个字段）   思考关掉（认了之后）
输出 token        77.5k                               8.2k
耗时              317 秒                              34 秒
逐条判定           已报告 36 / 模糊 15 / 未报告 27        39 / 15 / 24
全稿校验           issue 2 · ok 2（发现 12 条）          issue 2 · ok 2（发现 6 条）
输入              136.8k，命中 12%                    见下表
```

- **此前后台配了「支持推理=否」，worker 照样思考**：`model_registry` 没读这一列。
  思考的输出按输出价计费，是这个任务最大的一笔开销

前缀缓存（2026-09-24，**每次都换一篇没跑过的论文**，量的是首跑命中率）：

```
                          逐条判定命中   整个任务命中
改造前（按批生成主键枚举）         0%          12%
字母标签（Schema 每批相同）       54%          50%    ← 前 4 批并发起跑，都没吃到
+ 先预热再并发                  86%          81%    ← 只剩逐条、全稿各第一次不命中
```

三处设计都是为了「同一次任务里请求的开头逐字相同」，改动前先想清楚会不会破坏它：

- **条目标签用批内字母 `[A]`…，不用库主键**（`_batch_schema`）：function_calling / json_schema 下
  Schema 渲染在提示词**最前面**。旧写法每批生成 `enum: [101..108]`、`[109..116]`……，开头一变，
  后面整篇稿件都算未命中；顺序发出的后几批同样是 0，所以不是并发的问题
- **Schema 在一次任务内逐字不变**：枚举固定是 `LABELS[:批大小]`，最后一批不满时靠校验器兜底；
  strict 与放宽两种 Schema 文本也相同。`test_schema_text_is_identical_for_every_batch` 钉住
- **先预热再并发**：逐条判定每个窗口的第一批、全稿校验的第一条规则先单独跑完，
  其余的才起跑（多等约 10 秒）。一起起跑的话，缓存还没建起来，头几个请求谁也吃不到谁的
- 逐条与全稿的 system 不同，所以两段之间不共享前缀（全稿第一条不命中）。把两边合成
  同一段 system 能再省一次，但要动提示词、得重新回归判定质量，收益约一次调用，暂不做

## 环境变量

`CHECKLIST_WORKER_*` 优先，回落同名通用变量：

```
CHECKLIST_WORKER_REDIS_HOST / _PORT / _DB / _PASSWORD
CHECKLIST_WORKER_QUEUE_NAME               默认 checklist_review
CHECKLIST_WORKER_MAX_CONCURRENT_SESSIONS  默认 2
CHECKLIST_WORKER_MAX_CONCURRENT_LLM       默认 12
CHECKLIST_WORKER_LOG_LEVEL                默认 INFO
```
