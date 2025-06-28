-- Invite Service Database Initialization
-- Создание базы данных и пользователя для Invite Service

-- Создание пользователя
CREATE USER invite_user WITH PASSWORD 'invite_password';

-- Создание базы данных
CREATE DATABASE invite_db OWNER invite_user;

-- Подключение к базе данных invite_db
\c invite_db;

-- Выдача всех прав пользователю invite_user на базу данных invite_db
GRANT ALL PRIVILEGES ON DATABASE invite_db TO invite_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO invite_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO invite_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO invite_user;

-- Установка прав по умолчанию для новых объектов
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO invite_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO invite_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO invite_user; 