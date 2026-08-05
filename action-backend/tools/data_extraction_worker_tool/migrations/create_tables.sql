-- 数据抽取 Worker Tool 数据库迁移脚本

-- 1. 修改现有的 data_extraction_history 表（新增 Worker 相关字段）
-- 注意：该表已存在，这里只添加缺少的字段
-- 注意：ALTER TABLE ADD COLUMN 不支持 IF NOT EXISTS，如果列已存在会报错（迁移脚本会自动忽略）

-- 新增 total_file_size 字段
ALTER TABLE `data_extraction_history`
ADD COLUMN `total_file_size` BIGINT DEFAULT 0 COMMENT '文件总大小（字节）' AFTER `files_count`;

-- 新增 extraction_schema 字段
ALTER TABLE `data_extraction_history`
ADD COLUMN `extraction_schema` JSON COMMENT '抽取 schema（JSON）' AFTER `extraction_mode`;

-- 新增 output_log_path 字段
ALTER TABLE `data_extraction_history`
ADD COLUMN `output_log_path` VARCHAR(512) COMMENT '输出日志文件路径' AFTER `output_excel_path`;

-- 创建 session_id 唯一索引
CREATE UNIQUE INDEX `idx_session_id` ON `data_extraction_history` (`session_id`);

-- 创建 user_id 索引
CREATE INDEX `idx_user_id` ON `data_extraction_history` (`user_id`);

-- 创建 status 索引
CREATE INDEX `idx_status` ON `data_extraction_history` (`status`);


-- 2. 创建数据抽取文件状态表
CREATE TABLE IF NOT EXISTS `data_extraction_file_status` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID',
    `session_id` VARCHAR(64) NOT NULL COMMENT '会话 ID',
    `file_name` VARCHAR(512) NOT NULL COMMENT '文件名',
    `file_url` VARCHAR(1024) COMMENT '文件 URL',
    `file_index` INT NOT NULL COMMENT '文件索引',
    `local_path` VARCHAR(1024) COMMENT '本地路径',

    -- 状态
    `status` VARCHAR(32) DEFAULT 'pending' COMMENT '状态：pending/processing/completed/error',

    -- 错误信息
    `error_message` TEXT COMMENT '错误信息',

    -- 处理时长
    `processing_duration` INT COMMENT '处理时长（秒）',

    -- 时间戳
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `completed_at` DATETIME COMMENT '完成时间',

    INDEX `idx_session_id` (`session_id`),
    INDEX `idx_status` (`status`),
    INDEX `idx_session_file` (`session_id`, `file_name`(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据抽取文件状态表';
