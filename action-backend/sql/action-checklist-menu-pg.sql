-- ----------------------------
-- 规范条目（checklist）管理菜单（PostgreSQL）
--
-- 对应 action-admin 的 src/views/system/guidelineItem/index.vue，
-- 接口权限标识见 module_action/controller/action_admin_controller.py 的 action:guidelineItem:*。
-- 与 action-menu-pg.sql 同样可重复执行（先按 perms 清理再插入）。
--
-- menu_id 取 1078 起：action-menu-pg.sql 已占到 1077，sys_menu_menu_id_seq 从 2000 发号，
-- 因此 1078-1082 既不与存量冲突，也不会被「菜单管理」页面新增的记录占用。
-- ----------------------------

begin;

-- 幂等：先清掉本文件管辖的菜单及其角色授权
delete from sys_role_menu where menu_id in (select menu_id from sys_menu where perms like 'action:guidelineItem:%');
delete from sys_menu where perms like 'action:guidelineItem:%';

-- 规范条目管理菜单（挂在「系统管理」目录 parent_id = 1 下，排在新闻管理之后）
insert into sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
values (1078, '规范条目管理', 1, 12, 'guidelineItem', 'system/guidelineItem/index', '', '', 1, 0, 'C', '0', '0', 'action:guidelineItem:list', 'form', 'admin', current_timestamp, '报告规范 checklist 条目维护，供报告助手第二、三步取用');

-- 按钮权限
insert into sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
values (1079, '条目查询', 1078, 1, '', '', '', '', 1, 0, 'F', '0', '0', 'action:guidelineItem:query',  '#', 'admin', current_timestamp, ''),
       (1080, '条目新增', 1078, 2, '', '', '', '', 1, 0, 'F', '0', '0', 'action:guidelineItem:add',    '#', 'admin', current_timestamp, ''),
       (1081, '条目修改', 1078, 3, '', '', '', '', 1, 0, 'F', '0', '0', 'action:guidelineItem:edit',   '#', 'admin', current_timestamp, ''),
       (1082, '条目删除', 1078, 4, '', '', '', '', 1, 0, 'F', '0', '0', 'action:guidelineItem:remove', '#', 'admin', current_timestamp, '');

-- 条目管理页的「所属规范」下拉走 action:guideline:list 接口。该权限此前只在 controller 里声明、
-- sys_menu 无记录，超管以外的角色授不了权，下拉会空。这里补一条隐藏的按钮权限（visible = '1'），
-- 规范目录本身尚无管理页面，故不建目录型菜单。
delete from sys_role_menu where menu_id in (select menu_id from sys_menu where perms = 'action:guideline:list');
delete from sys_menu where perms = 'action:guideline:list';
insert into sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
values (1083, '规范目录查询', 1078, 5, '', '', '', '', 1, 0, 'F', '1', '0', 'action:guideline:list', '#', 'admin', current_timestamp, '条目管理页的规范下拉依赖此权限');

commit;
