# Full Text Screening Worker - 修复报告

## 问题描述

运行数据库迁移脚本时出现导入错误：

```
ImportError: cannot import name 'get_database_url' from 'config.env'
```

## 原因分析

`config/env.py` 中没有 `get_database_url()` 函数。该项目使用以下方式构建数据库 URL：

1. **异步模式**（在 `config/database.py` 中）：
   ```python
   ASYNC_SQLALCHEMY_DATABASE_URL = f'mysql+asyncmy://...'
   ```

2. **同步模式**（在 `config/get_scheduler.py` 中）：
   ```python
   SQLALCHEMY_DATABASE_URL = f'mysql+pymysql://...'
   ```

Worker 需要使用**同步模式**，因为 RQ (Redis Queue) 运行在同步上下文中。

## 修复内容

### 1. 修复 `run_migrations.py`

添加了 `get_database_url()` 辅助函数：

```python
from urllib.parse import quote_plus
from config.env import DataBaseConfig

def get_database_url():
    """Get database URL for synchronous SQLAlchemy"""
    url = (
        f'mysql+pymysql://{DataBaseConfig.db_username}:{quote_plus(DataBaseConfig.db_password)}@'
        f'{DataBaseConfig.db_host}:{DataBaseConfig.db_port}/{DataBaseConfig.db_database}'
    )
    if DataBaseConfig.db_type == 'postgresql':
        url = (
            f'postgresql+psycopg2://{DataBaseConfig.db_username}:{quote_plus(DataBaseConfig.db_password)}@'
            f'{DataBaseConfig.db_host}:{DataBaseConfig.db_port}/{DataBaseConfig.db_database}'
        )
    return url
```

**修改的文件**：
- `backend/tools/full_text_screening_worker_tool/migrations/run_migrations.py`

### 2. 修复 `base_worker.py`

同样添加了 `get_database_url()` 辅助函数：

```python
from urllib.parse import quote_plus
from config.env import DataBaseConfig

def get_database_url():
    """Get database URL for synchronous SQLAlchemy (Worker uses sync, not async)"""
    url = (
        f'mysql+pymysql://{DataBaseConfig.db_username}:{quote_plus(DataBaseConfig.db_password)}@'
        f'{DataBaseConfig.db_host}:{DataBaseConfig.db_port}/{DataBaseConfig.db_database}'
    )
    if DataBaseConfig.db_type == 'postgresql':
        url = (
            f'postgresql+psycopg2://{DataBaseConfig.db_username}:{quote_plus(DataBaseConfig.db_password)}@'
            f'{DataBaseConfig.db_host}:{DataBaseConfig.db_port}/{DataBaseConfig.db_database}'
        )
    return url
```

**修改的文件**：
- `backend/tools/full_text_screening_worker_tool/worker/base_worker.py`

## 依赖检查

运行迁移脚本需要以下依赖：

```bash
pip install sqlalchemy pymysql
```

运行 Worker 需要以下依赖：

```bash
pip install redis rq sqlalchemy pymysql
```

如果使用 PostgreSQL：

```bash
pip install psycopg2-binary  # 或 psycopg2
```

## 验证步骤

### 1. 安装依赖

```bash
cd backend
pip install sqlalchemy pymysql redis rq
```

### 2. 运行数据库迁移

```bash
cd backend/tools/full_text_screening_worker_tool/migrations
python run_migrations.py
```

预期输出：

```
Found 1 migration(s) to run:
  - 001_add_worker_fields.sql

✓ Connected to database: your_database_name

============================================================
Running migration: 001_add_worker_fields.sql
============================================================

Executing statement 1/3:
  ALTER TABLE fulltext_screening_history ADD COLUMN job_id VARCHAR(255)...
  ✓ Success

Executing statement 2/3:
  ALTER TABLE fulltext_screening_history ADD COLUMN log_file_path VARCHAR(500)...
  ✓ Success

Executing statement 3/3:
  CREATE INDEX idx_job_id ON fulltext_screening_history(job_id)
  ✓ Success

✓ Migration completed: 001_add_worker_fields.sql

============================================================
Verifying migration...
============================================================

✓ Columns created successfully:
  - job_id: varchar(255) NULL
  - log_file_path: varchar(500) NULL

✓ Index created successfully:
  - idx_job_id on column: job_id

============================================================
✓ All migrations completed successfully!
============================================================
```

### 3. 验证数据库

```sql
-- 检查字段是否添加
DESCRIBE fulltext_screening_history;

-- 应该看到新增的字段：
-- job_id          | varchar(255) | YES  | MUL | NULL    |       |
-- log_file_path   | varchar(500) | YES  |     | NULL    |       |

-- 检查索引
SHOW INDEX FROM fulltext_screening_history WHERE Key_name = 'idx_job_id';
```

## 注意事项

1. **数据库驱动**：
   - MySQL: 使用 `pymysql`（纯 Python 实现）
   - PostgreSQL: 使用 `psycopg2`

2. **密码特殊字符**：使用 `quote_plus()` 处理密码中的特殊字符

3. **同步 vs 异步**：
   - FastAPI Controller: 使用异步 SQLAlchemy (`mysql+asyncmy`)
   - RQ Worker: 使用同步 SQLAlchemy (`mysql+pymysql`)
   - 迁移脚本: 使用同步 SQLAlchemy (`mysql+pymysql`)

4. **向后兼容**：如果字段已存在，迁移脚本会显示警告并跳过，不会报错

## 修复完成

✅ 导入错误已修复
✅ 数据库 URL 构建逻辑已添加
✅ 支持 MySQL 和 PostgreSQL
✅ 密码特殊字符处理已添加

现在可以正常运行数据库迁移了！
