"""checklist 校验 Worker 服务 —— 指定任务类，注入共享的模型冻结表，其余全在基类。"""

from __future__ import annotations

from typing import Any

from tools.checklist_worker_tool.worker_service.checklist_session_task import ChecklistSessionTask
from tools.common.base_worker_service import BaseWorkerService
from tools.common.model_health import RedisModelHealth


class ChecklistWorkerService(BaseWorkerService):
    """监听 checklist_review 队列，逐个跑「稿件 × 规范」的逐条校验。"""

    task_cls = ChecklistSessionTask

    def task_kwargs(self) -> dict[str, Any]:
        """冻结表是进程级的，复用 worker 那条 Redis 连接，跨工具共享模型健康状态。"""
        return {'model_health': RedisModelHealth(self.cfg, self.redis)}
