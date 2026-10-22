"""报告助手 AI worker 的配置（一键优化 / 整篇成文）。

环境变量（`REPORT_AI_WORKER_*` 优先，回落到同名通用变量）::

    REPORT_AI_WORKER_REDIS_HOST / _PORT / _DB / _PASSWORD
    REPORT_AI_WORKER_QUEUE_NAME              默认 report_ai
    REPORT_AI_WORKER_MAX_CONCURRENT_SESSIONS 默认 2
    REPORT_AI_WORKER_MAX_CONCURRENT_LLM      默认 4（一键优化里同一任务的条目并发也受它管）
    REPORT_AI_WORKER_LOG_LEVEL               默认 INFO

模型不从这里读 —— 走后端 `AiAssistService`（`ai_models` 表的模型池），与单条「AI 优化」
同一条路：一键优化跑出来的建议和单条点出来的必须是同一个口径。
"""

from __future__ import annotations

from pathlib import Path

from tools.common.worker_config import WorkerConfig

BASE_DIR = Path(__file__).resolve().parents[1]

CONFIG = WorkerConfig.from_env(
    tool_name='report_ai_worker_tool',
    base_dir=BASE_DIR,
    queue_name='report_ai',
    env_prefix='REPORT_AI_WORKER',
    max_concurrent_sessions=2,
    max_concurrent_io=4,
    max_concurrent_llm=4,
)
