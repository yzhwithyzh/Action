"""报告规范 checklist 校验 worker —— 报告助手第三步的算力后端。

    cd action-backend
    python -m tools.checklist_worker_tool     启动 worker（常驻，守 Redis 队列）

一次任务 = 「一份稿件 × 一份报告规范」，产出两类判定：逐条完整性（这条报告了没有、在第几行）
与全稿一致性/术语（各处对不对得上）。

## 目录与分层

::

    checklist_worker_tool/
    ├── __main__.py                 启动入口：装日志 → 建 ChecklistWorkerService → run()
    ├── cli.py                      投递端命令行（submit/status/logs/stop/queue），不开浏览器跑通链路
    ├── config/worker_config.py     CONFIG（队列名、并发、Redis）+ 结果目录 + srd-engine 路径
    ├── worker_service/             ── 服务层：认识 Redis / 数据库 / 任务生命周期，不写算法
    │   ├── worker_service.py         守队列、起任务（生命周期全在 tools/common 基类里）
    │   └── checklist_session_task.py 一次校验：取条目 → 组模型池 → 调引擎 → 写结果
    └── engine/                     ── 算法层：纯函数 + 一个 runner 协议，不认识 Redis/HTTP/数据库
        ├── audit.py                  逐条完整性：切窗 → 分批判定 → 引文定位 → 跨窗取最优
        ├── consistency.py            全稿一致性：整篇不切窗 → 每条规则一次请求 → 引文定位 → 代码定级
        └── grounding.py              引文回原文定位：行号只从这里来（模型不接触行号），打 located 标

依赖只朝一个方向：``__main__ → worker_service → engine``；engine 只 import 它自己的三个模块。
这样引擎能离线单测（``tools/tests/test_checklist_*.py``，用脚本化的假 runner 代替模型），
worker 换队列/换存储也不用碰算法。

## 一次任务的数据流

::

    后端 POST /action/site/checklist-review
      └─ TaskClient.submit(payload) ──rpush──► Redis 队列 checklist_review
                                                 │
    worker（BaseWorkerService 主循环）◄──blpop───┘
      └─ ChecklistSessionTask.run()                       [tools/common/base_session_task.py]
           validate()        payload 校验，早失败
           process()
             ├─ _load_items()        action_guideline_item → [ChecklistItem]
             ├─ _resolve_pool()      ai_models → [ModelConfig]，组成 LlmRunner（粘性 + 出错切换）
             ├─ audit()              ── 进度 6%→86%，几十次模型调用，主产物
             ├─ _run_consistency()   ── 进度 86%→96%，4 次调用，失败不拖垮任务
             ├─ _persist_structured_methods()  探测到的结构化输出方式回写 ai_models
             └─ _finalize()          完整结果写 results/<sid>.json，精简版作为任务结果回 Redis
                                                 │
    后端轮询 GET /action/site/checklist-review/{sid} ◄┘  读到 completed 时落库
      （action_report_review + action_report_review_item，见 action_service.py）

## 读代码时要知道的几条纪律

- **换模型时结论不许大起大落**：凡是代码能定的事都不交给模型 —— 条目标签（批内字母）由 Schema 枚举锁死
  （``audit._batch_schema``）；**模型不接触行号**，位置由代码拿引文去原文里查（``grounding``）；
  一致性的严重度由代码按「引文定位到几处不同位置」算（``consistency._severity``，
  模型输出里既没有 severity 也没有行号字段）。
- **核对只打标，不改判定**：朴素字符串核对会误伤好模型的正确判定，校准数据见 ``grounding.py`` 文件头。
  找不到的引文没有位置（不沿用模型的任何数字），前台提示人工核对。
- **没跑成 ≠ 没问题**：批次失败 / 漏回 → 条目按 missing 且挂「模型未返回」或「部分片段未判定」；
  规则失败 → ``unchecked``；两者都进结果的 ``errors``，前台顶部提示「部分判定未完成」。
  都与「看过了、确实没写 / 确实没问题」分开显示。
- **输出结构的字段全部必填**：走 function calling 的厂商会把可选字段整个省掉（踩过一次，见
  ``audit._ItemJudgement``）。

这里刻意不 import worker_service（它会连带 import LangChain 与数据库配置），
让只需要 CONFIG 的调用方（后端投递任务时）保持轻量。
"""
