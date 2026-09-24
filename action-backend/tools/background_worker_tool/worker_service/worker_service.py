"""背景生成 Worker 服务 —— 指定任务类，注入共享的模型冻结表，其余全在基类。"""

from __future__ import annotations

from typing import Any

from tools.background_worker_tool.worker_service.background_session_task import BackgroundSessionTask
from tools.common.base_worker_service import BaseWorkerService
from tools.common.model_health import RedisModelHealth


class BackgroundWorkerService(BaseWorkerService):
    """监听 background_gen 队列，逐个跑「研究方向 → 背景初稿 + 参考文献」。"""

    task_cls = BackgroundSessionTask

    def task_kwargs(self) -> dict[str, Any]:
        """冻结表是进程级的，复用 worker 那条 Redis 连接，跨工具共享模型健康状态。"""
        return {'model_health': RedisModelHealth(self.cfg, self.redis)}
