-- PostgreSQL enum types for Invite Service
-- Этот файл создает необходимые enum типы для корректной работы invite-service

-- Создание enum типа для статусов задач
DO $$ BEGIN
    CREATE TYPE taskstatus AS ENUM (
        'pending',
        'running', 
        'completed',
        'failed',
        'cancelled',
        'paused'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Создание enum типа для приоритетов задач
DO $$ BEGIN
    CREATE TYPE taskpriority AS ENUM (
        'low',
        'normal',
        'high',
        'urgent'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Создание enum типа для статусов целей приглашений
DO $$ BEGIN
    CREATE TYPE targetstatus AS ENUM (
        'pending',
        'invited',
        'failed',
        'skipped'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Создание enum типа для источников целей
DO $$ BEGIN
    CREATE TYPE targetsource AS ENUM (
        'manual',
        'csv_import',
        'parsing_import',
        'api_import'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Создание enum типа для статусов выполнения приглашений
DO $$ BEGIN
    CREATE TYPE inviteresultstatus AS ENUM (
        'success',
        'failed',
        'rate_limited',
        'flood_wait',
        'account_banned',
        'target_not_found',
        'privacy_restricted',
        'peer_flood',
        'user_not_mutual_contact'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Проверка созданных типов
SELECT typname FROM pg_type WHERE typname IN ('taskstatus', 'taskpriority', 'targetstatus', 'targetsource', 'inviteresultstatus');
