# Project Learnings — LightRAG

> **Tier 3: Project-Specific Knowledge**
>
> This file is maintained automatically by ADD agents. Entries are added at checkpoints
> (after verify, TDD cycles, deployments, away sessions) and reviewed during retrospectives.
>
> This is one of three knowledge tiers agents read before starting work:
> 1. **Tier 1: Plugin-Global** (`knowledge/global.md`) — universal ADD best practices
> 2. **Tier 2: User-Local** (`~/.claude/add/library.md`) — your cross-project wisdom
> 3. **Tier 3: Project-Specific** (this file) — discoveries specific to this project
>
> **Agents:** Read ALL three tiers before starting any task.
> **Humans:** Review with `/add:retro --agent-summary` or during full `/add:retro`.

## Technical Discoveries
<!-- Things learned about the tech stack, libraries, APIs, infrastructure -->
- 2026-02-10: Always call `await rag.initialize_storages()` after creating a LightRAG instance. Source: CLAUDE.md.
- 2026-02-10: Embedding models must be consistent across indexing and querying — changing models requires clearing vector storage. Source: CLAUDE.md.
- 2026-02-10: Ollama models default to 8k context; LightRAG requires 32k+. Configure via `llm_model_kwargs={"options": {"num_ctx": 32768}}`. Source: CLAUDE.md.
- 2026-02-10: Cannot wrap already-decorated embedding functions. Use `.func` to access the underlying function. Source: CLAUDE.md.
- 2026-02-10: `orjson` is used as an optional performance optimization for JSON serialization. Source: git log.
- 2026-02-10: Query handling separates embedding and keyword extraction with parallel execution for improved latency. Source: git log.

## Architecture Decisions
<!-- Decisions made and their rationale -->
- 2026-02-10: Pluggable storage backends via abstract base classes (BaseKVStorage, BaseVectorStorage, BaseGraphStorage, BaseDocStatusStorage). Source: CLAUDE.md.
- 2026-02-10: Workspace isolation per storage type (subdirectories for file-based, prefixes for collections, fields for relational DBs). Source: CLAUDE.md.

## What Worked
<!-- Patterns, approaches, tools that proved effective -->
- 2026-02-10: Async/await patterns throughout the codebase for consistent non-blocking I/O. Source: CLAUDE.md.
- 2026-02-10: Redis key prefix for multi-instance isolation. Source: git log.

## What Didn't Work
<!-- Patterns, approaches, tools that caused problems -->

## Agent Checkpoints
<!-- Automatic entries from verification, TDD cycles, deploys, away sessions -->
<!-- These are processed and archived during /add:retro -->

## Checkpoint: Post-TDD — 2026-06-16 — specs/resumable-ingestion.md (Cycle 1)
- **ACs covered:** AC-001 (per-chunk checkpoint write), AC-002 (resume skips checkpointed chunks), AC-003 (resumed union == clean run), AC-009 (no store ⇒ legacy path). AC-004/005/006/007/008/010 deferred to Cycle 2+ (pipeline/API/UI wiring).
- **RED phase:** 6 tests written; 5 failed (missing param + helpers), 1 passed immediately — the AC-009 backward-compat test, which asserts the *unchanged* legacy path, so passing-on-RED is correct, not a smell.
- **GREEN phase:** clean; `extract_entities` gained an optional `extraction_checkpoint: BaseKVStorage | None` param. Default None ⇒ zero behavior change for the live pipeline (it doesn't pass the store yet).
- **Patterns discovered:** (1) `extract_entities(chunks, global_config)` is directly unit-testable with an `AsyncMock` LLM; `llm_func.await_count` cleanly proves resume skips work. (2) Edge keys are `(src,tgt)` tuples — NOT JSON-serializable as object keys; checkpoint records store edges as `[[src,tgt], values]` and rebuild tuples on read (pure `_serialize/_deserialize_extraction_checkpoint` helpers). (3) `BaseKVStorage.filter_keys(keys)` returns the subset NOT yet stored — reuse it to compute the resume work-list.
- **Verify:** ruff clean on new code (3 pre-existing errors at operate.py:83/4011/4012 left untouched per minimal-scope); mypy clean on additions; 68-test extraction/chunking/doc-status regression green.

## Checkpoint: Post-TDD — 2026-06-16 — specs/resumable-ingestion.md (Cycle 2)
- **ACs covered:** AC-006 (new `KV_STORE_EXTRACTION_CHECKPOINT` namespace + `self.extraction_checkpoint` store), AC-001 live (pipeline writes checkpoints that survive a merge failure), AC-004 (cleared on PROCESSED), AC-005 core (`aclear_extraction_checkpoint(doc_ids)`). Deferred to Cycle 3+: PG DDL/migration for the namespace, the `from_scratch` API endpoint body, WebUI + Playwright.
- **GOTCHA (cost me a RED→GREEN iteration):** adding a KV store attribute in `LightRAG` is NOT enough — a storage is created in `__post_init__` but only *initialized* if added to BOTH explicit lists: the `for storage in (...)` loop in `initialize_storages()` (~lightrag.py:820) AND the `storages = [...]` list in `finalize_storages()` (~:844), plus the `_insert_done()` persist list (~:2381). Miss the init list → `StorageNotInitializedError` on first upsert. Four touch-points total for a new KV namespace: namespace.py constant, `__post_init__` instantiation, initialize_storages, finalize_storages (+ _insert_done for persistence).
- **GOTCHA:** JsonKVStorage.upsert enriches records with `_id`/`create_time`/`update_time` — never assert exact-dict equality on a stored record; assert the fields you care about. (Fixed an over-strict test, not the impl.)
- **Test harness:** tests/test_doc_status_chunk_preservation.py's `_build_rag` + `_deterministic_chunking` + dummy llm/embedding is the canonical way to drive the FULL offline pipeline (`apipeline_enqueue_documents` → `apipeline_process_enqueue_documents`); monkeypatch `lightrag_module.merge_nodes_and_edges` to force a post-extraction failure.
- **Verify:** 83-test regression green (incl. full-pipeline doc-status suite); ruff clean on changed files.

## Checkpoint: Post-TDD — 2026-06-16 — specs/resumable-ingestion.md (Cycle 3)
- **ACs covered:** AC-005 endpoint surface (`from_scratch` body on `POST /documents/reprocess_failed` → `rag.areprocess_documents_from_scratch(doc_ids)`: clears checkpoints + resets docs to PENDING) and AC-007 telemetry (`pipeline_phase` + `extracted_chunks` written into doc_status `metadata` at all four status-transition sites: PROCESSING/PROCESSED/extraction-failure/merge-failure). Deferred: PG DDL/migration for the namespace, AC-008 WebUI+Playwright, AC-010 perf.
- **GOTCHA (edit collision):** the pipeline has FOUR near-identical `doc_status.upsert({... "metadata": {...}})` blocks. The PROCESSED and merge-failure metadata sub-blocks are byte-identical (same 44-space indent, same start/end-time keys) → an Edit on the metadata alone is ambiguous. Disambiguate by anchoring on the unique discriminator line (`"status": DocStatus.PROCESSED,` + `"chunks_count": len(chunks),` vs `"chunks_count": failed_chunks_count,`). PROCESSING (only `processing_start_time`) and extraction-failure (shallower 40-space indent) are uniquely matchable on their own.
- **Pattern:** API routes are closures inside `create_document_routes(rag,...)` and aren't offline-testable without the FastAPI app (needs the `api` extra; `aiofiles` etc.). Put the real logic in an awaitable `rag` method, unit-test that, and keep the route a thin delegator. Validate the route file with `python -m py_compile` (don't import it — import pulls `aiofiles`).
- **Verify:** 86-test regression green; ruff clean on lightrag.py + document_routes.py + tests.

## Checkpoint: Post-TDD — 2026-06-16 — specs/resumable-ingestion.md (Cycle 4, WebUI / AC-008)
- **ACs covered:** AC-008 WebUI — API client `reprocessFailedDocuments({documentIds, fromScratch})` + pure `buildReprocessPayload`; pure `getResumeProgress(doc)` helper (`src/lib/documentResume.ts`); `ReprocessFromScratchDialog` (mirrors DeleteDocumentsDialog); DocumentManager selection-toolbar button + resume indicator under the status badge; en.json i18n. Playwright TC-003 scaffolded at tests/e2e/resumable-ingestion.spec.ts.
- **Strategy that worked:** push logic into PURE, framework-free helpers (`buildReprocessPayload`, `getResumeProgress`) and unit-test them with `bun:test` — fast, no DOM/axios. 13 bun tests pass. React components stay thin around the tested helpers.
- **ENV LIMITATION (be honest in reports):** in this workspace eslint can't run (`eslint.config.js` imports `@stylistic/eslint-plugin`, not in installed node_modules) and Playwright isn't installed. So frontend verification here = bun unit tests + `npx tsc --noEmit` (my files type-clean) + JSON parse. The Playwright spec is a documented SCAFFOLD, not a passing test — running it needs `bun add -d @playwright/test` + `bunx playwright install` + a served build. Don't claim E2E/lint pass when the tools aren't present.
- **GOTCHA:** `npx tsc --noEmit` already reports 2 PRE-EXISTING errors (FileUploader.tsx; a `resolveSharedRequest?.()` line in the original lightrag.test.ts) unrelated to this work — verify new errors are absent in YOUR files (grep tsc output by filename) rather than expecting a zero exit.
- **Resume metadata lives in `doc.metadata`** on the frontend (`DocStatusResponse.metadata` is `Record<string,any>`): read `metadata.extracted_chunks` / `metadata.pipeline_phase` and gate the indicator on `extracted < chunks_count` for processing/failed rows only.

## Checkpoint: Post-Verify — 2026-06-16 — specs/resumable-ingestion.md (deploy level)
- **Clean pass on feature code:** Gate 1 (ruff) clean on all changed/new files; Gate 3 backend 13 + frontend 13 tests pass, 75-test offline regression green; Gate 4.6 staged-secret scan clean (exit 0, nothing staged); Gate 3.5 SKIPPED (no `.add/cycles/*` RED/GREEN snapshots — TDD cycles were run without the snapshot tooling).
- **Gate 4 spec compliance: 9/10 ACs covered.** AC-001/002/003/004/005/006/007/008/009 each map to ≥1 passing test. **AC-010 (perf budget) NOT COVERED** — not implemented (nice-to-have). AC-006 satisfied on Redis (see [[redis-kv-backend]]); PG migration is N/A for this deployment.
- **Pre-existing debt (do not attribute to this feature):** `ruff` reports 3 errors in `lightrag/operate.py` (E402 at :83, F841 at :4011/:4012) that exist on HEAD and are outside the feature's changes. mypy/eslint full runs are noisy/unavailable in this workspace; verify feature files individually rather than expecting a clean global exit.

## Profile Update Candidates
<!-- Cross-project patterns flagged for promotion to ~/.claude/add/profile.md -->
<!-- Only promoted during /add:retro with human confirmation -->
