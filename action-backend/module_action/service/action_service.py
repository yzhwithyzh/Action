from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.vo import CrudResponseModel, PageModel
from exceptions.exception import ServiceException
from module_action.dao.action_dao import (
    CollabRequestDao,
    GuidelineDao,
    GuidelineItemDao,
    ImplementationDao,
    NewsDao,
    SrdDao,
    StudyTypeDao,
    TeamMemberDao,
)
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
    GuidelineItemModel,
    GuidelineItemPageQueryModel,
    GuidelineModel,
    GuidelinePageQueryModel,
    NewsModel,
    NewsPageQueryModel,
    ReaimDimensionModel,
    SrdAssessmentModel,
    SrdDomainModel,
    SrdGroupModel,
    SrdItemModel,
    StudyTypeModel,
    StudyTypeStatModel,
    TeamMemberModel,
    TeamMemberPageQueryModel,
)
from utils.common_util import CamelCaseUtil


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
    async def add_guideline_services(cls, query_db: AsyncSession, page_object: GuidelineModel) -> CrudResponseModel:
        """
        新增报告规范

        :param query_db: orm对象
        :param page_object: 规范对象
        :return: 新增结果
        """
        if await GuidelineDao.get_guideline_by_code(query_db, page_object.code):
            raise ServiceException(message=f'新增失败，规范代号 {page_object.code} 已存在')
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
        try:
            await GuidelineDao.edit_guideline_dao(query_db, page_object.model_dump(exclude_unset=True))
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


class SrdService:
    """
    SRD 系统综述重复性评估服务层
    """

    @classmethod
    async def get_assessment_services(
        cls, query_db: AsyncSession, assessment_id: int | None = None
    ) -> SrdAssessmentModel:
        """
        获取完整的 SRD 评估（评估 -> 领域 -> 分组 -> 条目）

        :param query_db: orm对象
        :param assessment_id: 评估id；不传则取示例评估
        :return: 评估详情
        """
        assessment = (
            await SrdDao.get_assessment_by_id(query_db, assessment_id)
            if assessment_id
            else await SrdDao.get_sample_assessment(query_db)
        )
        if not assessment:
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
                    level=it.level,
                    pct=it.pct,
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
            reviewATitleZh=assessment.review_a_title_zh,
            reviewATitleEn=assessment.review_a_title_en,
            reviewBTitleZh=assessment.review_b_title_zh,
            reviewBTitleEn=assessment.review_b_title_en,
            overallLevel=assessment.overall_level,
            overallPct=assessment.overall_pct,
            overallReasonZh=assessment.overall_reason_zh,
            overallReasonEn=assessment.overall_reason_en,
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
                    groups=group_map.get(d.domain_id, []),
                )
                for d in domains
            ],
        )


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
