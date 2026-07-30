from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.vo import CrudResponseModel, PageModel
from exceptions.exception import ServiceException
from module_action.dao.action_dao import (
    CollabRequestDao,
    GuidelineDao,
    ImplementationDao,
    NewsDao,
    SrdDao,
    StudyTypeDao,
)
from module_action.entity.vo.action_vo import (
    CfirConstructModel,
    CfirDomainModel,
    CfirStrategyModel,
    CollabRequestPageQueryModel,
    CollabRequestSubmitModel,
    EricCategoryModel,
    EricStrategyModel,
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
