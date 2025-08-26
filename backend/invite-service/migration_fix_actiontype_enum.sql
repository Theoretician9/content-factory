-- Migration: Fix ActionType enum to include missing values
-- This fixes the enum to match the ActionType class in invite_execution_log.py

-- Check current enum values
-- SELECT unnest(enum_range(NULL::actiontype));

-- Add missing enum values if they don't exist
DO $$ 
BEGIN
    -- Add invite_sent if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'invite_sent' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'actiontype')) THEN
        ALTER TYPE actiontype ADD VALUE 'invite_sent';
    END IF;
    
    -- Add invite_successful if it doesn't exist  
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'invite_successful' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'actiontype')) THEN
        ALTER TYPE actiontype ADD VALUE 'invite_successful';
    END IF;
    
    -- Add invite_failed if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'invite_failed' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'actiontype')) THEN
        ALTER TYPE actiontype ADD VALUE 'invite_failed';
    END IF;
    
    -- Add account_switched if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'account_switched' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'actiontype')) THEN
        ALTER TYPE actiontype ADD VALUE 'account_switched';
    END IF;
    
    -- Add rate_limit_hit if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'rate_limit_hit' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'actiontype')) THEN
        ALTER TYPE actiontype ADD VALUE 'rate_limit_hit';
    END IF;
    
    -- Add error_occurred if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'error_occurred' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'actiontype')) THEN
        ALTER TYPE actiontype ADD VALUE 'error_occurred';
    END IF;
END $$;

-- Verify the enum values
SELECT enumlabel as "ActionType Values" 
FROM pg_enum 
WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'actiontype') 
ORDER BY enumlabel;