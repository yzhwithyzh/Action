# Database Migration Guide for Data Extraction Worker

## ⚠️ Error Message

If you see this error:
```
Unconsumed column names: extraction_schema, total_file_size
```

It means the database is missing required columns. You need to run the migration.

---

## 🚀 Quick Fix (Copy & Paste)

### Option 1: Using Python Script

```bash
cd backend/tools/data_extraction_worker_tool/migrations
python run_migrations.py
```

### Option 2: Using MySQL Command

```bash
mysql -u root -p your_database < backend/tools/data_extraction_worker_tool/migrations/create_tables.sql
```

Replace:
- `root` with your MySQL username
- `your_database` with your database name

### Option 3: Manual SQL Execution

Copy and paste the SQL below into your MySQL client:

```sql
-- Add missing columns to data_extraction_history table
ALTER TABLE `data_extraction_history`
ADD COLUMN `total_file_size` BIGINT DEFAULT 0 COMMENT '文件总大小（字节）' AFTER `files_count`;

ALTER TABLE `data_extraction_history`
ADD COLUMN `extraction_schema` JSON COMMENT '抽取 schema（JSON）' AFTER `extraction_mode`;

ALTER TABLE `data_extraction_history`
ADD COLUMN `output_log_path` VARCHAR(512) COMMENT '输出日志文件路径' AFTER `output_excel_path`;

-- Add indexes (ignore errors if they already exist)
CREATE UNIQUE INDEX `idx_session_id` ON `data_extraction_history` (`session_id`);
CREATE INDEX `idx_user_id` ON `data_extraction_history` (`user_id`);
CREATE INDEX `idx_status` ON `data_extraction_history` (`status`);

-- Create data_extraction_file_status table
CREATE TABLE IF NOT EXISTS `data_extraction_file_status` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID',
    `session_id` VARCHAR(64) NOT NULL COMMENT '会话 ID',
    `file_name` VARCHAR(512) NOT NULL COMMENT '文件名',
    `file_url` VARCHAR(1024) COMMENT '文件 URL',
    `file_index` INT NOT NULL COMMENT '文件索引',
    `local_path` VARCHAR(1024) COMMENT '本地路径',
    `status` VARCHAR(32) DEFAULT 'pending' COMMENT '状态：pending/processing/completed/error',
    `error_message` TEXT COMMENT '错误信息',
    `processing_duration` INT COMMENT '处理时长（秒）',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `completed_at` DATETIME COMMENT '完成时间',
    INDEX `idx_session_id` (`session_id`),
    INDEX `idx_status` (`status`),
    INDEX `idx_session_file` (`session_id`, `file_name`(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据抽取文件状态表';
```

---

## ✅ Verify Migration

Run this SQL to verify:

```sql
-- Check data_extraction_history columns
DESCRIBE data_extraction_history;

-- Check if data_extraction_file_status table exists
SHOW TABLES LIKE 'data_extraction_file_status';
```

Expected result:
- `data_extraction_history` should have: `total_file_size`, `extraction_schema`, `output_log_path`
- `data_extraction_file_status` table should exist

---

## 🔧 Troubleshooting

**"Duplicate column name" error**
- This is OK! It means the column already exists. Skip it.

**"Duplicate key name" error**
- This is OK! It means the index already exists. Skip it.

**"ModuleNotFoundError: No module named 'sqlalchemy'"**
- Activate your Python virtual environment first:
  ```bash
  source venv/bin/activate  # Linux/Mac
  venv\Scripts\activate     # Windows
  ```

**Connection refused**
- Check if MySQL is running
- Verify database credentials in `backend/config/env.py`

---

## 📚 More Information

- [README.md](../README.md) - Full documentation
- [QUICKSTART.md](../QUICKSTART.md) - Quick start guide
- [执行迁移.md](执行迁移.md) - Chinese version
