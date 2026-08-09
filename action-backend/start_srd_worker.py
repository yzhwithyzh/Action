"""SRD 评估 Worker Service 启动脚本：单进程异步 Worker。

    cd action-backend
    python start_srd_worker.py --env dev

与 `python -m tools.srd_worker_tool` 等价 —— 真正的服务实现在
`tools/srd_worker_tool/worker_service/`，这里只是给运维一个不用记模块路径的入口
（与 `start_data_extraction_worker.py` 保持同一种用法），并补上模块入口里没有的东西：

1. 把 `action-backend/` 塞进 `sys.path`：从任意工作目录 `python /path/to/start_srd_worker.py`
   都能 import 到 `tools.*` 与 `config.*`；
2. 用 `signal.signal` 兜一层停止信号 —— 服务自己装的是 `loop.add_signal_handler`，
   Windows 的 ProactorEventLoop 不支持，装不上就只能靠 Ctrl+C，SIGTERM 直接被当成强杀。
   Linux 上服务装的那份会覆盖这里的，行为不变。

`--env` 由 `config/env.py` 的 `parse_cli_args()` 解析（决定读哪个 `.env`），不传就是 `dev`；
`start_srd_worker.sh` 按 `APP_ENV` 带上，默认同样是 `dev`，上生产库时改传 `prod`。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import FrameType

# 添加 action-backend 目录到 Python 路径（必须在导入 tools/config 之前，E402 是刻意的）
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from tools.common.bootstrap import ensure_repo_root, setup_logging  # noqa: E402
from tools.srd_worker_tool.config.worker_config import CONFIG  # noqa: E402
from tools.srd_worker_tool.worker_service.worker_service import SrdWorkerService  # noqa: E402

logger = logging.getLogger('srd_worker')


def install_signal_fallback(service: SrdWorkerService) -> None:
    """SIGINT/SIGTERM 的兜底处理器：只置停止标志，收尾交给服务自己。

    别在这里 `asyncio.create_task(...)`：信号处理器跑在主线程的字节码间隙，
    不保证有 running loop（Windows 上尤其），而 `request_shutdown()` 只是改个 bool，
    在任何上下文里都安全。worker 最迟在下一次 blpop 超时（pop_timeout，默认 5s）时看到它。
    """

    def handler(signum: int, _frame: FrameType | None) -> None:
        logger.info('收到信号 %s，开始优雅关闭...', signum)
        service.request_shutdown()

    for sig in (signal.SIGINT, signal.SIGTERM):
        # 装不上就算了（不在主线程 / 平台不支持该信号）：服务自己那份 add_signal_handler 还在
        with contextlib.suppress(ValueError, OSError, AttributeError):
            signal.signal(sig, handler)


async def main() -> int:
    ensure_repo_root()
    setup_logging(CONFIG)

    logger.info('=' * 60)
    logger.info('SRD 评估 Worker Service 启动中...')
    logger.info('=' * 60)
    logger.info('配置: %s', CONFIG.to_dict())

    service = SrdWorkerService(CONFIG)
    install_signal_fallback(service)

    try:
        await service.run()
    except KeyboardInterrupt:
        logger.info('收到键盘中断，正在关闭...')
    except Exception:
        logger.exception('Worker Service 运行异常')
        return 1
    finally:
        logger.info('=' * 60)
        logger.info('SRD 评估 Worker Service 已完全停止')
        logger.info('=' * 60)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        print('\n程序已终止')
