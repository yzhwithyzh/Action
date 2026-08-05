"""SRD 评估引擎.

系统综述重复性评估（Systematic Review Duplication）：给定两篇系统综述，
逐条目判定是否重复，再由代码按表 2 / 表 3 算出领域与整体判定。

设计见同目录上级的 DESIGN.md。本包**不依赖任何后端模块**，可独立 pip install -e 后用 CLI 跑。
"""

from srd_engine.config import CRITERIA_VERSION, ENGINE_VERSION, PROMPT_VERSION, EngineConfig, ModelConfig

__all__ = [
    'CRITERIA_VERSION',
    'ENGINE_VERSION',
    'PROMPT_VERSION',
    'EngineConfig',
    'ModelConfig',
]
