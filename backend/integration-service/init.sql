-- Инициализация базы данных Integration Service
-- Создание необходимых расширений

-- Расширения
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Таблица для хранения сессий Telegram
CREATE TABLE telegram_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id INT NOT NULL,
    phone VARCHAR(20) NOT NULL,
    session_data JSONB NOT NULL,
    session_metadata JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для telegram_sessions
CREATE INDEX idx_telegram_sessions_user_id ON telegram_sessions(user_id);
CREATE INDEX idx_telegram_sessions_phone ON telegram_sessions(phone);
CREATE INDEX idx_telegram_sessions_metadata ON telegram_sessions USING GIN (session_metadata);
CREATE INDEX idx_telegram_sessions_active ON telegram_sessions(is_active) WHERE is_active = TRUE;

-- Таблица для хранения ботов
CREATE TABLE telegram_bots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id INT NOT NULL,
    bot_token VARCHAR(100) NOT NULL,
    username VARCHAR(50) NOT NULL,
    settings JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для telegram_bots
CREATE INDEX idx_telegram_bots_user_id ON telegram_bots(user_id);
CREATE INDEX idx_telegram_bots_username ON telegram_bots(username);
CREATE INDEX idx_telegram_bots_settings ON telegram_bots USING GIN (settings);
CREATE INDEX idx_telegram_bots_active ON telegram_bots(is_active) WHERE is_active = TRUE;

-- Таблица для хранения каналов/групп
CREATE TABLE telegram_channels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id INT NOT NULL,
    channel_id BIGINT NOT NULL,
    title VARCHAR(255) NOT NULL,
    type VARCHAR(20) NOT NULL CHECK (type IN ('channel', 'group', 'supergroup')),
    settings JSONB DEFAULT '{}',
    members_count INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для telegram_channels
CREATE INDEX idx_telegram_channels_user_id ON telegram_channels(user_id);
CREATE INDEX idx_telegram_channels_channel_id ON telegram_channels(channel_id);
CREATE INDEX idx_telegram_channels_settings ON telegram_channels USING GIN (settings);
CREATE INDEX idx_telegram_channels_title_trgm ON telegram_channels USING GIN (title gin_trgm_ops);
CREATE INDEX idx_telegram_channels_type ON telegram_channels(type);
CREATE INDEX idx_telegram_channels_active ON telegram_channels(is_active) WHERE is_active = TRUE;

-- Таблица для логов интеграций
CREATE TABLE integration_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id INT NOT NULL,
    integration_type VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'error', 'pending')),
    details JSONB DEFAULT '{}',
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для integration_logs
CREATE INDEX idx_integration_logs_user_id ON integration_logs(user_id);
CREATE INDEX idx_integration_logs_created_at ON integration_logs(created_at);
CREATE INDEX idx_integration_logs_details ON integration_logs USING GIN (details);
CREATE INDEX idx_integration_logs_type_action ON integration_logs(integration_type, action);
CREATE INDEX idx_integration_logs_status ON integration_logs(status);

-- Функция для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Триггеры для автоматического обновления updated_at
CREATE TRIGGER update_telegram_sessions_updated_at
    BEFORE UPDATE ON telegram_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_telegram_bots_updated_at
    BEFORE UPDATE ON telegram_bots
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_telegram_channels_updated_at
    BEFORE UPDATE ON telegram_channels
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Создание пользователя для приложения (если не существует)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'integration_user') THEN
        CREATE USER integration_user WITH PASSWORD 'integration_password';
    END IF;
END
$$;

-- Выдача прав пользователю
GRANT ALL PRIVILEGES ON DATABASE integration_db TO integration_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO integration_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO integration_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO integration_user;

-- Разрешаем создание новых таблиц
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO integration_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO integration_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO integration_user; 