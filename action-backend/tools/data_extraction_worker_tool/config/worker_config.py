"""
Worker 配置文件
"""
import os
from typing import Dict, Any


class WorkerConfig:
    """Worker 配置类"""

    # Redis 配置
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)

    # 队列名称
    QUEUE_NAME = 'data_extraction'

    # Worker 配置
    WORKER_NAME = 'data_extraction_worker'

    # 日志配置
    LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')

    # 临时文件目录
    TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'temp')

    # 任务超时时间（秒）
    JOB_TIMEOUT = 7200  # 2 小时

    # 结果保留时间（秒）
    RESULT_TTL = 86400  # 24 小时

    @classmethod
    def get_redis_url(cls) -> str:
        """获取 Redis 连接 URL"""
        if cls.REDIS_PASSWORD:
            return f"redis://:{cls.REDIS_PASSWORD}@{cls.REDIS_HOST}:{cls.REDIS_PORT}/{cls.REDIS_DB}"
        return f"redis://{cls.REDIS_HOST}:{cls.REDIS_PORT}/{cls.REDIS_DB}"

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'redis_host': cls.REDIS_HOST,
            'redis_port': cls.REDIS_PORT,
            'redis_db': cls.REDIS_DB,
            'queue_name': cls.QUEUE_NAME,
            'worker_name': cls.WORKER_NAME,
            'job_timeout': cls.JOB_TIMEOUT,
            'result_ttl': cls.RESULT_TTL,
        }
