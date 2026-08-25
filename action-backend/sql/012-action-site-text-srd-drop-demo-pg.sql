-- ----------------------------
-- 增量：撤掉 SRD 页「载入示例」入口，清掉它留下的孤儿文案键
--
-- `srd.s016`（「没有文件？载入两篇示例 PDF 试用」）对应的按钮已从
-- `action-frontend/pages/srd.vue` 移除，i18n 两份 locale JSON 里的键也一并删了。
--
-- 但 `tools.extract_site_texts` 只做 upsert、不删旧键（它不知道一个键是「这次没生成」
-- 还是「本来就不该动」），所以已经跑过全量的库里这一行会留下来：
-- 后台「站点文案管理」里搜得到、改得动，官网上却没有任何地方读它 —— 改了不生效，
-- 比看不见更难排查。这里显式删掉。
--
-- 走软删（`del_flag='2'`）而不是 `delete`：跟全库其余表的约定一致，
-- 且哪天要把示例入口挂回去，重跑一次同步脚本的 on conflict 会把这行刷回来
-- （届时记得把 del_flag 改回 '0'）。
--
-- 全量文件 `action-site-text-pg.sql` 已重新生成、不含此键，新库无需执行本文件；
-- 只有已经执行过旧版全量的库需要跑一次。可重复执行。
-- ----------------------------

begin;

update action_site_text
   set del_flag    = '2',
       update_time = now(),
       remark      = 'SRD 页「载入示例」入口已撤除，键不再被前端读取'
 where text_key = 'srd.s016'
   and del_flag <> '2';

commit;
