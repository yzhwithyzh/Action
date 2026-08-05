"""Worker 通用配置 —— 所有 worker 工具共用一套环境变量解析规则。

与参考实现（data_extraction_worker_tool/config/worker_config.py）的区别：
那里是「类属性 + 模块导入时读 env」，加第二个工具时没法给不同工具不同的 Redis/队列/并发，
只能整个文件复制一份。这里改成不可变 dataclass + `from_env()`，每个工具在自己的
`config/worker_config.py` 里调一次即可：

    CONFIG = WorkerConfig.from_env(
        tool_name='srd_worker_tool',
        base_dir=Path(__file__).resolve().parents[1],
        queue_name='srd_assessment',
        env_prefix='SRD_WORKER',
    )

环境变量按「工具前缀优先、通用兜底」解析：`SRD_WORKER_REDIS_HOST` → `REDIS_HOST` → 默认值。
这样多个 worker 跑在同一台机器上时，既能共用一份 Redis 配置，也能单独给某个工具改并发。
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

# 未显式指定 env_prefix 时的通用前缀
DEFAULT_ENV_PREFIX = 'WORKER'
# Redis key 的统一命名空间，避免与后端业务 key 撞车
DEFAULT_NAMESPACE = 'action_worker'


def env_str(prefix: str, name: str, default: str = '') -> str:
    """按「工具前缀优先、通用兜底」取环境变量。"""
    for key in (f'{prefix}_{name}', name):
        value = os.environ.get(key)
        if value is not None and value.strip():
            return value.strip()
    return default


def env_int(prefix: str, name: str, default: int) -> int:
    raw = env_str(prefix, name)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


@dataclass(frozen=True)
class WorkerConfig:
    """一个 worker 工具的全部运行参数。

    frozen 是刻意的：配置在进程启动时定型，运行期任何地方都不该改它。
    需要派生（比如测试里换个队列名）用 `dataclasses.replace` 或 `with_overrides`。
    """

    # ---- 身份 ----
    tool_name: str
    base_dir: Path
    queue_name: str
    namespace: str = DEFAULT_NAMESPACE
    env_prefix: str = DEFAULT_ENV_PREFIX

    # ---- Redis ----
    redis_host: str = 'localhost'
    redis_port: int = 6379
    redis_db: int = 0
    redis_username: str = ''
    redis_password: str = ''

    # ---- 并发 ----
    # session：同时处理几个任务；io：下载/解析等 IO 密集动作；llm：模型调用总闸
    max_concurrent_sessions: int = 3
    max_concurrent_io: int = 10
    max_concurrent_llm: int = 30

    # ---- 模型池（从 ai_models 表取，撞限流/欠费时轮换）----
    # 出错模型的冻结时长；到期自动重新参与轮换
    model_freeze_seconds: int = 300
    # 池内模型全被冻结时最多等多久（只对限流/5xx 这类会自愈的错误等待）
    model_all_frozen_wait: int = 600
    # 单次模型调用最多把整个池子轮几遍
    model_max_rounds: int = 2
    # 只用这些 model_type（逗号分隔；`ai_models.model_type` 是自由文本，默认不过滤）
    model_types: str = ''

    # ---- 时间与生命周期（秒 / 天）----
    pop_timeout: int = 5  # blpop 阻塞时长
    stop_check_interval: int = 15  # 停止标志轮询间隔
    shutdown_timeout: int = 300  # 优雅关闭时等待在跑任务的上限
    task_ttl: int = 7 * 24 * 3600  # 任务状态在 Redis 里的保留时长
    log_max_lines: int = 5000  # 单任务在 Redis 里保留的日志行数上限
    log_retention_days: int = 7  # 磁盘日志保留天数
    workdir_retention_days: int = 7  # 工作目录保留天数

    # ---- 其他 ----
    log_level: str = 'INFO'
    extra: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ 构造

    @classmethod
    def from_env(
        cls,
        *,
        tool_name: str,
        base_dir: Path | str,
        queue_name: str | None = None,
        namespace: str = DEFAULT_NAMESPACE,
        env_prefix: str = DEFAULT_ENV_PREFIX,
        **overrides: Any,
    ) -> WorkerConfig:
        """从环境变量构造。`overrides` 里显式传的值优先级最高（高于环境变量）。"""
        p = env_prefix
        cfg = cls(
            tool_name=tool_name,
            base_dir=Path(base_dir),
            queue_name=env_str(p, 'QUEUE_NAME', queue_name or tool_name),
            namespace=env_str(p, 'NAMESPACE', namespace),
            env_prefix=env_prefix,
            redis_host=env_str(p, 'REDIS_HOST', 'localhost'),
            redis_port=env_int(p, 'REDIS_PORT', 6379),
            redis_db=env_int(p, 'REDIS_DB', 0),
            redis_username=env_str(p, 'REDIS_USERNAME'),
            redis_password=env_str(p, 'REDIS_PASSWORD'),
            max_concurrent_sessions=env_int(p, 'MAX_CONCURRENT_SESSIONS', 3),
            max_concurrent_io=env_int(p, 'MAX_CONCURRENT_IO', 10),
            max_concurrent_llm=env_int(p, 'MAX_CONCURRENT_LLM', 30),
            model_freeze_seconds=env_int(p, 'MODEL_FREEZE_SECONDS', 300),
            model_all_frozen_wait=env_int(p, 'MODEL_ALL_FROZEN_WAIT', 600),
            model_max_rounds=env_int(p, 'MODEL_MAX_ROUNDS', 2),
            model_types=env_str(p, 'MODEL_TYPES'),
            pop_timeout=env_int(p, 'POP_TIMEOUT', 5),
            stop_check_interval=env_int(p, 'STOP_CHECK_INTERVAL', 15),
            shutdown_timeout=env_int(p, 'SHUTDOWN_TIMEOUT', 300),
            task_ttl=env_int(p, 'TASK_TTL', 7 * 24 * 3600),
            log_max_lines=env_int(p, 'LOG_MAX_LINES', 5000),
            log_retention_days=env_int(p, 'LOG_RETENTION_DAYS', 7),
            workdir_retention_days=env_int(p, 'WORKDIR_RETENTION_DAYS', 7),
            log_level=env_str(p, 'LOG_LEVEL', 'INFO').upper(),
        )
        return replace(cfg, **overrides) if overrides else cfg

    def with_overrides(self, **overrides: Any) -> WorkerConfig:
        return replace(self, **overrides)

    # ------------------------------------------------------------------ 派生值

    @property
    def redis_url(self) -> str:
        auth = ''
        if self.redis_password:
            auth = f'{self.redis_username}:{self.redis_password}@'
        return f'redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}'

    def key(self, *parts: str) -> str:
        """拼一个带命名空间的 Redis key：`action_worker:srd_worker_tool:task:xxx`。"""
        return ':'.join((self.namespace, self.tool_name, *parts))

    @property
    def queue_key(self) -> str:
        """队列的完整 Redis key —— 后端投递任务时必须用同一个值：`action_worker:queue:srd_assessment`。

        队列 key 里刻意不含 tool_name：队列属于「任务类型」，多个 worker 进程共享同一条队列
        才能横向扩容；而 task/log/stop 这些 key 含 tool_name，避免不同工具的状态互相覆盖。
        """
        return f'{self.namespace}:queue:{self.queue_name}'

    def llm_freeze_key(self, model_ref: str) -> str:
        """模型冻结标记的 key：`action_worker:llm:freeze:ai_models:3`。

        和 `queue_key` 同理，这里刻意不含 tool_name —— 模型的健康状态属于「模型」而不属于某个工具，
        SRD worker 撞到的限流，别的工具也该躲开。
        """
        return f'{self.namespace}:llm:freeze:{model_ref}'

    @property
    def model_type_list(self) -> list[str]:
        return [t.strip() for t in self.model_types.split(',') if t.strip()]

    @property
    def logs_dir(self) -> Path:
        return self.base_dir / 'logs'

    @property
    def temp_dir(self) -> Path:
        return self.base_dir / 'temp'

    @property
    def checkpoint_dir(self) -> Path:
        return self.base_dir / 'checkpoint'

    def to_dict(self) -> dict[str, Any]:
        """脱敏后的配置快照，可直接进日志 / 健康检查接口。"""
        data = asdict(self)
        data['base_dir'] = str(self.base_dir)
        data['redis_password'] = '***' if self.redis_password else ''
        data['redis_url'] = self.redis_url.replace(self.redis_password, '***') if self.redis_password else self.redis_url
        return data
