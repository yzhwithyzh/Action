"""背景生成 worker 的配置。

环境变量（`BACKGROUND_WORKER_*` 优先，回落到同名通用变量）::

    BACKGROUND_WORKER_REDIS_HOST / _PORT / _DB / _PASSWORD
    BACKGROUND_WORKER_QUEUE_NAME              默认 background_gen
    BACKGROUND_WORKER_MAX_CONCURRENT_SESSIONS 默认 2
    BACKGROUND_WORKER_MAX_CONCURRENT_LLM      默认 4
    BACKGROUND_WORKER_LOG_LEVEL               默认 INFO

模型不从这里读 —— 与其它工具一样，从后台 `ai_models` 表取池子
（`tools/common/model_registry.py`）。检索用的 embedding / rerank 端点也不在这里，
走 `config.env.RetrievalConfig`（`.env` 的 `EMBED_*` / `RERANK_*`）：
那是**后端与 worker 共用的一份配置**，两处各配一遍必然漂移。

**并发默认压到 2**（checklist 那个是 2、SRD 也是）：一次生成是 PICO 1 次 + 写作 4 次
+ 核验 4 次 ≈ 9 次模型调用外加若干次 embedding，跑满 5 分钟。放大并发只会让所有人
一起变慢，还更容易撞模型限流。
"""

from __future__ import annotations

from pathlib import Path

from tools.common.worker_config import WorkerConfig

BASE_DIR = Path(__file__).resolve().parents[1]
#: 成功后工作目录会被删掉，完整结果先搬到这里留档（同 checklist worker）
RESULT_DIR = BASE_DIR / 'results'

CONFIG = WorkerConfig.from_env(
    tool_name='background_worker_tool',
    base_dir=BASE_DIR,
    queue_name='background_gen',
    env_prefix='BACKGROUND_WORKER',
    max_concurrent_sessions=2,
    max_concurrent_io=4,
    max_concurrent_llm=4,
)
