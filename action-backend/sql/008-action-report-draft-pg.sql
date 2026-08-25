-- ----------------------------
-- 008 · 报告草稿两张表（报告助手第二步 · PostgreSQL）
--
-- 【为什么要这两张表】第二步此前是**只读展示**：checklist 条目排在那里看，针灸四字段是
-- readonly 的示例值，没有任何承载体存下用户写的东西。于是第四步的续写没处落笔、第五步的
-- 导出没内容可导、第三步只能让用户另行粘贴稿件——文档里「模板 → 初稿 → 优化 → 导出」
-- 那条链子是断的。这两张表就是那个承载体。
--
-- 【为什么拆两张】主表一行 = 一份报告初稿，逐条目正文单独一张：条目数按规范从 21 到 79 不等，
-- 塞进主表要么开一堆列要么存 JSON，前者随规范变动，后者没法按条目 id 查改。
--
-- 【针灸四字段为什么在主表而不在条目表】它们是文档 2.2 的「针灸特色专属字段」，
-- 语义上**不属于任何单条 checklist 条目**，而要在生成初稿时注入到多条里去
-- （这正是文档说的「关键参数一次定义、全文联动同步」）。挂在主表才只填一次。
--
-- 【隐私】草稿正文是用户未发表的研究内容，只进这张业务库表，**不进 OSS**
-- （那个桶是整桶公共读）。与第三步刻意不落稿件的取舍不同：第三步的稿件是过路数据，
-- 这里的草稿是用户明确要求保存下来的东西，不存反而是丢数据。
--
-- 跑在 `action-website-pg.sql` 之后（依赖 action_guideline / sys_user 已建好）。
--
-- 【为什么这份增量里没有 drop】编号增量是运维会**反复重跑**的东西（补机器、确认某台有没有
-- 漏跑），全量文件才是可以带 drop 的快照。这两张表装的是用户自己写的报告正文，重跑一次
-- drop 就是把所有人的草稿静默清空，且没有任何恢复路径。所以这里一律 if not exists。
-- ----------------------------

begin;

-- ----------------------------
-- 1、报告草稿主表
-- ----------------------------
create table if not exists action_report_draft (
    draft_id       serial       primary key,
    user_id        bigint       not null,
    guideline_id   int          not null,
    study_type_key varchar(32)  default '',
    title          varchar(300) default '',
    acu_basis      varchar(32)  default '',
    acu_basis_note varchar(1000) default '',
    acu_needle     varchar(1000) default '',
    acu_deqi       varchar(1000) default '',
    acu_control    varchar(1000) default '',
    status         char(1)      default '0',
    del_flag       char(1)      default '0',
    create_by      varchar(64)  default '',
    create_time    timestamp,
    update_by      varchar(64)  default '',
    update_time    timestamp
);

comment on table  action_report_draft is '官网-报告助手报告草稿';
comment on column action_report_draft.draft_id is '草稿id';
comment on column action_report_draft.user_id is '归属访客用户id（sys_user.user_id）';
comment on column action_report_draft.guideline_id is '所依据的报告规范id（action_guideline.guideline_id）';
comment on column action_report_draft.study_type_key is '第一步判定的研究类型（action_study_type.type_key），仅作留档';
comment on column action_report_draft.title is '草稿名称，由用户自取';
comment on column action_report_draft.acu_basis is '穴位选取依据（bianzheng辨证 / duizheng对症 / jingyan经验）';
comment on column action_report_draft.acu_basis_note is '选穴依据补充说明';
comment on column action_report_draft.acu_needle is '进针手法（角度、深度、行针手法）';
comment on column action_report_draft.acu_deqi is '得气感应（酸麻胀重等患者感知描述）';
comment on column action_report_draft.acu_control is '对照 / 对照措施设置（非穴道对照、假电针参数等）';
comment on column action_report_draft.status is '状态（0正常 1停用）';
comment on column action_report_draft.del_flag is '删除标志（0存在 2删除）';

-- 列表按「我的 + 最近改的在前」取，这个索引就是那条查询的形状
create index if not exists idx_action_report_draft_user on action_report_draft (user_id, update_time desc);

-- ----------------------------
-- 2、草稿的逐条目正文
--
-- 一条 checklist 条目对应一行。用户没填过的条目**不建行**——
-- 「没有行」与「填了空串」在完成度统计里是同一回事，不必为 282 条各占一行。
-- ----------------------------
create table if not exists action_report_draft_item (
    id          serial primary key,
    draft_id    int    not null,
    item_id     int    not null,
    content     text,
    update_time timestamp
);

comment on table  action_report_draft_item is '官网-报告草稿逐条目正文';
comment on column action_report_draft_item.draft_id is '所属草稿id（action_report_draft.draft_id）';
comment on column action_report_draft_item.item_id is '所应答的 checklist 条目id（action_guideline_item.item_id）';
comment on column action_report_draft_item.content is '用户为该条目写的正文';

-- 唯一索引挡的是「同一条目两份正文」：保存是先删后插（见 ReportDraftDao.replace_draft_items），
-- 同一账号两个标签页并发保存时，落后的那次会撞在这个索引上失败而不是写出重复行
create unique index if not exists uk_action_report_draft_item on action_report_draft_item (draft_id, item_id);

-- ----------------------------
-- 3、矫正由 create_all 建出来的错误默认值（可反复执行）
--
-- 【为什么需要这一段】应用启动时 SQLAlchemy 的 `create_all` 会先按 ORM 建表，本文件的
-- `create table if not exists` 于是成了空操作 —— 两条路径建出来的表并不等价。DO 里空串默认值
-- 若写成 `server_default="''"`，DDL 会渲染成 `DEFAULT ''''''`，默认值变成「两个引号字符」
-- 这个**非空**字符串。表现是：新建的草稿一进来针灸四字段就都是 `''`，
-- 「草稿还没有任何内容，请先填写至少一条」那道闸直接失效，用户能对着一份空稿去合成初稿。
-- DO 侧已改用 `text("''")`，这里把已经建歪的库拉回来，并洗掉写进去的那些 `''`。
-- ----------------------------
alter table action_report_draft alter column study_type_key set default '';
alter table action_report_draft alter column title          set default '';
alter table action_report_draft alter column acu_basis      set default '';
alter table action_report_draft alter column acu_basis_note set default '';
alter table action_report_draft alter column acu_needle     set default '';
alter table action_report_draft alter column acu_deqi       set default '';
alter table action_report_draft alter column acu_control    set default '';
alter table action_report_draft alter column create_by      set default '';
alter table action_report_draft alter column update_by      set default '';

update action_report_draft
   set study_type_key = case when study_type_key = '''''' then '' else study_type_key end,
       title          = case when title          = '''''' then '' else title end,
       acu_basis      = case when acu_basis      = '''''' then '' else acu_basis end,
       acu_basis_note = case when acu_basis_note = '''''' then '' else acu_basis_note end,
       acu_needle     = case when acu_needle     = '''''' then '' else acu_needle end,
       acu_deqi       = case when acu_deqi       = '''''' then '' else acu_deqi end,
       acu_control    = case when acu_control    = '''''' then '' else acu_control end,
       create_by      = case when create_by      = '''''' then '' else create_by end,
       update_by      = case when update_by      = '''''' then '' else update_by end
 where '''''' in (study_type_key, title, acu_basis, acu_basis_note, acu_needle, acu_deqi, acu_control,
                  create_by, update_by);

commit;
