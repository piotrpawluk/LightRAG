# Implementation Plan: Excel Tools

**Spec Version**: 0.1.0
**Spec**: specs/excel-tools.md
**Created**: 2026-03-06
**Team Size**: Solo
**Estimated Duration**: 4-5 days

## Overview

Add a "Tools" tab to the LightRAG WebUI where users upload Excel files, define them as LLM-callable tools with searchable columns, and have the LLM invoke those tools during RAG queries. Tool definitions and data persist in Redis. Search combines similarity + full-text matching.

## Acceptance Criteria Analysis

### AC-001: Tools tab visible in WebUI
- **Complexity**: Simple
- **Tasks**: Add tab trigger to SiteHeader.tsx, add TabsContent to App.tsx, create skeleton component
- **Pattern**: Follow existing tabs (documents, knowledge-graph, retrieval, api)

### AC-002–AC-007: Upload Excel, preview columns, define tool metadata
- **Complexity**: Medium
- **Tasks**: File upload endpoint, Excel parsing, column preview, tool creation form
- **Dependencies**: openpyxl for Excel parsing, existing FileUploader component

### AC-008: Persist in Redis
- **Complexity**: Medium
- **Tasks**: Redis storage for tool definitions + row data, key schema design
- **Pattern**: Follow RedisKVStorage patterns in kg/redis_impl.py

### AC-009–AC-010: List and delete tools
- **Complexity**: Simple
- **Tasks**: GET /tools and DELETE /tools/{tool_id} endpoints, UI list with delete

### AC-011: LLM receives tool definitions with every query
- **Complexity**: Complex
- **Tasks**: Load tools from Redis, format as LLM tool/function schemas, inject into query flow
- **Risk**: LLM providers handle tool-calling differently. Start with OpenAI-compatible format.

### AC-012–AC-014: Tool execution with similarity + full-text search
- **Complexity**: Complex
- **Tasks**: Embed search-by column values, build search index, combine similarity + text matching, return rows to LLM
- **Dependencies**: Embedding function from LightRAG instance

### AC-015–AC-017: Validation (duplicate name, invalid format, empty file)
- **Complexity**: Simple
- **Tasks**: Backend validation + frontend error display

### AC-018: Persist across restarts
- **Complexity**: Covered by AC-008 (Redis storage)

## Implementation Phases

### Phase 0: Preparation & Data Layer (0.5 day)

| Task ID | Description | Effort | Dependencies | AC |
|---------|-------------|--------|--------------|-----|
| TASK-001 | Design Redis key schema for tools | 30min | — | AC-008 |
| TASK-002 | Create `lightrag/tools/excel_tool_manager.py` — ToolDefinition dataclass, Redis CRUD operations | 2h | TASK-001 | AC-008, AC-018 |
| TASK-003 | Add `openpyxl` dependency to pyproject.toml | 15min | — | AC-002 |

**Redis Key Schema:**
```
{workspace}:tools:index              → SET of tool_ids
{workspace}:tools:{tool_id}:meta     → HASH {name, description, created_at, row_count}
{workspace}:tools:{tool_id}:params   → JSON [{column_name, param_name, param_description}, ...]
{workspace}:tools:{tool_id}:data     → JSON {columns, search_columns, rows}
{workspace}:tools:{tool_id}:embeddings → JSON {column_name: [[emb1], [emb2], ...]}
```

**Temp upload storage:**
```
{workspace}:tools:upload:{file_id}   → JSON {columns, rows} (TTL: 30min)
```

### Phase 1: Backend API (1 day)

| Task ID | Description | Effort | Dependencies | AC |
|---------|-------------|--------|--------------|-----|
| TASK-004 | Create `lightrag/api/routers/tools_routes.py` — router factory following existing pattern | 30min | — | — |
| TASK-005 | POST /tools/upload — accept Excel file, parse with openpyxl, extract columns, store temp in Redis, return columns + file_id | 2h | TASK-002, TASK-003 | AC-002, AC-003, AC-016, AC-017 |
| TASK-006 | POST /tools — create tool from file_id + metadata, validate unique name, persist to Redis | 1.5h | TASK-002, TASK-005 | AC-004–AC-008, AC-015 |
| TASK-007 | GET /tools — list all tools from Redis index | 30min | TASK-002 | AC-009 |
| TASK-008 | DELETE /tools/{tool_id} — remove tool + data + embeddings from Redis | 30min | TASK-002 | AC-010 |
| TASK-009 | Register tools router in lightrag_server.py | 15min | TASK-004 | AC-001 |

### Phase 2: Search & Embedding (1 day)

| Task ID | Description | Effort | Dependencies | AC |
|---------|-------------|--------|--------------|-----|
| TASK-010 | On tool creation, embed all search-by column values using LightRAG's embedding function, store embeddings in Redis | 2h | TASK-006 | AC-012 |
| TASK-011 | POST /tools/{tool_id}/search — similarity search (cosine on embeddings) + full-text search (substring match) on search-by columns, merge results, return top-k rows | 3h | TASK-010 | AC-012, AC-013, AC-014 |
| TASK-012 | Add search method to ExcelToolManager that combines both search strategies with deduplication | 1h | TASK-011 | AC-012 |

**Search Strategy:**
1. Embed the query parameter values using the same embedding function
2. Cosine similarity against stored column embeddings → top-k candidates
3. Full-text substring match on raw column values → additional candidates
4. Merge, deduplicate by row index, sort by relevance score
5. Return top 10 rows as list of dicts

### Phase 3: LLM Tool Integration (1 day)

| Task ID | Description | Effort | Dependencies | AC |
|---------|-------------|--------|--------------|-----|
| TASK-013 | Create tool schema generator — convert ToolDefinition to OpenAI-compatible function/tool JSON schema | 1h | TASK-002 | AC-011 |
| TASK-014 | Modify query flow in `operate.py` to load tool definitions and pass to LLM | 2h | TASK-013 | AC-011 |
| TASK-015 | Add tool-call handling — detect when LLM calls a tool, execute search, return results back to LLM for final response | 3h | TASK-011, TASK-014 | AC-011, AC-014 |

**Integration Point:**
In `operate.py`'s `kg_query()` function, after building the context:
1. Load all tool definitions from Redis via ExcelToolManager
2. Convert to OpenAI function-calling format
3. Pass `tools` parameter to LLM call
4. If LLM response contains tool calls, execute them via ExcelToolManager.search()
5. Feed tool results back into a second LLM call for final answer
6. If no tool calls, return response as normal

**LLM Provider Considerations:**
- OpenAI: native `tools` parameter support
- Anthropic: native `tools` parameter support
- Ollama: tool support varies by model, pass via `tools` parameter
- Bedrock: provider-specific format adaptation needed
- **Initial scope**: OpenAI-compatible format only. Other providers follow same pattern.

### Phase 4: Frontend — Tools Tab (1 day)

| Task ID | Description | Effort | Dependencies | AC |
|---------|-------------|--------|--------------|-----|
| TASK-016 | Add "tools" tab to App.tsx and SiteHeader.tsx, add i18n keys to en.json | 30min | — | AC-001 |
| TASK-017 | Create `lightrag_webui/src/features/ExcelTools.tsx` — empty state, tool list, upload button | 1.5h | TASK-016 | AC-001, AC-009 |
| TASK-018 | Add API methods to `lightrag.ts` — uploadToolFile, createTool, listTools, deleteTool | 1h | TASK-004–TASK-008 | — |
| TASK-019 | Implement file upload flow — use existing FileUploader component, call uploadToolFile, show column names | 1.5h | TASK-017, TASK-018 | AC-002, AC-003 |
| TASK-020 | Implement tool creation form — column checkboxes, name/description inputs, param name/description per column, submit | 2h | TASK-019 | AC-004–AC-007 |
| TASK-021 | Implement tool list with delete — card/table layout, delete with confirmation dialog | 1h | TASK-017, TASK-018 | AC-009, AC-010 |
| TASK-022 | Error handling — toast notifications for validation errors (invalid format, duplicate name, empty file) | 30min | TASK-019, TASK-020 | AC-015–AC-017 |

### Phase 5: Testing & Polish (0.5 day)

| Task ID | Description | Effort | Dependencies | AC |
|---------|-------------|--------|--------------|-----|
| TASK-023 | Write unit tests for ExcelToolManager — CRUD, Redis operations, search | 2h | TASK-002, TASK-012 | All |
| TASK-024 | Write unit tests for tools API endpoints — upload, create, list, delete, validation | 1h | TASK-004–TASK-008 | AC-015–AC-017 |
| TASK-025 | Write integration test for tool-calling query flow — mock LLM, verify tool invocation and result handling | 1.5h | TASK-015 | AC-011–AC-014 |
| TASK-026 | Manual end-to-end testing and bug fixes | 1h | All | All |

## Effort Summary

| Phase | Estimated Hours | Days (solo) |
|-------|-----------------|-------------|
| Phase 0: Preparation & Data Layer | 2.75h | 0.5 |
| Phase 1: Backend API | 5.25h | 1 |
| Phase 2: Search & Embedding | 6h | 1 |
| Phase 3: LLM Tool Integration | 6h | 1 |
| Phase 4: Frontend — Tools Tab | 8h | 1 |
| Phase 5: Testing & Polish | 5.5h | 0.5 |
| **Total** | **33.5h** | **5 days** |

## Dependencies

### External Dependencies
- `openpyxl` — Excel file parsing (new dependency)
- Redis — already in use, no new infrastructure
- LLM provider with tool/function calling support

### Internal Dependencies
- LightRAG embedding function (reuse existing)
- Redis connection via existing RedisKVStorage patterns
- FileUploader component (reuse existing)
- Query flow in operate.py (modification required)

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| LLM provider doesn't support tool calling | Medium | High | Start with OpenAI-compatible; fallback to prompt-based tool injection |
| Large Excel files cause memory/performance issues | Medium | Medium | Limit file size, warn on >10k rows, paginate Redis storage |
| Embedding all column values is slow | Low | Medium | Batch embedding calls, embed on creation (not query time) |
| Tool-calling loop (LLM keeps calling tools) | Low | Medium | Limit to 1 tool-call round per query |
| Redis key conflicts with existing data | Low | Low | Use `tools:` namespace prefix |

## Key Design Decisions

1. **Two-step upload flow**: Upload returns column names → user configures tool → create. This avoids re-uploading on form errors.

2. **Pre-computed embeddings**: Column values are embedded at tool creation time, not query time. This trades storage for query latency.

3. **Single tool-call round**: LLM gets one chance to call tools per query. Results are injected and a final response generated. No recursive tool calling.

4. **OpenAI-compatible tool format**: Use OpenAI's function-calling JSON schema as the standard. Other providers adapt from this.

5. **First sheet only**: For multi-sheet Excel files, only the first sheet is processed. Document this in the UI.

## File Changes

### New Files
- `lightrag/tools/__init__.py`
- `lightrag/tools/excel_tool_manager.py` — core tool management + search logic
- `lightrag/api/routers/tools_routes.py` — API endpoints
- `lightrag_webui/src/features/ExcelTools.tsx` — Tools tab component
- `tests/test_excel_tools.py` — unit + integration tests

### Modified Files
- `lightrag/api/lightrag_server.py` — register tools router
- `lightrag/operate.py` — inject tools into query flow, handle tool calls
- `lightrag_webui/src/App.tsx` — add Tools tab
- `lightrag_webui/src/features/SiteHeader.tsx` — add Tools tab trigger
- `lightrag_webui/src/api/lightrag.ts` — add tool API methods
- `lightrag_webui/src/locales/en.json` — add i18n keys
- `lightrag_webui/src/stores/settings.ts` — add tools-related state (if needed)
- `pyproject.toml` — add openpyxl dependency

## Spec Traceability

| AC | Tasks | Phase |
|----|-------|-------|
| AC-001 | TASK-009, TASK-016, TASK-017 | 1, 4 |
| AC-002 | TASK-003, TASK-005, TASK-019 | 0, 1, 4 |
| AC-003 | TASK-005, TASK-019 | 1, 4 |
| AC-004 | TASK-006, TASK-020 | 1, 4 |
| AC-005 | TASK-006, TASK-020 | 1, 4 |
| AC-006 | TASK-006, TASK-020 | 1, 4 |
| AC-007 | TASK-006, TASK-020 | 1, 4 |
| AC-008 | TASK-001, TASK-002, TASK-006 | 0, 1 |
| AC-009 | TASK-007, TASK-017, TASK-021 | 1, 4 |
| AC-010 | TASK-008, TASK-021 | 1, 4 |
| AC-011 | TASK-013, TASK-014, TASK-015 | 3 |
| AC-012 | TASK-010, TASK-011, TASK-012 | 2 |
| AC-013 | TASK-011 | 2 |
| AC-014 | TASK-011, TASK-015 | 2, 3 |
| AC-015 | TASK-006, TASK-022 | 1, 4 |
| AC-016 | TASK-005, TASK-022 | 1, 4 |
| AC-017 | TASK-005, TASK-022 | 1, 4 |
| AC-018 | TASK-002 | 0 |

## Next Steps

1. Review and approve this plan
2. Begin Phase 0: Add openpyxl dependency, design Redis schema, build ExcelToolManager
3. Run `/add:tdd-cycle specs/excel-tools.md` to execute with TDD
