-- ============================================================================
-- ai_models 增量：结构化输出方式（structured_method）
--
-- 让模型「按给定 JSON 结构回话」有四种实现，厂商支持情况**按模型**不同 ——
-- 同一个 deepseek 在官方端点支持 json_schema，在火山方舟上就回 400
-- `response_format.type: json_schema is not supported by this model`。
--
-- 取值（由强到弱，也是自动降级的顺序）：
--   json_schema       服务端按 JSON Schema 约束解码，最稳，默认从它起步
--   function_calling  走工具调用，兼容面最广
--   json_mode         只保证是合法 JSON，字段对不对得自己验
--   text              纯文本 + 自己抠 JSON，什么都不保证，最后一档兜底
--   空 / auto         交给 worker 运行时探测；探测出结果会自动回写到这一列
--
-- 留空是推荐值：撞对了自动记住，撞错了（探测判断失误）再手动钉死。
-- 反过来一开始就手填，填错的代价是整条链路用一种更弱的方式跑，不报错、只是结果更差。
--
-- 跑在 ruoyi-fastapi-pg.sql 之后。可重复执行。
-- ============================================================================

alter table ai_models add column if not exists structured_method varchar(32) default null;

comment on column ai_models.structured_method is '结构化输出方式(空=自动探测 json_schema function_calling json_mode text)';
