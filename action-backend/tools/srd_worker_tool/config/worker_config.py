"""SRD worker 的配置与引擎路径引导。

环境变量（`SRD_WORKER_*` 优先，回落到同名通用变量）：
    SRD_WORKER_REDIS_HOST / _PORT / _DB / _PASSWORD
    SRD_WORKER_QUEUE_NAME              默认 srd_assessment
    SRD_WORKER_MAX_CONCURRENT_SESSIONS 默认 2（一次评估要跑几十次模型调用，别开太大）
    SRD_WORKER_MAX_CONCURRENT_LLM      默认 16（跨任务的模型调用总闸）
    SRD_WORKER_LOG_LEVEL               默认 INFO

模型配置沿用引擎自己的 `SRD_*`（SRD_PROVIDER / SRD_MODEL / SRD_API_KEY / SRD_BASE_URL），
任务 payload 里传的 model 段优先级更高 —— 后端从 ai_model 表取到密钥后直接塞进 payload 即可。
"""

from __future__ import annotations

import sys
from pathlib import Path

from tools.common.worker_config import WorkerConfig

BASE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BASE_DIR.parents[1]
#: 纯算法引擎所在目录（目录名带连字符，不能直接当包名，只能塞 sys.path）
ENGINE_DIR = REPO_ROOT / 'tools' / 'srd-engine'
#: 抽取结果缓存：按 sha256 + 引擎版本 + 模型 命中，**跨 session 共享**。
#: 这就是 SRD 的断点续传 —— 任务失败重跑时，已经抽过的文献不会再花一次钱。
EXTRACT_CACHE_DIR = BASE_DIR / '.extract-cache'
#: 成功后工作目录会被删掉，结果文件先搬到这里留档
RESULT_DIR = BASE_DIR / 'results'

CONFIG = WorkerConfig.from_env(
    tool_name='srd_worker_tool',
    base_dir=BASE_DIR,
    queue_name='srd_assessment',
    env_prefix='SRD_WORKER',
    max_concurrent_sessions=2,
    max_concurrent_io=8,
    max_concurrent_llm=16,
)


def ensure_engine_importable() -> None:
    """让 `import srd_engine` 可用。

    正式部署建议 `pip install -e tools/srd-engine`（引擎有 pyproject，装完这个函数就是空转）；
    开发机上没装也能跑，直接把引擎目录塞进 sys.path。
    """
    path = str(ENGINE_DIR)
    if ENGINE_DIR.exists() and path not in sys.path:
        sys.path.append(path)
