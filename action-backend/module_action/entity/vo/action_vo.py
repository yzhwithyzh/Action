from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel
from pydantic_validation_decorator import NotBlank, Size, Xss

from exceptions.exception import ModelValidatorException

DupLevel = Literal['none', 'low', 'mod', 'high']


class ActionBaseModel(BaseModel):
    """
    官网模块公共配置：出入参一律驼峰，支持从 ORM 对象构造
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)


# ---------------------------------------------------------------- 新闻动态


class NewsModel(ActionBaseModel):
    """
    官网新闻动态
    """

    news_id: int | None = Field(default=None, description='新闻id')
    category_zh: str | None = Field(default=None, description='分类（中文）')
    category_en: str | None = Field(default=None, description='分类（英文）')
    title_zh: str | None = Field(default=None, description='标题（中文）')
    title_en: str | None = Field(default=None, description='标题（英文）')
    summary_zh: str | None = Field(default=None, description='摘要（中文）')
    summary_en: str | None = Field(default=None, description='摘要（英文）')
    content_zh: str | None = Field(default=None, description='正文（中文）')
    content_en: str | None = Field(default=None, description='正文（英文）')
    thumb_url: str | None = Field(default=None, description='缩略图地址')
    link_url: str | None = Field(default=None, description='跳转链接（站内路由或外部URL）')
    is_external: Literal['0', '1'] | None = Field(default=None, description='是否外部链接（0否 1是）')
    publish_date: date | None = Field(default=None, description='发布日期')
    is_top: Literal['0', '1'] | None = Field(default=None, description='是否置顶（0否 1是）')
    sort_num: int | None = Field(default=None, description='显示顺序')
    status: Literal['0', '1'] | None = Field(default=None, description='状态（0正常 1停用）')
    create_by: str | None = Field(default=None, description='创建者')
    create_time: datetime | None = Field(default=None, description='创建时间')
    update_by: str | None = Field(default=None, description='更新者')
    update_time: datetime | None = Field(default=None, description='更新时间')
    remark: str | None = Field(default=None, description='备注')

    @Xss(field_name='title_zh', message='标题不能包含脚本字符')
    @NotBlank(field_name='title_zh', message='中文标题不能为空')
    @Size(field_name='title_zh', min_length=0, max_length=300, message='中文标题不能超过300个字符')
    def get_title_zh(self) -> str | None:
        return self.title_zh

    def validate_fields(self) -> None:
        self.get_title_zh()


class NewsQueryModel(NewsModel):
    """
    新闻不分页查询模型
    """

    begin_time: str | None = Field(default=None, description='开始时间')
    end_time: str | None = Field(default=None, description='结束时间')


class NewsPageQueryModel(NewsQueryModel):
    """
    新闻分页查询模型
    """

    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


class DeleteNewsModel(BaseModel):
    """
    删除新闻模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    news_ids: str = Field(description='需要删除的新闻id，多个以逗号分隔')


# ---------------------------------------------------------------- 报告规范目录


class GuidelineModel(ActionBaseModel):
    """
    官网报告规范目录
    """

    guideline_id: int | None = Field(default=None, description='规范id')
    code: str | None = Field(default=None, description='规范代号')
    name_zh: str | None = Field(default=None, description='名称（中文）')
    name_en: str | None = Field(default=None, description='名称（英文）')
    study_type: str | None = Field(default=None, description='适用研究类型')
    summary_zh: str | None = Field(default=None, description='简介（中文）')
    summary_en: str | None = Field(default=None, description='简介（英文）')
    version: str | None = Field(default=None, description='版本')
    file_url_zh: str | None = Field(
        default=None, description='中文版下载地址（文件存阿里云 OSS，由后台上传；初始为空串）'
    )
    file_url_en: str | None = Field(
        default=None, description='英文版下载地址（文件存阿里云 OSS，由后台上传；初始为空串）'
    )
    external_url: str | None = Field(default=None, description='外部官方链接（如已发表共识的 DOI 或官方站点）')
    logo_url: str | None = Field(default=None, description='标识图地址')
    release_state: Literal['open', 'beta', 'soon'] | None = Field(default=None, description='开放状态')
    sort_num: int | None = Field(default=None, description='显示顺序')
    status: Literal['0', '1'] | None = Field(default=None, description='状态（0正常 1停用）')
    create_by: str | None = Field(default=None, description='创建者')
    create_time: datetime | None = Field(default=None, description='创建时间')
    update_by: str | None = Field(default=None, description='更新者')
    update_time: datetime | None = Field(default=None, description='更新时间')
    remark: str | None = Field(default=None, description='备注')

    @Xss(field_name='name_zh', message='名称不能包含脚本字符')
    @NotBlank(field_name='name_zh', message='中文名称不能为空')
    @Size(field_name='name_zh', min_length=0, max_length=300, message='中文名称不能超过300个字符')
    def get_name_zh(self) -> str | None:
        return self.name_zh

    @NotBlank(field_name='code', message='规范代号不能为空')
    @Size(field_name='code', min_length=0, max_length=64, message='规范代号不能超过64个字符')
    def get_code(self) -> str | None:
        return self.code

    def validate_fields(self) -> None:
        self.get_code()
        self.get_name_zh()


class GuidelinePageQueryModel(GuidelineModel):
    """
    报告规范分页查询模型
    """

    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


class DeleteGuidelineModel(BaseModel):
    """
    删除报告规范模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    guideline_ids: str = Field(description='需要删除的规范id，多个以逗号分隔')


# ---------------------------------------------------------------- 研究类型


class StudyTypeStatModel(ActionBaseModel):
    """
    研究类型的统计方法推荐条目
    """

    text_zh: str | None = Field(default=None, description='推荐说明（中文）')
    text_en: str | None = Field(default=None, description='推荐说明（英文）')


class StudyTypeModel(ActionBaseModel):
    """
    研究类型（含关联规范与统计推荐）
    """

    type_id: int | None = Field(default=None, description='类型id')
    type_key: str | None = Field(default=None, description='类型标识')
    name_zh: str | None = Field(default=None, description='名称（中文）')
    name_en: str | None = Field(default=None, description='名称（英文）')
    hot_guideline: str | None = Field(default=None, description='重点推荐规范代号')
    sort_num: int | None = Field(default=None, description='显示顺序')
    guidelines: list[str] = Field(default_factory=list, description='关联规范代号列表')
    stats: list[StudyTypeStatModel] = Field(default_factory=list, description='统计方法推荐')


# ---------------------------------------------------------------- CFIR


class CfirStrategyModel(ActionBaseModel):
    """
    CFIR 构念对应的实施策略
    """

    strategy_id: int | None = Field(default=None, description='策略id')
    name_zh: str | None = Field(default=None, description='策略名称（中文）')
    name_en: str | None = Field(default=None, description='策略名称（英文）')
    detail_zh: str | None = Field(default=None, description='策略说明（中文）')
    detail_en: str | None = Field(default=None, description='策略说明（英文）')
    source_zh: str | None = Field(default=None, description='来源（中文）')
    source_en: str | None = Field(default=None, description='来源（英文）')


class CfirConstructModel(ActionBaseModel):
    """
    CFIR 构念（障碍点）
    """

    construct_id: int | None = Field(default=None, description='构念id')
    code: str | None = Field(default=None, description='构念标识')
    name_zh: str | None = Field(default=None, description='名称（中文）')
    name_en: str | None = Field(default=None, description='名称（英文）')
    hint_zh: str | None = Field(default=None, description='释义（中文）')
    hint_en: str | None = Field(default=None, description='释义（英文）')
    severity: Literal['h', 'm', 'l'] | None = Field(default=None, description='严重度')
    strategies: list[CfirStrategyModel] = Field(default_factory=list, description='应对策略')


class CfirDomainModel(ActionBaseModel):
    """
    CFIR 领域
    """

    domain_id: int | None = Field(default=None, description='领域id')
    seq: int | None = Field(default=None, description='领域序号')
    name_zh: str | None = Field(default=None, description='名称（中文）')
    name_en: str | None = Field(default=None, description='名称（英文）')
    constructs: list[CfirConstructModel] = Field(default_factory=list, description='构念列表')


# ---------------------------------------------------------------- ERIC / RE-AIM


class EricCategoryModel(ActionBaseModel):
    """
    ERIC 策略分类
    """

    cat_key: str | None = Field(default=None, description='分类标识')
    name_zh: str | None = Field(default=None, description='名称（中文）')
    name_en: str | None = Field(default=None, description='名称（英文）')


class EricStrategyModel(ActionBaseModel):
    """
    ERIC 实施策略
    """

    eric_id: int | None = Field(default=None, description='策略id')
    category: str | None = Field(default=None, description='策略分类标识')
    name_zh: str | None = Field(default=None, description='名称（中文）')
    name_en: str | None = Field(default=None, description='名称（英文）')
    detail_zh: str | None = Field(default=None, description='说明（中文）')
    detail_en: str | None = Field(default=None, description='说明（英文）')
    map_zh: str | None = Field(default=None, description='对应CFIR构念（中文）')
    map_en: str | None = Field(default=None, description='对应CFIR构念（英文）')


class ReaimDimensionModel(ActionBaseModel):
    """
    RE-AIM 维度
    """

    dim_id: int | None = Field(default=None, description='维度id')
    letter: str | None = Field(default=None, description='维度首字母')
    name_zh: str | None = Field(default=None, description='名称（中文）')
    name_en: str | None = Field(default=None, description='名称（英文）')
    sub_title: str | None = Field(default=None, description='副标题')
    definition_zh: str | None = Field(default=None, description='定义（中文）')
    definition_en: str | None = Field(default=None, description='定义（英文）')
    measure_zh: str | None = Field(default=None, description='测量指标（中文）')
    measure_en: str | None = Field(default=None, description='测量指标（英文）')
    score_text: str | None = Field(default=None, description='示例得分')


# ---------------------------------------------------------------- SRD


class SrdItemModel(ActionBaseModel):
    """
    SRD 评估条目
    """

    item_id: int | None = Field(default=None, description='条目id')
    code: str | None = Field(default=None, description='条目编号')
    question_zh: str | None = Field(default=None, description='评估问题（中文）')
    question_en: str | None = Field(default=None, description='评估问题（英文）')
    level: DupLevel | None = Field(default=None, description='重复程度')
    pct: int | None = Field(default=None, description='重复度百分比')
    basis_zh: str | None = Field(default=None, description='判定依据（中文）')
    basis_en: str | None = Field(default=None, description='判定依据（英文）')
    cite_a_zh: str | None = Field(default=None, description='综述A原文引用（中文）')
    cite_a_en: str | None = Field(default=None, description='综述A原文引用（英文）')
    cite_b_zh: str | None = Field(default=None, description='综述B原文引用（中文）')
    cite_b_en: str | None = Field(default=None, description='综述B原文引用（英文）')


class SrdGroupModel(ActionBaseModel):
    """
    SRD 评估条目分组
    """

    group_id: int | None = Field(default=None, description='分组id')
    code: str | None = Field(default=None, description='分组编号')
    name_zh: str | None = Field(default=None, description='名称（中文）')
    name_en: str | None = Field(default=None, description='名称（英文）')
    items: list[SrdItemModel] = Field(default_factory=list, description='条目列表')


class SrdDomainModel(ActionBaseModel):
    """
    SRD 评估领域
    """

    domain_id: int | None = Field(default=None, description='领域id')
    seq: int | None = Field(default=None, description='领域序号')
    name_zh: str | None = Field(default=None, description='名称（中文）')
    name_en: str | None = Field(default=None, description='名称（英文）')
    is_key: Literal['0', '1'] | None = Field(default=None, description='是否关键领域')
    level: DupLevel | None = Field(default=None, description='重复程度')
    pct: int | None = Field(default=None, description='重复度百分比')
    groups: list[SrdGroupModel] = Field(default_factory=list, description='分组列表')


class SrdAssessmentModel(ActionBaseModel):
    """
    SRD 系统综述重复性评估（含完整层级）
    """

    assessment_id: int | None = Field(default=None, description='评估id')
    review_a_title_zh: str | None = Field(default=None, description='综述A标题（中文）')
    review_a_title_en: str | None = Field(default=None, description='综述A标题（英文）')
    review_b_title_zh: str | None = Field(default=None, description='综述B标题（中文）')
    review_b_title_en: str | None = Field(default=None, description='综述B标题（英文）')
    overall_level: DupLevel | None = Field(default=None, description='整体判定')
    overall_pct: int | None = Field(default=None, description='整体重复度百分比')
    overall_reason_zh: str | None = Field(default=None, description='整体判定理由（中文）')
    overall_reason_en: str | None = Field(default=None, description='整体判定理由（英文）')
    is_sample: Literal['0', '1'] | None = Field(default=None, description='是否示例数据')
    domains: list[SrdDomainModel] = Field(default_factory=list, description='领域列表')


# ---------------------------------------------------------------- 协作申请


class CollabRequestModel(ActionBaseModel):
    """
    协作与专家咨询申请
    """

    request_id: int | None = Field(default=None, description='申请id')
    request_type: Literal['consult', 'collab', 'feedback'] | None = Field(default=None, description='申请类型')
    applicant: str | None = Field(default=None, description='申请人')
    organization: str | None = Field(default=None, description='所属机构')
    email: str | None = Field(default=None, description='邮箱')
    phone: str | None = Field(default=None, description='联系电话')
    topic: str | None = Field(default=None, description='主题')
    content: str | None = Field(default=None, description='正文')
    source_lang: Literal['zh', 'en'] | None = Field(default=None, description='提交时界面语言')
    source_ip: str | None = Field(default=None, description='来源ip')
    handle_status: Literal['0', '1', '2', '3'] | None = Field(default=None, description='处理状态')
    handle_by: str | None = Field(default=None, description='处理人')
    handle_time: datetime | None = Field(default=None, description='处理时间')
    handle_remark: str | None = Field(default=None, description='处理备注')
    create_time: datetime | None = Field(default=None, description='提交时间')


class CollabRequestSubmitModel(BaseModel):
    """
    官网表单提交入参

    公开接口，字段独立定义而非复用 CollabRequestModel：
    避免调用方伪造 handle_status / handle_by 等仅后台可写的字段。
    """

    model_config = ConfigDict(alias_generator=to_camel)

    request_type: Literal['consult', 'collab', 'feedback'] = Field(default='consult', description='申请类型')
    applicant: str = Field(min_length=1, max_length=100, description='申请人')
    organization: str | None = Field(default=None, max_length=300, description='所属机构')
    email: EmailStr = Field(description='邮箱')
    phone: str | None = Field(default=None, max_length=50, description='联系电话')
    topic: str | None = Field(default=None, max_length=300, description='主题')
    content: str = Field(min_length=1, max_length=5000, description='正文')
    source_lang: Literal['zh', 'en'] = Field(default='zh', description='提交时界面语言')


class CollabRequestPageQueryModel(CollabRequestModel):
    """
    协作申请分页查询模型
    """

    begin_time: str | None = Field(default=None, description='开始时间')
    end_time: str | None = Field(default=None, description='结束时间')
    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


# ---------------------------------------------------------------- 官网访客账号
#
# 以下入参一律用裸 BaseModel 独立定义，不复用 UserModel / ActionBaseModel：
# 这些是完全公开的匿名接口，复用完整实体等于让调用方有机会伪造 userType、status、
# delFlag 等仅服务端可写的字段。
#
# 文本字段的 @Xss / 非空白校验必须落在本层：UserModel 上的同类校验器只在显式调用
# validate_fields() 时才跑，而访客注册走的 UserService.add_user_services 从不调用它。

# bcrypt 限制的是密码的 UTF-8 字节数而非字符数：25 个中文就是 75 字节，
# max_length=50（字符）完全拦不住，落到 bcrypt.hashpw/checkpw 会抛 ValueError
# 变成 500，且兜底 handler 会把英文原文回给匿名调用方。必须在入参层按字节拦。
BCRYPT_MAX_PASSWORD_BYTES = 72


def _reject_oversize_password(password: str | None, field_label: str) -> None:
    """
    校验密码的UTF-8字节长度不超过bcrypt上限

    :param password: 待校验的密码，None表示未提供
    :param field_label: 出错提示里使用的字段名称
    :return: None
    """
    if password is not None and len(password.encode('utf-8')) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ModelValidatorException(message=f'{field_label}长度不能超过{BCRYPT_MAX_PASSWORD_BYTES}个字节')


def _strip_optional_text(value: str | None) -> str | None:
    """
    去除可选自由文本两端空白，纯空白视为未填写

    :param value: 原始文本
    :return: 归一化后的文本，纯空白或空串返回None
    """
    if value is None:
        return None
    stripped = value.strip()

    return stripped or None


class GuestEmailCodeModel(BaseModel):
    """
    官网访客-发送邮箱验证码入参
    """

    model_config = ConfigDict(alias_generator=to_camel)

    email: EmailStr = Field(max_length=50, description='邮箱')
    scene: Literal['register', 'login'] = Field(description='验证码场景（register注册 login登录）')
    # 这一项是邮件正文选语言用的，与注册/登录入参不同，必须保留
    source_lang: Literal['zh', 'en'] = Field(default='zh', description='提交时界面语言')


class GuestRegisterModel(BaseModel):
    """
    官网访客-注册入参
    """

    model_config = ConfigDict(alias_generator=to_camel)

    email: EmailStr = Field(max_length=50, description='邮箱')
    code: str = Field(min_length=6, max_length=6, pattern=r'^\d{6}$', description='邮箱验证码')
    # 用户名写入 sys_user.nick_name（String(30)），登录标识始终是邮箱
    username: str = Field(min_length=1, max_length=30, description='用户名')
    institution: str | None = Field(default=None, max_length=300, description='所属机构')
    position: str | None = Field(default=None, max_length=100, description='职位')
    password: str = Field(min_length=6, max_length=50, description='密码')
    confirm_password: str = Field(min_length=6, max_length=50, description='确认密码')

    @field_validator('username', mode='after')
    @classmethod
    def strip_username(cls, value: str) -> str:
        """
        去除用户名两端空白，纯空白交由下方 NotBlank 拦截

        :param value: 原始用户名
        :return: 去除两端空白后的用户名
        """
        return value.strip()

    @field_validator('institution', 'position', mode='after')
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        """
        机构与职位去空白，纯空白按未填写处理

        :param value: 原始文本
        :return: 归一化后的文本
        """
        return _strip_optional_text(value)

    @model_validator(mode='after')
    @Xss(field_name='username', message='用户名不能包含脚本字符')
    @NotBlank(field_name='username', message='用户名不能为空')
    @Size(field_name='username', min_length=0, max_length=30, message='用户名长度不能超过30个字符')
    @Xss(field_name='institution', message='所属机构不能包含脚本字符')
    @Size(field_name='institution', min_length=0, max_length=300, message='所属机构长度不能超过300个字符')
    @Xss(field_name='position', message='职位不能包含脚本字符')
    @Size(field_name='position', min_length=0, max_length=100, message='职位长度不能超过100个字符')
    def check_text_fields(self) -> 'GuestRegisterModel':
        """
        校验自由文本字段（脚本字符、空白、长度）

        :return: 校验通过的入参对象
        """
        return self

    @model_validator(mode='after')
    def check_password(self) -> 'GuestRegisterModel':
        """
        校验密码字节长度不超过bcrypt上限

        :return: 校验通过的入参对象
        """
        _reject_oversize_password(self.password, '密码')
        _reject_oversize_password(self.confirm_password, '确认密码')

        return self


class GuestLoginModel(BaseModel):
    """
    官网访客-登录入参

    验证码登录与密码登录二选一，两者都传或都不传都视为非法入参。
    """

    model_config = ConfigDict(alias_generator=to_camel)

    email: EmailStr = Field(max_length=50, description='邮箱')
    code: str | None = Field(default=None, min_length=6, max_length=6, pattern=r'^\d{6}$', description='邮箱验证码')
    password: str | None = Field(default=None, min_length=1, max_length=50, description='密码')

    @model_validator(mode='after')
    def check_credential(self) -> 'GuestLoginModel':
        """
        校验验证码与密码恰好提供其中一项，并校验密码字节长度

        :return: 校验通过的入参对象
        """
        if bool(self.code) == bool(self.password):
            raise ModelValidatorException(message='请提供验证码或密码其中一项')
        # 登录路径同样要在入参层拦超长密码：否则 bcrypt.checkpw 抛 ValueError，
        # 「邮箱不存在」返回业务错误而「邮箱存在」返回 500，状态码本身就成了枚举信号
        _reject_oversize_password(self.password, '密码')

        return self


class GuestPublicInfoModel(BaseModel):
    """
    官网访客-对外暴露的访客信息

    刻意不含 user_id：内部身份识别用 GuestInfoModel，接口响应体一律用本模型，
    避免把 sys_user 的自增主键泄露给官网调用方。
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    email: str = Field(description='邮箱')
    username: str = Field(description='用户名')
    institution: str | None = Field(default=None, description='所属机构')
    position: str | None = Field(default=None, description='职位')


class GuestInfoModel(GuestPublicInfoModel):
    """
    官网访客-当前登录访客信息（内部使用，含用户id）
    """

    user_id: int = Field(description='用户id')

    def to_public(self) -> GuestPublicInfoModel:
        """
        转为对外返回体（剥掉user_id）

        :return: 对外访客信息
        """
        return GuestPublicInfoModel(
            email=self.email,
            username=self.username,
            institution=self.institution,
            position=self.position,
        )


class GuestTokenModel(BaseModel):
    """
    官网访客-登录/注册成功后的令牌信息
    """

    model_config = ConfigDict(alias_generator=to_camel)

    token: str = Field(description='访客令牌')
    guest: GuestPublicInfoModel = Field(description='访客信息')
