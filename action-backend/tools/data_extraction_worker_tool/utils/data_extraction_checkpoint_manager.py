"""
DataExtractionCheckpointManager: 数据抽取断点续传管理器

文件位置: backend/tools/data_extraction_worker_tool/utils/data_extraction_checkpoint_manager.py

双重存储策略:
1. 数据库 data_extraction_file_status: 记录状态、时间、错误信息
2. JSON 文件 checkpoint/{session_id}/results/*.json: 记录完整结果

职责:
- 保存单个文件的处理结果（DB + JSON）
- 加载某个 session 的断点信息
- 检查是否需要断点续传
- 任务完成后清理 JSON 临时数据
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from tools.common.checkpoint_json_manager import CheckpointJsonManager

logger = logging.getLogger(__name__)


class DataExtractionCheckpointManager:
    """
    数据抽取断点续传管理器

    双重存储策略:
    1. 数据库 data_extraction_file_status: 记录状态、时间、错误信息
    2. JSON 文件 checkpoint/{session_id}/results/*.json: 记录完整结果

    职责:
    - 保存单个文件的处理结果（DB + JSON）
    - 加载某个 session 的断点信息
    - 检查是否需要断点续传
    - 任务完成后清理 JSON 临时数据
    """

    def __init__(self, session_id: str, checkpoint_dir: Optional[str] = None):
        """
        初始化断点管理器

        Args:
            session_id: 会话 ID（与 DB 中一致）
            checkpoint_dir: checkpoint 目录（默认自动生成）
        """
        self.session_id = session_id

        # 确定 checkpoint 根目录
        if checkpoint_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            checkpoint_dir = os.path.join(base_dir, 'checkpoint', session_id)

        self.checkpoint_dir = checkpoint_dir
        self.results_dir = os.path.join(checkpoint_dir, 'results')
        self.status_file = os.path.join(checkpoint_dir, 'file_status.json')

        # 确保目录存在
        os.makedirs(self.results_dir, exist_ok=True)

        # JSON 管理器仅负责文件层面的存储
        self.json_manager = CheckpointJsonManager(checkpoint_dir)

        logger.info(f"DataExtractionCheckpointManager 初始化成功: session_id={session_id}, dir={checkpoint_dir}")

    # ===================== 1. 保存文件结果 =====================

    async def save_file_result(
        self,
        db: AsyncSession,
        file_name: str,
        result_data: Dict[str, Any],
        processing_duration: Optional[int] = None
    ) -> bool:
        """
        保存单个文件的处理结果（JSON + DB）

        Args:
            db: 数据库会话
            file_name: 文件名
            result_data: 结果数据
            processing_duration: 处理耗时（秒）（可选）

        流程:
        1. 将 result_data 保存为 JSON（file_name.json）到临时文件夹
        2. 更新 DB 该文件状态为 completed（不存储 extraction_result）

        Returns:
            True: 保存成功
            False: 任何一步失败
        """
        try:
            # 1. JSON 文件存储到临时文件夹
            self.json_manager.save_file_result(file_name, result_data)

            # 2. 更新数据库（仅标记状态，不存储结果）
            from module_common.service.data_extraction_file_status_service import DataExtractionFileStatusService

            await DataExtractionFileStatusService.mark_as_completed(
                db=db,
                session_id=self.session_id,
                file_name=file_name
            )
            await db.commit()

            logger.info(f"✓ 断点保存成功: session={self.session_id}, file={file_name}")
            return True

        except Exception as e:
            logger.error(f"✗ 保存文件结果失败 [{file_name}]: {str(e)}")
            await db.rollback()
            return False

    # ===================== 2. 加载断点数据 =====================

    async def load_checkpoint(self, db: AsyncSession) -> Dict[str, Any]:
        """
        加载断点数据（用于恢复任务）

        Args:
            db: 数据库会话

        Returns:
            {
                'completed_files': [file_index1, ...],
                'pending_files': [file_index2, ...],
                'completed_results': [result1, result2, ...],
                'total_completed': int,
                'total_pending': int,
            }
        """
        try:
            from module_common.service.data_extraction_file_status_service import DataExtractionFileStatusService

            # 1. 查询各状态文件
            completed_files = await DataExtractionFileStatusService.get_completed_files(
                db=db,
                session_id=self.session_id
            )
            pending_files = await DataExtractionFileStatusService.get_pending_files(
                db=db,
                session_id=self.session_id
            )

            # 2. 加载 JSON 结果
            completed_results = self.json_manager.load_all_results()

            checkpoint_data = {
                'completed_files': [f['file_index'] for f in completed_files],
                'pending_files': [f['file_index'] for f in pending_files],
                'completed_results': completed_results,
                'total_completed': len(completed_files),
                'total_pending': len(pending_files),
            }

            logger.info(
                "✓ 断点数据加载成功: session=%s, completed=%d, pending=%d",
                self.session_id,
                len(completed_files),
                len(pending_files),
            )

            return checkpoint_data

        except Exception as e:
            logger.error(f"✗ 加载断点数据失败: {str(e)}")
            return {
                'completed_files': [],
                'pending_files': [],
                'completed_results': [],
                'total_completed': 0,
                'total_pending': 0,
            }

    # ===================== 3. 检查是否需要断点续传 =====================

    async def need_resume(self, db: AsyncSession) -> bool:
        """
        检查是否需要断点续传

        逻辑：
        - 当前 session 已有部分文件 completed 或 processing
        - 且仍有 pending 文件
        => 返回 True

        Args:
            db: 数据库会话
        """
        from module_common.service.data_extraction_file_status_service import DataExtractionFileStatusService

        needs_resume, stats = await DataExtractionFileStatusService.check_resume_needed(
            db=db,
            session_id=self.session_id
        )

        if needs_resume:
            logger.warning(
                "⚠️ 检测到断点数据: session=%s, stats=%s",
                self.session_id,
                stats
            )

        return needs_resume

    # ===================== 4. 清理 =====================

    def cleanup(self):
        """清理 JSON 临时数据"""
        try:
            self.json_manager.cleanup()
            logger.info(f"✓ 断点临时数据已清理: session={self.session_id}")
        except Exception as e:
            logger.warning(f"清理断点数据失败: {str(e)}")
