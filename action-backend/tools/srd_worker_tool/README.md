# SRD 评估 Worker

把 `tools/srd-engine`（系统综述重复性评估引擎，纯算法、无外部依赖）包成一个
**Redis 驱动的常驻服务**：后端把任务丢进队列，worker 拉起来跑，进度与日志实时回传。

引擎本身一行没改 —— 算法与服务是两层，换服务形态不影响离线批量验证（`run_batch.py` 照常可用）。

---

## 1. 启动

```bash
# 依赖：redis / httpx + 引擎依赖（pydantic、langchain-openai、pymupdf …）
cd action-backend                      # worker 的工作目录是 action-backend，不是仓库根
pip install -r tools/srd_worker_tool/requirements.txt
pip install -e tools/srd-engine        # 可选；不装也能跑（会自动把引擎目录加进 sys.path）

export SRD_WORKER_REDIS_HOST=127.0.0.1
# 模型默认从 ai_models 表读（见 §3），以下两个只是数据库里一个可用模型都没有时的兜底
export SRD_API_KEY=sk-xxx
export SRD_MODEL=deepseek-chat

python -m tools.srd_worker_tool
```

Windows PowerShell：`$env:SRD_API_KEY='sk-xxx'; python -m tools.srd_worker_tool`

## 2. 提交任务

命令行（用于联调，等价于后端接口该做的事）：

```bash
python -m tools.srd_worker_tool.cli submit A.pdf B.pdf                 # 模型取自 ai_models 表
python -m tools.srd_worker_tool.cli submit A.pdf B.pdf --model-ids 3,7 # 只用其中两个
python -m tools.srd_worker_tool.cli status <session_id>
python -m tools.srd_worker_tool.cli logs   <session_id> -f     # -f 等价于前端 SSE
python -m tools.srd_worker_tool.cli stop   <session_id>
python -m tools.srd_worker_tool.cli queue
```

后端代码：

```python
from tools.common import TaskClient
from tools.srd_worker_tool.config import CONFIG

async with TaskClient(CONFIG) as client:
    session_id = await client.submit({
        'user_id': user.id,
        'review_a': {'url': cos_url_a, 'title': '综述A标题'},
        'review_b': {'url': cos_url_b, 'title': '综述B标题'},
        'engine': {'judge_granularity': 'all', 'max_concurrency': 8},
        # 不用传模型：worker 自己从 ai_models 表取一整个池子。要限定范围才传 model_ids
    })
```

### payload 字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `session_id` | 由 `submit()` 自动生成 | 全链路唯一标识 |
| `review_a` / `review_b` | ✅ | `{'url': ...}` 或 `{'path': ...}`，可带 `title`；也可直接传字符串，或用 `files: [a, b]` |
| `model_ids` | 否 | 只用 `ai_models` 里这几个模型（不传＝全部启用中的） |
| `model` | 否 | 带 `api_key` 时＝一次性临时模型（不查库、不轮换）；只给 `temperature`/`max_tokens`/`timeout` 时＝套到池内每个模型上。空串视为「不覆盖」 |
| `engine` | 否 | `extract_scope` / `judge_granularity` / `max_concurrency` / `evidence_sufficient_ratio` |
| `options.force` | 否 | `true` 时忽略断点强制重跑 |

`max_concurrency` 会被裁到 `max_concurrent_llm / max_concurrent_sessions`（默认 16/2 = 8），
防止单个任务把模型配额吃满。

## 3. 模型从哪来

模型配置**从后台的 `ai_models` 表读**（`AiModelService.get_usable_ai_model_pool_services`，
与 AI 对话共用同一份筛选与解密逻辑）。后台改了模型，下一个任务立刻生效，不用重启 worker。

筛选规则：`status='0'`（启用）+ 配了 `api_key`，按 `model_sort` 升序 —— **这个顺序就是轮询顺序**。

优先级：

1. `payload.model` 里带 `api_key` → 一次性临时模型，不查库也不轮换；
2. `ai_models` 表（可用 `payload.model_ids` 缩小范围）；
3. `SRD_PROVIDER / SRD_MODEL / SRD_API_KEY / SRD_BASE_URL` 环境变量 —— 库里一个都没有时的兜底。

### 出错怎么切换

策略是**粘性 + 出错切换**：一直用当前模型（同一次评估尽量由同一个模型判定，结论才好解释），
撞到问题才换。为什么不是每次调用都轮流打：34 条判定由不同模型给出的话，自一致性和可追溯性都会变差。

| 错误 | 处置 |
|------|------|
| 限流 429 / 服务端 5xx | **冻结该模型 5 分钟 → 换下一个**，冻结期满自动回到候选队列 |
| 鉴权 401/403、欠费 402、模型不存在 404 | 同上，但标记为「等也没用」 |
| 网络抖动、超时、认不出来的错误 | 先在**同一个模型**上重试（默认 3 次），仍失败才按限流处理 |
| 参数非法 400、内容审核拒绝 | 换谁都一样：**不冻结**，直接把这一次调用判错（引擎降级为 unclear） |

冻结记录写在 Redis 的 `action_worker:llm:freeze:ai_models:{id}`（TTL 即剩余冻结时长），
键里刻意不含工具名 —— **所有 worker 进程共享同一份健康状态**，A 进程撞到限流，B 进程就不会再撞一次。

池内模型**全部**被冻结时：

- 全是「等也没用」的错（鉴权/欠费）→ 立刻判任务失败；
- 有会自愈的错（限流）→ 阻塞等待最早解冻，最多等 `SRD_WORKER_MODEL_ALL_FROZEN_WAIT`（默认 600s），
  期间会重新读一次 `ai_models`（捡运维刚启用的模型），超时仍不可用则判任务失败。

失败而不是「继续跑出一份全 unclear 的报告」是刻意的：一份什么都没判出来的报告比失败更危险，
用户会拿它当结论。断点与抽取缓存都还在，配好模型重新入队即可续跑。

任务摘要里会带 `model_pool` / `models_used` / `model_switches` / `model_usage`，
一次评估中途换过模型的话，从摘要和日志里都能看出来是谁判的。

## 4. 结果

任务状态里的 `result` 字段是摘要（可直接喂给前端列表页）：

```json
{
  "overall_level": "mod", "overall_level_zh": "中度重复", "overall_pct": 55,
  "overall_score_sum": 42, "overall_score_max": 93, "overall_score_max_full": 102,
  "provisional": false, "unclear_count": 3, "review_count": 1,
  "domains": [{"seq": 1, "name_zh": "研究主题", "is_key": true, "level": "high", "pct": 83,
               "score_sum": 4, "score_max": 24, "score_max_full": 24, ...}],
  "ratings": {"1a": "0", "1b": "1", "2a": "3", "...": "unclear"},
  "score_distribution": {"0": 11, "1": 8, "2": 6, "3": 6, "unclear": 3},
  "llm_calls": 41, "token_in": 128000, "token_out": 19000, "seconds": 214.6,
  "model": "deepseek-chat", "model_pool_source": "db",
  "model_pool": ["DeepSeek/deepseek-chat#ai_models:3", "Moonshot/kimi-k2#ai_models:7"],
  "models_used": ["DeepSeek/deepseek-chat#ai_models:3"], "model_switches": [],
  "engine_version": "srd-engine/0.7.0", "prompt_version": "prompt/2026-08-05",
  "files": {"json": "...", "csv": "...", "txt": "..."}
}
```

**评分怎么读**（0.7.0 起，口径全在引擎侧，见 [srd-engine/README.md](../srd-engine/README.md)）：
每个条目 0–3 分，**分越低越重复**（0 = 完全相同，3 = 完全不同，`unclear` = 证据不足不计分）。
`score_max` 是可评分条目的满分（3 × 可评分条目数），`score_max_full` 是名义满分
（领域 /24 /18 /42 /18，整体 /102）—— 两者不等就说明有条目证据不足被剔出了分母。
`overall_pct` 是重复百分比 =（`score_max` − `score_sum`）÷ `score_max` × 100，
而 `overall_level` 不是把它再分一次箱，是拿四个领域的档位查表 3 得来的，两者可能不同向。

完整结果（34 条目逐条评分、引用、投票留痕）在 `results/{session_id}/`：

| 文件 | 用途 |
|------|------|
| `result.json` | `AssessmentResult` 全量结构，前端详情页渲染用 |
| `report.csv` | Excel 友好（UTF-8 BOM），给方法学专家核对 |
| `report.txt` | 纯文本报告 |

> 要传对象存储（COS/OSS）时，在 `SrdSessionTask.on_success()` 里上传并把 URL 写回 `result['files']`，
> 其余流程无需改动。

## 5. 断点与省钱

两层：

1. **抽取缓存** `.extract-cache/`：按 `sha256 + 引擎版本 + 提示词版本 + 模型` 命中，**跨任务共享**。
   同一篇文献第二次出现（换配对、失败重跑）不会再花钱抽一次。
2. **结果断点** `checkpoint/{session_id}/result.json`：任务失败/被停止后重新入队同一个 `session_id`，
   若结果已算完则直接复用。引擎三件套版本任一变化即作废（结论必须可追溯）。

失败或被停止时工作目录**保留**；成功后自动清理，7 天前的残留由框架顺手回收。

## 6. 目录

```
tools/srd_worker_tool/
├── __main__.py                 启动入口
├── cli.py                      投递端命令行
├── config/worker_config.py     配置 + 引擎路径引导
├── worker_service/
│   ├── srd_session_task.py     任务实现（本工具唯一的业务代码）
│   └── worker_service.py       服务（只指定 task_cls）
├── logs/ temp/ checkpoint/ results/ .extract-cache/    运行时生成，已 gitignore
└── README.md
```

框架说明见 [`tools/common/README.md`](../common/README.md)。

## 7. 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `SRD_WORKER_REDIS_HOST/_PORT/_DB/_PASSWORD` | localhost:6379/0 | 回落到通用 `REDIS_*` |
| `SRD_WORKER_QUEUE_NAME` | `srd_assessment` | 队列名（完整 key：`action_worker:queue:srd_assessment`） |
| `SRD_WORKER_MAX_CONCURRENT_SESSIONS` | 2 | 同时评估几对综述 |
| `SRD_WORKER_MAX_CONCURRENT_LLM` | 16 | 模型调用总闸 |
| `SRD_WORKER_STOP_CHECK_INTERVAL` | 15 | 停止信号响应延迟上限（秒） |
| `SRD_WORKER_MODEL_FREEZE_SECONDS` | 300 | 出错模型冻结多久（秒） |
| `SRD_WORKER_MODEL_ALL_FROZEN_WAIT` | 600 | 全池冻结时最多等多久（秒） |
| `SRD_WORKER_MODEL_MAX_ROUNDS` | 2 | 单次调用最多把池子轮几遍 |
| `SRD_WORKER_MODEL_TYPES` | 空 | 只用这些 `model_type`（逗号分隔，空＝不过滤） |
| `SRD_PROVIDER / SRD_MODEL / SRD_API_KEY / SRD_BASE_URL` | — | `ai_models` 里一个可用模型都没有时的兜底 |

模型池还需要 worker 能连上后端那套数据库（`config/.env` 里的 `DB_*`）与解密密钥（`JwtConfig.jwt_secret_key`）——
和后端进程用同一份配置即可，systemd 的 `EnvironmentFile` 指向同一个 `.env` 最省事。

## 8. 部署（systemd 示例）

```ini
[Unit]
Description=SRD Assessment Worker
After=network.target redis.service

[Service]
Type=simple
WorkingDirectory=/srv/action/action-backend
Environment="PYTHONPATH=/srv/action/action-backend"
EnvironmentFile=/srv/action/.env.srd-worker
ExecStart=/srv/action/.venv/bin/python -m tools.srd_worker_tool
Restart=always
RestartSec=10
KillSignal=SIGTERM
TimeoutStopSec=330      # 略大于 shutdown_timeout(300)，留出优雅收尾时间

[Install]
WantedBy=multi-user.target
```

多开进程即横向扩容：同一条队列，谁有空谁取。
