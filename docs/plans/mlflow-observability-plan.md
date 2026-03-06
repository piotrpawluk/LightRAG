# Implementation Plan: MLflow Observability

**Spec Version**: 0.1.0
**Spec**: specs/mlflow-observability.md
**Created**: 2026-02-19
**Team Size**: Solo
**Maturity**: Beta
**Estimated Duration**: 3-4 days

## Overview

Add provider-agnostic MLflow tracing to LightRAG — every LLM call, query, and document ingestion gets traced with spans, attributes, and metrics. The integration is optional (activated via env vars), non-blocking (tracing failures never affect requests), and coexists with the existing Langfuse integration.

## Objectives

- Full pipeline observability: queries, inserts, LLM calls, extraction, merging
- Zero impact on existing functionality when MLflow is not configured
- Graceful degradation when MLflow server is unreachable
- User identity propagation via `contextvars` (no signature changes)
- MLflow Evaluate support for comparing retrieval configurations

## Success Criteria

- All 15 acceptance criteria implemented and tested
- Existing test suite passes unchanged (regression-free)
- Code coverage >= 80% for new module
- All quality gates passing (ruff, type checks)
- No import errors when `mlflow` package is absent

---

## Acceptance Criteria Analysis

### AC-001: Optional dependency (Must)
- **Complexity**: Simple
- **Effort**: 30min
- **Tasks**: TASK-002 (pyproject.toml extra), TASK-001 (try/except import in core module)
- **Testing**: TASK-014 (mock absent import)

### AC-002: Env-var activation (Must)
- **Complexity**: Simple
- **Effort**: 1h
- **Tasks**: TASK-001 (config reader), TASK-003 (env.example)
- **Testing**: TASK-014 (env var presence/absence)

### AC-003: LLM call trace spans (Must)
- **Complexity**: Medium
- **Effort**: 2h
- **Tasks**: TASK-006 (instrument `use_llm_func_with_cache` in utils.py), TASK-007 (instrument direct LLM calls in operate.py)
- **Dependencies**: TASK-001 (core module)
- **Testing**: TASK-015 (mock spans, verify attributes)

### AC-004: Query parent+child spans (Must)
- **Complexity**: Medium
- **Effort**: 3h
- **Tasks**: TASK-005 (`aquery_llm` parent span), TASK-007 (kg_query/naive_query child spans)
- **Dependencies**: TASK-001
- **Testing**: TASK-015

### AC-005: Insert parent+child spans (Must)
- **Complexity**: Medium
- **Effort**: 2h
- **Tasks**: TASK-005 (`ainsert` parent span), TASK-007 (extract_entities, merge child spans)
- **Dependencies**: TASK-001
- **Testing**: TASK-015

### AC-006: Query params as span attributes (Must)
- **Complexity**: Simple
- **Effort**: 30min
- **Tasks**: TASK-005 (pass params dict to trace_query)
- **Testing**: TASK-015

### AC-007: Artifact logging (Should)
- **Complexity**: Medium
- **Effort**: 2h
- **Tasks**: TASK-007 (log context_result raw_data as artifacts in kg_query)
- **Dependencies**: TASK-001
- **Testing**: TASK-016

### AC-008: Langfuse coexistence (Must)
- **Complexity**: Simple
- **Effort**: 30min
- **Tasks**: No code needed — MLflow instrumentation is at different call sites (provider-agnostic wrappers vs OpenAI client swap)
- **Testing**: TASK-017 (enable both, verify no conflict)

### AC-009: User identity in traces (Must)
- **Complexity**: Medium
- **Effort**: 2h
- **Tasks**: TASK-001 (contextvars), TASK-004 (API middleware), TASK-008 (route fallbacks)
- **Testing**: TASK-015

### AC-010: MLflow Evaluate support (Should)
- **Complexity**: Medium
- **Effort**: 2h
- **Tasks**: TASK-010 (helper functions/docs for comparing modes)
- **Testing**: TASK-016

### AC-011: Dashboard config (Should)
- **Complexity**: Simple
- **Effort**: 1h
- **Tasks**: TASK-009 (JSON config file)

### AC-012: Remote server + auth token (Must)
- **Complexity**: Simple
- **Effort**: 30min
- **Tasks**: TASK-001 (MLFLOW_TRACKING_TOKEN env var handling)
- **Testing**: TASK-014

### AC-013: Retry on unreachable server (Must)
- **Complexity**: Medium
- **Effort**: 2h
- **Tasks**: TASK-001 (background retry loop)
- **Testing**: TASK-014

### AC-014: Silent no-op when not installed (Must)
- **Complexity**: Simple
- **Effort**: 30min (covered by TASK-001 design)
- **Testing**: TASK-014

### AC-015: Non-blocking trace failures (Must)
- **Complexity**: Simple
- **Effort**: 30min (all span context managers catch exceptions)
- **Testing**: TASK-014

---

## Implementation Phases

### Phase 0: Preparation (0.5 day)

| Task ID | Description | AC | Effort | Dependencies |
|---------|-------------|-----|--------|--------------|
| TASK-001 | Create `lightrag/mlflow_integration.py` — client singleton, `contextvars`, span context managers (`trace_query`, `trace_insert`, `trace_llm_call`, `trace_operation`), `TracedAsyncIterator`, retry loop, no-op fallbacks | AC-001,002,012,013,014,015 | 3h | None |
| TASK-002 | Add `mlflow = ["mlflow>=2.12.0"]` extra to `pyproject.toml` | AC-001 | 15min | None |
| TASK-003 | Add MLflow env vars section to `env.example` | AC-002 | 15min | None |

**Phase Duration**: 0.5 day
**Blockers**: None

### Phase 1: Core Instrumentation (1.5 days)

| Task ID | Description | AC | Effort | Dependencies |
|---------|-------------|-----|--------|--------------|
| TASK-004 | Instrument `combined_dependency()` in `lightrag/api/utils_api.py` — capture JWT username into `mlflow_user_context` ContextVar | AC-009 | 1h | TASK-001 |
| TASK-005 | Add parent spans to `lightrag/lightrag.py` — `aquery_llm()` gets `trace_query` span, `ainsert()` gets `trace_insert` span | AC-004,005,006 | 2h | TASK-001 |
| TASK-006 | Add LLM call spans to `lightrag/utils.py` — instrument `use_llm_func_with_cache()` with `trace_llm_call` for both cache hit and cache miss paths | AC-003 | 1.5h | TASK-001 |
| TASK-007 | Add child spans to `lightrag/operate.py` — instrument `kg_query()` (keyword extraction, context building, direct LLM call), `naive_query()` (vector search, LLM call), `extract_entities()`, `merge_nodes_and_edges()` | AC-003,004,005,007 | 3h | TASK-001 |
| TASK-008 | Add user identity fallback in route handlers (`query_routes.py`, `document_routes.py`) for non-JWT auth paths (API key, anonymous) | AC-009 | 1h | TASK-004 |

**Phase Duration**: 1.5 days
**Blockers**: TASK-001 must be complete before Phase 1

### Phase 2: Extras & Polish (0.5 day)

| Task ID | Description | AC | Effort | Dependencies |
|---------|-------------|-----|--------|--------------|
| TASK-009 | Create `docs/mlflow-dashboard.json` — pre-built MLflow view configuration for LightRAG traces | AC-011 | 1h | None |
| TASK-010 | Add MLflow Evaluate helper utilities or documentation for comparing retrieval modes | AC-010 | 1.5h | TASK-005, TASK-007 |

**Phase Duration**: 0.5 day

### Phase 3: Testing (1 day)

| Task ID | Description | AC | Effort | Dependencies |
|---------|-------------|-----|--------|--------------|
| TASK-014 | Unit tests: graceful degradation — MLflow not installed (mock import), env vars not set, server unreachable, retry logic, non-blocking failures | AC-001,002,012,013,014,015 | 2h | TASK-001 |
| TASK-015 | Unit tests: span creation — verify spans created with correct attributes for query/insert/LLM calls, user identity propagation, streaming `TracedAsyncIterator` lifecycle | AC-003,004,005,006,009 | 3h | TASK-005,006,007 |
| TASK-016 | Unit tests: artifact logging and MLflow Evaluate helpers | AC-007,010 | 1h | TASK-007,010 |
| TASK-017 | Regression: run existing test suite, verify no behavior changes when MLflow not configured; verify Langfuse+MLflow coexistence | AC-008 | 1h | All implementation tasks |

**Phase Duration**: 1 day
**Blockers**: Implementation phases must be complete

---

## Effort Summary

| Phase | Estimated Hours | Days (solo) |
|-------|-----------------|-------------|
| Phase 0: Preparation | 3.5 | 0.5 |
| Phase 1: Core Instrumentation | 8.5 | 1.5 |
| Phase 2: Extras & Polish | 2.5 | 0.5 |
| Phase 3: Testing | 7 | 1 |
| **Total** | **21.5** | **3.5** |

---

## Key Architecture Decisions

### 1. `contextvars` for user identity and trace context
No signature changes to `aquery()`, `ainsert()`, or any existing function. Set in API middleware, read anywhere downstream. This is critical for non-invasive integration.

### 2. Provider-agnostic instrumentation
Unlike Langfuse (which swaps the OpenAI client at `lightrag/llm/openai.py:40-64`), MLflow uses wrapper/decorator patterns at call sites. Works with all LLM providers (OpenAI, Ollama, Anthropic, Bedrock, etc.).

### 3. Multiple hook points required
`use_llm_func_with_cache()` covers entity extraction/summary LLM calls, but direct LLM calls in `kg_query()` (~line 3213), `naive_query()`, and `extract_keywords_only()` bypass it and must also be instrumented.

### 4. Streaming: `TracedAsyncIterator` wrapper
When `QueryParam.stream=True`, wrap the `AsyncIterator` with a traced proxy that keeps the span open until the stream completes or errors.

### 5. Lazy import in utils.py
`lightrag/utils.py` is imported before `lightrag/mlflow_integration.py` in the module graph. Use a lazy `_get_mf_trace()` helper to avoid circular imports.

---

## Files to Create

| File | Purpose | Tasks |
|------|---------|-------|
| `lightrag/mlflow_integration.py` | Core module: singleton, contextvars, spans, retry, no-ops | TASK-001 |
| `docs/mlflow-dashboard.json` | Pre-built MLflow dashboard config | TASK-009 |
| `tests/test_mlflow_integration.py` | Unit tests for MLflow integration | TASK-014,015,016,017 |

## Files to Modify

| File | Change | Tasks | Key Locations |
|------|--------|-------|---------------|
| `pyproject.toml` | Add `mlflow` extra | TASK-002 | After `observability` extra (~line 153) |
| `env.example` | Add MLflow env vars section | TASK-003 | After Langfuse section (~line 553) |
| `lightrag/api/utils_api.py` | Capture JWT username into contextvars | TASK-004 | `combined_dependency()` line 128 |
| `lightrag/lightrag.py` | Parent spans on `aquery_llm()` and `ainsert()` | TASK-005 | `aquery_llm()` ~line 2740, `ainsert()` ~line 1175 |
| `lightrag/utils.py` | LLM call spans in `use_llm_func_with_cache()` | TASK-006 | Cache hit ~line 2146, LLM call ~line 2165, no-cache ~line 2200 |
| `lightrag/operate.py` | Child spans on query phases, extraction, merge | TASK-007 | `kg_query()` ~line 3024, `naive_query()` ~line 4901, `extract_entities()` ~line 2777, `merge_nodes_and_edges()` ~line 2407 |
| `lightrag/api/routers/query_routes.py` | User identity fallback | TASK-008 | Request handlers |
| `lightrag/api/routers/document_routes.py` | User identity fallback | TASK-008 | Request handlers |

## Existing Utilities to Reuse

- **Langfuse pattern** (`lightrag/llm/openai.py:40-64`): env-var activation, try/except import — use as reference
- **`statistic_data` dict** (`lightrag/utils.py:303`): existing LLM call/cache counters — forward as MLflow metrics
- **`_log_timing()` function** (`lightrag/lightrag.py:130-133`): existing timing infrastructure — complement with span durations
- **`CacheData` dataclass** (`lightrag/utils.py:1546`): cache entry metadata — use for span attributes
- **`QueryParam` / `QueryResult`** (`lightrag/base.py`): query config and result metadata — log as span attributes
- **`combined_dependency()`** (`lightrag/api/utils_api.py:109`): auth handler — extend to set contextvars

---

## Dependencies

### External Dependencies
- `mlflow>=2.12.0` — optional, installed via `pip install lightrag-hku[mlflow]`
- Remote MLflow tracking server (for production use)

### Internal Dependencies
- Existing auth system (`lightrag/api/auth.py`) for JWT username extraction
- `lightrag/utils.py` `use_llm_func_with_cache()` for centralized LLM call instrumentation

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Circular import between utils.py and mlflow_integration.py | Medium | High | Use lazy import pattern (`_get_mf_trace()` helper) |
| MLflow API changes between versions | Low | Medium | Pin minimum version `>=2.12.0`, use stable trace API |
| Performance overhead from tracing | Low | Medium | All span operations are fire-and-forget, no-op when disabled |
| Indentation errors when wrapping existing code with `async with` | Medium | Medium | Use explicit `__aenter__`/`__aexit__` to avoid re-indenting large blocks |
| Trace context leaking between concurrent requests | Low | High | Use `contextvars` which are coroutine-safe by design |
| Breaking existing Langfuse integration | Low | High | MLflow instruments at different call sites (provider-agnostic); verify coexistence in tests |

---

## Testing Strategy

### Unit Tests (TASK-014, 015, 016)
- Mock `mlflow` module entirely — no real server needed
- Verify span creation calls with correct names and attributes
- Verify graceful no-op when `mlflow` not installed (mock `ImportError`)
- Verify graceful no-op when `MLFLOW_TRACKING_URI` not set
- Verify retry logic with mock connection failures
- Verify `TracedAsyncIterator` span lifecycle
- Verify user identity propagation from contextvars

### Regression (TASK-017)
- Run full existing test suite with MLflow NOT configured
- Verify zero behavior changes
- Enable both Langfuse and MLflow env vars (mocked), verify no conflict

### Manual Smoke Test (not automated)
- Start local MLflow server (`mlflow server`)
- Set `MLFLOW_TRACKING_URI=http://localhost:5000`
- Run queries and inserts
- Verify traces visible in MLflow UI with correct hierarchy

---

## Spec Traceability

| Task | Acceptance Criteria |
|------|-------------------|
| TASK-001 | AC-001, AC-002, AC-012, AC-013, AC-014, AC-015 |
| TASK-002 | AC-001 |
| TASK-003 | AC-002 |
| TASK-004 | AC-009 |
| TASK-005 | AC-004, AC-005, AC-006 |
| TASK-006 | AC-003 |
| TASK-007 | AC-003, AC-004, AC-005, AC-007 |
| TASK-008 | AC-009 |
| TASK-009 | AC-011 |
| TASK-010 | AC-010 |
| TASK-014 | AC-001, AC-002, AC-012, AC-013, AC-014, AC-015 |
| TASK-015 | AC-003, AC-004, AC-005, AC-006, AC-009 |
| TASK-016 | AC-007, AC-010 |
| TASK-017 | AC-008 |

---

## Implementation Order (Critical Path)

```
TASK-001 (core module)
  ├── TASK-002 (pyproject.toml)     ← can parallelize
  ├── TASK-003 (env.example)        ← can parallelize
  │
  ├── TASK-004 (API middleware)
  │     └── TASK-008 (route fallbacks)
  │
  ├── TASK-005 (lightrag.py spans)
  ├── TASK-006 (utils.py spans)
  ├── TASK-007 (operate.py spans)
  │
  ├── TASK-009 (dashboard config)   ← independent
  └── TASK-010 (evaluate helpers)   ← depends on TASK-005,007
        │
        └── TASK-014,015,016,017 (tests) ← all impl complete
```

**Longest critical path**: TASK-001 → TASK-007 → TASK-015 (~9h)

---

## Next Steps

1. Get approval of this plan
2. Begin Phase 0: Create core module, update pyproject.toml, env.example
3. Phase 1: Instrument all call sites
4. Phase 2: Dashboard and evaluate helpers
5. Phase 3: Write comprehensive tests
6. Run `/add:verify` for quality gates
