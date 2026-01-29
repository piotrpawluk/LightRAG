# LightRAG with Full PostgreSQL Storage

Complete LightRAG setup using PostgreSQL for all storage needs.

## Architecture

- **Database**: PostgreSQL with PGVector extension
- **LLM**: Qwen 2 (1.5B) - Optimized for CPU
- **Embedding**: All-MiniLM (384 dimensions) - Fast & efficient
- **Storage**:
  - KV Storage: PGKVStorage
  - Vector Storage: PGVectorStorage
  - Graph Storage: PGGraphStorage
  - Doc Status: PGDocStatusStorage

## Quick Start

### 1. Start Services

```bash
docker-compose -f docker-compose-postgres.yml up -d
```

### 2. Check Health

```bash
# Check all services
docker-compose -f docker-compose-postgres.yml ps

# Check PostgreSQL
docker exec lightrag-postgres pg_isready -U lightrag

# Check LightRAG
curl http://localhost:9621/health | jq
```

### 3. Submit Test Document

```bash
curl -X POST http://localhost:9621/documents/text \
  -H "Content-Type: application/json" \
  -d '{
    "text": "LightRAG is a graph-enhanced retrieval-augmented generation framework.",
    "document_id": "test-doc-1"
  }' | jq
```

### 4. Query

```bash
curl -X POST http://localhost:9621/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is LightRAG?",
    "mode": "hybrid"
  }' | jq
```

## Configuration

### Database Connection

- **Host**: `lightrag-postgres` (internal) / `localhost:5432` (external)
- **Database**: `lightrag`
- **User**: `lightrag`
- **Password**: `lightrag_secure_password` (⚠️ **Change in production!**)

### Ports

- **LightRAG API**: `9621`
- **PostgreSQL**: `5432`
- **Ollama**: `11434`

## Storage Details

### PGVector

- Stores embeddings for entities, relations, and chunks
- Uses vector similarity search (cosine distance)
- Dimension: 384 (all-minilm)

### PGGraphStorage

- Stores graph relationships in native PostgreSQL
- Tables for nodes and edges
- Workspace isolation via table prefixes

## Upgrading to AGE Extension (Optional)

If you want to use Apache AGE instead of PGGraphStorage:

1. **Use custom PostgreSQL image** with AGE:
   ```yaml
   postgres:
     image: sohamthakurdesai/postgres-age-pgvector:latest
   ```

2. **Update storage configuration**:
   ```yaml
   - LIGHTRAG_GRAPH_STORAGE=AGEStorage
   ```

3. **Update init script** to enable AGE:
   ```sql
   CREATE EXTENSION IF NOT EXISTS age;
   LOAD 'age';
   SET search_path = ag_catalog, "$user", public;
   ```

## Maintenance

### Backup Database

```bash
docker exec lightrag-postgres pg_dump -U lightrag lightrag > backup.sql
```

### Restore Database

```bash
cat backup.sql | docker exec -i lightrag-postgres psql -U lightrag lightrag
```

### Clear All Data

```bash
docker-compose -f docker-compose-postgres.yml down -v
docker-compose -f docker-compose-postgres.yml up -d
```

### View Logs

```bash
# All services
docker-compose -f docker-compose-postgres.yml logs -f

# Specific service
docker logs lightrag-server -f
docker logs lightrag-postgres -f
```

## Performance Tuning

### PostgreSQL Settings

For better performance, create `postgresql.conf` and mount it:

```ini
# Memory
shared_buffers = 256MB
effective_cache_size = 1GB

# Query Planning
random_page_cost = 1.1
effective_io_concurrency = 200

# Vector Search
max_parallel_workers_per_gather = 2
```

### LightRAG Settings

Adjust in docker-compose.yml:

```yaml
- WORKERS=4  # Increase for more concurrent requests
- LLM_FUNC_TIMEOUT=600  # Adjust for slower/faster LLM
```

## Troubleshooting

### Connection Refused

```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Check PostgreSQL logs
docker logs lightrag-postgres
```

### Slow Queries

```bash
# Check PostgreSQL slow queries
docker exec lightrag-postgres psql -U lightrag -c "SELECT * FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 10;"
```

### Out of Memory

Increase PostgreSQL memory limits in docker-compose.yml:

```yaml
postgres:
  deploy:
    resources:
      limits:
        memory: 2G
```

## Security Notes

⚠️ **Production Checklist**:

1. Change default password: `lightrag_secure_password`
2. Use environment variables or secrets for credentials
3. Enable SSL for PostgreSQL connections
4. Restrict network access (firewall rules)
5. Regular backups
6. Monitor disk space

## Support

For issues specific to:
- **LightRAG**: https://github.com/HKUDS/LightRAG/issues
- **PGVector**: https://github.com/pgvector/pgvector/issues
- **Apache AGE**: https://age.apache.org/

## License

Same as LightRAG project license.
