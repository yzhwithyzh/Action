# Database Migrations - Data Extraction Worker Tool

## Overview

This directory contains database migration scripts for the Data Extraction Worker tool. These migrations improve cost tracking and add necessary fields for the worker architecture.

## Migration Files

### 001_add_worker_fields.sql

**Purpose**: Add worker support fields to `data_extraction_history` table

**Changes**:
- Adds `job_id` (VARCHAR 255): Stores RQ job ID for async task tracking
- Adds `log_file_path` (VARCHAR 500): Stores worker log file path for SSE streaming
- Creates index on `job_id` for faster queries

**Required for**:
- Async worker task tracking
- SSE log file streaming mode

### 002_update_cost_and_model_fields.sql (2025-12-19)

**Purpose**: Improve cost tracking precision and add model information

**Changes**:
1. Modified `total_cost_estimate` from `FLOAT` to `DECIMAL(10,4)` for precise cost tracking
2. Added `model_name` field (VARCHAR(64)) to track the LLM model used

**Code Changes**:
- Updated `DataExtractionHistoryDO` to use `DECIMAL` type
- Added `Token_usageService.get_total_cost_by_session()` method
- Modified completion logic to calculate and save:
  - Total cost (sum of `cost_in_balance` from `token_usage` table)
  - Model name (from first token usage record)
  - Processing duration (created_at to completed_at in seconds)

## How to Run Migrations

### Method 1: MySQL Command Line

```bash
mysql -u your_username -p your_database < 001_add_worker_fields.sql
```

### Method 2: MySQL Workbench

1. Open MySQL Workbench
2. Connect to your database
3. Open the SQL file (`001_add_worker_fields.sql`)
4. Execute the script (Ctrl+Shift+Enter)

### Method 3: phpMyAdmin

1. Login to phpMyAdmin
2. Select your database
3. Go to SQL tab
4. Copy and paste the migration content
5. Click "Go"

### Method 4: Python Script (Recommended)

Create a migration script in your backend:

```python
# backend/scripts/run_migrations.py
import os
from sqlalchemy import create_engine, text
from config.env import get_database_url

def run_migration(migration_file):
    engine = create_engine(get_database_url())

    with open(migration_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # Split by semicolons and execute each statement
    statements = [s.strip() for s in sql_content.split(';') if s.strip()]

    with engine.connect() as conn:
        for statement in statements:
            if statement and not statement.startswith('--'):
                conn.execute(text(statement))
        conn.commit()

    print(f"✓ Migration completed: {migration_file}")

if __name__ == '__main__':
    migrations_dir = os.path.join(
        os.path.dirname(__file__),
        '..',
        'tools',
        'full_text_screening_worker_tool',
        'migrations'
    )

    # Run migration 001
    run_migration(os.path.join(migrations_dir, '001_add_worker_fields.sql'))
```

Then run:

```bash
cd backend
python scripts/run_migrations.py
```

## Verification

After running the migration, verify the changes:

```sql
-- Check if columns exist
DESCRIBE fulltext_screening_history;

-- Check if index exists
SHOW INDEX FROM fulltext_screening_history WHERE Key_name = 'idx_job_id';

-- Test query
SELECT id, session_id, job_id, log_file_path, status
FROM fulltext_screening_history
LIMIT 5;
```

## Rollback (If Needed)

If you need to rollback this migration:

```sql
-- Remove index
DROP INDEX idx_job_id ON fulltext_screening_history;

-- Remove columns
ALTER TABLE fulltext_screening_history DROP COLUMN job_id;
ALTER TABLE fulltext_screening_history DROP COLUMN log_file_path;
```

## Migration History

| Migration | Date | Description |
|-----------|------|-------------|
| 001_add_worker_fields.sql | 2025-12-05 | Add job_id and log_file_path fields for worker support |
| 002_update_cost_and_model_fields.sql | 2025-12-19 | Change total_cost_estimate to DECIMAL(10,4) and ensure model_name exists |

## Notes

- **Backward Compatibility**: These migrations are backward compatible. Existing records will have NULL values for the new fields.
- **Non-Breaking**: The original `/start-process` endpoint continues to work without using these fields.
- **Optional Fields**: Both `job_id` and `log_file_path` are optional (DEFAULT NULL), only used by the new async endpoints.

## Troubleshooting

### Error: Column already exists

If you see `Duplicate column name 'job_id'`, the migration has already been run. You can skip it or verify the columns exist:

```sql
SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'fulltext_screening_history'
AND COLUMN_NAME IN ('job_id', 'log_file_path');
```

### Error: Table doesn't exist

Make sure you're connected to the correct database and that the `fulltext_screening_history` table exists.

### Error: Access denied

Make sure your database user has ALTER TABLE privileges:

```sql
GRANT ALTER ON your_database.* TO 'your_username'@'localhost';
FLUSH PRIVILEGES;
```
