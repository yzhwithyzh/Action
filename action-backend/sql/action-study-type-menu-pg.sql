-- ----------------------------
-- 研究类型管理菜单（PostgreSQL）
--
-- 对应 action-admin 的 src/views/system/studyType/index.vue，接口权限标识见
-- module_action/controller/action_admin_controller.py 的「研究类型」一段。
--
-- 【这张表管什么】`action_study_type` 是**报告助手第一步的问卷词表** —— 决定「你的研究属于
-- 哪一类」有哪些选项、每个选项挂哪些规范标签、推荐哪些统计方法，以及最要紧的
-- `hot_guideline`（第二步展开哪份 checklist）。此前它只能改 SQL，没有任何后台入口。
--
-- 【与「规范分类管理」的分工】那张表（`action_guideline_category`）是规范目录页的**陈列分类**，
-- 这张是**助手的问卷词表**，用途不同、不要合并。同一类研究在两边取同样的 key
-- （protocol / animal / guideline），但不构成外键关系。
--
-- 【可反复执行】先按 perms 前缀清掉旧菜单与角色关联，再整段插回来 —— 与
-- action-guideline-menu-pg.sql 同一个写法。菜单 id 取 1108 起（现有 action 菜单占到 1107）。
-- ----------------------------

begin;

delete from sys_role_menu where menu_id in (
    select menu_id from sys_menu where perms like 'action:studyType:%'
);
delete from sys_menu where perms like 'action:studyType:%';

insert into sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
values (1108, '研究类型管理', 1, 18, 'studyType', 'system/studyType/index', '', '', 1, 0, 'C', '0', '0', 'action:studyType:list', 'tree', 'admin', current_timestamp, '报告助手第一步的问卷词表：类型 → 规范标签 + 重点规范 + 统计推荐');

insert into sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
values (1109, '类型新增', 1108, 1, '', '', '', '', 1, 0, 'F', '0', '0', 'action:studyType:add',    '#', 'admin', current_timestamp, ''),
       (1110, '类型修改', 1108, 2, '', '', '', '', 1, 0, 'F', '0', '0', 'action:studyType:edit',   '#', 'admin', current_timestamp, ''),
       (1111, '类型删除', 1108, 3, '', '', '', '', 1, 0, 'F', '0', '0', 'action:studyType:remove', '#', 'admin', current_timestamp, '');

-- 超级管理员（role_id=1）默认拥有全部菜单，这里给其余已存在的角色留空，由管理员按需分配。
-- 与其他 action 菜单一致：不擅自给业务角色开权限。

commit;

-- 核对：
--   select menu_id, menu_name, perms from sys_menu where perms like 'action:studyType:%' order by menu_id;
