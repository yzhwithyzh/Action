import asyncio
import contextlib
import json
import shlex
import shutil
import uuid
from collections import defaultdict
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
    ResourceLinkDao,
    SiteTextDao,
    SrdDao,
    StudyTypeDao,
    TeamMemberDao,
)
from module_action.entity.do.action_do import ActionSrdAssessment
from module_action.entity.vo.action_vo import (
    CfirConstructModel,
    CfirDomainModel,
    CfirStrategyModel,
    ChecklistReviewStateModel,
    ChecklistReviewSubmitModel,
    CollabRequestPageQueryModel,
    CollabRequestSubmitModel,
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
    ResourceLinkModel,
    ResourceLinkPageQueryModel,
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
    StudyTypeStatModel,
    TeamMemberModel,
    TeamMemberPageQueryModel,
)
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


class ChecklistReviewService:
    """
    checklist 逐条校验服务层（报告助手第三步）

    这里只做投递与查询，真正干活的是 `tools/checklist_worker_tool` 常驻 worker：
    后端把稿件与规范代号 rpush 进 Redis 队列，worker 取条目、调模型、写状态，
    两个进程互不依赖 —— worker 挂了不影响官网，后端重启也不影响在跑的任务。
    """

    @classmethod
    def _client(cls) -> Any:
        """延迟导入 worker 配置：tools 包依赖 redis 等库，不该拖累未用到该功能的进程启动。"""
        from tools.checklist_worker_tool.config.worker_config import CONFIG  # noqa: PLC0415
        from tools.common.task_client import TaskClient  # noqa: PLC0415

        return TaskClient(CONFIG)

    @classmethod
    async def submit_review_services(
        cls, query_db: AsyncSession, submit: ChecklistReviewSubmitModel, user_id: int | None = None
    ) -> str:
        """
        提交一次校验，返回任务id

        :param query_db: orm对象
        :param submit: 提交模型
        :param user_id: 访客用户id，用于记账
        :return: 任务id（session_id）
        """
        guideline = await GuidelineDao.get_guideline_by_code(query_db, submit.guideline_code)
        if not guideline:
            raise ServiceException(message=f'报告规范 {submit.guideline_code} 不存在')

        # 条目为空时 worker 也会失败，但那要等排队+启动，不如在这里直接回绝
        items = await GuidelineItemDao.get_item_list(
            query_db,
            GuidelineItemPageQueryModel(guidelineId=guideline.guideline_id),
            is_page=False,
            only_published=True,
        )
        if not items:
            raise ServiceException(message=f'报告规范 {submit.guideline_code} 尚未录入 checklist 条目')

        payload = {
            'guideline_code': guideline.code,
            'guideline_id': guideline.guideline_id,
            'manuscript': submit.manuscript,
            'locale': submit.locale,
            'user_id': user_id,
        }
        try:
            async with cls._client() as client:
                return await client.submit(payload)
        except ServiceException:
            raise
        except Exception as e:
            raise ServiceException(message=f'校验任务提交失败，请稍后重试：{type(e).__name__}') from e

    @classmethod
    async def review_state_services(cls, session_id: str) -> ChecklistReviewStateModel:
        """
        查询校验任务状态

        :param session_id: 任务id
        :return: 任务状态
        """
        try:
            async with cls._client() as client:
                state = await client.status(session_id)
        except Exception as e:
            raise ServiceException(message=f'校验任务状态查询失败：{type(e).__name__}') from e
        if not state:
            raise ServiceException(message='校验任务不存在或已过期')

        return ChecklistReviewStateModel(
            sessionId=session_id,
            status=str(state.get('status') or ''),
            progressCurrent=int(state.get('progress_current') or 0),
            progressTotal=int(state.get('progress_total') or 100),
            message=str(state.get('message') or ''),
            error=str(state.get('error') or ''),
            result=state.get('result') if isinstance(state.get('result'), dict) else None,
        )

    @classmethod
    async def stop_review_services(cls, session_id: str) -> CrudResponseModel:
        """
        请求停止校验任务

        :param session_id: 任务id
        :return: 操作结果
        """
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
