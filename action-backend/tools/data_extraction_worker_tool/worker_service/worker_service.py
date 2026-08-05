"""
Worker Service：单进程异步调度器
"""
import asyncio
import logging
from typing import Set, Optional
from datetime import datetime

from tools.data_extraction_worker_tool.worker_service.redis_queue_manager import RedisQueueManager
from tools.common.resource_limiter import ResourceLimiter
from tools.data_extraction_worker_tool.worker_service.data_extraction_session_task import DataExtractionSessionTask

logger = logging.getLogger(__name__)


class WorkerService:
    """单进程异步 Worker Service：持续从 Redis 拉取任务并异步处理"""

    def __init__(
        self,
        max_concurrent_sessions: int = 5,
        max_concurrent_pdfs: int = 20,
        max_concurrent_llm_calls: int = 50
    ):
        """
        初始化 Worker Service

        Args:
            max_concurrent_sessions: 最大并发 session 数量
            max_concurrent_pdfs: 最大并发 PDF 解析数量
            max_concurrent_llm_calls: 最大并发 LLM 调用数量
        """
        # Redis 队列管理器
        self.redis_manager = RedisQueueManager()

        # 资源限流器
        self.resource_limiter = ResourceLimiter(
            max_concurrent_sessions=max_concurrent_sessions,
            max_concurrent_pdfs=max_concurrent_pdfs,
            max_concurrent_llm_calls=max_concurrent_llm_calls
        )

        # 运行中的任务集合
        self.running_tasks: Set[asyncio.Task] = set()

        # 运行状态标志
        self.shutdown_flag = False

        logger.info("Worker Service 初始化完成")

    async def run(self):
        """主循环：持续从 Redis 拉取任务"""
        logger.info("=" * 60)
        logger.info("Data Extraction Worker Service (Async)")
        logger.info("=" * 60)
        logger.info("Worker Service 已启动，正在监听 Redis 队列...")
        logger.info("按 Ctrl+C 停止 Worker Service")
        logger.info("=" * 60)

        try:
            # 连接 Redis
            await self.redis_manager.connect()

            # 主循环
            while not self.shutdown_flag:
                try:
                    # 从 Redis 队列拉取任务（blocking pop，超时 5 秒）
                    task_data = await self.redis_manager.pop_task(timeout=5)

                    if task_data:
                        # 创建异步任务处理 session
                        task = asyncio.create_task(self._handle_session(task_data))

                        # 添加到运行中的任务集合
                        self.running_tasks.add(task)

                        # 任务完成后自动从集合中移除
                        task.add_done_callback(self.running_tasks.discard)

                        logger.info(f"任务已提交: {task_data.get('session_id')} "
                                   f"(当前运行任务数: {len(self.running_tasks)})")

                    else:
                        # 没有任务，继续循环（避免 CPU 空转）
                        await asyncio.sleep(1)

                except asyncio.CancelledError:
                    logger.info("收到取消信号，停止拉取任务...")
                    break

                except Exception as e:
                    logger.error(f"拉取任务失败: {str(e)}")
                    await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("收到中断信号（Ctrl+C），正在关闭...")

        finally:
            # 优雅关闭
            await self.shutdown_gracefully()

    async def _handle_session(self, task_data: dict):
        """
        处理一个 session（异步）

        Args:
            task_data: 任务数据
                {
                    'session_id': str,
                    'user_id': int,
                    'file_urls': List[str],
                    'extraction_config': Dict[str, Any]
                }
        """
        session_id = task_data.get('session_id', 'unknown')

        # 使用资源限流器的 session 信号量
        try:
            # 获取 session 槽位（限流）
            await self.resource_limiter.acquire_session_slot()

            logger.info(f"开始处理 Session: {session_id}")

            # NEW: 从数据库查询 freeze_id
            freeze_id = None
            try:
                from config.database import AsyncSessionLocal
                from module_client.service.data_extraction_service import DataExtractionHistoryService

                async with AsyncSessionLocal() as db:
                    history = await DataExtractionHistoryService.get_by_session(db, session_id)
                    freeze_id = history.freeze_id if history else None

                    if freeze_id:
                        logger.info(f"查询到冻结记录ID: {freeze_id} - session_id: {session_id}")
                    else:
                        logger.warning(f"未找到冻结记录ID - session_id: {session_id}")
            except Exception as e:
                logger.error(f"查询 freeze_id 失败: {e}")

            # 创建 DataExtractionSessionTask (NEW: 传入 freeze_id)
            session_task = DataExtractionSessionTask(
                session_id=session_id,
                user_id=task_data.get('user_id'),
                file_urls=task_data.get('file_urls', []),
                extraction_config=task_data.get('extraction_config', {}),
                resource_limiter=self.resource_limiter,
                freeze_id=freeze_id  # NEW: 传入冻结记录ID
            )

            # 运行 SessionTask
            await session_task.run()

            logger.info(f"Session 完成: {session_id}")

        except Exception as e:
            logger.error(f"Session 执行失败 [{session_id}]: {str(e)}")

        finally:
            # 释放 session 槽位
            self.resource_limiter.release_session_slot()

            # 打印资源使用统计
            stats = self.resource_limiter.get_stats()
            logger.info(f"资源使用情况: "
                       f"Sessions={stats['session_slots']['used']}/{stats['session_slots']['total']}, "
                       f"PDFs={stats['pdf_slots']['used']}/{stats['pdf_slots']['total']}, "
                       f"LLM={stats['llm_slots']['used']}/{stats['llm_slots']['total']}")

    async def shutdown_gracefully(self):
        """优雅关闭：等待所有运行中的任务完成"""
        logger.info("正在优雅关闭 Worker Service...")

        # 设置关闭标志
        self.shutdown_flag = True

        # 等待所有运行中的任务完成
        if self.running_tasks:
            logger.info(f"等待 {len(self.running_tasks)} 个任务完成...")

            try:
                # 等待所有任务完成（超时 60 秒）
                await asyncio.wait_for(
                    asyncio.gather(*self.running_tasks, return_exceptions=True),
                    timeout=60.0
                )
                logger.info("所有任务已完成")

            except asyncio.TimeoutError:
                logger.warning("任务超时，强制关闭")

                # 取消所有未完成的任务
                for task in self.running_tasks:
                    task.cancel()

        # 断开 Redis 连接
        await self.redis_manager.disconnect()

        logger.info("Worker Service 已停止")

    def get_status(self) -> dict:
        """
        获取 Worker Service 状态

        Returns:
            状态信息字典
        """
        return {
            'running': not self.shutdown_flag,
            'running_tasks': len(self.running_tasks),
            'resource_stats': self.resource_limiter.get_stats(),
            'timestamp': datetime.now().isoformat()
        }
