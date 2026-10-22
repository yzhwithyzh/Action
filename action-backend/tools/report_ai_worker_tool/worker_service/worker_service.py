"""报告助手 AI Worker 服务 —— 指定任务类，注入共享的模型冻结表，其余全在基类。"""

from __future__ import annotations

from typing import Any

from tools.common.base_worker_service import BaseWorkerService
from tools.common.model_health import RedisModelHealth
from tools.report_ai_worker_tool.worker_service.report_ai_session_task import ReportAiSessionTask


class ReportAiWorkerService(BaseWorkerService):
    """监听 report_ai 队列，跑一键优化与整篇成文。"""

    task_cls = ReportAiSessionTask

    def task_kwargs(self) -> dict[str, Any]:
        """冻结表是进程级的，复用 worker 那条 Redis 连接，跨工具共享模型健康状态。"""
        return {'model_health': RedisModelHealth(self.cfg, self.redis)}
