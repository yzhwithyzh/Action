from datetime import datetime

from sqlalchemy import CHAR, BigInteger, Column, Date, DateTime, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP

from config.database import Base


def _timestamp_second() -> DateTime:
    """
    对齐 DDL 的 `timestamp(0)` 秒级精度列类型

    SQLAlchemy 2.x 的通用 `DateTime` 不接受 `precision` 参数，只有方言类型才有；
    这里用 with_variant 让 PostgreSQL 走 `timestamp(0)`，其余方言仍退回通用类型，
    既与 sql/action-website-pg.sql 逐字对齐，又不把 DO 绑死在单一方言上。

    :return: 秒级精度的时间列类型
    """
    return DateTime().with_variant(TIMESTAMP(precision=0), 'postgresql')


class ActionNews(Base):
    """
    官网-新闻动态
    """

    __tablename__ = 'action_news'
    __table_args__ = {'comment': '官网-新闻动态'}

    news_id = Column(Integer, primary_key=True, autoincrement=True, comment='新闻id')
    category_zh = Column(String(50), nullable=True, server_default="''", comment='分类（中文）')
    category_en = Column(String(50), nullable=True, server_default="''", comment='分类（英文）')
    title_zh = Column(String(300), nullable=False, comment='标题（中文）')
    title_en = Column(String(500), nullable=True, server_default="''", comment='标题（英文）')
    summary_zh = Column(Text, nullable=True, comment='摘要（中文）')
    summary_en = Column(Text, nullable=True, comment='摘要（英文）')
    content_zh = Column(Text, nullable=True, comment='正文（中文）')
    content_en = Column(Text, nullable=True, comment='正文（英文）')
    thumb_url = Column(String(300), nullable=True, server_default="''", comment='缩略图地址')
    link_url = Column(String(500), nullable=True, server_default="''", comment='跳转链接（站内路由或外部URL）')
    is_external = Column(CHAR(1), nullable=True, server_default='0', comment='是否外部链接（0否 1是）')
    publish_date = Column(Date, nullable=True, comment='发布日期')
    is_top = Column(CHAR(1), nullable=True, server_default='0', comment='是否置顶（0否 1是）')
    sort_num = Column(Integer, nullable=True, server_default='0', comment='显示顺序')
    status = Column(CHAR(1), nullable=True, server_default='0', comment='状态（0正常 1停用）')
    del_flag = Column(CHAR(1), nullable=True, server_default='0', comment='删除标志（0存在 2删除）')
    create_by = Column(String(64), nullable=True, server_default="''", comment='创建者')
    create_time = Column(DateTime, nullable=True, comment='创建时间', default=datetime.now)
    update_by = Column(String(64), nullable=True, server_default="''", comment='更新者')
    update_time = Column(DateTime, nullable=True, comment='更新时间', default=datetime.now)
    remark = Column(String(500), nullable=True, comment='备注')


class ActionGuideline(Base):
    """
    官网-报告规范目录
    """

    __tablename__ = 'action_guideline'
    __table_args__ = {'comment': '官网-报告规范目录'}

    guideline_id = Column(Integer, primary_key=True, autoincrement=True, comment='规范id')
    code = Column(String(64), nullable=False, comment='规范代号（CONSORT/STRICTA/SPIRIT…）')
    name_zh = Column(String(300), nullable=False, comment='名称（中文）')
    name_en = Column(String(500), nullable=True, server_default="''", comment='名称（英文）')
    study_type = Column(String(64), nullable=True, server_default="''", comment='适用研究类型')
    summary_zh = Column(Text, nullable=True, comment='简介（中文）')
    summary_en = Column(Text, nullable=True, comment='简介（英文）')
    version = Column(String(64), nullable=True, server_default="''", comment='版本')
    file_url_zh = Column(
        String(500),
        nullable=True,
        server_default="''",
        comment='中文版下载地址（文件存阿里云 OSS，由后台上传；初始为空串）',
    )
    file_url_en = Column(
        String(500),
        nullable=True,
        server_default="''",
        comment='英文版下载地址（文件存阿里云 OSS，由后台上传；初始为空串）',
    )
    external_url = Column(
        String(500), nullable=True, server_default="''", comment='外部官方链接（如已发表共识的 DOI 或官方站点）'
    )
    logo_url = Column(String(300), nullable=True, server_default="''", comment='标识图地址')
    release_state = Column(String(32), nullable=True, server_default="'open'", comment='开放状态（open/beta/soon）')
    sort_num = Column(Integer, nullable=True, server_default='0', comment='显示顺序')
    status = Column(CHAR(1), nullable=True, server_default='0', comment='状态（0正常 1停用）')
    del_flag = Column(CHAR(1), nullable=True, server_default='0', comment='删除标志（0存在 2删除）')
    create_by = Column(String(64), nullable=True, server_default="''", comment='创建者')
    create_time = Column(DateTime, nullable=True, comment='创建时间', default=datetime.now)
    update_by = Column(String(64), nullable=True, server_default="''", comment='更新者')
    update_time = Column(DateTime, nullable=True, comment='更新时间', default=datetime.now)
    remark = Column(String(500), nullable=True, comment='备注')


class ActionStudyType(Base):
    """
    官网-研究类型
    """

    __tablename__ = 'action_study_type'
    __table_args__ = {'comment': '官网-研究类型'}

    type_id = Column(Integer, primary_key=True, autoincrement=True, comment='类型id')
    type_key = Column(String(32), nullable=False, comment='类型标识（rct/nrct/case/sr/obs）')
    name_zh = Column(String(200), nullable=False, comment='名称（中文）')
    name_en = Column(String(300), nullable=True, server_default="''", comment='名称（英文）')
    hot_guideline = Column(String(64), nullable=True, server_default="''", comment='重点推荐规范代号')
    sort_num = Column(Integer, nullable=True, server_default='0', comment='显示顺序')
    status = Column(CHAR(1), nullable=True, server_default='0', comment='状态（0正常 1停用）')
    create_by = Column(String(64), nullable=True, server_default="''", comment='创建者')
    create_time = Column(DateTime, nullable=True, comment='创建时间', default=datetime.now)
    update_by = Column(String(64), nullable=True, server_default="''", comment='更新者')
    update_time = Column(DateTime, nullable=True, comment='更新时间', default=datetime.now)


class ActionStudyTypeGuideline(Base):
    """
    官网-研究类型与报告规范关联
    """

    __tablename__ = 'action_study_type_guideline'
    __table_args__ = {'comment': '官网-研究类型与报告规范关联'}

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键')
    type_id = Column(Integer, nullable=False, comment='研究类型id')
    guideline_code = Column(String(64), nullable=False, comment='规范代号')
    sort_num = Column(Integer, nullable=True, server_default='0', comment='显示顺序')


class ActionStudyTypeStat(Base):
    """
    官网-研究类型统计方法推荐
    """

    __tablename__ = 'action_study_type_stat'
    __table_args__ = {'comment': '官网-研究类型统计方法推荐'}

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键')
    type_id = Column(Integer, nullable=False, comment='研究类型id')
    text_zh = Column(String(500), nullable=False, comment='推荐说明（中文）')
    text_en = Column(String(800), nullable=True, server_default="''", comment='推荐说明（英文）')
    sort_num = Column(Integer, nullable=True, server_default='0', comment='显示顺序')


class ActionCfirDomain(Base):
    """
    官网-CFIR领域
    """

    __tablename__ = 'action_cfir_domain'
    __table_args__ = {'comment': '官网-CFIR领域'}

    domain_id = Column(Integer, primary_key=True, autoincrement=True, comment='领域id')
    seq = Column(Integer, nullable=False, comment='领域序号')
    name_zh = Column(String(200), nullable=False, comment='名称（中文）')
    name_en = Column(String(300), nullable=True, server_default="''", comment='名称（英文）')
    status = Column(CHAR(1), nullable=True, server_default='0', comment='状态（0正常 1停用）')
    create_by = Column(String(64), nullable=True, server_default="''", comment='创建者')
    create_time = Column(DateTime, nullable=True, comment='创建时间', default=datetime.now)
    update_by = Column(String(64), nullable=True, server_default="''", comment='更新者')
    update_time = Column(DateTime, nullable=True, comment='更新时间', default=datetime.now)


class ActionCfirConstruct(Base):
    """
    官网-CFIR构念（障碍点）
    """

    __tablename__ = 'action_cfir_construct'
    __table_args__ = {'comment': '官网-CFIR构念（障碍点）'}

    construct_id = Column(Integer, primary_key=True, autoincrement=True, comment='构念id')
    domain_id = Column(Integer, nullable=False, comment='所属领域id')
    code = Column(String(64), nullable=False, comment='构念标识')
    name_zh = Column(String(200), nullable=False, comment='名称（中文）')
    name_en = Column(String(300), nullable=True, server_default="''", comment='名称（英文）')
    hint_zh = Column(String(800), nullable=True, server_default="''", comment='释义（中文）')
    hint_en = Column(String(1000), nullable=True, server_default="''", comment='释义（英文）')
    severity = Column(CHAR(1), nullable=True, server_default="'m'", comment='严重度（h高 m中 l低）')
    sort_num = Column(Integer, nullable=True, server_default='0', comment='显示顺序')


class ActionCfirStrategy(Base):
    """
    官网-CFIR构念对应的实施策略
    """

    __tablename__ = 'action_cfir_strategy'
    __table_args__ = {'comment': '官网-CFIR构念对应的实施策略'}

    strategy_id = Column(Integer, primary_key=True, autoincrement=True, comment='策略id')
    construct_id = Column(Integer, nullable=False, comment='所属构念id')
    name_zh = Column(String(300), nullable=False, comment='策略名称（中文）')
    name_en = Column(String(500), nullable=True, server_default="''", comment='策略名称（英文）')
    detail_zh = Column(Text, nullable=True, comment='策略说明（中文）')
    detail_en = Column(Text, nullable=True, comment='策略说明（英文）')
    source_zh = Column(String(300), nullable=True, server_default="''", comment='来源（中文）')
    source_en = Column(String(500), nullable=True, server_default="''", comment='来源（英文）')
    sort_num = Column(Integer, nullable=True, server_default='0', comment='显示顺序')


class ActionEricCategory(Base):
    """
    官网-ERIC策略分类
    """

    __tablename__ = 'action_eric_category'
    __table_args__ = {'comment': '官网-ERIC策略分类'}

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键')
    cat_key = Column(String(64), nullable=False, comment='分类标识')
    name_zh = Column(String(200), nullable=False, comment='名称（中文）')
    name_en = Column(String(300), nullable=True, server_default="''", comment='名称（英文）')
    sort_num = Column(Integer, nullable=True, server_default='0', comment='显示顺序')


class ActionEricStrategy(Base):
    """
    官网-ERIC实施策略库
    """

    __tablename__ = 'action_eric_strategy'
    __table_args__ = {'comment': '官网-ERIC实施策略库'}

    eric_id = Column(Integer, primary_key=True, autoincrement=True, comment='策略id')
    category = Column(String(64), nullable=False, comment='策略分类标识')
    name_zh = Column(String(300), nullable=False, comment='名称（中文）')
    name_en = Column(String(500), nullable=True, server_default="''", comment='名称（英文）')
    detail_zh = Column(Text, nullable=True, comment='说明（中文）')
    detail_en = Column(Text, nullable=True, comment='说明（英文）')
    map_zh = Column(String(300), nullable=True, server_default="''", comment='对应CFIR构念（中文）')
    map_en = Column(String(500), nullable=True, server_default="''", comment='对应CFIR构念（英文）')
    sort_num = Column(Integer, nullable=True, server_default='0', comment='显示顺序')
    status = Column(CHAR(1), nullable=True, server_default='0', comment='状态（0正常 1停用）')
    create_by = Column(String(64), nullable=True, server_default="''", comment='创建者')
    create_time = Column(DateTime, nullable=True, comment='创建时间', default=datetime.now)
    update_by = Column(String(64), nullable=True, server_default="''", comment='更新者')
    update_time = Column(DateTime, nullable=True, comment='更新时间', default=datetime.now)


class ActionReaimDimension(Base):
    """
    官网-RE-AIM维度
    """

    __tablename__ = 'action_reaim_dimension'
    __table_args__ = {'comment': '官网-RE-AIM维度'}

    dim_id = Column(Integer, primary_key=True, autoincrement=True, comment='维度id')
    letter = Column(CHAR(1), nullable=False, comment='维度首字母（R/E/A/I/M）')
    name_zh = Column(String(100), nullable=False, comment='名称（中文）')
    name_en = Column(String(200), nullable=True, server_default="''", comment='名称（英文）')
    sub_title = Column(String(200), nullable=True, server_default="''", comment='副标题')
    definition_zh = Column(String(800), nullable=True, server_default="''", comment='定义（中文）')
    definition_en = Column(String(1000), nullable=True, server_default="''", comment='定义（英文）')
    measure_zh = Column(String(800), nullable=True, server_default="''", comment='测量指标（中文）')
    measure_en = Column(String(1000), nullable=True, server_default="''", comment='测量指标（英文）')
    score_text = Column(String(32), nullable=True, server_default="''", comment='示例得分')
    sort_num = Column(Integer, nullable=True, server_default='0', comment='显示顺序')
    status = Column(CHAR(1), nullable=True, server_default='0', comment='状态（0正常 1停用）')
    create_by = Column(String(64), nullable=True, server_default="''", comment='创建者')
    create_time = Column(DateTime, nullable=True, comment='创建时间', default=datetime.now)
    update_by = Column(String(64), nullable=True, server_default="''", comment='更新者')
    update_time = Column(DateTime, nullable=True, comment='更新时间', default=datetime.now)


class ActionSrdAssessment(Base):
    """
    官网-SRD系统综述重复性评估
    """

    __tablename__ = 'action_srd_assessment'
    __table_args__ = {'comment': '官网-SRD系统综述重复性评估'}

    assessment_id = Column(Integer, primary_key=True, autoincrement=True, comment='评估id')
    review_a_title_zh = Column(String(600), nullable=False, comment='综述A标题（中文）')
    review_a_title_en = Column(String(900), nullable=True, server_default="''", comment='综述A标题（英文）')
    review_b_title_zh = Column(String(600), nullable=False, comment='综述B标题（中文）')
    review_b_title_en = Column(String(900), nullable=True, server_default="''", comment='综述B标题（英文）')
    overall_level = Column(String(16), nullable=True, server_default="'mod'", comment='整体判定（none/low/mod/high）')
    overall_pct = Column(Integer, nullable=True, server_default='0', comment='整体重复度百分比')
    overall_reason_zh = Column(Text, nullable=True, comment='整体判定理由（中文）')
    overall_reason_en = Column(Text, nullable=True, comment='整体判定理由（英文）')
    is_sample = Column(CHAR(1), nullable=True, server_default='1', comment='是否示例数据（0否 1是）')
    status = Column(CHAR(1), nullable=True, server_default='0', comment='状态（0正常 1停用）')
    del_flag = Column(CHAR(1), nullable=True, server_default='0', comment='删除标志（0存在 2删除）')
    create_by = Column(String(64), nullable=True, server_default="''", comment='创建者')
    create_time = Column(DateTime, nullable=True, comment='创建时间', default=datetime.now)
    update_by = Column(String(64), nullable=True, server_default="''", comment='更新者')
    update_time = Column(DateTime, nullable=True, comment='更新时间', default=datetime.now)


class ActionSrdDomain(Base):
    """
    官网-SRD评估领域
    """

    __tablename__ = 'action_srd_domain'
    __table_args__ = {'comment': '官网-SRD评估领域'}

    domain_id = Column(Integer, primary_key=True, autoincrement=True, comment='领域id')
    assessment_id = Column(Integer, nullable=False, comment='所属评估id')
    seq = Column(Integer, nullable=False, comment='领域序号')
    name_zh = Column(String(200), nullable=False, comment='名称（中文）')
    name_en = Column(String(300), nullable=True, server_default="''", comment='名称（英文）')
    is_key = Column(CHAR(1), nullable=True, server_default='0', comment='是否关键领域（0否 1是）')
    level = Column(String(16), nullable=True, server_default="'mod'", comment='重复程度（none/low/mod/high）')
    pct = Column(Integer, nullable=True, server_default='0', comment='重复度百分比')


class ActionSrdGroup(Base):
    """
    官网-SRD评估条目分组
    """

    __tablename__ = 'action_srd_group'
    __table_args__ = {'comment': '官网-SRD评估条目分组'}

    group_id = Column(Integer, primary_key=True, autoincrement=True, comment='分组id')
    domain_id = Column(Integer, nullable=False, comment='所属领域id')
    code = Column(String(32), nullable=True, server_default="''", comment='分组编号')
    name_zh = Column(String(300), nullable=False, comment='名称（中文）')
    name_en = Column(String(500), nullable=True, server_default="''", comment='名称（英文）')
    sort_num = Column(Integer, nullable=True, server_default='0', comment='显示顺序')


class ActionSrdItem(Base):
    """
    官网-SRD评估条目
    """

    __tablename__ = 'action_srd_item'
    __table_args__ = {'comment': '官网-SRD评估条目'}

    item_id = Column(Integer, primary_key=True, autoincrement=True, comment='条目id')
    group_id = Column(Integer, nullable=False, comment='所属分组id')
    code = Column(String(32), nullable=True, server_default="''", comment='条目编号（如 1a）')
    question_zh = Column(Text, nullable=False, comment='评估问题（中文）')
    question_en = Column(Text, nullable=True, comment='评估问题（英文）')
    level = Column(String(16), nullable=True, server_default="'mod'", comment='重复程度（none/low/mod/high）')
    pct = Column(Integer, nullable=True, server_default='0', comment='重复度百分比')
    basis_zh = Column(Text, nullable=True, comment='判定依据（中文）')
    basis_en = Column(Text, nullable=True, comment='判定依据（英文）')
    cite_a_zh = Column(Text, nullable=True, comment='综述A原文引用（中文）')
    cite_a_en = Column(Text, nullable=True, comment='综述A原文引用（英文）')
    cite_b_zh = Column(Text, nullable=True, comment='综述B原文引用（中文）')
    cite_b_en = Column(Text, nullable=True, comment='综述B原文引用（英文）')
    sort_num = Column(Integer, nullable=True, server_default='0', comment='显示顺序')


class ActionCollabRequest(Base):
    """
    官网-协作与专家咨询申请
    """

    __tablename__ = 'action_collab_request'
    __table_args__ = {'comment': '官网-协作与专家咨询申请'}

    request_id = Column(Integer, primary_key=True, autoincrement=True, comment='申请id')
    request_type = Column(String(32), nullable=True, server_default="'consult'", comment='申请类型')
    applicant = Column(String(100), nullable=False, comment='申请人')
    organization = Column(String(300), nullable=True, server_default="''", comment='所属机构')
    email = Column(String(200), nullable=False, comment='邮箱')
    phone = Column(String(50), nullable=True, server_default="''", comment='联系电话')
    topic = Column(String(300), nullable=True, server_default="''", comment='主题')
    content = Column(Text, nullable=True, comment='正文')
    source_lang = Column(String(8), nullable=True, server_default="'zh'", comment='提交时界面语言（zh/en）')
    source_ip = Column(String(128), nullable=True, server_default="''", comment='来源ip')
    handle_status = Column(CHAR(1), nullable=True, server_default='0', comment='处理状态（0待处理 1处理中 2已回复 3已关闭）')
    handle_by = Column(String(64), nullable=True, server_default="''", comment='处理人')
    handle_time = Column(DateTime, nullable=True, comment='处理时间')
    handle_remark = Column(String(1000), nullable=True, server_default="''", comment='处理备注')
    del_flag = Column(CHAR(1), nullable=True, server_default='0', comment='删除标志（0存在 2删除）')
    create_time = Column(DateTime, nullable=True, comment='提交时间', default=datetime.now)


class ActionGuestProfile(Base):
    """
    官网-访客档案

    官网访客账号的主表是 sys_user（user_type='01'），本表只补齐后台用户表没有的
    「所属机构 / 职位」两项。字段与 sql/action-website-pg.sql 第 10 节严格一一对应。
    """

    __tablename__ = 'action_guest_profile'
    # uk_agp_user_id 在 DDL 里是唯一索引，DO 里必须同步声明：
    # 少了它，create_all 建出来的表就没有「一个访客只能有一份档案」这条完整性约束，
    # 并发注册或补偿中断都可能写出重复档案，而线上库反而拦得住 —— ORM 与 SQL 分叉。
    __table_args__ = (
        UniqueConstraint('user_id', name='uk_agp_user_id'),
        {'comment': '官网-访客档案'},
    )

    profile_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='档案id')
    user_id = Column(BigInteger, nullable=False, comment='关联的用户id（sys_user.user_id，user_type=01）')
    # 空串默认值写 text("''") 而不是本文件其他表沿用的 server_default="''"：
    # 后者会被当成需要转义的字面量，DDL 里渲染成 DEFAULT ''''''（默认值是两个引号字符），
    # 与 sql/action-website-pg.sql 的 default '' 并不一致。本表有「DO 与 DDL 逐项一致」
    # 的验收要求，故在此表按正确写法，不去大范围改动既有表。
    institution = Column(
        String(300), nullable=True, server_default=text("''"), comment='所属机构（注册时用户自由填写）'
    )
    position = Column(String(100), nullable=True, server_default=text("''"), comment='职位（注册时用户自由填写）')
    del_flag = Column(CHAR(1), nullable=True, server_default='0', comment='删除标志（0存在 2删除）')
    create_time = Column(_timestamp_second(), nullable=True, comment='创建时间', default=datetime.now)
    update_time = Column(_timestamp_second(), nullable=True, comment='更新时间', default=datetime.now)
