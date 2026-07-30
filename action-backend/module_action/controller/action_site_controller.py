from typing import Annotated

from fastapi import Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.rate_limit_annotation import ApiRateLimit, ApiRateLimitPreset
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.guest_auth import GuestUserDependency
from common.constant import ApiNamespace
from common.router import APIRouterPro
from common.vo import DataResponseModel, DynamicResponseModel, PageResponseModel, ResponseBaseModel
from module_action.entity.vo.action_vo import (
    CfirDomainModel,
    CollabRequestSubmitModel,
    GuestEmailCodeModel,
    GuestInfoModel,
    GuestLoginModel,
    GuestPublicInfoModel,
    GuestRegisterModel,
    GuestTokenModel,
    GuidelineModel,
    GuidelinePageQueryModel,
    NewsModel,
    NewsPageQueryModel,
    ReaimDimensionModel,
    SrdAssessmentModel,
    StudyTypeModel,
)
from module_action.service.action_service import (
    CollabRequestService,
    GuidelineService,
    ImplementationService,
    NewsService,
    SrdService,
    StudyTypeService,
)
from module_action.service.guest_auth_service import GuestAuthService
from utils.log_util import logger
from utils.response_util import ResponseUtil

# 官网公开接口：**不挂 PreAuthDependency**。
# 这些数据本就对外公开，官网是匿名访问的静态站，加鉴权会直接打不开。
# 后台维护用的写接口在 action_admin_controller.py，那边才做鉴权与权限校验。
action_site_controller = APIRouterPro(prefix='/action/site', order_num=90, tags=['官网-公开接口'])


def _client_ip(request: Request) -> str:
    """
    取客户端 ip，用于表单来源记录

    :param request: 请求对象
    :return: 客户端 ip
    """
    return request.client.host if request.client else ''


@action_site_controller.get(
    '/news',
    summary='获取官网新闻列表',
    description='官网公开接口，返回已发布的新闻动态分页列表',
    response_model=PageResponseModel[NewsModel],
)
async def get_site_news_list(
    request: Request,
    news_page_query: Annotated[NewsPageQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await NewsService.get_news_list_services(query_db, news_page_query, is_page=True, only_published=True)
    logger.info('获取官网新闻列表成功')

    return ResponseUtil.success(model_content=result)


@action_site_controller.get(
    '/news/{news_id}',
    summary='获取官网新闻详情',
    description='官网公开接口，返回指定新闻的详细内容',
    response_model=DataResponseModel[NewsModel],
)
async def get_site_news_detail(
    request: Request,
    news_id: int,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await NewsService.news_detail_services(query_db, news_id)
    logger.info(f'获取新闻{news_id}详情成功')

    return ResponseUtil.success(data=result)


@action_site_controller.get(
    '/guidelines',
    summary='获取报告规范目录',
    description='官网公开接口，返回启用中的报告规范目录',
    response_model=PageResponseModel[GuidelineModel],
)
async def get_site_guideline_list(
    request: Request,
    guideline_page_query: Annotated[GuidelinePageQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await GuidelineService.get_guideline_list_services(
        query_db, guideline_page_query, is_page=True, only_published=True
    )
    logger.info('获取报告规范目录成功')

    return ResponseUtil.success(model_content=result)


@action_site_controller.get(
    '/study-types',
    summary='获取研究类型及其规范与统计推荐',
    description='官网公开接口，供智能报告工具做「研究类型 → 报告规范 + 统计方法」匹配',
    response_model=DataResponseModel[list[StudyTypeModel]],
)
async def get_site_study_types(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await StudyTypeService.get_study_type_tree_services(query_db)
    logger.info('获取研究类型成功')

    return ResponseUtil.success(data=result)


@action_site_controller.get(
    '/implementation/cfir',
    summary='获取 CFIR 针刺版障碍与策略库',
    description='官网公开接口，返回 CFIR 领域 → 构念 → 应对策略三级结构',
    response_model=DataResponseModel[list[CfirDomainModel]],
)
async def get_site_cfir(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await ImplementationService.get_cfir_tree_services(query_db)
    logger.info('获取CFIR策略库成功')

    return ResponseUtil.success(data=result)


@action_site_controller.get(
    '/implementation/eric',
    summary='获取 ERIC 实施策略库',
    description='官网公开接口，返回 ERIC 策略分类与策略条目',
)
async def get_site_eric(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    category: str | None = Query(default=None, description='策略分类标识，all 或留空表示全部'),
) -> Response:
    result = await ImplementationService.get_eric_services(query_db, category)
    logger.info('获取ERIC策略库成功')

    return ResponseUtil.success(data=result)


@action_site_controller.get(
    '/implementation/reaim',
    summary='获取 RE-AIM 维度',
    description='官网公开接口，返回 RE-AIM 五个维度的定义与测量指标',
    response_model=DataResponseModel[list[ReaimDimensionModel]],
)
async def get_site_reaim(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await ImplementationService.get_reaim_services(query_db)
    logger.info('获取RE-AIM维度成功')

    return ResponseUtil.success(data=result)


@action_site_controller.get(
    '/srd/sample',
    summary='获取 SRD 示例评估',
    description='官网公开接口，返回系统综述重复性评估的示例数据（评估 → 领域 → 分组 → 条目）',
    response_model=DataResponseModel[SrdAssessmentModel],
)
async def get_site_srd_sample(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await SrdService.get_assessment_services(query_db)
    logger.info('获取SRD示例评估成功')

    return ResponseUtil.success(data=result)


@action_site_controller.post(
    '/collaborate',
    summary='提交协作与专家咨询申请',
    description='官网公开接口，接收官网表单提交',
    response_model=ResponseBaseModel,
)
async def submit_site_collaborate(
    request: Request,
    submit: CollabRequestSubmitModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await CollabRequestService.submit_request_services(query_db, submit, _client_ip(request))
    logger.info('官网协作申请提交成功')

    return ResponseUtil.success(msg=result.message)


# ---------------------------------------------------------------- 访客账号
#
# 这四个接口是官网唯一的写入口（前三个还是完全匿名的），必须挂限流。
# 访客与后台账号共用 sys_user 但走完全独立的身份依赖，不复用 PreAuthDependency。


@action_site_controller.post(
    '/auth/email-code',
    summary='发送访客邮箱验证码',
    description='官网公开接口，向注册/登录邮箱发送6位数字验证码，5分钟有效',
    response_model=ResponseBaseModel,
)
@ApiRateLimit(namespace=ApiNamespace.ACTION_GUEST_EMAIL_CODE, preset=ApiRateLimitPreset.ANON_AUTH_CAPTCHA)
async def send_guest_email_code(
    request: Request,
    code_model: GuestEmailCodeModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await GuestAuthService.send_email_code(request, query_db, code_model)
    logger.info('访客邮箱验证码请求处理完成')

    return ResponseUtil.success(msg=result)


@action_site_controller.post(
    '/auth/register',
    summary='访客注册',
    description='官网公开接口，凭邮箱验证码注册访客账号并直接返回登录令牌',
    response_model=DynamicResponseModel[GuestTokenModel],
)
@ApiRateLimit(namespace=ApiNamespace.ACTION_GUEST_REGISTER, preset=ApiRateLimitPreset.ANON_AUTH_REGISTER)
async def register_guest(
    request: Request,
    register_model: GuestRegisterModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await GuestAuthService.register(request, query_db, register_model)
    logger.info('访客注册成功')

    return ResponseUtil.success(msg='注册成功', model_content=result)


@action_site_controller.post(
    '/auth/login',
    summary='访客登录',
    description='官网公开接口，支持邮箱验证码登录与邮箱密码登录（二选一）',
    response_model=DynamicResponseModel[GuestTokenModel],
)
@ApiRateLimit(namespace=ApiNamespace.ACTION_GUEST_LOGIN, preset=ApiRateLimitPreset.ANON_AUTH_LOGIN)
async def login_guest(
    request: Request,
    login_model: GuestLoginModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await GuestAuthService.login(request, query_db, login_model)
    logger.info('访客登录成功')

    return ResponseUtil.success(msg='登录成功', model_content=result)


@action_site_controller.get(
    '/auth/me',
    summary='获取当前访客信息',
    description='官网访客接口，需携带访客令牌',
    response_model=DataResponseModel[GuestPublicInfoModel],
)
@ApiRateLimit(namespace=ApiNamespace.ACTION_GUEST_ME, preset=ApiRateLimitPreset.ANON_AUTH_CAPTCHA)
async def get_current_guest(
    request: Request,
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    logger.info('获取当前访客信息成功')

    # 依赖返回的 GuestInfoModel 带 user_id，那是给身份识别用的内部字段；
    # 对外返回体只暴露 {email, username, institution, position}
    return ResponseUtil.success(data=current_guest.to_public())


@action_site_controller.post(
    '/auth/logout',
    summary='访客登出',
    description='官网访客接口，撤销当前令牌对应的会话；令牌本就失效时同样返回成功',
    response_model=ResponseBaseModel,
)
@ApiRateLimit(namespace=ApiNamespace.ACTION_GUEST_LOGOUT, preset=ApiRateLimitPreset.ANON_AUTH_CAPTCHA)
async def logout_guest(
    request: Request,
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    # current_guest 只作身份闸门用：登出不需要访客的任何字段，但没有它这个接口就成了
    # 「任何人都能拿别人的 session_id 来注销」的匿名撤销入口。
    result = await GuestAuthService.logout(request)
    logger.info('访客登出成功')

    return ResponseUtil.success(msg=result)
