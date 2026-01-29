# LightRAG + Qwen 3 + Redis Vectors - Quick Start Guide

## 🚀 One-Command Setup

```bash
./lightrag.sh start
```

That's it! This will:
- ✅ Start Redis Stack (with vector search)
- ✅ Start Ollama
- ✅ Download Qwen 3 8B LLM (~5GB)
- ✅ Download Qwen 3 Embedding 8B (~5GB)
- ✅ Start LightRAG server

**Time required:** 10-30 minutes (first time only, depending on internet speed)

## 📋 What You Get

```
┌─────────────────────────────────────────────┐
│  LightRAG Stack                             │
├─────────────────────────────────────────────┤
│  🧠 LLM:        Qwen 3 8B (via Ollama)      │
│  📊 Embeddings: Qwen 3 Embedding 8B         │
│  🔍 Vectors:    Redis Stack                 │
│  📈 Graph:      NetworkX                    │
│  🗄️  KV Store:   Redis                       │
├─────────────────────────────────────────────┤
│  Port 9621:  LightRAG API                   │
│  Port 11434: Ollama API                     │
│  Port 6379:  Redis                          │
└─────────────────────────────────────────────┘
```

## 🎯 Quick Test

### 1. Check Health
```bash
curl http://localhost:9621/health
```

### 2. Insert a Document
```bash
curl -X POST http://localhost:9621/insert \
  -H "Content-Type: application/json" \
  -d '{"text": "LightRAG combines vector search with knowledge graphs for better retrieval."}'
```

### 3. Query
```bash
curl -X POST http://localhost:9621/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is LightRAG?", "mode": "hybrid"}'
```

### 4. Run Demo Script
```bash
pip install -r requirements.txt
./lightrag_demo.py
```

## 📦 Two Configuration Options

### Option 1: Default (Faster, Less Persistent)
```bash
./lightrag.sh start
```
- Uses NanoVectorDB for vectors (in-memory, faster)
- Uses Redis for KV and document status
- Uses NetworkX for graphs

### Option 2: Full Redis (More Persistent)
```bash
./lightrag.sh start-redis
```
- Uses Redis for EVERYTHING including vectors
- Better for production
- Survives container restarts

## 🔧 Common Commands

```bash
# View status
./lightrag.sh status

# View logs
./lightrag.sh logs
./lightrag.sh logs lightrag    # specific service

# Restart
./lightrag.sh restart

# Stop
./lightrag.sh stop

# Test connections
./lightrag.sh test

# Run demo
./lightrag.sh demo

# Complete cleanup (removes everything)
./lightrag.sh cleanup
```

## 📊 Query Modes

LightRAG supports 5 retrieval modes:

| Mode | Description | When to Use |
|------|-------------|-------------|
| `naive` | Simple keyword search | Fast, basic queries |
| `local` | Local entity neighborhood | Single-topic questions |
| `global` | Global graph structure | Broad overview questions |
| `hybrid` | Combines local + global | Complex questions |
| `mix` | Vector + Graph retrieval | **Recommended** for best results |

Example:
```python
import requests

response = requests.post(
    "http://localhost:9621/query",
    json={
        "query": "Explain how graph-based retrieval works",
        "mode": "mix",  # Recommended
        "top_k": 10
    }
)
```

## 🎨 Model Selection

### Change Model Sizes

Edit `docker-compose.yml`:

**For Faster/Smaller:**
```yaml
- LLM_MODEL=qwen3:4b              # Instead of 8b
- EMBEDDING_MODEL=qwen3-embedding:4b
```

**For Better Quality:**
```yaml
- LLM_MODEL=qwen3:14b             # If you have GPU
- EMBEDDING_MODEL=qwen3-embedding:8b
```

Available sizes:
- Qwen 3 LLM: 0.5b, 1.5b, 4b, 8b, 14b, 32b
- Qwen 3 Embedding: 0.6b, 4b, 8b

## 🚄 Enable GPU (NVIDIA)

1. Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

2. Edit `docker-compose.yml`, uncomment:
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

3. Restart:
```bash
./lightrag.sh restart
```

## 📈 Performance Tips

### For Better Speed:
1. Use GPU (10-50x faster)
2. Use smaller models (4b instead of 8b)
3. Use quantized models: `qwen3:8b-q4_K_M`
4. Increase Redis memory
5. Use SSD for Docker volumes

### For Better Quality:
1. Use larger models (14b or 32b)
2. Use `mode="mix"` for queries
3. Enable reranker (Qwen3-Reranker)
4. Increase `top_k` parameter

## 🔍 Monitoring

### Check Resource Usage
```bash
docker stats
```

### Monitor Redis
```bash
# Enter Redis CLI
docker exec -it lightrag-redis redis-cli

# Check memory
INFO MEMORY

# Monitor operations
MONITOR

# Check vector index
FT.INFO lightrag_vectors_qwen3
```

### View Ollama Models
```bash
docker exec lightrag-ollama ollama list
```

## 🐛 Troubleshooting

### Models Not Downloading?
```bash
# Check logs
docker logs lightrag-ollama-setup

# Manual download
docker exec lightrag-ollama ollama pull qwen3:8b
docker exec lightrag-ollama ollama pull qwen3-embedding:8b
```

### LightRAG Not Starting?
```bash
# Check logs
docker logs lightrag-server

# Verify Ollama is ready
curl http://localhost:11434/api/tags

# Restart
./lightrag.sh restart
```

### Out of Memory?
```bash
# Use smaller models
- LLM_MODEL=qwen3:4b
- EMBEDDING_MODEL=qwen3-embedding:0.6b

# Or increase Docker memory in Docker Desktop settings
```

### Slow Queries?
1. Enable GPU support
2. Use quantized models
3. Use Redis for vector storage
4. Increase `WORKERS` in compose file

## 📚 API Reference

### Insert Document
```http
POST /insert
Content-Type: application/json

{
  "text": "Your document text here"
}
```

### Batch Insert
```http
POST /batch_insert
Content-Type: application/json

{
  "texts": ["doc1", "doc2", "doc3"]
}
```

### Query
```http
POST /query
Content-Type: application/json

{
  "query": "Your question",
  "mode": "mix",
  "top_k": 10
}
```

### Health Check
```http
GET /health
```

## 💾 Data Persistence

All data is in Docker volumes:
- `redis-data`: Redis database (persistent)
- `ollama-data`: Downloaded models (persistent)
- `lightrag-data`: Graph and documents (persistent)

### Backup
```bash
# Backup Redis
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

## 🔗 Links

- [Full README](README-LIGHTRAG.md) - Comprehensive documentation
- [LightRAG GitHub](https://github.com/HKUDS/LightRAG)
- [Qwen 3 Models](https://qwenlm.github.io/)
- [Redis Vector Docs](https://redis.io/docs/latest/develop/get-started/vector-database/)

## 🆘 Need Help?

```bash
./lightrag.sh help
```

Or check logs:
```bash
./lightrag.sh logs
```
