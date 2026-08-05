"""
Redis 队列管理器：异步 Redis 操作
"""
import json
import logging
from typing import Dict, Any, Optional
import redis.asyncio as aioredis

from tools.data_extraction_worker_tool.config.worker_config import WorkerConfig

logger = logging.getLogger(__name__)


class RedisQueueManager:
    """Redis 队列管理器（异步）"""

    def __init__(self):
        """初始化 Redis 连接"""
        self.redis_client: Optional[aioredis.Redis] = None
        self.queue_name = WorkerConfig.QUEUE_NAME

    async def connect(self):
        """连接到 Redis"""
        if self.redis_client is None:
            redis_url = WorkerConfig.get_redis_url()
            self.redis_client = await aioredis.from_url(
                redis_url,
                decode_responses=True,
                encoding='utf-8'
            )
            logger.info(f"已连接到 Redis: {WorkerConfig.REDIS_HOST}:{WorkerConfig.REDIS_PORT}")

    async def disconnect(self):
        """断开 Redis 连接"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            logger.info("已断开 Redis 连接")

    async def push_task(self, task_data: Dict[str, Any]) -> bool:
        """
        推送任务到队列（rpush）

        Args:
            task_data: 任务数据字典
                {
                    'session_id': str,
                    'user_id': int,
                    'file_urls': List[str],
                    'prompts': Dict[str, str]
                }

        Returns:
            是否成功
        """
        try:
            await self.connect()

            # 序列化任务数据
            task_json = json.dumps(task_data, ensure_ascii=False)

            # 推送到队列尾部
            await self.redis_client.rpush(self.queue_name, task_json)

            logger.info(f"任务已推送到队列: {task_data.get('session_id')}")
            return True

        except Exception as e:
            logger.error(f"推送任务失败: {str(e)}")
            return False

    async def pop_task(self, timeout: int = 5) -> Optional[Dict[str, Any]]:
        """
        从队列拉取任务（blpop，blocking pop）

        Args:
            timeout: 超时时间（秒），0 表示无限等待

        Returns:
            任务数据字典，如果超时则返回 None
        """
        try:
            await self.connect()

            # 阻塞式拉取（从队列头部）
            result = await self.redis_client.blpop(self.queue_name, timeout=timeout)

            if result:
                _, task_json = result
                task_data = json.loads(task_json)
                logger.info(f"从队列拉取任务: {task_data.get('session_id')}")
                return task_data

            return None

        except Exception as e:
            logger.error(f"拉取任务失败: {str(e)}")
            return None

    async def get_queue_length(self) -> int:
        """
        获取队列长度

        Returns:
            队列中的任务数量
        """
        try:
            await self.connect()
            length = await self.redis_client.llen(self.queue_name)
            return length

        except Exception as e:
            logger.error(f"获取队列长度失败: {str(e)}")
            return 0

    async def clear_queue(self) -> bool:
        """
        清空队列（危险操作，仅用于测试）

        Returns:
            是否成功
        """
        try:
            await self.connect()
            await self.redis_client.delete(self.queue_name)
            logger.warning(f"队列已清空: {self.queue_name}")
            return True

        except Exception as e:
            logger.error(f"清空队列失败: {str(e)}")
            return False
