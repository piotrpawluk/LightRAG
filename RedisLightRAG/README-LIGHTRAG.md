# LightRAG with Qwen 3, Redis Vector Store, and NetworkX

A complete Docker Compose setup for LightRAG with Qwen 3 models, Redis for vector storage, and NetworkX for graph operations.

## Architecture Overview

This setup includes:
- **LightRAG**: Graph-enhanced RAG system for intelligent document retrieval
- **Qwen 3**: State-of-the-art LLM (8B) for text generation
- **Qwen 3 Embedding**: Top-ranked embedding model (8B) for vector representations
- **Redis Stack**: Vector database with persistence for storing embeddings
- **NetworkX**: Graph storage for knowledge graph operations
- **Ollama**: Local model serving for both LLM and embeddings

## Features

- ✅ **Local Deployment**: All components run locally with no external API calls
- ✅ **Vector Search**: Redis Stack provides fast similarity search capabilities
- ✅ **Knowledge Graph**: NetworkX for graph-based retrieval
- ✅ **Dual-Level Retrieval**: Combines vector search with graph exploration
- ✅ **Multilingual**: Qwen 3 supports 100+ languages
- ✅ **Persistent Storage**: Redis with automatic data persistence
- ✅ **GPU Support**: Optional GPU acceleration for models

## Prerequisites

- Docker and Docker Compose installed
- At least 16GB RAM (32GB recommended)
- 20GB free disk space for models
- (Optional) NVIDIA GPU with Docker GPU support for faster inference

## Quick Start

### 1. Clone and Setup

```bash
# Create project directory
mkdir lightrag-qwen && cd lightrag-qwen

# Download the docker-compose.yml file (or copy from this repository)
# Download the .env.lightrag file

# Optional: Copy environment variables
cp .env.lightrag .env
```

### 2. Start Services

```bash
# Start all services
docker-compose up -d

# This will:
# 1. Start Redis Stack
# 2. Start Ollama service
# 3. Download Qwen 3 models (8B LLM + 8B Embedding) - this takes time!
# 4. Start LightRAG server
```

### 3. Monitor Setup Progress

```bash
# Watch model download progress
docker logs -f lightrag-ollama-setup

# Check LightRAG server logs
docker logs -f lightrag-server

# Verify all services are healthy
docker-compose ps
```

### 4. Test the Setup

```bash
# Check LightRAG health
curl http://localhost:9621/health

# Check Ollama models
curl http://localhost:11434/api/tags

# Check Redis
docker exec lightrag-redis redis-cli ping
```

## Usage Examples

### Using Python Client

```python
import requests

# Base URL
base_url = "http://localhost:9621"

# 1. Insert documents
response = requests.post(
    f"{base_url}/insert",
    json={
        "text": "LightRAG is a retrieval-augmented generation system that combines vector search with knowledge graphs."
    }
)
print(response.json())

# 2. Query with hybrid mode (vector + graph)
response = requests.post(
    f"{base_url}/query",
    json={
        "query": "What is LightRAG?",
        "mode": "hybrid"
    }
)
print(response.json())

# 3. Query modes: naive, local, global, hybrid, mix
modes = ["local", "global", "hybrid"]
for mode in modes:
    response = requests.post(
        f"{base_url}/query",
        json={"query": "Explain graph-based retrieval", "mode": mode}
    )
    print(f"\n{mode.upper()} mode:", response.json())
```

### Using cURL

```bash
# Insert a document
curl -X POST http://localhost:9621/insert \
  -H "Content-Type: application/json" \
  -d '{"text": "The Qwen 3 model supports over 100 languages and excels at multilingual tasks."}'

# Query with hybrid mode
curl -X POST http://localhost:9621/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What languages does Qwen 3 support?", "mode": "hybrid"}'

# Batch insert documents
curl -X POST http://localhost:9621/batch_insert \
  -H "Content-Type: application/json" \
  -d '{"texts": ["Document 1 text", "Document 2 text", "Document 3 text"]}'
```

## Query Modes Explained

LightRAG supports multiple query modes:

- **naive**: Simple keyword-based retrieval
- **local**: Retrieves from local entity neighborhoods in the graph
- **global**: Retrieves from global graph structure
- **hybrid**: Combines local and global retrieval
- **mix**: Integrates knowledge graph and vector retrieval (recommended)

## Configuration

### Model Selection

Edit `docker-compose.yml` to change model sizes:

```yaml
# For smaller/faster models:
- LLM_MODEL=qwen3:4b
- EMBEDDING_MODEL=qwen3-embedding:4b

# For larger/better quality:
- LLM_MODEL=qwen3:14b
- EMBEDDING_MODEL=qwen3-embedding:8b
```

### Enable Redis Vector Storage

By default, NanoVectorDB is used for vectors. To use Redis for vector storage:

1. Edit `docker-compose.yml`:
```yaml
- LIGHTRAG_VECTOR_STORAGE=RedisVectorStorage
- REDIS_VECTOR_URL=redis://redis:6379
- REDIS_VECTOR_DB=2
```

2. Restart services:
```bash
docker-compose restart lightrag
```

### GPU Support

Uncomment the GPU section in `docker-compose.yml`:

```yaml
ollama:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: all
            capabilities: [gpu]
```

Then restart:
```bash
docker-compose down
docker-compose up -d
```

## Storage Backends

### Current Configuration

- **KV Storage**: Redis (persistent key-value store)
- **Document Status**: Redis (tracks document processing)
- **Vector Storage**: NanoVectorDB (in-memory, fast) OR Redis (persistent)
- **Graph Storage**: NetworkX (file-based, suitable for small to medium graphs)

### Alternative Graph Stores

For larger deployments, consider Neo4j:

```yaml
neo4j:
  image: neo4j:latest
  ports:
    - "7474:7474"
    - "7687:7687"
  environment:
    - NEO4J_AUTH=neo4j/password
    - NEO4J_PLUGINS=["graph-data-science"]

lightrag:
  environment:
    - LIGHTRAG_GRAPH_STORAGE=Neo4JStorage
    - NEO4J_URL=bolt://neo4j:7687
    - NEO4J_USER=neo4j
    - NEO4J_PASSWORD=password
```

## Performance Tuning

### Redis Configuration

Adjust Redis memory in `docker-compose.yml`:
```yaml
- REDIS_ARGS=--save 900 1 --save 300 10 --save 60 1000 --maxmemory 8gb --maxmemory-policy noeviction
```

### Worker Processes

Adjust LightRAG workers based on CPU cores:
```yaml
- WORKERS=8  # Increase for more concurrent requests
```

### Model Quantization

Use quantized models for faster inference:
```bash
# In ollama-setup service
ollama pull qwen3:8b-q4_K_M  # 4-bit quantization
ollama pull qwen3-embedding:8b-q5_K_M  # 5-bit quantization
```

## Monitoring

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f lightrag
docker-compose logs -f ollama
docker-compose logs -f redis
```

### Check Resource Usage

```bash
# Container stats
docker stats

# Disk usage
docker system df -v
```

### Redis Monitoring

```bash
# Enter Redis CLI
docker exec -it lightrag-redis redis-cli

# Monitor commands
MONITOR

# Check memory usage
INFO MEMORY

# List all keys
KEYS *

# Check vector index
FT.INFO lightrag_vectors
```

## Troubleshooting

### Models Not Downloading

```bash
# Check ollama-setup logs
docker logs lightrag-ollama-setup

# Manually pull models
docker exec lightrag-ollama ollama pull qwen3:8b
docker exec lightrag-ollama ollama pull qwen3-embedding:8b
```

### LightRAG Connection Errors

```bash
# Verify Ollama is accessible
curl http://localhost:11434/api/tags

# Verify Redis is accessible
docker exec lightrag-redis redis-cli ping

# Restart LightRAG
docker-compose restart lightrag
```

### Out of Memory

```bash
# Use smaller models
# In docker-compose.yml change to:
- LLM_MODEL=qwen3:4b
- EMBEDDING_MODEL=qwen3-embedding:0.6b

# Or increase Docker memory limit in Docker Desktop settings
```

### Slow Performance

1. Enable GPU support (see above)
2. Use quantized models
3. Increase Redis memory
4. Use Redis for vector storage (persistent caching)

## Data Persistence

All data is stored in Docker volumes:
- `redis-data`: Redis persistence
- `ollama-data`: Downloaded models
- `lightrag-data`: Graph and document data

### Backup

```bash
# Backup volumes
docker run --rm \
  -v lightrag-redis-data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/redis-backup.tar.gz /data

# Backup LightRAG data
docker run --rm \
  -v lightrag-lightrag-data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/lightrag-backup.tar.gz /data
```

### Restore

```bash
# Restore from backup
docker run --rm \
  -v lightrag-redis-data:/data \
  -v $(pwd):/backup \
  alpine sh -c "cd / && tar xzf /backup/redis-backup.tar.gz"
```

## API Endpoints

- `POST /insert` - Insert a single document
- `POST /batch_insert` - Insert multiple documents
- `POST /query` - Query with specified mode
- `GET /health` - Health check
- `GET /stats` - Get statistics

## Cleanup

```bash
# Stop services
docker-compose down

# Remove volumes (WARNING: deletes all data)
docker-compose down -v

# Remove downloaded models
docker volume rm lightrag-qwen_ollama-data
```

## Resources

- [LightRAG GitHub](https://github.com/HKUDS/LightRAG)
- [Qwen 3 Models](https://qwenlm.github.io/)
- [Redis Vector Search](https://redis.io/docs/latest/develop/get-started/vector-database/)
- [Ollama Documentation](https://ollama.ai/docs)

## License

This configuration is provided as-is. Please refer to individual component licenses:
- LightRAG: Apache 2.0
- Qwen 3: Apache 2.0
- Redis: BSD-3-Clause
- Ollama: MIT

## Support

For issues:
- LightRAG: https://github.com/HKUDS/LightRAG/issues
- This setup: Create an issue in your repository
