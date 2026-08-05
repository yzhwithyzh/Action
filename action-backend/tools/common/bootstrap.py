"""进程启动的杂活：日志配置、把仓库根目录塞进 sys.path。

`python -m tools.srd_worker_tool`（在仓库根执行）本来就能 import 到 `tools.common`，
但 `python tools/srd_worker_tool/__main__.py` 这种直接跑文件的用法不行 ——
运维手一抖就会用后者，所以入口里统一调一次 `ensure_repo_root()`。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.common.worker_config import WorkerConfig

# tools/common/bootstrap.py → tools/common → tools → 仓库根
REPO_ROOT = Path(__file__).resolve().parents[2]


def ensure_repo_root() -> Path:
    """保证 `import tools.xxx` 可用，返回仓库根路径。"""
    root = str(REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    return REPO_ROOT


def configure_console() -> None:
    """把 stdout/stderr 切成 UTF-8。

    Windows 控制台默认 GBK，日志里的 `✓ ▶ ■` 会直接抛 UnicodeEncodeError：
    worker 只是丢一行日志，CLI 却会整个崩掉。`errors='replace'` 是兜底，
    保证再冷门的字符也只是显示成 `?`，不会中断进程。
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, 'reconfigure', None)
        if reconfigure is not None:
            try:
                reconfigure(encoding='utf-8', errors='replace')
            except (ValueError, OSError):
                continue


def setup_logging(cfg: WorkerConfig) -> None:
    """控制台 + 单文件的进程级日志。任务级日志走 AsyncLogWriter，不在这里。"""
    configure_console()
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, cfg.log_level, logging.INFO),
        format='%(asctime)s | %(levelname)-7s | %(name)s | %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(cfg.logs_dir / f'{cfg.tool_name}.log', encoding='utf-8'),
        ],
    )
    # 第三方库的 INFO 噪音很大，统一压到 WARNING
    for noisy in ('httpx', 'httpcore', 'openai', 'urllib3', 'asyncio'):
        logging.getLogger(noisy).setLevel(logging.WARNING)
