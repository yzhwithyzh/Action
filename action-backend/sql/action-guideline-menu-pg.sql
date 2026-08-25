-- ----------------------------
-- 规范目录 / 规范分类管理菜单（PostgreSQL）
--
-- 对应 action-admin 的 src/views/system/guideline/index.vue 与
-- src/views/system/guidelineCategory/index.vue，接口权限标识见
-- module_action/controller/action_admin_controller.py 的 action:guideline:* /
-- action:guidelineCategory:*。与其余 action-*-menu-pg.sql 一样可重复执行。
--
-- action:guideline:* 此前只在 controller 里声明，sys_menu 里唯一的记录是
-- action-checklist-menu-pg.sql 补的那条隐藏按钮（menu_id 1083，只为让条目管理页的
-- 规范下拉能授权）。规范目录现在有自己的管理页了，那条隐藏按钮已从该文件删除，
-- 本文件接管整个 action:guideline:* 命名空间；1083 号被下面的 delete 一并清掉。
--
-- menu_id 取 1089 起：action-team-menu-pg.sql 已占到 1088，sys_menu_menu_id_seq
-- 从 2000 发号，因此 1089-1098 既不与存量冲突，也不会被「菜单管理」页面新增的记录占用。
-- ----------------------------

begin;

-- 幂等：先清掉本文件管辖的菜单及其角色授权（含 checklist 菜单文件留下的 1083 隐藏按钮）
delete from sys_role_menu where menu_id in (
    select menu_id from sys_menu where perms like 'action:guideline:%' or perms like 'action:guidelineCategory:%'
);
delete from sys_menu where perms like 'action:guideline:%' or perms like 'action:guidelineCategory:%';

-- 规范目录管理菜单（挂在「系统管理」目录 parent_id = 1 下，排在团队成员管理之后）
insert into sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
values (1089, '规范目录管理', 1, 14, 'guideline', 'system/guideline/index', '', '', 1, 0, 'C', '0', '0', 'action:guideline:list', 'documentation', 'admin', current_timestamp, '官网「报告规范」页的规范目录维护；条目清单在「规范条目管理」页');

-- 按钮权限
insert into sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
values (1090, '规范查询', 1089, 1, '', '', '', '', 1, 0, 'F', '0', '0', 'action:guideline:query',  '#', 'admin', current_timestamp, ''),
       (1091, '规范新增', 1089, 2, '', '', '', '', 1, 0, 'F', '0', '0', 'action:guideline:add',    '#', 'admin', current_timestamp, ''),
       (1092, '规范修改', 1089, 3, '', '', '', '', 1, 0, 'F', '0', '0', 'action:guideline:edit',   '#', 'admin', current_timestamp, ''),
       (1093, '规范删除', 1089, 4, '', '', '', '', 1, 0, 'F', '0', '0', 'action:guideline:remove', '#', 'admin', current_timestamp, '');

-- 规范分类管理菜单
insert into sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
values (1094, '规范分类管理', 1, 15, 'guidelineCategory', 'system/guidelineCategory/index', '', '', 1, 0, 'C', '0', '0', 'action:guidelineCategory:list', 'tree-table', 'admin', current_timestamp, '官网「报告规范」页第①段筛选条的分类词表');

insert into sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
values (1095, '分类查询', 1094, 1, '', '', '', '', 1, 0, 'F', '0', '0', 'action:guidelineCategory:query',  '#', 'admin', current_timestamp, ''),
       (1096, '分类新增', 1094, 2, '', '', '', '', 1, 0, 'F', '0', '0', 'action:guidelineCategory:add',    '#', 'admin', current_timestamp, ''),
       (1097, '分类修改', 1094, 3, '', '', '', '', 1, 0, 'F', '0', '0', 'action:guidelineCategory:edit',   '#', 'admin', current_timestamp, ''),
       (1098, '分类删除', 1094, 4, '', '', '', '', 1, 0, 'F', '0', '0', 'action:guidelineCategory:remove', '#', 'admin', current_timestamp, '');

commit;
