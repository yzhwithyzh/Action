import asyncio
import contextlib
import json
import re
import shlex
import shutil
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from common.vo import CrudResponseModel, PageModel
from config.env import SiteBuildConfig, UploadConfig
from exceptions.exception import ServiceException
from module_action.dao.action_dao import (
    CollabRequestDao,
    GuidelineCategoryDao,
    GuidelineDao,
    GuidelineItemDao,
    ImplementationDao,
    NewsDao,
    ReportDraftDao,
    ReportReviewDao,
    ReportTrailDao,
    ResourceLinkDao,
    SiteTextDao,
    SrdDao,
    StudyTypeDao,
    TeamMemberDao,
)
from module_action.entity.do.action_do import (
    ActionReportReview,
    ActionReportTrail,
    ActionSrdAssessment,
    ActionStudyType,
)
from module_action.entity.vo.action_vo import (
    MAX_ASSIST_INPUT_CHARS,
    MAX_TRAIL_ROWS,
    MIN_MANUSCRIPT_CHARS,
    AssistApplyModel,
    AssistRequestModel,
    AssistResultModel,
    CfirConstructModel,
    CfirDomainModel,
    CfirStrategyModel,
    ChecklistReviewStateModel,
    ChecklistReviewSubmitModel,
    ChecklistReviewSubmitResultModel,
    CollabRequestPageQueryModel,
    CollabRequestSubmitModel,
    DraftImportResultModel,
    EricCategoryModel,
    EricStrategyModel,
    GuidelineCategoryModel,
    GuidelineCategoryPageQueryModel,
    GuidelineItemModel,
    GuidelineItemPageQueryModel,
    GuidelineModel,
    GuidelinePageQueryModel,
    NewsModel,
    NewsPageQueryModel,
    ReaimDimensionModel,
    ReportDraftComposeModel,
    ReportDraftCreateModel,
    ReportDraftItemModel,
    ReportDraftModel,
    ReportDraftSaveModel,
    ReportReviewHistoryModel,
    ReportReviewModel,
    ResourceLinkModel,
    ResourceLinkPageQueryModel,
    ReviewPurpose,
    ReviewVerdictModel,
    SiteRebuildStateModel,
    SiteTextGroupModel,
    SiteTextModel,
    SiteTextOverridesModel,
    SiteTextPageQueryModel,
    SrdAssessmentModel,
    SrdDomainModel,
    SrdGroupModel,
    SrdHistoryModel,
    SrdItemModel,
    SrdRunStateModel,
    StudyTypeModel,
    StudyTypeSaveModel,
    StudyTypeStatModel,
    TeamMemberModel,
    TeamMemberPageQueryModel,
    TrailAddModel,
    TrailModel,
)
from module_action.service.ai_assist_service import AiAssistService
from module_action.service.report_assist_prompt import AssistContext, needs_current_text
from module_action.service.report_compose_service import ComposeItem, compose_draft_text
from module_action.service.report_export_service import BUILDERS, ExportDraft, ExportItem
from module_action.service.srd_export_service import build_assessment_xlsx
from utils.common_util import CamelCaseUtil
from utils.log_util import logger


class NewsService:
    """
    官网新闻动态服务层
    """

    @classmethod
    async def get_news_list_services(
        cls, query_db: AsyncSession, query_object: NewsPageQueryModel, is_page: bool = False,
        only_published: bool = False,
    ) -> PageModel | list[dict[str, Any]]:
        """
        获取新闻列表

        :param query_db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :param only_published: 是否只取已发布（官网公开接口传 True）
        :return: 新闻列表
        """
        return await NewsDao.get_news_list(query_db, query_object, is_page, only_published)

    @classmethod
    async def news_detail_services(cls, query_db: AsyncSession, news_id: int) -> NewsModel:
        """
        获取新闻详情

        :param query_db: orm对象
        :param news_id: 新闻id
        :return: 新闻详情
        """
        news = await NewsDao.get_news_detail_by_id(query_db, news_id)
        if not news:
            raise ServiceException(message='新闻不存在')

        return NewsModel(**CamelCaseUtil.transform_result(news))

    @classmethod
    async def add_news_services(cls, query_db: AsyncSession, page_object: NewsModel) -> CrudResponseModel:
        """
        新增新闻

        :param query_db: orm对象
        :param page_object: 新闻对象
        :return: 新增结果
        """
        try:
            await NewsDao.add_news_dao(query_db, page_object)
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='新增成功')
        except Exception as e:
            await query_db.rollback()
            raise e

    @classmethod
    async def edit_news_services(cls, query_db: AsyncSession, page_object: NewsModel) -> CrudResponseModel:
        """
        编辑新闻

        :param query_db: orm对象
        :param page_object: 新闻对象
        :return: 编辑结果
        """
        edit_news = page_object.model_dump(exclude_unset=True)
        news_info = await NewsDao.get_news_detail_by_id(query_db, page_object.news_id)
        if not news_info:
            raise ServiceException(message='新闻不存在')
        try:
            await NewsDao.edit_news_dao(query_db, edit_news)
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='更新成功')
        except Exception as e:
            await query_db.rollback()
            raise e

    @classmethod
    async def delete_news_services(cls, query_db: AsyncSession, news_ids: str) -> CrudResponseModel:
        """
        删除新闻

        :param query_db: orm对象
        :param news_ids: 新闻id字符串，多个以逗号分隔
        :return: 删除结果
        """
        id_list = [int(i) for i in news_ids.split(',') if i.strip()]
        if not id_list:
            raise ServiceException(message='传入新闻id为空')
        try:
            await NewsDao.delete_news_dao(query_db, id_list)
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='删除成功')
        except Exception as e:
            await query_db.rollback()
            raise e


class TeamMemberService:
    """
    官网团队成员服务层
    """

    @classmethod
    async def get_member_list_services(
        cls,
        query_db: AsyncSession,
        query_object: TeamMemberPageQueryModel,
        is_page: bool = False,
        only_published: bool = False,
    ) -> PageModel | list[dict[str, Any]]:
        """
        获取团队成员列表

        :param query_db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :param only_published: 是否只取启用中的（官网公开接口传 True）
        :return: 成员列表
        """
        return await TeamMemberDao.get_member_list(query_db, query_object, is_page, only_published)

    @classmethod
    async def member_detail_services(cls, query_db: AsyncSession, member_id: int) -> TeamMemberModel:
        """
        获取团队成员详情

        :param query_db: orm对象
        :param member_id: 成员id
        :return: 成员详情
        """
        member = await TeamMemberDao.get_member_detail_by_id(query_db, member_id)
        if not member:
            raise ServiceException(message='团队成员不存在')

        return TeamMemberModel(**CamelCaseUtil.transform_result(member))

    @classmethod
    async def add_member_services(cls, query_db: AsyncSession, page_object: TeamMemberModel) -> CrudResponseModel:
        """
        新增团队成员

        :param query_db: orm对象
        :param page_object: 成员对象
        :return: 新增结果
        """
        # 未指定顺序时排到本组末尾，避免新成员挤到委员会名单最前
        if page_object.sort_num is None:
            page_object.sort_num = await TeamMemberDao.get_max_sort_num(query_db, page_object.group_key or 'board') + 1
        try:
            await TeamMemberDao.add_member_dao(query_db, page_object)
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='新增成功')
        except Exception as e:
            await query_db.rollback()
            raise e

    @classmethod
    async def edit_member_services(cls, query_db: AsyncSession, page_object: TeamMemberModel) -> CrudResponseModel:
        """
        编辑团队成员

        :param query_db: orm对象
        :param page_object: 成员对象
        :return: 编辑结果
        """
        if not await TeamMemberDao.get_member_detail_by_id(query_db, page_object.member_id):
            raise ServiceException(message='团队成员不存在')
        try:
            await TeamMemberDao.edit_member_dao(
                query_db, page_object.model_dump(exclude_unset=True, exclude={'keyword'})
            )
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='更新成功')
        except Exception as e:
            await query_db.rollback()
            raise e

    @classmethod
    async def delete_member_services(cls, query_db: AsyncSession, member_ids: str) -> CrudResponseModel:
        """
        删除团队成员

        :param query_db: orm对象
        :param member_ids: 成员id字符串，多个以逗号分隔
        :return: 删除结果
        """
        id_list = [int(i) for i in member_ids.split(',') if i.strip()]
        if not id_list:
            raise ServiceException(message='传入成员id为空')
        try:
            await TeamMemberDao.delete_member_dao(query_db, id_list)
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='删除成功')
        except Exception as e:
            await query_db.rollback()
            raise e


class ResourceLinkService:
    """
    官网资源中心链接服务层

    首页「国际报告规范组织与循证枢纽」一段的外链卡片，纯陈列数据，
    没有别的表引用它，因此增删改都不带占用校验。
    """

    @classmethod
    async def get_link_list_services(
        cls,
        query_db: AsyncSession,
        query_object: ResourceLinkPageQueryModel,
        is_page: bool = False,
        only_published: bool = False,
    ) -> PageModel | list[dict[str, Any]]:
        """
        获取资源中心链接列表

        :param query_db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :param only_published: 是否只取启用中的（官网公开接口传 True）
        :return: 资源列表
        """
        return await ResourceLinkDao.get_link_list(query_db, query_object, is_page, only_published)

    @classmethod
    async def link_detail_services(cls, query_db: AsyncSession, link_id: int) -> ResourceLinkModel:
        """
        获取资源中心链接详情

        :param query_db: orm对象
        :param link_id: 资源id
        :return: 资源详情
        """
        link = await ResourceLinkDao.get_link_detail_by_id(query_db, link_id)
        if not link:
            raise ServiceException(message='资源中心链接不存在')

        return ResourceLinkModel(**CamelCaseUtil.transform_result(link))

    @classmethod
    async def add_link_services(cls, query_db: AsyncSession, page_object: ResourceLinkModel) -> CrudResponseModel:
        """
        新增资源中心链接

        :param query_db: orm对象
        :param page_object: 资源对象
        :return: 新增结果
        """
        # 未指定顺序时排到末尾，避免新资源挤到 EQUATOR 前面
        if page_object.sort_num is None:
            page_object.sort_num = await ResourceLinkDao.get_max_sort_num(query_db) + 1
        try:
            await ResourceLinkDao.add_link_dao(query_db, page_object)
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='新增成功')
        except Exception as e:
            await query_db.rollback()
            raise e

    @classmethod
    async def edit_link_services(cls, query_db: AsyncSession, page_object: ResourceLinkModel) -> CrudResponseModel:
        """
        编辑资源中心链接

        :param query_db: orm对象
        :param page_object: 资源对象
        :return: 编辑结果
        """
        link_info = await ResourceLinkDao.get_link_detail_by_id(query_db, page_object.link_id)
        if not link_info:
            raise ServiceException(message='资源中心链接不存在')
        try:
            await ResourceLinkDao.edit_link_dao(
                query_db, page_object.model_dump(exclude_unset=True, exclude={'keyword'})
            )
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='更新成功')
        except Exception as e:
            await query_db.rollback()
            raise e

    @classmethod
    async def delete_link_services(cls, query_db: AsyncSession, link_ids: str) -> CrudResponseModel:
        """
        删除资源中心链接

        :param query_db: orm对象
        :param link_ids: 资源id字符串，多个以逗号分隔
        :return: 删除结果
        """
        id_list = [int(i) for i in link_ids.split(',') if i.strip()]
        if not id_list:
            raise ServiceException(message='传入资源id为空')
        try:
            await ResourceLinkDao.delete_link_dao(query_db, id_list)
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='删除成功')
        except Exception as e:
            await query_db.rollback()
            raise e


class SiteTextService:
    """
    官网站点文案服务层

    只提供「查 / 改 / 还原默认」。词条的增删由 `python -m tools.extract_site_texts`
    从前端 i18n JSON 同步 —— 键是模板里 `$t()` 的参数，后台建键只会建出没人读的孤儿行，
    后台删键则会让官网上一段文字凭空消失且无从查起。
    """

    #: 编辑接口只认这几列。`text_key` / `default_*` / `sort_num` 由代码与同步脚本决定，
    #: 前端把整个 form 原样 PUT 回来时，多余字段在这里被丢掉而不是写进库。
    EDITABLE_FIELDS: ClassVar[set[str]] = {'text_zh', 'text_en', 'remark', 'update_by', 'update_time'}

    @classmethod
    async def get_text_list_services(
        cls, query_db: AsyncSession, query_object: SiteTextPageQueryModel, is_page: bool = False
    ) -> PageModel | list[dict[str, Any]]:
        """
        获取站点文案列表

        :param query_db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 文案列表
        """
        return await SiteTextDao.get_text_list(query_db, query_object, is_page)

    @classmethod
    async def text_detail_services(cls, query_db: AsyncSession, text_id: int) -> SiteTextModel:
        """
        获取站点文案详情

        :param query_db: orm对象
        :param text_id: 文案id
        :return: 文案详情
        """
        site_text = await SiteTextDao.get_text_detail_by_id(query_db, text_id)
        if not site_text:
            raise ServiceException(message='站点文案不存在')

        return SiteTextModel(**CamelCaseUtil.transform_result(site_text))

    @classmethod
    async def get_page_groups_services(cls, query_db: AsyncSession) -> list[SiteTextGroupModel]:
        """
        获取分组词表（含每组词条数与已改动数），供后台筛选下拉

        :param query_db: orm对象
        :return: 分组列表
        """
        return [SiteTextGroupModel(**row) for row in await SiteTextDao.get_page_groups(query_db)]

    @classmethod
    async def edit_text_services(cls, query_db: AsyncSession, page_object: SiteTextModel) -> CrudResponseModel:
        """
        编辑站点文案

        :param query_db: orm对象
        :param page_object: 文案对象
        :return: 编辑结果
        """
        text_info = await SiteTextDao.get_text_detail_by_id(query_db, page_object.text_id)
        if not text_info:
            raise ServiceException(message='站点文案不存在')
        payload = {
            key: value
            for key, value in page_object.model_dump(exclude_unset=True).items()
            if key in cls.EDITABLE_FIELDS
        }
        if not payload:
            raise ServiceException(message='没有可修改的内容')
        payload['text_id'] = page_object.text_id
        try:
            await SiteTextDao.edit_text_dao(query_db, payload)
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='更新成功')
        except Exception as e:
            await query_db.rollback()
            raise e

    @classmethod
    async def restore_text_services(cls, query_db: AsyncSession, text_ids: str, operator: str) -> CrudResponseModel:
        """
        把指定文案还原成代码里的默认值

        :param query_db: orm对象
        :param text_ids: 文案id字符串，多个以逗号分隔；传 `all` 表示全部还原
        :param operator: 操作人
        :return: 还原结果
        """
        if text_ids.strip() == 'all':
            id_list: list[int] = []
        else:
            id_list = [int(i) for i in text_ids.split(',') if i.strip()]
            if not id_list:
                raise ServiceException(message='传入文案id为空')
        try:
            await SiteTextDao.restore_text_dao(query_db, id_list, operator)
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='已还原为默认文案')
        except Exception as e:
            await query_db.rollback()
            raise e

    @classmethod
    async def get_overrides_services(cls, query_db: AsyncSession) -> SiteTextOverridesModel:
        """
        取官网文案覆盖包（只含与默认值不同的词条）

        中英分别只放**这一语言**被改过的键：中文改了英文没改时，只下发中文那一条，
        英文界面继续用打进包里的 i18n 默认值，不多传一份一模一样的字符串。

        :param query_db: orm对象
        :return: 覆盖包
        """
        rows = await SiteTextDao.get_changed_texts(query_db)
        zh = {row.text_key: row.text_zh or '' for row in rows if row.text_zh != row.default_zh}
        en = {row.text_key: row.text_en or '' for row in rows if row.text_en != row.default_en}

        return SiteTextOverridesModel(zh=zh, en=en)


class SiteRebuildService:
    """
    官网静态站重新生成服务层

    官网是预渲染站，后台改完文案，**访客的浏览器**会通过 `/action/site/texts` 立刻拿到新文案，
    但**搜索引擎与分享卡片**只看首屏 HTML，那还是上一次构建的产物。这个服务负责按运维在
    .env 里配好的命令跑一次构建，把改动烤进静态产物。

    命令来自配置、不接受任何请求参数，且不经 shell（见 `SiteBuildSettings` 的说明）。
    状态放 Redis 而不是内存：后端可能多副本，构建是全局互斥的一件事。
    """

    #: 状态存放的 Redis 键。构建可能跑几分钟，给一天的过期时间，够后台回看上一次结果。
    STATE_KEY: ClassVar[str] = 'action:site:rebuild:state'
    STATE_TTL_SECONDS: ClassVar[int] = 86400
    #: 互斥锁键。TTL 取构建超时 + 一点余量，进程被 kill 时锁也能自己过期。
    LOCK_KEY: ClassVar[str] = 'action:site:rebuild:lock'

    @classmethod
    async def get_state_services(cls, redis: Any) -> SiteRebuildStateModel:
        """
        取当前构建状态

        :param redis: redis客户端
        :return: 构建状态
        """
        if not SiteBuildConfig.site_rebuild_enabled:
            return SiteRebuildStateModel(
                status='disabled',
                message='未启用「重新生成官网」。需在后端 .env 配置 SITE_REBUILD_ENABLED / '
                'SITE_REBUILD_COMMAND / SITE_REBUILD_CWD 后重启后端。',
            )
        raw = await redis.get(cls.STATE_KEY)
        if not raw:
            return SiteRebuildStateModel(status='idle', message='尚未执行过')

        return SiteRebuildStateModel(**json.loads(raw))

    @classmethod
    async def _write_state(cls, redis: Any, state: SiteRebuildStateModel) -> None:
        """
        写入构建状态

        :param redis: redis客户端
        :param state: 构建状态
        :return: None
        """
        await redis.set(cls.STATE_KEY, state.model_dump_json(), ex=cls.STATE_TTL_SECONDS)

    @classmethod
    async def trigger_services(cls, redis: Any, operator: str) -> CrudResponseModel:
        """
        触发一次官网重新生成

        立刻返回，构建在后台任务里跑；进度与结果走 `get_state_services`。

        :param redis: redis客户端
        :param operator: 触发人
        :return: 触发结果
        """
        if not SiteBuildConfig.site_rebuild_enabled:
            raise ServiceException(
                message='未启用「重新生成官网」。需在后端 .env 配置 SITE_REBUILD_ENABLED / '
                'SITE_REBUILD_COMMAND / SITE_REBUILD_CWD 后重启后端。'
            )
        if not SiteBuildConfig.site_rebuild_command.strip():
            raise ServiceException(message='SITE_REBUILD_COMMAND 未配置')
        cwd = Path(SiteBuildConfig.site_rebuild_cwd)
        # to_thread 只是为了不在事件循环里做磁盘 stat；这是个配置自检，命中的是「运维填错路径」
        if not SiteBuildConfig.site_rebuild_cwd or not await asyncio.to_thread(cwd.is_dir):
            raise ServiceException(message=f'SITE_REBUILD_CWD 不是一个存在的目录：{SiteBuildConfig.site_rebuild_cwd}')

        # setnx 拿锁：同一时刻只允许一次构建。两个构建同时往 .output 里写等于产物损坏。
        acquired = await redis.set(
            cls.LOCK_KEY, operator, ex=SiteBuildConfig.site_rebuild_timeout_seconds + 60, nx=True
        )
        if not acquired:
            raise ServiceException(message='官网正在重新生成中，请等这一次跑完')

        state = SiteRebuildStateModel(
            status='running',
            message='正在重新生成官网……',
            started_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            started_by=operator,
        )
        await cls._write_state(redis, state)
        # 不 await：接口要立刻返回。任务对象存一份引用，否则可能被 GC 提前回收。
        task = asyncio.create_task(cls._run(redis, state))
        cls._running_tasks.add(task)
        task.add_done_callback(cls._running_tasks.discard)

        return CrudResponseModel(is_success=True, message='已开始重新生成官网，预计需要几分钟')

    #: 后台构建任务的强引用集合（asyncio 只持弱引用，不存就可能被中途回收）
    _running_tasks: ClassVar[set[asyncio.Task]] = set()

    @classmethod
    async def _run(cls, redis: Any, state: SiteRebuildStateModel) -> None:
        """
        实际执行构建命令

        :param redis: redis客户端
        :param state: 触发时写入的状态，用于保留 startedAt / startedBy
        :return: None
        """
        argv = shlex.split(SiteBuildConfig.site_rebuild_command)
        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                cwd=SiteBuildConfig.site_rebuild_cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            try:
                stdout, _ = await asyncio.wait_for(
                    process.communicate(), timeout=SiteBuildConfig.site_rebuild_timeout_seconds
                )
            except TimeoutError:
                process.kill()
                await process.wait()
                raise ServiceException(
                    message=f'构建超时（{SiteBuildConfig.site_rebuild_timeout_seconds}s），已终止'
                ) from None

            output = (stdout or b'').decode('utf-8', errors='replace')
            if process.returncode == 0:
                # 只回显末尾若干行：构建日志动辄几千行，整包塞进 Redis 状态没有意义
                result = SiteRebuildStateModel(
                    status='success',
                    message='官网已重新生成。' + cls._tail(output),
                    started_at=state.started_at,
                    started_by=state.started_by,
                    finished_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                )
                logger.info('官网重新生成成功')
            else:
                result = SiteRebuildStateModel(
                    status='failed',
                    message=f'构建失败（退出码 {process.returncode}）。' + cls._tail(output),
                    started_at=state.started_at,
                    started_by=state.started_by,
                    finished_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                )
                logger.error(f'官网重新生成失败，退出码 {process.returncode}')
            await cls._write_state(redis, result)
        except Exception as e:
            logger.error(f'官网重新生成异常：{e}')
            await cls._write_state(
                redis,
                SiteRebuildStateModel(
                    status='failed',
                    message=f'构建异常：{e}',
                    started_at=state.started_at,
                    started_by=state.started_by,
                    finished_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                ),
            )
        finally:
            # 无论成败都要放锁，否则下一次触发要等到 TTL 过期
            await redis.delete(cls.LOCK_KEY)

    @staticmethod
    def _tail(output: str, lines: int = 12) -> str:
        """
        取构建输出的末尾若干行

        :param output: 完整输出
        :param lines: 保留行数
        :return: 末尾片段
        """
        kept = [line for line in output.strip().splitlines() if line.strip()][-lines:]

        return '\n'.join(kept)


class GuidelineService:
    """
    官网报告规范目录服务层
    """

    @classmethod
    async def get_guideline_list_services(
        cls, query_db: AsyncSession, query_object: GuidelinePageQueryModel, is_page: bool = False,
        only_published: bool = False,
    ) -> PageModel | list[dict[str, Any]]:
        """
        获取报告规范列表

        :param query_db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :param only_published: 是否只取启用中的
        :return: 规范列表
        """
        return await GuidelineDao.get_guideline_list(query_db, query_object, is_page, only_published)

    @classmethod
    async def guideline_detail_services(cls, query_db: AsyncSession, guideline_id: int) -> GuidelineModel:
        """
        获取报告规范详情

        :param query_db: orm对象
        :param guideline_id: 规范id
        :return: 规范详情
        """
        guideline = await GuidelineDao.get_guideline_detail_by_id(query_db, guideline_id)
        if not guideline:
            raise ServiceException(message='报告规范不存在')

        return GuidelineModel(**CamelCaseUtil.transform_result(guideline))

    @classmethod
    async def _assert_study_type_exists(cls, query_db: AsyncSession, study_type: str | None) -> None:
        """
        校验分类标识确实在 action_guideline_category 里

        规范页的筛选条与卡片上的「研究设计」标签都靠 study_type 去分类表取值。写进一个表外的值，
        这份规范在前台就会「哪个筛选按钮都点不出来、标签还是空白」—— 这正是分类入库前的老毛病，
        所以在写入口就拦住，而不是等前台去兜底。

        :param query_db: orm对象
        :param study_type: 分类标识，留空表示不归类（允许）
        :return: None
        """
        if not study_type:
            return
        if not await GuidelineCategoryDao.get_category_by_key(query_db, study_type):
            raise ServiceException(message=f'研究设计分类 {study_type} 不存在，请先在「规范分类管理」中添加')

    @classmethod
    async def add_guideline_services(cls, query_db: AsyncSession, page_object: GuidelineModel) -> CrudResponseModel:
        """
        新增报告规范

        :param query_db: orm对象
        :param page_object: 规范对象
        :return: 新增结果
        """
        if await GuidelineDao.get_guideline_by_code(query_db, page_object.code):
            raise ServiceException(message=f'新增失败，规范代号 {page_object.code} 已存在')
        await cls._assert_study_type_exists(query_db, page_object.study_type)
        # 未指定顺序时排到目录末尾，避免新规范挤到 STRICTA 前面
        if page_object.sort_num is None:
            page_object.sort_num = await GuidelineDao.get_max_sort_num(query_db) + 1
        try:
            await GuidelineDao.add_guideline_dao(query_db, page_object)
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='新增成功')
        except Exception as e:
            await query_db.rollback()
            raise e

    @classmethod
    async def edit_guideline_services(cls, query_db: AsyncSession, page_object: GuidelineModel) -> CrudResponseModel:
        """
        编辑报告规范

        :param query_db: orm对象
        :param page_object: 规范对象
        :return: 编辑结果
        """
        guideline_info = await GuidelineDao.get_guideline_detail_by_id(query_db, page_object.guideline_id)
        if not guideline_info:
            raise ServiceException(message='报告规范不存在')
        if page_object.code:
            exist = await GuidelineDao.get_guideline_by_code(query_db, page_object.code)
            if exist and exist.guideline_id != page_object.guideline_id:
                raise ServiceException(message=f'修改失败，规范代号 {page_object.code} 已存在')
        await cls._assert_study_type_exists(query_db, page_object.study_type)
        try:
            await GuidelineDao.edit_guideline_dao(
                query_db, page_object.model_dump(exclude_unset=True, exclude={'keyword'})
            )
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='更新成功')
        except Exception as e:
            await query_db.rollback()
            raise e

    @classmethod
    async def delete_guideline_services(cls, query_db: AsyncSession, guideline_ids: str) -> CrudResponseModel:
        """
        删除报告规范

        :param query_db: orm对象
        :param guideline_ids: 规范id字符串，多个以逗号分隔
        :return: 删除结果
        """
        id_list = [int(i) for i in guideline_ids.split(',') if i.strip()]
        if not id_list:
            raise ServiceException(message='传入规范id为空')
        try:
            await GuidelineDao.delete_guideline_dao(query_db, id_list)
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='删除成功')
        except Exception as e:
            await query_db.rollback()
            raise e


class GuidelineCategoryService:
    """
    官网报告规范分类服务层

    规范页第①段筛选条的词表。分类标识（cat_key）就是 action_guideline.study_type 的取值域，
    改键、停用、删除都会立刻反映到前台，因此这几件事都带占用校验。
    """

    @classmethod
    async def get_category_list_services(
        cls,
        query_db: AsyncSession,
        query_object: GuidelineCategoryPageQueryModel,
        is_page: bool = False,
        only_published: bool = False,
    ) -> PageModel | list[dict[str, Any]]:
        """
        获取报告规范分类列表

        :param query_db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :param only_published: 是否只取启用中的（官网公开接口传 True）
        :return: 分类列表
        """
        return await GuidelineCategoryDao.get_category_list(query_db, query_object, is_page, only_published)

    @classmethod
    async def category_detail_services(cls, query_db: AsyncSession, cat_id: int) -> GuidelineCategoryModel:
        """
        获取报告规范分类详情

        :param query_db: orm对象
        :param cat_id: 分类id
        :return: 分类详情
        """
        category = await GuidelineCategoryDao.get_category_detail_by_id(query_db, cat_id)
        if not category:
            raise ServiceException(message='报告规范分类不存在')

        return GuidelineCategoryModel(**CamelCaseUtil.transform_result(category))

    @classmethod
    async def add_category_services(
        cls, query_db: AsyncSession, page_object: GuidelineCategoryModel
    ) -> CrudResponseModel:
        """
        新增报告规范分类

        :param query_db: orm对象
        :param page_object: 分类对象
        :return: 新增结果
        """
        if await GuidelineCategoryDao.get_category_by_key(query_db, page_object.cat_key):
            raise ServiceException(message=f'新增失败，分类标识 {page_object.cat_key} 已存在')
        # 未指定顺序时排到筛选条末尾，避免新分类挤到「随机对照试验」前面
        if page_object.sort_num is None:
            page_object.sort_num = await GuidelineCategoryDao.get_max_sort_num(query_db) + 1
        try:
            await GuidelineCategoryDao.add_category_dao(query_db, page_object)
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='新增成功')
        except Exception as e:
            await query_db.rollback()
            raise e

    @classmethod
    async def edit_category_services(
        cls, query_db: AsyncSession, page_object: GuidelineCategoryModel
    ) -> CrudResponseModel:
        """
        编辑报告规范分类

        :param query_db: orm对象
        :param page_object: 分类对象
        :return: 编辑结果
        """
        category_info = await GuidelineCategoryDao.get_category_detail_by_id(query_db, page_object.cat_id)
        if not category_info:
            raise ServiceException(message='报告规范分类不存在')
        if page_object.cat_key:
            exist = await GuidelineCategoryDao.get_category_by_key(query_db, page_object.cat_key)
            if exist and exist.cat_id != page_object.cat_id:
                raise ServiceException(message=f'修改失败，分类标识 {page_object.cat_key} 已存在')
            # 改键等于把这批规范的 study_type 指向一个不存在的分类，它们会立刻从前台筛选条上消失。
            # 名称随便改（前台跟着变），键不许在有占用时改。
            if page_object.cat_key != category_info.cat_key:
                used = await GuidelineDao.count_by_study_type(query_db, category_info.cat_key)
                if used:
                    raise ServiceException(
                        message=f'修改失败，已有 {used} 份规范挂在分类标识 {category_info.cat_key} 下；'
                        f'请先在「规范目录管理」中改掉这些规范的研究设计，或只改名称不改标识'
                    )
        try:
            await GuidelineCategoryDao.edit_category_dao(
                query_db, page_object.model_dump(exclude_unset=True, exclude={'keyword'})
            )
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='更新成功')
        except Exception as e:
            await query_db.rollback()
            raise e

    @classmethod
    async def delete_category_services(cls, query_db: AsyncSession, cat_ids: str) -> CrudResponseModel:
        """
        删除报告规范分类

        :param query_db: orm对象
        :param cat_ids: 分类id字符串，多个以逗号分隔
        :return: 删除结果
        """
        id_list = [int(i) for i in cat_ids.split(',') if i.strip()]
        if not id_list:
            raise ServiceException(message='传入分类id为空')
        # 删掉还有规范在用的分类，那些规范在前台会变成「筛不出来 + 标签空白」，正是分类入库要消灭的状态
        for cat_id in id_list:
            category = await GuidelineCategoryDao.get_category_detail_by_id(query_db, cat_id)
            if not category:
                continue
            used = await GuidelineDao.count_by_study_type(query_db, category.cat_key)
            if used:
                raise ServiceException(
                    message=f'删除失败，分类「{category.name_zh}」下还有 {used} 份规范；'
                    f'请先在「规范目录管理」中改掉这些规范的研究设计'
                )
        try:
            await GuidelineCategoryDao.delete_category_dao(query_db, id_list)
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='删除成功')
        except Exception as e:
            await query_db.rollback()
            raise e


class GuidelineItemService:
    """
    报告规范 checklist 条目服务层

    条目是报告助手第二步（结构化模板）与第三步（逐条校验）共用的数据源，
    也是投稿时随稿提交的那份清单，改动会直接影响前台，写操作只走后台鉴权接口。
    """

    @classmethod
    async def get_item_list_services(
        cls,
        query_db: AsyncSession,
        query_object: GuidelineItemPageQueryModel,
        is_page: bool = False,
        only_published: bool = False,
    ) -> PageModel | list[dict[str, Any]]:
        """
        获取规范条目列表

        :param query_db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :param only_published: 是否只取启用中的
        :return: 条目列表
        """
        return await GuidelineItemDao.get_item_list(query_db, query_object, is_page, only_published)

    @classmethod
    async def item_detail_services(cls, query_db: AsyncSession, item_id: int) -> GuidelineItemModel:
        """
        获取规范条目详情

        :param query_db: orm对象
        :param item_id: 条目id
        :return: 条目详情
        """
        item = await GuidelineItemDao.get_item_detail_by_id(query_db, item_id)
        if not item:
            raise ServiceException(message='规范条目不存在')

        return GuidelineItemModel(**CamelCaseUtil.transform_result(item))

    @classmethod
    async def add_item_services(cls, query_db: AsyncSession, page_object: GuidelineItemModel) -> CrudResponseModel:
        """
        新增规范条目

        :param query_db: orm对象
        :param page_object: 条目对象
        :return: 新增结果
        """
        if not page_object.guideline_id:
            raise ServiceException(message='新增失败，未指定所属规范')
        if not await GuidelineDao.get_guideline_detail_by_id(query_db, page_object.guideline_id):
            raise ServiceException(message='新增失败，所属规范不存在')
        # 未指定顺序时排到该规范末尾，避免新条目挤在 0 位打乱既有清单
        if page_object.sort_num is None:
            page_object.sort_num = await GuidelineItemDao.get_max_sort_num(query_db, page_object.guideline_id) + 1
        try:
            await GuidelineItemDao.add_item_dao(query_db, page_object)
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='新增成功')
        except Exception as e:
            await query_db.rollback()
            raise e

    @classmethod
    async def edit_item_services(cls, query_db: AsyncSession, page_object: GuidelineItemModel) -> CrudResponseModel:
        """
        编辑规范条目

        :param query_db: orm对象
        :param page_object: 条目对象
        :return: 编辑结果
        """
        if not await GuidelineItemDao.get_item_detail_by_id(query_db, page_object.item_id):
            raise ServiceException(message='规范条目不存在')
        if page_object.guideline_id and not await GuidelineDao.get_guideline_detail_by_id(
            query_db, page_object.guideline_id
        ):
            raise ServiceException(message='修改失败，所属规范不存在')
        try:
            await GuidelineItemDao.edit_item_dao(
                query_db, page_object.model_dump(exclude_unset=True, exclude={'guideline_code', 'keyword'})
            )
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='更新成功')
        except Exception as e:
            await query_db.rollback()
            raise e

    @classmethod
    async def delete_item_services(cls, query_db: AsyncSession, item_ids: str) -> CrudResponseModel:
        """
        删除规范条目

        :param query_db: orm对象
        :param item_ids: 条目id字符串，多个以逗号分隔
        :return: 删除结果
        """
        id_list = [int(i) for i in item_ids.split(',') if i.strip()]
        if not id_list:
            raise ServiceException(message='传入条目id为空')
        try:
            await GuidelineItemDao.delete_item_dao(query_db, id_list)
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='删除成功')
        except Exception as e:
            await query_db.rollback()
            raise e


def _manuscript_line_map(text: str) -> dict[int, str]:
    """
    行号 → 该行原文，**直接用引擎那份实现**，不在后端另造一份。

    「空行不占行号」这条规则已经踩过一次：照物理行号去取原文，稿件里出现第一个空行之后
    就整体错位，而且**不报任何错** —— 行号仍在合法范围、页面照常滚过去，只是指着一段
    不相干的话。实测一份 2193 字的稿件：物理 77 行、有效 39 行。

    全仓的唯一定义在 `tools/checklist_worker_tool/engine/audit.py::line_map`；
    前端那份对照实现在 `action-frontend/composables/manuscriptLines.ts`，各有测试钉住。
    延迟导入：tools 包依赖 redis 等库，不该拖累未用到该功能的进程启动。

    :param text: 稿件全文
    :return: {行号: 该行原文}
    """
    from tools.checklist_worker_tool.engine.audit import line_map  # noqa: PLC0415

    return line_map(text)


@dataclass(frozen=True)
class _ReviewRun:
    """
    一次 checklist 校验的运行态快照（普通值，不是 ORM 对象）

    同 `_SrdRun`：投递 → 轮询 → 落库要连着提交好几次事务，而会话是 `expire_on_commit=True`，
    commit 之后读任何 ORM 属性都会触发懒加载，在 async 会话里直接抛 `MissingGreenlet`。
    """

    review_id: int
    session_id: str
    user_id: int
    guideline_id: int | None
    #: 这次是「导入并回填草稿」还是「只判定」。回填只在 import 那次做 ——
    #: 不分的话，用户之后每复查一次就把自己在第二步的编辑悄悄盖掉一遍
    purpose: str
    draft_id: int | None
    run_status: str
    progress: int
    error_msg: str


class ChecklistReviewService:
    """
    checklist 逐条校验服务层（报告助手第三步）

    算法由 `tools/checklist_worker_tool` 常驻 worker 干：后端把稿件与规范代号 rpush 进
    Redis 队列，worker 取条目、调模型、写状态。两个进程互不依赖 —— worker 挂了不影响官网，
    后端重启也不影响在跑的任务。

    ## 三件事：投递、对账、回看

    **投递**时就落一行 `pending` 台账（`action_report_review`），**轮询**时把 worker 的状态
    同步进库、终态那一刻把判定写进来，**回看**由历史列表与详情两个口提供。

    014 之前这里只有投递与透传状态，落库由前端在轮到 completed 时另调一个口完成。那样有两个
    后果，而它们在「刷新一下页面，刚跑完的校验就没了」上撞成同一个：跑失败/被停/用户关掉
    页面的任务一条都没留下（恰恰是要排查的那批），以及 session_id 只活在前端内存里，
    刷新之后 Redis 里明明还有结果却再也找不回来。

    ## 落库为什么在轮询里，不在 worker 里

    同 `SrdService`：worker 已经为了模型池连过一次库，再让它写业务表就等于把两个系统焊死。
    代价是「用户关掉页面就没人来落库」，由 `list_history_services` 顺带对账兜底。
    """

    #: 一个访客最多留几条历史。每行挂着一整篇稿件正文，比 014 之前更该管上限
    KEEP_HISTORY = 20
    #: 历史列表一次返回几条
    HISTORY_LIMIT = 20
    #: 同一访客同时在跑的校验数上限 —— 一次校验是几十次模型调用，不设闸等于把账单交给公网
    MAX_RUNNING_PER_USER = 2

    #: 完整度权重（模糊算半条）。与 `tools/checklist_worker_tool/engine/audit.py` 的
    #: `STATUS_WEIGHT` 是同一张表 —— 这里不 import 引擎（后端进程不该为了 3 个键去加载
    #: worker 那一整包依赖），但两处必须一致，**改引擎的权重时记得同步这里**。
    #: 同 `SrdService.RATING_SCORE` 的处理
    STATUS_WEIGHT: ClassVar[dict[str, float]] = {'reported': 1.0, 'vague': 0.5, 'missing': 0.0}

    @classmethod
    def _client(cls) -> Any:
        """延迟导入 worker 配置：tools 包依赖 redis 等库，不该拖累未用到该功能的进程启动。"""
        from tools.checklist_worker_tool.config.worker_config import CONFIG  # noqa: PLC0415
        from tools.common.task_client import TaskClient  # noqa: PLC0415

        return TaskClient(CONFIG)

    @classmethod
    def _snapshot(cls, record: ActionReportReview) -> _ReviewRun:
        """
        把 ORM 记录里这条链路要用的几个字段抄成普通值（理由见 `_ReviewRun`）

        :param record: 校验记录
        :return: 运行态快照
        """
        return _ReviewRun(
            review_id=record.review_id,
            session_id=record.session_id or '',
            user_id=record.user_id,
            guideline_id=record.guideline_id,
            purpose=record.purpose or 'check',
            draft_id=record.draft_id,
            run_status=record.run_status or 'pending',
            progress=record.progress or 0,
            error_msg=record.error_msg or '',
        )

    # ------------------------------------------------------------------ 对账

    @classmethod
    async def _count_running(cls, query_db: AsyncSession, user_id: int) -> int:
        """
        库里还挂着 pending/running 的记录数

        :param query_db: orm对象
        :param user_id: 访客用户id
        :return: 条数
        """
        return len(
            [
                r
                for r in await ReportReviewDao.get_user_reviews_dao(query_db, user_id, cls.HISTORY_LIMIT)
                if (r.run_status or '') in ('pending', 'running')
            ]
        )

    @classmethod
    async def _reconcile_pending(cls, query_db: AsyncSession, user_id: int) -> int:
        """
        对未终结的记录补查一次 worker 状态，跑完的补落库、查不到的判过期

        **这是整条链路的兜底**：落库发生在轮询里，而用户随时可能关掉页面 ——
        没有这一步，跑完的任务会永远挂在 running，孤儿还会占满并发名额。
        历史列表每次打开都做一遍，提交口只在撞上限时做。

        :param query_db: orm对象
        :param user_id: 访客用户id
        :return: 对账之后仍在跑的条数
        """
        pending = [
            cls._snapshot(r)
            for r in await ReportReviewDao.get_user_reviews_dao(query_db, user_id, cls.HISTORY_LIMIT)
            if (r.run_status or '') in ('pending', 'running') and r.session_id
        ]
        for run in pending:
            try:
                state = await cls._fetch_worker_state(run.session_id)
                if state is None:
                    await cls._mark_failed(query_db, run, '任务状态已过期，请重新提交')
                    continue
                await cls._sync_run(query_db, run, state)
            except Exception as e:
                # 对账是顺带做的，Redis 抖一下不该让整个历史列表打不开
                logger.warning(f'checklist 校验历史对账失败 {run.session_id}: {type(e).__name__}: {e}')

        return await cls._count_running(query_db, user_id)

    # ------------------------------------------------------------------ 投递

    @classmethod
    async def submit_review_services(
        cls,
        query_db: AsyncSession,
        submit: ChecklistReviewSubmitModel,
        user_id: int,
        purpose: ReviewPurpose = 'check',
    ) -> ChecklistReviewSubmitResultModel:
        """
        提交一次校验：先落台账，再入队

        **顺序与 SRD 相反，是刻意的**。SRD 先入队后落库，因为它要先把 PDF 落盘；这里没有
        文件，而台账本身就是目的之一 —— 先落库意味着连「入队都没成功」的任务都留得下痕迹，
        那正是排查队列/Redis 故障时唯一的线索。入队失败就地标 failed，不回滚掉这一行。

        :param query_db: orm对象
        :param submit: 提交模型
        :param user_id: 访客用户id
        :return: 任务id + 校验记录id
        :raises ServiceException: 规范不存在 / 无条目 / 草稿不属于本人 / 在跑的任务过多
        """
        guideline = await GuidelineDao.get_guideline_by_code(query_db, submit.guideline_code)
        if not guideline:
            raise ServiceException(message=f'报告规范 {submit.guideline_code} 不存在')
        # **就地抄成普通值，别把这个 ORM 对象带过下面那次 commit**：会话是
        # `expire_on_commit=True`，commit 之后读它的任何属性都要发一次懒加载，
        # 而懒加载在 async 会话里直接抛 `MissingGreenlet`（"greenlet_spawn has not been
        # called"）。踩过一次：入队用的 payload 在 commit 之后才去取 guideline.code，
        # 于是每一次提交都在落库成功后炸掉 —— 表现是「历史里多了一条 pending，
        # 页面却报错」。同 `_ReviewRun` / `_SrdRun` 那两个快照的理由
        guideline_id = guideline.guideline_id
        guideline_code = guideline.code

        # 条目为空时 worker 也会失败，但那要等排队+启动，不如在这里直接回绝
        items = await ReportDraftService._items_of(query_db, guideline_id)
        if not items:
            raise ServiceException(message=f'报告规范 {submit.guideline_code} 尚未录入 checklist 条目')

        # **撞上限时先对账再判**。这道闸数的是库里挂着 pending/running 的行，而那种行
        # 未必真的还在跑：入队失败、worker 崩了、Redis 里的状态过了 TTL，都会留下一个
        # 永远等不到终态的孤儿。只数不对账的话，两个孤儿就把这个账号永久锁在门外
        # ——而用户能看到的现象只有一句「你已有 2 个校验在进行中」，且怎么等都不会消失。
        # 对账本身有 Redis 往返，所以只在**真的撞上限**时才做：正常提交一次都不发
        running = await cls._count_running(query_db, user_id)
        if running >= cls.MAX_RUNNING_PER_USER:
            running = await cls._reconcile_pending(query_db, user_id)
        if running >= cls.MAX_RUNNING_PER_USER:
            raise ServiceException(message=f'你已有 {running} 个校验在进行中，请等它跑完再提交')

        # draft_id 由前端传，但**归属必须在这里验**：不验的话随手改一个 id
        # 就能把自己的判定挂到别人的草稿上，第四步的工作清单会跟着串台
        draft_id = None
        if submit.draft_id:
            draft = await ReportDraftDao.get_draft_by_id(query_db, submit.draft_id, user_id)
            if not draft:
                raise ServiceException(message='草稿不存在')
            draft_id = submit.draft_id

        # session_id 自己先生成：台账要先落库，而落库时就得带上它
        session_id = uuid.uuid4().hex
        manuscript = submit.manuscript
        review = ActionReportReview(
            draft_id=draft_id,
            user_id=user_id,
            guideline_id=guideline_id,
            guideline_code=guideline_code,
            session_id=session_id,
            purpose=purpose,
            run_status='pending',
            progress=0,
            locale=submit.locale,
            char_count=len(manuscript),
            item_total=len(items),
            manuscript=manuscript,
            del_flag='0',
            create_time=datetime.now(),
        )
        try:
            await ReportReviewDao.add_review_dao(query_db, review)
            # flush 之后主键才有值，而 commit 之后就读不到了（expire_on_commit）
            review_id = review.review_id
            await ReportReviewDao.trim_user_reviews_dao(query_db, user_id, cls.KEEP_HISTORY)
            await query_db.commit()
        except Exception:
            await query_db.rollback()
            raise

        payload = {
            'guideline_code': guideline_code,
            'guideline_id': guideline_id,
            'manuscript': manuscript,
            'locale': submit.locale,
            'user_id': user_id,
        }
        try:
            async with cls._client() as client:
                await client.submit(payload, session_id=session_id)
        except Exception as e:
            # 台账留着并标记失败：用户在历史里看得见「这次没提交上去」，
            # 运维也查得到是哪一刻的哪一条。静默回滚等于把这次故障抹掉
            with contextlib.suppress(Exception):
                await ReportReviewDao.edit_review_dao(
                    query_db,
                    review_id,
                    {
                        'run_status': 'failed',
                        'error_msg': f'任务入队失败：{type(e).__name__}'[:500],
                        'finish_time': datetime.now(),
                    },
                )
                await query_db.commit()
            raise ServiceException(message=f'校验任务提交失败，请稍后重试：{type(e).__name__}') from e

        return ChecklistReviewSubmitResultModel(sessionId=session_id, reviewId=review_id)

    # ------------------------------------------------------------------ 轮询与对账

    @classmethod
    async def review_state_services(
        cls, query_db: AsyncSession, session_id: str, user_id: int
    ) -> ChecklistReviewStateModel:
        """
        查询校验任务状态；跑完顺手把判定落库

        :param query_db: orm对象
        :param session_id: 任务id
        :param user_id: 访客用户id（越权保护）
        :return: 任务快照
        :raises ServiceException: 任务不存在或不属于该用户
        """
        record = await ReportReviewDao.get_review_by_session_dao(query_db, session_id, user_id)
        if not record:
            raise ServiceException(message='校验任务不存在')
        run = cls._snapshot(record)

        state = await cls._fetch_worker_state(session_id)
        if state is None:
            # Redis 里的任务状态有 TTL（默认 7 天）。已经落过库的记录不受影响 ——
            # 判定就在业务表里，用户照样能从历史点开看
            if run.run_status in ('pending', 'running'):
                run = await cls._mark_failed(query_db, run, '任务状态已过期，请重新提交')
        else:
            run = await cls._sync_run(query_db, run, state)

        return ChecklistReviewStateModel(
            sessionId=run.session_id,
            reviewId=run.review_id,
            status=run.run_status,
            progressCurrent=int((state or {}).get('progress_current') or 0),
            progressTotal=int((state or {}).get('progress_total') or 100) or 100,
            message=str((state or {}).get('message') or ''),
            error=run.error_msg,
            result=(state or {}).get('result') if isinstance((state or {}).get('result'), dict) else None,
        )

    @classmethod
    async def _fetch_worker_state(cls, session_id: str) -> dict[str, Any] | None:
        """
        读 worker 的任务状态快照

        :param session_id: 任务id
        :return: 状态字典；任务不存在或已过期时为 None
        """
        try:
            async with cls._client() as client:
                return await client.status(session_id)
        except Exception as e:
            raise ServiceException(message=f'校验任务状态查询失败：{type(e).__name__}') from e

    @classmethod
    async def _commit_values(cls, query_db: AsyncSession, run: _ReviewRun, values: dict[str, Any]) -> _ReviewRun:
        """
        更新校验记录并返回改过的快照

        :param query_db: orm对象
        :param run: 运行态快照
        :param values: 列名到值的映射
        :return: 更新后的快照
        """
        try:
            await ReportReviewDao.edit_review_dao(query_db, run.review_id, values)
            await query_db.commit()
        except Exception:
            await query_db.rollback()
            raise

        return replace(
            run,
            run_status=str(values.get('run_status', run.run_status)),
            progress=int(values.get('progress', run.progress)),
            error_msg=str(values.get('error_msg', run.error_msg)),
        )

    @classmethod
    async def _mark_failed(cls, query_db: AsyncSession, run: _ReviewRun, error: str) -> _ReviewRun:
        """
        把记录标记为失败

        :param query_db: orm对象
        :param run: 运行态快照
        :param error: 失败原因
        :return: 更新后的快照
        """
        return await cls._commit_values(
            query_db, run, {'run_status': 'failed', 'error_msg': error[:500], 'finish_time': datetime.now()}
        )

    @classmethod
    async def _sync_run(cls, query_db: AsyncSession, run: _ReviewRun, state: dict[str, Any]) -> _ReviewRun:
        """
        把 worker 的状态同步进库；首次看到 completed 时把判定写进来

        已经是 completed 的记录直接跳过 —— 前端会一直轮询到拿着结果离开页面，
        没有这道闸就会每 2 秒重写一次 282 条判定。

        :param query_db: orm对象
        :param run: 运行态快照
        :param state: worker 状态快照
        :return: 更新后的快照
        """
        if run.run_status == 'completed':
            return run

        status = str(state.get('status') or 'pending')
        current = int(state.get('progress_current') or 0)
        total = int(state.get('progress_total') or 100) or 100
        progress = min(100, round(current / total * 100))

        if status == 'completed':
            result = state.get('result') if isinstance(state.get('result'), dict) else {}

            return await cls._persist_result(query_db, run, result or {})

        values: dict[str, Any] = {'run_status': status, 'progress': progress}
        if status in ('failed', 'stopped'):
            values['error_msg'] = (str(state.get('error') or '') or ('已停止' if status == 'stopped' else '校验失败'))[
                :500
            ]
            values['finish_time'] = datetime.now()

        return await cls._commit_values(query_db, run, values)

    @classmethod
    async def _persist_result(
        cls, query_db: AsyncSession, run: _ReviewRun, result: dict[str, Any]
    ) -> _ReviewRun:
        """
        把 worker 的判定结果写进业务表

        **判定必须落在这份规范当前启用的条目上**：条目 id 来自 worker，而 worker 是照着
        提交那一刻的条目表跑的；后台若在这期间停用了某几条，落进来就是一批孤儿 ——
        第四步按 item_id 取要求原文会取不到，渲染成一排空白。

        :param query_db: orm对象
        :param run: 运行态快照
        :param result: worker 的结果摘要
        :return: 更新后的快照
        """
        raw_verdicts = result.get('verdicts') if isinstance(result.get('verdicts'), list) else []

        # 条目取出来是**驼峰键的字典**（PageUtil.paginate 的出参），不是 ORM 对象
        valid_ids: set[int] = set()
        if run.guideline_id:
            items = await ReportDraftService._items_of(query_db, run.guideline_id)
            valid_ids = {int(it['itemId']) for it in items}

        seen: set[int] = set()
        rows: list[dict[str, Any]] = []
        for v in raw_verdicts or []:
            if not isinstance(v, dict):
                continue
            try:
                item_id = int(v.get('itemId') or v.get('item_id') or 0)
            except (TypeError, ValueError):
                continue
            status = str(v.get('status') or '')
            if item_id not in valid_ids or item_id in seen or status not in ('reported', 'vague', 'missing'):
                continue
            seen.add(item_id)
            lines = v.get('lines') or []
            rows.append(
                {
                    'item_id': item_id,
                    'status': status,
                    'reason': str(v.get('reason') or '')[:2000],
                    'evidence': str(v.get('evidence') or '')[:500],
                    # 库里存逗号分隔的字符串，引擎给的是数字数组
                    'lines': ','.join(str(int(n)) for n in lines if isinstance(n, (int, float)))[:200],
                }
            )

        counts = Counter(r['status'] for r in rows)
        consistency = result.get('consistency') if isinstance(result.get('consistency'), dict) else None
        models = result.get('models') if isinstance(result.get('models'), list) else []

        # 条目总数与完整度**按实际落库的行重算**，不照抄 worker 摘要里的 total/completeness。
        # 上面那道过滤可能丢掉几条（后台在任务跑着的时候停用了条目），照抄的话历史行会显示
        # 「共 3 条、完整度 50%」而点开只有 1 条 —— 数字与明细对不上，且对不上的方向永远是
        # 「看起来判得比实际多」。没有可计分条目时完整度按 0
        graded = len(rows)
        score = sum(cls.STATUS_WEIGHT.get(r['status'], 0.0) for r in rows)

        values: dict[str, Any] = {
            'run_status': 'completed',
            'progress': 100,
            'error_msg': '',
            'reported': counts.get('reported', 0),
            'vague': counts.get('vague', 0),
            'missing': counts.get('missing', 0),
            'item_total': graded,
            'completeness': round(score / graded * 100) if graded else 0,
            'line_count': int(result.get('lineCount') or 0),
            'truncated': '1' if result.get('truncated') else '0',
            'models': ' / '.join(str(m) for m in models)[:200],
            'consistency': json.dumps(consistency, ensure_ascii=False) if consistency else None,
            'finish_time': datetime.now(),
        }
        try:
            await ReportReviewDao.replace_review_items_dao(query_db, run.review_id, rows)
            await ReportReviewDao.edit_review_dao(query_db, run.review_id, values)
            await query_db.commit()
        except Exception:
            await query_db.rollback()
            raise

        # 导入那一次跑完，把匹配到的原文段落回填进草稿条目。**只在 import 时做**：
        # 之后每次复查都回填的话，用户在第二步的编辑会被悄无声息地盖掉一遍
        if run.purpose == 'import' and run.draft_id:
            try:
                await cls._backfill_draft(query_db, run, rows)
            except Exception as e:
                # 回填失败不该让整次判定作废 —— 判定已经落库了，用户至少还能在第三步看结果，
                # 也能自己去第二步逐条填。静默吞掉才是最糟的，所以记日志
                logger.warning(f'导入回填失败 review={run.review_id} draft={run.draft_id}: {type(e).__name__}: {e}')

        return replace(run, run_status='completed', progress=100, error_msg='')

    @classmethod
    async def _backfill_draft(cls, query_db: AsyncSession, run: _ReviewRun, rows: list[dict[str, Any]]) -> None:
        """
        按判定里的行号，从原稿还原段落、填进草稿条目

        ## 为什么用行号而不是 evidence

        `evidence` 是引擎截到 200 字符的**片段**，拿它当条目正文，用户在第二步看到的
        就是一句被砍断的话。行号指向的才是完整的原文行。行号口径由引擎的 `line_map`
        定义（**空行不占号**），后端直接 import 它，不另造实现。

        ## 只填空框

        已经有内容的条目一律跳过。导入那一刻草稿是全新的、框都是空的，这道判断是为
        「同一份草稿被重复导入」之类的意外兜底 —— 覆盖用户已有的字是不能接受的。

        :param query_db: orm对象
        :param run: 运行态快照
        :param rows: 已落库的逐条判定
        """
        draft = await ReportDraftDao.get_draft_by_id(query_db, run.draft_id, run.user_id)
        if not draft or not draft.source_text:
            return
        source = draft.source_text
        lines = _manuscript_line_map(source)

        existing = await ReportDraftDao.get_draft_items(query_db, run.draft_id, run.user_id)
        contents = {r.item_id: (r.content or '') for r in existing}

        filled = 0
        for r in rows:
            item_id = int(r['item_id'])
            if contents.get(item_id, '').strip():
                continue
            nums = [int(n) for n in str(r.get('lines') or '').split(',') if n.strip().isdigit()]
            text = '\n'.join(lines[n] for n in sorted(set(nums)) if n in lines)
            if not text.strip():
                continue
            contents[item_id] = text
            filled += 1

        if not filled:
            return

        items = await ReportDraftService._items_of(query_db, run.guideline_id) if run.guideline_id else []
        valid_ids = {int(it['itemId']) for it in items}
        try:
            await ReportDraftDao.replace_draft_items(query_db, run.draft_id, run.user_id, contents, valid_ids)
            await query_db.commit()
        except Exception:
            await query_db.rollback()
            raise
        logger.info(f'导入回填：草稿 {run.draft_id} 填入 {filled} 条')


    # ------------------------------------------------------------------ 回看

    @classmethod
    async def list_history_services(cls, query_db: AsyncSession, user_id: int) -> list[ReportReviewHistoryModel]:
        """
        我的校验历史

        顺手对账：用户关掉页面后没人再轮询，跑完的任务会一直挂在 running。这里对未终结的
        记录补查一次 worker 状态，把结果补落库 —— **这一步就是「刷新之后还找得回来」的兜底**。

        对账与取列表分成两趟：对账要提交事务，而提交会让第一趟查出来的 ORM 对象全部失效
        （见 `_ReviewRun`），所以对账只在快照上做，改完再重新查一次列表。

        :param query_db: orm对象
        :param user_id: 访客用户id
        :return: 历史列表
        """
        await cls._reconcile_pending(query_db, user_id)

        records = await ReportReviewDao.get_user_reviews_dao(query_db, user_id, cls.HISTORY_LIMIT)

        return [
            ReportReviewHistoryModel(
                reviewId=r.review_id,
                sessionId=r.session_id or '',
                draftId=r.draft_id,
                guidelineCode=r.guideline_code or '',
                runStatus=r.run_status or 'pending',
                errorMsg=r.error_msg or '',
                progress=r.progress or 0,
                charCount=r.char_count or 0,
                itemTotal=r.item_total or 0,
                completeness=r.completeness or 0,
                reported=r.reported or 0,
                vague=r.vague or 0,
                missing=r.missing or 0,
                createTime=r.create_time,
                finishTime=r.finish_time,
            )
            for r in records
        ]

    @classmethod
    async def get_review_services(cls, query_db: AsyncSession, review_id: int, user_id: int) -> ReportReviewModel:
        """
        取一次校验的完整结果（历史回看）

        :param query_db: orm对象
        :param review_id: 校验记录id
        :param user_id: 访客用户id
        :return: 校验详情
        :raises ServiceException: 记录不存在或不属于该用户
        """
        record = await ReportReviewDao.get_review_by_id_dao(query_db, review_id, user_id)
        if not record:
            # 「不存在」而不是「无权访问」：后者等于告诉调用方这个 id 是真的
            raise ServiceException(message='校验记录不存在')

        rows = await ReportReviewDao.get_review_items_dao(query_db, record.review_id)
        consistency = None
        if record.consistency:
            try:
                parsed = json.loads(record.consistency)
                consistency = parsed if isinstance(parsed, dict) else None
            except ValueError:
                # 存进去的是引擎给的 JSON，解不动说明这一行坏了。整份详情不该因此打不开，
                # 一致性那一段空着就是了（前台本来就按「worker 没跑这段」处理）
                logger.warning(f'校验记录 {record.review_id} 的一致性结果解析失败')

        return ReportReviewModel(
            reviewId=record.review_id,
            draftId=record.draft_id,
            guidelineId=record.guideline_id,
            guidelineCode=record.guideline_code or '',
            sessionId=record.session_id or '',
            runStatus=record.run_status or 'completed',
            errorMsg=record.error_msg or '',
            progress=record.progress or 0,
            models=record.models or '',
            locale=record.locale or 'zh',
            charCount=record.char_count or 0,
            itemTotal=record.item_total or 0,
            completeness=record.completeness or 0,
            reported=record.reported or 0,
            vague=record.vague or 0,
            missing=record.missing or 0,
            lineCount=record.line_count or 0,
            truncated=(record.truncated or '0') == '1',
            manuscript=record.manuscript or '',
            consistency=consistency,
            verdicts=[
                ReviewVerdictModel(
                    itemId=r.item_id,
                    status=r.status,
                    reason=r.reason or '',
                    evidence=r.evidence or '',
                    lines=r.lines or '',
                )
                for r in rows
            ],
            createTime=record.create_time,
            finishTime=record.finish_time,
        )

    @classmethod
    async def delete_history_services(cls, query_db: AsyncSession, review_id: int, user_id: int) -> CrudResponseModel:
        """
        删除一条校验历史（记录逻辑删，稿件正文与 evidence 物理删）

        「真删正文」是 014 存稿件的对价，理由见 `ReportReviewDao.soft_delete_review_dao`。

        :param query_db: orm对象
        :param review_id: 校验记录id
        :param user_id: 访客用户id
        :return: 操作结果
        """
        record = await ReportReviewDao.get_review_by_id_dao(query_db, review_id, user_id)
        if not record:
            raise ServiceException(message='校验记录不存在')
        try:
            await ReportReviewDao.soft_delete_review_dao(query_db, review_id)
            await query_db.commit()
        except Exception:
            await query_db.rollback()
            raise

        return CrudResponseModel(is_success=True, message='删除成功')

    @classmethod
    async def stop_review_services(cls, query_db: AsyncSession, session_id: str, user_id: int) -> CrudResponseModel:
        """
        请求停止校验任务

        :param query_db: orm对象
        :param session_id: 任务id
        :param user_id: 访客用户id（越权保护）
        :return: 操作结果
        :raises ServiceException: 任务不存在或不属于该用户
        """
        # 停别人的任务本来就该拦住；014 之前这个口只认 session_id，
        # 拿到一个 id 就能停任意用户在跑的校验
        record = await ReportReviewDao.get_review_by_session_dao(query_db, session_id, user_id)
        if not record:
            raise ServiceException(message='校验任务不存在')
        try:
            async with cls._client() as client:
                await client.stop(session_id)
        except Exception as e:
            raise ServiceException(message=f'停止失败：{type(e).__name__}') from e

        return CrudResponseModel(is_success=True, message='已请求停止')


class StudyTypeService:
    """
    官网研究类型服务层（智能报告工具：类型 -> 规范 + 统计推荐）
    """

    @classmethod
    async def get_study_type_tree_services(cls, query_db: AsyncSession) -> list[StudyTypeModel]:
        """
        获取研究类型及其关联规范、统计推荐

        单独取三张表后在内存里组装，避免 ORM 关系映射带来的 N+1 查询。

        :param query_db: orm对象
        :return: 研究类型列表
        """
        types = await StudyTypeDao.get_study_type_list(query_db)
        type_ids = [t.type_id for t in types]
        guidelines = await StudyTypeDao.get_guidelines_by_type_ids(query_db, type_ids)
        stats = await StudyTypeDao.get_stats_by_type_ids(query_db, type_ids)

        gl_map: dict[int, list[str]] = defaultdict(list)
        for g in guidelines:
            gl_map[g.type_id].append(g.guideline_code)

        stat_map: dict[int, list[StudyTypeStatModel]] = defaultdict(list)
        for s in stats:
            stat_map[s.type_id].append(StudyTypeStatModel(textZh=s.text_zh, textEn=s.text_en))

        return [
            StudyTypeModel(
                typeId=t.type_id,
                typeKey=t.type_key,
                nameZh=t.name_zh,
                nameEn=t.name_en,
                hotGuideline=t.hot_guideline,
                sortNum=t.sort_num,
                guidelines=gl_map.get(t.type_id, []),
                stats=stat_map.get(t.type_id, []),
            )
            for t in types
        ]


    # ------------------------------------------------------------------ 后台管理
    #
    # 「研究类型管理」页面。这张表是**报告助手第一步的问卷词表**，与
    # `action_guideline_category`（规范目录的陈列分类）用途不同、不要合并 ——
    # 同一类研究在两边取同样的 key，但不构成外键关系。

    @classmethod
    async def _assert_hot_guideline(cls, query_db: AsyncSession, code: str) -> None:
        """
        校验重点推荐规范：必须存在，且**真有 checklist 条目**

        `hot_guideline` 决定第二步展开哪份 checklist。指向一份不存在或 0 条目的规范，
        表现是「第一步选得出来、第二步一片空白」，而且要等用户走到第二步才发现。
        眼下 `obs → STROBE` 就是 0 条（仓库里没有 STROBE 的中英素材），所以 0 条**只警告不拦**
        —— 拦死就没法先把类型建起来、素材后补。不存在的代号则直接拦。

        :param query_db: orm对象
        :param code: 规范代号
        :raises ServiceException: 代号在 action_guideline 里不存在
        """
        if not code:
            return
        guideline = await GuidelineDao.get_guideline_by_code(query_db, code)
        if not guideline:
            raise ServiceException(
                message=f'重点推荐规范 {code} 不存在；它决定第二步展开哪份 checklist，'
                f'请先在「规范目录管理」中建好这份规范'
            )

    @classmethod
    async def get_study_type_page_services(
        cls, query_db: AsyncSession, keyword: str | None = None
    ) -> list[StudyTypeModel]:
        """
        后台列表。**不分页** —— 这是张词表，眼下 8 行，可预见也就十几行

        :param query_db: orm对象
        :param keyword: 按标识或名称模糊搜索
        :return: 研究类型列表（含两张子表）
        """
        rows = await cls.get_study_type_tree_services(query_db)
        kw = (keyword or '').strip().lower()
        if not kw:
            return rows

        return [
            r
            for r in rows
            if kw in (r.type_key or '').lower()
            or kw in (r.name_zh or '').lower()
            or kw in (r.name_en or '').lower()
        ]

    @classmethod
    async def add_study_type_services(
        cls, query_db: AsyncSession, save: StudyTypeSaveModel, operator: str
    ) -> CrudResponseModel:
        """
        新增研究类型

        :param query_db: orm对象
        :param save: 入参
        :param operator: 操作人
        :return: 新增结果
        """
        if await StudyTypeDao.get_study_type_by_key(query_db, save.type_key):
            raise ServiceException(message=f'新增失败，类型标识 {save.type_key} 已存在')
        await cls._assert_hot_guideline(query_db, save.hot_guideline)

        sort_num = save.sort_num
        if sort_num is None:
            sort_num = await StudyTypeDao.get_max_type_sort_num(query_db) + 1
        try:
            obj = ActionStudyType(
                type_key=save.type_key,
                name_zh=save.name_zh,
                name_en=save.name_en,
                hot_guideline=save.hot_guideline,
                sort_num=sort_num,
                status=save.status,
                create_by=operator,
                create_time=datetime.now(),
                update_by=operator,
                update_time=datetime.now(),
            )
            await StudyTypeDao.add_study_type_dao(query_db, obj)
            await StudyTypeDao.replace_type_children_dao(
                query_db, obj.type_id, save.guidelines, [(s.text_zh or '', s.text_en or '') for s in save.stats]
            )
            await query_db.commit()
        except Exception as e:
            await query_db.rollback()
            raise e

        # 前台选项是写死的数组 + i18n 键，光入库还看不见 —— 这句话必须让操作者当场读到
        return CrudResponseModel(
            is_success=True,
            message=f'新增成功。注意：前台第一步的选项还需开发同步 '
            f'`composables/wizardQuery.ts` 的 TYPE_OPTS 与文案键 assistant.typeOpt.{save.type_key}，'
            f'否则这个类型在官网上选不出来',
        )

    @classmethod
    async def edit_study_type_services(
        cls, query_db: AsyncSession, save: StudyTypeSaveModel, operator: str
    ) -> CrudResponseModel:
        """
        编辑研究类型

        :param query_db: orm对象
        :param save: 入参
        :param operator: 操作人
        :return: 编辑结果
        """
        current = await StudyTypeDao.get_study_type_by_id(query_db, save.type_id or 0)
        if not current:
            raise ServiceException(message='研究类型不存在')
        old_key = current.type_key
        await cls._assert_hot_guideline(query_db, save.hot_guideline)

        if save.type_key != old_key:
            exist = await StudyTypeDao.get_study_type_by_key(query_db, save.type_key)
            if exist and exist.type_id != save.type_id:
                raise ServiceException(message=f'修改失败，类型标识 {save.type_key} 已存在')

        try:
            await StudyTypeDao.edit_study_type_dao(
                query_db,
                save.type_id,
                {
                    'type_key': save.type_key,
                    'name_zh': save.name_zh,
                    'name_en': save.name_en,
                    'hot_guideline': save.hot_guideline,
                    'sort_num': save.sort_num if save.sort_num is not None else current.sort_num,
                    'status': save.status,
                    'update_by': operator,
                    'update_time': datetime.now(),
                },
            )
            await StudyTypeDao.replace_type_children_dao(
                query_db, save.type_id, save.guidelines, [(s.text_zh or '', s.text_en or '') for s in save.stats]
            )
            await query_db.commit()
        except Exception as e:
            await query_db.rollback()
            raise e

        if save.type_key != old_key:
            # 改键 = 前台那个选项的文案退化成键名本身，且老键的 i18n 词条成了孤儿
            return CrudResponseModel(
                is_success=True,
                message=f'更新成功。注意：类型标识由 {old_key} 改为 {save.type_key}，'
                f'前台的 TYPE_OPTS 与文案键 assistant.typeOpt.* 需同步改，否则该选项会显示成键名',
            )

        return CrudResponseModel(is_success=True, message='更新成功')

    @classmethod
    async def delete_study_type_services(cls, query_db: AsyncSession, type_ids: str) -> CrudResponseModel:
        """
        删除研究类型（连同两张子表）

        :param query_db: orm对象
        :param type_ids: 类型id字符串，多个以逗号分隔
        :return: 删除结果
        """
        id_list = [int(i) for i in type_ids.split(',') if i.strip()]
        if not id_list:
            raise ServiceException(message='传入类型id为空')
        try:
            await StudyTypeDao.delete_study_types_dao(query_db, id_list)
            await query_db.commit()

            return CrudResponseModel(
                is_success=True,
                message='删除成功。若前台 TYPE_OPTS 里还留着这个标识，那个选项会匹配不到规范，请一并清理',
            )
        except Exception as e:
            await query_db.rollback()
            raise e

class ImplementationService:
    """
    实施科学服务层（CFIR / ERIC / RE-AIM）
    """

    @classmethod
    async def get_cfir_tree_services(cls, query_db: AsyncSession) -> list[CfirDomainModel]:
        """
        获取 CFIR 领域 -> 构念 -> 策略 三级结构

        :param query_db: orm对象
        :return: CFIR 领域列表
        """
        domains = await ImplementationDao.get_cfir_domains(query_db)
        domain_ids = [d.domain_id for d in domains]
        constructs = await ImplementationDao.get_cfir_constructs(query_db, domain_ids)
        construct_ids = [c.construct_id for c in constructs]
        strategies = await ImplementationDao.get_cfir_strategies(query_db, construct_ids)

        strat_map: dict[int, list[CfirStrategyModel]] = defaultdict(list)
        for s in strategies:
            strat_map[s.construct_id].append(
                CfirStrategyModel(
                    strategyId=s.strategy_id,
                    nameZh=s.name_zh,
                    nameEn=s.name_en,
                    detailZh=s.detail_zh,
                    detailEn=s.detail_en,
                    sourceZh=s.source_zh,
                    sourceEn=s.source_en,
                )
            )

        con_map: dict[int, list[CfirConstructModel]] = defaultdict(list)
        for c in constructs:
            con_map[c.domain_id].append(
                CfirConstructModel(
                    constructId=c.construct_id,
                    code=c.code,
                    nameZh=c.name_zh,
                    nameEn=c.name_en,
                    hintZh=c.hint_zh,
                    hintEn=c.hint_en,
                    severity=c.severity,
                    strategies=strat_map.get(c.construct_id, []),
                )
            )

        return [
            CfirDomainModel(
                domainId=d.domain_id,
                seq=d.seq,
                nameZh=d.name_zh,
                nameEn=d.name_en,
                constructs=con_map.get(d.domain_id, []),
            )
            for d in domains
        ]

    @classmethod
    async def get_eric_services(
        cls, query_db: AsyncSession, category: str | None = None
    ) -> dict[str, list[Any]]:
        """
        获取 ERIC 分类与策略

        :param query_db: orm对象
        :param category: 可选的分类过滤
        :return: 含 categories 与 strategies 的字典
        """
        categories = await ImplementationDao.get_eric_categories(query_db)
        strategies = await ImplementationDao.get_eric_strategies(query_db, category)

        return {
            'categories': [
                EricCategoryModel(catKey=c.cat_key, nameZh=c.name_zh, nameEn=c.name_en) for c in categories
            ],
            'strategies': [
                EricStrategyModel(
                    ericId=s.eric_id,
                    category=s.category,
                    nameZh=s.name_zh,
                    nameEn=s.name_en,
                    detailZh=s.detail_zh,
                    detailEn=s.detail_en,
                    mapZh=s.map_zh,
                    mapEn=s.map_en,
                )
                for s in strategies
            ],
        }

    @classmethod
    async def get_reaim_services(cls, query_db: AsyncSession) -> list[ReaimDimensionModel]:
        """
        获取 RE-AIM 维度列表

        :param query_db: orm对象
        :return: 维度列表
        """
        dims = await ImplementationDao.get_reaim_dimensions(query_db)

        return [
            ReaimDimensionModel(
                dimId=d.dim_id,
                letter=d.letter,
                nameZh=d.name_zh,
                nameEn=d.name_en,
                subTitle=d.sub_title,
                definitionZh=d.definition_zh,
                definitionEn=d.definition_en,
                measureZh=d.measure_zh,
                measureEn=d.measure_en,
                scoreText=d.score_text,
            )
            for d in dims
        ]


@dataclass(frozen=True)
class _SrdRun:
    """
    一次 SRD 评估的运行态快照（普通值，不是 ORM 对象）

    投递 → 轮询 → 落库这条链路要连着提交好几次事务，而会话是 `expire_on_commit=True`：
    commit 之后 ORM 实例全部失效，再读属性就要发懒加载，在 async 会话里直接抛
    `MissingGreenlet`。所以这条链路一律只在这个快照上走。
    """

    assessment_id: int
    session_id: str
    user_id: int | None
    run_status: str
    progress: int
    error_msg: str


class SrdService:
    """
    SRD 系统综述重复性评估服务层

    三件事：**投递**（存 PDF → 入队 → 落一行 pending 记录）、**轮询**（读 worker 状态，
    跑完就把引擎结果落库）、**回看**（我的历史 + 按 id 取详情）。

    干活的是 `tools/srd_worker_tool` 常驻 worker（Redis 队列驱动），后端不碰算法。
    两个进程之间除了 Redis 还共享一件东西：**文件系统** ——
    输入 PDF 由后端写进 `vf_admin/private_upload_path/srd/`、以 `path` 交给 worker，
    结果 `result.json` 由 worker 写进自己的 `results/`、后端按摘要里的路径读回来。
    这是刻意的：用户上传的综述 PDF 不该进那个整桶公共读的 OSS 桶。
    代价是 **worker 必须与后端同机（或挂同一份存储）**，部署时别拆开。
    """

    #: 上传上限。系统综述 PDF 常规在 1–5MB，30MB 足够带附录；再大多半是扫描件（引擎也解析不出文字）
    MAX_PDF_BYTES = 30 * 1024 * 1024
    #: 单个访客最多能看到多少条历史
    HISTORY_LIMIT = 30
    #: 同一访客同时在跑的评估数上限 —— 一次评估是几十次模型调用，不设闸等于把账单交给公网
    MAX_RUNNING_PER_USER = 2

    #: 评分 → 分数。与 `srd_engine.schemas.RATING_SCORE` 同一张表；
    #: 这里不 import 引擎（后端进程不该为了 5 个键去加载 pydantic 模型与 yaml 口径），
    #: 但两处必须一致，改引擎的评分档位时记得同步这里。
    #:
    #: **rating 键就是分数本身**，引擎 0.8.0 翻转的是标签不是这层映射，所以这张表一字未动：
    #: 3 = 完全相同（最重复）… 0 = 完全不同。分越高越重复，别照着 Excel 表 1 的表头读反。
    RATING_SCORE: ClassVar[dict[str, int | None]] = {'0': 0, '1': 1, '2': 2, '3': 3, 'unclear': None}

    # ------------------------------------------------------------------ 投递

    @classmethod
    def _client(cls) -> Any:
        """延迟导入 worker 配置：tools 包依赖 redis 等库，不该拖累未用到该功能的进程启动。"""
        from tools.common.task_client import TaskClient  # noqa: PLC0415
        from tools.srd_worker_tool.config.worker_config import CONFIG  # noqa: PLC0415

        return TaskClient(CONFIG)

    @classmethod
    def _session_dir(cls, session_id: str) -> Path:
        """
        某次评估的输入目录

        一次评估一个目录（目录名就是 session_id），跑完整个目录删掉即可 ——
        不必再把两条服务器本地路径存进业务表。

        :param session_id: 任务id
        :return: 目录路径
        """
        return Path(UploadConfig.PRIVATE_UPLOAD_PATH) / 'srd' / session_id

    @classmethod
    async def _save_pdf(cls, upload: UploadFile, label: str, session_dir: Path) -> tuple[Path, str]:
        """
        校验并落盘一个上传的 PDF

        只认 PDF：引擎的解析器（pymupdf）也只吃 PDF，放行别的格式只会在 worker 里
        跑到一半才失败，用户白等几分钟。扩展名不可信，按文件头判。

        :param upload: 上传文件
        :param label: A / B，仅用于报错文案与文件名
        :param session_dir: 本次评估的输入目录
        :return: (落盘路径, 原始文件名)
        """
        limit_mb = cls.MAX_PDF_BYTES // 1024 // 1024
        # 先看 Starlette 解析 multipart 时记下的大小，再决定要不要整份读进内存 ——
        # 只靠 read() 之后判长度的话，一发 500MB 的请求就是 500MB 的驻留内存
        if upload.size is not None and upload.size > cls.MAX_PDF_BYTES:
            raise ServiceException(message=f'综述{label} 超过 {limit_mb}MB 上限')

        content = await upload.read()
        if not content:
            raise ServiceException(message=f'综述{label} 的文件为空')
        if len(content) > cls.MAX_PDF_BYTES:
            raise ServiceException(message=f'综述{label} 超过 {limit_mb}MB 上限')
        if not content.startswith(b'%PDF'):
            raise ServiceException(message=f'综述{label} 不是 PDF 文件')

        await asyncio.to_thread(session_dir.mkdir, parents=True, exist_ok=True)
        # 文件名不取用户给的：那是攻击面（路径穿越、超长名、非法字符），而且引擎只看内容
        target = session_dir / f'{label}.pdf'
        await asyncio.to_thread(target.write_bytes, content)

        return target, (upload.filename or f'review_{label}.pdf')

    @classmethod
    def _title_from_filename(cls, filename: str) -> str:
        """
        用文件名当占位标题

        真实标题由引擎从正文里抽（`AssessmentResult.review_a_title`），跑完会覆盖掉这个值。
        但 `review_a_title_zh` 是 not null，提交那一刻必须先有个能看的东西 ——
        历史列表在任务还没跑完时显示的就是它。

        :param filename: 原始文件名
        :return: 去掉扩展名的文件名
        """
        stem = Path(filename).stem.strip()

        return (stem or filename)[:600]

    @classmethod
    async def submit_assessment_services(
        cls, query_db: AsyncSession, user_id: int, file_a: UploadFile, file_b: UploadFile
    ) -> str:
        """
        提交一次 A/B 配对评估

        :param query_db: orm对象
        :param user_id: 访客用户id
        :param file_a: 综述A的PDF
        :param file_b: 综述B的PDF
        :return: 任务id（session_id）
        """
        running = [
            r
            for r in await SrdDao.get_user_assessments(query_db, user_id, cls.HISTORY_LIMIT)
            if r.run_status in ('pending', 'running')
        ]
        if len(running) >= cls.MAX_RUNNING_PER_USER:
            raise ServiceException(message=f'你已有 {len(running)} 个评估在进行中，请等它跑完再提交')

        # session_id 自己先生成：输入目录以它命名，跑完按 id 就能整目录删掉
        session_id = uuid.uuid4().hex
        session_dir = cls._session_dir(session_id)
        try:
            path_a, name_a = await cls._save_pdf(file_a, 'A', session_dir)
            path_b, name_b = await cls._save_pdf(file_b, 'B', session_dir)
        except Exception:
            await asyncio.to_thread(shutil.rmtree, session_dir, True)
            raise

        title_a = cls._title_from_filename(name_a)
        title_b = cls._title_from_filename(name_b)
        payload = {
            'user_id': user_id,
            'review_a': {'path': str(path_a.resolve()), 'title': title_a},
            'review_b': {'path': str(path_b.resolve()), 'title': title_b},
        }
        try:
            async with cls._client() as client:
                await client.submit(payload, session_id=session_id)
        except Exception as e:
            # 入队失败就别把 PDF 留在盘上：没有任何东西会再来读它
            await asyncio.to_thread(shutil.rmtree, session_dir, True)
            raise ServiceException(message=f'评估任务提交失败，请稍后重试：{type(e).__name__}') from e

        try:
            await SrdDao.add_assessment_dao(
                query_db,
                {
                    'session_id': session_id,
                    'user_id': user_id,
                    'run_status': 'pending',
                    'progress': 0,
                    'file_a_name': name_a[:255],
                    'file_b_name': name_b[:255],
                    'review_a_title_zh': title_a,
                    'review_b_title_zh': title_b,
                    'is_sample': '0',
                    'status': '0',
                    'del_flag': '0',
                    'create_by': str(user_id),
                    'create_time': datetime.now(),
                },
            )
            await query_db.commit()
        except Exception as e:
            await query_db.rollback()
            # 队列里已经有这个任务了，落库却失败：没有记录就没人会去轮询它，
            # 让它白跑几十次模型调用不如立刻叫停。
            with contextlib.suppress(Exception):
                async with cls._client() as client:
                    await client.stop(session_id)
            await asyncio.to_thread(shutil.rmtree, session_dir, True)
            raise e

        return session_id

    # ------------------------------------------------------------------ 轮询与落库

    @classmethod
    def _snapshot(cls, record: ActionSrdAssessment) -> _SrdRun:
        """
        把 ORM 记录里这条链路要用的几个字段抄成普通值

        **这一步不是多余的**：会话是 `expire_on_commit=True`（`config/database.py` 的默认），
        commit 之后所有 ORM 实例都会失效，再读任何属性都要发一次懒加载 ——
        而懒加载在 async 会话里直接抛 `MissingGreenlet`。下面这条链路要连着提交好几次
        （改状态、写结果树），所以一律只在普通值上走。

        :param record: 评估记录
        :return: 运行态快照
        """
        return _SrdRun(
            assessment_id=record.assessment_id,
            session_id=record.session_id or '',
            user_id=record.user_id,
            run_status=record.run_status or 'pending',
            progress=record.progress or 0,
            error_msg=record.error_msg or '',
        )

    @classmethod
    async def run_state_services(cls, query_db: AsyncSession, session_id: str, user_id: int) -> SrdRunStateModel:
        """
        查询任务状态；跑完顺手把引擎结果落库

        落库放在轮询里而不是 worker 里，是为了让 worker 保持「只认 Redis 不认数据库」——
        它已经为了模型池连了一次库，再让它写业务表就等于把两个系统焊死。
        代价是「用户关掉页面就没人来落库」，由 `list_history_services` 兜底对账。

        :param query_db: orm对象
        :param session_id: 任务id
        :param user_id: 访客用户id（越权保护）
        :return: 任务快照
        """
        record = await SrdDao.get_assessment_by_session(query_db, session_id)
        if not record or record.user_id != user_id:
            raise ServiceException(message='评估任务不存在')
        run = cls._snapshot(record)

        state = await cls._fetch_worker_state(session_id)
        if state is None:
            # Redis 里的任务状态有 TTL；已经落库过的记录不受影响，没落过的就是真过期了
            if run.run_status in ('pending', 'running'):
                run = await cls._mark_failed(query_db, run, '任务状态已过期，请重新提交')
        else:
            run = await cls._sync_run(query_db, run, state)

        return SrdRunStateModel(
            sessionId=run.session_id,
            assessmentId=run.assessment_id,
            runStatus=run.run_status,
            progress=run.progress,
            message=str((state or {}).get('message') or ''),
            errorMsg=run.error_msg,
        )

    @classmethod
    async def _fetch_worker_state(cls, session_id: str) -> dict[str, Any] | None:
        """
        读 worker 的任务状态快照

        :param session_id: 任务id
        :return: 状态字典；任务不存在或已过期时为 None
        """
        try:
            async with cls._client() as client:
                return await client.status(session_id)
        except Exception as e:
            raise ServiceException(message=f'评估任务状态查询失败：{type(e).__name__}') from e

    @classmethod
    async def _commit_values(cls, query_db: AsyncSession, run: _SrdRun, values: dict[str, Any]) -> _SrdRun:
        """
        更新评估记录并返回改过的快照

        :param query_db: orm对象
        :param run: 运行态快照
        :param values: 列名到值的映射
        :return: 更新后的快照
        """
        try:
            await SrdDao.edit_assessment_dao(query_db, run.assessment_id, values)
            await query_db.commit()
        except Exception:
            await query_db.rollback()
            raise

        return replace(
            run,
            run_status=str(values.get('run_status', run.run_status)),
            progress=int(values.get('progress', run.progress)),
            error_msg=str(values.get('error_msg', run.error_msg)),
        )

    @classmethod
    async def _mark_failed(cls, query_db: AsyncSession, run: _SrdRun, error: str) -> _SrdRun:
        """
        把记录标记为失败

        :param query_db: orm对象
        :param run: 运行态快照
        :param error: 失败原因
        :return: 更新后的快照
        """
        return await cls._commit_values(
            query_db, run, {'run_status': 'failed', 'error_msg': error[:500], 'finish_time': datetime.now()}
        )

    @classmethod
    async def _sync_run(cls, query_db: AsyncSession, run: _SrdRun, state: dict[str, Any]) -> _SrdRun:
        """
        把 worker 的状态同步进库；首次看到 completed 时把整棵结果树写进来

        已经是 completed 的记录直接跳过 —— 前端会一直轮询到拿着结果离开页面，
        没有这道闸就会每 3 秒重写一次 34 条目。

        :param query_db: orm对象
        :param run: 运行态快照
        :param state: worker 状态快照
        :return: 更新后的快照
        """
        if run.run_status == 'completed':
            return run

        status = str(state.get('status') or 'pending')
        current = int(state.get('progress_current') or 0)
        total = int(state.get('progress_total') or 100) or 100
        progress = min(100, round(current / total * 100))

        if status == 'completed':
            summary = state.get('result') if isinstance(state.get('result'), dict) else {}
            done = await cls._persist_result(query_db, run, summary if isinstance(summary, dict) else {})
            await cls._cleanup_inputs(run.session_id)

            return done

        values: dict[str, Any] = {'run_status': status, 'progress': progress}
        if status in ('failed', 'stopped'):
            values['error_msg'] = (str(state.get('error') or '') or ('已停止' if status == 'stopped' else '评估失败'))[
                :500
            ]
            values['finish_time'] = datetime.now()
            await cls._cleanup_inputs(run.session_id)

        return await cls._commit_values(query_db, run, values)

    @classmethod
    async def _cleanup_inputs(cls, session_id: str | None) -> None:
        """
        删掉这次评估的输入 PDF

        任务到终态后没人再读它们，而它们是用户上传的原文，不该无限期留在服务器上。
        删不掉只记日志：清理失败不该让一份跑完的报告落不了库。

        :param session_id: 任务id
        :return:
        """
        if not session_id:
            return
        try:
            await asyncio.to_thread(shutil.rmtree, cls._session_dir(session_id), True)
        except OSError as e:
            logger.warning(f'SRD 输入文件清理失败 {session_id}: {type(e).__name__}: {e}')

    @classmethod
    async def _persist_result(cls, query_db: AsyncSession, run: _SrdRun, summary: dict[str, Any]) -> _SrdRun:
        """
        把引擎结果写进 评估 / 领域 / 分组 / 条目 四张表

        摘要里只有领域级数字与一张 `ratings` 表，34 条目的理由与引用在
        `result.json` 里（摘要的 `files.json` 给了路径）。读不到就判失败而不是
        只落一半 —— 一份没有判定依据的报告，用户会拿它当结论。

        整棵树在**一个事务**里写：中途炸掉会回滚成「还没落库」，下次轮询重来一遍，
        而不是留下半棵只有两个领域的结果树。

        :param query_db: orm对象
        :param run: 运行态快照
        :param summary: worker 摘要
        :return: 更新后的快照
        """
        detail = await cls._load_result_json(summary)
        if detail is None:
            return await cls._mark_failed(
                query_db, run, '评估已完成但读不到结果文件：后端与 worker 需共享文件系统（详见 SrdService 说明）'
            )

        try:
            # 断点续跑的任务可能已经落过一次，先清后写，否则会叠出两套 34 条目
            await SrdDao.clear_result_tree(query_db, run.assessment_id)
            await SrdDao.edit_assessment_dao(query_db, run.assessment_id, cls._assessment_values(detail, summary))
            for d in detail.get('domains') or []:
                domain = await SrdDao.add_domain_dao(
                    query_db, {'assessment_id': run.assessment_id, **cls._domain_values(d)}
                )
                for gi, g in enumerate(d.get('groups') or []):
                    group = await SrdDao.add_group_dao(
                        query_db,
                        {
                            'domain_id': domain.domain_id,
                            'code': str(g.get('code') or '')[:32],
                            'name_zh': str(g.get('name_zh') or '')[:300],
                            'name_en': str(g.get('name_en') or '')[:500],
                            'sort_num': gi,
                        },
                    )
                    await SrdDao.add_items_dao(
                        query_db,
                        [
                            {'group_id': group.group_id, 'sort_num': ii, **cls._item_values(it)}
                            for ii, it in enumerate(g.get('items') or [])
                        ],
                    )
            await query_db.commit()
        except Exception:
            await query_db.rollback()
            raise

        return replace(run, run_status='completed', progress=100, error_msg='')

    @classmethod
    async def _load_result_json(cls, summary: dict[str, Any]) -> dict[str, Any] | None:
        """
        读 worker 落盘的 `result.json`

        :param summary: worker 摘要（`files.json` 是绝对路径）
        :return: 完整结果；读不到则 None
        """
        raw_path = ((summary.get('files') or {}) if isinstance(summary.get('files'), dict) else {}).get('json')
        if not raw_path:
            return None
        path = Path(str(raw_path))
        try:
            text = await asyncio.to_thread(path.read_text, 'utf-8')

            return json.loads(text)
        except (OSError, ValueError) as e:
            logger.error(f'SRD 结果文件读取失败 {path}: {type(e).__name__}: {e}')

            return None

    @classmethod
    def _assessment_values(cls, detail: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
        """
        结果 → 评估表的列值

        :param detail: result.json
        :param summary: worker 摘要（用量与模型信息只有它有）
        :return: 列名到值的映射
        """
        return {
            'run_status': 'completed',
            'progress': 100,
            'error_msg': '',
            'review_a_title_zh': str(detail.get('review_a_title') or '')[:600] or '综述 A',
            'review_b_title_zh': str(detail.get('review_b_title') or '')[:600] or '综述 B',
            'overall_level': detail.get('overall_level'),
            'overall_pct': int(detail.get('overall_pct') or 0),
            'overall_score_sum': int(detail.get('overall_score_sum') or 0),
            'overall_score_max': int(detail.get('overall_score_max') or 0),
            'overall_score_max_full': int(detail.get('overall_score_max_full') or 0),
            'overall_reason_zh': detail.get('overall_reason_zh') or '',
            'overall_reason_en': detail.get('overall_reason_en') or '',
            'provisional': '1' if detail.get('provisional') else '0',
            'unclear_count': int(detail.get('unclear_count') or 0),
            'review_count': int(detail.get('review_count') or 0),
            'model_name': str(detail.get('model') or summary.get('model') or '')[:200],
            'engine_version': str(detail.get('engine_version') or '')[:64],
            'prompt_version': str(detail.get('prompt_version') or '')[:64],
            'criteria_version': str(detail.get('criteria_version') or '')[:64],
            'llm_calls': int(detail.get('llm_calls') or 0),
            'token_in': int(detail.get('token_in') or 0),
            'token_out': int(detail.get('token_out') or 0),
            'seconds': float(summary.get('seconds') or 0),
            'finish_time': datetime.now(),
            'update_time': datetime.now(),
        }

    @classmethod
    def _domain_values(cls, d: dict[str, Any]) -> dict[str, Any]:
        """
        结果 → 领域表的列值

        :param d: result.json 里的一个领域
        :return: 列名到值的映射
        """
        return {
            'seq': int(d.get('seq') or 0),
            # 引擎的名字带「领域 1：」前缀，前台模板自己会拼序号，存进去就成了「领域 1 · 领域 1：研究主题」
            'name_zh': cls._strip_domain_prefix(str(d.get('name_zh') or ''), '：')[:200],
            'name_en': cls._strip_domain_prefix(str(d.get('name_en') or ''), ': ')[:300],
            'is_key': '1' if d.get('is_key') else '0',
            'level': d.get('level'),
            'pct': int(d.get('pct') or 0),
            'score_sum': int(d.get('score_sum') or 0),
            'score_max': int(d.get('score_max') or 0),
            'score_max_full': int(d.get('score_max_full') or 0),
            'dup_count': int(d.get('dup_count') or 0),
            'diff_count': int(d.get('diff_count') or 0),
            'unclear_count': int(d.get('unclear_count') or 0),
            'evidence_sufficient': '0' if d.get('evidence_sufficient') is False else '1',
            'near_boundary': '1' if d.get('near_boundary') else '0',
        }

    @staticmethod
    def _strip_domain_prefix(name: str, sep: str) -> str:
        """
        去掉「领域 1：」/「Domain 1: 」前缀

        :param name: 引擎给的领域名
        :param sep: 分隔符
        :return: 裸名称
        """
        return name.split(sep, 1)[-1].strip() if sep in name else name.strip()

    @classmethod
    def _item_values(cls, it: dict[str, Any]) -> dict[str, Any]:
        """
        结果 → 条目表的列值

        引擎的引用字段是「原文逐字 `cite_a` + 中文翻译 `cite_a_zh`」，而库里是
        `cite_a_zh` / `cite_a_en` 一对双语列。原文既然保持原语言，就放进 `*_en`
        那一格 —— **`cite_*_en` 装的是原语言，不一定是英文**（中文文献就是中文，
        与 `cite_*_zh` 同值）。列名是历史包袱，前台 `pages/srd.vue` 因此不用
        `pick()` 取这两列（那会在中文界面拿到译文），只认 `citeAEn` 这一格。

        :param it: result.json 里的一个条目
        :return: 列名到值的映射
        """
        rating = str(it.get('override_rating') or it.get('rating') or 'unclear')
        if rating not in cls.RATING_SCORE:
            rating = 'unclear'
        reason_zh = str(it.get('override_reason_zh') or it.get('reason_zh') or '')

        return {
            'code': str(it.get('code') or '')[:32],
            'question_zh': it.get('question_zh') or '',
            'question_en': it.get('question_en') or '',
            'rating': rating,
            'score': cls.RATING_SCORE[rating],
            'confidence': str(it.get('confidence') or 'medium')[:16],
            'needs_review': '1' if it.get('needs_review') else '0',
            'review_note': str(it.get('review_note') or '')[:500],
            'evidence_card': it.get('evidence_card') or '',
            'basis_zh': reason_zh,
            'basis_en': it.get('reason_en') or '',
            'cite_a_zh': it.get('cite_a_zh') or '',
            'cite_a_en': it.get('cite_a') or '',
            'cite_b_zh': it.get('cite_b_zh') or '',
            'cite_b_en': it.get('cite_b') or '',
        }

    # ------------------------------------------------------------------ 控制与回看

    @classmethod
    async def stop_run_services(cls, query_db: AsyncSession, session_id: str, user_id: int) -> CrudResponseModel:
        """
        请求停止评估任务

        :param query_db: orm对象
        :param session_id: 任务id
        :param user_id: 访客用户id
        :return: 操作结果
        """
        record = await SrdDao.get_assessment_by_session(query_db, session_id)
        if not record or record.user_id != user_id:
            raise ServiceException(message='评估任务不存在')
        try:
            async with cls._client() as client:
                await client.stop(session_id)
        except Exception as e:
            raise ServiceException(message=f'停止失败：{type(e).__name__}') from e

        return CrudResponseModel(is_success=True, message='已请求停止')

    @classmethod
    async def list_history_services(cls, query_db: AsyncSession, user_id: int) -> list[SrdHistoryModel]:
        """
        我的评估历史

        顺手对账：用户关掉页面后没人再轮询，跑完的任务会一直挂在 running。
        这里对未终结的记录补查一次 worker 状态，把结果补落库。

        对账与取列表分成两趟：对账要提交事务，而提交会让第一趟查出来的 ORM 对象全部失效
        （见 `_snapshot`），所以对账只在快照上做，改完再重新查一次列表。

        :param query_db: orm对象
        :param user_id: 访客用户id
        :return: 历史列表
        """
        pending = [
            cls._snapshot(r)
            for r in await SrdDao.get_user_assessments(query_db, user_id, cls.HISTORY_LIMIT)
            if r.run_status in ('pending', 'running') and r.session_id
        ]
        for run in pending:
            try:
                state = await cls._fetch_worker_state(run.session_id)
                if state is None:
                    await cls._mark_failed(query_db, run, '任务状态已过期，请重新提交')
                    continue
                await cls._sync_run(query_db, run, state)
            except Exception as e:
                # 对账是顺带做的，Redis 抖一下不该让整个历史列表打不开
                logger.warning(f'SRD 历史对账失败 {run.session_id}: {type(e).__name__}: {e}')

        records = await SrdDao.get_user_assessments(query_db, user_id, cls.HISTORY_LIMIT)

        return [
            SrdHistoryModel(
                assessmentId=r.assessment_id,
                sessionId=r.session_id,
                runStatus=r.run_status,
                progress=r.progress,
                errorMsg=r.error_msg,
                reviewATitleZh=r.review_a_title_zh,
                reviewATitleEn=r.review_a_title_en,
                reviewBTitleZh=r.review_b_title_zh,
                reviewBTitleEn=r.review_b_title_en,
                overallLevel=r.overall_level,
                overallPct=r.overall_pct,
                overallScoreSum=r.overall_score_sum,
                overallScoreMax=r.overall_score_max,
                provisional=r.provisional,
                createTime=r.create_time,
                finishTime=r.finish_time,
            )
            for r in records
        ]

    @classmethod
    async def delete_history_services(cls, query_db: AsyncSession, assessment_id: int, user_id: int) -> CrudResponseModel:
        """
        删除一条评估历史（逻辑删除）

        :param query_db: orm对象
        :param assessment_id: 评估id
        :param user_id: 访客用户id
        :return: 操作结果
        """
        record = await SrdDao.get_assessment_by_id(query_db, assessment_id)
        if not record or record.user_id != user_id:
            raise ServiceException(message='评估记录不存在')
        try:
            await SrdDao.soft_delete_assessment_dao(query_db, assessment_id)
            await query_db.commit()
        except Exception:
            await query_db.rollback()
            raise

        return CrudResponseModel(is_success=True, message='删除成功')

    @classmethod
    async def get_assessment_services(
        cls, query_db: AsyncSession, assessment_id: int | None = None, user_id: int | None = None
    ) -> SrdAssessmentModel:
        """
        获取完整的 SRD 评估（评估 -> 领域 -> 分组 -> 条目）

        示例评估（`is_sample='1'`）对所有人可见；真实评估只有本人能看
        —— 里面是用户自己上传的两篇文献的逐条比对，不是公开数据。

        :param query_db: orm对象
        :param assessment_id: 评估id；不传则取示例评估
        :param user_id: 访客用户id，取真实评估时必传
        :return: 评估详情
        """
        assessment = (
            await SrdDao.get_assessment_by_id(query_db, assessment_id)
            if assessment_id
            else await SrdDao.get_sample_assessment(query_db)
        )
        if not assessment:
            raise ServiceException(message='评估记录不存在')
        if assessment.is_sample != '1' and assessment.user_id != user_id:
            # 「不存在」而不是「无权访问」：后者等于告诉调用方这个 id 是真的
            raise ServiceException(message='评估记录不存在')

        domains = await SrdDao.get_domains(query_db, assessment.assessment_id)
        domain_ids = [d.domain_id for d in domains]
        groups = await SrdDao.get_groups(query_db, domain_ids)
        group_ids = [g.group_id for g in groups]
        items = await SrdDao.get_items(query_db, group_ids)

        item_map: dict[int, list[SrdItemModel]] = defaultdict(list)
        for it in items:
            item_map[it.group_id].append(
                SrdItemModel(
                    itemId=it.item_id,
                    code=it.code,
                    questionZh=it.question_zh,
                    questionEn=it.question_en,
                    rating=it.rating,
                    score=it.score,
                    confidence=it.confidence,
                    needsReview=it.needs_review,
                    reviewNote=it.review_note,
                    evidenceCard=it.evidence_card,
                    basisZh=it.basis_zh,
                    basisEn=it.basis_en,
                    citeAZh=it.cite_a_zh,
                    citeAEn=it.cite_a_en,
                    citeBZh=it.cite_b_zh,
                    citeBEn=it.cite_b_en,
                )
            )

        group_map: dict[int, list[SrdGroupModel]] = defaultdict(list)
        for g in groups:
            group_map[g.domain_id].append(
                SrdGroupModel(
                    groupId=g.group_id,
                    code=g.code,
                    nameZh=g.name_zh,
                    nameEn=g.name_en,
                    items=item_map.get(g.group_id, []),
                )
            )

        return SrdAssessmentModel(
            assessmentId=assessment.assessment_id,
            sessionId=assessment.session_id,
            runStatus=assessment.run_status,
            progress=assessment.progress,
            errorMsg=assessment.error_msg,
            fileAName=assessment.file_a_name,
            fileBName=assessment.file_b_name,
            reviewATitleZh=assessment.review_a_title_zh,
            reviewATitleEn=assessment.review_a_title_en,
            reviewBTitleZh=assessment.review_b_title_zh,
            reviewBTitleEn=assessment.review_b_title_en,
            overallLevel=assessment.overall_level,
            overallPct=assessment.overall_pct,
            overallScoreSum=assessment.overall_score_sum,
            overallScoreMax=assessment.overall_score_max,
            overallScoreMaxFull=assessment.overall_score_max_full,
            overallReasonZh=assessment.overall_reason_zh,
            overallReasonEn=assessment.overall_reason_en,
            provisional=assessment.provisional,
            unclearCount=assessment.unclear_count,
            reviewCount=assessment.review_count,
            modelName=assessment.model_name,
            engineVersion=assessment.engine_version,
            llmCalls=assessment.llm_calls,
            seconds=float(assessment.seconds) if assessment.seconds is not None else None,
            createTime=assessment.create_time,
            finishTime=assessment.finish_time,
            isSample=assessment.is_sample,
            domains=[
                SrdDomainModel(
                    domainId=d.domain_id,
                    seq=d.seq,
                    nameZh=d.name_zh,
                    nameEn=d.name_en,
                    isKey=d.is_key,
                    level=d.level,
                    pct=d.pct,
                    scoreSum=d.score_sum,
                    scoreMax=d.score_max,
                    scoreMaxFull=d.score_max_full,
                    dupCount=d.dup_count,
                    diffCount=d.diff_count,
                    unclearCount=d.unclear_count,
                    evidenceSufficient=d.evidence_sufficient,
                    nearBoundary=d.near_boundary,
                    groups=group_map.get(d.domain_id, []),
                )
                for d in domains
            ],
        )

    @classmethod
    async def export_assessment_services(
        cls,
        query_db: AsyncSession,
        assessment_id: int | None = None,
        user_id: int | None = None,
        lang: str = 'zh',
    ) -> bytes:
        """
        把一次 SRD 评估导成 xlsx

        取数复用 `get_assessment_services`，可见性那两道闸（示例公开、真实评估只有本人能看）
        因此不必在这里再判一遍 —— 导出与查看是同一份数据，权限判定分成两处写迟早会分叉。

        排版在 `srd_export_service`：那是纯函数（模型 → 字节），不碰数据库，可离线单测。

        :param query_db: orm对象
        :param assessment_id: 评估id；不传则导出示例评估
        :param user_id: 访客用户id，导出真实评估时必传
        :param lang: 导出语言（zh / en）
        :return: xlsx 文件字节
        """
        assessment = await cls.get_assessment_services(query_db, assessment_id, user_id)

        return build_assessment_xlsx(assessment, 'en' if lang == 'en' else 'zh')


class CollabRequestService:
    """
    协作与专家咨询申请服务层
    """

    @classmethod
    async def submit_request_services(
        cls, query_db: AsyncSession, submit: CollabRequestSubmitModel, source_ip: str
    ) -> CrudResponseModel:
        """
        官网提交协作/咨询申请

        入库字段由服务端组装，不接受调用方传入处理状态等后台字段。

        :param query_db: orm对象
        :param submit: 表单提交对象
        :param source_ip: 来源ip
        :return: 提交结果
        """
        values = {
            'request_type': submit.request_type,
            'applicant': submit.applicant,
            'organization': submit.organization or '',
            'email': str(submit.email),
            'phone': submit.phone or '',
            'topic': submit.topic or '',
            'content': submit.content,
            'source_lang': submit.source_lang,
            'source_ip': source_ip[:128],
            'handle_status': '0',
            'del_flag': '0',
            'create_time': datetime.now(),
        }
        try:
            await CollabRequestDao.add_request_dao(query_db, values)
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='提交成功，我们会在 3–5 个工作日内回复')
        except Exception as e:
            await query_db.rollback()
            raise e

    @classmethod
    async def get_request_list_services(
        cls, query_db: AsyncSession, query_object: CollabRequestPageQueryModel, is_page: bool = False
    ) -> PageModel | list[dict[str, Any]]:
        """
        获取申请列表（后台）

        :param query_db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 申请列表
        """
        return await CollabRequestDao.get_request_list(query_db, query_object, is_page)

    @classmethod
    async def handle_request_services(
        cls, query_db: AsyncSession, request_id: int, handle_status: str, handle_by: str, handle_remark: str
    ) -> CrudResponseModel:
        """
        处理申请（后台）

        :param query_db: orm对象
        :param request_id: 申请id
        :param handle_status: 处理状态
        :param handle_by: 处理人
        :param handle_remark: 处理备注
        :return: 处理结果
        """
        try:
            await CollabRequestDao.edit_request_dao(
                query_db,
                {
                    'request_id': request_id,
                    'handle_status': handle_status,
                    'handle_by': handle_by,
                    'handle_time': datetime.now(),
                    'handle_remark': handle_remark,
                },
            )
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='处理成功')
        except Exception as e:
            await query_db.rollback()
            raise e

    @classmethod
    async def delete_request_services(cls, query_db: AsyncSession, request_ids: str) -> CrudResponseModel:
        """
        删除申请（后台，逻辑删除）

        :param query_db: orm对象
        :param request_ids: 申请id字符串，多个以逗号分隔
        :return: 删除结果
        """
        id_list = [int(i) for i in request_ids.split(',') if i.strip()]
        if not id_list:
            raise ServiceException(message='传入申请id为空')
        try:
            await CollabRequestDao.delete_request_dao(query_db, id_list)
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='删除成功')
        except Exception as e:
            await query_db.rollback()
            raise e


class ReportDraftService:
    """
    报告草稿服务层（报告助手第二步）

    文档 2 要的是「含必填/选填的编辑页 + 一键生成标准化报告初稿 + 关键参数一次定义、
    全文联动」。这里负责草稿的增删改查与合成调度，**合成算法本身在
    `report_compose_service`**（纯函数、离线可单测），本类只做取数与拼装。

    越权保护在 `ReportDraftDao` 的 where 里，本层不重复判 user_id；
    取不到就统一报「草稿不存在」——**不区分「不存在」与「不是你的」**，
    否则拿 id 逐个试就能探出别人有几份草稿。
    """

    #: 单个访客的草稿数上限。一份草稿最多几十条正文，30 份足够一个课题组用，
    #: 同时挡住「脚本无限建草稿」把库撑大
    MAX_DRAFTS_PER_USER = 30
    #: 列表一次最多回多少条
    LIST_LIMIT = 50

    # ------------------------------------------------------------------ 取数

    @classmethod
    async def _items_of(cls, query_db: AsyncSession, guideline_id: int) -> list[dict[str, Any]]:
        """
        取某规范的全部启用条目（已按展示顺序排好）

        :param query_db: orm对象
        :param guideline_id: 规范id
        :return: 条目字典列表（驼峰键）
        """
        result = await GuidelineItemDao.get_item_list(
            query_db, GuidelineItemPageQueryModel(guidelineId=guideline_id), is_page=False, only_published=True
        )

        return list(result) if isinstance(result, list) else []

    @classmethod
    def _to_model(
        cls,
        draft: Any,
        code: str,
        require_map: dict[int, str],
        filled_ids: set[int],
        contents: dict[int, str] | None = None,
    ) -> ReportDraftModel:
        """
        把一份草稿装成出参模型，顺带算完成度

        完成度**现算不落库**：存冗余计数就要在每次保存、每次后台改条目填写要求时同步维护，
        算一遍的成本远低于维护一致性的成本。

        计数只认 `require_map` 里的条目（当前规范下仍启用的那些）：草稿里可能留着
        已被后台停用的条目正文，把它算进「已填」会让完成度虚高，用户按着 100% 去投稿。

        :param draft: 草稿 ORM 对象
        :param code: 规范代号
        :param require_map: 条目id -> require_level（该规范当前启用的全部条目）
        :param filled_ids: 已填写的条目id集合（可能含已下线条目）
        :param contents: 条目id -> 正文；给 None 表示这次不带逐条正文（列表页）
        :return: 草稿模型
        """
        filled = filled_ids & set(require_map)
        required_ids = {item_id for item_id, level in require_map.items() if level == '0'}

        return ReportDraftModel(
            draftId=draft.draft_id,
            guidelineId=draft.guideline_id,
            guidelineCode=code,
            studyTypeKey=draft.study_type_key or '',
            title=draft.title or '',
            items=(
                [ReportDraftItemModel(itemId=item_id, content=text) for item_id, text in sorted(contents.items())]
                if contents is not None
                else []
            ),
            itemTotal=len(require_map),
            filledCount=len(filled),
            requiredTotal=len(required_ids),
            requiredFilled=len(filled & required_ids),
            createTime=draft.create_time,
            updateTime=draft.update_time,
        )

    @classmethod
    async def _load(cls, query_db: AsyncSession, draft_id: int, user_id: int) -> tuple[Any, str, list[dict[str, Any]]]:
        """
        取草稿 + 它所依据的规范代号 + 该规范的条目

        :param query_db: orm对象
        :param draft_id: 草稿id
        :param user_id: 访客用户id
        :return: (草稿对象, 规范代号, 条目列表)
        """
        draft = await ReportDraftDao.get_draft_by_id(query_db, draft_id, user_id)
        if not draft:
            raise ServiceException(message='草稿不存在')
        guideline = await GuidelineDao.get_guideline_detail_by_id(query_db, draft.guideline_id)
        items = await cls._items_of(query_db, draft.guideline_id)

        return draft, (guideline.code if guideline else ''), items

    # ------------------------------------------------------------------ 增删改查

    @classmethod
    async def list_drafts_services(cls, query_db: AsyncSession, user_id: int) -> list[ReportDraftModel]:
        """
        我的草稿列表（不带逐条正文）

        :param query_db: orm对象
        :param user_id: 访客用户id
        :return: 草稿列表
        """
        drafts = await ReportDraftDao.get_draft_list(query_db, user_id, cls.LIST_LIMIT)
        if not drafts:
            return []

        # 规范代号与条目按 guideline_id 只查一次：一个用户的草稿多半集中在一两份规范上，
        # 逐份草稿各查一遍等于把同一条查询跑 N 遍
        codes: dict[int, str] = {}
        require_cache: dict[int, dict[int, str]] = {}
        for gid in {d.guideline_id for d in drafts}:
            guideline = await GuidelineDao.get_guideline_detail_by_id(query_db, gid)
            codes[gid] = guideline.code if guideline else ''
            require_cache[gid] = await ReportDraftDao.get_item_require_map(query_db, gid)

        # 一条查询取回全部草稿的「哪些条目已填」，**不读正文**：列表只需要计数，
        # 而正文是这张表里唯一的大字段（单条上限两万字符 × 几十条 × 最多 30 份草稿）
        filled_map = await ReportDraftDao.get_filled_item_ids(query_db, [d.draft_id for d in drafts], user_id)

        return [
            cls._to_model(
                draft,
                codes[draft.guideline_id],
                require_cache[draft.guideline_id],
                filled_map.get(draft.draft_id, set()),
            )
            for draft in drafts
        ]

    @classmethod
    async def create_draft_services(
        cls, query_db: AsyncSession, create: ReportDraftCreateModel, user_id: int
    ) -> ReportDraftModel:
        """
        新建一份草稿

        :param query_db: orm对象
        :param create: 新建入参
        :param user_id: 访客用户id
        :return: 新建的草稿（带空的逐条正文）
        """
        guideline = await GuidelineDao.get_guideline_by_code(query_db, create.guideline_code)
        if not guideline:
            raise ServiceException(message=f'报告规范 {create.guideline_code} 不存在')

        items = await cls._items_of(query_db, guideline.guideline_id)
        if not items:
            # 与第三步同一道闸：一条条目都没有的规范，建出来的草稿是个空壳
            raise ServiceException(message=f'报告规范 {create.guideline_code} 尚未录入 checklist 条目')

        if await ReportDraftDao.count_drafts(query_db, user_id) >= cls.MAX_DRAFTS_PER_USER:
            raise ServiceException(message=f'草稿数已达上限（{cls.MAX_DRAFTS_PER_USER} 份），请先删除不用的草稿')

        # **commit 之前先把要用的值抄成普通变量**：会话是 expire_on_commit=True，
        # commit 会让所有 ORM 对象的属性失效，下一次读属性触发的是一次懒加载，
        # 而在 async 会话里那会直接抛 MissingGreenlet（CLAUDE.md 里 SRD 那条链路记着同一个坑）。
        # 主键也不例外 —— 连 draft.draft_id 都读不得。
        code = guideline.code
        guideline_id = guideline.guideline_id
        now = datetime.now()
        try:
            draft = await ReportDraftDao.add_draft_dao(
                query_db,
                {
                    'user_id': user_id,
                    'guideline_id': guideline_id,
                    'study_type_key': create.study_type_key,
                    'title': create.title.strip() or f'{code} 报告初稿',
                    'create_by': str(user_id),
                    'create_time': now,
                    'update_by': str(user_id),
                    'update_time': now,
                },
            )
            # add_draft_dao 里已经 flush 过，这时主键已经有值，趁 commit 之前抄下来
            new_draft_id = draft.draft_id
            await query_db.commit()
        except Exception as e:
            await query_db.rollback()
            raise e

        fresh = await ReportDraftDao.get_draft_by_id(query_db, new_draft_id, user_id)
        require_map = {int(it['itemId']): (it.get('requireLevel') or '0') for it in items}

        return cls._to_model(fresh, code, require_map, set(), {})

    #: 导入稿件的大小上限。一篇论文正文常规在几十 KB；10MB 足够带图表，
    #: 再大多半是插了大量图片的 docx —— 图片对条目映射毫无用处，只会拖慢解析
    MAX_IMPORT_BYTES = 10 * 1024 * 1024

    @classmethod
    async def import_manuscript_services(
        cls,
        query_db: AsyncSession,
        user_id: int,
        guideline_code: str,
        study_type_key: str,
        title: str,
        filename: str,
        data: bytes,
        locale: str = 'zh',
    ) -> DraftImportResultModel:
        """
        导入一份已有稿件：建草稿 → 存原稿 → 提交条目映射任务

        ## 这个口补的是哪个洞

        导入此前只在第三步，而第三步只产出**只读**判定：第四步没有草稿条目可写回，
        第五步的数据源是草稿于是整个导不出，下次再来还得重新粘一遍。而「哪些条目没覆盖」
        第三步其实已经算出来了 —— 缺的只是把它落成一份可继续加工的草稿。

        ## 原稿与条目框两份并存

        `source_text` 存整篇原稿，**导出正文以它为准**；条目框只装「从原稿里摘出来的
        对应段落」，是对照与改写的工作面。不这么分的话，导出拼回来的就不是用户写的那篇
        稿子了 —— 一句话常同时答好几条，而讨论、致谢、参考文献不对应任何条目、会凭空消失。

        ## 映射是异步的

        建草稿是同步的（所以立刻有 draftId），回填要等 worker 跑完条目映射。
        复用第三步那套队列与引擎，只是 `purpose='import'` —— 跑完那一下才回填。

        :param query_db: orm对象
        :param user_id: 访客用户id
        :param guideline_code: 规范代号
        :param study_type_key: 第一步判定的研究类型，仅作留档
        :param title: 草稿名称，留空由后端起一个
        :param filename: 原始文件名
        :param data: 文件字节
        :param locale: 判定语言
        :return: 导入回执
        :raises ServiceException: 文件解析失败、规范不存在或无条目、草稿数超限
        """
        from module_action.service.manuscript_parse import (  # noqa: PLC0415
            ManuscriptParseError,
            parse_manuscript,
        )

        limit_mb = cls.MAX_IMPORT_BYTES // 1024 // 1024
        if len(data) > cls.MAX_IMPORT_BYTES:
            raise ServiceException(message=f'文件超过 {limit_mb}MB 上限')

        # 解析放在 CPU 线程里：pymupdf/python-docx 都是同步阻塞的，
        # 一份几十页的 PDF 能占住事件循环好几百毫秒
        try:
            source_text = await asyncio.to_thread(parse_manuscript, filename, data)
        except ManuscriptParseError as e:
            raise ServiceException(message=str(e)) from e

        # 与第三步同一道下限：太短的稿件判不出东西，白跑几十次模型调用
        if len(source_text) < MIN_MANUSCRIPT_CHARS:
            raise ServiceException(
                message=f'从文件里只读到 {len(source_text)} 个字符，不足 {MIN_MANUSCRIPT_CHARS}，请确认这是稿件正文'
            )

        guideline = await GuidelineDao.get_guideline_by_code(query_db, guideline_code)
        if not guideline:
            raise ServiceException(message=f'报告规范 {guideline_code} 不存在')
        code = guideline.code
        guideline_id = guideline.guideline_id

        items = await cls._items_of(query_db, guideline_id)
        if not items:
            raise ServiceException(message=f'报告规范 {code} 尚未录入 checklist 条目')

        if await ReportDraftDao.count_drafts(query_db, user_id) >= cls.MAX_DRAFTS_PER_USER:
            raise ServiceException(message=f'草稿数已达上限（{cls.MAX_DRAFTS_PER_USER} 份），请先删除不用的草稿')

        # 行号口径由引擎定义（空行不占号），这里只是为了在列表里显示「导入 N 行」
        line_count = len(_manuscript_line_map(source_text))
        safe_name = (filename or '')[:255]
        now = datetime.now()
        try:
            draft = await ReportDraftDao.add_draft_dao(
                query_db,
                {
                    'user_id': user_id,
                    'guideline_id': guideline_id,
                    'study_type_key': study_type_key,
                    'title': title.strip() or f'{code} · {Path(safe_name).stem or "导入稿件"}'[:300],
                    'source_text': source_text,
                    'source_name': safe_name,
                    'source_lines': line_count,
                    'create_by': str(user_id),
                    'create_time': now,
                    'update_by': str(user_id),
                    'update_time': now,
                },
            )
            # commit 之后连主键都读不得（expire_on_commit），趁现在抄下来
            new_draft_id = draft.draft_id
            await query_db.commit()
        except Exception:
            await query_db.rollback()
            raise

        # 提交条目映射。**草稿已经建好了**，所以即使这一步失败，用户手上仍有一份存着
        # 原稿的草稿，可以在第三步手动跑一次校验 —— 不至于整个白导
        submit = ChecklistReviewSubmitModel(
            guidelineCode=code, manuscript=source_text, locale=locale, draftId=new_draft_id
        )
        ticket = await ChecklistReviewService.submit_review_services(
            query_db, submit, user_id, purpose='import'
        )

        return DraftImportResultModel(
            draftId=new_draft_id,
            sessionId=ticket.session_id,
            reviewId=ticket.review_id,
            sourceName=safe_name,
            sourceLines=line_count,
            charCount=len(source_text),
        )

    @classmethod
    async def get_draft_services(cls, query_db: AsyncSession, draft_id: int, user_id: int) -> ReportDraftModel:
        """
        取一份草稿详情（带逐条正文）

        :param query_db: orm对象
        :param draft_id: 草稿id
        :param user_id: 访客用户id
        :return: 草稿详情
        """
        draft, code, items = await cls._load(query_db, draft_id, user_id)
        rows = await ReportDraftDao.get_draft_items(query_db, draft_id, user_id)
        require_map = {int(it['itemId']): (it.get('requireLevel') or '0') for it in items}

        # **只回当前仍启用的条目的正文**。管理员停用/删除一条 checklist 条目后，草稿里那条
        # 正文就没有输入框可承载了；照旧回给前端的话，前端会把它原样回传，而保存接口按
        # 「条目必须属于当前规范」判定 —— 于是这份草稿从此每次保存都失败，用户还没有任何
        # 途径把它清掉。库里那行不动（见 replace_draft_items 的 scope_ids），条目恢复启用就回来了
        all_contents = {row.item_id: row.content or '' for row in rows}
        contents = {item_id: text for item_id, text in all_contents.items() if item_id in require_map}
        filled_ids = {item_id for item_id, text in all_contents.items() if text.strip()}

        return cls._to_model(draft, code, require_map, filled_ids, contents)

    @classmethod
    async def save_draft_services(
        cls, query_db: AsyncSession, draft_id: int, save: ReportDraftSaveModel, user_id: int
    ) -> ReportDraftModel:
        """
        保存一份草稿（整体覆盖）

        :param query_db: orm对象
        :param draft_id: 草稿id
        :param save: 保存入参
        :param user_id: 访客用户id
        :return: 保存后的草稿详情
        """
        draft, code, items = await cls._load(query_db, draft_id, user_id)

        # 条目必须属于这份草稿所依据的规范：不校验的话，随手改个 item_id 就能往
        # 别的规范的条目上写内容，合成时永远取不出来，表现成「保存成功但内容丢了」
        valid_ids = {int(it['itemId']) for it in items}
        contents = {it.item_id: it.content for it in save.items}
        stray = sorted(set(contents) - valid_ids)
        if stray:
            raise ServiceException(message=f'条目 {stray[:5]} 不属于当前报告规范')

        try:
            await ReportDraftDao.edit_draft_dao(
                query_db,
                draft_id,
                user_id,
                {
                    'title': save.title.strip() or draft.title,
                    'update_by': str(user_id),
                    'update_time': datetime.now(),
                },
            )
            # 只覆盖当前规范仍启用的那些条目，草稿里已下线条目的正文原样留着
            await ReportDraftDao.replace_draft_items(query_db, draft_id, user_id, contents, valid_ids)
            await query_db.commit()
        except Exception as e:
            await query_db.rollback()
            raise e

        fresh = await ReportDraftDao.get_draft_by_id(query_db, draft_id, user_id)
        rows = await ReportDraftDao.get_draft_items(query_db, draft_id, user_id)
        require_map = {int(it['itemId']): (it.get('requireLevel') or '0') for it in items}
        filled_ids = {row.item_id for row in rows if (row.content or '').strip()}

        return cls._to_model(fresh, code, require_map, filled_ids, contents)

    @classmethod
    async def delete_draft_services(cls, query_db: AsyncSession, draft_id: int, user_id: int) -> CrudResponseModel:
        """
        删除一份草稿（逻辑删除，条目正文物理删）

        :param query_db: orm对象
        :param draft_id: 草稿id
        :param user_id: 访客用户id
        :return: 删除结果
        """
        draft = await ReportDraftDao.get_draft_by_id(query_db, draft_id, user_id)
        if not draft:
            raise ServiceException(message='草稿不存在')
        try:
            await ReportDraftDao.delete_draft_dao(query_db, draft_id, user_id)
            # 校验记录不跟着删，只摘掉 draft_id：014 起每条记录自带稿件快照，
            # 它是一条能独立回看的历史，跟着草稿删等于用户没要求过的数据丢失
            await ReportReviewDao.detach_reviews_of_draft_dao(query_db, draft_id)
            await query_db.commit()

            return CrudResponseModel(is_success=True, message='删除成功')
        except Exception as e:
            await query_db.rollback()
            raise e

    # ------------------------------------------------------------------ 合成初稿

    @classmethod
    async def compose_draft_services(
        cls, query_db: AsyncSession, draft_id: int, user_id: int, locale: str = 'zh'
    ) -> ReportDraftComposeModel:
        """
        把一份草稿合成为报告初稿正文

        :param query_db: orm对象
        :param draft_id: 草稿id
        :param user_id: 访客用户id
        :param locale: 输出语言（zh / en）
        :return: 合成结果
        """
        draft, _code, items = await cls._load(query_db, draft_id, user_id)
        rows = await ReportDraftDao.get_draft_items(query_db, draft_id, user_id)
        contents = {row.item_id: row.content or '' for row in rows}

        lang = 'en' if locale == 'en' else 'zh'
        # 已被后台停用/删除的条目，它的正文仍是用户写的东西 —— 合成时不能因为「没有对应条目」
        # 就静默丢掉，那会让用户拿到一份看起来完整、实际少了几段的初稿。挪到末尾单独成节
        valid_ids = {int(it['itemId']) for it in items}
        orphan_texts = [
            text.strip() for item_id, text in sorted(contents.items()) if item_id not in valid_ids and text.strip()
        ]

        # 一条正文都没有 —— 合出来只会是一串「待补充」，
        # 送去第三步等于让模型对着一份空稿判几十条「未报告」，白烧一次调用
        if not any((text or '').strip() for text in contents.values()):
            raise ServiceException(message='草稿还没有任何内容，请先填写至少一条')

        # 条目要求原文（contentZh/En）**不往下传**：合成层拿不到它，就不可能把它写进稿件，
        # 见 `report_compose_service` 的模块 docstring
        compose_items = [
            ComposeItem(
                item_id=int(it['itemId']),
                domain=(it.get('domainEn') if lang == 'en' else it.get('domainZh')) or '',
                item_no=(it.get('itemNoEn') if lang == 'en' else it.get('itemNoZh')) or '',
                require_level=(it.get('requireLevel') or '0'),
            )
            for it in items
        ]
        result = compose_draft_text(draft.title or '', compose_items, contents, lang, orphan_texts)

        return ReportDraftComposeModel(
            draftId=draft_id,
            text=result.text,
            charCount=result.char_count,
            missingRequired=result.missing_required,
        )


    @classmethod
    async def export_draft_services(
        cls, query_db: AsyncSession, draft_id: int, user_id: int, fmt: str = 'docx', locale: str = 'zh'
    ) -> tuple[bytes, str, str, str]:
        """
        导出一份草稿（第五步）

        **数据源是业务库，不是第二步合成的那份文本** —— 那是个瞬时产物，用户可能压根没点过
        「生成初稿」。三种格式回答三个不同的问题，见 `report_export_service` 的模块 docstring。

        判定列（第三步的校验结果）取最近一次；没跑过校验就整列留空，不报错 ——
        导出不该被「还没校验」挡住。

        :param query_db: orm对象
        :param draft_id: 草稿id
        :param user_id: 访客用户id
        :param fmt: docx / xlsx / json
        :param locale: 语言（zh / en）
        :return: (文件字节, 文件名, media type, 扩展名)
        :raises ServiceException: 草稿不存在，或格式不认识
        """
        builder = BUILDERS.get(fmt)
        if not builder:
            raise ServiceException(message=f'不支持的导出格式：{fmt}')
        build, ext, media_type = builder

        draft, code, items = await cls._load(query_db, draft_id, user_id)
        title = draft.title or ''
        # 导入来的草稿带着原稿：docx 正文以它为准（见 `ExportDraft.source_text` 的注释）
        source_text = draft.source_text or ''
        rows = await ReportDraftDao.get_draft_items(query_db, draft_id, user_id)
        contents = {r.item_id: (r.content or '') for r in rows}

        # 第三步的判定：有就带上，没有就整列留空。导出不该被「还没校验」挡住
        verdicts: dict[int, str] = {}
        review = await ReportReviewDao.get_latest_review_dao(query_db, draft_id, user_id)
        if review:
            verdicts = {
                r.item_id: r.status
                for r in await ReportReviewDao.get_review_items_dao(query_db, review.review_id)
            }

        lang = 'en' if locale == 'en' else 'zh'

        def pick(item: dict[str, Any], zh_key: str, en_key: str) -> str:
            if lang == 'en':
                return item.get(en_key) or item.get(zh_key) or ''
            return item.get(zh_key) or ''

        export_items = [
            ExportItem(
                item_id=int(it['itemId']),
                item_no=pick(it, 'itemNoZh', 'itemNoEn'),
                domain=pick(it, 'domainZh', 'domainEn'),
                requirement=pick(it, 'contentZh', 'contentEn'),
                require_level=(it.get('requireLevel') or '0'),
                content=contents.get(int(it['itemId']), ''),
                verdict=verdicts.get(int(it['itemId']), ''),
            )
            for it in items
        ]
        payload = build(
            ExportDraft(
                title=title, guideline_code=code, items=tuple(export_items), source_text=source_text
            ),
            lang,
        )

        # 文件名里带草稿名，但**只保留安全字符**：这个值进 Content-Disposition，
        # 用户能自取的字符串里混进换行或引号就能往响应头里注入
        safe = re.sub(r'[^0-9A-Za-z一-鿿_-]+', '_', title).strip('_') or code or 'report'

        return payload, f'{safe[:60]}.{ext}', media_type, ext

class ReportReviewService:
    """
    第四步的工作清单与改写（报告助手 2→3→4→2 这个环的后半段）

    ## 这个类存在的理由

    第四步原先是一屏静态演示，对前三步状态的引用次数是 0 —— 既没有输入也没有输出。
    照文档字面实现（一个关键词框 → AI 续写一段）它**依然**是独立的：不知道你在写哪份稿、
    依据哪份规范、哪几条没写好。文档那句「遵循 STRICTA 条目规范」只有在「你正站在某一条上」
    时才有意义。

    所以第四步改成一张工作清单：输入是第三步对**这份草稿**的判定，输出写回
    `action_report_draft_item`。链路因此闭合成 2（填）→ 3（判）→ 4（改）→ 2（回写）。

    ## 落库不在这里

    014 起判定由 `ChecklistReviewService` 在轮询到终态时落库 —— 这里只**读**最近一次判定。
    此前是前端在拿到结果那一刻另调一个写入口（`POST /report-reviews`，已撤），
    那条路径有两个后果：用户中途刷新就没人来落库，以及外部粘贴的稿件永远进不了库。
    两条写入路径并存必然漂移，所以撤掉一条而不是两条都留。
    """

    @classmethod
    async def get_latest_review_services(
        cls, query_db: AsyncSession, draft_id: int, user_id: int
    ) -> ReportReviewModel:
        """
        取某份草稿最近一次跑完的校验（第四步工作清单的数据源）

        **没有校验过不算错**：返回一个 reviewId 为空的壳，前台据此显示「先去第三步跑一次」。
        报错会让「还没跑过」和「出问题了」长得一模一样。

        **不带 manuscript**：第四步要的是「哪几条待办」，整篇稿件在这里没有用途，
        而它是这条链路上最不该顺手多发一遍的东西。

        :param query_db: orm对象
        :param draft_id: 草稿id
        :param user_id: 访客用户id
        :return: 校验记录；没跑过时 reviewId 为 None
        """
        review = await ReportReviewDao.get_latest_review_dao(query_db, draft_id, user_id)
        if not review:
            return ReportReviewModel(draftId=draft_id)
        rows = await ReportReviewDao.get_review_items_dao(query_db, review.review_id)

        return ReportReviewModel(
            reviewId=review.review_id,
            draftId=review.draft_id,
            guidelineId=review.guideline_id,
            guidelineCode=review.guideline_code or '',
            runStatus=review.run_status or 'completed',
            reported=review.reported or 0,
            vague=review.vague or 0,
            missing=review.missing or 0,
            completeness=review.completeness or 0,
            itemTotal=review.item_total or 0,
            lineCount=review.line_count or 0,
            verdicts=[
                ReviewVerdictModel(
                    itemId=r.item_id,
                    status=r.status,
                    reason=r.reason or '',
                    evidence=r.evidence or '',
                    lines=r.lines or '',
                )
                for r in rows
            ],
            createTime=review.create_time,
            finishTime=review.finish_time,
        )

    @staticmethod
    def _pick_item(item: dict[str, Any], lang: str) -> dict[str, str]:
        """
        按语言取条目的四个文案字段

        :param item: 条目字典（驼峰键）
        :param lang: 语言（zh / en）
        :return: item_no / domain / requirement / extension
        """

        def pick(zh_key: str, en_key: str) -> str:
            if lang == 'en':
                return item.get(en_key) or item.get(zh_key) or ''
            return item.get(zh_key) or ''

        return {
            'item_no': pick('itemNoZh', 'itemNoEn'),
            'domain': pick('domainZh', 'domainEn'),
            'requirement': pick('contentZh', 'contentEn'),
            'extension': pick('extensionZh', 'extensionEn'),
        }

    @classmethod
    async def _context_of(cls, query_db: AsyncSession, req: AssistRequestModel, user_id: int, lang: str) -> AssistContext:
        """
        为一次改写攒齐上下文

        **两条路，由 `draft_id` 分**：

        · **草稿路径**（带 draft_id + item_id）：条目要求 + 用户已写的正文 + 第三步对这一条
          的判定，全部从库里取，改完能写回。
        · **独立路径**（不带 draft_id）：正文用前端传来的 `text`，规范上下文取自
          `guideline_code`（第一步的结果），`item_id` 可选 —— 给了就连条目要求一起带上。
          这是文档第 4 节的字面形态，也是唯一一条已写好稿、没有草稿的用户走得通的路。

        **条目要求永远从库里取，两条路都一样**：前端能传的话，它就成了一个可伪造的
        任意指令注入口。能由前端给的只有用户自己手打的 `text`。

        :param query_db: orm对象
        :param req: 改写请求
        :param user_id: 访客用户id
        :param lang: 语言（zh / en）
        :return: 改写上下文
        :raises ServiceException: 草稿不存在，或条目不属于对应的规范
        """
        if req.draft_id is not None and req.item_id is not None:
            return await cls._context_from_draft(query_db, req.draft_id, req.item_id, user_id, lang)

        return await cls._context_standalone(query_db, req, lang)

    @classmethod
    async def _context_from_draft(
        cls, query_db: AsyncSession, draft_id: int, item_id: int, user_id: int, lang: str
    ) -> AssistContext:
        """
        草稿路径的上下文：条目要求 + 用户已写的正文 + 第三步对这一条的判定

        :param query_db: orm对象
        :param draft_id: 草稿id
        :param item_id: 条目id
        :param user_id: 访客用户id
        :param lang: 语言（zh / en）
        :return: 改写上下文
        :raises ServiceException: 草稿不存在，或条目不属于这份草稿所依据的规范
        """
        _draft, code, items = await ReportDraftService._load(query_db, draft_id, user_id)
        item = next((it for it in items if int(it['itemId']) == item_id), None)
        if item is None:
            raise ServiceException(message='该条目不属于当前报告规范')

        rows = await ReportDraftDao.get_draft_items(query_db, draft_id, user_id)
        current = next((r.content or '' for r in rows if r.item_id == item_id), '')

        verdict, reason = '', ''
        review = await ReportReviewDao.get_latest_review_dao(query_db, draft_id, user_id)
        if review:
            judged = await ReportReviewDao.get_review_items_dao(query_db, review.review_id)
            hit = next((r for r in judged if r.item_id == item_id), None)
            if hit:
                verdict, reason = hit.status, (hit.reason or '')

        return AssistContext(
            guideline_code=code,
            current_text=current,
            verdict=verdict,
            verdict_reason=reason,
            **cls._pick_item(item, lang),
        )

    @classmethod
    async def _context_standalone(
        cls, query_db: AsyncSession, req: AssistRequestModel, lang: str
    ) -> AssistContext:
        """
        独立路径的上下文：用户自己给的正文 +（可选的）规范与条目

        规范代号只做展示与「按哪份规范写」的指令，**查不到也不报错** —— 用户没走第一步
        就直接来第四步是完全合理的用法，这一步本来就该能单独用。

        :param query_db: orm对象
        :param req: 改写请求
        :param lang: 语言（zh / en）
        :return: 改写上下文
        :raises ServiceException: 指定了 item_id 但它不属于这份规范
        """
        code, fields = '', {}
        if req.guideline_code:
            guideline = await GuidelineDao.get_guideline_by_code(query_db, req.guideline_code)
            if guideline:
                code = guideline.code
                if req.item_id is not None:
                    items = await ReportDraftService._items_of(query_db, guideline.guideline_id)
                    item = next((it for it in items if int(it['itemId']) == req.item_id), None)
                    if item is None:
                        raise ServiceException(message='该条目不属于当前报告规范')
                    fields = cls._pick_item(item, lang)

        return AssistContext(guideline_code=code, current_text=req.text, **fields)

    @classmethod
    async def assist_services(
        cls, query_db: AsyncSession, req: AssistRequestModel, user_id: int, locale: str = 'zh'
    ) -> AssistResultModel:
        """
        跑一次续写 / 润色 / 中译英

        **结果不落库**：由用户在第四步看过之后显式「采用」，才走 `apply_services`。
        直接写回等于让模型改用户的稿子而不问一声。

        :param query_db: orm对象
        :param req: 改写请求
        :param user_id: 访客用户id
        :param locale: 界面语言
        :return: 改写结果
        :raises ServiceException: 上下文取不到、该动作缺少必要输入、或池里模型全挂
        """
        lang = 'en' if locale == 'en' else 'zh'
        ctx = await cls._context_of(query_db, req, user_id, lang)
        from_draft = req.draft_id is not None

        # 润色与翻译都是改写已有内容，没有输入就没有输出 —— 在调模型之前挡下来，
        # 省掉一次白花钱的调用，也免得模型对着空串自由发挥。
        # **两条路径的提示要分开说**：草稿模式该去第二步填，独立模式是「把要改的文字贴进来」，
        # 给独立模式的用户一句「请先在第二步填写」等于把他支去一个他根本用不上的步骤
        if needs_current_text(req.action) and not ctx.current_text.strip():
            raise ServiceException(
                message='这一条还没有正文，请先填写，或先用「续写」' if from_draft else '请先把要改的正文贴进来'
            )
        if req.action == 'continue' and not req.keywords.strip() and not ctx.current_text.strip():
            raise ServiceException(
                message='请先给几个关键词，或先在第二步写一句' if from_draft else '请先给几个关键词'
            )
        # 一条 checklist 应答不该长过这个数，超了多半是把整篇稿子粘进来了。
        # 独立模式下入参已由 VO 的 max_length 挡过一道，这里兜的是草稿里存量的超长正文
        if len(ctx.current_text) > MAX_ASSIST_INPUT_CHARS:
            raise ServiceException(message=f'正文超过 {MAX_ASSIST_INPUT_CHARS} 字符，请先拆分')

        text, label = await AiAssistService.rewrite(
            query_db, action=req.action, ctx=ctx, style=req.style, keywords=req.keywords, locale=lang
        )

        return AssistResultModel(itemId=req.item_id or 0, action=req.action, text=text, modelLabel=label)

    @classmethod
    async def apply_services(cls, query_db: AsyncSession, apply: AssistApplyModel, user_id: int) -> ReportDraftModel:
        """
        把第四步的改写结果写回第二步的草稿条目 —— 这一步让 2→3→4→2 真正闭合

        走的是**单条覆盖**：第四步一次只改一条，套用第二步的整体覆盖语义
        （`ReportDraftSaveModel`）会把没带上的其余条目全部清空。所以这里先把现有正文
        整份读回来，只换掉这一条，再整份写回去。

        :param query_db: orm对象
        :param apply: 写回入参
        :param user_id: 访客用户id
        :return: 写回后的草稿详情
        :raises ServiceException: 草稿不存在，或条目不属于这份草稿所依据的规范
        """
        _draft, code, items = await ReportDraftService._load(query_db, apply.draft_id, user_id)
        valid_ids = {int(it['itemId']) for it in items}
        if apply.item_id not in valid_ids:
            raise ServiceException(message='该条目不属于当前报告规范')

        rows = await ReportDraftDao.get_draft_items(query_db, apply.draft_id, user_id)
        contents = {r.item_id: (r.content or '') for r in rows}
        contents[apply.item_id] = apply.content

        try:
            await ReportDraftDao.replace_draft_items(query_db, apply.draft_id, user_id, contents, valid_ids)
            # 留痕由服务端在这里自己记，**不依赖前端调用** —— 这是整套工具里真正的
            # 「关键数据修改」（模型生成的文字进了用户的稿子），前端不调这条就没了
            await ReportTrailService.record(
                query_db,
                user_id,
                'applied',
                draft_id=apply.draft_id,
                guideline_code=code,
                item_id=apply.item_id,
                char_count=len(apply.content),
            )
            await query_db.commit()
        except Exception as e:
            await query_db.rollback()
            raise e

        fresh = await ReportDraftDao.get_draft_by_id(query_db, apply.draft_id, user_id)
        after = await ReportDraftDao.get_draft_items(query_db, apply.draft_id, user_id)
        require_map = {int(it['itemId']): (it.get('requireLevel') or '0') for it in items}
        filled_ids = {r.item_id for r in after if (r.content or '').strip()}

        return ReportDraftService._to_model(
            fresh, code, require_map, filled_ids, {r.item_id: (r.content or '') for r in after}
        )


class ReportTrailService:
    """
    报告助手操作留痕（文档 3.4「校验过程保留操作日志，确保关键数据修改有迹可循」）

    ## 只记事件元数据，不记稿件内容

    第三步对用户的承诺是「稿件只在校验期间流转，不会入库」。留痕若存渲染好的句子，
    句子里迟早会混进正文片段，承诺就绕过去了。所以入参**除 `note` 外全是数字与枚举**，
    人读的那句话由前端按 i18n 渲染。`note` 仅供系统诊断，VO 限长 300 字符。

    ## 最该留痕的其实是第四步的写回

    「关键数据修改」在这套工具里最字面的落点是 `event=applied` —— 模型生成的文字被写回
    `action_report_draft_item`。一篇稿子里哪几段来自模型、什么时候被采纳的，
    是投稿时被问起「AI 参与了多少」时唯一能拿出来的答案。所以那条留痕**由服务端在写回时
    自己记**（见 `ReportReviewService.apply_services`），不依赖前端调用 —— 前端不调，
    这条最重要的记录就没了。
    """

    @classmethod
    async def add_trail_services(cls, query_db: AsyncSession, add: TrailAddModel, user_id: int) -> TrailModel:
        """
        追加一条留痕

        :param query_db: orm对象
        :param add: 入参
        :param user_id: 操作人
        :return: 落库后的留痕
        """
        trail = ActionReportTrail(
            user_id=user_id,
            draft_id=add.draft_id,
            guideline_code=add.guideline_code or '',
            event=add.event,
            actor=add.actor or '',
            item_id=add.item_id,
            total=add.total,
            reported=add.reported,
            vague=add.vague,
            missing=add.missing,
            completeness=add.completeness,
            char_count=add.char_count,
            note=add.note or '',
            create_time=datetime.now(),
        )
        try:
            await ReportTrailDao.add_trail_dao(query_db, trail)
            # 会话是 expire_on_commit=True：commit 之后再读 ORM 属性（**包括主键**）
            # 会触发懒加载，在 async 会话里直接抛 MissingGreenlet。DAO 里已经 flush 过，
            # 主键这会儿就有了，所以先把出参装好、再提交（实跑时踩到过）
            result = cls._to_model(trail)
            await query_db.commit()
        except Exception as e:
            await query_db.rollback()
            raise e

        return result

    @classmethod
    async def record(cls, query_db: AsyncSession, user_id: int, event: str, **fields: Any) -> None:
        """
        服务端内部留痕（不经接口）。**失败不抛** —— 留痕是旁路，不该把主流程带崩。

        :param query_db: orm对象
        :param user_id: 操作人
        :param event: 事件类型
        :param fields: 其余字段
        """
        try:
            trail = ActionReportTrail(user_id=user_id, event=event, create_time=datetime.now(), **fields)
            await ReportTrailDao.add_trail_dao(query_db, trail)
        except Exception:
            logger.warning('留痕失败（已忽略）: event=%s user=%s', event, user_id)

    @classmethod
    async def get_trail_list_services(
        cls, query_db: AsyncSession, user_id: int, draft_id: int | None = None
    ) -> list[TrailModel]:
        """
        取留痕列表（最近的在前）

        :param query_db: orm对象
        :param user_id: 操作人
        :param draft_id: 只看某份草稿；None 表示全部
        :return: 留痕列表
        """
        rows = await ReportTrailDao.get_trail_list_dao(query_db, user_id, draft_id, MAX_TRAIL_ROWS)

        return [cls._to_model(r) for r in rows]

    @classmethod
    def _to_model(cls, row: Any) -> TrailModel:
        """ORM 行 → 出参模型"""
        return TrailModel(
            trailId=row.trail_id,
            draftId=row.draft_id,
            guidelineCode=row.guideline_code or '',
            event=row.event,
            actor=row.actor or '',
            itemId=row.item_id,
            total=row.total,
            reported=row.reported,
            vague=row.vague,
            missing=row.missing,
            completeness=row.completeness,
            charCount=row.char_count,
            note=row.note or '',
            createTime=row.create_time,
        )
