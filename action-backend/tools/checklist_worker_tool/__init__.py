"""报告规范 checklist 逐条校验 worker —— 报告助手第三步的算力后端。

    python -m tools.checklist_worker_tool     启动 worker

这里刻意不 import worker_service（它会连带 import LangChain 与数据库配置），
让只需要 CONFIG 的调用方（后端投递任务时）保持轻量。
"""
