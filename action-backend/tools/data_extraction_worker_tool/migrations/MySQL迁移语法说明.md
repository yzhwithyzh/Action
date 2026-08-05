# MySQL 数据库迁移语法说明

## 问题：`IF EXISTS` / `IF NOT EXISTS` 语法限制

### MySQL 版本支持

| MySQL 版本 | `DROP COLUMN IF EXISTS` | `ADD COLUMN IF NOT EXISTS` |
|-----------|------------------------|---------------------------|
| MySQL 5.7 及以下 | ❌ 不支持 | ❌ 不支持 |
| MySQL 8.0.29+ | ✅ 支持 | ✅ 支持 |
| MariaDB 10.0+ | ✅ 支持 | ✅ 支持 |

### 错误示例

```sql
-- ❌ MySQL 5.7 会报错
ALTER TABLE fulltext_screening_file_status
DROP COLUMN IF EXISTS result_json;

-- 错误信息：
-- (1064, "You have an error in your SQL syntax...")
```

---

## 解决方案：使用动态 SQL

### 方式1：检查后删除字段（推荐）

```sql
-- 安全删除字段
SET @dbname = DATABASE();
SET @tablename = 'fulltext_screening_file_status';
SET @columnname = 'result_json';

SET @preparedStatement = (
    SELECT IF(
        COUNT(*) > 0,
        CONCAT('ALTER TABLE ', @tablename, ' DROP COLUMN ', @columnname),
        'SELECT 1'  -- 字段不存在时执行空操作
    )
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @dbname
        AND TABLE_NAME = @tablename
        AND COLUMN_NAME = @columnname
);

PREPARE alterStatement FROM @preparedStatement;
EXECUTE alterStatement;
DEALLOCATE PREPARE alterStatement;
```

### 方式2：检查后添加字段

```sql
-- 安全添加字段
SET @dbname = DATABASE();
SET @tablename = 'fulltext_screening_file_status';
SET @columnname = 'file_url';

SET @preparedStatement = (
    SELECT IF(
        COUNT(*) = 0,  -- 字段不存在
        CONCAT('ALTER TABLE ', @tablename,
               ' ADD COLUMN ', @columnname,
               ' VARCHAR(1000) COMMENT ''COS 文件 URL'' AFTER file_name'),
        'SELECT 1'  -- 字段已存在时执行空操作
    )
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @dbname
        AND TABLE_NAME = @tablename
        AND COLUMN_NAME = @columnname
);

PREPARE alterStatement FROM @preparedStatement;
EXECUTE alterStatement;
DEALLOCATE PREPARE alterStatement;
```

---

## 为什么这样写？

### 原理

1. **查询 INFORMATION_SCHEMA**：检查字段是否存在
2. **动态生成 SQL**：根据检查结果决定执行什么操作
3. **PREPARE/EXECUTE**：执行动态 SQL
4. **DEALLOCATE**：清理预处理语句

### 优势

✅ **兼容性**：支持 MySQL 5.7 及以上所有版本
✅ **幂等性**：多次执行不会报错
✅ **安全性**：自动检查，避免误操作

---

## 应用到本项目

### 迁移脚本 003：删除 result_json

```sql
-- backend/tools/full_text_screening_worker_tool/migrations/003_remove_result_json_field.sql
SET @dbname = DATABASE();
SET @tablename = 'fulltext_screening_file_status';
SET @columnname = 'result_json';
SET @preparedStatement = (
    SELECT IF(
        COUNT(*) > 0,
        CONCAT('ALTER TABLE ', @tablename, ' DROP COLUMN ', @columnname),
        'SELECT 1'
    )
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @dbname
        AND TABLE_NAME = @tablename
        AND COLUMN_NAME = @columnname
);

PREPARE alterStatement FROM @preparedStatement;
EXECUTE alterStatement;
DEALLOCATE PREPARE alterStatement;
```

### 迁移脚本 004：添加 file_url 和 local_path

```sql
-- backend/tools/full_text_screening_worker_tool/migrations/004_add_file_paths.sql
-- 分两次执行，每次添加一个字段

-- 添加 file_url
SET @columnname = 'file_url';
SET @preparedStatement = (
    SELECT IF(
        COUNT(*) = 0,
        CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' VARCHAR(1000) ...'),
        'SELECT 1'
    )
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @dbname
        AND TABLE_NAME = @tablename
        AND COLUMN_NAME = @columnname
);
PREPARE alterStatement FROM @preparedStatement;
EXECUTE alterStatement;
DEALLOCATE PREPARE alterStatement;

-- 添加 local_path（类似）
```

---

## 总结

| 方法 | 适用场景 | 优缺点 |
|------|---------|--------|
| `IF EXISTS` | MySQL 8.0.29+ | ✅ 简洁，但不兼容旧版本 |
| 动态 SQL | 所有版本 | ✅ 兼容性好，稍微复杂 |

**本项目采用动态 SQL 方式，确保最大兼容性。**
