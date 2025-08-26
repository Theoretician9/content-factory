-- Migration: Remove duplicate lowercase ActionType enum values
-- Keep only UPPERCASE values to match the original enum definition

-- First, update any existing records that use lowercase values to use uppercase
UPDATE invite_execution_logs 
SET action_type = UPPER(action_type::text)::actiontype 
WHERE action_type::text IN ('invite_sent', 'invite_successful', 'invite_failed', 'account_switched', 'rate_limit_hit', 'error_occurred');

-- Remove the duplicate lowercase enum values
-- Note: This is complex in PostgreSQL, so we'll create a new enum and replace it

-- Step 1: Create a new enum with only the correct values
CREATE TYPE actiontype_new AS ENUM (
    'TASK_STARTED',
    'TASK_COMPLETED', 
    'TASK_FAILED',
    'TASK_PAUSED',
    'TASK_RESUMED',
    'INVITE_SENT',
    'INVITE_SUCCESSFUL',
    'INVITE_FAILED',
    'ACCOUNT_SWITCHED',
    'RATE_LIMIT_HIT',
    'ERROR_OCCURRED'
);

-- Step 2: Update the column to use the new enum
ALTER TABLE invite_execution_logs 
ALTER COLUMN action_type TYPE actiontype_new 
USING action_type::text::actiontype_new;

-- Step 3: Drop the old enum and rename the new one
DROP TYPE actiontype;
ALTER TYPE actiontype_new RENAME TO actiontype;

-- Verify the final enum values
SELECT enumlabel as "Final ActionType Values" 
FROM pg_enum 
WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'actiontype') 
ORDER BY enumlabel;