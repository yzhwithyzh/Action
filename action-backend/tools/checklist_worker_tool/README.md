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
| 稿件 | 任务 payload，只在 Redis 队列与 worker 进程里流转，**不落业务库**（用户未发表的研究稿件） |

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
编行号 → 切窗口 → (条目分批 × 窗口) 并发判定 → 同条目跨窗口取最优 → 聚合完整度
```

- **编行号**：行号是「报告于第几行」的载体，也是模型定位证据的唯一锚点。空行保留但不编号。
- **切窗口**：稿件超过 `window_chars` 时按行切成重叠窗口，重叠是为了避免证据正好被切在边界上。
- **取最优**：`reported > vague > missing`；同档位优先取带行号的。只要有一个窗口找到了证据，这条就算报告了。
- **聚合**：完整度 =（已报告 × 1 + 模糊 × 0.5）/ 总条目数。

几条刻意的保守设定，都有单测盯着（`tools/tests/test_checklist_audit.py`）：

| 情况 | 处理 | 为什么 |
|------|------|--------|
| 模型漏回某条 | 记为 `missing` | 漏判必须表现为「没报告」，不能悄悄算成合格 |
| 行号超出稿件行数 | 丢掉该行号 | 编造的行号比没有行号更有害 |
| 整批判定失败 | 该批按 `missing`，错误写进 `result.errors` 与日志 | 不能因为一次网络抖动就把结论抬高 |
| 稿件超 `max_chars` | 截断并在结果里标 `truncated` | 让用户知道后半段没被看过 |

## 算法二：全稿一致性与术语（`engine/consistency.py`）

```
编行号 → 整篇（不切窗）→ 每条规则一次并发请求 → 收敛发现 → 聚合状态
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
| `warn` | 有疑点，需人工确认（只定位到一处证据） |
| `issue` | 明确不一致（相互矛盾的两处都能定位） |
| `na` | 该研究类型不涉及这项检查（系统综述没有自设对照组等），由模型判定 |
| `unchecked` | **没跑成**（模型调用失败）—— 既不是有问题也不是没问题 |

保守设定，同样有单测盯着（`tools/tests/test_checklist_consistency.py`）：

| 情况 | 处理 | 为什么 |
|------|------|--------|
| 某条规则请求失败 | 停在 `unchecked`，写进 `errors` | 显示成「未发现问题」等于把没跑过的检查算成合格 |
| 行号超出稿件行数 | 丢掉行号，该发现从 `issue` 降为 `warn` | `issue` 的定义就是「两处都能定位」，定位不了就不配这个档 |
| `applicable=false` 但列了问题 | 按问题算，不判 `na` | 不许用「不适用」吞掉已经指出来的问题 |
| 发现只有严重度、没有任何说明 | 丢掉 | 无从核起的「问题」等于噪声 |
| 同类发现超过 `max_findings` | 截断并标 `capped`，前台如实说「仅列出前 N 条」 | 不做静默截断 |
| 稿件超 `max_chars`（默认 6 万字符） | 按整行截断并标 `truncated` | 这一层不切窗，后半段是真没看；按行截是因为行号是唯一锚点 |

**全稿校验整体失败不拖垮任务**：逐条完整性已经跑完，为最后这四次请求把几十次调用的结果
作废没有道理 —— 失败时回一个全 `unchecked` 的空壳，任务照常 completed。

算法不认识 Redis / HTTP / 队列，只要一个满足 `Runner` 协议（`structured()`）的调用器；
LLM 适配层（模型池、故障切换、token 计数）复用 `tools/srd-engine` 里的 `LlmRunner` ——
那部分是基础设施不是 SRD 算法，重写一份只会让两处的切换行为漂移。

## 环境变量

`CHECKLIST_WORKER_*` 优先，回落同名通用变量：

```
CHECKLIST_WORKER_REDIS_HOST / _PORT / _DB / _PASSWORD
CHECKLIST_WORKER_QUEUE_NAME               默认 checklist_review
CHECKLIST_WORKER_MAX_CONCURRENT_SESSIONS  默认 2
CHECKLIST_WORKER_MAX_CONCURRENT_LLM       默认 12
CHECKLIST_WORKER_LOG_LEVEL                默认 INFO
```
