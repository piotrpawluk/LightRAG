/# LightRAG — Product Requirements Document

**Version:** 0.1.0
**Created:** 2026-02-10
**Author:** peterpawluk
**Status:** Draft

## 1. Problem Statement

Traditional RAG systems rely on flat vector search, which loses contextual relationships between concepts. This results in poor retrieval quality for complex queries that require understanding connections between entities. LightRAG solves this by using graph-based knowledge representation — extracting entities and relationships from documents, building a knowledge graph, and combining graph-based retrieval with vector search for higher-quality answers.

## 2. Target Users

Internal team deploying LightRAG for specific knowledge-intensive applications. The team needs a customizable RAG framework that can be tuned for domain-specific use cases, with support for Polish language content and optimized query performance.

## 3. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Query quality | Accurate, relevant responses from knowledge graph | Manual evaluation of response relevance |
| Processing speed | Fast document ingestion and query response times | Latency benchmarks for ingestion and query endpoints |

## 4. Scope

### In Scope (MVP)

- Core RAG pipeline with graph-based knowledge extraction
- Multi-modal retrieval (local, global, hybrid, mix, naive modes)
- FastAPI server with REST endpoints
- React WebUI for knowledge graph visualization and query testing
- Pluggable storage backends (Neo4j, PostgreSQL, Redis, Milvus, etc.)
- LLM provider bindings (OpenAI, Ollama, Anthropic, Bedrock, etc.)
- Polish language optimization and prompt tuning
- Query performance optimization (parallel execution, caching)

### Out of Scope

- Mobile application
- Multi-tenant SaaS deployment
- Custom training of embedding models
- Real-time document streaming ingestion

## 5. Architecture

### Tech Stack

| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| Language (backend) | Python | >=3.10 (running 3.12) | Async/await patterns throughout |
| Language (frontend) | TypeScript | ~5.9 | React 19 with functional components |
| Backend Framework | FastAPI | latest | REST + Ollama-compatible API |
| Frontend Framework | React | 19 | Vite + Bun build, Tailwind CSS |
| Database | Pluggable | multiple | Neo4j, PostgreSQL, Redis, Milvus, Qdrant, MongoDB, Faiss |
| Auth | JWT + API Key | — | bcrypt, python-jose |

### Infrastructure

| Component | Choice | Notes |
|-----------|--------|-------|
| Git Host | GitHub | origin: HKUDS/LightRAG, fork: piotrpawluk/LightRAG |
| Cloud Provider | Self-hosted (OKD) | 2 environments: DEV, QA |
| CI/CD | GitHub Actions | 9 workflows (docker, linting, tests, pypi-publish) |
| Containers | Docker + docker-compose | Dockerfile, Dockerfile.lite, multiple compose files |
| IaC | none | Manual OKD deployment |

### Environment Strategy

| Environment | Purpose | URL | Deploy Trigger |
|-------------|---------|-----|----------------|
| Local | Development & unit tests | http://localhost:9621 | Manual |
| DEV (OKD) | Development/integration testing | TBD | Push to dev branch |
| QA (OKD) | Quality assurance testing | TBD | Push to qa branch |

**Environment Tier:** 2 (Local + DEV/QA on OKD)

## 6. Milestones & Roadmap

### Current Maturity: Beta

### Roadmap

| Milestone | Goal | Target Maturity | Status | Success Criteria |
|-----------|------|-----------------|--------|------------------|
| M1: Polish & Optimize | Improve query quality and processing speed | Beta | NOW | Query relevance improvement, latency reduction |

### Milestone Detail

#### M1: Polish & Optimize [NOW]
**Goal:** Optimize query quality and processing speed for production use
**Appetite:** Ongoing
**Target maturity:** Beta
**Features:**
- Polish language prompt optimization
- Query parallelization and caching
- Storage backend performance tuning
**Success criteria:**
- [ ] Query response quality meets internal standards
- [ ] Query latency within acceptable thresholds
- [ ] Stable deployment on OKD environments

### Maturity Promotion Path

| From | To | Requirements |
|------|-----|-------------|
| beta -> ga | 90%+ coverage, 30+ days production stability, SLAs defined, comprehensive E2E tests |

## 7. Key Features

### Feature 1: Multi-Modal Retrieval
Graph-based knowledge retrieval combining entity/relation extraction with vector search across 5 modes (local, global, hybrid, mix, naive).

### Feature 2: Pluggable Storage Backends
Supports multiple storage backends for different deployment scenarios — from file-based development to production PostgreSQL/Neo4j/Redis.

### Feature 3: Knowledge Graph WebUI
React-based visualization of the knowledge graph with interactive query testing.

## 8. Non-Functional Requirements

- **Performance:** Sub-5-second query response time for typical queries
- **Security:** JWT authentication, API key support, no secrets in source
- **Accessibility:** Standard web accessibility for WebUI

## 9. Open Questions

- Production URL and domain for OKD environments
- Specific performance benchmarks and SLA targets
- Monitoring and alerting strategy for production

## 10. Revision History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2026-02-10 | 0.1.0 | peterpawluk | Initial draft from /add:init interview |
