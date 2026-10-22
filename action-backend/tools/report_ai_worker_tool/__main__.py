"""报告助手 AI Worker（一键优化 · 整篇成文）启动入口。

    cd action-backend
    python -m tools.report_ai_worker_tool

也支持直接跑文件 —— 入口里会自己把仓库根塞进 sys.path。
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

if __package__ in (None, ''):  # 直接跑文件时，先让 `import tools.xxx` 能用
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.common.bootstrap import ensure_repo_root, setup_logging
from tools.report_ai_worker_tool.config.worker_config import CONFIG
from tools.report_ai_worker_tool.worker_service.worker_service import ReportAiWorkerService

logger = logging.getLogger('report_ai_worker')


async def main() -> int:
    ensure_repo_root()
    setup_logging(CONFIG)
    logger.info('配置: %s', CONFIG.to_dict())

    service = ReportAiWorkerService(CONFIG)
    try:
        await service.run()
    except KeyboardInterrupt:
        logger.info('手动停止')
    except Exception:
        logger.exception('Worker 异常退出')
        return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
