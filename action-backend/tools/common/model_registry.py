"""模型池加载 —— 从 `ai_models` 表取「现在能用的模型」。

worker 与后端共用同一份筛选/解密逻辑（`AiModelService.get_usable_ai_model_pool_services`），
所以后台改了模型配置，下一个任务立刻生效，不需要重启 worker，也不需要把密钥写进 Redis 队列。

    from tools.common.model_registry import load_llm_models

    models = await load_llm_models()                    # 全部启用中的模型，按 model_sort
    models = await load_llm_models(model_ids=[3, 7])    # 只用指定的几个

本模块刻意**不** import 引擎（srd_engine）的任何东西：tools/common 是通用骨架，
各个工具自己把 `LlmModelInfo` 转成它那套模型配置对象（SRD 是 `ModelConfig`）。

依赖说明：这里会 import `config.database` 与 `module_ai`，也就是说 worker 进程需要能连上
后端那套数据库（工作目录本来就是 action-backend）。连不上时抛异常，由调用方决定是回落到
环境变量还是直接判任务失败 —— 本模块不替调用方做这个决定。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LlmModelInfo:
    """一个可直接发起调用的模型（api_key 已是明文）。"""

    model_id: int
    provider: str
    model_code: str
    model_name: str
    api_key: str
    base_url: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    model_type: str = ''

    @property
    def ref(self) -> str:
        """池内唯一标识。带表名前缀，避免和别处的模型标识撞车。"""
        return f'ai_models:{self.model_id}'

    @property
    def label(self) -> str:
        return f'{self.provider}/{self.model_code}#{self.model_id}'


async def load_llm_models(
    model_ids: list[int] | None = None,
    model_types: list[str] | None = None,
) -> list[LlmModelInfo]:
    """读取可用模型池。按 `model_sort` 排序，轮询顺序就是这个顺序。

    :param model_ids: 只取这些模型主键（任务 payload 可以指定）
    :param model_types: 只取这些模型类型（`ai_models.model_type` 是自由文本，默认不过滤）
    """
    # 局部 import：tools/common 的其他模块不该被后端的数据库配置连坐，
    # 没有 .env 的环境（比如只跑框架单测）照样能 import 本文件。
    from config.database import AsyncSessionLocal  # noqa: PLC0415
    from module_ai.service.ai_model_service import AiModelService  # noqa: PLC0415

    async with AsyncSessionLocal() as session:
        pool = await AiModelService.get_usable_ai_model_pool_services(session, model_ids, model_types)

    models = [
        LlmModelInfo(
            model_id=int(item.model_id),
            provider=(item.provider or 'OpenAI').strip(),
            model_code=(item.model_code or '').strip(),
            model_name=(item.model_name or '').strip(),
            api_key=(item.api_key or '').strip(),
            base_url=(item.base_url or '').strip() or None,
            temperature=item.temperature,
            max_tokens=item.max_tokens,
            model_type=(item.model_type or '').strip(),
        )
        for item in pool
        if item.model_id and item.model_code and item.api_key
    ]
    logger.info('从 ai_models 取到 %d 个可用模型: %s', len(models), '、'.join(m.label for m in models))
    return models
