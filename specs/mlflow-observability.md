# Spec: MLflow Observability

**Version:** 0.1.0
**Created:** 2026-02-19
**PRD Reference:** docs/prd.md
**Status:** Draft

## 1. Overview

Add full MLflow observability to LightRAG — tracing spans for every pipeline step (LLM calls, queries, document ingestion, entity extraction, merging), metrics logging, artifact capture (retrieved contexts, knowledge graph data), and MLflow Evaluate support for comparing retrieval configurations. Integration is optional, activated via environment variables, and never blocks LightRAG operations.

### User Stories

- As a **LightRAG operator**, I want full pipeline observability via MLflow so I can debug retrieval quality issues and monitor production performance.
- As an **ML engineer**, I want to track RAG experiments across different models, embeddings, and retrieval modes so I can find the best configuration using MLflow Evaluate.

## 2. Acceptance Criteria

| ID | Criterion | Priority |
|----|-----------|----------|
| AC-001 | MLflow is an optional dependency — LightRAG works without it installed | Must |
| AC-002 | Integration activates via environment variables (`MLFLOW_TRACKING_URI`, `MLFLOW_EXPERIMENT_NAME`) | Must |
| AC-003 | Every LLM call gets a trace span with: prompt, response, tokens, latency, cache hit/miss | Must |
| AC-004 | Every query (`aquery`) gets a parent span with child spans for retrieval, reranking, and LLM generation | Must |
| AC-005 | Every document ingestion (`ainsert`) gets a parent span with child spans for chunking, extraction, and merging | Must |
| AC-006 | Query parameters logged as span attributes (mode, top_k, chunk_top_k, model, etc.) | Must |
| AC-007 | Retrieved entities/relations and knowledge graph context logged as artifacts | Should |
| AC-008 | Existing Langfuse integration continues to work alongside MLflow (not either/or) | Must |
| AC-009 | User identity captured in traces — JWT username when available, fallback to env var or API key | Must |
| AC-010 | MLflow Evaluate support for comparing retrieval modes/models | Should |
| AC-011 | Pre-built MLflow dashboard/view configuration shipped with the project | Should |
| AC-012 | Works with remote MLflow tracking server (auth token support via `MLFLOW_TRACKING_TOKEN`) | Must |
| AC-013 | When MLflow server is unreachable: log warning, disable tracing, retry connection periodically (~60s) | Must |
| AC-014 | When MLflow is not installed: feature silently disabled, no import errors | Must |
| AC-015 | When trace export fails mid-request: request completes normally, trace data lost (non-blocking) | Must |

## 3. User Test Cases

### TC-001: Auto-Trace Happy Path

**Precondition:** MLflow server running, `MLFLOW_TRACKING_URI` set in `.env`
**Steps:**
1. Start LightRAG server with MLflow env vars configured
2. Send a query via API (`POST /query` with mode=hybrid)
3. Open MLflow UI
**Expected Result:** Trace visible in MLflow UI with parent query span, child spans for retrieval/reranking/LLM, user identity tag, latency metrics
**Maps to:** AC-003, AC-004, AC-006, AC-009

### TC-002: Document Ingestion Tracing

**Precondition:** MLflow server running, `MLFLOW_TRACKING_URI` set
**Steps:**
1. Insert a document via API (`POST /documents/text`)
2. Open MLflow UI
**Expected Result:** Trace with parent ingestion span, child spans for chunking, entity extraction, merge operations, with document metadata
**Maps to:** AC-005

### TC-003: Graceful Degradation — MLflow Unavailable

**Precondition:** `MLFLOW_TRACKING_URI` set but server is down
**Steps:**
1. Start LightRAG server
2. Send a query
3. Check logs
**Expected Result:** Warning logged at startup, query succeeds normally, retry attempts logged every ~60s
**Maps to:** AC-013, AC-015

### TC-004: MLflow Not Installed

**Precondition:** `mlflow` package not in environment, `MLFLOW_TRACKING_URI` set
**Steps:**
1. Start LightRAG server
2. Send a query
**Expected Result:** No import errors, debug log "MLflow not available", query works normally
**Maps to:** AC-001, AC-014

### TC-005: User Identity in Traces

**Precondition:** MLflow running, JWT auth enabled with `AUTH_ACCOUNTS`
**Steps:**
1. Authenticate and get JWT token
2. Send query with JWT token
3. Check trace in MLflow UI
**Expected Result:** Trace has `user` attribute set to JWT username
**Maps to:** AC-009

### TC-006: MLflow Evaluate Comparison

**Precondition:** MLflow running, documents ingested
**Steps:**
1. Run the same query across modes (local, global, hybrid)
2. Use MLflow Evaluate to compare results
**Expected Result:** Comparison view in MLflow UI showing per-mode metrics (latency, token usage, retrieval counts)
**Maps to:** AC-010

## 4. Data Model

### MLflow Trace Structure

| Span | Parent | Attributes |
|------|--------|------------|
| `lightrag.query` | root | mode, top_k, chunk_top_k, user, query_text |
| `lightrag.query.retrieval` | query | entities_found, relations_found, chunks_found |
| `lightrag.query.rerank` | query | reranker_model, items_reranked |
| `lightrag.query.llm` | query | model, tokens_in, tokens_out, cache_hit |
| `lightrag.insert` | root | doc_count, chunk_count, user |
| `lightrag.insert.chunking` | insert | chunks_created |
| `lightrag.insert.extraction` | insert | entities_extracted, relations_extracted |
| `lightrag.insert.merge` | insert | nodes_merged, edges_merged |
| `lightrag.llm_call` | varies | prompt_hash, model, tokens, latency_ms, cache_hit |

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MLFLOW_TRACKING_URI` | Yes (to enable) | — | MLflow server URL |
| `MLFLOW_EXPERIMENT_NAME` | No | `lightrag` | Experiment name |
| `MLFLOW_TRACKING_TOKEN` | No | — | Auth token for remote server |
| `MLFLOW_USER` | No | — | Fallback user identity |
| `MLFLOW_RETRY_INTERVAL` | No | `60` | Seconds between reconnection attempts |
| `MLFLOW_LOG_ARTIFACTS` | No | `true` | Enable/disable artifact logging |

## 5. API Contract

No new API endpoints. Integration is transparent — existing query and insert APIs gain tracing automatically.

## 6. Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| MLflow not installed | Silent no-op, debug log |
| MLflow server unreachable at startup | Warning log, periodic retry every N seconds |
| MLflow server goes down mid-session | Current trace lost, warning logged, retry starts |
| MLflow server comes back after retry | Tracing resumes automatically |
| Very large artifact (huge KG context) | Truncate to configurable max size before logging |
| Concurrent queries from multiple users | Each trace has its own user identity, no cross-contamination |
| Streaming query response | Parent span stays open until stream completes |
| Both Langfuse and MLflow enabled | Both work independently, no conflict |

## 7. Dependencies

- `mlflow` — optional dependency in `pyproject.toml` (new extra: `[mlflow]`)
- Remote MLflow server (for production use)
- Existing auth system (`lightrag/api/`) for JWT username extraction
