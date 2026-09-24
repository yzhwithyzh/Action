"""checklist 校验 Worker 服务 —— 指定任务类，注入共享的模型冻结表，其余全在基类。

基类 `tools/common/base_worker_service.py` 已经做完的事（这里一行都不用写）：

- 主循环：**先占到一个并发槽位（`max_concurrent_sessions`）才去队列里取任务** ——
  满了就不取，积压留在 Redis 里，别的 worker 进程可以接；
- 优雅关闭：收到 SIGTERM 后不再取新任务，关闭途中取到的任务还回队列，等在跑的收尾
  （最多 `shutdown_timeout` 秒）；
- 心跳：定期往 Redis 写本 worker 的状态，`status_checklist_worker.sh` 靠它判断活着没有；
- 失败兜底：payload 缺 `session_id` 在构造任务时就失败；其余错误（包括 `validate()`
  抛的 `TaskPayloadError`）在 `BaseSessionTask.run()` 里被接住，状态标 failed、写进任务日志。

子类只需要回答两件事：跑哪个任务类（`task_cls`）、构造任务时额外塞什么（`task_kwargs`）。
"""

from __future__ import annotations

from typing import Any

from tools.checklist_worker_tool.worker_service.checklist_session_task import ChecklistSessionTask
from tools.common.base_worker_service import BaseWorkerService
from tools.common.model_health import RedisModelHealth


class ChecklistWorkerService(BaseWorkerService):
    """监听 checklist_review 队列，逐个跑「稿件 × 规范」的逐条校验。"""

    task_cls = ChecklistSessionTask

    def task_kwargs(self) -> dict[str, Any]:
        """每个任务构造时额外拿到的参数：模型冻结表。

        冻结表记的是「某个模型撞了限流/欠费，接下来 N 分钟别再用它」。它存在 Redis 里，
        所以同一台机器上的 SRD worker、背景生成 worker 与这里**共享同一份**：
        别的 worker 刚把某个模型撞欠费了，这边的任务一开跑就会跳过它，而不是再撞一遍。
        复用 worker 已有的 Redis 连接，不为每个任务另开。
        """
        return {'model_health': RedisModelHealth(self.cfg, self.redis)}
