-- Invite Service Database Initialization
-- База данных invite_db и пользователь invite_user уже созданы через переменные окружения
-- Этот файл выполняется уже в контексте созданной базы данных

-- Устанавливаем права доступа для пользователя
GRANT ALL PRIVILEGES ON DATABASE invite_db TO invite_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO invite_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO invite_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO invite_user;

-- Установка прав по умолчанию для новых объектов
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO invite_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO invite_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO invite_user;

-- Создание расширений, если нужны
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp"; 