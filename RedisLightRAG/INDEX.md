# LightRAG with Qwen 3, Redis Vector Store & NetworkX - Complete Setup

## 📦 Package Contents

This package contains everything you need to run LightRAG with:
- **Qwen 3** (8B) for LLM
- **Qwen 3 Embedding** (8B) for embeddings
- **Redis Stack** for vector storage
- **NetworkX** for graph storage
- **Ollama** for local model serving

---

## 📁 Files Included

### Core Configuration Files

1. **docker-compose.yml** ⭐ Main configuration
   - Default setup with NanoVectorDB for vectors (faster)
   - Redis for KV and document status storage
   - NetworkX for graph storage
   - Recommended for: Testing and development

2. **docker-compose.redis-vectors.yml** 🚀 Production configuration
   - Redis for ALL storage including vectors
   - Better persistence and production deployment
   - Recommended for: Production use

3. **env.example** 🔧 Environment variables
   - Copy to `.env` and customize as needed
   - Contains all configuration options
   - Includes comments and alternatives

4. **redis.conf** ⚙️ Redis configuration
   - Optimized for vector storage
   - Persistence enabled (RDB + AOF)
   - Memory management configured

### Scripts and Tools

5. **lightrag.sh** 🛠️ Management script (executable)
   - One-command setup: `./lightrag.sh start`
   - Service management
   - Log viewing
   - Health checks
   - Demo runner

6. **lightrag_demo.py** 🐍 Python demo script (executable)
   - Complete usage examples
   - Demonstrates all query modes
   - Batch operations
   - Mode comparison

7. **requirements.txt** 📋 Python dependencies
   - Install with: `pip install -r requirements.txt`

### Documentation

8. **QUICKSTART.md** ⚡ Quick start guide
   - Get started in minutes
   - Common commands
   - Troubleshooting
   - Performance tips

9. **README-LIGHTRAG.md** 📖 Complete documentation
   - Architecture overview
   - Detailed configuration
   - API reference
   - Advanced topics

---

## 🚀 Getting Started (3 Steps)

### Step 1: Extract Files
```bash
# Extract all files to a directory
mkdir lightrag-qwen
cd lightrag-qwen
# Copy all files here
```

### Step 2: Start Services
```bash
# Make scripts executable
chmod +x lightrag.sh lightrag_demo.py

# Start with default configuration (faster)
./lightrag.sh start

# OR start with full Redis storage (production)
./lightrag.sh start-redis
```

### Step 3: Test
```bash
# Check status
./lightrag.sh status

# Run demo
./lightrag.sh demo

# Or manually test
curl -X POST http://localhost:9621/insert \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello LightRAG!"}'
```

---

## 📊 Quick Reference

### Architecture
```
┌─────────────────────────────────────────────────────┐
│                    LightRAG Stack                   │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │   Ollama    │  │  Redis Stack │  │ LightRAG  │ │
│  │             │  │              │  │           │ │
│  │ • Qwen3 8B  │  │ • Vectors    │  │ • Server  │ │
│  │ • Qwen3-Emb │  │ • KV Store   │  │ • API     │ │
│  └─────────────┘  └──────────────┘  └───────────┘ │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │  NetworkX Graph Storage (File-based)       │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
└─────────────────────────────────────────────────────┘

         Ports: 9621 (API) | 11434 (Ollama) | 6379 (Redis)
```

### Service URLs
- **LightRAG API**: http://localhost:9621
- **Ollama API**: http://localhost:11434
- **Redis**: redis://localhost:6379

### Key Commands
```bash
./lightrag.sh start          # Start all services
./lightrag.sh stop           # Stop all services
./lightrag.sh status         # Show status
./lightrag.sh logs           # View logs
./lightrag.sh demo           # Run demo
./lightrag.sh test           # Test connections
./lightrag.sh cleanup        # Remove everything
```

### API Endpoints
```bash
# Insert document
POST /insert
{"text": "Your document"}

# Batch insert
POST /batch_insert
{"texts": ["doc1", "doc2"]}

# Query (5 modes: naive, local, global, hybrid, mix)
POST /query
{"query": "Your question", "mode": "mix"}

# Health check
GET /health
```

---

## 🎯 Configuration Options

### Choose Your Setup

**Option A: Default (docker-compose.yml)**
- ✅ Faster startup
- ✅ Lower memory usage
- ⚠️ Vectors in memory (lost on restart)
- 👉 Best for: Testing, development

**Option B: Full Redis (docker-compose.redis-vectors.yml)**
- ✅ Complete persistence
- ✅ Production-ready
- ✅ Vectors survive restarts
- ⚠️ Slightly more memory
- 👉 Best for: Production, important data

### Model Sizes

Edit `docker-compose.yml` to change:

| Model | Size | RAM Needed | Speed | Quality |
|-------|------|------------|-------|---------|
| qwen3:4b | ~3GB | ~8GB | Fast | Good |
| qwen3:8b | ~5GB | ~16GB | Medium | Better |
| qwen3:14b | ~9GB | ~24GB | Slower | Best |

---

## 🔧 Customization

### Change Models
Edit `docker-compose.yml`:
```yaml
- LLM_MODEL=qwen3:4b              # Smaller/faster
- EMBEDDING_MODEL=qwen3-embedding:4b
```

### Enable GPU
Uncomment in `docker-compose.yml`:
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

### Adjust Memory
Edit Redis memory:
```yaml
- REDIS_ARGS=--maxmemory 8gb  # Increase as needed
```

### More Workers
```yaml
- WORKERS=8  # Increase for more concurrency
```

---

## 📊 Query Modes Explained

| Mode | Vector Search | Graph Search | Use Case |
|------|--------------|--------------|----------|
| naive | ❌ | ❌ | Simple keyword matching |
| local | ✅ | ✅ (local) | Single-topic questions |
| global | ✅ | ✅ (global) | Broad overview questions |
| hybrid | ✅ | ✅ (both) | Complex questions |
| **mix** | ✅ | ✅ (integrated) | **Best overall** ⭐ |

**Recommendation**: Use `mode="mix"` for best results

---

## 🐛 Common Issues

### Models Not Downloading?
```bash
docker logs lightrag-ollama-setup
docker exec lightrag-ollama ollama pull qwen3:8b
```

### Service Not Starting?
```bash
./lightrag.sh logs lightrag
docker-compose restart lightrag
```

### Out of Memory?
```bash
# Use smaller models
- LLM_MODEL=qwen3:4b
- EMBEDDING_MODEL=qwen3-embedding:0.6b
```

### Slow Performance?
1. Enable GPU (10-50x faster)
2. Use quantized models: `qwen3:8b-q4_K_M`
3. Increase Redis memory
4. Use more workers

---

## 📚 Documentation

- **QUICKSTART.md** - Get started in 5 minutes
- **README-LIGHTRAG.md** - Complete guide
- **env.example** - All configuration options
- **lightrag_demo.py** - Usage examples

---

## 🔗 Resources

- [LightRAG GitHub](https://github.com/HKUDS/LightRAG)
- [Qwen 3 Documentation](https://qwenlm.github.io/)
- [Redis Vector Search](https://redis.io/docs/latest/develop/get-started/vector-database/)
- [Ollama Documentation](https://ollama.ai/docs)

---

## 📝 License

- LightRAG: Apache 2.0
- Qwen 3: Apache 2.0
- Redis: BSD-3-Clause
- Ollama: MIT

---

## 🆘 Support

**Quick Help:**
```bash
./lightrag.sh help
```

**Check Logs:**
```bash
./lightrag.sh logs
```

**Test Everything:**
```bash
./lightrag.sh test
```

---

## ✨ Features

✅ **Local Deployment** - No external API calls  
✅ **State-of-the-Art Models** - Qwen 3 top MTEB ranking  
✅ **Vector + Graph** - Dual retrieval for better results  
✅ **100+ Languages** - Multilingual support  
✅ **Persistent Storage** - Redis with auto-save  
✅ **GPU Support** - Optional acceleration  
✅ **Easy Management** - One-command setup  
✅ **Production Ready** - Full Redis option  

---

**Happy RAG-ing! 🚀**

For detailed instructions, see **QUICKSTART.md** or **README-LIGHTRAG.md**
