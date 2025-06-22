-- Multi-Platform Parser Service Database Initialization
-- PostgreSQL initialization script

-- Create database if not exists (handled by Docker)
-- CREATE DATABASE parsing_db;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search
CREATE EXTENSION IF NOT EXISTS "btree_gin"; -- For JSON indexing

-- Set timezone
SET timezone = 'UTC';

-- Create custom functions for search
CREATE OR REPLACE FUNCTION update_search_vector() RETURNS trigger AS $$
BEGIN
    NEW.search_vector := to_tsvector('english', 
        COALESCE(NEW.content_text, '') || ' ' ||
        COALESCE(NEW.author_username, '') || ' ' ||
        COALESCE(NEW.author_name, '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions to parsing_user
GRANT ALL PRIVILEGES ON DATABASE parsing_db TO parsing_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO parsing_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO parsing_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO parsing_user;

-- Default settings
ALTER DATABASE parsing_db SET log_statement = 'all';
ALTER DATABASE parsing_db SET log_min_duration_statement = 1000;  -- Log slow queries

-- Create initial admin user for testing (optional)
-- This would be handled by the application in production 