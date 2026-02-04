-- PostgreSQL initialization script for Django Ninja Boilerplate
-- This script runs when the PostgreSQL container starts for the first time

-- Create extensions for enhanced functionality
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- Trigram matching for fuzzy search
CREATE EXTENSION IF NOT EXISTS "unaccent";       -- Accent-insensitive search
CREATE EXTENSION IF NOT EXISTS "btree_gin";      -- GIN index support

-- Set timezone to UTC
SET timezone = 'UTC';

-- Create additional databases for testing (optional)
-- CREATE DATABASE boilerplate_db_test;

-- Grant permissions (database is created via POSTGRES_DB env var)
-- This runs after the database is created by the entrypoint script
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_database WHERE datname = 'boilerplate_db') THEN
        EXECUTE 'GRANT ALL PRIVILEGES ON DATABASE boilerplate_db TO postgres';
    END IF;
END $$;

-- Performance tuning for development
-- These settings optimize for development, adjust for production
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '768MB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = '0.9';
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = '100';
ALTER SYSTEM SET random_page_cost = '1.1';
ALTER SYSTEM SET effective_io_concurrency = '200';
ALTER SYSTEM SET work_mem = '4MB';
ALTER SYSTEM SET min_wal_size = '1GB';
ALTER SYSTEM SET max_wal_size = '4GB';

-- Logging configuration for debugging
ALTER SYSTEM SET log_statement = 'none';  -- Set to 'all' for debugging
ALTER SYSTEM SET log_duration = 'off';
ALTER SYSTEM SET log_min_duration_statement = '1000';  -- Log queries > 1s

-- Reload configuration
SELECT pg_reload_conf();

-- Create helper function for trigram similarity search
CREATE OR REPLACE FUNCTION similarity_threshold(threshold float DEFAULT 0.3)
RETURNS void AS $$
BEGIN
    EXECUTE format('SET pg_trgm.similarity_threshold = %L', threshold);
END;
$$ LANGUAGE plpgsql;

-- Create function for generating random strings (useful for seeds)
CREATE OR REPLACE FUNCTION random_string(length integer DEFAULT 10)
RETURNS text AS $$
DECLARE
    chars text[] := '{0,1,2,3,4,5,6,7,8,9,A,B,C,D,E,F,G,H,I,J,K,L,M,N,O,P,Q,R,S,T,U,V,W,X,Y,Z,a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p,q,r,s,t,u,v,w,x,y,z}';
    result text := '';
    i integer := 0;
BEGIN
    FOR i IN 1..length LOOP
        result := result || chars[1+floor(random()*62)::int];
    END LOOP;
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Log initialization complete
DO $$
BEGIN
    RAISE NOTICE 'Database initialization complete!';
END $$;

