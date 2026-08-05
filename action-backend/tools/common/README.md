# tools/common —— worker 工具公共框架

所有「常驻进程 + Redis 队列 + 长耗时 AI 任务」的工具共用这一套骨架。
参考实现是 `tools/data_extraction_worker_tool`（从 SmartEBM 搬来的样板），
本框架把其中**与业务无关的部分**抽了出来，并修掉了几处样板里的结构性问题（见文末）。

---

## 1. 一张图看懂

```
后端 / 脚本                    Redis                        worker 进程
─────────────                ─────────                     ─────────────
TaskClient.submit()  ──rpush──▶ 队列 ────────────blpop────▶ BaseWorkerService
                                                              │ 抢 session 槽位
                                                              ▼
   status()  ◀──hgetall──── task:{sid}  ◀──状态/进度──   BaseSessionTask.run()
   logs()    ◀──lrange───── log:{sid}   ◀──日志─────       ├─ validate()
   SSE       ◀──subscribe── log:channel ◀──日志─────       ├─ process()   ← 子类唯一必须实现的
   stop()    ──set────────▶ stop:{sid}  ──轮询──▶ 看门狗    └─ 结果落盘 + 清场
```

## 2. 模块清单

| 文件 | 职责 |
|------|------|
| `worker_config.py` | 不可变配置 dataclass；`from_env()` 按「工具前缀优先、通用兜底」读环境变量 |
| `redis_queue_manager.py` | 队列读写：push / blpop / requeue / 长度 / 清空 |
| `task_store.py` | 状态存储接口 + Redis 实现 + 内存实现（测试用） |
| `task_client.py` | **投递端** API：提交、查状态、拉日志、订阅日志（SSE）、请求停止 |
| `async_log_writer.py` | 任务日志：内存队列 → 批量落盘 + 写 Redis 列表 + 发布到频道 |
| `checkpoint_json_manager.py` | 断点 JSON 落盘（先写 tmp 再 replace，不会留半个文件） |
| `resource_limiter.py` | session / io / llm 三级并发闸门 |
| `model_registry.py` | 从 `ai_models` 表取可用模型池（api_key 已解密） |
| `model_health.py` | 模型冻结表（Redis，跨进程/跨工具共享） |
| `base_session_task.py` | **任务基类**：生命周期、进度、停止、断点、清场 |
| `base_worker_service.py` | **服务基类**：拉取循环、并发调度、心跳、优雅关闭 |
| `bootstrap.py` | 日志配置、sys.path 引导 |

## 3. 新增一个工具的步骤

以 `action-backend/tools/xxx_worker_tool` 为例，一共四个文件（可直接照抄 `tools/srd_worker_tool`）：

```
tools/xxx_worker_tool/
├── __main__.py                       # 启动入口，照抄改个类名
├── config/worker_config.py           # CONFIG = WorkerConfig.from_env(...)
└── worker_service/
    ├── xxx_session_task.py           # class XxxSessionTask(BaseSessionTask): async def process()
    └── worker_service.py             # class XxxWorkerService(BaseWorkerService): task_cls = XxxSessionTask
```

想给任务注入进程级依赖（模型冻结表、对象存储客户端），在 WorkerService 里覆盖 `task_kwargs()`：

```python
class XxxWorkerService(BaseWorkerService):
    task_cls = XxxSessionTask

    def task_kwargs(self):
        return {'model_health': RedisModelHealth(self.cfg, self.redis)}
```

`process()` 里可以用的基类能力：

```python
await self.log.write_info('阶段一开始')       # 日志（落盘 + 前端可拉可推）
await self.report_progress(30, 100, 'parse')  # 进度（异步版）
self.report_progress_nowait(30, 100, 'parse') # 进度（同步版，给第三方同步回调用）
await self.raise_if_stopped()                 # 主动检查停止（长循环里插一句）
async with self.limiter.io_slot(): ...        # 跨任务的 IO 并发闸
self.checkpoint.save('step1', data)           # 断点
self.input_dir / self.output_dir              # 工作目录（成功后自动删、失败自动留）
```

约定：
- `process()` 的返回值会被 JSON 序列化进任务状态，**只放摘要**，大文件写磁盘/对象存储再给路径。
- 参数不合法请抛 `TaskPayloadError`（会被标成 failed 且不重试）。
- 想在成功/失败/停止后做记账、通知、上传，覆盖 `on_success / on_failure / on_stopped`。

## 4. 模型配置从哪来

长耗时 AI 工具的模型**不从环境变量读，也不由后端塞进 payload**，而是 worker 自己按需从
后台的 `ai_models` 表取 —— 后台改完配置下一个任务立刻生效，密钥也不用进 Redis 队列：

```python
from tools.common import load_llm_models

models = await load_llm_models()                  # 启用中 + 配了 key，按 model_sort
models = await load_llm_models(model_ids=[3, 7])  # 任务 payload 可以缩小范围
```

底层就是后端的 `AiModelService.get_usable_ai_model_pool_services()`，
筛选与解密逻辑与 AI 对话共用一份。代价是 worker 需要能连上后端那套数据库
（工作目录本来就是 `action-backend`，和后端用同一个 `.env` 即可）。

### 为什么是「一组」模型而不是一个

单个厂商都有并发/RPM 上限，一次长任务几十次调用很容易撞上。所以取到的是一个**池子**，
交给引擎做「粘性 + 出错切换」：正常时一直用第一个（结论才好解释），撞到限流/欠费/鉴权/5xx
就把它冻结 5 分钟并切到下一个，冻结到期自动回到候选队列。

冻结表在 Redis：`{namespace}:llm:freeze:{model_ref}`，TTL 即剩余冻结时长。
键里刻意不含工具名 —— 模型的健康状态属于模型，A 工具撞到的限流，B 工具也该躲开。

```python
from tools.common import RedisModelHealth

health = RedisModelHealth(cfg, redis)     # 塞给引擎的 runner 即可
await health.snapshot()                   # 运维：现在有哪些模型被冻着
await health.thaw('ai_models:3')          # 运维：改完配置立刻解冻，不等 5 分钟
```

相关配置见 `WorkerConfig.model_freeze_seconds / model_all_frozen_wait / model_max_rounds / model_types`
（环境变量 `{前缀}_MODEL_FREEZE_SECONDS` 等）。

## 5. 后端怎么接

```python
from tools.common import TaskClient
from tools.srd_worker_tool.config import CONFIG

async with TaskClient(CONFIG) as client:
    sid = await client.submit({'review_a': ..., 'review_b': ..., 'model': {...}})
    state = await client.status(sid)            # 轮询接口直接返回它
    async for record in client.subscribe_logs(sid):  # SSE 接口直接转发它
        ...
    await client.stop(sid)                      # 停止按钮
```

后端只依赖 `TaskClient` 与 `CONFIG`，不 import worker 内部实现；
worker 挂了不影响后端进程，后端重启也不影响在跑的任务。

## 6. Redis 键位

| key | 类型 | 说明 |
|-----|------|------|
| `{ns}:queue:{queue_name}` | list | 任务队列（同一队列可挂多个 worker 进程） |
| `{ns}:{tool}:task:{sid}` | hash | 状态快照：status / progress / message / error / result |
| `{ns}:{tool}:log:{sid}` | list | 日志行（超过 `log_max_lines` 自动裁剪） |
| `{ns}:{tool}:log:channel:{sid}` | pubsub | 日志实时推送 |
| `{ns}:{tool}:stop:{sid}` | string | 停止标志 |
| `{ns}:{tool}:tasks:active` | zset | 在跑任务（score = 开始时间） |
| `{ns}:{tool}:workers:{worker_id}` | string | 心跳（TTL 45s），含在跑任务数与资源占用 |
| `{ns}:llm:freeze:{model_ref}` | string | 模型冻结标记（TTL＝剩余冻结时长），**跨工具共享** |

默认 `ns = action_worker`。状态默认保留 7 天（`task_ttl`）。

## 7. 相对参考实现改了什么

| 问题（参考实现） | 本框架 |
|---|---|
| 配置写死成类属性，第二个工具只能整份复制 | `WorkerConfig.from_env()`，一行一份 |
| 先 blpop 再等并发槽位 → 积压被搬进单机内存，重启即丢、扩容无效 | 先抢槽位再 blpop，积压留在 Redis |
| session 槽位 acquire/release 手工配对，异常路径漏还 | 统一 context manager + `finally` 归还 |
| 状态强绑 MySQL + 一整套 Service 层 | `TaskStore` 接口，Redis / 内存 / 将来 MySQL 可换 |
| 停止只靠业务代码主动查，卡在 LLM 调用里就停不下来 | 看门狗超时取消主协程，区分「用户停止」与「进程关闭」 |
| 进度直接写库，且晚到的旧进度会覆盖新进度 | 节流 + 序号校验，收尾时补写最终值 |
| 关闭时未开跑的任务直接丢 | 还回队列 |
| 模型配置写死在环境变量，一个 key 撞限流就卡死 | 从 `ai_models` 表取一池子，出错冻结 5 分钟并轮换 |

## 8. 测试

```bash
cd action-backend                          # 所有命令的工作目录
python -m pytest tools/tests -q            # 全部（联调用例在无 Redis 时自动跳过）
python -m ruff check tools --config tools/ruff.toml
```
