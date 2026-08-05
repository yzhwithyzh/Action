"""断点数据的 JSON 落盘 —— 任务重跑时避开已经花过钱的步骤。

刻意做得很笨：一个 session 一个目录，一个中间产物一个 JSON 文件。
不上数据库，是因为断点数据只对「同一台 worker 上的重跑」有意义，
跨机重跑本来就要重新下载文件，省不下什么。

写入走「先写 .tmp 再 replace」，避免任务被 kill 在写文件正中间时留下半个 JSON ——
半个 JSON 比没有更糟：下次重跑会当成有效断点读进来。
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_UNSAFE = re.compile(r'[^0-9A-Za-z_.\-一-鿿]+')


def safe_name(name: str) -> str:
    """把任意标识（文件名、URL 片段）压成安全的文件名。"""
    cleaned = _UNSAFE.sub('_', name).strip('_')
    return (cleaned or 'item')[:120]


class CheckpointJsonManager:
    """一个 session 一个实例。"""

    def __init__(self, checkpoint_dir: Path | str) -> None:
        self.dir = Path(checkpoint_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def path_of(self, name: str) -> Path:
        return self.dir / f'{safe_name(name)}.json'

    def exists(self, name: str) -> bool:
        return self.path_of(name).exists()

    def save(self, name: str, data: Any) -> Path:
        path = self.path_of(name)
        tmp = path.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
        tmp.replace(path)
        return path

    def save_text(self, name: str, text: str, suffix: str = '.txt') -> Path:
        """非 JSON 的中间产物（渲染好的报告文本、CSV 等）。"""
        path = self.dir / f'{safe_name(name)}{suffix}'
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(text, encoding='utf-8')
        tmp.replace(path)
        return path

    def load(self, name: str) -> Any | None:
        """读不出来一律当没有断点 —— 断点坏了应该重跑，不该让任务失败。"""
        path = self.path_of(name)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception as exc:
            logger.warning('断点文件损坏，忽略 [%s]: %s', path.name, exc)
            return None

    def load_all(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for path in sorted(self.dir.glob('*.json')):
            try:
                results[path.stem] = json.loads(path.read_text(encoding='utf-8'))
            except Exception as exc:  # noqa: PERF203 —— 单个断点文件坏掉不能影响其余，必须逐个兜
                logger.warning('断点文件损坏，跳过 [%s]: %s', path.name, exc)
        return results

    def delete(self, name: str) -> None:
        self.path_of(name).unlink(missing_ok=True)

    def cleanup(self) -> None:
        """任务真正完成后删掉整个断点目录。"""
        try:
            shutil.rmtree(self.dir, ignore_errors=True)
        except Exception as exc:
            logger.warning('清理断点目录失败 [%s]: %s', self.dir, exc)
