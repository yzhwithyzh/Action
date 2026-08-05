"""SRD Worker 启动入口。

    cd <仓库根>
    python -m tools.srd_worker_tool

也支持直接跑文件（`python tools/srd_worker_tool/__main__.py`）—— 入口里会自己把仓库根塞进 sys.path。
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

if __package__ in (None, ''):  # 直接跑文件时，先让 `import tools.xxx` 能用
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.common.bootstrap import ensure_repo_root, setup_logging
from tools.srd_worker_tool.config.worker_config import CONFIG
from tools.srd_worker_tool.worker_service.worker_service import SrdWorkerService

logger = logging.getLogger('srd_worker')


async def main() -> int:
    ensure_repo_root()
    setup_logging(CONFIG)
    logger.info('配置: %s', CONFIG.to_dict())

    service = SrdWorkerService(CONFIG)
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
