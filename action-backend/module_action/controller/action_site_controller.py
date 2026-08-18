import re
from typing import Annotated
from urllib.parse import quote

from fastapi import File, Form, Query, Request, Response, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.rate_limit_annotation import ApiRateLimit, ApiRateLimitPreset
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.guest_auth import GuestUserDependency
from common.constant import ApiNamespace
from common.router import APIRouterPro
from common.vo import DataResponseModel, DynamicResponseModel, PageResponseModel, ResponseBaseModel
from module_action.entity.vo.action_vo import (
    AssistApplyModel,
    AssistRequestModel,
    AssistResultModel,
    CfirDomainModel,
    ChecklistReviewStateModel,
    ChecklistReviewSubmitModel,
    ChecklistReviewSubmitResultModel,
    CollabRequestSubmitModel,
    DraftImportResultModel,
    GuestEmailCodeModel,
    GuestInfoModel,
    GuestLoginModel,
    GuestPublicInfoModel,
    GuestRegisterModel,
    GuestTokenModel,
    GuidelineCategoryModel,
    GuidelineCategoryPageQueryModel,
    GuidelineItemModel,
    GuidelineItemPageQueryModel,
    GuidelineItemQueryModel,
    GuidelineModel,
    GuidelinePageQueryModel,
    NewsModel,
    NewsPageQueryModel,
    ReaimDimensionModel,
    ReportDraftComposeModel,
    ReportDraftCreateModel,
    ReportDraftModel,
    ReportDraftSaveModel,
    ReportReviewHistoryModel,
    ReportReviewModel,
    ResourceLinkModel,
    ResourceLinkPageQueryModel,
    SiteTextOverridesModel,
    SrdAssessmentModel,
    SrdHistoryModel,
    SrdRunStateModel,
    StudyTypeModel,
    TeamMemberModel,
    TeamMemberPageQueryModel,
    TrailAddModel,
    TrailModel,
)
from module_action.service.action_service import (
    ChecklistReviewService,
    CollabRequestService,
    GuidelineCategoryService,
    GuidelineItemService,
    GuidelineService,
    ImplementationService,
    NewsService,
    ReportDraftService,
    ReportReviewService,
    ReportTrailService,
    ResourceLinkService,
    SiteTextService,
    SrdService,
    StudyTypeService,
    TeamMemberService,
)
from module_action.service.guest_auth_service import GuestAuthService
from utils.common_util import bytes2file_response
from utils.log_util import logger
from utils.oss_util import OssUtil
from utils.response_util import ResponseUtil

#: xlsx 的媒体类型。**必须显式给** —— `ResponseUtil.streaming` 默认不带 Content-Type，
#: 而前台要靠它把「一份 xlsx」和「同一条通道上回来的 JSON 错误信封」区分开
#: （本站错误走 HTTP 200 + code≠200，光看状态码分不出来）。
XLSX_MEDIA_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

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
    '/resource-links',
    summary='获取资源中心链接',
    description=(
        '官网公开接口，返回启用中的资源中心外链，已按 sortNum 排好。'
        '首页「国际报告规范组织与循证枢纽」一段按本接口渲染，栏目标题与导语仍在前端 i18n。'
    ),
    response_model=DataResponseModel[list[ResourceLinkModel]],
)
async def get_site_resource_links(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await ResourceLinkService.get_link_list_services(
        query_db, ResourceLinkPageQueryModel(), only_published=True
    )
    logger.info('获取资源中心链接成功')

    return ResponseUtil.success(data=result)


@action_site_controller.get(
    '/texts',
    summary='获取官网文案覆盖包',
    description=(
        '官网公开接口，返回**被后台改过**的 i18n 词条（键为 index.s052 这样的完整 i18n 键）。'
        '前台在打包进来的 i18n 默认文案之上 merge 这一层，没人改过时两个字典都是空的。'
        '刻意不返回全部 934 条：那会给每个页面的 hydration payload 白压上约 120KB。'
    ),
    response_model=DataResponseModel[SiteTextOverridesModel],
)
async def get_site_texts(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await SiteTextService.get_overrides_services(query_db)
    logger.info('获取官网文案覆盖包成功')

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
    '/guidelines/{guideline_id}',
    summary='获取报告规范详情',
    description=(
        '官网公开接口，供规范原文阅读页（`/guideline/[id]`）取名称、版本与中英文 PDF 直链。'
        '与团队成员详情同理：已停用的规范仍可按 id 直达，但不会出现在目录列表里。'
    ),
    response_model=DataResponseModel[GuidelineModel],
)
async def get_site_guideline_detail(
    request: Request,
    guideline_id: int,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await GuidelineService.guideline_detail_services(query_db, guideline_id)
    logger.info(f'获取报告规范{guideline_id}详情成功')

    return ResponseUtil.success(data=result)


@action_site_controller.get(
    '/guidelines/{guideline_id}/file',
    summary='内嵌预览报告规范原文',
    description=(
        '官网公开接口，把 OSS 上的规范原文 PDF 以 `Content-Disposition: inline` 转发出来，'
        '供 `/guideline/[id]` 页的 `<iframe>` 直接渲染。'
        '**不要改回让前台直连 OSS**：阿里云对默认域名下的所有对象强制加 attachment 响应头'
        '（`x-oss-force-download: true`），iframe 里点开只会触发下载、页面一片空白。'
        '下载按钮仍走 OSS 直链 —— 那个场景要的正是 attachment。'
    ),
    response_class=Response,
    responses={200: {'content': {'application/pdf': {}}, 'description': '规范原文 PDF'}},
)
async def get_site_guideline_file(
    request: Request,
    guideline_id: int,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    lang: Annotated[str, Query(pattern='^(zh|en)$', description='原文语言版本')] = 'zh',
) -> Response:
    guideline = await GuidelineService.guideline_detail_services(query_db, guideline_id)
    wanted, other = (
        (guideline.file_url_zh, guideline.file_url_en) if lang == 'zh' else (guideline.file_url_en, guideline.file_url_zh)
    )
    # 只有一种语言有原文时回落到另一种：与前台「两版都有才给切换按钮」的取值口径保持一致。
    # served_lang 跟着回落一起改，否则下载下来的文件名会写成没送出去的那一版
    url, served_lang = (wanted or '').strip(), lang
    if not url:
        url, served_lang = (other or '').strip(), ('en' if lang == 'zh' else 'zh')
    if not url:
        return ResponseUtil.failure(msg='该规范暂未上传原文')

    # 只把自家 OSS 上的 PDF 内联转发。放开这两个条件的代价：任意 URL 转发是 SSRF，
    # 而把 text/html 之类以 inline 挂到本站域名下，等于给了一个同源的脚本执行面。
    if not url.lower().split('?')[0].endswith('.pdf') or not OssUtil.is_own_public_url(url):
        return RedirectResponse(url)

    content = await OssUtil.fetch_public_object(url)
    # 文件名只留 ASCII 安全字符：code 由后台录入，直接拼进响应头会被换行/引号截断
    safe_code = re.sub(r'[^A-Za-z0-9._-]', '', guideline.code or 'guideline') or 'guideline'
    logger.info(f'预览报告规范{guideline_id}原文（{served_lang}）')

    return Response(
        content=content,
        media_type='application/pdf',
        headers={
            'Content-Disposition': f'inline; filename="{safe_code}-{served_lang}.pdf"',
            # 原文换版要靠后台重新上传（对象键是随机名，URL 会变），这里可以放心缓存
            'Cache-Control': 'public, max-age=3600',
        },
    )


@action_site_controller.get(
    '/guideline-categories',
    summary='获取报告规范分类',
    description=(
        '官网公开接口，返回启用中的研究设计分类，已按 sortNum 排好。'
        '规范页第①段的筛选条按本接口渲染，卡片上的「研究设计」标签与图标也取自这里；'
        '与规范的对应关系是 category.catKey == guideline.studyType。'
    ),
    response_model=DataResponseModel[list[GuidelineCategoryModel]],
)
async def get_site_guideline_categories(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await GuidelineCategoryService.get_category_list_services(
        query_db, GuidelineCategoryPageQueryModel(), only_published=True
    )
    logger.info('获取报告规范分类成功')

    return ResponseUtil.success(data=result)


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


# ---------------------------------------------------------------- SRD 真实评估
#
# 与 checklist 校验同理：一次评估是几十次模型调用，必须挂限流且要求访客登录。
# 上传的两篇 PDF 只落后端私有目录（供同机的 worker 读），既不进业务库也不进那个
# 整桶公共读的 OSS 桶；任务到终态后由服务层删掉。评估结果本人可见，示例对所有人可见。


@action_site_controller.post(
    '/srd/assessments',
    summary='提交两篇系统综述做重复性评估',
    description='上传 A/B 两篇 PDF，立即返回任务id，结果通过状态接口轮询获取',
    response_model=DataResponseModel[str],
)
@ApiRateLimit(namespace=ApiNamespace.ACTION_SRD_ASSESS, preset=ApiRateLimitPreset.USER_RESOURCE_EXECUTION)
async def submit_site_srd_assessment(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
    file_a: Annotated[UploadFile, File(..., alias='fileA', description='综述A的PDF')],
    file_b: Annotated[UploadFile, File(..., alias='fileB', description='综述B的PDF')],
) -> Response:
    session_id = await SrdService.submit_assessment_services(query_db, current_guest.user_id, file_a, file_b)
    logger.info(f'SRD 评估任务已提交：{session_id}')

    return ResponseUtil.success(data=session_id, msg='已提交，正在评估')


@action_site_controller.get(
    '/srd/assessments/{session_id}/state',
    summary='查询 SRD 评估任务状态',
    description='轮询接口。任务跑完时顺手把引擎结果落库，出参里的 assessmentId 即可用于取详情',
    response_model=DataResponseModel[SrdRunStateModel],
)
async def get_site_srd_run_state(
    request: Request,
    session_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    result = await SrdService.run_state_services(query_db, session_id, current_guest.user_id)
    logger.info(f'查询 SRD 评估任务 {session_id} 状态成功')

    return ResponseUtil.success(data=result)


@action_site_controller.post(
    '/srd/assessments/{session_id}/stop',
    summary='停止 SRD 评估任务',
    description='用户点「中止」时调用',
    response_model=ResponseBaseModel,
)
async def stop_site_srd_run(
    request: Request,
    session_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    result = await SrdService.stop_run_services(query_db, session_id, current_guest.user_id)
    logger.info(f'已请求停止 SRD 评估任务 {session_id}')

    return ResponseUtil.success(msg=result.message)


@action_site_controller.get(
    '/srd/assessments',
    summary='获取我的 SRD 评估历史',
    description='返回当前访客的评估记录列表（不含 34 条目明细）',
    response_model=DataResponseModel[list[SrdHistoryModel]],
)
async def list_site_srd_history(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    result = await SrdService.list_history_services(query_db, current_guest.user_id)
    logger.info('获取 SRD 评估历史成功')

    return ResponseUtil.success(data=result)


@action_site_controller.get(
    '/srd/assessments/{assessment_id}',
    summary='获取一次 SRD 评估的完整结果',
    description='评估 → 领域 → 分组 → 条目；只能取本人的记录',
    response_model=DataResponseModel[SrdAssessmentModel],
)
async def get_site_srd_assessment(
    request: Request,
    assessment_id: int,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    result = await SrdService.get_assessment_services(query_db, assessment_id, current_guest.user_id)
    logger.info(f'获取 SRD 评估 {assessment_id} 成功')

    return ResponseUtil.success(data=result)


# 导出走两条路而不是一条，与上面「示例公开 / 真实评估要登录」的分法一致：
# 示例是给没有账号的访客看形态的，导出按钮在那份结果上也得能按。两条路的排版共用
# 同一个 `build_assessment_xlsx`，出参完全一致。
#
# 文件名由前端给（照抄后台 `download()` 的做法）：这里回的是裸字节流，
# 中文文件名进 `Content-Disposition` 还要 RFC 5987 编码，交给浏览器侧省一层。


@action_site_controller.get(
    '/srd/sample/export',
    summary='导出 SRD 示例评估为 Excel',
    description='官网公开接口，返回示例评估的 xlsx 文件流',
    response_class=Response,
)
@ApiRateLimit(namespace=ApiNamespace.ACTION_SRD_EXPORT, preset=ApiRateLimitPreset.USER_RESOURCE_EXPORT, scope='ip')
async def export_site_srd_sample(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    lang: Annotated[str, Query(description='导出语言（zh / en）')] = 'zh',
) -> Response:
    content = await SrdService.export_assessment_services(query_db, lang=lang)
    logger.info('导出 SRD 示例评估成功')

    return ResponseUtil.streaming(data=bytes2file_response(content), media_type=XLSX_MEDIA_TYPE)


@action_site_controller.get(
    '/srd/assessments/{assessment_id}/export',
    summary='导出一次 SRD 评估为 Excel',
    description='三张工作表：概览 / 领域 / 条目明细；只能导出本人的记录',
    response_class=Response,
)
@ApiRateLimit(namespace=ApiNamespace.ACTION_SRD_EXPORT, preset=ApiRateLimitPreset.USER_RESOURCE_EXPORT, scope='ip')
async def export_site_srd_assessment(
    request: Request,
    assessment_id: int,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
    lang: Annotated[str, Query(description='导出语言（zh / en）')] = 'zh',
) -> Response:
    content = await SrdService.export_assessment_services(query_db, assessment_id, current_guest.user_id, lang)
    logger.info(f'导出 SRD 评估 {assessment_id} 成功')

    return ResponseUtil.streaming(data=bytes2file_response(content), media_type=XLSX_MEDIA_TYPE)


@action_site_controller.delete(
    '/srd/assessments/{assessment_id}',
    summary='删除一条 SRD 评估历史',
    description='逻辑删除，只能删本人的记录',
    response_model=ResponseBaseModel,
)
async def delete_site_srd_assessment(
    request: Request,
    assessment_id: int,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    result = await SrdService.delete_history_services(query_db, assessment_id, current_guest.user_id)
    logger.info(f'删除 SRD 评估 {assessment_id} 成功')

    return ResponseUtil.success(msg=result.message)


# ---------------------------------------------------------------- 报告助手第三步：checklist 逐条校验
#
# 提交接口会触发几十次模型调用，必须挂限流且要求访客登录 —— 匿名放开等于把账单交给公网。
#
# 六个口：提交 / 轮询 / 停止 / 历史 / 详情 / 删除。014 起提交那一刻就落一行台账
# （`action_report_review`），所以刷新页面之后还能从历史里把这次校验找回来，
# 跑挂了的任务也留得下痕迹。稿件正文随台账入库，用户可随时删除（删除是真删正文）。


@action_site_controller.post(
    '/checklist-review',
    summary='提交稿件做 checklist 逐条校验',
    description=(
        '报告助手第三步。提交后立即返回 sessionId 与 reviewId，结果通过状态接口轮询获取。'
        '**reviewId 要存下来**：刷新页面后靠它从历史里找回这次校验'
    ),
    response_model=DataResponseModel[ChecklistReviewSubmitResultModel],
)
@ApiRateLimit(namespace=ApiNamespace.ACTION_CHECKLIST_REVIEW, preset=ApiRateLimitPreset.USER_RESOURCE_EXECUTION)
async def submit_site_checklist_review(
    request: Request,
    submit: ChecklistReviewSubmitModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    result = await ChecklistReviewService.submit_review_services(query_db, submit, current_guest.user_id)
    logger.info(f'checklist 校验任务已提交：{result.session_id}（记录 {result.review_id}）')

    return ResponseUtil.success(data=result, msg='已提交，正在校验')


@action_site_controller.get(
    '/checklist-reviews',
    summary='我的 checklist 校验历史',
    description=(
        '报告助手第三步的历史列表，只返回本人的记录，不带逐条判定与稿件正文。'
        '顺带对账：用户关掉页面后没人再轮询，这里对未终结的记录补查一次 worker 状态'
    ),
    response_model=DataResponseModel[list[ReportReviewHistoryModel]],
)
async def get_site_checklist_review_history(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    result = await ChecklistReviewService.list_history_services(query_db, current_guest.user_id)

    return ResponseUtil.success(data=result)


# 注意路由顺序与形状：这条是 `/checklist-reviews/{id}`（复数，按记录id 取历史详情），
# 下面那条是 `/checklist-review/{session_id}`（单数，按任务id 轮询）。两者不同路径不会撞，
# 但改名时别把复数改没了 —— 那会让详情把轮询的路径吃掉
@action_site_controller.get(
    '/checklist-reviews/{review_id}',
    summary='取一次校验的完整结果',
    description='历史回看。带逐条判定、原文引用、全稿一致性与当时提交的稿件正文',
    response_model=DataResponseModel[ReportReviewModel],
)
async def get_site_checklist_review_detail(
    request: Request,
    review_id: int,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    result = await ChecklistReviewService.get_review_services(query_db, review_id, current_guest.user_id)
    logger.info(f'获取 checklist 校验记录 {review_id} 成功')

    return ResponseUtil.success(data=result)


@action_site_controller.delete(
    '/checklist-reviews/{review_id}',
    summary='删除一条校验历史',
    description='记录逻辑删，**稿件正文与原文引用物理删** —— 用户点删除时期待的是「那篇稿子没了」',
    response_model=ResponseBaseModel,
)
async def delete_site_checklist_review(
    request: Request,
    review_id: int,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    result = await ChecklistReviewService.delete_history_services(query_db, review_id, current_guest.user_id)
    logger.info(f'删除 checklist 校验记录 {review_id} 成功')

    return ResponseUtil.success(msg=result.message)


@action_site_controller.get(
    '/checklist-review/{session_id}',
    summary='查询 checklist 校验任务状态',
    description='报告助手第三步的轮询接口，完成后 result 里带逐条判定，并顺手把结果落库',
    response_model=DataResponseModel[ChecklistReviewStateModel],
)
async def get_site_checklist_review(
    request: Request,
    session_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    result = await ChecklistReviewService.review_state_services(query_db, session_id, current_guest.user_id)
    logger.info(f'查询 checklist 校验任务 {session_id} 状态成功')

    return ResponseUtil.success(data=result)


@action_site_controller.post(
    '/checklist-review/{session_id}/stop',
    summary='停止 checklist 校验任务',
    description='报告助手第三步的中止按钮。只能停自己的任务',
    response_model=ResponseBaseModel,
)
async def stop_site_checklist_review(
    request: Request,
    session_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    result = await ChecklistReviewService.stop_review_services(query_db, session_id, current_guest.user_id)
    logger.info(f'已请求停止 checklist 校验任务 {session_id}')

    return ResponseUtil.success(msg=result.message)


# ---------------------------------------------------------------- 报告助手第二步：报告草稿
#
# 六个口全部要访客登录：草稿是用户未发表的研究内容，匿名可读写等于把它挂到公网上。
# 越权保护在 DAO 的 where 里，服务层对「不存在」与「不是你的」返回同一句话
# —— 分开报的话，拿 draft_id 逐个试就能探出别人有几份草稿。


@action_site_controller.get(
    '/report-drafts',
    summary='我的报告草稿列表',
    description='报告助手第二步。只返回本人的草稿，不带逐条正文（列表页用不上）',
    response_model=DataResponseModel[list[ReportDraftModel]],
)
async def get_site_report_drafts(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    result = await ReportDraftService.list_drafts_services(query_db, current_guest.user_id)
    logger.info('获取报告草稿列表成功')

    return ResponseUtil.success(data=result)


@action_site_controller.post(
    '/report-drafts',
    summary='新建一份报告草稿',
    description='报告助手第二步。按第一步匹配到的规范建，条目为空的规范不许建',
    response_model=DataResponseModel[ReportDraftModel],
)
@ApiRateLimit(namespace=ApiNamespace.ACTION_REPORT_DRAFT, preset=ApiRateLimitPreset.USER_COMMON_MUTATION)
async def create_site_report_draft(
    request: Request,
    create: ReportDraftCreateModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    result = await ReportDraftService.create_draft_services(query_db, create, current_guest.user_id)
    logger.info(f'新建报告草稿 {result.draft_id} 成功')

    return ResponseUtil.success(data=result, msg='已新建草稿')


# 导入口在**第二步**，不在第三步 —— 第三步只产出只读判定，导进去之后第四步没东西可写回、
# 第五步整个导不出、下次再来还得重新粘一遍。挂限流：解析 + 几十次模型调用，比新建草稿重得多。
@action_site_controller.post(
    '/report-drafts/import',
    summary='导入已有稿件，建草稿并映射到 checklist 条目',
    description=(
        '报告助手第二步的第二条路。上传 docx/pdf/txt/md → 解析 → 建草稿并存原稿 → '
        '提交条目映射任务。**建草稿是同步的**（立刻回 draftId），映射是异步的，'
        '拿 sessionId 走 `GET /checklist-review/{sessionId}` 轮询；跑完会把匹配到的'
        '原文段落回填进条目框，空框就是「没覆盖到的条目」。'
        '原稿整篇另存（`source_text`），**导出正文以它为准** —— 条目框只是对照与改写的工作面'
    ),
    response_model=DataResponseModel[DraftImportResultModel],
)
@ApiRateLimit(namespace=ApiNamespace.ACTION_CHECKLIST_REVIEW, preset=ApiRateLimitPreset.USER_RESOURCE_EXECUTION)
async def import_site_report_draft(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
    file: Annotated[UploadFile, File(description='稿件文件（docx/pdf/txt/md）')],
    guideline_code: Annotated[str, Form(alias='guidelineCode', description='规范代号')],
    study_type_key: Annotated[str, Form(alias='studyTypeKey', description='研究类型，仅留档')] = '',
    title: Annotated[str, Form(description='草稿名称，留空由后端起')] = '',
    lang: Annotated[str, Query(description='判定语言 zh/en')] = 'zh',
) -> Response:
    result = await ReportDraftService.import_manuscript_services(
        query_db,
        current_guest.user_id,
        guideline_code=guideline_code,
        study_type_key=study_type_key,
        title=title,
        filename=file.filename or '',
        data=await file.read(),
        locale='en' if lang == 'en' else 'zh',
    )
    logger.info(f'导入稿件建草稿 {result.draft_id}，映射任务 {result.session_id}')

    return ResponseUtil.success(data=result, msg='已导入，正在匹配条目')


@action_site_controller.get(
    '/report-drafts/{draft_id}',
    summary='取一份报告草稿详情',
    description='报告助手第二步。带逐条目正文与完成度统计',
    response_model=DataResponseModel[ReportDraftModel],
)
async def get_site_report_draft(
    request: Request,
    draft_id: int,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    result = await ReportDraftService.get_draft_services(query_db, draft_id, current_guest.user_id)
    logger.info(f'获取报告草稿 {draft_id} 成功')

    return ResponseUtil.success(data=result)


@action_site_controller.put(
    '/report-drafts/{draft_id}',
    summary='保存一份报告草稿',
    description='报告助手第二步。**整体覆盖**：传进来的 items 就是全部正文，没带上的条目会被清空',
    response_model=DataResponseModel[ReportDraftModel],
)
# 前端是「停止输入若干秒后自动保存」，天然高频，走 USER_INTERACTIVE_HIGH_FREQ 而不是
# 普通写接口那一档 —— 后者 24 次/2 分钟，正常编辑就会被限流拦下，用户看到的是「保存失败」
@ApiRateLimit(namespace=ApiNamespace.ACTION_REPORT_DRAFT, preset=ApiRateLimitPreset.USER_INTERACTIVE_HIGH_FREQ)
async def save_site_report_draft(
    request: Request,
    draft_id: int,
    save: ReportDraftSaveModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    result = await ReportDraftService.save_draft_services(query_db, draft_id, save, current_guest.user_id)
    logger.info(f'保存报告草稿 {draft_id} 成功')

    return ResponseUtil.success(data=result, msg='已保存')


@action_site_controller.delete(
    '/report-drafts/{draft_id}',
    summary='删除一份报告草稿',
    description='报告助手第二步。逻辑删除，只能删本人的',
    response_model=ResponseBaseModel,
)
@ApiRateLimit(namespace=ApiNamespace.ACTION_REPORT_DRAFT, preset=ApiRateLimitPreset.USER_DESTRUCTIVE_MUTATION)
async def delete_site_report_draft(
    request: Request,
    draft_id: int,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    result = await ReportDraftService.delete_draft_services(query_db, draft_id, current_guest.user_id)
    logger.info(f'删除报告草稿 {draft_id} 成功')

    return ResponseUtil.success(msg=result.message)


@action_site_controller.post(
    '/report-drafts/{draft_id}/compose',
    summary='把草稿合成为报告初稿正文',
    description=(
        '报告助手第二步的「一键生成初稿」。返回纯文本正文，可直接送第三步逐条校验。'
        '正文按章节组织，**不含 checklist 条目要求原文**（那会被第三步误判成已报告）'
    ),
    response_model=DataResponseModel[ReportDraftComposeModel],
)
@ApiRateLimit(namespace=ApiNamespace.ACTION_REPORT_DRAFT, preset=ApiRateLimitPreset.USER_RESOURCE_GENERATE)
async def compose_site_report_draft(
    request: Request,
    draft_id: int,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
    lang: Annotated[str, Query(description='初稿语言（zh / en）')] = 'zh',
) -> Response:
    result = await ReportDraftService.compose_draft_services(query_db, draft_id, current_guest.user_id, lang)
    logger.info(f'合成报告草稿 {draft_id} 初稿成功')

    return ResponseUtil.success(data=result)


@action_site_controller.get(
    '/report-drafts/{draft_id}/export',
    summary='导出报告草稿（第五步）',
    description=(
        '三种格式各答一个问题：**docx** 稿件本身（按章节分节 + 附录对照表）· '
        '**xlsx** 投稿随附的 checklist 对照表 · **json** 结构化留档。'
        '数据源是业务库而不是第二步那份合成文本 —— 那是瞬时产物，用户可能压根没点过「生成初稿」。'
        '**不出 PDF**：服务端生成中文 PDF 要在服务器装中文字体，字体缺失时是整篇方块字而不是报错，'
        '这种失败方式在导出场景代价太高；docx 自己另存更可靠'
    ),
    response_class=Response,
)
@ApiRateLimit(namespace=ApiNamespace.ACTION_REPORT_DRAFT, preset=ApiRateLimitPreset.USER_RESOURCE_EXPORT)
async def export_site_report_draft(
    request: Request,
    draft_id: int,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
    fmt: Annotated[str, Query(description='导出格式（docx / xlsx / json）')] = 'docx',
    lang: Annotated[str, Query(description='导出语言（zh / en）')] = 'zh',
) -> Response:
    content, filename, media_type, _ext = await ReportDraftService.export_draft_services(
        query_db, draft_id, current_guest.user_id, fmt, lang
    )
    logger.info(f'导出报告草稿 {draft_id}（{fmt}）成功')

    # media_type 必须显式给：本站错误走「HTTP 200 + code≠200」的 JSON 信封，
    # 前端靠这个头把「一份文件」和「同一条通道上回来的错误信封」分开（useAuth.authedBlob）。
    # 文件名走 RFC 5987 的 filename*，否则中文名在部分浏览器上是乱码
    return ResponseUtil.streaming(
        data=bytes2file_response(content),
        media_type=media_type,
        headers={'Content-Disposition': f"attachment; filename*=UTF-8''{quote(filename)}"},
    )

# ---------------------------------------------------------------- 第三步判定 · 第四步改写
#
# 这三个口把 2→3→4→2 那个环的后半段接上：第四步按第三步的判定列出工作清单、逐条改写、
# 确认后写回第二步的草稿条目。全部要访客登录 —— 读写的都是用户自己的草稿。
#
# **判定的写入口不在这一段**：014 起由 `/checklist-review/{session_id}` 轮询时落库
# （原先前端在拿到结果那一刻另调 `POST /report-reviews`，那个口已撤 ——
# 用户中途刷新就没人来落库，而且两条写入路径并存必然漂移）。


@action_site_controller.get(
    '/report-drafts/{draft_id}/review',
    summary='取某份草稿最近一次校验（第四步工作清单）',
    description='没校验过不算错，返回 reviewId 为空的壳，前台据此提示先去第三步跑一次',
    response_model=DataResponseModel[ReportReviewModel],
)
async def get_site_report_review(
    request: Request,
    draft_id: int,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    result = await ReportReviewService.get_latest_review_services(query_db, draft_id, current_guest.user_id)

    return ResponseUtil.success(data=result)


@action_site_controller.post(
    '/report-assist',
    summary='第四步：对某一条 checklist 条目做续写 / 润色 / 中译英',
    description=(
        '**必须带 draftId + itemId**：条目要求与已写正文都由后端从库里取，不由前端传。'
        '结果不落库，由用户显式「采用」后走 `/report-assist/apply`。'
        '同步调用模型池（`ai_models`），秒级返回，不走 Redis 队列'
    ),
    response_model=DataResponseModel[AssistResultModel],
)
@ApiRateLimit(namespace=ApiNamespace.ACTION_REPORT_DRAFT, preset=ApiRateLimitPreset.USER_RESOURCE_GENERATE)
async def assist_site_report_draft(
    request: Request,
    assist_req: AssistRequestModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
    lang: Annotated[str, Query(description='界面语言（zh / en）')] = 'zh',
) -> Response:
    result = await ReportReviewService.assist_services(query_db, assist_req, current_guest.user_id, lang)
    logger.info(f'草稿 {assist_req.draft_id} 条目 {assist_req.item_id} 执行 {assist_req.action} 成功')

    return ResponseUtil.success(data=result)


@action_site_controller.put(
    '/report-assist/apply',
    summary='把第四步的改写结果写回第二步的草稿条目',
    description='**单条覆盖**，不套用第二步的整体覆盖语义——那会把没带上的其余条目清空',
    response_model=DataResponseModel[ReportDraftModel],
)
async def apply_site_report_assist(
    request: Request,
    apply_req: AssistApplyModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    result = await ReportReviewService.apply_services(query_db, apply_req, current_guest.user_id)
    logger.info(f'草稿 {apply_req.draft_id} 条目 {apply_req.item_id} 写回成功')

    return ResponseUtil.success(data=result)


@action_site_controller.post(
    '/report-trails',
    summary='追加一条操作留痕',
    description=(
        '文档 3.4 的「操作日志」。**只收数字与枚举**：事件类型、条目计数、字符数、规范代号。'
        '人读的那句话由前端按 i18n 渲染，库里没有它 —— 存渲染好的句子迟早会混进稿件正文片段，'
        '第三步「稿件不入库」的承诺就绕过去了。'
        '第四步写回草稿的那条留痕由服务端自己记，不走这个口'
    ),
    response_model=DataResponseModel[TrailModel],
)
async def add_site_report_trail(
    request: Request,
    add_trail: TrailAddModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
) -> Response:
    result = await ReportTrailService.add_trail_services(query_db, add_trail, current_guest.user_id)

    return ResponseUtil.success(data=result)


@action_site_controller.get(
    '/report-trails',
    summary='取操作留痕（最近的在前）',
    description='只能看自己的。`draftId` 可选，用来只看某一份草稿的记录',
    response_model=DataResponseModel[list[TrailModel]],
)
async def get_site_report_trails(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_guest: Annotated[GuestInfoModel, GuestUserDependency()],
    draft_id: Annotated[int | None, Query(alias='draftId', description='只看某份草稿')] = None,
) -> Response:
    result = await ReportTrailService.get_trail_list_services(query_db, current_guest.user_id, draft_id)

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
