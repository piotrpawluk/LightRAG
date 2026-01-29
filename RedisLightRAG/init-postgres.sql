-- Initialize PostgreSQL database for LightRAG
-- Enable PGVector and AGE extensions

-- Enable PGVector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Note: AGE extension installation
-- The ankane/pgvector image doesn't include AGE by default
-- AGE needs to be built from source or use a custom image

-- For now, we'll use PGGraphStorage (native PostgreSQL)
-- which doesn't require AGE extension

-- Create schema for LightRAG
CREATE SCHEMA IF NOT EXISTS lightrag;

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA lightrag TO lightrag;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA lightrag TO lightrag;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA lightrag TO lightrag;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA lightrag GRANT ALL ON TABLES TO lightrag;
ALTER DEFAULT PRIVILEGES IN SCHEMA lightrag GRANT ALL ON SEQUENCES TO lightrag;

SELECT 'LightRAG PostgreSQL initialization complete!' AS status;
