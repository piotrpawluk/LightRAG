-- Initialize PostgreSQL extensions for LightRAG
-- Enable PGVector and Apache AGE extensions

-- Enable PGVector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable Apache AGE extension for graph database
CREATE EXTENSION IF NOT EXISTS age;

-- Load AGE into the search path
LOAD 'age';

-- Set search path to include ag_catalog for AGE functions
SET search_path = ag_catalog, "$user", public;

-- Create schema for LightRAG (if not using default)
CREATE SCHEMA IF NOT EXISTS lightrag;

-- Grant permissions to lightrag user
GRANT ALL PRIVILEGES ON SCHEMA lightrag TO lightrag;
GRANT ALL PRIVILEGES ON SCHEMA ag_catalog TO lightrag;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA lightrag TO lightrag;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA lightrag TO lightrag;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA ag_catalog TO lightrag;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA ag_catalog TO lightrag;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA lightrag GRANT ALL ON TABLES TO lightrag;
ALTER DEFAULT PRIVILEGES IN SCHEMA lightrag GRANT ALL ON SEQUENCES TO lightrag;
ALTER DEFAULT PRIVILEGES IN SCHEMA ag_catalog GRANT ALL ON TABLES TO lightrag;
ALTER DEFAULT PRIVILEGES IN SCHEMA ag_catalog GRANT ALL ON SEQUENCES TO lightrag;

-- Verify extensions
SELECT 'PostgreSQL extensions initialized:' AS status;
SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector', 'age');
