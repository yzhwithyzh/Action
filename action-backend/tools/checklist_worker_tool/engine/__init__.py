"""checklist 逐条校验的纯算法（不认识 Redis / HTTP / 队列）。

两类判定，分在两个模块：
- `audit`       逐条完整性 —— 「这一条报告了没有、报在第几行」，证据是局部的，可以切窗并发
- `consistency` 全稿一致性与术语标准化 —— 「各处对不对得上」，跨段落，刻意不切窗

两边都叫 `summarize`，这里只导出 `audit` 的那个；一致性的从 `consistency` 模块直接取，
免得两个同名函数在调用处混起来。
"""

from tools.checklist_worker_tool.engine.audit import (
    MISSING,
    REPORTED,
    VAGUE,
    AuditConfig,
    ChecklistItem,
    ItemVerdict,
    audit,
    number_lines,
    split_windows,
    summarize,
)
from tools.checklist_worker_tool.engine.consistency import (
    ISSUE,
    NA,
    OK,
    RULES,
    UNCHECKED,
    WARN,
    CheckResult,
    CheckRule,
    ConsistencyConfig,
    Finding,
    check_consistency,
)

__all__ = [
    'ISSUE',
    'MISSING',
    'NA',
    'OK',
    'REPORTED',
    'RULES',
    'UNCHECKED',
    'VAGUE',
    'WARN',
    'AuditConfig',
    'CheckResult',
    'CheckRule',
    'ChecklistItem',
    'ConsistencyConfig',
    'Finding',
    'ItemVerdict',
    'audit',
    'check_consistency',
    'number_lines',
    'split_windows',
    'summarize',
]
