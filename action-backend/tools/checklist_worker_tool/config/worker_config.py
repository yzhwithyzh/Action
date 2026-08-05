"""checklist 校验 worker 的配置。

环境变量（`CHECKLIST_WORKER_*` 优先，回落到同名通用变量）：
    CHECKLIST_WORKER_REDIS_HOST / _PORT / _DB / _PASSWORD
    CHECKLIST_WORKER_QUEUE_NAME              默认 checklist_review
    CHECKLIST_WORKER_MAX_CONCURRENT_SESSIONS 默认 2
    CHECKLIST_WORKER_MAX_CONCURRENT_LLM      默认 12
    CHECKLIST_WORKER_LOG_LEVEL               默认 INFO

模型不从这里读 —— 与其它工具一样，从后台 `ai_models` 表取池子（见 tools/common/README.md 第 4 节）。
"""

from __future__ import annotations

import sys
from pathlib import Path

from tools.common.worker_config import WorkerConfig

BASE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BASE_DIR.parents[1]
#: 复用 srd-engine 里的通用 LLM 适配层（模型池 / 粘性切换 / token 计数）。
#: 那部分是基础设施不是 SRD 算法，重写一份只会让两处的故障切换行为漂移。
#: 本工具自己的算法在 engine/audit.py，不依赖 srd_engine 的任何业务模块。
ENGINE_DIR = REPO_ROOT / 'tools' / 'srd-engine'
#: 成功后工作目录会被删掉，完整判定结果先搬到这里留档
RESULT_DIR = BASE_DIR / 'results'

CONFIG = WorkerConfig.from_env(
    tool_name='checklist_worker_tool',
    base_dir=BASE_DIR,
    queue_name='checklist_review',
    env_prefix='CHECKLIST_WORKER',
    max_concurrent_sessions=2,
    max_concurrent_io=8,
    max_concurrent_llm=12,
)


def ensure_engine_importable() -> None:
    """让 `from srd_engine.adapters...` 可用（只取 LLM 适配层）。"""
    path = str(ENGINE_DIR)
    if ENGINE_DIR.exists() and path not in sys.path:
        sys.path.append(path)
