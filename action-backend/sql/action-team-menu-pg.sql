-- ----------------------------
-- 团队成员管理菜单（PostgreSQL）
--
-- 对应 action-admin 的 src/views/system/teamMember/index.vue，
-- 接口权限标识见 module_action/controller/action_admin_controller.py 的 action:teamMember:*。
-- 与 action-checklist-menu-pg.sql 同样可重复执行（先按 perms 清理再插入）。
--
-- menu_id 取 1084 起：action-checklist-menu-pg.sql 已占到 1083，
-- sys_menu_menu_id_seq 从 2000 发号，因此 1084-1088 既不与存量冲突，
-- 也不会被「菜单管理」页面新增的记录占用。
-- ----------------------------

begin;

-- 幂等：先清掉本文件管辖的菜单及其角色授权
delete from sys_role_menu where menu_id in (select menu_id from sys_menu where perms like 'action:teamMember:%');
delete from sys_menu where perms like 'action:teamMember:%';

-- 团队成员管理菜单（挂在「系统管理」目录 parent_id = 1 下，排在规范条目管理之后）
insert into sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
values (1084, '团队成员管理', 1, 13, 'teamMember', 'system/teamMember/index', '', '', 1, 0, 'C', '0', '0', 'action:teamMember:list', 'peoples', 'admin', current_timestamp, '官网「关于我们」页的国际顾问委员会与核心执行团队成员维护');

-- 按钮权限
insert into sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
values (1085, '成员查询', 1084, 1, '', '', '', '', 1, 0, 'F', '0', '0', 'action:teamMember:query',  '#', 'admin', current_timestamp, ''),
       (1086, '成员新增', 1084, 2, '', '', '', '', 1, 0, 'F', '0', '0', 'action:teamMember:add',    '#', 'admin', current_timestamp, ''),
       (1087, '成员修改', 1084, 3, '', '', '', '', 1, 0, 'F', '0', '0', 'action:teamMember:edit',   '#', 'admin', current_timestamp, ''),
       (1088, '成员删除', 1084, 4, '', '', '', '', 1, 0, 'F', '0', '0', 'action:teamMember:remove', '#', 'admin', current_timestamp, '');

commit;
