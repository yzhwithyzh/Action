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
    ActionGuidelineCategory,
    ActionGuidelineItem,
    ActionNews,
    ActionReaimDimension,
    ActionReportDraft,
    ActionReportDraftItem,
    ActionReportReview,
    ActionReportReviewItem,
    ActionReportTrail,
    ActionResourceLink,
    ActionSiteText,
    ActionSrdAssessment,
    ActionSrdDomain,
    ActionSrdGroup,
    ActionSrdItem,
    ActionStudyType,
    ActionStudyTypeGuideline,
    ActionStudyTypeStat,
    ActionTeamMember,
)
from module_action.entity.vo.action_vo import (
    CollabRequestPageQueryModel,
    GuidelineCategoryModel,
    GuidelineCategoryPageQueryModel,
    GuidelineItemModel,
    GuidelineItemPageQueryModel,
    GuidelineModel,
    GuidelinePageQueryModel,
    NewsModel,
    NewsPageQueryModel,
    ResourceLinkModel,
    ResourceLinkPageQueryModel,
    SiteTextPageQueryModel,
    TeamMemberModel,
    TeamMemberPageQueryModel,
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


class TeamMemberDao:
    """
    官网团队成员数据库操作层
    """

    @classmethod
    async def get_member_detail_by_id(cls, db: AsyncSession, member_id: int) -> ActionTeamMember | None:
        """
        根据成员id获取详情

        :param db: orm对象
        :param member_id: 成员id
        :return: 成员对象
        """
        return (
            (
                await db.execute(
                    select(ActionTeamMember).where(
                        ActionTeamMember.member_id == member_id, ActionTeamMember.del_flag == '0'
                    )
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def get_member_list(
        cls,
        db: AsyncSession,
        query_object: TeamMemberPageQueryModel,
        is_page: bool = False,
        only_published: bool = False,
    ) -> PageModel | list[dict[str, Any]]:
        """
        根据查询参数获取团队成员列表

        排序按「组 → 组内顺序」：group_key 的 'board' 字母序恰好在 'core' 之前，
        与页面上顾问委员会在前、执行团队在后的呈现一致，无需额外的组序字段。

        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :param only_published: 是否只取启用中的
        :return: 成员列表
        """
        conditions = [
            ActionTeamMember.del_flag == '0',
            ActionTeamMember.status == '0' if only_published else True,
            ActionTeamMember.group_key == query_object.group_key if query_object.group_key else True,
            ActionTeamMember.status == query_object.status if query_object.status and not only_published else True,
        ]
        if query_object.keyword:
            kw = f'%{query_object.keyword}%'
            conditions.append(
                ActionTeamMember.name_zh.like(kw)
                | ActionTeamMember.name_en.like(kw)
                | ActionTeamMember.affiliation_zh.like(kw)
                | ActionTeamMember.affiliation_en.like(kw)
                | ActionTeamMember.summary_zh.like(kw)
                | ActionTeamMember.summary_en.like(kw)
            )

        query = (
            select(ActionTeamMember)
            .where(*conditions)
            .order_by(ActionTeamMember.group_key, ActionTeamMember.sort_num, ActionTeamMember.member_id)
            .distinct()
        )

        return await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

    @classmethod
    async def get_max_sort_num(cls, db: AsyncSession, group_key: str) -> int:
        """
        取某组下已有成员的最大 sort_num，供新增成员默认排到组末尾

        :param db: orm对象
        :param group_key: 所属组
        :return: 最大显示顺序，无成员时返回 -1
        """
        result = (
            await db.execute(
                select(func.max(ActionTeamMember.sort_num)).where(
                    ActionTeamMember.group_key == group_key, ActionTeamMember.del_flag == '0'
                )
            )
        ).scalar()

        return -1 if result is None else int(result)

    @classmethod
    async def add_member_dao(cls, db: AsyncSession, member: TeamMemberModel) -> ActionTeamMember:
        """
        新增团队成员

        :param db: orm对象
        :param member: 成员对象
        :return: 新增的成员对象
        """
        db_member = ActionTeamMember(**member.model_dump(exclude_unset=True, exclude={'keyword'}))
        db.add(db_member)
        await db.flush()

        return db_member

    @classmethod
    async def edit_member_dao(cls, db: AsyncSession, member: dict) -> None:
        """
        编辑团队成员

        :param db: orm对象
        :param member: 需要更新的成员字典
        :return: None
        """
        await db.execute(update(ActionTeamMember), [member])

    @classmethod
    async def delete_member_dao(cls, db: AsyncSession, member_ids: list[int]) -> None:
        """
        逻辑删除团队成员

        :param db: orm对象
        :param member_ids: 成员id列表
        :return: None
        """
        await db.execute(
            update(ActionTeamMember)
            .where(ActionTeamMember.member_id.in_(member_ids))
            .values(del_flag='2', update_time=datetime.now())
        )


class ResourceLinkDao:
    """
    官网资源中心链接数据库操作层
    """

    @classmethod
    async def get_link_detail_by_id(cls, db: AsyncSession, link_id: int) -> ActionResourceLink | None:
        """
        根据资源id获取详情

        :param db: orm对象
        :param link_id: 资源id
        :return: 资源对象
        """
        return (
            (
                await db.execute(
                    select(ActionResourceLink).where(
                        ActionResourceLink.link_id == link_id, ActionResourceLink.del_flag == '0'
                    )
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def get_link_list(
        cls,
        db: AsyncSession,
        query_object: ResourceLinkPageQueryModel,
        is_page: bool = False,
        only_published: bool = False,
    ) -> PageModel | list[dict[str, Any]]:
        """
        根据查询参数获取资源中心链接列表

        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :param only_published: 是否只取启用中的
        :return: 资源列表
        """
        conditions = [
            ActionResourceLink.del_flag == '0',
            ActionResourceLink.status == '0' if only_published else True,
            ActionResourceLink.status == query_object.status if query_object.status and not only_published else True,
        ]
        if query_object.keyword:
            kw = f'%{query_object.keyword}%'
            conditions.append(
                ActionResourceLink.name_zh.like(kw)
                | ActionResourceLink.name_en.like(kw)
                | ActionResourceLink.summary_zh.like(kw)
                | ActionResourceLink.summary_en.like(kw)
                | ActionResourceLink.url.like(kw)
            )

        query = (
            select(ActionResourceLink)
            .where(*conditions)
            .order_by(ActionResourceLink.sort_num, ActionResourceLink.link_id)
            .distinct()
        )

        return await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

    @classmethod
    async def get_max_sort_num(cls, db: AsyncSession) -> int:
        """
        取已有资源的最大 sort_num，供新增资源默认排到末尾

        :param db: orm对象
        :return: 最大显示顺序，无记录时返回 -1
        """
        result = (
            await db.execute(select(func.max(ActionResourceLink.sort_num)).where(ActionResourceLink.del_flag == '0'))
        ).scalar()

        return -1 if result is None else int(result)

    @classmethod
    async def add_link_dao(cls, db: AsyncSession, link: ResourceLinkModel) -> ActionResourceLink:
        """
        新增资源中心链接

        :param db: orm对象
        :param link: 资源对象
        :return: 新增的资源对象
        """
        db_link = ActionResourceLink(**link.model_dump(exclude_unset=True, exclude={'keyword'}))
        db.add(db_link)
        await db.flush()

        return db_link

    @classmethod
    async def edit_link_dao(cls, db: AsyncSession, link: dict) -> None:
        """
        编辑资源中心链接

        :param db: orm对象
        :param link: 需要更新的资源字典
        :return: None
        """
        await db.execute(update(ActionResourceLink), [link])

    @classmethod
    async def delete_link_dao(cls, db: AsyncSession, link_ids: list[int]) -> None:
        """
        逻辑删除资源中心链接

        :param db: orm对象
        :param link_ids: 资源id列表
        :return: None
        """
        await db.execute(
            update(ActionResourceLink)
            .where(ActionResourceLink.link_id.in_(link_ids))
            .values(del_flag='2', update_time=datetime.now())
        )


class SiteTextDao:
    """
    官网站点文案数据库操作层

    没有 add / delete：词条由前端代码定义，增删走 `python -m tools.extract_site_texts`
    生成的同步 SQL。后台只改 text_zh / text_en（还原默认也是改这两列）。
    """

    #: 「后台改过」的判定条件。用 is distinct from 而不是 <>，
    #: 否则任一侧为 null 时整个比较是 null，那一行会被静默漏掉。
    CHANGED_CONDITION = (ActionSiteText.text_zh.is_distinct_from(ActionSiteText.default_zh)) | (
        ActionSiteText.text_en.is_distinct_from(ActionSiteText.default_en)
    )

    @classmethod
    async def get_text_detail_by_id(cls, db: AsyncSession, text_id: int) -> ActionSiteText | None:
        """
        根据文案id获取详情

        :param db: orm对象
        :param text_id: 文案id
        :return: 文案对象
        """
        return (
            (
                await db.execute(
                    select(ActionSiteText).where(ActionSiteText.text_id == text_id, ActionSiteText.del_flag == '0')
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def get_text_list(
        cls,
        db: AsyncSession,
        query_object: SiteTextPageQueryModel,
        is_page: bool = False,
    ) -> PageModel | list[dict[str, Any]]:
        """
        根据查询参数获取文案列表

        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 文案列表
        """
        conditions = [
            ActionSiteText.del_flag == '0',
            ActionSiteText.page_key == query_object.page_key if query_object.page_key else True,
            cls.CHANGED_CONDITION if query_object.only_changed else True,
        ]
        if query_object.keyword:
            kw = f'%{query_object.keyword}%'
            conditions.append(
                ActionSiteText.text_key.like(kw) | ActionSiteText.text_zh.like(kw) | ActionSiteText.text_en.like(kw)
            )

        query = (
            select(ActionSiteText)
            .where(*conditions)
            .order_by(ActionSiteText.sort_num, ActionSiteText.text_id)
            .distinct()
        )

        return await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

    @classmethod
    async def get_changed_texts(cls, db: AsyncSession) -> list[ActionSiteText]:
        """
        取所有与默认值不同的文案，供官网公开接口下发覆盖包

        :param db: orm对象
        :return: 被改过的文案列表
        """
        return list(
            (
                await db.execute(
                    select(ActionSiteText)
                    .where(ActionSiteText.del_flag == '0', cls.CHANGED_CONDITION)
                    .order_by(ActionSiteText.sort_num)
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def get_page_groups(cls, db: AsyncSession) -> list[dict[str, Any]]:
        """
        取分组词表（含每组的词条数与被改过的条数），供后台筛选下拉

        :param db: orm对象
        :return: 分组列表
        """
        rows = (
            await db.execute(
                select(
                    ActionSiteText.page_key,
                    func.max(ActionSiteText.page_label).label('page_label'),
                    func.count().label('total'),
                    func.count().filter(cls.CHANGED_CONDITION).label('changed'),
                )
                .where(ActionSiteText.del_flag == '0')
                .group_by(ActionSiteText.page_key)
                .order_by(func.min(ActionSiteText.sort_num))
            )
        ).all()

        # 键用驼峰：`SiteTextGroupModel` 与本模块其余 VO 一样只认别名（alias_generator=to_camel，
        # 没开 populate_by_name），传下划线键会以「字段缺失」报错
        return [
            {'pageKey': row.page_key, 'pageLabel': row.page_label, 'total': row.total, 'changed': row.changed}
            for row in rows
        ]

    @classmethod
    async def edit_text_dao(cls, db: AsyncSession, site_text: dict) -> None:
        """
        编辑文案

        :param db: orm对象
        :param site_text: 需要更新的文案字典
        :return: None
        """
        await db.execute(update(ActionSiteText), [site_text])

    @classmethod
    async def restore_text_dao(cls, db: AsyncSession, text_ids: list[int], operator: str) -> None:
        """
        把指定文案还原成代码里的默认值

        在库里一条 update 做完，不逐条读出来再写回去 —— 「还原全部」可能是几百行。

        :param db: orm对象
        :param text_ids: 文案id列表，空列表表示全部
        :param operator: 操作人
        :return: None
        """
        conditions = [ActionSiteText.del_flag == '0']
        if text_ids:
            conditions.append(ActionSiteText.text_id.in_(text_ids))
        await db.execute(
            update(ActionSiteText)
            .where(*conditions)
            .values(
                text_zh=ActionSiteText.default_zh,
                text_en=ActionSiteText.default_en,
                update_by=operator,
                update_time=datetime.now(),
            )
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
        conditions = [
            ActionGuideline.del_flag == '0',
            ActionGuideline.status == '0' if only_published else True,
            ActionGuideline.name_zh.like(f'%{query_object.name_zh}%') if query_object.name_zh else True,
            func.lower(ActionGuideline.code).like(f'%{query_object.code.lower()}%') if query_object.code else True,
            ActionGuideline.study_type == query_object.study_type if query_object.study_type else True,
            ActionGuideline.release_state == query_object.release_state if query_object.release_state else True,
            ActionGuideline.status == query_object.status if query_object.status and not only_published else True,
        ]
        if query_object.keyword:
            kw = f'%{query_object.keyword}%'
            conditions.append(
                ActionGuideline.code.like(kw)
                | ActionGuideline.name_zh.like(kw)
                | ActionGuideline.name_en.like(kw)
                | ActionGuideline.summary_zh.like(kw)
                | ActionGuideline.summary_en.like(kw)
            )

        query = (
            select(ActionGuideline)
            .where(*conditions)
            .order_by(ActionGuideline.sort_num, ActionGuideline.guideline_id)
            .distinct()
        )

        return await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

    @classmethod
    async def get_max_sort_num(cls, db: AsyncSession) -> int:
        """
        取已有规范的最大 sort_num，供新增规范默认排到目录末尾

        :param db: orm对象
        :return: 最大显示顺序，无记录时返回 -1
        """
        result = (
            await db.execute(select(func.max(ActionGuideline.sort_num)).where(ActionGuideline.del_flag == '0'))
        ).scalar()

        return -1 if result is None else int(result)

    @classmethod
    async def count_by_study_type(cls, db: AsyncSession, study_type: str) -> int:
        """
        统计某个分类下还挂着多少份规范，供删除分类前做占用校验

        :param db: orm对象
        :param study_type: 分类标识
        :return: 规范数量
        """
        result = (
            await db.execute(
                select(func.count(ActionGuideline.guideline_id)).where(
                    ActionGuideline.study_type == study_type, ActionGuideline.del_flag == '0'
                )
            )
        ).scalar()

        return int(result or 0)

    @classmethod
    async def add_guideline_dao(cls, db: AsyncSession, guideline: GuidelineModel) -> ActionGuideline:
        """
        新增报告规范

        :param db: orm对象
        :param guideline: 规范对象
        :return: 新增的规范对象
        """
        db_guideline = ActionGuideline(**guideline.model_dump(exclude_unset=True, exclude={'keyword'}))
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


class GuidelineCategoryDao:
    """
    官网报告规范分类数据库操作层
    """

    @classmethod
    async def get_category_detail_by_id(cls, db: AsyncSession, cat_id: int) -> ActionGuidelineCategory | None:
        """
        根据分类id获取详情

        :param db: orm对象
        :param cat_id: 分类id
        :return: 分类对象
        """
        return (
            (
                await db.execute(
                    select(ActionGuidelineCategory).where(
                        ActionGuidelineCategory.cat_id == cat_id, ActionGuidelineCategory.del_flag == '0'
                    )
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def get_category_by_key(cls, db: AsyncSession, cat_key: str) -> ActionGuidelineCategory | None:
        """
        根据分类标识获取分类

        :param db: orm对象
        :param cat_key: 分类标识
        :return: 分类对象
        """
        return (
            (
                await db.execute(
                    select(ActionGuidelineCategory).where(
                        ActionGuidelineCategory.cat_key == cat_key, ActionGuidelineCategory.del_flag == '0'
                    )
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def get_category_list(
        cls,
        db: AsyncSession,
        query_object: GuidelineCategoryPageQueryModel,
        is_page: bool = False,
        only_published: bool = False,
    ) -> PageModel | list[dict[str, Any]]:
        """
        根据查询参数获取报告规范分类列表

        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :param only_published: 是否只取启用中的
        :return: 分类列表
        """
        conditions = [
            ActionGuidelineCategory.del_flag == '0',
            ActionGuidelineCategory.status == '0' if only_published else True,
            ActionGuidelineCategory.cat_key == query_object.cat_key if query_object.cat_key else True,
            ActionGuidelineCategory.status == query_object.status
            if query_object.status and not only_published
            else True,
        ]
        if query_object.keyword:
            kw = f'%{query_object.keyword}%'
            conditions.append(
                ActionGuidelineCategory.cat_key.like(kw)
                | ActionGuidelineCategory.name_zh.like(kw)
                | ActionGuidelineCategory.name_en.like(kw)
            )

        query = (
            select(ActionGuidelineCategory)
            .where(*conditions)
            .order_by(ActionGuidelineCategory.sort_num, ActionGuidelineCategory.cat_id)
            .distinct()
        )

        return await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

    @classmethod
    async def get_max_sort_num(cls, db: AsyncSession) -> int:
        """
        取已有分类的最大 sort_num，供新增分类默认排到筛选条末尾

        :param db: orm对象
        :return: 最大显示顺序，无记录时返回 -1
        """
        result = (
            await db.execute(
                select(func.max(ActionGuidelineCategory.sort_num)).where(ActionGuidelineCategory.del_flag == '0')
            )
        ).scalar()

        return -1 if result is None else int(result)

    @classmethod
    async def add_category_dao(cls, db: AsyncSession, category: GuidelineCategoryModel) -> ActionGuidelineCategory:
        """
        新增报告规范分类

        :param db: orm对象
        :param category: 分类对象
        :return: 新增的分类对象
        """
        db_category = ActionGuidelineCategory(**category.model_dump(exclude_unset=True, exclude={'keyword'}))
        db.add(db_category)
        await db.flush()

        return db_category

    @classmethod
    async def edit_category_dao(cls, db: AsyncSession, category: dict) -> None:
        """
        编辑报告规范分类

        :param db: orm对象
        :param category: 需要更新的分类字典
        :return: None
        """
        await db.execute(update(ActionGuidelineCategory), [category])

    @classmethod
    async def delete_category_dao(cls, db: AsyncSession, cat_ids: list[int]) -> None:
        """
        逻辑删除报告规范分类

        :param db: orm对象
        :param cat_ids: 分类id列表
        :return: None
        """
        await db.execute(
            update(ActionGuidelineCategory)
            .where(ActionGuidelineCategory.cat_id.in_(cat_ids))
            .values(del_flag='2', update_time=datetime.now())
        )


class GuidelineItemDao:
    """
    报告规范 checklist 条目数据库操作层
    """

    @classmethod
    async def get_item_detail_by_id(cls, db: AsyncSession, item_id: int) -> ActionGuidelineItem | None:
        """
        根据条目id获取详情

        :param db: orm对象
        :param item_id: 条目id
        :return: 条目对象
        """
        return (
            (
                await db.execute(
                    select(ActionGuidelineItem).where(
                        ActionGuidelineItem.item_id == item_id, ActionGuidelineItem.del_flag == '0'
                    )
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def get_item_list(
        cls,
        db: AsyncSession,
        query_object: GuidelineItemPageQueryModel,
        is_page: bool = False,
        only_published: bool = False,
    ) -> PageModel | list[dict[str, Any]]:
        """
        根据查询参数获取规范条目列表

        guideline_code 走 action_guideline 子查询解析成 guideline_id，
        公开接口不必先查一次规范再查条目。

        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :param only_published: 是否只取启用中的
        :return: 条目列表
        """
        conditions = [
            ActionGuidelineItem.del_flag == '0',
            ActionGuidelineItem.status == '0' if only_published else True,
            ActionGuidelineItem.guideline_id == query_object.guideline_id if query_object.guideline_id else True,
            ActionGuidelineItem.part_no == query_object.part_no if query_object.part_no else True,
        ]
        if query_object.guideline_code:
            conditions.append(
                ActionGuidelineItem.guideline_id.in_(
                    select(ActionGuideline.guideline_id).where(
                        func.lower(ActionGuideline.code) == query_object.guideline_code.lower(),
                        ActionGuideline.del_flag == '0',
                    )
                )
            )
        if query_object.keyword:
            kw = f'%{query_object.keyword}%'
            conditions.append(
                ActionGuidelineItem.content_zh.like(kw)
                | ActionGuidelineItem.content_en.like(kw)
                | ActionGuidelineItem.domain_zh.like(kw)
                | ActionGuidelineItem.domain_en.like(kw)
                | ActionGuidelineItem.item_no_zh.like(kw)
            )

        query = (
            select(ActionGuidelineItem)
            .where(*conditions)
            .order_by(ActionGuidelineItem.guideline_id, ActionGuidelineItem.sort_num, ActionGuidelineItem.item_id)
            .distinct()
        )

        return await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

    @classmethod
    async def get_max_sort_num(cls, db: AsyncSession, guideline_id: int) -> int:
        """
        取某规范下已有条目的最大 sort_num，供新增条目默认排到末尾

        :param db: orm对象
        :param guideline_id: 规范id
        :return: 最大显示顺序，无条目时返回 -1
        """
        result = (
            await db.execute(
                select(func.max(ActionGuidelineItem.sort_num)).where(
                    ActionGuidelineItem.guideline_id == guideline_id, ActionGuidelineItem.del_flag == '0'
                )
            )
        ).scalar()

        return -1 if result is None else int(result)

    @classmethod
    async def add_item_dao(cls, db: AsyncSession, item: GuidelineItemModel) -> ActionGuidelineItem:
        """
        新增规范条目

        :param db: orm对象
        :param item: 条目对象
        :return: 新增的条目对象
        """
        db_item = ActionGuidelineItem(**item.model_dump(exclude_unset=True, exclude={'guideline_code', 'keyword'}))
        db.add(db_item)
        await db.flush()

        return db_item

    @classmethod
    async def edit_item_dao(cls, db: AsyncSession, item: dict) -> None:
        """
        编辑规范条目

        :param db: orm对象
        :param item: 需要更新的条目字典
        :return: None
        """
        await db.execute(update(ActionGuidelineItem), [item])

    @classmethod
    async def delete_item_dao(cls, db: AsyncSession, item_ids: list[int]) -> None:
        """
        逻辑删除规范条目

        :param db: orm对象
        :param item_ids: 条目id列表
        :return: None
        """
        await db.execute(
            update(ActionGuidelineItem)
            .where(ActionGuidelineItem.item_id.in_(item_ids))
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
    @classmethod
    async def get_study_type_by_key(cls, db: AsyncSession, type_key: str) -> ActionStudyType | None:
        """
        按标识取一行研究类型（判重用）

        :param db: orm对象
        :param type_key: 类型标识
        :return: 研究类型；没有则 None
        """
        return (
            (await db.execute(select(ActionStudyType).where(ActionStudyType.type_key == type_key)))
            .scalars()
            .first()
        )

    @classmethod
    async def get_study_type_by_id(cls, db: AsyncSession, type_id: int) -> ActionStudyType | None:
        """
        按id取一行研究类型

        :param db: orm对象
        :param type_id: 类型id
        :return: 研究类型；没有则 None
        """
        return (
            (await db.execute(select(ActionStudyType).where(ActionStudyType.type_id == type_id)))
            .scalars()
            .first()
        )

    @classmethod
    async def get_max_type_sort_num(cls, db: AsyncSession) -> int:
        """
        当前最大显示顺序。新类型排到末尾，免得挤到「随机对照试验」前面

        :param db: orm对象
        :return: 最大值；表空时 0
        """
        return (await db.execute(select(func.coalesce(func.max(ActionStudyType.sort_num), 0)))).scalar() or 0

    @classmethod
    async def add_study_type_dao(cls, db: AsyncSession, obj: ActionStudyType) -> ActionStudyType:
        """
        新增一行研究类型

        :param db: orm对象
        :param obj: 研究类型
        :return: 落库后的对象（已 flush，主键可用）
        """
        db.add(obj)
        await db.flush()

        return obj

    @classmethod
    async def edit_study_type_dao(cls, db: AsyncSession, type_id: int, fields: dict[str, Any]) -> None:
        """
        改一行研究类型

        :param db: orm对象
        :param type_id: 类型id
        :param fields: 待改字段
        """
        await db.execute(update(ActionStudyType).where(ActionStudyType.type_id == type_id).values(**fields))

    @classmethod
    async def delete_study_types_dao(cls, db: AsyncSession, type_ids: list[int]) -> None:
        """
        删除研究类型，连同它的两张子表

        **物理删**：这张表没有 del_flag，而且留一行「已删除」的类型在库里毫无用处
        —— 前台问卷是按 type_key 取的，软删只会让同名 key 再也加不回来。

        :param db: orm对象
        :param type_ids: 类型id列表
        """
        if not type_ids:
            return
        await db.execute(delete(ActionStudyTypeGuideline).where(ActionStudyTypeGuideline.type_id.in_(type_ids)))
        await db.execute(delete(ActionStudyTypeStat).where(ActionStudyTypeStat.type_id.in_(type_ids)))
        await db.execute(delete(ActionStudyType).where(ActionStudyType.type_id.in_(type_ids)))

    @classmethod
    async def replace_type_children_dao(
        cls, db: AsyncSession, type_id: int, guidelines: list[str], stats: list[tuple[str, str]]
    ) -> None:
        """
        整体覆盖某个研究类型的两张子表

        先删后插而不是逐条 upsert：保存是**整体覆盖语义**，「这次没带这条」与
        「用户删掉了这条」必须得到同一个结果，先删后插天然如此。顺序按数组下标写进
        `sort_num` —— 前台 chip 的排列顺序就是它。

        :param db: orm对象
        :param type_id: 类型id
        :param guidelines: 规范代号（展示标签）
        :param stats: (中文, 英文) 二元组列表
        """
        await db.execute(delete(ActionStudyTypeGuideline).where(ActionStudyTypeGuideline.type_id == type_id))
        await db.execute(delete(ActionStudyTypeStat).where(ActionStudyTypeStat.type_id == type_id))
        rows: list[Any] = [
            ActionStudyTypeGuideline(type_id=type_id, guideline_code=code, sort_num=i)
            for i, code in enumerate(g.strip() for g in guidelines)
            if code
        ]
        rows += [
            ActionStudyTypeStat(type_id=type_id, text_zh=zh, text_en=en, sort_num=i)
            for i, (zh, en) in enumerate(stats)
            if (zh or '').strip()
        ]
        if rows:
            db.add_all(rows)



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

    # ------------------------------------------------------------------ 任务记录

    @classmethod
    async def get_assessment_by_session(cls, db: AsyncSession, session_id: str) -> ActionSrdAssessment | None:
        """
        根据 worker 任务id获取评估记录

        :param db: orm对象
        :param session_id: worker任务id
        :return: 评估对象
        """
        return (
            (
                await db.execute(
                    select(ActionSrdAssessment).where(
                        ActionSrdAssessment.session_id == session_id, ActionSrdAssessment.del_flag == '0'
                    )
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def add_assessment_dao(cls, db: AsyncSession, values: dict[str, Any]) -> ActionSrdAssessment:
        """
        新增评估记录

        :param db: orm对象
        :param values: 列名到值的映射
        :return: 新增的评估对象
        """
        row = ActionSrdAssessment(**values)
        db.add(row)
        await db.flush()

        return row

    @classmethod
    async def edit_assessment_dao(cls, db: AsyncSession, assessment_id: int, values: dict[str, Any]) -> None:
        """
        更新评估记录

        :param db: orm对象
        :param assessment_id: 评估id
        :param values: 列名到值的映射
        :return:
        """
        await db.execute(
            update(ActionSrdAssessment).where(ActionSrdAssessment.assessment_id == assessment_id).values(**values)
        )

    @classmethod
    async def get_user_assessments(cls, db: AsyncSession, user_id: int, limit: int) -> list[ActionSrdAssessment]:
        """
        获取某访客的评估历史（新的在前）

        :param db: orm对象
        :param user_id: 访客用户id
        :param limit: 返回条数上限
        :return: 评估列表
        """
        return list(
            (
                await db.execute(
                    select(ActionSrdAssessment)
                    .where(ActionSrdAssessment.user_id == user_id, ActionSrdAssessment.del_flag == '0')
                    .order_by(ActionSrdAssessment.assessment_id.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def clear_result_tree(cls, db: AsyncSession, assessment_id: int) -> None:
        """
        清空一次评估已落库的领域/分组/条目

        重跑同一个 session_id（worker 支持断点续跑）时先清后写，否则会叠出两套 34 条目。

        :param db: orm对象
        :param assessment_id: 评估id
        :return:
        """
        domain_ids = list(
            (
                await db.execute(
                    select(ActionSrdDomain.domain_id).where(ActionSrdDomain.assessment_id == assessment_id)
                )
            )
            .scalars()
            .all()
        )
        if domain_ids:
            group_ids = list(
                (await db.execute(select(ActionSrdGroup.group_id).where(ActionSrdGroup.domain_id.in_(domain_ids))))
                .scalars()
                .all()
            )
            if group_ids:
                await db.execute(delete(ActionSrdItem).where(ActionSrdItem.group_id.in_(group_ids)))
            await db.execute(delete(ActionSrdGroup).where(ActionSrdGroup.domain_id.in_(domain_ids)))
            await db.execute(delete(ActionSrdDomain).where(ActionSrdDomain.assessment_id == assessment_id))

    @classmethod
    async def add_domain_dao(cls, db: AsyncSession, values: dict[str, Any]) -> ActionSrdDomain:
        """
        新增领域

        :param db: orm对象
        :param values: 列名到值的映射
        :return: 新增的领域对象
        """
        row = ActionSrdDomain(**values)
        db.add(row)
        await db.flush()

        return row

    @classmethod
    async def add_group_dao(cls, db: AsyncSession, values: dict[str, Any]) -> ActionSrdGroup:
        """
        新增分组

        :param db: orm对象
        :param values: 列名到值的映射
        :return: 新增的分组对象
        """
        row = ActionSrdGroup(**values)
        db.add(row)
        await db.flush()

        return row

    @classmethod
    async def add_items_dao(cls, db: AsyncSession, rows: list[dict[str, Any]]) -> None:
        """
        批量新增条目

        :param db: orm对象
        :param rows: 列名到值的映射列表
        :return:
        """
        if not rows:
            return
        db.add_all([ActionSrdItem(**r) for r in rows])
        await db.flush()

    @classmethod
    async def soft_delete_assessment_dao(cls, db: AsyncSession, assessment_id: int) -> None:
        """
        逻辑删除评估记录（领域/分组/条目保持不动，跟着主记录一起看不见）

        :param db: orm对象
        :param assessment_id: 评估id
        :return:
        """
        await db.execute(
            update(ActionSrdAssessment)
            .where(ActionSrdAssessment.assessment_id == assessment_id)
            .values(del_flag='2', update_time=datetime.now())
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


class ReportDraftDao:
    """
    报告草稿数据库操作层（报告助手第二步）

    **越权保护做在这一层的 where 里**，不靠上层写 if：每个按 draft_id 取数或改数的方法都
    强制带 user_id —— 主表直接比对 `user_id`，从表（条目正文）走 `_owned_draft()` 那个
    子查询限定「这个 draft_id 确实属于这个人」。把判断放上层的问题在于将来多一个调用方
    就多一次遗漏的机会，而这里漏一次等于任何登录用户能读写、删除别人的稿件。
    """

    @classmethod
    def _owned_draft(cls, draft_id: int, user_id: int, include_deleted: bool = False) -> Any:
        """
        「这个 draft_id 属于这个人」的子查询，供条目正文表的语句挂 where 用

        :param draft_id: 草稿id
        :param user_id: 归属访客用户id
        :param include_deleted: 是否连已逻辑删除的草稿一起算（删除流程内部用）
        :return: 可用于 in_() 的子查询
        """
        conditions = [ActionReportDraft.draft_id == draft_id, ActionReportDraft.user_id == user_id]
        if not include_deleted:
            conditions.append(ActionReportDraft.del_flag == '0')

        return select(ActionReportDraft.draft_id).where(*conditions)

    @classmethod
    async def get_draft_by_id(cls, db: AsyncSession, draft_id: int, user_id: int) -> ActionReportDraft | None:
        """
        取一份草稿（限本人）

        :param db: orm对象
        :param draft_id: 草稿id
        :param user_id: 归属访客用户id
        :return: 草稿对象；不存在或不属于该用户时为 None
        """
        return (
            (
                await db.execute(
                    select(ActionReportDraft).where(
                        ActionReportDraft.draft_id == draft_id,
                        ActionReportDraft.user_id == user_id,
                        ActionReportDraft.del_flag == '0',
                    )
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def get_draft_list(cls, db: AsyncSession, user_id: int, limit: int) -> list[ActionReportDraft]:
        """
        我的草稿列表（最近改的在前）

        :param db: orm对象
        :param user_id: 归属访客用户id
        :param limit: 条数上限
        :return: 草稿列表
        """
        return list(
            (
                await db.execute(
                    select(ActionReportDraft)
                    .where(ActionReportDraft.user_id == user_id, ActionReportDraft.del_flag == '0')
                    .order_by(nullslast(ActionReportDraft.update_time.desc()), ActionReportDraft.draft_id.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def count_drafts(cls, db: AsyncSession, user_id: int) -> int:
        """
        统计我的草稿数（用于新建时的配额闸）

        :param db: orm对象
        :param user_id: 归属访客用户id
        :return: 草稿数
        """
        return (
            await db.execute(
                select(func.count())
                .select_from(ActionReportDraft)
                .where(ActionReportDraft.user_id == user_id, ActionReportDraft.del_flag == '0')
            )
        ).scalar() or 0

    @classmethod
    async def add_draft_dao(cls, db: AsyncSession, values: dict[str, Any]) -> ActionReportDraft:
        """
        新增草稿

        :param db: orm对象
        :param values: 草稿字段字典
        :return: 新增的草稿对象
        """
        db_draft = ActionReportDraft(**values)
        db.add(db_draft)
        await db.flush()

        return db_draft

    @classmethod
    async def edit_draft_dao(cls, db: AsyncSession, draft_id: int, user_id: int, values: dict[str, Any]) -> None:
        """
        更新草稿主表字段（限本人）

        :param db: orm对象
        :param draft_id: 草稿id
        :param user_id: 归属访客用户id
        :param values: 待更新字段字典
        """
        await db.execute(
            update(ActionReportDraft)
            .where(ActionReportDraft.draft_id == draft_id, ActionReportDraft.user_id == user_id)
            .values(**values)
        )

    @classmethod
    async def delete_draft_dao(cls, db: AsyncSession, draft_id: int, user_id: int) -> None:
        """
        逻辑删除草稿（限本人）

        条目正文一并物理删除：草稿都不在了，留着几十行孤儿正文没有任何用途，
        而它们是用户的研究内容，留在库里反而是多余的留存。

        :param db: orm对象
        :param draft_id: 草稿id
        :param user_id: 归属访客用户id
        """
        # 先删从表再软删主表：从表那句的归属判断挂在主表的 del_flag='0' 上，
        # 反过来做的话子查询就找不到这份草稿了，正文会留成孤儿行
        await db.execute(
            delete(ActionReportDraftItem).where(
                ActionReportDraftItem.draft_id.in_(cls._owned_draft(draft_id, user_id))
            )
        )
        await db.execute(
            update(ActionReportDraft)
            .where(ActionReportDraft.draft_id == draft_id, ActionReportDraft.user_id == user_id)
            .values(del_flag='2', update_time=datetime.now())
        )

    @classmethod
    async def get_draft_items(cls, db: AsyncSession, draft_id: int, user_id: int) -> list[ActionReportDraftItem]:
        """
        取一份草稿的全部条目正文（限本人）

        :param db: orm对象
        :param draft_id: 草稿id
        :param user_id: 归属访客用户id
        :return: 条目正文列表；草稿不存在或不属于该用户时为空
        """
        return list(
            (
                await db.execute(
                    select(ActionReportDraftItem)
                    .where(ActionReportDraftItem.draft_id.in_(cls._owned_draft(draft_id, user_id)))
                    .order_by(ActionReportDraftItem.item_id)
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def replace_draft_items(
        cls, db: AsyncSession, draft_id: int, user_id: int, contents: dict[int, str], scope_ids: set[int]
    ) -> None:
        """
        整体覆盖一份草稿的条目正文（**只在 scope_ids 这个范围内覆盖**）

        先删后插而不是逐条 upsert：保存是**整体覆盖语义**（见 ReportDraftSaveModel），
        「这次没带这条」与「用户清空了这条」必须得到同一个结果，先删后插天然如此。
        空内容不入库 —— 「没有行」与「填了空串」在完成度统计里是同一回事。

        **`scope_ids` 是这次保存有权改动的条目集合**（当前规范下仍启用的条目）。
        管理员在后台停用或删除一条 checklist 条目之后，用户草稿里那条正文就落在范围之外：
        它不再出现在编辑页上，用户也就无从保留它，如果照旧「全表删光再插回来」，
        下一次自动保存就会把它悄悄抹掉。留着它，条目被重新启用时内容还在。

        :param db: orm对象
        :param draft_id: 草稿id
        :param user_id: 归属访客用户id
        :param contents: 条目id -> 正文
        :param scope_ids: 本次允许覆盖的条目id集合
        """
        owned = (await db.execute(cls._owned_draft(draft_id, user_id))).scalars().first()
        if owned is None:
            return
        if scope_ids:
            await db.execute(
                delete(ActionReportDraftItem).where(
                    ActionReportDraftItem.draft_id == draft_id,
                    ActionReportDraftItem.item_id.in_(scope_ids),
                )
            )
        now = datetime.now()
        rows = [
            ActionReportDraftItem(draft_id=draft_id, item_id=item_id, content=content, update_time=now)
            for item_id, content in contents.items()
            if content.strip() and item_id in scope_ids
        ]
        if rows:
            db.add_all(rows)

    @classmethod
    async def get_filled_item_ids(cls, db: AsyncSession, draft_ids: list[int], user_id: int) -> dict[int, set[int]]:
        """
        批量取「哪些条目已填」，**不读正文**

        列表页只需要完成度计数。正文是这张表里唯一的大字段，为了算个数把 30 份草稿、
        每份几十条、每条最多两万字符全捞进内存，是这个接口最容易被打穿的地方。

        :param db: orm对象
        :param draft_ids: 草稿id列表
        :param user_id: 归属访客用户id
        :return: 草稿id -> 已填条目id集合
        """
        if not draft_ids:
            return {}
        owned = select(ActionReportDraft.draft_id).where(
            ActionReportDraft.draft_id.in_(draft_ids),
            ActionReportDraft.user_id == user_id,
            ActionReportDraft.del_flag == '0',
        )
        rows = (
            await db.execute(
                select(ActionReportDraftItem.draft_id, ActionReportDraftItem.item_id).where(
                    ActionReportDraftItem.draft_id.in_(owned),
                    ActionReportDraftItem.content.isnot(None),
                    func.length(func.trim(ActionReportDraftItem.content)) > 0,
                )
            )
        ).all()
        result: dict[int, set[int]] = {draft_id: set() for draft_id in draft_ids}
        for draft_id, item_id in rows:
            result[draft_id].add(item_id)

        return result

    @classmethod
    async def get_item_require_map(cls, db: AsyncSession, guideline_id: int) -> dict[int, str]:
        """
        取某份规范全部启用条目的「填写要求」

        只取 item_id 与 require_level 两列：完成度统计不需要条目正文，
        而条目正文是这张表里最大的字段。

        :param db: orm对象
        :param guideline_id: 规范id
        :return: 条目id -> require_level（'0'必填 '1'选填）
        """
        rows = (
            await db.execute(
                select(ActionGuidelineItem.item_id, ActionGuidelineItem.require_level).where(
                    ActionGuidelineItem.guideline_id == guideline_id,
                    ActionGuidelineItem.status == '0',
                    ActionGuidelineItem.del_flag == '0',
                )
            )
        ).all()

        return {row[0]: (row[1] or '0') for row in rows}


class ReportReviewDao:
    """
    第三步校验结果数据库操作层

    **越权保护同样做在 where 里**，做法照抄 `ReportDraftDao`：每个方法都把
    「这份记录属于这个用户」写进条件，而不是让上层先查一次再判。

    这两张表是第三步与第四步之间那段管道 —— 第四步的工作清单从这里取「哪几条描述模糊、
    哪几条未报告」，改写后写回 `action_report_draft_item`。
    """

    @classmethod
    async def add_review_dao(cls, db: AsyncSession, review: ActionReportReview) -> ActionReportReview:
        """
        落一行校验任务台账

        **提交那一刻就调用它**（还没有任何判定），结果由 `replace_review_items_dao` 后补。
        014 之前这张表是「跑完才写」，于是失败与中途离开的任务一条都没留下 —— 而那正是
        事后要排查的那批。

        :param db: orm对象
        :param review: 校验记录
        :return: 落库后的记录（已 flush，review_id 可用）
        """
        db.add(review)
        await db.flush()

        return review

    @classmethod
    async def edit_review_dao(cls, db: AsyncSession, review_id: int, values: dict[str, Any]) -> None:
        """
        更新校验记录的若干列（对账用）

        :param db: orm对象
        :param review_id: 校验记录id
        :param values: 列名到值的映射
        """
        if not values:
            return
        await db.execute(
            update(ActionReportReview).where(ActionReportReview.review_id == review_id).values(**values)
        )

    @classmethod
    async def replace_review_items_dao(cls, db: AsyncSession, review_id: int, verdicts: list[dict[str, Any]]) -> None:
        """
        写入一次校验的逐条判定，先清后写

        **先删再插而不是 upsert**：对账可能对同一次任务跑第二遍（比如轮询与历史列表撞在
        一起），而唯一索引 `(review_id, item_id)` 会让第二遍整批插入失败。清掉重写是幂等的。

        :param db: orm对象
        :param review_id: 校验记录id
        :param verdicts: 逐条判定（item_id/status/reason/evidence/lines 的字典列表）
        """
        await db.execute(delete(ActionReportReviewItem).where(ActionReportReviewItem.review_id == review_id))
        if not verdicts:
            return
        db.add_all(
            [
                ActionReportReviewItem(
                    review_id=review_id,
                    item_id=int(v['item_id']),
                    status=str(v['status']),
                    reason=v.get('reason') or '',
                    evidence=v.get('evidence') or '',
                    lines=v.get('lines') or '',
                )
                for v in verdicts
            ]
        )

    @classmethod
    async def trim_user_reviews_dao(cls, db: AsyncSession, user_id: int, keep: int) -> None:
        """
        只保留一个访客最近 keep 次校验，更早的连同判定一起物理删

        不设上限的话，反复点「重新校验」会让这两张表随用户手速无限长 —— 而每行现在还挂着
        一整篇稿件正文，比 014 之前更该管。**按访客而不是按草稿修剪**：外部粘贴的稿件没有
        草稿可依附，按草稿修剪对它们完全不起作用。

        :param db: orm对象
        :param user_id: 归属访客用户id
        :param keep: 保留几次
        """
        stale = (
            (
                await db.execute(
                    select(ActionReportReview.review_id)
                    .where(ActionReportReview.user_id == user_id)
                    .order_by(ActionReportReview.review_id.desc())
                    .offset(keep)
                )
            )
            .scalars()
            .all()
        )
        if not stale:
            return
        await db.execute(delete(ActionReportReviewItem).where(ActionReportReviewItem.review_id.in_(stale)))
        await db.execute(delete(ActionReportReview).where(ActionReportReview.review_id.in_(stale)))

    @classmethod
    async def get_review_by_id_dao(cls, db: AsyncSession, review_id: int, user_id: int) -> ActionReportReview | None:
        """
        按 id 取一次校验（限本人）

        :param db: orm对象
        :param review_id: 校验记录id
        :param user_id: 归属访客用户id
        :return: 校验记录；没有或不属于该用户时为 None
        """
        return (
            (
                await db.execute(
                    select(ActionReportReview).where(
                        ActionReportReview.review_id == review_id,
                        ActionReportReview.user_id == user_id,
                        ActionReportReview.del_flag == '0',
                    )
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def get_review_by_session_dao(
        cls, db: AsyncSession, session_id: str, user_id: int
    ) -> ActionReportReview | None:
        """
        按 worker 任务id 取校验记录（限本人，轮询接口用）

        :param db: orm对象
        :param session_id: worker任务id
        :param user_id: 归属访客用户id
        :return: 校验记录；没有或不属于该用户时为 None
        """
        return (
            (
                await db.execute(
                    select(ActionReportReview)
                    .where(
                        ActionReportReview.session_id == session_id,
                        ActionReportReview.user_id == user_id,
                        ActionReportReview.del_flag == '0',
                    )
                    .order_by(ActionReportReview.review_id.desc())
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def get_user_reviews_dao(cls, db: AsyncSession, user_id: int, limit: int) -> list[ActionReportReview]:
        """
        「我的校验历史」列表（限本人，含未跑完的）

        :param db: orm对象
        :param user_id: 归属访客用户id
        :param limit: 最多取几条
        :return: 校验记录列表，新的在前
        """
        return list(
            (
                await db.execute(
                    select(ActionReportReview)
                    .where(ActionReportReview.user_id == user_id, ActionReportReview.del_flag == '0')
                    .order_by(ActionReportReview.review_id.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def soft_delete_review_dao(cls, db: AsyncSession, review_id: int) -> None:
        """
        删除一条校验历史：记录逻辑删，**正文物理删**

        这是 014 存稿件正文的对价（见 `sql/014-action-report-review-history-pg.sql` 的文件头）。
        用户点「删除」时期待的是「那篇稿子没了」，而不是「列表里看不见了」——
        只置 `del_flag` 的话正文会一直躺在库里。反过来，台账那几列（session_id / 状态 /
        错误 / 计数 / 时间）留着不动：事后排查「上周那次校验为什么挂了」靠的正是它们，
        而它们不含任何稿件内容。

        :param db: orm对象
        :param review_id: 校验记录id
        """
        await db.execute(
            update(ActionReportReview)
            .where(ActionReportReview.review_id == review_id)
            .values(del_flag='2', manuscript=None)
        )
        await db.execute(
            update(ActionReportReviewItem)
            .where(ActionReportReviewItem.review_id == review_id)
            .values(evidence=None)
        )

    @classmethod
    async def get_latest_review_dao(
        cls, db: AsyncSession, draft_id: int, user_id: int
    ) -> ActionReportReview | None:
        """
        取某份草稿最近一次**跑完的**校验（限本人，第四步工作清单的数据源）

        `run_status == 'completed'` 这道过滤是 014 加的，别去掉：台账化之后表里会有排队中、
        跑挂了的行，取到它们的话第四步会拿着一份空判定列出「0 条待办」，
        和「这份稿子全绿」长得一模一样。

        :param db: orm对象
        :param draft_id: 草稿id
        :param user_id: 归属访客用户id
        :return: 校验记录；没有或不属于该用户时为 None
        """
        return (
            (
                await db.execute(
                    select(ActionReportReview)
                    .where(
                        ActionReportReview.draft_id == draft_id,
                        ActionReportReview.user_id == user_id,
                        ActionReportReview.run_status == 'completed',
                        ActionReportReview.del_flag == '0',
                    )
                    .order_by(ActionReportReview.review_id.desc())
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def get_review_items_dao(cls, db: AsyncSession, review_id: int) -> list[ActionReportReviewItem]:
        """
        取一次校验的全部逐条判定

        调用方必须先用 `get_latest_review_dao` 确认过归属 —— 本方法不再判一次。

        :param db: orm对象
        :param review_id: 校验记录id
        :return: 判定列表
        """
        return list(
            (
                await db.execute(
                    select(ActionReportReviewItem)
                    .where(ActionReportReviewItem.review_id == review_id)
                    .order_by(ActionReportReviewItem.item_id)
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def detach_reviews_of_draft_dao(cls, db: AsyncSession, draft_id: int) -> None:
        """
        草稿被删时把它的校验记录**摘下来，而不是删掉**

        014 之前这里是物理删，理由是「判定脱离了草稿没有任何意义（条目正文都没了）」。
        那个理由随 014 失效了：每行校验记录现在自带一份稿件快照与逐条 evidence，
        它本身就是一条完整的、能独立回看的历史。跟着草稿一起删等于用户删一份草稿、
        校验历史里悄悄少掉几条 —— 那是没人要求过的数据丢失。

        摘下来之后它就是一条普通的「外部稿件」历史，用户可以在第三步的历史列表里
        自己删（那条路径会连正文一起真删）。

        :param db: orm对象
        :param draft_id: 草稿id
        """
        await db.execute(
            update(ActionReportReview).where(ActionReportReview.draft_id == draft_id).values(draft_id=None)
        )
class ReportTrailDao:
    """
    报告助手操作留痕数据库操作层

    **只追加，不修改、不删除**：审计记录能改就不是审计记录了。草稿被删时留痕也**不删**
    —— 「这份稿子有哪几段来自模型」这个问题，在草稿删掉之后反而更需要答得出来，
    所以 `draft_id` 只是个弱关联，不做级联。
    """

    @classmethod
    async def add_trail_dao(cls, db: AsyncSession, trail: ActionReportTrail) -> ActionReportTrail:
        """
        追加一条留痕

        :param db: orm对象
        :param trail: 留痕对象
        :return: 落库后的对象
        """
        db.add(trail)
        await db.flush()

        return trail

    @classmethod
    async def get_trail_list_dao(
        cls, db: AsyncSession, user_id: int, draft_id: int | None, limit: int
    ) -> list[ActionReportTrail]:
        """
        取某人的留痕（可按草稿过滤），最近的在前

        **越权保护做在 where 里**：`user_id` 是条件的一部分，不靠上层先查一次再判。

        :param db: orm对象
        :param user_id: 操作人
        :param draft_id: 只看某份草稿；None 表示看全部
        :param limit: 最多回多少条
        :return: 留痕列表
        """
        conditions = [ActionReportTrail.user_id == user_id]
        if draft_id is not None:
            conditions.append(ActionReportTrail.draft_id == draft_id)

        return list(
            (
                await db.execute(
                    select(ActionReportTrail)
                    .where(*conditions)
                    .order_by(ActionReportTrail.trail_id.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
