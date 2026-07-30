-- ----------------------------
-- 官网内容管理菜单（PostgreSQL）
--
-- action_* 业务表的接口权限标识已在 module_action/controller 里声明，但 sys_menu
-- 里一直没有对应记录，导致：① 后台没有菜单入口 ② 超管以外的角色无法授权。
-- 本文件补上这些菜单/按钮，可重复执行（先按 perms 清理再插入）。
--
-- menu_id 取 1073 起：现库最大为 1072，而 sys_menu_menu_id_seq 从 2000 开始发号，
-- 因此 1073-1077 这段既不与存量冲突，也不会被后续「菜单管理」页面新增的记录占用。
-- ----------------------------

begin;

-- 幂等：先清掉本文件管辖的菜单及其角色授权
delete from sys_role_menu where menu_id in (select menu_id from sys_menu where perms like 'action:news:%');
delete from sys_menu where perms like 'action:news:%';

-- 新闻管理菜单（挂在「系统管理」目录 parent_id = 1 下，排在文件管理之后）
insert into sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
values (1073, '新闻管理', 1, 11, 'news', 'system/news/index', '', '', 1, 0, 'C', '0', '0', 'action:news:list', 'documentation', 'admin', current_timestamp, '官网新闻动态维护');

-- 按钮权限
insert into sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
values (1074, '新闻查询', 1073, 1, '', '', '', '', 1, 0, 'F', '0', '0', 'action:news:query',  '#', 'admin', current_timestamp, ''),
       (1075, '新闻新增', 1073, 2, '', '', '', '', 1, 0, 'F', '0', '0', 'action:news:add',    '#', 'admin', current_timestamp, ''),
       (1076, '新闻修改', 1073, 3, '', '', '', '', 1, 0, 'F', '0', '0', 'action:news:edit',   '#', 'admin', current_timestamp, ''),
       (1077, '新闻删除', 1073, 4, '', '', '', '', 1, 0, 'F', '0', '0', 'action:news:remove', '#', 'admin', current_timestamp, '');

commit;
