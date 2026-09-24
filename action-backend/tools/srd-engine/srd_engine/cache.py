"""抽取结果的磁盘缓存 —— 引擎里唯一读写文件系统的地方。

抽取一篇文献要 4 次模型调用，而「一篇 vs 库里 N 篇」的场景里同一篇会被反复用到，
所以按内容 hash 缓存。判定阶段不缓存：那是两篇之间的比较，每对都不一样。

**key 里必须包含一切会改变 facet 内容的东西**，否则会读到用别的配置抽出来的结果：

- `sha256`         —— 文献内容
- `ENGINE_VERSION` —— 抽取行为由引擎代码决定（切块、合并、正文预处理都在代码里）
- `PROMPT_VERSION` —— 提示词
- `model`          —— 模型

（0.8.1 前还有个 `variant`，装的是 `extract_scope` 开关；那个开关已删，抽取一律喂全文。）

代价是升 `ENGINE_VERSION` 即全量重抽，这是刻意接受的：靠「改引擎时记得顺手改提示词」
那种人工纪律来保证缓存正确性，已经出过一次问题（0.2.0 引入正文预处理时 key 完全没变）。
"""

from __future__ import annotations

import json
from pathlib import Path

from srd_engine.config import ENGINE_VERSION, PROMPT_VERSION
from srd_engine.schemas import ExtractDoc, ParsedDoc


def cache_key(doc: ParsedDoc, model: str) -> str:
    """再加「会改变喂进模型的内容」的运行期开关时，必须同时加进这里，否则不同配置会互相命中。"""
    ver = f'{ENGINE_VERSION}+{PROMPT_VERSION}'.replace('/', '-')
    return f'{doc.sha256[:16]}_{ver}_{model.replace("/", "-")}'


def load(cache_dir: str | Path, doc: ParsedDoc, model: str) -> ExtractDoc | None:
    """读缓存。任何异常都当作未命中 —— 缓存坏了应该重抽，不该让整次评估失败。"""
    path = Path(cache_dir) / f'{cache_key(doc, model)}.json'
    if not path.exists():
        return None
    try:
        return ExtractDoc.model_validate(json.loads(path.read_text(encoding='utf-8')))
    except Exception:
        return None


def save(cache_dir: str | Path, doc: ParsedDoc, model: str, extract: ExtractDoc) -> Path:
    directory = Path(cache_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'{cache_key(doc, model)}.json'
    path.write_text(extract.model_dump_json(indent=2), encoding='utf-8')
    return path
