-- ----------------------------
-- 增量：action_guideline 的版本号拆成中英两列
--
-- 原来只有一列 `version`，装的是「2010 修订 · 6 领域 / 17 条目」这种要显示给访客的中文，
-- 于是英文界面上规范卡片与版本管理表的「版本」一栏原样吐中文。
-- 版本号在这里是一句展示文案、不是内部版本标识，按全表 name_zh/name_en、summary_zh/summary_en
-- 的惯例拆成 version_zh / version_en，前台走 pick() 取值（en 为空时回落 zh）。
--
-- 全量文件 action-website-pg.sql 已同步改过（建表 + 6 条种子），两边写入语义一致。
-- 可反复执行。
-- ----------------------------

-- 1、加列（rename 到 version_zh；已经改过的库跳过）
do $$
begin
    if exists (
        select 1 from information_schema.columns
        where table_name = 'action_guideline' and column_name = 'version'
    ) then
        alter table action_guideline rename column version to version_zh;
    end if;
end $$;

alter table action_guideline add column if not exists version_zh varchar(64) default '';
alter table action_guideline add column if not exists version_en varchar(64) default '';

comment on column action_guideline.version_zh is '版本（中文）';
comment on column action_guideline.version_en is '版本（英文）';

-- 2、回填 6 份种子规范的英文版本号
--    文案取自 action-frontend/i18n/locales/en.json 的 guidelines.s126/s131/s136/s141/s146/s151。
--    只填还空着的行 —— 后台已经人工改过的不覆盖。
update action_guideline set version_en = 'Revised 2010 · 6 domains / 17 items'
    where upper(code) = 'STRICTA' and coalesce(version_en, '') = '';
update action_guideline set version_en = 'Extension 2018'
    where upper(code) = 'SPIRIT' and coalesce(version_en, '') = '';
update action_guideline set version_en = 'Current checklist'
    where upper(code) = 'PRISMA' and coalesce(version_en, '') = '';
update action_guideline set version_en = 'v1.0 · 13 domains / 30 items'
    where upper(code) = 'CARE' and coalesce(version_en, '') = '';
update action_guideline set version_en = 'Current version'
    where upper(code) = 'RIGHT' and coalesce(version_en, '') = '';
update action_guideline set version_en = 'Version 2.0 (2020)'
    where upper(code) = 'ARRIVE' and coalesce(version_en, '') = '';
-- STROBE 那行由 sql/action-checklist-pg.sql 补录（素材待补、release_state=soon），一并回填
update action_guideline set version_en = 'Current version'
    where upper(code) = 'STROBE' and coalesce(version_en, '') = '';
