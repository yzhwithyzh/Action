from datetime import datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    Column,
    Date,
    DateTime,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
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


class ActionTeamMember(Base):
    """
    官网-团队成员

    「关于我们」页的国际顾问委员会与核心执行团队，按 group_key 分组。
    简介分三层：summary（卡片一句话）、bio（详情页履历）、contribution（对 ACTION 的贡献）。
    """

    __tablename__ = 'action_team_member'
    __table_args__ = {'comment': '官网-团队成员'}

    member_id = Column(Integer, primary_key=True, autoincrement=True, comment='成员id')
    group_key = Column(
        String(32),
        nullable=False,
        server_default=text("'board'"),
        comment='所属组（board国际顾问委员会 core核心执行团队）',
    )
    name_zh = Column(String(200), nullable=False, comment='姓名（中文）')
    name_en = Column(String(200), nullable=True, server_default=text("''"), comment='姓名（英文）')
    honorific = Column(String(32), nullable=True, server_default=text("''"), comment='称谓（Prof./Dr.）')
    title_zh = Column(String(300), nullable=True, server_default=text("''"), comment='职称/头衔（中文）')
    title_en = Column(String(500), nullable=True, server_default=text("''"), comment='职称/头衔（英文）')
    affiliation_zh = Column(String(500), nullable=True, server_default=text("''"), comment='所属机构（中文）')
    affiliation_en = Column(String(800), nullable=True, server_default=text("''"), comment='所属机构（英文）')
    role_zh = Column(String(300), nullable=True, server_default=text("''"), comment='在 ACTION 中的角色（中文）')
    role_en = Column(String(500), nullable=True, server_default=text("''"), comment='在 ACTION 中的角色（英文）')
    expertise_zh = Column(
        String(500), nullable=True, server_default=text("''"), comment='研究方向标签（中文，顿号分隔）'
    )
    expertise_en = Column(
        String(800), nullable=True, server_default=text("''"), comment='研究方向标签（英文，分号分隔）'
    )
    summary_zh = Column(Text, nullable=True, comment='一句话简介（中文）')
    summary_en = Column(Text, nullable=True, comment='一句话简介（英文）')
    bio_zh = Column(Text, nullable=True, comment='详细履历（中文）')
    bio_en = Column(Text, nullable=True, comment='详细履历（英文）')
    contribution_zh = Column(Text, nullable=True, comment='对 ACTION 的贡献（中文）')
    contribution_en = Column(Text, nullable=True, comment='对 ACTION 的贡献（英文）')
    avatar_url = Column(String(300), nullable=True, server_default=text("''"), comment='头像地址')
    homepage_url = Column(String(500), nullable=True, server_default=text("''"), comment='个人主页/学术档案链接')
    email = Column(String(200), nullable=True, server_default=text("''"), comment='联系邮箱')
    sort_num = Column(Integer, nullable=True, server_default='0', comment='组内显示顺序')
    status = Column(CHAR(1), nullable=True, server_default='0', comment='状态（0正常 1停用）')
    del_flag = Column(CHAR(1), nullable=True, server_default='0', comment='删除标志（0存在 2删除）')
    create_by = Column(String(64), nullable=True, server_default=text("''"), comment='创建者')
    create_time = Column(DateTime, nullable=True, comment='创建时间', default=datetime.now)
    update_by = Column(String(64), nullable=True, server_default=text("''"), comment='更新者')
    update_time = Column(DateTime, nullable=True, comment='更新时间', default=datetime.now)
    remark = Column(String(500), nullable=True, comment='备注')


class ActionResourceLink(Base):
    """
    官网-资源中心链接

    首页「国际报告规范组织与循证枢纽」一段的外链卡片，一行一张。
    名称/说明中英成对，url 一律外部地址（前台新标签页打开）。
    """

    __tablename__ = 'action_resource_link'
    __table_args__ = {'comment': '官网-资源中心链接'}

    link_id = Column(Integer, primary_key=True, autoincrement=True, comment='资源id')
    name_zh = Column(String(200), nullable=False, comment='名称（中文）')
    name_en = Column(String(300), nullable=True, server_default=text("''"), comment='名称（英文）')
    summary_zh = Column(String(500), nullable=True, server_default=text("''"), comment='一句话说明（中文）')
    summary_en = Column(String(800), nullable=True, server_default=text("''"), comment='一句话说明（英文）')
    url = Column(String(500), nullable=False, comment='外部地址（前台一律新标签页打开）')
    logo_url = Column(
        String(300),
        nullable=True,
        server_default=text("''"),
        comment='标识图地址（随前端打包的 /assets/*.png 或后台上传的 OSS 直链），留空则不画图',
    )
    sort_num = Column(Integer, nullable=True, server_default='0', comment='卡片显示顺序')
    status = Column(CHAR(1), nullable=True, server_default='0', comment='状态（0正常 1停用）')
    del_flag = Column(CHAR(1), nullable=True, server_default='0', comment='删除标志（0存在 2删除）')
    create_by = Column(String(64), nullable=True, server_default=text("''"), comment='创建者')
    create_time = Column(DateTime, nullable=True, comment='创建时间', default=datetime.now)
    update_by = Column(String(64), nullable=True, server_default=text("''"), comment='更新者')
    update_time = Column(DateTime, nullable=True, comment='更新时间', default=datetime.now)
    remark = Column(String(500), nullable=True, comment='备注')


class ActionPublication(Base):
    """
    官网-成果发表

    「成果发表」页的论文列表与详情。**这张表刻意没有 `*_zh`/`*_en` 成对的双语列**：
    标题、作者、期刊、摘要都是发表时的原文，同时也是引用信息，翻译一遍就既检索不到
    也引用不了。页面上的栏目标题与按钮文字照旧走 i18n + `action_site_text`。

    `authors` / `affiliations` / `keywords` 三列存的是 **JSON 文本**，读写在
    `PublicationService` 里成对完成（`_load_json` / `_dump_json`）。用 text 而不是子表，
    是因为作者顺序即署名顺序、且没有任何跨论文的按作者查询需求；不用 jsonb，
    是因为这三列永远整体读写、从不在库内按字段查。
    """

    __tablename__ = 'action_publication'
    __table_args__ = {'comment': '官网-成果发表'}

    publication_id = Column(Integer, primary_key=True, autoincrement=True, comment='成果id')
    title = Column(String(500), nullable=False, comment='论文标题（发表原文，逐字，不翻译）')
    authors = Column(Text, nullable=True, comment='作者 JSON 数组，顺序即署名顺序')
    affiliations = Column(Text, nullable=True, comment='机构 JSON 数组，下标对应 authors[].affiliationIndex')
    abstract = Column(Text, nullable=True, comment='摘要（发表原文纯文本）')
    keywords = Column(Text, nullable=True, comment='关键词 JSON 数组')
    journal = Column(String(300), nullable=True, server_default=text("''"), comment='期刊名称')
    volume = Column(String(50), nullable=True, server_default=text("''"), comment='卷')
    issue = Column(String(50), nullable=True, server_default=text("''"), comment='期')
    pages = Column(String(50), nullable=True, server_default=text("''"), comment='页码')
    publication_year = Column(Integer, nullable=True, comment='发表年份，列表页按它分组')
    doi = Column(String(200), nullable=True, server_default=text("''"), comment='DOI')
    source_url = Column(String(500), nullable=True, server_default=text("''"), comment='出版社/期刊页面地址')
    pdf_url = Column(String(500), nullable=True, server_default=text("''"), comment='PDF 全文地址（OSS 公网直链）')
    cover_image_url = Column(String(300), nullable=True, server_default=text("''"), comment='配图/封面地址')
    citation_text = Column(Text, nullable=True, comment='引用文本，留空时由后端按字段自动拼一条')
    sort_num = Column(Integer, nullable=True, server_default='0', comment='同年内的显示顺序')
    status = Column(CHAR(1), nullable=True, server_default='0', comment='状态（0正常 1停用）')
    del_flag = Column(CHAR(1), nullable=True, server_default='0', comment='删除标志（0存在 2删除）')
    create_by = Column(String(64), nullable=True, server_default=text("''"), comment='创建者')
    create_time = Column(DateTime, nullable=True, comment='创建时间', default=datetime.now)
    update_by = Column(String(64), nullable=True, server_default=text("''"), comment='更新者')
    update_time = Column(DateTime, nullable=True, comment='更新时间', default=datetime.now)
    remark = Column(String(500), nullable=True, comment='备注')


class ActionSiteText(Base):
    """
    官网-站点文案（i18n 词条的可编辑副本）

    官网各页的标题/导语/正文/按钮字原本写死在 action-frontend/i18n/locales/{zh,en}.json，
    改一个字要改代码 + 重新 generate。本表把那 934 条搬进库供后台编辑。

    **default_* 与 text_* 不是中英那种对称关系**：
      default_zh / default_en  代码里的原始文案，由 `tools/extract_site_texts.py` 同步，后台只读
      text_zh    / text_en     当前生效文案，后台改的是这两列
    公开接口只吐 `text_* <> default_*` 的行 —— 一条没改时返回空对象，
    不给每个页面的 hydration payload 白压 120KB。「还原默认」= 把 text_* 写回 default_*。
    """

    __tablename__ = 'action_site_text'
    __table_args__ = {'comment': '官网-站点文案'}

    text_id = Column(Integer, primary_key=True, autoincrement=True, comment='文案id')
    text_key = Column(String(128), nullable=False, comment='i18n 键，如 index.s052，与前端 $t() 的参数一字不差')
    page_key = Column(String(64), nullable=False, server_default=text("''"), comment='所属分组（= text_key 首段）')
    page_label = Column(String(64), nullable=False, server_default=text("''"), comment='分组中文名')
    text_zh = Column(Text, nullable=True, comment='当前生效的中文文案')
    text_en = Column(Text, nullable=True, comment='当前生效的英文文案')
    default_zh = Column(Text, nullable=True, comment='代码里的中文默认值（后台只读）')
    default_en = Column(Text, nullable=True, comment='代码里的英文默认值（后台只读）')
    has_markup = Column(CHAR(1), nullable=True, server_default='0', comment='默认值里含HTML标签（0否 1是）')
    sort_num = Column(Integer, nullable=True, server_default='0', comment='显示顺序，大体等同页面从上到下')
    del_flag = Column(CHAR(1), nullable=True, server_default='0', comment='删除标志（0存在 2删除）')
    create_by = Column(String(64), nullable=True, server_default=text("''"), comment='创建者')
    create_time = Column(DateTime, nullable=True, comment='创建时间', default=datetime.now)
    update_by = Column(String(64), nullable=True, server_default=text("''"), comment='更新者')
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
    # 取值域是 action_guideline_category.cat_key —— 规范页的筛选条与卡片「研究设计」标签都靠它对上，
    # 写入表外的值会让这份规范在前台既筛不出来、标签也是空白。写接口会校验，见 GuidelineService。
    study_type = Column(
        String(64), nullable=True, server_default="''", comment='适用研究类型（取 action_guideline_category.cat_key）'
    )
    summary_zh = Column(Text, nullable=True, comment='简介（中文）')
    summary_en = Column(Text, nullable=True, comment='简介（英文）')
    # 版本号是显示给访客的一句话（「2010 修订 · 6 领域 / 17 条目」），不是内部版本标识，
    # 所以和 name/summary 一样分中英两列 —— 只留一列的话英文界面会原样显示中文。
    version_zh = Column(String(64), nullable=True, server_default="''", comment='版本（中文）')
    version_en = Column(String(64), nullable=True, server_default="''", comment='版本（英文）')
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


class ActionGuidelineCategory(Base):
    """
    官网-报告规范分类

    规范页第①段筛选条的词表。`cat_key` 的取值域就是 `ActionGuideline.study_type`，
    两者靠这个键对上；不另设外键列，避免同一件事有两列可写而各写各的。
    """

    __tablename__ = 'action_guideline_category'
    __table_args__ = {'comment': '官网-报告规范分类'}

    cat_id = Column(Integer, primary_key=True, autoincrement=True, comment='分类id')
    cat_key = Column(
        String(32),
        nullable=False,
        comment='分类标识，取值即 action_guideline.study_type（rct/nrct/protocol/sr/case/obs/guideline/animal）',
    )
    name_zh = Column(String(200), nullable=False, comment='名称（中文）')
    name_en = Column(String(300), nullable=True, server_default=text("''"), comment='名称（英文）')
    icon_paths = Column(Text, nullable=True, comment='卡片图标的 SVG path d 属性，一行一条')
    sort_num = Column(Integer, nullable=True, server_default='0', comment='筛选条中的显示顺序')
    status = Column(CHAR(1), nullable=True, server_default='0', comment='状态（0正常 1停用）')
    del_flag = Column(CHAR(1), nullable=True, server_default='0', comment='删除标志（0存在 2删除）')
    create_by = Column(String(64), nullable=True, server_default=text("''"), comment='创建者')
    create_time = Column(DateTime, nullable=True, comment='创建时间', default=datetime.now)
    update_by = Column(String(64), nullable=True, server_default=text("''"), comment='更新者')
    update_time = Column(DateTime, nullable=True, comment='更新时间', default=datetime.now)
    remark = Column(String(500), nullable=True, comment='备注')


class ActionGuidelineItem(Base):
    """
    官网-报告规范checklist条目
    """

    __tablename__ = 'action_guideline_item'
    __table_args__ = {'comment': '官网-报告规范checklist条目'}

    item_id = Column(Integer, primary_key=True, autoincrement=True, comment='条目id')
    guideline_id = Column(Integer, nullable=False, comment='所属规范id')
    part_no = Column(Integer, nullable=True, server_default='1', comment='所属清单表序号（一份规范可能含多张表）')
    part_zh = Column(String(300), nullable=True, server_default="''", comment='清单表标题（中文）')
    part_en = Column(String(500), nullable=True, server_default="''", comment='清单表标题（英文）')
    domain_zh = Column(String(300), nullable=True, server_default="''", comment='章节/主题/领域（中文）')
    domain_en = Column(String(500), nullable=True, server_default="''", comment='章节/主题/领域（英文）')
    item_no_zh = Column(String(64), nullable=True, server_default="''", comment='条目号（中文，如 1a）')
    item_no_en = Column(String(64), nullable=True, server_default="''", comment='条目号（英文，如 1a）')
    content_zh = Column(Text, nullable=True, comment='条目内容（中文）')
    content_en = Column(Text, nullable=True, comment='条目内容（英文）')
    ext_label_zh = Column(String(200), nullable=True, server_default="''", comment='扩展列列名（中文）')
    ext_label_en = Column(String(300), nullable=True, server_default="''", comment='扩展列列名（英文）')
    extension_zh = Column(Text, nullable=True, comment='扩展/对照条目内容（中文）')
    extension_en = Column(Text, nullable=True, comment='扩展/对照条目内容（英文）')
    # 报告助手第二步「要求 / 示例 / 撰写」三段式面板的中间那段。由后台「规范条目管理」逐条录入，
    # 各规范 docx 里没有这一列，所以 extract_checklists.py 不产出它；为空即「暂无示例」。
    example_zh = Column(Text, nullable=True, comment='条目示例/范例（中文）')
    example_en = Column(Text, nullable=True, comment='条目示例/范例（英文）')
    # 报告规范的通例是条目默认都要应答，所以默认 '0'（必填）；只有带「如适用 / if applicable」
    # 这类限定语的才是 '1'。种子由 sql/007 的关键词启发式回填，后台可逐条修正。
    require_level = Column(CHAR(1), nullable=True, server_default='0', comment='填写要求（0必填 1条件填写/选填）')
    sort_num = Column(Integer, nullable=True, server_default='0', comment='规范内显示顺序')
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
    # 代号快照，程序不按它匹配：规范代号在后台可改，按字符串挂的话一改名就全部指空（sql/048）
    hot_guideline = Column(String(64), nullable=True, server_default="''", comment='重点推荐规范代号（快照）')
    hot_guideline_id = Column(Integer, nullable=True, comment='重点推荐规范id（决定第二步展开哪份 checklist）')
    sort_num = Column(Integer, nullable=True, server_default='0', comment='显示顺序')
    status = Column(CHAR(1), nullable=True, server_default='0', comment='状态（0正常 1停用）')
    tip_zh = Column(String(1000), nullable=True, server_default="''", comment='专属提示（中文）')
    tip_en = Column(String(2000), nullable=True, server_default="''", comment='专属提示（英文）')
    create_by = Column(String(64), nullable=True, server_default="''", comment='创建者')
    create_time = Column(DateTime, nullable=True, comment='创建时间', default=datetime.now)
    update_by = Column(String(64), nullable=True, server_default="''", comment='更新者')
    update_time = Column(DateTime, nullable=True, comment='更新时间', default=datetime.now)


class ActionWizardQuestion(Base):
    """
    官网-报告助手第一步分支问卷：问题（sql/041）

    问卷是一棵树：第一题（`is_root='1'`，全表唯一）的每个选项要么弹出下一题、要么判定出
    一类研究（`action_study_type`）。同一层的题在不同分支里问的东西完全不同，层数也不齐，
    所以不能再用「研究类型一行一个按钮」来表达。
    """

    __tablename__ = 'action_wizard_question'
    __table_args__ = {'comment': '官网-报告助手第一步分支问卷：问题'}

    question_id = Column(Integer, primary_key=True, autoincrement=True, comment='问题id')
    q_key = Column(String(32), nullable=False, comment='问题标识')
    text_zh = Column(String(300), nullable=False, comment='题干（中文）')
    text_en = Column(String(500), nullable=True, server_default="''", comment='题干（英文）')
    is_root = Column(CHAR(1), nullable=True, server_default='0', comment='是否第一题')
    sort_num = Column(Integer, nullable=True, server_default='0', comment='后台列表顺序')
    create_by = Column(String(64), nullable=True, server_default="''", comment='创建者')
    create_time = Column(DateTime, nullable=True, comment='创建时间', default=datetime.now)
    update_by = Column(String(64), nullable=True, server_default="''", comment='更新者')
    update_time = Column(DateTime, nullable=True, comment='更新时间', default=datetime.now)


class ActionWizardOption(Base):
    """
    官网-报告助手第一步分支问卷：选项与去向

    `next_question_id` 与 `result_type_key` **二选一**：前者接着弹出下一题，后者到此判定。
    `opt_key` 进 URL（`/assistant?path=A.y.y`），同一题内唯一。
    """

    __tablename__ = 'action_wizard_option'
    __table_args__ = {'comment': '官网-报告助手第一步分支问卷：选项与去向'}

    option_id = Column(Integer, primary_key=True, autoincrement=True, comment='选项id')
    question_id = Column(Integer, nullable=False, comment='所属问题id')
    opt_key = Column(String(32), nullable=False, comment='选项标识')
    label_zh = Column(String(200), nullable=False, comment='选项文字（中文）')
    label_en = Column(String(300), nullable=True, server_default="''", comment='选项文字（英文）')
    next_question_id = Column(Integer, nullable=True, comment='下一题id')
    result_type_key = Column(String(32), nullable=True, server_default="''", comment='判定的研究类型标识')
    tip_zh = Column(String(1000), nullable=True, server_default="''", comment='选中时的提示（中文）')
    tip_en = Column(String(2000), nullable=True, server_default="''", comment='选中时的提示（英文）')
    sort_num = Column(Integer, nullable=True, server_default='0', comment='显示顺序')


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

    既是**任务记录**（session_id / user_id / run_status 那一组），也是**结果留档**：
    访客提交后先落一行 pending，worker 跑完由轮询接口把引擎结果写回同一行。
    示例行（is_sample='1'）没有 session_id 与 user_id —— 它不属于任何访客。
    """

    __tablename__ = 'action_srd_assessment'
    __table_args__ = {'comment': '官网-SRD系统综述重复性评估'}

    assessment_id = Column(Integer, primary_key=True, autoincrement=True, comment='评估id')
    session_id = Column(String(64), nullable=True, comment='worker任务id')
    user_id = Column(BigInteger, nullable=True, comment='发起评估的访客用户id')
    run_status = Column(
        String(16), nullable=True, server_default="'completed'", comment='任务状态（pending/running/completed/failed/stopped）'
    )
    progress = Column(Integer, nullable=True, server_default='0', comment='进度百分比0-100')
    error_msg = Column(String(500), nullable=True, server_default="''", comment='失败原因')
    file_a_name = Column(String(255), nullable=True, server_default="''", comment='综述A上传文件名')
    file_b_name = Column(String(255), nullable=True, server_default="''", comment='综述B上传文件名')
    review_a_title_zh = Column(String(600), nullable=False, comment='综述A标题（中文）')
    review_a_title_en = Column(String(900), nullable=True, server_default="''", comment='综述A标题（英文）')
    review_b_title_zh = Column(String(600), nullable=False, comment='综述B标题（中文）')
    review_b_title_en = Column(String(900), nullable=True, server_default="''", comment='综述B标题（英文）')
    # 没有 server_default：判定为空就是「还没判 / 判不出来」，不能兜成「中度重复」。
    # 兜了之后，ORM 会把显式传进来的 None 当成「没给值」而落成 'mod'（列有默认值时的既定行为），
    # 于是一条刚排队的任务、或一个全领域证据不足的结果，都会在历史里显示成中度重复。
    overall_level = Column(String(16), nullable=True, comment='整体判定（none/low/mod/high）')
    overall_pct = Column(Integer, nullable=True, server_default='0', comment='整体重复度百分比')
    overall_score_sum = Column(Integer, nullable=True, server_default='0', comment='整体得分（分越高越重复）')
    overall_score_max = Column(Integer, nullable=True, server_default='0', comment='可评分条目满分=3×可评分条目数')
    overall_score_max_full = Column(Integer, nullable=True, server_default='0', comment='名义满分=3×34=102')
    overall_reason_zh = Column(Text, nullable=True, comment='整体判定理由（中文）')
    overall_reason_en = Column(Text, nullable=True, comment='整体判定理由（英文）')
    provisional = Column(CHAR(1), nullable=True, server_default='0', comment='关键领域证据不足，结论仅供参考（0否 1是）')
    unclear_count = Column(Integer, nullable=True, server_default='0', comment='证据不足条目数')
    review_count = Column(Integer, nullable=True, server_default='0', comment='待人工复核条目数')
    model_name = Column(String(200), nullable=True, server_default="''", comment='判定所用模型')
    engine_version = Column(String(64), nullable=True, server_default="''", comment='引擎版本')
    prompt_version = Column(String(64), nullable=True, server_default="''", comment='提示词版本')
    criteria_version = Column(String(64), nullable=True, server_default="''", comment='判定口径版本')
    llm_calls = Column(Integer, nullable=True, server_default='0', comment='模型调用次数')
    token_in = Column(Integer, nullable=True, server_default='0', comment='输入token数')
    token_out = Column(Integer, nullable=True, server_default='0', comment='输出token数')
    seconds = Column(Numeric(10, 1), nullable=True, server_default='0', comment='耗时（秒）')
    finish_time = Column(DateTime, nullable=True, comment='完成时间')
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
    # 同 ActionSrdAssessment.overall_level：不设默认值，「没得判」必须是 null 而不是 'mod'
    level = Column(String(16), nullable=True, comment='重复程度（none/low/mod/high）')
    pct = Column(Integer, nullable=True, server_default='0', comment='重复度百分比')
    score_sum = Column(Integer, nullable=True, server_default='0', comment='领域得分（分越高越重复）')
    score_max = Column(Integer, nullable=True, server_default='0', comment='可评分条目满分=3×可评分条目数')
    score_max_full = Column(Integer, nullable=True, server_default='0', comment='名义满分=3×条目数')
    dup_count = Column(Integer, nullable=True, server_default='0', comment='偏重复条目数（评分0/1）')
    diff_count = Column(Integer, nullable=True, server_default='0', comment='偏不同条目数（评分2/3）')
    unclear_count = Column(Integer, nullable=True, server_default='0', comment='证据不足条目数')
    evidence_sufficient = Column(CHAR(1), nullable=True, server_default='1', comment='证据是否充分（0否 1是）')
    near_boundary = Column(CHAR(1), nullable=True, server_default='0', comment='百分比临近分箱边界（0否 1是）')


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
    # 条目层只有评分，没有「重复程度」与百分比：3=完全相同 … 0=完全不同，unclear=证据不足。
    # 百分比是领域与整体才有的量（由这些分数算出来，见 srd-engine/aggregate.py）。
    rating = Column(String(8), nullable=True, server_default="'unclear'", comment='条目评分（0/1/2/3/unclear）')
    score = Column(Integer, nullable=True, comment='评分对应分数0-3；证据不足为空，不进分子分母')
    confidence = Column(String(16), nullable=True, server_default="'medium'", comment='判定把握（high/medium/low）')
    needs_review = Column(CHAR(1), nullable=True, server_default='0', comment='是否需人工复核（0否 1是）')
    review_note = Column(String(500), nullable=True, server_default="''", comment='复核提示')
    evidence_card = Column(Text, nullable=True, comment='代码算出的客观事实（3a/6a/8b）')
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


class ActionReportDraft(Base):
    """
    官网-报告助手报告草稿

    一行 = 一份报告初稿，逐条目正文在 `ActionReportDraftItem`。字段与
    sql/008-action-report-draft-pg.sql 严格一一对应。

    **acu_* 五列已停用，代码里不再读写**（针灸专属字段整体撤除的理由见
    `module_action/service/report_compose_service.py` 的模块 docstring）。
    列留着不删：撤除前存过草稿的用户，那几行数据还在里面，drop 一次就没了；
    留着不读不写没有代价。ORM 里也照留，好让这个类继续与实表一一对应 ——
    少写一列，`create_all` 在全新库上建出来的表就和 008 建出来的不是同一张。

    空串默认值一律写 `text("''")`，**不能写 `server_default="''"`**：后者会被当成需要转义的
    字面量，DDL 渲染成 `DEFAULT ''''''`，默认值变成「两个引号字符」这个非空字符串
    （实跑时踩到过：本该判空的列一律变成非空）。同 `ActionGuestProfile` 的处理。
    """

    __tablename__ = 'action_report_draft'
    __table_args__ = {'comment': '官网-报告助手报告草稿'}

    draft_id = Column(Integer, primary_key=True, autoincrement=True, comment='草稿id')
    user_id = Column(BigInteger, nullable=False, comment='归属访客用户id（sys_user.user_id）')
    guideline_id = Column(Integer, nullable=False, comment='所依据的报告规范id')
    study_type_key = Column(String(32), nullable=True, server_default=text("''"), comment='第一步判定的研究类型，仅作留档')
    title = Column(String(300), nullable=True, server_default=text("''"), comment='草稿名称，由用户自取')
    #: 导入的原稿。**与条目框两份并存**：导出正文以它为准，条目框只是对照与改写的工作面。
    #: 拆碎了当唯一真相的话，导出拼回来的就不是用户写的那篇稿子了（见 sql/019 的文件头）
    source_text = Column(Text, nullable=True, comment='导入的原稿全文；逐条填的草稿为空')
    source_name = Column(String(255), nullable=True, server_default=text("''"), comment='导入时的原始文件名')
    source_lines = Column(Integer, nullable=True, server_default='0', comment='原稿有效行数（空行不占号）')
    acu_basis = Column(String(32), nullable=True, server_default=text("''"), comment='穴位选取依据（bianzheng/duizheng/jingyan）')
    acu_basis_note = Column(String(1000), nullable=True, server_default=text("''"), comment='选穴依据补充说明')
    acu_needle = Column(String(1000), nullable=True, server_default=text("''"), comment='进针手法（角度、深度、行针手法）')
    acu_deqi = Column(String(1000), nullable=True, server_default=text("''"), comment='得气感应')
    acu_control = Column(String(1000), nullable=True, server_default=text("''"), comment='对照/对照措施设置')
    status = Column(CHAR(1), nullable=True, server_default='0', comment='状态（0正常 1停用）')
    del_flag = Column(CHAR(1), nullable=True, server_default='0', comment='删除标志（0存在 2删除）')
    create_by = Column(String(64), nullable=True, server_default=text("''"), comment='创建者')
    create_time = Column(DateTime, nullable=True, comment='创建时间', default=datetime.now)
    update_by = Column(String(64), nullable=True, server_default=text("''"), comment='更新者')
    update_time = Column(DateTime, nullable=True, comment='更新时间', default=datetime.now)


class ActionReportDraftSource(Base):
    """
    官网-报告草稿导入的原文件与条目锚点（sql/044，与草稿 1:1，删草稿时物理删除）

    「生成初稿」从原文件出发、把改过的条目写回原位（`service/manuscript_rebuild.py`），
    图片、表格、样式因此得以保留。存库而不是 OSS：那个桶整桶公共读，未发表稿件不能放那儿。
    """

    __tablename__ = 'action_report_draft_source'
    __table_args__ = {'comment': '官网-报告草稿导入原稿（原文件 + 条目锚点）'}

    draft_id = Column(BigInteger, primary_key=True, comment='草稿id')
    file_name = Column(String(255), nullable=True, server_default=text("''"), comment='原始文件名')
    file_ext = Column(String(10), nullable=True, server_default=text("''"), comment='扩展名（带点）')
    file_data = Column(LargeBinary, nullable=True, comment='原文件字节')
    anchors = Column(Text, nullable=True, server_default=text("''"), comment='条目锚点 JSON')
    create_time = Column(DateTime, nullable=True, comment='创建时间', default=datetime.now)
    update_time = Column(DateTime, nullable=True, comment='更新时间', default=datetime.now)


class ActionReportDraftItem(Base):
    """
    官网-报告草稿逐条目正文

    用户没填过的条目**不建行**：「没有行」与「填了空串」在完成度统计里是同一回事，
    没必要为一份 282 条的规范预先铺 282 行空记录。
    """

    __tablename__ = 'action_report_draft_item'
    # uk_action_report_draft_item 在 DDL 里是唯一索引，DO 必须同步声明 ——
    # 少了它 create_all 建出来的表会允许同一条目写出多行，于是「保存两次」变成
    # 「同一条目两份正文」，而线上库反而拦得住。保存本身走的是先删后插
    # （`ReportDraftDao.replace_draft_items`），这个索引挡的是并发保存时落后的那一次。
    __table_args__ = (
        UniqueConstraint('draft_id', 'item_id', name='uk_action_report_draft_item'),
        {'comment': '官网-报告草稿逐条目正文'},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键')
    draft_id = Column(Integer, nullable=False, comment='所属草稿id')
    item_id = Column(Integer, nullable=False, comment='所应答的 checklist 条目id')
    content = Column(Text, nullable=True, comment='用户为该条目写的正文')
    update_time = Column(DateTime, nullable=True, comment='更新时间', default=datetime.now)


class ActionReportReview(Base):
    """
    官网-报告助手第三步校验记录

    一行 = 一次逐条校验任务。字段与 sql/010-action-report-review-pg.sql +
    sql/014-action-report-review-history-pg.sql 一一对应。

    ## 它同时是两样东西

    ① **任务台账**：提交那一刻就落一行 `pending`，由轮询与历史列表对账到终态。
    所以跑失败的、被停掉的、用户中途关掉页面的任务在这里都留得下痕迹 ——
    014 之前落库发生在前端轮到 completed 的那一刻，恰恰把这批最该排查的任务全漏了。
    ② **结果快照**：跑完的判定连同稿件正文一起存，用户可按历史回看。

    ## draft_id 可空

    外部粘贴稿件的用户（第三步真正的主用户）没有草稿可挂。第四步的工作清单仍旧从这里取
    「这份草稿最近一次校验」，那只是 `draft_id is not null` 的一个子集。

    ## 稿件正文在这里，删除时是真删

    014 起存 `manuscript` 与逐条 `evidence`（`assistant.rvHint` 那句承诺已同步改写）。
    作为对价，`ReportReviewDao.soft_delete_review_dao` 在置 `del_flag='2'` 的同时把这两处
    **物理清空**，只留台账那几列。排障要的是 session_id / 状态 / 计数 / 时间，
    隐私风险在正文 —— 用户点了删除就该是真的没了，而不是列表里看不见了。
    """

    __tablename__ = 'action_report_review'
    __table_args__ = {'comment': '官网-报告助手第三步校验记录'}

    review_id = Column(Integer, primary_key=True, autoincrement=True, comment='校验记录id')
    draft_id = Column(Integer, nullable=True, comment='被校验的草稿id；外部粘贴的稿件为空')
    user_id = Column(BigInteger, nullable=False, comment='归属访客用户id（sys_user.user_id）')
    guideline_id = Column(Integer, nullable=True, comment='所依据的报告规范id')
    guideline_code = Column(String(64), nullable=True, server_default=text("''"), comment='报告规范代号（冗余存）')
    session_id = Column(String(64), nullable=True, server_default=text("''"), comment='worker会话id，仅供排障对账')
    #: 用途。`import` 那一次跑完会**回填草稿条目**，`check` 不会 —— 不分的话，
    #: 用户之后每复查一次就把自己在第二步的编辑悄悄盖掉一遍
    purpose = Column(String(16), nullable=True, server_default='check', comment='用途（check / import）')
    run_status = Column(String(16), nullable=True, server_default='completed', comment='任务状态')
    error_msg = Column(String(500), nullable=True, server_default=text("''"), comment='失败原因')
    progress = Column(Integer, nullable=True, server_default='0', comment='进度百分比0-100')
    models = Column(String(200), nullable=True, server_default=text("''"), comment='实际出结果的模型，排障用')
    locale = Column(String(2), nullable=True, server_default='zh', comment='判定语言（zh/en）')
    char_count = Column(Integer, nullable=True, server_default='0', comment='稿件字符数')
    item_total = Column(Integer, nullable=True, server_default='0', comment='该规范的条目总数')
    completeness = Column(Integer, nullable=True, server_default='0', comment='完整度百分比0-100')
    reported = Column(Integer, nullable=True, server_default='0', comment='已报告条目数')
    vague = Column(Integer, nullable=True, server_default='0', comment='描述模糊条目数')
    missing = Column(Integer, nullable=True, server_default='0', comment='未报告条目数')
    line_count = Column(Integer, nullable=True, server_default='0', comment='稿件行数')
    truncated = Column(CHAR(1), nullable=True, server_default='0', comment='稿件是否被截断（0否 1是）')
    manuscript = Column(Text, nullable=True, comment='稿件正文；删除记录时物理清空')
    consistency = Column(Text, nullable=True, comment='全稿一致性判定结果（JSON）')
    #: 任务完成了、但有一部分没判成（批次失败 / 条目未作答 / 某条全稿规则没跑成），JSON 字符串数组。
    #: 与 error_msg 不同：那一列是「整个任务失败」的原因。sql/039；删除记录时物理清空
    run_warnings = Column(Text, nullable=True, comment='部分判定未完成的说明（JSON 数组）；删除记录时物理清空')
    del_flag = Column(CHAR(1), nullable=True, server_default='0', comment='删除标志（0存在 2删除）')
    create_time = Column(DateTime, nullable=True, comment='创建时间', default=datetime.now)
    finish_time = Column(DateTime, nullable=True, comment='任务到终态的时间')


class ActionReportReviewItem(Base):
    """
    官网-报告助手第三步逐条判定

    `reason` 是模型对该条目的判断说明，`evidence` 才是稿件的逐字片段。
    **evidence 与主表的 manuscript 是一对**：单存 evidence 是一句回不到上下文的孤立引文，
    所以两者要么都在，要么在删除时一起清空（见 `ActionReportReview` 的 docstring）。
    """

    __tablename__ = 'action_report_review_item'
    # 同一次校验里一条目只该有一条判定。DO 必须同步声明这个唯一索引 ——
    # 少了它 create_all 建出来的表允许重复写入，而线上库反而拦得住
    __table_args__ = (
        UniqueConstraint('review_id', 'item_id', name='uk_action_report_review_item'),
        {'comment': '官网-报告助手第三步逐条判定'},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键')
    review_id = Column(Integer, nullable=False, comment='所属校验记录id')
    item_id = Column(Integer, nullable=False, comment='checklist条目id')
    status = Column(String(16), nullable=False, comment='判定（reported / vague / missing）')
    reason = Column(Text, nullable=True, comment='判定说明')
    evidence = Column(Text, nullable=True, comment='判定引用的稿件原文片段；删除记录时物理清空')
    lines = Column(String(200), nullable=True, server_default=text("''"), comment='报告于第几行，逗号分隔')
    #: 引文回原文核对的结论（sql/037）。只是给人看的提示，status 不因它改变
    evidence_located = Column(
        String(8), nullable=True, server_default=text("''"), comment='引文回原文核对：yes / partial / no / 空'
    )
class ActionReportTrail(Base):
    """
    官网-报告助手操作留痕

    字段与 sql/011-action-report-trail-pg.sql 一一对应。

    **只存结构化的数字与枚举，不存渲染好的句子**：句子里迟早会混进稿件正文片段
    （「已提交稿件：本研究纳入 120 例……」），第三步「稿件不入库」的承诺就绕过去了。
    人读的那句话由前端按 i18n 渲染，库里没有它。唯一的自由文本是 `note`，仅供系统诊断。

    `event=applied` 记的是第四步把模型生成的文字写回草稿条目 —— 那是这套工具里
    真正的「关键数据修改」，也是投稿时被问起「AI 参与了多少」时唯一能拿出来的答案。
    """

    __tablename__ = 'action_report_trail'
    __table_args__ = {'comment': '官网-报告助手操作留痕'}

    trail_id = Column(Integer, primary_key=True, autoincrement=True, comment='留痕id')
    user_id = Column(BigInteger, nullable=False, comment='操作人（sys_user.user_id）')
    draft_id = Column(Integer, nullable=True, comment='关联草稿id；外部稿件为空')
    guideline_code = Column(String(64), nullable=True, server_default=text("''"), comment='报告规范代号')
    event = Column(String(32), nullable=False, comment='事件（submitted/judged/cross/failed/applied）')
    actor = Column(String(200), nullable=True, server_default=text("''"), comment='执行者：用户名或模型标识')
    item_id = Column(Integer, nullable=True, comment='event=applied 时被写回的条目id')
    total = Column(Integer, nullable=True, comment='判定条目总数')
    reported = Column(Integer, nullable=True, comment='已报告条目数')
    vague = Column(Integer, nullable=True, comment='描述模糊条目数')
    missing = Column(Integer, nullable=True, comment='未报告条目数')
    completeness = Column(Integer, nullable=True, comment='完整性百分比')
    char_count = Column(Integer, nullable=True, comment='稿件字符数（只记长度，不记内容）')
    note = Column(String(300), nullable=True, server_default=text("''"), comment='系统诊断信息，不得写入稿件内容')
    create_time = Column(DateTime, nullable=True, comment='创建时间', default=datetime.now)

class ActionLiterature(Base):
    """
    针灸文献知识库

    「研究背景与讨论智能生成」的唯一数据源。567 篇针刺文献 PDF 由
    `tools/lit_ingest.py` 离线抽取入库，后台「参考文献管理」页做人工复核与修正。

    **这张表的记录是机器抽取的产物，不是人工录入的。** 后台页面的主要工作是
    「复核」而不是「新增」—— 一条记录必须对应一个真实的 PDF 文件（`corpus_no`
    的唯一约束就是这条纪律的落点），手工凭空建一条会得到一份没有原文可核的元数据。

    `authors` / `condition` / `intervention` / `comparator` / `outcomes` /
    `acu_points` 等列是 **JSON 文本**，读写在 `LiteratureService` 里成对完成。
    用 text 不用 jsonb：整体读写、不在库内按字段查。

    `condition_group` 是病种上位类目（见 `ActionConditionDict`），
    **覆盖度统计与检索扩展按它算，不按原始 `condition`** —— 原始标签 485 个、
    80% 只出现一次，按它算几乎所有研究方向都会被判「本库撑不住」。
    """

    __tablename__ = 'action_literature'
    __table_args__ = (
        UniqueConstraint('corpus_no', name='uk_action_literature_corpus_no'),
        {'comment': '针灸文献知识库'},
    )

    lit_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='文献id')
    corpus_no = Column(Integer, nullable=False, comment='语料编号（目录.xlsx 的「新编号」，唯一）')
    file_name = Column(String(500), nullable=False, comment='PDF 文件名')
    title = Column(String(1000), nullable=False,
                   comment='原文题名，按 PDF 原语言照录（中文文献存中文题名）。引用输出用这一列')
    title_en = Column(String(1000), nullable=True,
                      comment='英文题名，取自目录.xlsx；同时是抽取时的防夹带锚。英文文献与 title 同值')

    year = Column(Integer, nullable=True, comment='出版年')
    year_evidence = Column(String(300), nullable=True, server_default=text("''"), comment='判定出版年所依据的原文片段')
    year_confidence = Column(String(10), nullable=True, server_default=text("'low'"), comment='high/low')
    authors = Column(Text, nullable=True, comment='作者 JSON 数组，顺序即署名顺序')
    journal = Column(String(300), nullable=True, server_default=text("''"), comment='期刊名')
    country = Column(String(100), nullable=True, server_default=text("''"), comment='国家')
    lang = Column(CHAR(2), nullable=True, server_default=text("'zh'"), comment='文献语言 zh/en')

    abstract = Column(Text, nullable=True, comment='摘要')
    population = Column(String(1000), nullable=True, server_default=text("''"), comment='研究对象')
    condition = Column(Text, nullable=True, comment='病种 JSON 数组（归一化中文标签，非原文）')
    condition_norm = Column(Text, nullable=True, comment='规范病种名 JSON 数组')
    condition_group = Column(Text, nullable=True, comment='上位病种类目 JSON 数组，覆盖度按它算')
    intervention = Column(Text, nullable=True, comment='干预 JSON 数组')
    comparator = Column(Text, nullable=True, comment='对照 JSON 数组，短标签；自由文本会让下游分组静默漂移')
    outcomes = Column(Text, nullable=True, comment='结局指标 JSON 数组')
    tcm_syndrome = Column(Text, nullable=True, comment='中医证候 JSON 数组')

    study_design = Column(String(20), nullable=True, server_default=text("'other'"), comment='研究设计')
    sample_size = Column(Integer, nullable=True, comment='总样本量')
    effect_direction = Column(
        String(20), nullable=True, server_default=text("'unclear'"), comment='效应方向，按主要结局判'
    )
    finding_summary = Column(Text, nullable=True, comment='主要结果概括')

    acu_points = Column(Text, nullable=True, comment='穴位 JSON 数组，国际代码优先')
    acu_meridian = Column(Text, nullable=True, comment='经络 JSON 数组')
    acu_method = Column(String(200), nullable=True, server_default=text("''"), comment='针法')
    acu_frequency = Column(String(200), nullable=True, server_default=text("''"), comment='电针频率')
    acu_deqi = Column(CHAR(1), nullable=True, comment='是否报告得气：1是 0否 null未提及')
    acu_retention_min = Column(Integer, nullable=True, comment='留针分钟数')
    acu_sessions = Column(Integer, nullable=True, comment='总治疗次数')
    acu_course_weeks = Column(Integer, nullable=True, comment='疗程周数')

    contamination = Column(CHAR(1), nullable=True, server_default='0', comment='PDF 是否夹带其他论文内容')
    contamination_note = Column(String(1000), nullable=True, server_default=text("''"), comment='夹带说明')
    contam_kind = Column(String(20), nullable=True, server_default=text("''"), comment='夹带形态')
    clean_status = Column(String(20), nullable=True, server_default=text("'na'"), comment='切除结果')
    clean_ratio = Column(Integer, nullable=True, comment='切除后正文占原文百分比')
    intruders = Column(Text, nullable=True, comment='混入的其他论文标题 JSON 数组')
    truncated = Column(CHAR(1), nullable=True, server_default='0', comment='本文后半截不在本 PDF 里')
    review_status = Column(String(20), nullable=True, server_default=text("'pending'"), comment='人工复核状态')
    review_by = Column(String(64), nullable=True, server_default=text("''"), comment='复核人')
    review_time = Column(DateTime, nullable=True, comment='复核时间')

    #: 检索向量。float32 小端原始字节（numpy tobytes），**已 L2 归一化**，检索时点积即余弦。
    #: 567 × 1024 × 4B = 2.2MB，全量常驻内存 numpy 暴力算 —— 不装 pgvector、不引向量库。
    #: `embed_hash` 是送去 embed 那段文本的指纹：后台改了标题/摘要/病种标签之后向量就过期了，
    #: 而**过期的表现是「这篇检索排位莫名其妙」，没有任何报错**，不靠 hash 就永远发现不了。
    #: `embed_model` 同理不能省 —— 不同模型的向量空间不可比，换模型必须全量重算。
    embedding = Column(LargeBinary, nullable=True, comment='检索向量（float32 原始字节，已归一化）')
    embed_model = Column(String(100), nullable=True, server_default=text("''"), comment='算这条向量的模型标识')
    embed_dim = Column(Integer, nullable=True, comment='向量维度')
    embed_hash = Column(String(64), nullable=True, server_default=text("''"), comment='embed 输入文本的指纹')
    embed_time = Column(DateTime, nullable=True, comment='向量计算时间')

    extract_model = Column(String(200), nullable=True, server_default=text("''"), comment='抽取所用模型')
    extract_status = Column(String(20), nullable=True, server_default=text("'ok'"), comment='抽取状态')
    extract_error = Column(String(500), nullable=True, server_default=text("''"), comment='抽取失败原因')
    extract_time = Column(DateTime, nullable=True, comment='抽取时间')
    pages = Column(Integer, nullable=True, comment='PDF 页数')
    text_chars = Column(Integer, nullable=True, comment='正文字符数')

    status = Column(CHAR(1), nullable=True, server_default='0', comment='状态（0正常 1停用，停用即不进检索）')
    del_flag = Column(CHAR(1), nullable=True, server_default='0', comment='删除标志（0存在 2删除）')
    create_by = Column(String(64), nullable=True, server_default=text("''"), comment='创建者')
    create_time = Column(DateTime, nullable=True, comment='创建时间', default=datetime.now)
    update_by = Column(String(64), nullable=True, server_default=text("''"), comment='更新者')
    update_time = Column(DateTime, nullable=True, comment='更新时间', default=datetime.now)
    remark = Column(String(500), nullable=True, comment='备注')


class ActionLiteratureText(Base):
    """
    针灸文献全文，与 `ActionLiterature` 1:1

    **单独一张表**：567 篇全文合计 14.3M 字符、单篇中位 17.9k。列表查询与检索排序
    都不读正文，混在主表里会让每次 `select *` 平均多拖 20KB。

    `clean_text` 是切除 PDF 夹带内容后的正文（见 `tools/lit_declean.py`）。
    **检索与展示用它，元数据重抽仍用 `full_text`** —— 原文要留着，切错了能回滚、
    人工复核时能看到切掉的是什么。为空表示无须切除。
    """

    __tablename__ = 'action_literature_text'
    __table_args__ = {'comment': '针灸文献全文'}

    lit_id = Column(BigInteger, primary_key=True, comment='文献id')
    corpus_no = Column(Integer, nullable=False, comment='语料编号')
    full_text = Column(Text, nullable=True, comment='NFKC 规范化后的 PDF 正文')
    clean_text = Column(Text, nullable=True, comment='切除夹带后的正文；为空表示无须切除')


class ActionConditionDict(Base):
    """
    病种词表：原始标签 → 规范名 → 上位类目

    抽取产出的 `condition` 是模型按各篇原文写的自由标签，实测 566 篇产出 485 个
    不同标签、80% 只出现一次（失眠散在 15 种写法里共 38 篇）。不归并的直接后果是
    覆盖度闸对几乎所有研究方向都判「本库撑不住」，而库里其实有料。

    **norm 与 group 必须分两层**：「围绝经期失眠」不是「失眠」的另一种写法 ——
    人群、病因、干预方案都不同，合并到 norm 就是把两类研究混为一谈；但判
    「这个方向撑不撑得住」时它确实该算进失眠。一层解决不了这个矛盾。

    `source='manual'` 的行由 `tools/lit_conditions.py` 重跑时**不覆盖**，
    同 `action_site_text` 的人工覆盖优先。
    """

    __tablename__ = 'action_condition_dict'
    __table_args__ = {'comment': '病种词表'}

    raw_name = Column(String(200), primary_key=True, comment='原始标签，永不修改')
    norm_name = Column(String(200), nullable=False, comment='规范名，只合并同义词与异写')
    group_name = Column(String(200), nullable=False, comment='上位类目，覆盖度统计与检索扩展用')
    system_name = Column(String(50), nullable=True, server_default=text("'其他'"), comment='人体系统归类')
    hits = Column(Integer, nullable=True, server_default='0', comment='该标签在语料中出现的篇数')
    source = Column(String(20), nullable=True, server_default=text("'llm'"), comment='llm/manual，人工优先')
    create_time = Column(DateTime, nullable=True, comment='创建时间', default=datetime.now)


class ActionBackgroundRun(Base):
    """
    背景与讨论智能生成任务（报告助手第四步的第四个工具）

    研究方向 → 检索 `ActionLiterature` → 研究背景初稿 + 推荐近 3-5 年核心文献。
    算法在 `tools/background_worker_tool`。

    **为什么不走 `/report-assist` 那条同步路**：另外三个工具（续写/润色/翻译）是秒级
    单次模型调用；这一个是 PICO + 4 槽检索 + 4 槽写作 + 引证核验，实测约 5 分钟，
    同步跑必然超时。所以照第三步 checklist 校验那套「提交 → 轮询」的 worker 模式另建。

    **结果整块存 JSON 不拆子表**：一次生成的产出（正文分段 / 参考文献 / 引证核验）
    只作为一次生成的完整快照被读取与展示，没有跨记录的查询需求。拆子表只换来级联维护。

    **`corpus_snapshot` 必须存快照，不能查的时候现算**：语料构成（「阴性 0 篇」那组
    数字）是这次生成的证据基础。文献库随时会补录，三个月后现算会得到与当时不同的数字，
    而用户当初正是基于那组数字判断该不该信这段背景的。
    """

    __tablename__ = 'action_background_run'
    __table_args__ = {'comment': '背景与讨论智能生成任务'}

    run_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='任务id')
    user_id = Column(BigInteger, nullable=False, comment='访客id')
    session_id = Column(String(64), nullable=False, comment='worker 任务id，轮询用')
    topic = Column(String(500), nullable=False, comment='用户输入的研究方向；删除时随记录物理清除')
    guideline_code = Column(String(64), nullable=True, server_default=text("''"), comment='按哪份规范写')
    locale = Column(String(8), nullable=True, server_default=text("'zh'"), comment='语言')

    run_status = Column(String(20), nullable=True, server_default=text("'pending'"), comment='任务状态')
    progress = Column(Integer, nullable=True, server_default='0', comment='进度百分比')
    phase = Column(String(20), nullable=True, server_default=text("''"), comment='当前阶段 pico/search/write/verify')
    error_msg = Column(String(500), nullable=True, server_default=text("''"), comment='失败原因')

    condition_group = Column(String(200), nullable=True, server_default=text("''"), comment='命中的病种上位类目')
    slot_total = Column(Integer, nullable=True, server_default='0', comment='段落总数')
    slot_blocked = Column(
        Integer, nullable=True, server_default='0',
        comment='被覆盖度闸拦下的段落数。**这不是失败**：本库缺流行病学文献时 S1 永远被拦，如实报告是正确行为',
    )
    ref_count = Column(Integer, nullable=True, server_default='0', comment='参考文献条数')
    partial_count = Column(
        Integer, nullable=True, server_default='0',
        comment='引证核验判为 partial 的处数。引文真实、数据真实、但那篇文献不支持这句话',
    )
    retrieve_mode = Column(
        String(30), nullable=True, server_default=text("''"),
        comment='vector+rerank / vector / bm25。**bm25 表示降级了**，实测 P@5 由 0.94 掉到 0.73',
    )

    result_json = Column(Text, nullable=True, comment='完整结果快照')
    corpus_snapshot = Column(Text, nullable=True, comment='生成当时的语料构成，必须存快照')
    model_label = Column(String(200), nullable=True, server_default=text("''"), comment='出结果的模型')

    del_flag = Column(CHAR(1), nullable=True, server_default='0', comment='删除标志（0存在 2删除）')
    create_time = Column(DateTime, nullable=True, comment='创建时间', default=datetime.now)
    finish_time = Column(DateTime, nullable=True, comment='结束时间')
