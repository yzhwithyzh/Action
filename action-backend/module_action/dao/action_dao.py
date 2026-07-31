from datetime import datetime, time
from typing import Any

from sqlalchemy import Row, and_, delete, func, nullslast, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.constant import CommonConstant
from common.vo import PageModel
from module_action.entity.do.action_do import (
    ActionCfirConstruct,
    ActionCfirDomain,
    ActionCfirStrategy,
    ActionCollabRequest,
    ActionEricCategory,
    ActionEricStrategy,
    ActionGuestProfile,
    ActionGuideline,
    ActionNews,
    ActionReaimDimension,
    ActionSrdAssessment,
    ActionSrdDomain,
    ActionSrdGroup,
    ActionSrdItem,
    ActionStudyType,
    ActionStudyTypeGuideline,
    ActionStudyTypeStat,
)
from module_action.entity.vo.action_vo import (
    CollabRequestPageQueryModel,
    GuidelineModel,
    GuidelinePageQueryModel,
    NewsModel,
    NewsPageQueryModel,
)
from module_admin.entity.do.user_do import SysUser
from utils.page_util import PageUtil

# 官网访客在 sys_user 中的用户类型标记，与后台系统用户（'00'）彻底分开
GUEST_USER_TYPE = CommonConstant.GUEST_USER_TYPE


class NewsDao:
    """
    官网新闻动态数据库操作层
    """

    @classmethod
    async def get_news_detail_by_id(cls, db: AsyncSession, news_id: int) -> ActionNews | None:
        """
        根据新闻id获取新闻详情

        :param db: orm对象
        :param news_id: 新闻id
        :return: 新闻信息对象
        """
        return (
            (await db.execute(select(ActionNews).where(ActionNews.news_id == news_id, ActionNews.del_flag == '0')))
            .scalars()
            .first()
        )

    @classmethod
    async def get_news_list(
        cls, db: AsyncSession, query_object: NewsPageQueryModel, is_page: bool = False, only_published: bool = False
    ) -> PageModel | list[dict[str, Any]]:
        """
        根据查询参数获取新闻列表

        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :param only_published: 是否只取已发布（官网公开接口用）
        :return: 新闻列表
        """
        query = (
            select(ActionNews)
            .where(
                ActionNews.del_flag == '0',
                ActionNews.status == '0' if only_published else True,
                ActionNews.title_zh.like(f'%{query_object.title_zh}%') if query_object.title_zh else True,
                ActionNews.category_zh == query_object.category_zh if query_object.category_zh else True,
                # 官网列表页的「ACTION 小组动态 / 领域新闻」两个筛选条走这个字段：
                # 领域新闻一律是外链（is_external='1'），小组动态是站内条目（'0'）。
                ActionNews.is_external == query_object.is_external if query_object.is_external else True,
                ActionNews.status == query_object.status if query_object.status and not only_published else True,
                ActionNews.publish_date.between(
                    datetime.combine(datetime.strptime(query_object.begin_time, '%Y-%m-%d'), time(00, 00, 00)),
                    datetime.combine(datetime.strptime(query_object.end_time, '%Y-%m-%d'), time(23, 59, 59)),
                )
                if query_object.begin_time and query_object.end_time
                else True,
            )
            # publish_date 允许为空（外链类新闻多数没有确切日期）。PG 的 `desc()` 默认
            # NULLS FIRST，会把这些无日期的条目顶到最前，列表页看起来像是倒序排的。
            # 分页开启后这个问题更致命：第 1 页全是无日期外链，有日期的正文被挤到后面。
            # 用 nullslast() 钉死，让「有日期的按日期倒序在前、无日期的垫底」。
            .order_by(
                ActionNews.is_top.desc(),
                nullslast(ActionNews.publish_date.desc()),
                ActionNews.news_id.desc(),
            )
            .distinct()
        )

        return await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

    @classmethod
    async def add_news_dao(cls, db: AsyncSession, news: NewsModel) -> ActionNews:
        """
        新增新闻

        :param db: orm对象
        :param news: 新闻对象
        :return: 新增的新闻对象
        """
        db_news = ActionNews(**news.model_dump(exclude_unset=True))
        db.add(db_news)
        await db.flush()

        return db_news

    @classmethod
    async def edit_news_dao(cls, db: AsyncSession, news: dict) -> None:
        """
        编辑新闻

        :param db: orm对象
        :param news: 需要更新的新闻字典
        :return: None
        """
        await db.execute(update(ActionNews), [news])

    @classmethod
    async def delete_news_dao(cls, db: AsyncSession, news_ids: list[int]) -> None:
        """
        逻辑删除新闻

        :param db: orm对象
        :param news_ids: 新闻id列表
        :return: None
        """
        await db.execute(
            update(ActionNews).where(ActionNews.news_id.in_(news_ids)).values(del_flag='2', update_time=datetime.now())
        )


class GuidelineDao:
    """
    官网报告规范目录数据库操作层
    """

    @classmethod
    async def get_guideline_detail_by_id(cls, db: AsyncSession, guideline_id: int) -> ActionGuideline | None:
        """
        根据规范id获取详情

        :param db: orm对象
        :param guideline_id: 规范id
        :return: 规范信息对象
        """
        return (
            (
                await db.execute(
                    select(ActionGuideline).where(
                        ActionGuideline.guideline_id == guideline_id, ActionGuideline.del_flag == '0'
                    )
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def get_guideline_by_code(cls, db: AsyncSession, code: str) -> ActionGuideline | None:
        """
        根据规范代号获取规范（大小写不敏感，与唯一索引 lower(code) 保持一致）

        :param db: orm对象
        :param code: 规范代号
        :return: 规范信息对象
        """
        return (
            (
                await db.execute(
                    select(ActionGuideline).where(
                        func.lower(ActionGuideline.code) == func.lower(code), ActionGuideline.del_flag == '0'
                    )
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def get_guideline_list(
        cls,
        db: AsyncSession,
        query_object: GuidelinePageQueryModel,
        is_page: bool = False,
        only_published: bool = False,
    ) -> PageModel | list[dict[str, Any]]:
        """
        根据查询参数获取报告规范列表

        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :param only_published: 是否只取启用中的
        :return: 规范列表
        """
        query = (
            select(ActionGuideline)
            .where(
                ActionGuideline.del_flag == '0',
                ActionGuideline.status == '0' if only_published else True,
                ActionGuideline.name_zh.like(f'%{query_object.name_zh}%') if query_object.name_zh else True,
                func.lower(ActionGuideline.code).like(f'%{query_object.code.lower()}%') if query_object.code else True,
                ActionGuideline.study_type == query_object.study_type if query_object.study_type else True,
                ActionGuideline.release_state == query_object.release_state if query_object.release_state else True,
            )
            .order_by(ActionGuideline.sort_num, ActionGuideline.guideline_id)
            .distinct()
        )

        return await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

    @classmethod
    async def add_guideline_dao(cls, db: AsyncSession, guideline: GuidelineModel) -> ActionGuideline:
        """
        新增报告规范

        :param db: orm对象
        :param guideline: 规范对象
        :return: 新增的规范对象
        """
        db_guideline = ActionGuideline(**guideline.model_dump(exclude_unset=True))
        db.add(db_guideline)
        await db.flush()

        return db_guideline

    @classmethod
    async def edit_guideline_dao(cls, db: AsyncSession, guideline: dict) -> None:
        """
        编辑报告规范

        :param db: orm对象
        :param guideline: 需要更新的规范字典
        :return: None
        """
        await db.execute(update(ActionGuideline), [guideline])

    @classmethod
    async def delete_guideline_dao(cls, db: AsyncSession, guideline_ids: list[int]) -> None:
        """
        逻辑删除报告规范

        :param db: orm对象
        :param guideline_ids: 规范id列表
        :return: None
        """
        await db.execute(
            update(ActionGuideline)
            .where(ActionGuideline.guideline_id.in_(guideline_ids))
            .values(del_flag='2', update_time=datetime.now())
        )


class StudyTypeDao:
    """
    官网研究类型数据库操作层
    """

    @classmethod
    async def get_study_type_list(cls, db: AsyncSession) -> list[ActionStudyType]:
        """
        获取启用中的研究类型列表

        :param db: orm对象
        :return: 研究类型列表
        """
        return list(
            (
                await db.execute(
                    select(ActionStudyType)
                    .where(ActionStudyType.status == '0')
                    .order_by(ActionStudyType.sort_num, ActionStudyType.type_id)
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def get_guidelines_by_type_ids(cls, db: AsyncSession, type_ids: list[int]) -> list[ActionStudyTypeGuideline]:
        """
        批量获取研究类型关联的规范代号

        :param db: orm对象
        :param type_ids: 研究类型id列表
        :return: 关联记录列表
        """
        if not type_ids:
            return []

        return list(
            (
                await db.execute(
                    select(ActionStudyTypeGuideline)
                    .where(ActionStudyTypeGuideline.type_id.in_(type_ids))
                    .order_by(ActionStudyTypeGuideline.type_id, ActionStudyTypeGuideline.sort_num)
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def get_stats_by_type_ids(cls, db: AsyncSession, type_ids: list[int]) -> list[ActionStudyTypeStat]:
        """
        批量获取研究类型的统计方法推荐

        :param db: orm对象
        :param type_ids: 研究类型id列表
        :return: 统计推荐记录列表
        """
        if not type_ids:
            return []

        return list(
            (
                await db.execute(
                    select(ActionStudyTypeStat)
                    .where(ActionStudyTypeStat.type_id.in_(type_ids))
                    .order_by(ActionStudyTypeStat.type_id, ActionStudyTypeStat.sort_num)
                )
            )
            .scalars()
            .all()
        )


class ImplementationDao:
    """
    实施科学（CFIR / ERIC / RE-AIM）数据库操作层
    """

    @classmethod
    async def get_cfir_domains(cls, db: AsyncSession) -> list[ActionCfirDomain]:
        """
        获取 CFIR 领域列表

        :param db: orm对象
        :return: 领域列表
        """
        return list(
            (
                await db.execute(
                    select(ActionCfirDomain)
                    .where(ActionCfirDomain.status == '0')
                    .order_by(ActionCfirDomain.seq, ActionCfirDomain.domain_id)
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def get_cfir_constructs(cls, db: AsyncSession, domain_ids: list[int]) -> list[ActionCfirConstruct]:
        """
        批量获取 CFIR 构念

        :param db: orm对象
        :param domain_ids: 领域id列表
        :return: 构念列表
        """
        if not domain_ids:
            return []

        return list(
            (
                await db.execute(
                    select(ActionCfirConstruct)
                    .where(ActionCfirConstruct.domain_id.in_(domain_ids))
                    .order_by(ActionCfirConstruct.domain_id, ActionCfirConstruct.sort_num)
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def get_cfir_strategies(cls, db: AsyncSession, construct_ids: list[int]) -> list[ActionCfirStrategy]:
        """
        批量获取 CFIR 构念对应的策略

        :param db: orm对象
        :param construct_ids: 构念id列表
        :return: 策略列表
        """
        if not construct_ids:
            return []

        return list(
            (
                await db.execute(
                    select(ActionCfirStrategy)
                    .where(ActionCfirStrategy.construct_id.in_(construct_ids))
                    .order_by(ActionCfirStrategy.construct_id, ActionCfirStrategy.sort_num)
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def get_eric_categories(cls, db: AsyncSession) -> list[ActionEricCategory]:
        """
        获取 ERIC 策略分类

        :param db: orm对象
        :return: 分类列表
        """
        return list(
            (await db.execute(select(ActionEricCategory).order_by(ActionEricCategory.sort_num))).scalars().all()
        )

    @classmethod
    async def get_eric_strategies(cls, db: AsyncSession, category: str | None = None) -> list[ActionEricStrategy]:
        """
        获取 ERIC 策略列表

        :param db: orm对象
        :param category: 可选的分类过滤
        :return: 策略列表
        """
        return list(
            (
                await db.execute(
                    select(ActionEricStrategy)
                    .where(
                        ActionEricStrategy.status == '0',
                        ActionEricStrategy.category == category if category and category != 'all' else True,
                    )
                    .order_by(ActionEricStrategy.sort_num, ActionEricStrategy.eric_id)
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def get_reaim_dimensions(cls, db: AsyncSession) -> list[ActionReaimDimension]:
        """
        获取 RE-AIM 维度列表

        :param db: orm对象
        :return: 维度列表
        """
        return list(
            (
                await db.execute(
                    select(ActionReaimDimension)
                    .where(ActionReaimDimension.status == '0')
                    .order_by(ActionReaimDimension.sort_num, ActionReaimDimension.dim_id)
                )
            )
            .scalars()
            .all()
        )


class SrdDao:
    """
    SRD 系统综述重复性评估数据库操作层
    """

    @classmethod
    async def get_sample_assessment(cls, db: AsyncSession) -> ActionSrdAssessment | None:
        """
        获取示例评估（官网演示用，取最新一条 is_sample='1'）

        :param db: orm对象
        :return: 评估对象
        """
        return (
            (
                await db.execute(
                    select(ActionSrdAssessment)
                    .where(ActionSrdAssessment.is_sample == '1', ActionSrdAssessment.del_flag == '0')
                    .order_by(ActionSrdAssessment.assessment_id.desc())
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def get_assessment_by_id(cls, db: AsyncSession, assessment_id: int) -> ActionSrdAssessment | None:
        """
        根据id获取评估

        :param db: orm对象
        :param assessment_id: 评估id
        :return: 评估对象
        """
        return (
            (
                await db.execute(
                    select(ActionSrdAssessment).where(
                        ActionSrdAssessment.assessment_id == assessment_id, ActionSrdAssessment.del_flag == '0'
                    )
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def get_domains(cls, db: AsyncSession, assessment_id: int) -> list[ActionSrdDomain]:
        """
        获取评估下的领域列表

        :param db: orm对象
        :param assessment_id: 评估id
        :return: 领域列表
        """
        return list(
            (
                await db.execute(
                    select(ActionSrdDomain)
                    .where(ActionSrdDomain.assessment_id == assessment_id)
                    .order_by(ActionSrdDomain.seq, ActionSrdDomain.domain_id)
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def get_groups(cls, db: AsyncSession, domain_ids: list[int]) -> list[ActionSrdGroup]:
        """
        批量获取领域下的分组

        :param db: orm对象
        :param domain_ids: 领域id列表
        :return: 分组列表
        """
        if not domain_ids:
            return []

        return list(
            (
                await db.execute(
                    select(ActionSrdGroup)
                    .where(ActionSrdGroup.domain_id.in_(domain_ids))
                    .order_by(ActionSrdGroup.domain_id, ActionSrdGroup.sort_num)
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def get_items(cls, db: AsyncSession, group_ids: list[int]) -> list[ActionSrdItem]:
        """
        批量获取分组下的条目

        :param db: orm对象
        :param group_ids: 分组id列表
        :return: 条目列表
        """
        if not group_ids:
            return []

        return list(
            (
                await db.execute(
                    select(ActionSrdItem)
                    .where(ActionSrdItem.group_id.in_(group_ids))
                    .order_by(ActionSrdItem.group_id, ActionSrdItem.sort_num)
                )
            )
            .scalars()
            .all()
        )


class CollabRequestDao:
    """
    协作与专家咨询申请数据库操作层
    """

    @classmethod
    async def add_request_dao(cls, db: AsyncSession, values: dict[str, Any]) -> ActionCollabRequest:
        """
        新增申请

        :param db: orm对象
        :param values: 申请字段字典
        :return: 新增的申请对象
        """
        db_request = ActionCollabRequest(**values)
        db.add(db_request)
        await db.flush()

        return db_request

    @classmethod
    async def get_request_list(
        cls, db: AsyncSession, query_object: CollabRequestPageQueryModel, is_page: bool = False
    ) -> PageModel | list[dict[str, Any]]:
        """
        根据查询参数获取申请列表

        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 申请列表
        """
        query = (
            select(ActionCollabRequest)
            .where(
                ActionCollabRequest.del_flag == '0',
                ActionCollabRequest.applicant.like(f'%{query_object.applicant}%') if query_object.applicant else True,
                ActionCollabRequest.request_type == query_object.request_type if query_object.request_type else True,
                ActionCollabRequest.handle_status == query_object.handle_status
                if query_object.handle_status
                else True,
                ActionCollabRequest.create_time.between(
                    datetime.combine(datetime.strptime(query_object.begin_time, '%Y-%m-%d'), time(00, 00, 00)),
                    datetime.combine(datetime.strptime(query_object.end_time, '%Y-%m-%d'), time(23, 59, 59)),
                )
                if query_object.begin_time and query_object.end_time
                else True,
            )
            .order_by(ActionCollabRequest.create_time.desc(), ActionCollabRequest.request_id.desc())
            .distinct()
        )

        return await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

    @classmethod
    async def edit_request_dao(cls, db: AsyncSession, values: dict[str, Any]) -> None:
        """
        编辑申请（后台处理）

        :param db: orm对象
        :param values: 需要更新的字段字典
        :return: None
        """
        await db.execute(update(ActionCollabRequest), [values])

    @classmethod
    async def delete_request_dao(cls, db: AsyncSession, request_ids: list[int]) -> None:
        """
        逻辑删除申请

        :param db: orm对象
        :param request_ids: 申请id列表
        :return: None
        """
        await db.execute(
            update(ActionCollabRequest)
            .where(ActionCollabRequest.request_id.in_(request_ids))
            .values(del_flag='2')
        )

    @classmethod
    async def hard_delete_request_dao(cls, db: AsyncSession, request_ids: list[int]) -> None:
        """
        物理删除申请（仅用于清理测试数据）

        :param db: orm对象
        :param request_ids: 申请id列表
        :return: None
        """
        await db.execute(delete(ActionCollabRequest).where(ActionCollabRequest.request_id.in_(request_ids)))


class GuestProfileDao:
    """
    官网访客档案数据库操作层

    访客的主体信息在 sys_user，本层负责「按邮箱/用户id 取访客」以及 action_guest_profile
    的增改。永远不按 user_name 查访客——访客的 user_name 是随机串，只用于占位。
    """

    @classmethod
    def _guest_profile_join_condition(cls) -> Any:
        """
        访客档案与用户表的关联条件

        :return: join条件
        """
        return and_(ActionGuestProfile.user_id == SysUser.user_id, ActionGuestProfile.del_flag == '0')

    @classmethod
    async def get_guest_by_email(cls, db: AsyncSession, email: str) -> Row[tuple[SysUser, ActionGuestProfile]] | None:
        """
        根据邮箱获取访客用户及其档案

        邮箱按 func.lower() 大小写不敏感比对，与 user_dao 的唯一性校验策略保持一致，
        否则 PostgreSQL 下 A@x.com 与 a@x.com 会被当成两个账号。
        档案侧用外连接：档案缺失（历史数据或补偿删除中途）不应导致账号直接登不上。

        :param db: orm对象
        :param email: 邮箱
        :return: 访客用户与档案，不存在时返回None
        """
        return (
            await db.execute(
                select(SysUser, ActionGuestProfile)
                .join(ActionGuestProfile, cls._guest_profile_join_condition(), isouter=True)
                .where(
                    SysUser.del_flag == '0',
                    SysUser.user_type == GUEST_USER_TYPE,
                    func.lower(SysUser.email) == func.lower(email),
                )
                .distinct()
            )
        ).first()

    @classmethod
    async def get_guest_user_by_email(cls, db: AsyncSession, email: str) -> SysUser | None:
        """
        根据邮箱获取访客用户本体（不连档案）

        与 `UserDao.get_user_by_info` 的区别是**多一道 user_type='01' 过滤**，这一道不能省：
        - 注册前的存在性判断若不限访客维度，管理员邮箱同样会被回报「该邮箱已注册」，
          官网匿名接口就成了后台管理员邮箱的探测器；
        - 注册补偿链路若不限访客维度，可能软删掉一个与本次注册毫不相干的账号
          （最坏情况是管理员账号被匿名接口触发封禁）。

        :param db: orm对象
        :param email: 邮箱
        :return: 访客用户，不存在时返回None
        """
        return (
            (
                await db.execute(
                    select(SysUser)
                    .where(
                        SysUser.del_flag == '0',
                        SysUser.user_type == GUEST_USER_TYPE,
                        func.lower(SysUser.email) == func.lower(email),
                    )
                    .distinct()
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def get_guest_by_user_id(
        cls, db: AsyncSession, user_id: int
    ) -> Row[tuple[SysUser, ActionGuestProfile]] | None:
        """
        根据用户id获取访客用户及其档案

        :param db: orm对象
        :param user_id: 用户id
        :return: 访客用户与档案，不存在时返回None
        """
        return (
            await db.execute(
                select(SysUser, ActionGuestProfile)
                .join(ActionGuestProfile, cls._guest_profile_join_condition(), isouter=True)
                .where(
                    SysUser.del_flag == '0',
                    SysUser.user_type == GUEST_USER_TYPE,
                    SysUser.user_id == user_id,
                )
                .distinct()
            )
        ).first()

    @classmethod
    async def get_profile_by_user_id(cls, db: AsyncSession, user_id: int) -> ActionGuestProfile | None:
        """
        根据用户id获取访客档案

        :param db: orm对象
        :param user_id: 用户id
        :return: 访客档案，不存在时返回None
        """
        return (
            (
                await db.execute(
                    select(ActionGuestProfile)
                    .where(ActionGuestProfile.del_flag == '0', ActionGuestProfile.user_id == user_id)
                    .distinct()
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def add_guest_profile_dao(cls, db: AsyncSession, values: dict[str, Any]) -> ActionGuestProfile:
        """
        新增访客档案

        :param db: orm对象
        :param values: 档案字段字典
        :return: 新增的档案对象
        """
        db_profile = ActionGuestProfile(**values)
        db.add(db_profile)
        await db.flush()

        return db_profile
