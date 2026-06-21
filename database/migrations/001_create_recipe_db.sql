-- Migration: Create recipe_db database and recipe_user
-- Purpose: Initialize PostgreSQL database for Recipe automation system
-- Database: Markiz (100.81.127.54:5432)

-- =============================================
-- Create database
-- =============================================
CREATE DATABASE recipe_db
    ENCODING 'UTF8'
    LC_COLLATE = 'uk_UA.UTF-8'
    LC_CTYPE = 'uk_UA.UTF-8'
    TEMPLATE = template0;

-- =============================================
-- Create user with password
-- =============================================
CREATE USER recipe_user WITH ENCRYPTED PASSWORD 'your_password_here';

-- =============================================
-- Grant privileges to user
-- =============================================
-- Connect to recipe_db and run:
GRANT CONNECT ON DATABASE recipe_db TO recipe_user;
GRANT USAGE ON SCHEMA public TO recipe_user;
GRANT CREATE ON SCHEMA public TO recipe_user;

-- Grant privileges on future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO recipe_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO recipe_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO recipe_user;

-- =============================================
-- Run this as superuser (postgres):
-- =============================================
-- 1. Connect to default database:
--    psql -h 100.81.127.54 -U postgres -d postgres
--
-- 2. Execute the CREATE DATABASE and CREATE USER statements above
--
-- 3. Connect to recipe_db:
--    psql -h 100.81.127.54 -U postgres -d recipe_db
--
-- 4. Execute the GRANT statements
--
-- 5. Then run schema.sql with recipe_user:
--    psql -h 100.81.127.54 -U recipe_user -d recipe_db -f database/schema.sql
