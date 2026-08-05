"""SRD 评估 worker —— 把 tools/srd-engine 这个纯算法引擎包成 Redis 驱动的常驻服务。

    python -m tools.srd_worker_tool           启动 worker
    python -m tools.srd_worker_tool.cli ...   投递任务 / 看状态 / 看日志 / 停止

这里刻意不 import worker_service（它会连带 import 引擎与 LangChain），
让 `python -m tools.srd_worker_tool.cli` 这种只投递任务的用法保持轻量。
"""
