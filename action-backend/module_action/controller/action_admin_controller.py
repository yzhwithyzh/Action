from datetime import datetime
from typing import Annotated

from fastapi import Body, File, Path, Query, Request, Response, UploadFile
from pydantic_validation_decorator import ValidateFields
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.log_annotation import Log
from common.annotation.rate_limit_annotation import ApiRateLimit, ApiRateLimitPreset
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import CurrentUserDependency, PreAuthDependency
from common.constant import ApiNamespace
from common.enums import BusinessType
from common.router import APIRouterPro
from common.vo import DataResponseModel, DynamicResponseModel, PageResponseModel, ResponseBaseModel
from exceptions.exception import ServiceException
from module_action.entity.vo.action_vo import (
    CollabRequestModel,
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
    TeamMemberModel,
    TeamMemberPageQueryModel,
)
from module_action.service.action_service import (
    CollabRequestService,
    GuidelineCategoryService,
    GuidelineItemService,
    GuidelineService,
    NewsService,
    ResourceLinkService,
    TeamMemberService,
)
from module_admin.entity.vo.common_vo import UploadResponseModel
from module_admin.entity.vo.user_vo import CurrentUserModel
from utils.log_util import logger
from utils.oss_util import MAX_DOCUMENT_SIZE, MAX_IMAGE_SIZE, OssUtil
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


# ------------------------------------------------------------------ 团队成员


@action_admin_controller.get(
    '/team-member/list',
    summary='获取团队成员分页列表',
    description='后台维护用，含已停用的成员',
    response_model=PageResponseModel[TeamMemberModel],
    dependencies=[UserInterfaceAuthDependency('action:teamMember:list')],
)
async def get_admin_team_member_list(
    request: Request,
    member_page_query: Annotated[TeamMemberPageQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await TeamMemberService.get_member_list_services(query_db, member_page_query, is_page=True)
    logger.info('获取成功')

    return ResponseUtil.success(model_content=result)


@action_admin_controller.get(
    '/team-member/{member_id}',
    summary='获取团队成员详情',
    description='后台维护用',
    response_model=DataResponseModel[TeamMemberModel],
    dependencies=[UserInterfaceAuthDependency('action:teamMember:query')],
)
async def get_admin_team_member_detail(
    request: Request,
    member_id: Annotated[int, Path(description='成员id')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await TeamMemberService.member_detail_services(query_db, member_id)
    logger.info(f'获取member_id为{member_id}的信息成功')

    return ResponseUtil.success(data=result)


@action_admin_controller.post(
    '/team-member',
    summary='新增团队成员',
    description='后台维护用',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('action:teamMember:add')],
)
@ValidateFields(validate_model='add_team_member')
@Log(title='团队成员', business_type=BusinessType.INSERT)
async def add_admin_team_member(
    request: Request,
    add_team_member: TeamMemberModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    add_team_member.create_by = current_user.user.user_name
    add_team_member.create_time = datetime.now()
    add_team_member.update_by = current_user.user.user_name
    add_team_member.update_time = datetime.now()
    result = await TeamMemberService.add_member_services(query_db, add_team_member)
    logger.info(result.message)

    return ResponseUtil.success(msg=result.message)


@action_admin_controller.put(
    '/team-member',
    summary='编辑团队成员',
    description='后台维护用',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('action:teamMember:edit')],
)
@ValidateFields(validate_model='edit_team_member')
@Log(title='团队成员', business_type=BusinessType.UPDATE)
async def edit_admin_team_member(
    request: Request,
    edit_team_member: TeamMemberModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    edit_team_member.update_by = current_user.user.user_name
    edit_team_member.update_time = datetime.now()
    result = await TeamMemberService.edit_member_services(query_db, edit_team_member)
    logger.info(result.message)

    return ResponseUtil.success(msg=result.message)


@action_admin_controller.delete(
    '/team-member/{member_ids}',
    summary='删除团队成员',
    description='后台维护用，逻辑删除',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('action:teamMember:remove')],
)
@Log(title='团队成员', business_type=BusinessType.DELETE)
async def delete_admin_team_member(
    request: Request,
    member_ids: Annotated[str, Path(description='需要删除的成员id，多个以逗号分隔')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await TeamMemberService.delete_member_services(query_db, member_ids)
    logger.info(result.message)

    return ResponseUtil.success(msg=result.message)


@action_admin_controller.post(
    '/team-member/avatar',
    summary='上传团队成员头像',
    description='后台维护用，图片直传阿里云 OSS，返回可直接写入 avatarUrl 的公网地址',
    response_model=DynamicResponseModel[UploadResponseModel],
    dependencies=[UserInterfaceAuthDependency('action:teamMember:edit')],
)
@ApiRateLimit(namespace=ApiNamespace.ACTION_TEAM_AVATAR, preset=ApiRateLimitPreset.COMMON_UPLOAD)
async def upload_admin_team_member_avatar(
    request: Request,
    file: Annotated[UploadFile, File(...)],
) -> Response:
    # 不走 /common/upload：那条通道落后端本地磁盘并登记文件表，而官网是 SSG 静态站，
    # 头像必须是与后端机器解耦的公网地址，否则换机部署前台就开天窗。
    extension = OssUtil.normalize_extension(file.filename or '')
    content = await file.read()
    if not content:
        raise ServiceException(message='上传的图片为空')
    if len(content) > MAX_IMAGE_SIZE:
        raise ServiceException(message=f'图片大小不能超过 {MAX_IMAGE_SIZE // 1024 // 1024}MB')

    object_key = OssUtil.build_object_key('team', extension)
    url = await OssUtil.put_object(object_key, content, extension)
    logger.info(f'团队成员头像上传成功：{object_key}')

    # fileName 与 url 同为公网地址：action-admin 的 ImageUpload 组件取 res.fileName 回填，
    # 且对 http(s) 开头的值不会再拼 baseUrl（见其 isExternal 分支）。
    return ResponseUtil.success(
        model_content=UploadResponseModel(
            fileName=url,
            newFileName=object_key.rsplit('/', 1)[-1],
            originalFilename=file.filename,
            url=url,
        )
    )


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


@action_admin_controller.post(
    '/guideline/file',
    summary='上传报告规范文档',
    description='后台维护用，PDF 直传阿里云 OSS，返回可直接写入 fileUrlZh/fileUrlEn 的公网地址',
    response_model=DynamicResponseModel[UploadResponseModel],
    dependencies=[UserInterfaceAuthDependency('action:guideline:edit')],
)
@ApiRateLimit(namespace=ApiNamespace.ACTION_GUIDELINE_FILE, preset=ApiRateLimitPreset.COMMON_UPLOAD)
async def upload_admin_guideline_file(
    request: Request,
    file: Annotated[UploadFile, File(...)],
) -> Response:
    # 与团队头像同理：不走 /common/upload（落后端本地磁盘），官网是 SSG 静态站，
    # 规范原文必须是与后端机器解耦的公网地址，否则换机部署下载链接就断。
    extension = OssUtil.normalize_document_extension(file.filename or '')
    content = await file.read()
    if not content:
        raise ServiceException(message='上传的文档为空')
    if len(content) > MAX_DOCUMENT_SIZE:
        raise ServiceException(message=f'文档大小不能超过 {MAX_DOCUMENT_SIZE // 1024 // 1024}MB')

    object_key = OssUtil.build_object_key('guideline', extension)
    url = await OssUtil.put_object(object_key, content, extension)
    logger.info(f'报告规范文档上传成功：{object_key}')

    # fileName 与 url 同为公网地址，理由同头像接口：action-admin 的 FileUpload 取 res.fileName 回填
    return ResponseUtil.success(
        model_content=UploadResponseModel(
            fileName=url,
            newFileName=object_key.rsplit('/', 1)[-1],
            originalFilename=file.filename,
            url=url,
        )
    )


# ------------------------------------------------------------------ 报告规范分类


@action_admin_controller.get(
    '/guideline-category/list',
    summary='获取报告规范分类分页列表',
    description='后台维护用，含已停用的分类；也供规范目录管理页的「研究设计」下拉取值',
    response_model=PageResponseModel[GuidelineCategoryModel],
    dependencies=[UserInterfaceAuthDependency('action:guidelineCategory:list')],
)
async def get_admin_guideline_category_list(
    request: Request,
    category_page_query: Annotated[GuidelineCategoryPageQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await GuidelineCategoryService.get_category_list_services(query_db, category_page_query, is_page=True)
    logger.info('获取成功')

    return ResponseUtil.success(model_content=result)


@action_admin_controller.get(
    '/guideline-category/{cat_id}',
    summary='获取报告规范分类详情',
    description='后台维护用',
    response_model=DataResponseModel[GuidelineCategoryModel],
    dependencies=[UserInterfaceAuthDependency('action:guidelineCategory:query')],
)
async def get_admin_guideline_category_detail(
    request: Request,
    cat_id: Annotated[int, Path(description='分类id')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await GuidelineCategoryService.category_detail_services(query_db, cat_id)
    logger.info(f'获取cat_id为{cat_id}的信息成功')

    return ResponseUtil.success(data=result)


@action_admin_controller.post(
    '/guideline-category',
    summary='新增报告规范分类',
    description='后台维护用',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('action:guidelineCategory:add')],
)
@ValidateFields(validate_model='add_category')
@Log(title='报告规范分类', business_type=BusinessType.INSERT)
async def add_admin_guideline_category(
    request: Request,
    add_category: GuidelineCategoryModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    add_category.create_by = current_user.user.user_name
    add_category.create_time = datetime.now()
    add_category.update_by = current_user.user.user_name
    add_category.update_time = datetime.now()
    result = await GuidelineCategoryService.add_category_services(query_db, add_category)
    logger.info(result.message)

    return ResponseUtil.success(msg=result.message)


@action_admin_controller.put(
    '/guideline-category',
    summary='编辑报告规范分类',
    description='后台维护用；分类下已有规范时不允许改标识，只允许改名称',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('action:guidelineCategory:edit')],
)
@ValidateFields(validate_model='edit_category')
@Log(title='报告规范分类', business_type=BusinessType.UPDATE)
async def edit_admin_guideline_category(
    request: Request,
    edit_category: GuidelineCategoryModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    edit_category.update_by = current_user.user.user_name
    edit_category.update_time = datetime.now()
    result = await GuidelineCategoryService.edit_category_services(query_db, edit_category)
    logger.info(result.message)

    return ResponseUtil.success(msg=result.message)


@action_admin_controller.delete(
    '/guideline-category/{cat_ids}',
    summary='删除报告规范分类',
    description='后台维护用，逻辑删除；分类下还有规范时拒绝删除',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('action:guidelineCategory:remove')],
)
@Log(title='报告规范分类', business_type=BusinessType.DELETE)
async def delete_admin_guideline_category(
    request: Request,
    cat_ids: Annotated[str, Path(description='需要删除的分类id，多个以逗号分隔')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await GuidelineCategoryService.delete_category_services(query_db, cat_ids)
    logger.info(result.message)

    return ResponseUtil.success(msg=result.message)


# ------------------------------------------------------------------ 规范 checklist 条目


@action_admin_controller.get(
    '/guideline-item/list',
    summary='获取规范条目分页列表',
    description='后台维护用，含已停用的条目；可按规范、清单表、关键词过滤',
    response_model=PageResponseModel[GuidelineItemModel],
    dependencies=[UserInterfaceAuthDependency('action:guidelineItem:list')],
)
async def get_admin_guideline_item_list(
    request: Request,
    item_page_query: Annotated[GuidelineItemPageQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await GuidelineItemService.get_item_list_services(query_db, item_page_query, is_page=True)
    logger.info('获取成功')

    return ResponseUtil.success(model_content=result)


@action_admin_controller.get(
    '/guideline-item/{item_id}',
    summary='获取规范条目详情',
    description='后台维护用',
    response_model=DataResponseModel[GuidelineItemModel],
    dependencies=[UserInterfaceAuthDependency('action:guidelineItem:query')],
)
async def get_admin_guideline_item_detail(
    request: Request,
    item_id: Annotated[int, Path(description='条目id')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await GuidelineItemService.item_detail_services(query_db, item_id)
    logger.info(f'获取item_id为{item_id}的信息成功')

    return ResponseUtil.success(data=result)


@action_admin_controller.post(
    '/guideline-item',
    summary='新增规范条目',
    description='后台维护用',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('action:guidelineItem:add')],
)
@ValidateFields(validate_model='add_guideline_item')
@Log(title='规范条目', business_type=BusinessType.INSERT)
async def add_admin_guideline_item(
    request: Request,
    add_guideline_item: GuidelineItemModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    add_guideline_item.create_by = current_user.user.user_name
    add_guideline_item.create_time = datetime.now()
    add_guideline_item.update_by = current_user.user.user_name
    add_guideline_item.update_time = datetime.now()
    result = await GuidelineItemService.add_item_services(query_db, add_guideline_item)
    logger.info(result.message)

    return ResponseUtil.success(msg=result.message)


@action_admin_controller.put(
    '/guideline-item',
    summary='编辑规范条目',
    description='后台维护用',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('action:guidelineItem:edit')],
)
@ValidateFields(validate_model='edit_guideline_item')
@Log(title='规范条目', business_type=BusinessType.UPDATE)
async def edit_admin_guideline_item(
    request: Request,
    edit_guideline_item: GuidelineItemModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    edit_guideline_item.update_by = current_user.user.user_name
    edit_guideline_item.update_time = datetime.now()
    result = await GuidelineItemService.edit_item_services(query_db, edit_guideline_item)
    logger.info(result.message)

    return ResponseUtil.success(msg=result.message)


@action_admin_controller.delete(
    '/guideline-item/{item_ids}',
    summary='删除规范条目',
    description='后台维护用，逻辑删除',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('action:guidelineItem:remove')],
)
@Log(title='规范条目', business_type=BusinessType.DELETE)
async def delete_admin_guideline_item(
    request: Request,
    item_ids: Annotated[str, Path(description='需要删除的条目id，多个以逗号分隔')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await GuidelineItemService.delete_item_services(query_db, item_ids)
    logger.info(result.message)

    return ResponseUtil.success(msg=result.message)


# ------------------------------------------------------------------ 资源中心链接


@action_admin_controller.get(
    '/resource-link/list',
    summary='获取资源中心链接分页列表',
    description='后台维护用，含已停用的资源',
    response_model=PageResponseModel[ResourceLinkModel],
    dependencies=[UserInterfaceAuthDependency('action:resourceLink:list')],
)
async def get_admin_resource_link_list(
    request: Request,
    link_page_query: Annotated[ResourceLinkPageQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await ResourceLinkService.get_link_list_services(query_db, link_page_query, is_page=True)
    logger.info('获取成功')

    return ResponseUtil.success(model_content=result)


@action_admin_controller.get(
    '/resource-link/{link_id}',
    summary='获取资源中心链接详情',
    description='后台维护用',
    response_model=DataResponseModel[ResourceLinkModel],
    dependencies=[UserInterfaceAuthDependency('action:resourceLink:query')],
)
async def get_admin_resource_link_detail(
    request: Request,
    link_id: Annotated[int, Path(description='资源id')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await ResourceLinkService.link_detail_services(query_db, link_id)
    logger.info(f'获取link_id为{link_id}的信息成功')

    return ResponseUtil.success(data=result)


@action_admin_controller.post(
    '/resource-link',
    summary='新增资源中心链接',
    description='后台维护用',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('action:resourceLink:add')],
)
@ValidateFields(validate_model='add_link')
@Log(title='资源中心链接', business_type=BusinessType.INSERT)
async def add_admin_resource_link(
    request: Request,
    add_link: ResourceLinkModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    add_link.create_by = current_user.user.user_name
    add_link.create_time = datetime.now()
    add_link.update_by = current_user.user.user_name
    add_link.update_time = datetime.now()
    result = await ResourceLinkService.add_link_services(query_db, add_link)
    logger.info(result.message)

    return ResponseUtil.success(msg=result.message)


@action_admin_controller.put(
    '/resource-link',
    summary='编辑资源中心链接',
    description='后台维护用',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('action:resourceLink:edit')],
)
@ValidateFields(validate_model='edit_link')
@Log(title='资源中心链接', business_type=BusinessType.UPDATE)
async def edit_admin_resource_link(
    request: Request,
    edit_link: ResourceLinkModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    edit_link.update_by = current_user.user.user_name
    edit_link.update_time = datetime.now()
    result = await ResourceLinkService.edit_link_services(query_db, edit_link)
    logger.info(result.message)

    return ResponseUtil.success(msg=result.message)


@action_admin_controller.delete(
    '/resource-link/{link_ids}',
    summary='删除资源中心链接',
    description='后台维护用，逻辑删除',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('action:resourceLink:remove')],
)
@Log(title='资源中心链接', business_type=BusinessType.DELETE)
async def delete_admin_resource_link(
    request: Request,
    link_ids: Annotated[str, Path(description='需要删除的资源id，多个以逗号分隔')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await ResourceLinkService.delete_link_services(query_db, link_ids)
    logger.info(result.message)

    return ResponseUtil.success(msg=result.message)


@action_admin_controller.post(
    '/resource-link/logo',
    summary='上传资源中心标识图',
    description='后台维护用，图片直传阿里云 OSS，返回可直接写入 logoUrl 的公网地址',
    response_model=DynamicResponseModel[UploadResponseModel],
    dependencies=[UserInterfaceAuthDependency('action:resourceLink:edit')],
)
@ApiRateLimit(namespace=ApiNamespace.ACTION_RESOURCE_LOGO, preset=ApiRateLimitPreset.COMMON_UPLOAD)
async def upload_admin_resource_link_logo(
    request: Request,
    file: Annotated[UploadFile, File(...)],
) -> Response:
    # 与团队头像同理：不走 /common/upload（落后端本地磁盘），官网是 SSG 静态站，
    # 图片必须是与后端机器解耦的公网地址。种子里那 6 张 /assets/logo-*.png 是随前端
    # 打包的静态资源，不受此限，也不必迁走。
    extension = OssUtil.normalize_extension(file.filename or '')
    content = await file.read()
    if not content:
        raise ServiceException(message='上传的图片为空')
    if len(content) > MAX_IMAGE_SIZE:
        raise ServiceException(message=f'图片大小不能超过 {MAX_IMAGE_SIZE // 1024 // 1024}MB')

    object_key = OssUtil.build_object_key('resource', extension)
    url = await OssUtil.put_object(object_key, content, extension)
    logger.info(f'资源中心标识图上传成功：{object_key}')

    # fileName 与 url 同为公网地址，理由同头像接口：ImageUpload 取 res.fileName 回填
    return ResponseUtil.success(
        model_content=UploadResponseModel(
            fileName=url,
            newFileName=object_key.rsplit('/', 1)[-1],
            originalFilename=file.filename,
            url=url,
        )
    )


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
