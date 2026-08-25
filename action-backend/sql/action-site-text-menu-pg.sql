-- ----------------------------
-- 站点文案管理菜单（PostgreSQL）
--
-- 对应 action-admin 的 src/views/system/siteText/index.vue，接口权限标识见
-- module_action/controller/action_admin_controller.py 的 action:siteText:*。
-- 与其余 action-*-menu-pg.sql 一样可重复执行。
--
-- menu_id 取 1104 起：action-resource-link-menu-pg.sql 已占到 1103，sys_menu_menu_id_seq
-- 从 2000 发号，因此 1104-1107 既不与存量冲突，也不会被「菜单管理」页面新增的记录占用。
--
-- **没有「新增」和「删除」按钮权限，这是有意的**：一条文案对应模板里的一个 $t() 键，
-- 键由前端代码定义。后台能建键 = 建出永远没人读的孤儿行；后台能删键 = 官网上一段文字
-- 凭空消失且无从查起。词条的增删由 `python -m tools.extract_site_texts` 从
-- i18n JSON 同步，后台只负责改文案和还原默认。
-- ----------------------------

begin;

-- 幂等：先清掉本文件管辖的菜单及其角色授权
delete from sys_role_menu where menu_id in (
    select menu_id from sys_menu where perms like 'action:siteText:%'
);
delete from sys_menu where perms like 'action:siteText:%';

-- 站点文案管理菜单（挂在「系统管理」目录 parent_id = 1 下，排在资源中心管理之后）
insert into sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
values (1104, '站点文案管理', 1, 17, 'siteText', 'system/siteText/index', '', '', 1, 0, 'C', '0', '0', 'action:siteText:list', 'documentation', 'admin', current_timestamp, '官网各页面的标题/导语/正文/按钮文字，改完需重新生成官网才对搜索引擎可见');

-- 按钮权限
insert into sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
values (1105, '文案查询', 1104, 1, '', '', '', '', 1, 0, 'F', '0', '0', 'action:siteText:query',   '#', 'admin', current_timestamp, ''),
       (1106, '文案修改', 1104, 2, '', '', '', '', 1, 0, 'F', '0', '0', 'action:siteText:edit',    '#', 'admin', current_timestamp, '含「还原默认」'),
       (1107, '重新生成官网', 1104, 3, '', '', '', '', 1, 0, 'F', '0', '0', 'action:siteText:rebuild', '#', 'admin', current_timestamp, '触发官网静态站重新构建，耗时数分钟，建议只授给管理员');

commit;
