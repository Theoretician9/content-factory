-- Migration: Fix account_id field types from integer to varchar
-- This fixes the issue where UUID account IDs were being stored in integer fields

-- Fix invite_targets.sent_from_account_id field
ALTER TABLE invite_targets 
ALTER COLUMN sent_from_account_id TYPE VARCHAR(255);

-- Fix invite_execution_logs.account_id field  
ALTER TABLE invite_execution_logs
ALTER COLUMN account_id TYPE VARCHAR(255);

-- Add comment explaining the change
COMMENT ON COLUMN invite_targets.sent_from_account_id IS 'ID аккаунта (UUID string), с которого отправлено приглашение';
COMMENT ON COLUMN invite_execution_logs.account_id IS 'ID аккаунта (UUID string), выполнявшего действие';