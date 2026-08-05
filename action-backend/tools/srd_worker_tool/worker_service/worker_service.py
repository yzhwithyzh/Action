"""SRD Worker 服务 —— 除了指定任务类与注入模型健康表，没有别的事要做。

调度、限流、状态、日志、停止、优雅关闭全在 `BaseWorkerService` 里。
以后新增工具时，这个文件就是要照抄的模板（通常也就十几行）。
"""

from __future__ import annotations

from typing import Any

from tools.common.base_worker_service import BaseWorkerService
from tools.common.model_health import RedisModelHealth
from tools.srd_worker_tool.worker_service.srd_session_task import SrdSessionTask


class SrdWorkerService(BaseWorkerService):
    """监听 srd_assessment 队列，逐个跑系统综述重复性评估。"""

    task_cls = SrdSessionTask

    def task_kwargs(self) -> dict[str, Any]:
        """模型冻结表复用 worker 的那条 Redis 连接 —— 它是进程级的，不该每个任务建一份。"""
        return {'model_health': RedisModelHealth(self.cfg, self.redis)}
