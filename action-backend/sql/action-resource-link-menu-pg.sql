-- ----------------------------
-- 资源中心管理菜单（PostgreSQL）
--
-- 对应 action-admin 的 src/views/system/resourceLink/index.vue，接口权限标识见
-- module_action/controller/action_admin_controller.py 的 action:resourceLink:*。
-- 与其余 action-*-menu-pg.sql 一样可重复执行。
--
-- menu_id 取 1099 起：action-guideline-menu-pg.sql 已占到 1098，sys_menu_menu_id_seq
-- 从 2000 发号，因此 1099-1103 既不与存量冲突，也不会被「菜单管理」页面新增的记录占用。
-- ----------------------------

begin;

-- 幂等：先清掉本文件管辖的菜单及其角色授权
delete from sys_role_menu where menu_id in (
    select menu_id from sys_menu where perms like 'action:resourceLink:%'
);
delete from sys_menu where perms like 'action:resourceLink:%';

-- 资源中心管理菜单（挂在「系统管理」目录 parent_id = 1 下，排在规范分类管理之后）
insert into sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
values (1099, '资源中心管理', 1, 16, 'resourceLink', 'system/resourceLink/index', '', '', 1, 0, 'C', '0', '0', 'action:resourceLink:list', 'link', 'admin', current_timestamp, '官网首页第④段「国际报告规范组织与循证枢纽」的外链卡片');

-- 按钮权限
insert into sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
values (1100, '资源查询', 1099, 1, '', '', '', '', 1, 0, 'F', '0', '0', 'action:resourceLink:query',  '#', 'admin', current_timestamp, ''),
       (1101, '资源新增', 1099, 2, '', '', '', '', 1, 0, 'F', '0', '0', 'action:resourceLink:add',    '#', 'admin', current_timestamp, ''),
       (1102, '资源修改', 1099, 3, '', '', '', '', 1, 0, 'F', '0', '0', 'action:resourceLink:edit',   '#', 'admin', current_timestamp, ''),
       (1103, '资源删除', 1099, 4, '', '', '', '', 1, 0, 'F', '0', '0', 'action:resourceLink:remove', '#', 'admin', current_timestamp, '');

commit;
