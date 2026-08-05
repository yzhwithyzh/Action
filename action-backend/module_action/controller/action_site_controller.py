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
    ChecklistReviewStateModel,
    ChecklistReviewSubmitModel,
    CollabRequestSubmitModel,
    GuestEmailCodeModel,
    GuestInfoModel,
    GuestLoginModel,
    GuestPublicInfoModel,
    GuestRegisterModel,
    GuestTokenModel,
    GuidelineItemModel,
    GuidelineItemPageQueryModel,
    GuidelineItemQueryModel,
    GuidelineModel,
    GuidelinePageQueryModel,
    NewsModel,
    NewsPageQueryModel,
    ReaimDimensionModel,
    SrdAssessmentModel,
    StudyTypeModel,
    TeamMemberModel,
    TeamMemberPageQueryModel,
)
from module_action.service.action_service import (
    ChecklistReviewService,
    CollabRequestService,
    GuidelineItemService,
    GuidelineService,
    ImplementationService,
    NewsService,
    SrdService,
    StudyTypeService,
    TeamMemberService,
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
    '/team-members',
    summary='获取团队成员列表',
    description=(
        '官网公开接口，返回启用中的国际顾问委员会与核心执行团队成员，'
        '已按「组 → 组内顺序」排好，前台按 groupKey 分段渲染。'
    ),
    response_model=DataResponseModel[list[TeamMemberModel]],
)
async def get_site_team_members(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    group_key: str | None = Query(default=None, alias='groupKey', description='所属组（board/core），留空取全部'),
) -> Response:
    page_query = TeamMemberPageQueryModel(groupKey=group_key) if group_key else TeamMemberPageQueryModel()
    result = await TeamMemberService.get_member_list_services(query_db, page_query, only_published=True)
    logger.info('获取团队成员列表成功')

    return ResponseUtil.success(data=result)


@action_site_controller.get(
    '/team-members/{member_id}',
    summary='获取团队成员详情',
    description='官网公开接口，供成员详情页展示完整履历与对 ACTION 的贡献',
    response_model=DataResponseModel[TeamMemberModel],
)
async def get_site_team_member_detail(
    request: Request,
    member_id: int,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await TeamMemberService.member_detail_services(query_db, member_id)
    logger.info(f'获取团队成员{member_id}详情成功')

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
    '/guideline-items',
    summary='获取某份规范的 checklist 条目',
    description=(
        '官网公开接口，供报告助手第二步（结构化模板）与第三步（逐条校验）取条目。'
        '按 guidelineCode 或 guidelineId 取，多张清单表已按 sortNum 合并成一条流水清单。'
    ),
    response_model=DataResponseModel[list[GuidelineItemModel]],
)
async def get_site_guideline_items(
    request: Request,
    item_query: Annotated[GuidelineItemQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    if not item_query.guideline_code and not item_query.guideline_id:
        # 不给过滤条件会把 6 份规范 282 条全量吐出去，对公开接口没意义
        return ResponseUtil.failure(msg='请指定 guidelineCode 或 guidelineId')
    # 必须 by_alias：本模块的 VO 用了 alias_generator=to_camel 且没开 populate_by_name，
    # 传 snake_case 字段名会被 pydantic 静默丢掉（extra 默认 ignore），
    # 于是 guideline_code/guideline_id 双双落空、上面的守卫形同虚设，接口会把 282 条全量吐出。
    page_query = GuidelineItemPageQueryModel(**item_query.model_dump(by_alias=True))
    result = await GuidelineItemService.get_item_list_services(query_db, page_query, only_published=True)
    logger.info('获取规范条目成功')

    return ResponseUtil.success(data=result)


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


# ---------------------------------------------------------------- 报告助手第三步：checklist 逐条校验
#
# 提交接口会触发几十次模型调用，必须挂限流且要求访客登录 —— 匿名放开等于把账单交给公网。
# 稿件正文只进 Redis 队列与 worker 工作目录，不落业务库：那是用户未发表的研究稿件。


@action_site_controller.post(
    '/checklist-review',
    summary='提交稿件做 checklist 逐条校验',
    description='报告助手第三步。提交后立即返回任务id，结果通过状态接口轮询获取',
    response_model=DataResponseModel[str],
)
@ApiRateLimit(namespace=ApiNamespace.ACTION_CHECKLIST_REVIEW, preset=ApiRateLimitPreset.USER_RESOURCE_EXECUTION)
async def submit_site_checklist_review(
    request: Request,
    submit: ChecklistReviewSubmitModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    session_id = await ChecklistReviewService.submit_review_services(query_db, submit, current_guest.user_id)
    logger.info(f'checklist 校验任务已提交：{session_id}')

    return ResponseUtil.success(data=session_id, msg='已提交，正在校验')


@action_site_controller.get(
    '/checklist-review/{session_id}',
    summary='查询 checklist 校验任务状态',
    description='报告助手第三步的轮询接口，完成后 result 里带逐条判定',
    response_model=DataResponseModel[ChecklistReviewStateModel],
)
async def get_site_checklist_review(
    request: Request,
    session_id: str,
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    result = await ChecklistReviewService.review_state_services(session_id)
    logger.info(f'查询 checklist 校验任务 {session_id} 状态成功')

    return ResponseUtil.success(data=result)


@action_site_controller.post(
    '/checklist-review/{session_id}/stop',
    summary='停止 checklist 校验任务',
    description='报告助手第三步的中止按钮',
    response_model=ResponseBaseModel,
)
async def stop_site_checklist_review(
    request: Request,
    session_id: str,
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    result = await ChecklistReviewService.stop_review_services(session_id)
    logger.info(f'已请求停止 checklist 校验任务 {session_id}')

    return ResponseUtil.success(msg=result.message)


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
