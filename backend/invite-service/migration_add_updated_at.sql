-- Migration: Add updated_at field to invite_execution_logs if missing or make it nullable
-- This fixes the NOT NULL constraint violation for updated_at

-- Step 1: Check if updated_at column exists and add it if missing
DO $$ 
BEGIN
    -- Check if updated_at column exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'invite_execution_logs' 
        AND column_name = 'updated_at'
    ) THEN
        -- Add updated_at column with default value
        ALTER TABLE invite_execution_logs 
        ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL;
    ELSE
        -- If column exists but is NOT NULL, make it nullable temporarily 
        -- and then set default values for existing records
        ALTER TABLE invite_execution_logs 
        ALTER COLUMN updated_at DROP NOT NULL;
        
        -- Update existing records that have NULL updated_at
        UPDATE invite_execution_logs 
        SET updated_at = NOW() 
        WHERE updated_at IS NULL;
        
        -- Make it NOT NULL again with default
        ALTER TABLE invite_execution_logs 
        ALTER COLUMN updated_at SET DEFAULT NOW();
        
        ALTER TABLE invite_execution_logs 
        ALTER COLUMN updated_at SET NOT NULL;
    END IF;
END $$;

-- Step 2: Verify the column exists
SELECT column_name, is_nullable, column_default 
FROM information_schema.columns 
WHERE table_name = 'invite_execution_logs' 
AND column_name IN ('created_at', 'updated_at')
ORDER BY column_name;