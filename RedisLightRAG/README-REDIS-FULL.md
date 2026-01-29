# LightRAG with Full Redis Storage + External Qwen3 APIs

Complete setup guide for running LightRAG with full Redis Stack storage backend and external Qwen3 model APIs.

## Overview

This configuration uses **Redis Stack** for all primary storage layers (KV, Vector, DocStatus) with NetworkX for graph storage. It connects to external Qwen3-Next-80B-A3B-Thinking (LLM) and Qwen3-Embedding-8B (embeddings) APIs for inference, eliminating the need for local model deployment.

```
┌──────────────────────────────────────────────────────┐
│         LightRAG Full Redis + External APIs          │
├──────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌───────────────────────────┐     │
│  │ Redis Stack  │  │      LightRAG Server      │     │
│  │ DB 0: KV     │  │  ghcr.io/piotrpawluk/     │     │
│  │ DB 1: Status │  │  lightrag:latest          │     │
│  │ DB 2: Vectors│  └───────────────────────────┘     │
│  └──────────────┘                                     │
│  ┌────────────────────────────────────────────┐      │
│  │  NetworkX Graph Storage (File-based)       │      │
│  └────────────────────────────────────────────┘      │
│                                                       │
│  External APIs (HTTPS):                              │
│  ┌─────────────────────────────────────────────┐     │
│  │  LLM: Qwen3-Next-80B-A3B-Thinking          │     │
│  │  ml-llm-v-srv-v45-cp1-tst-node1.ai.warta.pl│     │
│  └─────────────────────────────────────────────┘     │
│  ┌─────────────────────────────────────────────┐     │
│  │  Embedding: Qwen3-Embedding-8B (4096 dim)  │     │
│  │  ml-ssm-l-srv-v16-cp2-tst-node5-llm-apps...│     │
│  └─────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────┘

Local Ports: 9621 (LightRAG API) | 6379 (Redis)
```

## Storage Architecture

### Storage Layer Breakdown

| Layer | Backend | Database | Purpose | Size (4096 dim) |
|-------|---------|----------|---------|-----------------|
| **KV Storage** | Redis | DB 0 | Documents, text chunks, LLM cache | ~100MB/10K docs |
| **DocStatus** | Redis | DB 1 | Document processing status/metadata | ~10MB/10K docs |
| **Vector Storage** | Redis + RediSearch | DB 2 | 4096-dim embeddings with HNSW | ~1.6GB/10K docs |
| **Graph Storage** | NetworkX | File-based | Entity-relationship knowledge graph | ~50MB/10K docs |

**Total Storage:** ~1.76GB per 10K documents (10x larger than 384-dim embeddings)

### Why This Architecture?

**Redis for KV/Vector/Status:**
- ✅ Fast in-memory operations
- ✅ Horizontal scalability via Redis Cluster
- ✅ Native vector search with HNSW indexing
- ✅ Persistent storage (RDB + AOF)
- ✅ Simple deployment (single service)

**NetworkX for Graph:**
- ✅ Mature and well-tested
- ✅ No additional service required
- ✅ Adequate performance for < 1M nodes
- ✅ Redis Graph module deprecated in v7.2+

**External Qwen3 APIs:**
- ✅ No local model deployment (saves ~10GB disk)
- ✅ 80B parameter LLM (better quality than 7B)
- ✅ Thinking mode for complex reasoning
- ✅ 4096-dim embeddings (higher quality than 384)
- ✅ Faster startup (~1 min vs 10-30 min)
- ✅ Easy model updates (change endpoint)

## Quick Start

```bash
# Navigate to RedisLightRAG directory
cd RedisLightRAG

# Start full Redis setup with external APIs
./lightrag.sh start-redis-full

# This will:
# 1. Start Redis Stack with RediSearch module
# 2. Start LightRAG server with external API configuration
# 3. Wait for health checks to pass (~30 seconds)
```

**Note**: No model downloads required - startup is fast!

## External API Endpoints

This configuration uses external OpenAI-compatible APIs for inference:

### LLM Endpoint
- **Model**: Qwen3-Next-80B-A3B-Thinking
- **Host**: https://ml-llm-v-srv-v45-cp1-tst-node1.ai.warta.pl/v1
- **API Key**: `iAsmiqkLkU4e9fFf`
- **Capabilities**: 80B parameter model with thinking mode
- **Context**: 4096 tokens
- **Binding**: OpenAI-compatible

### Embedding Endpoint
- **Model**: Qwen3-Embedding-8B
- **Host**: https://ml-ssm-l-srv-v16-cp2-tst-node5-llm-apps-tst.apps.ml.warta.pl/v1
- **API Key**: `pU68nMPXhWgXjnIQ`
- **Dimensions**: 4096
- **Max tokens**: 8192
- **Binding**: OpenAI-compatible

### Network Requirements
- ✅ Outbound HTTPS access required
- ✅ DNS resolution for `.ai.warta.pl` domains
- ✅ No proxy configuration needed (direct connection)
- ✅ API endpoints must be reachable from Docker container network

## Configuration Reference

### Environment Variables

All storage and API configuration is done via environment variables in `docker-compose-redis-full.yml`:

```yaml
# Server Configuration
HOST=0.0.0.0
PORT=9621
WORKERS=4
LOG_LEVEL=INFO
WORKSPACE=redis_qwen3_workspace

# LLM Configuration (External Qwen3-Next-80B)
LLM_BINDING=openai
LLM_BINDING_HOST=https://ml-llm-v-srv-v45-cp1-tst-node1.ai.warta.pl/v1
LLM_BINDING_API_KEY=iAsmiqkLkU4e9fFf
LLM_MODEL=Qwen/Qwen3-Next-80B-A3B-Thinking
LLM_MAX_TOKENS=4096
LLM_TEMPERATURE=0.0
LLM_TOP_P=0.9
LLM_TIMEOUT=900

# Embedding Configuration (External Qwen3-Embedding-8B)
EMBEDDING_BINDING=openai
EMBEDDING_BINDING_HOST=https://ml-ssm-l-srv-v16-cp2-tst-node5-llm-apps-tst.apps.ml.warta.pl/v1
EMBEDDING_BINDING_API_KEY=pU68nMPXhWgXjnIQ
EMBEDDING_MODEL=Qwen3-Embedding-8B
EMBEDDING_DIM=4096
EMBEDDING_MAX_TOKEN_SIZE=8192

# Storage Configuration
REDIS_URI=redis://lightrag-redis:6379
LIGHTRAG_KV_STORAGE=RedisKVStorage
REDIS_KV_DB=0
LIGHTRAG_DOC_STATUS_STORAGE=RedisDocStatusStorage
REDIS_DOC_STATUS_DB=1
LIGHTRAG_VECTOR_STORAGE=RedisVectorStorage
REDIS_VECTOR_DB=2
LIGHTRAG_GRAPH_STORAGE=NetworkXStorage

# Redis HNSW Index Configuration (optimized for 4096 dims)
REDIS_HNSW_M=16
REDIS_HNSW_EF_CONSTRUCTION=512  # Increased for better quality

# Redis Connection Settings
REDIS_MAX_CONNECTIONS=100
REDIS_SOCKET_TIMEOUT=30
REDIS_CONNECT_TIMEOUT=10
REDIS_RETRY_ATTEMPTS=3
```

### Redis HNSW Index Parameters

#### M (Connections per Node)
- **Default**: 16
- **Range**: 4-64
- **Impact**:
  - Higher = Better recall, more memory, slower indexing
  - Lower = Less memory, faster indexing, lower recall

**Recommendations for 4096-dim vectors:**
- Development: `M=8` (lower memory)
- Production: `M=16` (balanced) **← Current**
- High precision: `M=32` (best quality)

#### EF_CONSTRUCTION (Search Depth During Indexing)
- **Current**: 512 (increased from 256)
- **Range**: 100-512
- **Impact**:
  - Higher = Better index quality, slower indexing
  - Lower = Faster indexing, lower quality

**Recommendations for 4096-dim vectors:**
- Fast indexing: `EF_CONSTRUCTION=256`
- Balanced: `EF_CONSTRUCTION=512` **← Current**
- High quality: `EF_CONSTRUCTION=1024` (very slow)

#### Distance Metric
- **Fixed**: COSINE (optimal for text embeddings)
- **Range**: 0 (identical) to 2 (opposite)
- **Similarity**: 1 - distance

## Comparison: Storage Backend Options

| Feature | PostgreSQL | Full Redis (External API) | Hybrid Redis (Local Models) |
|---------|-----------|---------------------------|------------------------------|
| **KV Storage** | PG | Redis | Redis |
| **Vector** | PGVector (IVFFLAT) | Redis HNSW (4096 dim) | NanoVectorDB (384 dim) |
| **Graph** | Apache AGE | NetworkX | NetworkX |
| **DocStatus** | PG | Redis | Redis |
| **LLM** | Local Ollama | External API (80B) | Local Ollama (7B) |
| **Embedding** | Local Ollama | External API (4096 dim) | Local Ollama (384 dim) |
| **Persistence** | ACID, WAL | RDB+AOF | Mixed |
| **Disk Space** | Medium (~5GB) | Low (~500MB) | High (~15GB models) |
| **RAM Usage** | Medium (2-4GB) | High (8-16GB) | Very High (16-32GB) |
| **Startup Time** | Medium (2-5 min) | Fast (~1 min) | Slow (10-30 min) |
| **Query Speed** | Slow (5-15s) | Medium (3-10s)* | Fast (2-8s) |
| **Scalability** | Vertical | Horizontal | Limited |
| **Best For** | ACID requirements | Production API | Local development |

*Network latency adds 1-3s per API call

### When to Use This Configuration

**Use Full Redis + External APIs When:**
- ✅ You have access to powerful external LLM/embedding APIs
- ✅ You want high-quality embeddings (4096 dimensions)
- ✅ You need horizontal scalability
- ✅ You want fast startup and low disk usage
- ✅ Network latency is acceptable (< 500ms to APIs)
- ✅ You have sufficient RAM (16GB+ recommended)

**Don't Use When:**
- ❌ You need offline operation (no internet)
- ❌ API costs are prohibitive
- ❌ Network latency is unacceptable
- ❌ You need ACID guarantees
- ❌ RAM is limited (< 8GB)

## Memory Requirements

### Without Local Models (External APIs)

**Formula:**
```
Total RAM = Base + Redis Data

Base (Redis + LightRAG containers): ~1GB
Data (per 10K documents with 4096-dim vectors):
  - Chunks (KV):      ~100MB
  - Vectors (4096):   ~1.6GB  ← 10x larger than 384-dim
  - Graph (NetworkX): ~50MB
  - Status:           ~10MB
  Total per 10K:      ~1.76GB
```

**Scaling Examples:**
| Documents | Redis Data | Total RAM | Redis Allocation |
|-----------|------------|-----------|------------------|
| 10K | 1.8GB | 3GB | 2GB |
| 50K | 8.8GB | 10GB | 8GB ← **Current config** |
| 100K | 17.6GB | 19GB | 16GB |
| 250K | 44GB | 46GB | 40GB |

**Recommendations:**
- **Small datasets** (< 25K docs): 8GB RAM, 4GB Redis
- **Medium datasets** (25-75K docs): 16GB RAM, 8GB Redis **← Current**
- **Large datasets** (75-150K docs): 32GB RAM, 16GB Redis
- **Very large** (> 150K docs): Use Redis Cluster

## Performance Tuning

### 1. Increase Worker Count

For multi-core systems:

```yaml
environment:
  - WORKERS=8  # Default: 4
```

**Recommendation**: `WORKERS = CPU cores - 1`

### 2. Optimize HNSW Index for 4096 Dimensions

**For Speed (Development):**
```yaml
- REDIS_HNSW_M=8
- REDIS_HNSW_EF_CONSTRUCTION=256
```

**For Quality (Production) - Current:**
```yaml
- REDIS_HNSW_M=16
- REDIS_HNSW_EF_CONSTRUCTION=512
```

**For Maximum Precision:**
```yaml
- REDIS_HNSW_M=32
- REDIS_HNSW_EF_CONSTRUCTION=1024
```

### 3. Adjust Redis Memory

Edit docker-compose-redis-full.yml:

```yaml
redis-stack:
  environment:
    - REDIS_ARGS=--appendonly yes --maxmemory 16gb --maxmemory-policy noeviction
```

### 4. Connection Pool Sizing

```yaml
- REDIS_MAX_CONNECTIONS=200  # Default: 100
```

**Recommendation**: `CONNECTIONS = WORKERS × 25`

### 5. API Timeout Configuration

For slower network or complex queries:

```yaml
- LLM_TIMEOUT=1800  # 30 minutes (default: 900s)
- REDIS_SOCKET_TIMEOUT=60  # Increase if Redis queries timeout
```

## Monitoring and Health Checks

### Service Health Checks

```bash
# LightRAG API
curl http://localhost:9621/health

# Redis Stack
docker exec lightrag-redis redis-cli ping

# External LLM API
curl -H "Authorization: Bearer iAsmiqkLkU4e9fFf" \
  https://ml-llm-v-srv-v45-cp1-tst-node1.ai.warta.pl/v1/models

# External Embedding API
curl -H "Authorization: Bearer pU68nMPXhWgXjnIQ" \
  https://ml-ssm-l-srv-v16-cp2-tst-node5-llm-apps-tst.apps.ml.warta.pl/v1/models
```

### Redis Monitoring

```bash
# General info
docker exec lightrag-redis redis-cli INFO

# Memory usage
docker exec lightrag-redis redis-cli INFO memory

# Database sizes (per DB)
docker exec lightrag-redis redis-cli -n 0 DBSIZE  # KV
docker exec lightrag-redis redis-cli -n 1 DBSIZE  # DocStatus
docker exec lightrag-redis redis-cli -n 2 DBSIZE  # Vectors

# Vector index statistics
docker exec lightrag-redis redis-cli FT.INFO idx:redis_qwen3_workspace_vector_vdb_entities
docker exec lightrag-redis redis-cli FT.INFO idx:redis_qwen3_workspace_vector_vdb_relationships
docker exec lightrag-redis redis-cli FT.INFO idx:redis_qwen3_workspace_vector_vdb_chunks

# Connection stats
docker exec lightrag-redis redis-cli CLIENT LIST | wc -l  # Active connections
```

### Key Metrics to Monitor

**Memory:**
```bash
used_memory_human        # Current RAM usage
used_memory_peak_human   # Peak RAM usage
maxmemory_human          # Memory limit (8GB)
mem_fragmentation_ratio  # Should be < 1.5
```

**Performance:**
```bash
instantaneous_ops_per_sec  # Current throughput
total_commands_processed   # Cumulative operations
rejected_connections       # Should be 0
```

**Persistence:**
```bash
rdb_last_save_time        # Last RDB snapshot
rdb_changes_since_last_save  # Unsaved changes
aof_current_size          # AOF log size
```

**Vector Indexes (per namespace):**
```bash
num_docs                  # Total vectors stored
num_records               # Index records
inverted_sz_mb            # Index memory usage
vector_index_sz_mb        # Vector data size
```

## Backup and Restore

### Redis Backup

**Method 1: RDB Snapshot (Fastest, point-in-time)**
```bash
# Trigger background save
docker exec lightrag-redis redis-cli BGSAVE

# Wait for completion
docker exec lightrag-redis redis-cli LASTSAVE

# Copy RDB file
docker cp lightrag-redis:/data/dump.rdb ./backup/redis-$(date +%Y%m%d).rdb
```

**Method 2: Volume Backup (Complete, includes AOF)**
```bash
# Stop services
docker-compose -f docker-compose-redis-full.yml stop lightrag

# Backup volumes
docker run --rm \
  -v redis-data:/data \
  -v $(pwd)/backup:/backup \
  alpine tar czf /backup/redis-data-$(date +%Y%m%d).tar.gz /data

# Restart services
docker-compose -f docker-compose-redis-full.yml start lightrag
```

**Method 3: AOF Backup (Incremental)**
```bash
# Ensure AOF is enabled (already in redis.conf)
docker exec lightrag-redis redis-cli CONFIG GET appendonly

# Copy AOF file
docker cp lightrag-redis:/data/appendonly.aof ./backup/redis-$(date +%Y%m%d).aof
```

### NetworkX Graph Backup

```bash
# Backup graph files (lightweight)
docker run --rm \
  -v lightrag-data:/data \
  -v $(pwd)/backup:/backup \
  alpine tar czf /backup/graph-data-$(date +%Y%m%d).tar.gz /data
```

### Restore from Backup

**Restore Redis Data:**
```bash
# Stop services
docker-compose -f docker-compose-redis-full.yml down

# Remove old volume
docker volume rm redis-data

# Create new volume
docker volume create redis-data

# Restore data
docker run --rm \
  -v redis-data:/data \
  -v $(pwd)/backup:/backup \
  alpine sh -c "cd / && tar xzf /backup/redis-data-YYYYMMDD.tar.gz"

# Start services
docker-compose -f docker-compose-redis-full.yml up -d
```

**Restore Graph Data:**
```bash
docker volume rm lightrag-data
docker volume create lightrag-data
docker run --rm \
  -v lightrag-data:/data \
  -v $(pwd)/backup:/backup \
  alpine sh -c "cd / && tar xzf /backup/graph-data-YYYYMMDD.tar.gz"
```

## Troubleshooting

### External API Connection Errors

**Symptom**: `Connection refused` or `timeout` or `Failed to connect to LLM`

**Solutions:**

1. **Verify network connectivity from container:**
   ```bash
   # Test LLM endpoint
   docker exec lightrag-server curl -I https://ml-llm-v-srv-v45-cp1-tst-node1.ai.warta.pl/v1

   # Test embedding endpoint
   docker exec lightrag-server curl -I https://ml-ssm-l-srv-v16-cp2-tst-node5-llm-apps-tst.apps.ml.warta.pl/v1
   ```

2. **Check API key validity:**
   ```bash
   # Test LLM API
   curl -H "Authorization: Bearer iAsmiqkLkU4e9fFf" \
     https://ml-llm-v-srv-v45-cp1-tst-node1.ai.warta.pl/v1/models

   # Test Embedding API
   curl -H "Authorization: Bearer pU68nMPXhWgXjnIQ" \
     https://ml-ssm-l-srv-v16-cp2-tst-node5-llm-apps-tst.apps.ml.warta.pl/v1/models
   ```

3. **Verify DNS resolution:**
   ```bash
   docker exec lightrag-server nslookup ml-llm-v-srv-v45-cp1-tst-node1.ai.warta.pl
   ```

4. **Check firewall rules** (corporate network may block HTTPS)

5. **Increase timeout** if API is slow:
   ```yaml
   - LLM_TIMEOUT=1800  # 30 minutes
   ```

**Symptom**: `Invalid API key` or `401 Unauthorized`

**Solution**: Verify API keys in docker-compose-redis-full.yml match provided credentials

**Symptom**: `Model not found`

**Solution**: Verify model names exactly match:
- LLM: `Qwen/Qwen3-Next-80B-A3B-Thinking`
- Embedding: `Qwen3-Embedding-8B`

### Redis Connection Errors

**Symptom**: `ConnectionError: Redis connection not initialized`

**Solutions:**
```bash
# Check Redis is running
docker ps | grep lightrag-redis

# Check Redis logs
docker logs lightrag-redis

# Test connection
docker exec lightrag-redis redis-cli ping

# Verify port binding
docker port lightrag-redis
```

### Vector Index Creation Failures

**Symptom**: `ResponseError: Unknown Index name`

**Solutions:**
```bash
# Check RediSearch module loaded
docker exec lightrag-redis redis-cli MODULE LIST

# Should see: search, searchlight

# List all indexes
docker exec lightrag-redis redis-cli FT._LIST

# Check specific index info
docker exec lightrag-redis redis-cli FT.INFO idx:redis_qwen3_workspace_vector_vdb_entities
```

### Embedding Dimension Mismatch

**Symptom**: `Embedding dimension mismatch: stored=384, current=4096`

**Solution**: Clear existing vectors and re-index

```bash
# Option 1: Drop indexes (safe, preserves other data)
docker exec lightrag-redis redis-cli -n 2 FT.DROPINDEX idx:redis_qwen3_workspace_vector_vdb_entities DD
docker exec lightrag-redis redis-cli -n 2 FT.DROPINDEX idx:redis_qwen3_workspace_vector_vdb_relationships DD
docker exec lightrag-redis redis-cli -n 2 FT.DROPINDEX idx:redis_qwen3_workspace_vector_vdb_chunks DD

# Option 2: Flush vector database (clears all DB 2 data)
docker exec lightrag-redis redis-cli -n 2 FLUSHDB

# Then restart LightRAG to recreate indexes
docker-compose -f docker-compose-redis-full.yml restart lightrag
```

### Memory Exhaustion

**Symptom**: `OOM command not allowed when used memory > 'maxmemory'`

**Solutions:**

1. **Increase Redis memory:**
   ```yaml
   redis-stack:
     environment:
       - REDIS_ARGS=--appendonly yes --maxmemory 16gb --maxmemory-policy noeviction
   ```

2. **Enable LRU eviction** (use with caution):
   ```yaml
   - REDIS_ARGS=--appendonly yes --maxmemory 8gb --maxmemory-policy allkeys-lru
   ```

3. **Clear unused data:**
   ```bash
   # Check database sizes
   docker exec lightrag-redis redis-cli -n 0 DBSIZE
   docker exec lightrag-redis redis-cli -n 1 DBSIZE
   docker exec lightrag-redis redis-cli -n 2 DBSIZE

   # Clear specific database if too large
   docker exec lightrag-redis redis-cli -n 2 FLUSHDB  # Clear vectors only
   ```

### Slow Queries

**Solutions:**

1. **Lower HNSW quality** for speed:
   ```yaml
   - REDIS_HNSW_M=8
   - REDIS_HNSW_EF_CONSTRUCTION=256
   ```

2. **Use `mix` query mode** instead of `hybrid`:
   ```yaml
   - DEFAULT_QUERY_MODE=mix
   ```

3. **Increase worker count**:
   ```yaml
   - WORKERS=8
   ```

4. **Check API latency:**
   ```bash
   time curl -H "Authorization: Bearer iAsmiqkLkU4e9fFf" \
     https://ml-llm-v-srv-v45-cp1-tst-node1.ai.warta.pl/v1/models
   ```

### Connection Pool Exhaustion

**Symptom**: `ConnectionPool: too many connections`

**Solutions:**
```yaml
- REDIS_MAX_CONNECTIONS=200  # Increase from 100
- WORKERS=4  # Reduce if too many connections
```

## API Usage Examples

### Insert Documents

```bash
curl -X POST http://localhost:9621/insert \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "LightRAG combines vector search with knowledge graphs for enhanced retrieval."
  }'
```

### Batch Insert

```bash
curl -X POST http://localhost:9621/batch_insert \
  -H 'Content-Type: application/json' \
  -d '{
    "texts": [
      "Document 1: Redis provides fast in-memory storage.",
      "Document 2: HNSW enables efficient similarity search.",
      "Document 3: External APIs eliminate model deployment."
    ]
  }'
```

### Query with Different Modes

```bash
# Naive mode (vector search only - fastest)
curl -X POST http://localhost:9621/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "What is LightRAG?", "mode": "naive", "top_k": 10}'

# Hybrid mode (recommended for balanced performance)
curl -X POST http://localhost:9621/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "What is LightRAG?", "mode": "hybrid", "top_k": 10}'

# Mix mode (best for Redis with external APIs)
curl -X POST http://localhost:9621/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "What is LightRAG?", "mode": "mix", "top_k": 10}'
```

### Query Mode Performance (with External APIs)

| Mode | Description | Latency | Best For |
|------|-------------|---------|----------|
| `naive` | Vector search only | 2-4s | Simple queries |
| `local` | Entity neighborhood | 4-7s | Context-dependent |
| `global` | Graph structure | 6-10s | Global knowledge |
| `hybrid` | Local + global | 9-15s | Comprehensive |
| `mix` | KG + vector | 5-10s | **Recommended** |

*Latency includes ~1-3s network time to external APIs

## Security Considerations

### API Key Management

**Current Approach:** Plain text in docker-compose.yml

**Production Recommendations:**

1. **Docker Secrets:**
   ```yaml
   secrets:
     llm_api_key:
       file: ./secrets/llm_api_key.txt
     embedding_api_key:
       file: ./secrets/embedding_api_key.txt

   services:
     lightrag:
       secrets:
         - llm_api_key
         - embedding_api_key
   ```

2. **Environment Files:**
   ```bash
   # Create .env file (not committed to git)
   echo "LLM_BINDING_API_KEY=iAsmiqkLkU4e9fFf" > .env
   echo "EMBEDDING_BINDING_API_KEY=pU68nMPXhWgXjnIQ" >> .env

   # Reference in docker-compose
   env_file:
     - .env
   ```

3. **External Secret Managers:**
   - AWS Secrets Manager
   - HashiCorp Vault
   - Azure Key Vault

### Network Security

```yaml
# Restrict Redis to internal network only
redis-stack:
  ports: []  # Remove external port exposure
  networks:
    - internal

networks:
  internal:
    internal: true  # No external access
```

## Advanced Configuration

### Redis Cluster Setup (Horizontal Scaling)

For > 250K documents:

```yaml
redis-cluster:
  image: redis/redis-stack-server:latest
  command: redis-server --cluster-enabled yes --cluster-config-file nodes.conf
  # Deploy 3+ instances with cluster configuration
```

### Custom Redis Configuration

Mount custom redis.conf for fine-tuning:

```yaml
redis-stack:
  volumes:
    - ./redis-custom.conf:/usr/local/etc/redis/redis.conf
    - redis-data:/data
  command: redis-server /usr/local/etc/redis/redis.conf
```

**Advanced redis.conf options:**
```conf
# Threading for I/O
io-threads 4
io-threads-do-reads yes

# Memory optimization
activedefrag yes
active-defrag-threshold-lower 10

# Slow log
slowlog-log-slower-than 10000  # 10ms
slowlog-max-len 128
```

## Migration Guide

### From Local Ollama to External APIs

If you have existing data with 384-dim All-MiniLM embeddings:

1. **Backup existing data:**
   ```bash
   docker exec lightrag-redis redis-cli BGSAVE
   docker cp lightrag-redis:/data/dump.rdb ./backup/ollama-384dim.rdb
   ```

2. **Clear vector indexes** (384-dim incompatible with 4096-dim):
   ```bash
   docker exec lightrag-redis redis-cli -n 2 FLUSHDB
   ```

3. **Keep KV and DocStatus** (compatible):
   ```bash
   # DB 0 and DB 1 can remain - only vectors need re-indexing
   ```

4. **Start new configuration:**
   ```bash
   ./lightrag.sh stop
   ./lightrag.sh start-redis-full
   ```

5. **Re-index documents** with new 4096-dim embeddings:
   ```bash
   # Extract text from KV storage and re-insert
   # (Will trigger new embeddings via Qwen3-Embedding-8B)
   ```

### From PostgreSQL to Redis

See original README-REDIS-FULL.md migration section.

## Data Persistence

All data is stored in Docker volumes:

```
redis-data          → Redis persistence (RDB + AOF)
lightrag-data       → NetworkX graph files
```

**Persistence Strategy:**
- **Redis**: RDB snapshots (15min/5min/1min intervals) + AOF logs (every second)
- **Graph**: File-based JSON in lightrag-data volume
- **No models**: External APIs eliminate 10GB+ of model storage

**Data survives:**
- ✅ Container restarts
- ✅ Service updates
- ✅ Docker daemon restarts
- ✅ Network failures (local data persists)

**Data does NOT survive:**
- ❌ `docker-compose down -v` (removes volumes)
- ❌ `./lightrag.sh cleanup` (removes everything)
- ❌ Manual volume deletion

## Cost and Performance Considerations

### External API Costs

**Factors:**
- LLM API calls (per query + entity extraction)
- Embedding API calls (per document + per query)
- Network bandwidth
- API provider pricing

**Estimation for 1000 documents + 100 queries:**
- Document embeddings: ~1000 API calls
- Entity extraction: ~1000 LLM calls
- Query embeddings: ~100 API calls
- Query generation: ~100 LLM calls
- **Total**: ~2200 API calls

### Performance Trade-offs

**Pros:**
- ✅ 80B model vs 7B (better quality)
- ✅ 4096-dim vs 384-dim (better retrieval)
- ✅ No local GPU needed
- ✅ Faster startup

**Cons:**
- ❌ Network latency adds 1-3s per query
- ❌ API dependency (downtime affects system)
- ❌ Potential API rate limits
- ❌ Requires internet connection

## Support and Resources

- **LightRAG Repository**: https://github.com/HKUDS/LightRAG
- **Redis Stack Documentation**: https://redis.io/docs/stack/
- **Redis Search Documentation**: https://redis.io/docs/interact/search-and-query/
- **Docker Image**: ghcr.io/peterpawluk/lightrag:latest
- **Qwen3 Model**: Alibaba Cloud

## License

This configuration is part of the LightRAG project and follows the MIT license.
