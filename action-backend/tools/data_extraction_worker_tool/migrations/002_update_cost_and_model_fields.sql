-- Migration: Update total_cost_estimate to DECIMAL(10,4) and ensure model_name exists
-- Date: 2025-12-19
-- Description:
--   1. Change total_cost_estimate from FLOAT to DECIMAL(10,4) for precise cost tracking
--   2. Ensure model_name field exists (VARCHAR(64))

-- Step 1: Modify total_cost_estimate to DECIMAL(10,4)
ALTER TABLE `data_extraction_history`
MODIFY COLUMN `total_cost_estimate` DECIMAL(10,4) DEFAULT NULL
COMMENT '总成本估算（余额消耗）';

-- Step 2: Check if model_name exists, if not add it
-- Note: This is idempotent - if column exists, MySQL will show warning but won't fail
ALTER TABLE `data_extraction_history`
ADD COLUMN IF NOT EXISTS `model_name` VARCHAR(64) DEFAULT NULL
COMMENT '主要使用的LLM模型名称'
AFTER `llm_config`;

-- Verification queries (optional - can be commented out in production)
-- SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_COMMENT
-- FROM INFORMATION_SCHEMA.COLUMNS
-- WHERE TABLE_NAME = 'data_extraction_history'
-- AND COLUMN_NAME IN ('total_cost_estimate', 'model_name', 'processing_duration');
