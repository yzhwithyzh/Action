# checklist_worker_tool —— 报告规范逐条校验 worker

报告助手**第三步**的算力后端：拿到一份稿件和一份报告规范，逐条判断
「这条报告了没有、报在第几行」，也就是投稿时那张 checklist 最后一列要填的东西。

公共骨架（配置、队列、状态、日志、停止、优雅关闭）见 [`tools/common/README.md`](../common/README.md)，
这里只写本工具特有的部分。

## 跑起来

```bash
cd action-backend
python -m tools.checklist_worker_tool
```

工作目录必须是 `action-backend/`（要用同一份 `.env` 连数据库取条目与模型配置）。

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
  "engine": { "batch_size": 8, "max_concurrency": 4 },
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

## 算法（`engine/audit.py`）

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
