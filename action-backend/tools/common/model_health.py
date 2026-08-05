"""模型健康状态（冻结表）—— 多进程共享的「这个模型现在别用」标记。

某个模型撞到限流 / 欠费 / 鉴权错误时，调用方把它冻结一段时间（默认 5 分钟）并切到下一个；
冻结记录写在 Redis 里，**所有 worker 进程与后端共用同一份**：A 进程撞到限流之后，
B 进程不会再去撞一次。冻结用 Redis key 的 TTL 表达，到期自动消失，不需要任何清理逻辑。

键位（刻意不含工具名，跨工具共享）::

    {namespace}:llm:freeze:{model_ref}    string，value=冻结原因，TTL=剩余冻结时长

接口与 `srd_engine.adapters.langchain_client.ModelHealth` 协议一致，可以直接塞给 LlmRunner。
Redis 抖动时一律按「模型可用」处理 —— 健康表本身出问题，不该顺带把任务也停了。
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis import asyncio as aioredis

    from tools.common.worker_config import WorkerConfig

logger = logging.getLogger(__name__)

# key 存在但没有 TTL（理论上不会发生）时，按这个时长当作剩余冻结时间，避免永久拉黑
FALLBACK_FREEZE_SECONDS = 60.0


class RedisModelHealth:
    """Redis 实现，生产用。"""

    def __init__(self, cfg: WorkerConfig, client: aioredis.Redis) -> None:
        self.cfg = cfg
        self.redis = client

    def key(self, model_ref: str) -> str:
        return self.cfg.llm_freeze_key(model_ref)

    async def frozen_seconds(self, key: str) -> float:
        try:
            ttl = int(await self.redis.pttl(self.key(key)))
        except Exception as exc:
            logger.debug('查询模型冻结状态失败 [%s]: %s', key, exc)
            return 0.0
        if ttl > 0:
            return ttl / 1000
        return FALLBACK_FREEZE_SECONDS if ttl == -1 else 0.0

    async def freeze(self, key: str, seconds: float, reason: str) -> None:
        if seconds <= 0:
            return
        try:
            await self.redis.set(self.key(key), reason[:500], ex=math.ceil(seconds))
        except Exception as exc:
            logger.warning('写模型冻结标记失败 [%s]: %s', key, exc)

    async def thaw(self, key: str) -> None:
        """手动解冻（运维接口用：改完配置想立刻恢复，不用等 5 分钟）。"""
        try:
            await self.redis.delete(self.key(key))
        except Exception as exc:
            logger.warning('解冻模型失败 [%s]: %s', key, exc)

    async def snapshot(self) -> dict[str, dict[str, object]]:
        """当前所有被冻结的模型（监控 / 排障用）。"""
        prefix = self.cfg.llm_freeze_key('')
        result: dict[str, dict[str, object]] = {}
        try:
            async for name in self.redis.scan_iter(match=f'{prefix}*'):
                ttl = int(await self.redis.pttl(name))
                result[str(name)[len(prefix) :]] = {
                    'reason': await self.redis.get(name),
                    'remaining': max(0.0, ttl / 1000),
                }
        except Exception as exc:
            logger.warning('读取模型冻结快照失败: %s', exc)
        return result
