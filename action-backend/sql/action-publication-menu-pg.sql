-- ----------------------------
-- 成果发表管理菜单（PostgreSQL）
--
-- 对应 action-admin 的 src/views/system/publication/index.vue，接口权限标识见
-- module_action/controller/action_admin_controller.py 的 action:publication:*。
-- 与其余 action-*-menu-pg.sql 一样可重复执行。
--
-- menu_id 取 1112 起：action-study-type-menu-pg.sql 已占到 1111，sys_menu_menu_id_seq
-- 从 2000 发号，因此 1112-1116 既不与存量冲突，也不会被「菜单管理」页面新增的记录占用。
-- ----------------------------

begin;

-- 幂等：先清掉本文件管辖的菜单及其角色授权
delete from sys_role_menu where menu_id in (
    select menu_id from sys_menu where perms like 'action:publication:%'
);
delete from sys_menu where perms like 'action:publication:%';

-- 成果发表管理菜单（挂在「系统管理」目录 parent_id = 1 下，排在研究类型管理之后）
insert into sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
values (1112, '成果发表管理', 1, 19, 'publication', 'system/publication/index', '', '', 1, 0, 'C', '0', '0', 'action:publication:list', 'education', 'admin', current_timestamp, '官网「成果发表」页的论文列表，支持 DOI 与 PDF 自动解析录入');

-- 按钮权限。解析（DOI / PDF）与上传（PDF 全文 / 配图）都收在 edit 之下：
-- 它们只是「填这张表单」的辅助手段，单独授权只会让管理员拿到一个点了就报没权限的按钮。
insert into sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
values (1113, '成果查询', 1112, 1, '', '', '', '', 1, 0, 'F', '0', '0', 'action:publication:query',  '#', 'admin', current_timestamp, ''),
       (1114, '成果新增', 1112, 2, '', '', '', '', 1, 0, 'F', '0', '0', 'action:publication:add',    '#', 'admin', current_timestamp, ''),
       (1115, '成果修改', 1112, 3, '', '', '', '', 1, 0, 'F', '0', '0', 'action:publication:edit',   '#', 'admin', current_timestamp, '含 DOI/PDF 自动解析与全文、配图上传'),
       (1116, '成果删除', 1112, 4, '', '', '', '', 1, 0, 'F', '0', '0', 'action:publication:remove', '#', 'admin', current_timestamp, '');

commit;
