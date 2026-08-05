"""
数据抽取 Session 任务处理器：处理单个 session 的所有文件
重构说明：继承 BaseSessionTask 基类，大幅减少重复代码
"""
import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from decimal import Decimal
import logging

from tools.common.base_session_task import BaseSessionTask, SessionConfig
from tools.data_extraction_tool.src.extractors.json_extractor import JsonExtractor
from utils.cos_file_util import CosFileUtil
from exceptions.exception import ServiceException

logger = logging.getLogger(__name__)


class DataExtractionSessionTask(BaseSessionTask):
    """数据抽取 Session 任务处理器：继承自 BaseSessionTask"""

    def __init__(
        self,
        session_id: str,
        user_id: int,
        file_urls: List[str],
        extraction_config: Dict[str, Any],
        resource_limiter,
        freeze_id: Optional[int] = None  # NEW: 冻结记录ID
    ):
        """
        初始化数据抽取 Session 任务

        Args:
            session_id: 会话 ID
            user_id: 用户 ID
            file_urls: 文件 URL 列表
            extraction_config: 数据抽取配置
                {
                    'extraction_mode': 'table' or 'json',
                    'schema': {...},
                    'llm_config': {...}
                }
            resource_limiter: 资源限流器
            freeze_id: 冻结记录ID(用于任务完成后的余额结算)
        """
        # 调用父类构造函数
        super().__init__(session_id, user_id, resource_limiter)

        # 子类特有的属性
        self.file_urls = file_urls
        self.extraction_config = extraction_config
        self.config_file = None

        # 停止标志（内存缓存，避免频繁 Redis 查询）
        self._is_stopped = False

        # NEW: 余额冻结相关
        self.freeze_id = freeze_id  # 冻结记录ID
        self.total_actual_cost = Decimal('0.0000')  # 累计实际消耗

    # ==================== 实现抽象方法 ====================

    def _get_worker_tool_name(self) -> str:
        """返回 worker tool 名称"""
        return 'data_extraction_worker_tool'

    def _get_service_class(self):
        """返回对应的 Service 类"""
        from module_common.service.data_extraction_history_service import DataExtractionHistoryService
        return DataExtractionHistoryService

    # ==================== 覆盖父类方法以自定义行为 ====================

    def _create_work_dirs(self):
        """自定义工作目录结构（使用 temp 目录）"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.work_dir = os.path.join(base_dir, 'temp', self.session_id)
        self.input_dir = os.path.join(self.work_dir, 'input')
        self.output_dir = os.path.join(self.work_dir, 'output')

        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

        logger.info(f"工作目录已创建: {self.work_dir}")

    # ==================== 停止检查逻辑 ====================

    async def _check_if_stopped(self) -> bool:
        """
        检查任务是否已被用户停止（使用 Redis + 内存缓存，高性能）

        优化策略：
        1. 使用内存标志缓存，一旦检测到停止就不再查询
        2. Redis 操作极快（内存读取），支持 1000+ 并发

        Returns:
            bool: True 表示任务已停止，应终止处理
        """
        # 如果已经标记为停止，直接返回（避免重复查询 Redis）
        if self._is_stopped:
            return True

        try:
            # 从 utils.redis_client 获取 Redis 连接
            from utils.redis_client import get_redis_client

            redis_client = await get_redis_client()

            # Redis key: stop_flag:{session_id}
            stop_key = f"stop_flag:{self.session_id}"
            is_stopped = await redis_client.get(stop_key)

            if is_stopped:
                # 缓存到内存，避免后续重复查询
                self._is_stopped = True
                logger.info(f"⏸️  检测到停止标志（Redis key: {stop_key}）")
                return True

            return False

        except Exception as e:
            logger.error(f"检查停止标志失败: {str(e)}")
            # 出错时降级到数据库检查（保证可靠性）
            try:
                async with self.db_lock:
                    from module_common.service.data_extraction_history_service import DataExtractionHistoryService
                    task = await DataExtractionHistoryService.get_by_session(self.db_session, self.session_id)
                    if task and task.status == 'stopped':
                        self._is_stopped = True
                        return True
            except Exception:
                pass
            return False

    async def _periodic_stop_check_task(self):
        """
        定期检查停止信号的后台任务（每 30 秒检查一次）

        注意：
        - 断点数据由 FileStatusService 自动保存到数据库，无需手动保存
        - 这个任务只负责检查停止信号
        """
        while True:
            try:
                await asyncio.sleep(30)  # 每 30 秒检查一次

                # ⚡ 检查任务是否被用户停止
                if await self._check_if_stopped():
                    logger.info("⏸️  定期检查任务检测到停止信号，终止处理")
                    # 触发 CancelledError 来停止主任务
                    raise asyncio.CancelledError("用户停止任务")

            except asyncio.CancelledError:
                logger.info("定期检查任务被取消")
                raise

    async def _init_session(self):
        """初始化会话（添加配置文件准备）"""
        await super()._init_session()

        # 创建临时配置文件
        self._prepare_extraction_config()

    # ==================== 核心业务逻辑 ====================

    async def _process_phase(self):
        """
        核心处理阶段：数据抽取的完整流程

        流程：
        1. 初始化断点管理器
        2. 检查并加载断点
        3. 下载文件
        4. 处理文档（支持断点续传）
        5. 上传结果
        6. 更新状态
        """
        try:
            # 初始化 CheckpointManager
            from tools.data_extraction_worker_tool.utils.checkpoint_manager import DataExtractionCheckpointManager
            checkpoint_manager = DataExtractionCheckpointManager(self.session_id)

            # 检查并加载断点
            completed_indices = await self._check_and_load_checkpoint(checkpoint_manager)

            # 阶段 1: 下载文件
            saved_files = await self._download_phase(completed_indices, checkpoint_manager)

            # 阶段 2: 处理文档（复杂 + 简单）
            output_excel, simple_output_excel = await self._processing_phase(checkpoint_manager, completed_indices)

            # 阶段 3: 完成任务
            await self._finalize_phase(output_excel, checkpoint_manager, simple_output_excel)

        except asyncio.CancelledError:
            # 用户主动停止任务
            logger.info(f"Session 被用户停止 [{self.session_id}]")

            if self.log_writer:
                await self.log_writer.write_warning("⏸️  任务已被用户停止")

            # 保存断点数据
            try:
                checkpoint_manager.cleanup()  # 保存当前进度
                if self.log_writer:
                    await self.log_writer.write_info("💾 断点数据已保存，可稍后恢复任务")
            except Exception as e:
                logger.error(f"保存断点数据失败: {str(e)}")

            # 数据库状态已由 stop_process API 更新为 'stopped'，这里无需再次更新
            raise  # 重新抛出以便上层处理

        except Exception as e:
            logger.error(f"Session 执行失败 [{self.session_id}]: {str(e)}")

            if self.log_writer:
                await self.log_writer.write_error(f"任务失败: {str(e)}")

            # 更新数据库：错误状态
            if self.db_session:
                service = self._get_service_class()
                try:
                    await service.update_by_session(
                        self.db_session,
                        self.session_id,
                        {
                            'status': 'error',
                            'error_message': str(e)
                        }
                    )
                    await self.db_session.commit()
                except Exception:
                    pass

            raise  # 重新抛出异常

    def _prepare_extraction_config(self):
        """
        根据 extraction_config 生成临时配置文件
        """
        output_filename = f'extraction_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'

        # 获取 LLM 配置并确保格式正确
        llm_config = self.extraction_config.get('llm_config', {})

        # 如果 llm_config 中没有 'primary' 键，使用整个配置作为 primary
        if llm_config and 'primary' not in llm_config:
            llm_configs = {
                'primary': llm_config,
                'repair': llm_config  # 默认使用相同配置
            }
        else:
            llm_configs = llm_config

        config_data = {
            'user_id': self.user_id,
            'session_id': self.session_id,
            'paths': {
                'input_folder': self.input_dir,
                'output_folder': self.output_dir,
                'output_filename': output_filename
            },
            'mode': {
                'extraction_mode': self.extraction_config.get('extraction_mode', 'table')
            },
            'llm_configs': llm_configs,
            'extraction_schema': self.extraction_config.get('schema', {}),
            'processing': {
                'save_interval': 5,
                'create_debug_files': False,
                'create_process_files': False,
                'split_length': 100000
            }
        }

        # 写入临时配置文件
        self.config_file = os.path.join(self.work_dir, 'config.json')
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)

        logger.info(f"配置文件已创建: {self.config_file}")

    async def _check_and_load_checkpoint(self, checkpoint_manager):
        """检查并加载断点数据"""
        need_resume = await checkpoint_manager.need_resume(self.db_session)

        if need_resume:
            await self.log_writer.write_warning("⚠️ 检测到断点数据，开始断点恢复...")
            checkpoint_data = await checkpoint_manager.load_checkpoint(self.db_session)
            completed_indices = set(checkpoint_data['completed_files'])

            await self.log_writer.write_info(
                f"✓ 断点恢复: 已完成 {len(completed_indices)} 个文件, "
                f"继续处理 {checkpoint_data['total_pending']} 个文件"
            )
        else:
            await self.log_writer.write_info("✓ 无断点数据，从头开始处理")
            completed_indices = set()

        return completed_indices

    async def _download_phase(self, completed_indices, checkpoint_manager):
        """下载阶段：下载文件并更新数据库"""
        await self.log_writer.write_info("=" * 50)
        await self.log_writer.write_info("阶段 1: 文件下载")
        await self.log_writer.write_info("=" * 50)

        saved_files = await self._download_files_with_resume(completed_indices, checkpoint_manager)

        if len(saved_files) == 0 and len(completed_indices) == 0:
            raise Exception("没有成功下载任何文件")

        # 更新数据库记录中的文件信息
        if len(saved_files) > 0:
            total_size = sum(f['file_size'] for f in saved_files)
            await self.log_writer.write_info(f"已下载文件数: {len(saved_files)}")
            await self._update_main_task_with_files(saved_files, total_size)

        return saved_files

    async def _download_files_with_resume(
        self,
        completed_indices: set,
        checkpoint_manager
    ) -> List[Dict[str, Any]]:
        """
        下载文件（支持断点续传、并发下载、批量提交数据库）
        """
        from module_common.service.data_extraction_file_status_service import DataExtractionFileStatusService

        # 1. 获取所有待处理文件
        pending_files = await DataExtractionFileStatusService.get_pending_files(self.db_session, self.session_id)

        if not pending_files:
            await self.log_writer.write_info("无待处理文件")
            return []

        await self.log_writer.write_info(f"开始并发下载 {len(pending_files)} 个文件...")

        # 2. 创建下载信号量（限制并发数）
        download_semaphore = asyncio.Semaphore(SessionConfig.MAX_CONCURRENT_DOWNLOADS)

        async def download_with_semaphore(file_info):
            """带信号量的下载（控制并发数）"""
            async with download_semaphore:
                return await self._download_single_file(file_info, completed_indices)

        # 3. 并发下载所有文件
        download_tasks = [download_with_semaphore(f) for f in pending_files]
        results = await asyncio.gather(*download_tasks, return_exceptions=True)

        # 4. 处理下载结果
        saved_files = []
        status_updates = []

        for result in results:
            if isinstance(result, Exception):
                await self.log_writer.write_error(f"下载任务异常: {str(result)}")
                continue

            if result is None:
                continue

            status_update = result.get('status_update')
            if status_update:
                status_updates.append(status_update)

            if 'file_path' in result:
                saved_files.append({
                    'file_name': result['file_name'],
                    'file_path': result['file_path'],
                    'file_size': result['file_size'],
                    'content_type': result.get('content_type'),
                    'original_filename': result['original_filename'],
                    'source_url': result['source_url'],
                    'is_cos': result['is_cos'],
                })

        # 5. 批量更新数据库状态
        if status_updates:
            await self.log_writer.write_info(f"批量更新 {len(status_updates)} 个文件状态...")
            for update in status_updates:
                status_type = update[0]
                file_name = update[1]

                if status_type == 'processing':
                    local_path = update[2]
                    await DataExtractionFileStatusService.mark_as_processing(
                        self.db_session,
                        self.session_id,
                        file_name,
                        local_path=local_path,
                        auto_commit=False
                    )
                elif status_type == 'error':
                    error_msg = update[2]
                    await DataExtractionFileStatusService.mark_as_error(
                        self.db_session,
                        self.session_id,
                        file_name,
                        error_msg,
                        auto_commit=False
                    )

            await self.db_session.commit()
            await self.log_writer.write_info(f"✓ 数据库状态更新完成")

        await self.log_writer.write_info(
            f"✓ 并发下载完成: 成功 {len(saved_files)} 个, 失败 {len([u for u in status_updates if u[0] == 'error'])} 个"
        )

        return saved_files

    async def _processing_phase(self, checkpoint_manager, completed_indices):
        """处理阶段：数据抽取处理（复杂 + 简单并行双 Excel 输出）"""
        await self.log_writer.write_info("=" * 50)
        await self.log_writer.write_info("阶段 2: 数据抽取处理（复杂+简单并行）")
        await self.log_writer.write_info("=" * 50)

        # 复杂提取和简单提取并行执行
        results = await asyncio.gather(
            self._process_with_extractor_and_checkpoint(
                checkpoint_manager,
                completed_indices
            ),
            self._process_simple_extraction(),
            return_exceptions=True
        )

        # 处理结果，简单提取异常不影响复杂提取
        output_excel = results[0] if not isinstance(results[0], Exception) else None
        simple_output_excel = results[1] if not isinstance(results[1], Exception) else None

        # 复杂提取失败则抛出异常（关键任务）
        if isinstance(results[0], Exception):
            logger.error(f"复杂提取异常: {results[0]}")
            raise results[0]
        if isinstance(results[1], Exception):
            logger.error(f"简单提取异常: {results[1]}")
            await self.log_writer.write_error(f"简单提取异常: {str(results[1])}")

        return output_excel, simple_output_excel

    async def _process_with_extractor_and_checkpoint(
        self,
        checkpoint_manager,
        completed_indices: set
    ) -> str:
        """
        使用 JsonExtractor 处理文档（支持断点续传）

        Returns:
            输出 Excel 文件路径
        """
        # 准备输出文件路径
        output_excel_path = os.path.join(
            self.output_dir,
            f"extraction_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        # 读取配置文件
        with open(self.config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 获取 LLM 配置
        llm_configs = config.get('llm_configs', {})
        primary_llm = llm_configs.get('primary', {})

        # 导入需要的工具函数
        from tools.data_extraction_tool.src.core.data_processor import merge_results, post_process_data
        from tools.data_extraction_tool.src.utils.excel_writer import save_results_to_excel

        # 创建进度回调函数
        async def progress_callback(message: str):
            """进度回调函数，将进度信息写入日志"""
            try:
                await self.log_writer.write_info(f"[进度] {message}")
            except Exception as e:
                logger.warning(f"写入进度日志失败: {str(e)}")

        # 初始化 JsonExtractor
        extractor = JsonExtractor(
            user_id=self.user_id,
            llm_config=primary_llm,
            repair_llm_config=llm_configs.get('repair'),
            debug_folder=None,
            progress_callback=progress_callback,
            session_id=self.session_id
        )

        # 🔧 从数据库获取待处理的文件列表（直接获取 local_path）
        from module_common.service.data_extraction_file_status_service import DataExtractionFileStatusService

        # 获取所有未完成的文件（pending + processing + error，即非 completed）
        incomplete_files = await DataExtractionFileStatusService.get_incomplete_files(self.db_session, self.session_id)

        # 提取文件路径列表（过滤掉不存在的文件）
        file_paths = [f['local_path'] for f in incomplete_files if f.get('local_path') and os.path.exists(f['local_path'])]

        if not file_paths:
            await self.log_writer.write_info("✓ 所有文件已处理完成，无需继续处理")
            return None

        # 显示友好的处理信息
        completed_count = await DataExtractionFileStatusService.count_completed_files(self.db_session, self.session_id)

        if completed_count > 0:
            await self.log_writer.write_info(f"🔄 断点续传：已完成 {completed_count} 个文件，继续处理 {len(file_paths)} 个文件")
        else:
            await self.log_writer.write_info(f"📄 开始处理 {len(file_paths)} 个文件")

        # 聚合结果和处理计数
        aggregated_results = {}
        processed_count = 0
        processing_lock = asyncio.Lock()

        # 定义单个文件处理函数
        async def process_single_file_monitored(file_path: str):
            """处理单个文件并监控进度"""
            nonlocal processed_count, aggregated_results

            file_name = os.path.basename(file_path)
            start_time = datetime.now()

            try:
                # ⚡ 检查任务是否被停止
                if await self._check_if_stopped():
                    logger.info(f"⏸️ 检测到停止信号，跳过文件: {file_name}")
                    raise asyncio.CancelledError("用户停止任务")

                await self.log_writer.write_info(f"🚀 开始处理文件: {file_name} ({start_time.strftime('%H:%M:%S')})")

                # 处理单个文件
                result = await extractor.process_file(file_path)

                # 线程安全的结果聚合
                async with processing_lock:
                    if result:
                        aggregated_results = merge_results(aggregated_results, result)

                        # 保存断点
                        await checkpoint_manager.save_file_result(
                            db=self.db_session,
                            file_name=os.path.basename(file_path),
                            result_data=result
                        )

                    processed_count += 1

                    # 计算处理时间
                    elapsed_time = (datetime.now() - start_time).total_seconds()
                    await self.log_writer.write_info(f"进度: {processed_count}/{len(file_paths)}")

                await self.log_writer.write_success(f"✓ 完成: {file_name} (耗时 {elapsed_time:.1f}s)")
                return result

            except Exception as e:
                async with processing_lock:
                    processed_count += 1
                    await self.log_writer.write_info(f"进度: {processed_count}/{len(file_paths)}")

                await self.log_writer.write_error(f"处理失败 {os.path.basename(file_path)}: {str(e)}")
                logger.error(f"处理文件失败 [{file_path}]: {str(e)}")
                return None

        # 使用 semaphore 控制并发处理
        async def process_with_semaphore(file_path: str):
            async with self.resource_limiter.pdf_semaphore:
                return await process_single_file_monitored(file_path)

        # 启动定期停止检查的后台任务
        stop_check_task = None
        try:
            stop_check_task = asyncio.create_task(
                self._periodic_stop_check_task()
            )

            # 并行处理所有文件
            if file_paths:
                max_concurrent = self.resource_limiter.pdf_semaphore._value  # 获取信号量值
                await self.log_writer.write_info(
                    f"⚡ 开始并行处理 {len(file_paths)} 个文件 (最大并发数: {max_concurrent})"
                )
                tasks = [process_with_semaphore(file_path) for file_path in file_paths]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # 检查是否有 CancelledError（用户停止）
                for result in results:
                    if isinstance(result, asyncio.CancelledError):
                        logger.info("检测到用户停止任务")
                        raise result

            # 保存结果到 Excel
            if aggregated_results:
                # 后处理数据
                try:
                    processed_data = post_process_data(aggregated_results)
                except Exception as e:
                    logger.warning(f"Post-processing failed, using raw data: {str(e)}")
                    processed_data = aggregated_results

                # 保存到 Excel
                save_results_to_excel(processed_data, output_excel_path, create_process_files=False)
                await self.log_writer.write_success(f"✓ 结果已保存: {output_excel_path}")

            return output_excel_path

        except asyncio.CancelledError:
            # 用户停止任务
            logger.info("检测到任务停止")
            await self.log_writer.write_info(f"⏸️ 任务已停止，断点数据已自动保存到数据库")
            raise

        except Exception as e:
            # 错误场景
            logger.error(f"处理文档时出错: {str(e)}")
            raise

        finally:
            # 取消定期检查任务
            if stop_check_task:
                stop_check_task.cancel()
                try:
                    await stop_check_task
                except asyncio.CancelledError:
                    pass

    async def _process_simple_extraction(self) -> str:
        """
        简单提取阶段：使用数据库提示词模板分步提取，输出按 Section 分 Sheet 的 Excel
        """
        await self.log_writer.write_info("=" * 50)
        await self.log_writer.write_info("阶段 2.5: 简单数据提取")
        await self.log_writer.write_info("=" * 50)

        try:
            # 1. 从数据库加载启用的提示词模板
            from config.database import AsyncSessionLocal
            from module_common.dao.ai_prompt_template_dao import AiPromptTemplateDao
            from utils.common_util import CamelCaseUtil

            prompt_templates = []
            async with AsyncSessionLocal() as db:
                templates = await AiPromptTemplateDao.get_active_templates_by_module(db, 'data_extraction')
                for t in templates:
                    prompt_templates.append(CamelCaseUtil.transform_result(t))

            if not prompt_templates:
                await self.log_writer.write_warning("未找到启用的提示词模板，跳过简单提取")
                return None

            await self.log_writer.write_info(f"加载了 {len(prompt_templates)} 个提示词模板")

            # 2. 获取 LLM 配置
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            primary_llm = config.get('llm_configs', {}).get('primary', {})

            # 3. 创建简单提取器
            from tools.data_extraction_tool.src.extractors.simple_json_extractor import SimpleJsonExtractor
            from tools.data_extraction_tool.src.utils.simple_excel_writer import (
                save_simple_results_to_excel, merge_simple_results
            )

            async def simple_progress_callback(message: str):
                try:
                    await self.log_writer.write_info(f"[进度] {message}")
                except Exception:
                    pass

            extractor = SimpleJsonExtractor(
                user_id=self.user_id,
                llm_config=primary_llm,
                prompt_templates=prompt_templates,
                progress_callback=simple_progress_callback,
                session_id=self.session_id
            )

            # 4. 获取所有已下载的文件列表（复用已下载的文件，不依赖复杂提取完成状态）
            from module_common.service.data_extraction_file_status_service import DataExtractionFileStatusService
            all_files = await DataExtractionFileStatusService.get_all_files(self.db_session, self.session_id)

            file_paths = [f.local_path for f in all_files if f.local_path and os.path.exists(f.local_path)]

            if not file_paths:
                await self.log_writer.write_warning("没有已下载的文件可供简单提取")
                return None

            await self.log_writer.write_info(f"开始简单提取 {len(file_paths)} 个文件")

            # 5. 逐文件处理（简单提取不需要断点续传，因为复杂提取已完成）
            aggregated_simple = {}

            for i, file_path in enumerate(file_paths):
                file_name = os.path.basename(file_path)
                await self.log_writer.write_info(f"简单提取 ({i+1}/{len(file_paths)}): {file_name}")

                if await self._check_if_stopped():
                    await self.log_writer.write_warning("检测到停止信号，终止简单提取")
                    break

                try:
                    result = await extractor.process_file(file_path)
                    if result:
                        aggregated_simple = merge_simple_results(aggregated_simple, result)
                except ServiceException:
                    raise
                except Exception as e:
                    logger.error(f"简单提取文件失败 [{file_name}]: {e}")
                    await self.log_writer.write_error(f"简单提取失败: {file_name} - {str(e)}")

            # 6. 保存结果到 Excel
            if aggregated_simple:
                simple_excel_path = os.path.join(
                    self.output_dir,
                    f"simple_extraction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                )
                save_simple_results_to_excel(aggregated_simple, simple_excel_path)
                await self.log_writer.write_success(f"✓ 简单提取结果已保存: {simple_excel_path}")
                return simple_excel_path
            else:
                await self.log_writer.write_warning("简单提取无结果数据")
                return None

        except ServiceException:
            raise
        except Exception as e:
            logger.error(f"简单提取阶段失败: {e}")
            await self.log_writer.write_error(f"简单提取失败: {str(e)}")
            # 简单提取失败不影响整体任务
            return None

    async def _finalize_phase(self, output_excel, checkpoint_manager, simple_output_excel=None):
        """完成阶段：上传结果、更新状态、清理资源"""
        await self.log_writer.write_info("=" * 50)
        await self.log_writer.write_info("阶段 3: 完成任务")
        await self.log_writer.write_info("=" * 50)

        # 上传复杂提取结果到 COS
        result_url = None
        if output_excel and isinstance(output_excel, str) and os.path.exists(output_excel):
            await self.log_writer.write_info("上传结果到 COS...")
            result_url = await self._upload_result(output_excel)
        else:
            await self.log_writer.write_warning("无复杂提取结果可上传")

        # 上传简单提取结果到 COS（如果存在）
        simple_result_url = None
        if simple_output_excel and isinstance(simple_output_excel, str) and os.path.exists(simple_output_excel):
            await self.log_writer.write_info("上传简单提取结果到 COS...")
            simple_result_url = await self._upload_result(simple_output_excel)

        # 计算处理时长和总成本
        from module_common.service.token_usage_service import Token_usageService
        from module_common.service.data_extraction_history_service import DataExtractionHistoryService

        # 获取任务记录以计算处理时长
        task_record = await DataExtractionHistoryService.get_by_session(self.db_session, self.session_id)
        processing_duration = None
        if task_record and task_record.created_at:
            time_diff = datetime.now() - task_record.created_at
            processing_duration = int(time_diff.total_seconds())
            await self.log_writer.write_info(f"处理时长: {processing_duration} 秒")

        # 从 token_usage 表获取模型名称
        cost_data = await Token_usageService.get_total_cost_by_session(self.db_session, self.session_id)
        model_name = None

        if cost_data:
            model_name = cost_data.get('model_name')
            if model_name:
                await self.log_writer.write_info(f"使用模型: {model_name}")

        # 按成功处理的文件数计算实际费用
        # 复杂提取: 20 智币/篇 + 简单提取: 10 智币/篇 = 30 智币/篇
        from module_common.service.data_extraction_file_status_service import DataExtractionFileStatusService
        completed_files_count = await DataExtractionFileStatusService.count_completed_files(self.db_session, self.session_id)
        complex_cost = Decimal('20') * completed_files_count
        simple_cost = Decimal('10') * completed_files_count if simple_result_url else Decimal('0')
        total_cost_estimate = complex_cost + simple_cost
        self.total_actual_cost = total_cost_estimate
        await self.log_writer.write_info(
            f"总成本: {total_cost_estimate} 智币 ({completed_files_count} 篇 × "
            f"{'30' if simple_result_url else '20'} 智币)"
        )
        logger.info(f"实际消耗: {self.total_actual_cost:.4f} 智币")

        # 构建结果文件列表
        result_files = []

        if result_url and output_excel:
            result_files.append({
                'filename': os.path.basename(output_excel),
                'file_path': result_url,
                'file_size': os.path.getsize(output_excel) if os.path.exists(output_excel) else 0,
                'file_size_string': CosFileUtil.get_file_size_string(os.path.getsize(output_excel)) if os.path.exists(output_excel) else '0 B',
                'description': f"详细数据提取结果 - {os.path.basename(output_excel)}",
                'type': 'complex',
            })

        if simple_result_url and simple_output_excel:
            result_files.append({
                'filename': os.path.basename(simple_output_excel),
                'file_path': simple_result_url,
                'file_size': os.path.getsize(simple_output_excel) if os.path.exists(simple_output_excel) else 0,
                'file_size_string': CosFileUtil.get_file_size_string(os.path.getsize(simple_output_excel)) if os.path.exists(simple_output_excel) else '0 B',
                'description': f"简单数据提取结果 - {os.path.basename(simple_output_excel)}",
                'type': 'simple',
            })

        # 更新数据库
        update_kwargs = {
            'output_excel_path': result_url,
            'result_files': result_files,
            'processing_duration': processing_duration,
        }

        if total_cost_estimate is not None:
            update_kwargs['total_cost_estimate'] = total_cost_estimate

        if model_name:
            update_kwargs['model_name'] = model_name

        await self._update_main_task_status('completed', **update_kwargs)

        # 清理 JSON 断点数据
        checkpoint_manager.cleanup()

        # ========== 余额扣减和交易日志记录 ==========
        # 注意：余额扣减和交易日志记录现在统一由 _finalize_task_success() 中的
        # BalanceFreezeService.settle_and_unfreeze() 方法处理，避免重复扣费
        #
        # 旧的 Token_usageService.record_session_transaction_log() 方法已被移除，
        # 因为它会导致重复扣费（一次在这里，一次在 settle_and_unfreeze）
        #
        # 现在的流程：
        # 1. token_usage 表记录每次LLM调用的详细成本
        # 2. settle_and_unfreeze() 聚合 token_usage 的成本并一次性扣减余额
        # 3. coin_transaction_log 表只记录一条汇总的交易记录
        logger.info(f"Session {self.session_id} 任务完成，余额结算将由 settle_and_unfreeze() 统一处理")
        await self.log_writer.write_info("💰 余额结算将在任务结束时统一处理")

        await self.log_writer.write_success(f"✓ Session 完成: {self.session_id}")

        # 通知前端任务完成
        await self.log_writer.write_completed("任务已完成")

    async def _upload_result(self, local_file_path: str) -> str:
        """上传结果到 COS"""
        try:
            file_name = os.path.basename(local_file_path)
            cos_key = f"data_extraction/output/{file_name}"

            # 上传（同步调用，在线程池中执行）
            success, cos_url = await asyncio.to_thread(
                CosFileUtil.upload_local_file_to_cos,
                local_file_path=local_file_path,
                cos_key=cos_key,
                cleanup_local=False
            )

            if success and cos_url:
                await self.log_writer.write_success(f"结果已上传到 COS: {cos_url}")
                return cos_url
            else:
                raise Exception("上传到 COS 失败")

        except Exception as e:
            await self.log_writer.write_error(f"上传结果失败: {str(e)}")
            raise

    # ==================== 余额冻结结算管理 ====================

    async def _finalize_task_success(self):
        """任务成功完成后的余额结算和解冻"""
        if not self.freeze_id:
            logger.warning(f"未找到冻结记录ID,跳过解冻 - session_id: {self.session_id}")
            return

        logger.info(
            f"任务完成,开始结算 - session_id: {self.session_id}, "
            f"freeze_id: {self.freeze_id}, 实际消耗: {self.total_actual_cost:.4f} 元"
        )

        try:
            from config.database import AsyncSessionLocal
            from module_common.service.balance_freeze_service import BalanceFreezeService

            async with AsyncSessionLocal() as db:
                success = await BalanceFreezeService.settle_and_unfreeze(
                    db=db,
                    freeze_id=self.freeze_id,
                    actual_cost=self.total_actual_cost,
                    user_id=self.user_id
                )
                await db.commit()

                if success:
                    logger.info(
                        f"✓ 余额结算成功 - freeze_id: {self.freeze_id}, "
                        f"实际消耗: {self.total_actual_cost:.4f} 元"
                    )
                    if self.log_writer:
                        await self.log_writer.write_success(
                            f"💰 余额结算: 实际消耗 {self.total_actual_cost:.4f} 元"
                        )
                else:
                    logger.error(f"✗ 余额结算失败 - freeze_id: {self.freeze_id}")
                    if self.log_writer:
                        await self.log_writer.write_warning("⚠️ 余额结算失败")

        except Exception as e:
            logger.error(f"结算并解冻时发生错误: {e}", exc_info=True)
            if self.log_writer:
                await self.log_writer.write_error(f"结算余额时发生错误: {str(e)}")

    async def _finalize_task_failure(self):
        """任务失败/取消后的余额解冻(取消冻结,不扣费)"""
        if not self.freeze_id:
            logger.warning(f"未找到冻结记录ID,跳过解冻 - session_id: {self.session_id}")
            return

        logger.info(f"任务失败/取消,取消冻结 - freeze_id: {self.freeze_id}")

        try:
            from config.database import AsyncSessionLocal
            from module_common.service.balance_freeze_service import BalanceFreezeService

            async with AsyncSessionLocal() as db:
                success = await BalanceFreezeService.cancel_and_unfreeze(
                    db=db,
                    freeze_id=self.freeze_id,
                    user_id=self.user_id
                )
                await db.commit()

                if success:
                    logger.info(f"✓ 冻结已取消 - freeze_id: {self.freeze_id}")
                    if self.log_writer:
                        await self.log_writer.write_info("💰 已取消余额冻结,未扣费")
                else:
                    logger.error(f"✗ 取消冻结失败 - freeze_id: {self.freeze_id}")
                    if self.log_writer:
                        await self.log_writer.write_warning("⚠️ 取消冻结失败")

        except Exception as e:
            logger.error(f"取消冻结时发生错误: {e}", exc_info=True)
            if self.log_writer:
                await self.log_writer.write_error(f"取消冻结时发生错误: {str(e)}")

    # ==================== 资源清理管理 ====================

    async def _cleanup(self, cleanup_work_dir: bool = False):
        """
        清理会话资源（覆盖父类，添加智能清理逻辑）

        Args:
            cleanup_work_dir: 是否删除工作目录
                - True: 任务完成时删除工作目录
                - False: 任务失败/停止时保留工作目录以便断点续传
        """
        import shutil

        try:
            # 1. 清理工作目录（根据任务状态决定是否删除）
            if cleanup_work_dir and self.work_dir and os.path.exists(self.work_dir):
                try:
                    await asyncio.to_thread(shutil.rmtree, self.work_dir)
                    if self.log_writer:
                        await self.log_writer.write_info(f"✓ 已清理工作目录: {self.work_dir}")
                    logger.info(f"已清理工作目录: {self.work_dir}")
                except Exception as e:
                    logger.warning(f"清理工作目录失败: {str(e)}")
                    if self.log_writer:
                        await self.log_writer.write_warning(f"清理工作目录失败: {str(e)}")
            elif not cleanup_work_dir and self.work_dir:
                logger.info(f"保留工作目录以便断点续传: {self.work_dir}")
                if self.log_writer:
                    await self.log_writer.write_info(f"💾 保留工作目录以便断点续传: {self.work_dir}")

            # 2. 清理过期的会话目录（7天前）
            try:
                await self._cleanup_old_sessions()
            except Exception as e:
                logger.warning(f"清理过期会话目录失败: {str(e)}")

            # 3. 停止日志写入器
            if self.log_writer:
                await self.log_writer.stop()

            # 4. 清理过期日志（保留 5 天）
            try:
                from tools.common.log_cleaner import LogCleaner
                await asyncio.to_thread(
                    LogCleaner.cleanup_worker_logs,
                    self._get_worker_tool_name(),
                    retention_days=5
                )
            except Exception as e:
                logger.warning(f"清理过期日志失败: {str(e)}")

            # 5. 关闭数据库会话
            if self.db_session:
                await self.db_session.close()

            logger.info(f"Session 资源已清理: {self.session_id}")

        except Exception as e:
            logger.error(f"清理资源失败: {str(e)}")

    async def _cleanup_old_sessions(self, retention_days: int = 7):
        """
        清理旧的会话目录（超过指定天数的目录）

        Args:
            retention_days: 保留天数，默认 7 天
        """
        import time
        import shutil

        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            temp_dir = os.path.join(base_dir, 'temp')

            if not os.path.exists(temp_dir):
                return

            current_time = time.time()
            cutoff_time = current_time - (retention_days * 24 * 3600)

            # 遍历所有会话目录
            for session_folder in os.listdir(temp_dir):
                session_path = os.path.join(temp_dir, session_folder)

                # 跳过非目录
                if not os.path.isdir(session_path):
                    continue

                # 跳过当前会话
                if session_folder == self.session_id:
                    continue

                # 检查目录修改时间
                try:
                    dir_mtime = os.path.getmtime(session_path)

                    # 如果目录超过保留期限，删除
                    if dir_mtime < cutoff_time:
                        await asyncio.to_thread(shutil.rmtree, session_path)
                        logger.info(f"✓ 已清理过期会话目录: {session_folder} (创建于 {retention_days} 天前)")
                except Exception as e:
                    logger.warning(f"清理会话目录 {session_folder} 失败: {str(e)}")

        except Exception as e:
            logger.error(f"清理旧会话目录失败: {str(e)}")

    # ==================== 覆盖 run 方法以支持异常处理 ====================

    async def run(self):
        """
        运行 Session 任务（覆盖父类以支持用户停止任务和错误处理）

        清理策略：
        - 任务完成: cleanup_work_dir=True (删除工作目录)
        - 任务停止/失败: cleanup_work_dir=False (保留工作目录以便断点续传)
        """
        task_completed = False

        try:
            # 初始化
            await self._init_session()

            # 执行核心处理
            await self._process_phase()

            # 如果执行到这里，说明任务成功完成
            task_completed = True

            # NEW: 任务成功完成,结算并解冻余额
            await self._finalize_task_success()

        except asyncio.CancelledError:
            # 用户停止任务 - 保留工作目录以便断点续传
            logger.info(f"Session 被用户停止 [{self.session_id}]")

            # ========== 用户停止按实际消费扣费 ==========
            # 原因：
            # 1. LLM 已经实际调用，产生了真实成本
            # 2. 防止用户滥用停止功能来避免扣费
            # 3. 符合云服务行业惯例（按实际使用计费）

            # 按成功处理的文件数计算实际费用（固定 20 智币/篇）
            try:
                from module_common.service.data_extraction_file_status_service import DataExtractionFileStatusService
                completed_files = await DataExtractionFileStatusService.count_completed_files(self.db_session, self.session_id)
                self.total_actual_cost = Decimal('30') * completed_files
                logger.info(f"用户停止时实际消耗: {self.total_actual_cost:.4f} 智币 ({completed_files} 篇 × 30 智币/篇)")
            except Exception as e:
                logger.error(f"查询已完成文件数失败: {e}")

            # NOTE: 不在此处记录交易日志，统一由 _finalize_task_success() 内部的
            # BalanceFreezeService.settle_and_unfreeze() 方法记录，避免重复记录

            # NEW: 用户停止任务,结算并解冻(按实际消耗扣费)
            await self._finalize_task_success()

            if self.log_writer:
                await self.log_writer.write_completed("任务已停止")

        except Exception as e:
            # 任务失败 - 保留工作目录以便断点续传
            logger.error(f"Session 执行失败 [{self.session_id}]: {str(e)}")

            # ========== 系统错误不扣费策略 ==========
            # 原因：系统错误不是用户造成的，不应让用户承担成本
            # 虽然部分LLM已调用，但为了用户体验，系统承担这部分损失
            # NOTE: 不记录扣费交易日志，直接调用 _finalize_task_failure() 取消冻结并全额退还
            logger.info(f"任务失败，取消冻结，不扣费（系统承担已产生的LLM成本）")

            # NEW: 任务失败,取消冻结(不扣费)
            await self._finalize_task_failure()

            if self.log_writer:
                await self.log_writer.write_error(f"Session 失败: {str(e)}")
                await self._update_main_task_status('error', error_message=str(e))
                # 即使失败也要通知前端任务完成，关闭 SSE
                await self.log_writer.write_completed("任务已失败")

        finally:
            # 清理资源（根据任务完成状态决定是否删除工作目录）
            await self._cleanup(cleanup_work_dir=task_completed)
