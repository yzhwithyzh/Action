from datetime import datetime
from typing import Annotated

from fastapi import Body, Path, Query, Request, Response
from pydantic_validation_decorator import ValidateFields
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.log_annotation import Log
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import CurrentUserDependency, PreAuthDependency
from common.enums import BusinessType
from common.router import APIRouterPro
from common.vo import DataResponseModel, PageResponseModel, ResponseBaseModel
from module_action.entity.vo.action_vo import (
    CollabRequestModel,
    CollabRequestPageQueryModel,
    GuidelineModel,
    GuidelinePageQueryModel,
    NewsModel,
    NewsPageQueryModel,
)
from module_action.service.action_service import CollabRequestService, GuidelineService, NewsService
from module_admin.entity.vo.user_vo import CurrentUserModel
from utils.log_util import logger
from utils.response_util import ResponseUtil

# 官网内容管理：走后台鉴权，与 action_site_controller 的公开接口彻底分开。
action_admin_controller = APIRouterPro(
    prefix='/action/admin', order_num=91, tags=['官网-内容管理'], dependencies=[PreAuthDependency()]
)


# ------------------------------------------------------------------ 新闻动态


@action_admin_controller.get(
    '/news/list',
    summary='获取官网新闻分页列表',
    description='后台维护用，含未发布与已停用的新闻',
    response_model=PageResponseModel[NewsModel],
    dependencies=[UserInterfaceAuthDependency('action:news:list')],
)
async def get_admin_news_list(
    request: Request,
    news_page_query: Annotated[NewsPageQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await NewsService.get_news_list_services(query_db, news_page_query, is_page=True)
    logger.info('获取成功')

    return ResponseUtil.success(model_content=result)


@action_admin_controller.get(
    '/news/{news_id}',
    summary='获取官网新闻详情',
    description='后台维护用',
    response_model=DataResponseModel[NewsModel],
    dependencies=[UserInterfaceAuthDependency('action:news:query')],
)
async def get_admin_news_detail(
    request: Request,
    news_id: Annotated[int, Path(description='新闻id')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await NewsService.news_detail_services(query_db, news_id)
    logger.info(f'获取news_id为{news_id}的信息成功')

    return ResponseUtil.success(data=result)


@action_admin_controller.post(
    '/news',
    summary='新增官网新闻',
    description='后台维护用',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('action:news:add')],
)
@ValidateFields(validate_model='add_news')
@Log(title='官网新闻', business_type=BusinessType.INSERT)
async def add_admin_news(
    request: Request,
    add_news: NewsModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    add_news.create_by = current_user.user.user_name
    add_news.create_time = datetime.now()
    add_news.update_by = current_user.user.user_name
    add_news.update_time = datetime.now()
    result = await NewsService.add_news_services(query_db, add_news)
    logger.info(result.message)

    return ResponseUtil.success(msg=result.message)


@action_admin_controller.put(
    '/news',
    summary='编辑官网新闻',
    description='后台维护用',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('action:news:edit')],
)
@ValidateFields(validate_model='edit_news')
@Log(title='官网新闻', business_type=BusinessType.UPDATE)
async def edit_admin_news(
    request: Request,
    edit_news: NewsModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    edit_news.update_by = current_user.user.user_name
    edit_news.update_time = datetime.now()
    result = await NewsService.edit_news_services(query_db, edit_news)
    logger.info(result.message)

    return ResponseUtil.success(msg=result.message)


@action_admin_controller.delete(
    '/news/{news_ids}',
    summary='删除官网新闻',
    description='后台维护用，逻辑删除',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('action:news:remove')],
)
@Log(title='官网新闻', business_type=BusinessType.DELETE)
async def delete_admin_news(
    request: Request,
    news_ids: Annotated[str, Path(description='需要删除的新闻id，多个以逗号分隔')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await NewsService.delete_news_services(query_db, news_ids)
    logger.info(result.message)

    return ResponseUtil.success(msg=result.message)


# ------------------------------------------------------------------ 报告规范目录


@action_admin_controller.get(
    '/guideline/list',
    summary='获取报告规范分页列表',
    description='后台维护用',
    response_model=PageResponseModel[GuidelineModel],
    dependencies=[UserInterfaceAuthDependency('action:guideline:list')],
)
async def get_admin_guideline_list(
    request: Request,
    guideline_page_query: Annotated[GuidelinePageQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await GuidelineService.get_guideline_list_services(query_db, guideline_page_query, is_page=True)
    logger.info('获取成功')

    return ResponseUtil.success(model_content=result)


@action_admin_controller.get(
    '/guideline/{guideline_id}',
    summary='获取报告规范详情',
    description='后台维护用',
    response_model=DataResponseModel[GuidelineModel],
    dependencies=[UserInterfaceAuthDependency('action:guideline:query')],
)
async def get_admin_guideline_detail(
    request: Request,
    guideline_id: Annotated[int, Path(description='规范id')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await GuidelineService.guideline_detail_services(query_db, guideline_id)
    logger.info(f'获取guideline_id为{guideline_id}的信息成功')

    return ResponseUtil.success(data=result)


@action_admin_controller.post(
    '/guideline',
    summary='新增报告规范',
    description='后台维护用',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('action:guideline:add')],
)
@ValidateFields(validate_model='add_guideline')
@Log(title='报告规范', business_type=BusinessType.INSERT)
async def add_admin_guideline(
    request: Request,
    add_guideline: GuidelineModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    add_guideline.create_by = current_user.user.user_name
    add_guideline.create_time = datetime.now()
    add_guideline.update_by = current_user.user.user_name
    add_guideline.update_time = datetime.now()
    result = await GuidelineService.add_guideline_services(query_db, add_guideline)
    logger.info(result.message)

    return ResponseUtil.success(msg=result.message)


@action_admin_controller.put(
    '/guideline',
    summary='编辑报告规范',
    description='后台维护用',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('action:guideline:edit')],
)
@ValidateFields(validate_model='edit_guideline')
@Log(title='报告规范', business_type=BusinessType.UPDATE)
async def edit_admin_guideline(
    request: Request,
    edit_guideline: GuidelineModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    edit_guideline.update_by = current_user.user.user_name
    edit_guideline.update_time = datetime.now()
    result = await GuidelineService.edit_guideline_services(query_db, edit_guideline)
    logger.info(result.message)

    return ResponseUtil.success(msg=result.message)


@action_admin_controller.delete(
    '/guideline/{guideline_ids}',
    summary='删除报告规范',
    description='后台维护用，逻辑删除',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('action:guideline:remove')],
)
@Log(title='报告规范', business_type=BusinessType.DELETE)
async def delete_admin_guideline(
    request: Request,
    guideline_ids: Annotated[str, Path(description='需要删除的规范id，多个以逗号分隔')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await GuidelineService.delete_guideline_services(query_db, guideline_ids)
    logger.info(result.message)

    return ResponseUtil.success(msg=result.message)


# ------------------------------------------------------------------ 协作与咨询申请


@action_admin_controller.get(
    '/collab/list',
    summary='获取协作与咨询申请列表',
    description='后台维护用，查看官网表单提交',
    response_model=PageResponseModel[CollabRequestModel],
    dependencies=[UserInterfaceAuthDependency('action:collab:list')],
)
async def get_admin_collab_list(
    request: Request,
    collab_page_query: Annotated[CollabRequestPageQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await CollabRequestService.get_request_list_services(query_db, collab_page_query, is_page=True)
    logger.info('获取成功')

    return ResponseUtil.success(model_content=result)


@action_admin_controller.put(
    '/collab/{request_id}/handle',
    summary='处理协作与咨询申请',
    description='后台维护用，更新处理状态与备注',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('action:collab:edit')],
)
@Log(title='协作咨询申请', business_type=BusinessType.UPDATE)
async def handle_admin_collab(
    request: Request,
    request_id: Annotated[int, Path(description='申请id')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    handle_status: Annotated[str, Body(embed=True, description='处理状态（0待处理 1处理中 2已回复 3已关闭）')],
    handle_remark: Annotated[str, Body(embed=True, description='处理备注')] = '',
) -> Response:
    result = await CollabRequestService.handle_request_services(
        query_db, request_id, handle_status, current_user.user.user_name, handle_remark
    )
    logger.info(result.message)

    return ResponseUtil.success(msg=result.message)


@action_admin_controller.delete(
    '/collab/{request_ids}',
    summary='删除协作与咨询申请',
    description='后台维护用，逻辑删除',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('action:collab:remove')],
)
@Log(title='协作咨询申请', business_type=BusinessType.DELETE)
async def delete_admin_collab(
    request: Request,
    request_ids: Annotated[str, Path(description='需要删除的申请id，多个以逗号分隔')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await CollabRequestService.delete_request_services(query_db, request_ids)
    logger.info(result.message)

    return ResponseUtil.success(msg=result.message)
