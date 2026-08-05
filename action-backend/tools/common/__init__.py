"""worker 工具公共框架.

新增一个工具 = 写一份配置 + 一个 SessionTask 子类 + 一个 WorkerService 子类，
其余（队列、状态、进度、日志、停止、断点、清理）都在这里。
详见 tools/common/README.md。
"""

from tools.common.async_log_writer import AsyncLogWriter
from tools.common.base_session_task import BaseSessionTask, TaskPayloadError, TaskStopped
from tools.common.base_worker_service import BaseWorkerService
from tools.common.bootstrap import configure_console, ensure_repo_root, setup_logging
from tools.common.checkpoint_json_manager import CheckpointJsonManager
from tools.common.model_health import RedisModelHealth
from tools.common.model_registry import LlmModelInfo, load_llm_models
from tools.common.redis_queue_manager import RedisQueueManager, close_redis, create_redis
from tools.common.resource_limiter import ResourceLimiter
from tools.common.task_client import TaskClient
from tools.common.task_store import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_STOPPED,
    MemoryTaskStore,
    RedisTaskStore,
    TaskStore,
)
from tools.common.worker_config import WorkerConfig

__all__ = [
    'STATUS_COMPLETED',
    'STATUS_FAILED',
    'STATUS_PENDING',
    'STATUS_RUNNING',
    'STATUS_STOPPED',
    'AsyncLogWriter',
    'BaseSessionTask',
    'BaseWorkerService',
    'CheckpointJsonManager',
    'LlmModelInfo',
    'MemoryTaskStore',
    'RedisModelHealth',
    'RedisQueueManager',
    'RedisTaskStore',
    'ResourceLimiter',
    'TaskClient',
    'TaskPayloadError',
    'TaskStopped',
    'TaskStore',
    'WorkerConfig',
    'close_redis',
    'configure_console',
    'create_redis',
    'ensure_repo_root',
    'load_llm_models',
    'setup_logging',
]
