"""
数据抽取 Worker 主入口
"""
import asyncio
import logging
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.data_extraction_worker_tool.worker_service.worker_service import WorkerService

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('data_extraction_worker.log')
    ]
)

logger = logging.getLogger(__name__)


async def main():
    """主函数"""
    # 创建并运行 Worker Service
    worker = WorkerService(
        max_concurrent_sessions=5,
        max_concurrent_pdfs=20,
        max_concurrent_llm_calls=50
    )

    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Worker 已手动停止")
    except Exception as e:
        logger.error(f"Worker 运行异常: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
