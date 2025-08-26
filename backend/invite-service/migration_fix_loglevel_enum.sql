-- Migration: Fix LogLevel and ActionType enum values
-- This fixes both LogLevel enum values and ensures ActionType enum exists

-- Step 1: Create loglevel enum if it doesn't exist
DO $$ 
BEGIN
    -- Check if loglevel type exists
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'loglevel') THEN
        CREATE TYPE loglevel AS ENUM ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL');
    ELSE
        -- If it exists, check if it has the right values and recreate if necessary
        -- First, update any existing records that use lowercase values to use uppercase
        UPDATE invite_execution_logs 
        SET level = UPPER(level::text)::loglevel 
        WHERE level::text IN ('debug', 'info', 'warning', 'error', 'critical');
        
        -- Recreate the enum with correct values
        CREATE TYPE loglevel_new AS ENUM ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL');
        
        -- Update the column to use the new enum
        ALTER TABLE invite_execution_logs 
        ALTER COLUMN level TYPE loglevel_new 
        USING UPPER(level::text)::loglevel_new;
        
        -- Drop the old enum and rename the new one
        DROP TYPE loglevel;
        ALTER TYPE loglevel_new RENAME TO loglevel;
    END IF;
END $$;

-- Step 2: Ensure ActionType enum exists (in case it was missing)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'actiontype') THEN
        CREATE TYPE actiontype AS ENUM (
            'TASK_STARTED', 'TASK_COMPLETED', 'TASK_FAILED', 'TASK_PAUSED', 'TASK_RESUMED',
            'INVITE_SENT', 'INVITE_SUCCESSFUL', 'INVITE_FAILED', 'ACCOUNT_SWITCHED', 
            'RATE_LIMIT_HIT', 'ERROR_OCCURRED'
        );
    END IF;
END $$;

-- Verify the final enum values
SELECT 'LogLevel Values:' as enum_type;
SELECT enumlabel as values 
FROM pg_enum 
WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'loglevel') 
ORDER BY enumlabel;

SELECT 'ActionType Values:' as enum_type;
SELECT enumlabel as values 
FROM pg_enum 
WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'actiontype') 
ORDER BY enumlabel;