# Implementation Plan: Resumable Ingestion with Per-Chunk Extraction Checkpoints

**Spec Version:** 0.1.1 (specs/resumable-ingestion.md)
**UX:** specs/ux/resumable-ingestion-ux.md (APPROVED)
**Created:** 2026-06-16
**Team Size:** Solo
**Maturity:** beta
**Estimated Duration:** ~7–8 working days (≈49h + 15% contingency ≈ 56h)

## Overview

Persist each chunk's entity/relation extraction result to a new dedicated KV namespace as it completes, so a failed/interrupted ingestion resumes from the last extracted chunk instead of re-running all LLM extraction. Add a `from_scratch` option (API + WebUI) to discard the checkpoint and reprocess a document from the beginning.

## Objectives

- Durable per-chunk extraction checkpoint that survives crashes and works across all KV backends.
- Resume path that skips already-extracted chunks and produces a graph identical to a clean run.
- Explicit force-full (`from_scratch`) reprocess via the existing reprocess endpoint and a selection-based WebUI action.
- Zero behavioral change for installations/documents without checkpoint data (backward compatible).

## Success Criteria

- All 10 acceptance criteria implemented and covered by tests.
- Resume run for TC-001 invokes the LLM only for un-extracted chunks; resulting graph matches baseline.
- Backend coverage ≥ 80% (config threshold); `ruff`, `mypy`, WebUI `eslint`/`tsc` clean.
- Checkpoint write overhead < 5% on a ~200-chunk document (AC-010).

## Acceptance Criteria Analysis

| AC | Summary | Complexity | Primary Tasks |
|----|---------|-----------|---------------|
| AC-001 | Persist each chunk's extraction result before merge | Medium | TASK-006, TASK-007 |
| AC-002 | Resume skips already-extracted chunks | Complex | TASK-008, TASK-010 |
| AC-003 | Merge over union ⇒ graph identical to clean run | Medium | TASK-009, TASK-010 |
| AC-004 | Clear checkpoint on PROCESSED (+ on delete) | Simple–Medium | TASK-011, TASK-014, TASK-015 |
| AC-005 | `from_scratch` flag clears checkpoint + re-extracts all | Medium | TASK-013, TASK-015 |
| AC-006 | New KV namespace works on JSON/PG/Redis/Mongo | Medium | TASK-003, TASK-004, TASK-005 |
| AC-007 | Resume telemetry (phase + extracted/total) in doc_status & API | Medium | TASK-012, TASK-016 |
| AC-008 | WebUI resume indicator + selection-based reprocess-from-scratch | Medium | TASK-017–021 |
| AC-009 | Backward compatible (no checkpoint ⇒ full run) | Simple | TASK-008 (fallback), TASK-015 |
| AC-010 | < 5% checkpoint-write overhead on clean run | Medium | TASK-022 |

## Implementation Phases

### Phase 0: Preparation / De-risking spikes (~3h)

| Task ID | Description | Effort | Dependencies |
|---------|-------------|--------|--------------|
| TASK-001 (AC-006) | Confirm new-namespace registration per backend. JSON/Redis/Mongo auto-create by prefix/collection; PostgreSQL needs a `TABLES` DDL entry + `namespace_to_table_name()` mapping (`postgres_impl.py:6192`) + a migration following the `_migrate_create_full_entities_relations_tables` precedent (`postgres_impl.py:1585`). Document the exact change set. | 2h | Spec complete |
| TASK-002 (AC-001, AC-004) | Verify the serialized shape of `maybe_nodes`/`maybe_edges` returned by `_process_single_content` (`operate.py:2960-3119`) is JSON-safe, and that `doc_status.chunks_list` reliably enumerates chunk ids for later cleanup. | 1h | Spec complete |

**Blockers:** none. Output feeds Phase 1 storage tasks.

### Phase 1: Storage layer — new KV namespace (~4.25h)

| Task ID | Description | Effort | Dependencies |
|---------|-------------|--------|--------------|
| TASK-003 (AC-006) | Add `NameSpace.KV_STORE_EXTRACTION_CHECKPOINT = "extraction_checkpoint"` (`lightrag/namespace.py:7+`). | 15min | TASK-001 |
| TASK-004 (AC-006) | Instantiate `self.extraction_checkpoint: BaseKVStorage` in `LightRAG` alongside other KV stores (`lightrag.py:705-739`) and add it to `_insert_done()` persistence (`lightrag.py:2378-2407`). | 1h | TASK-003 |
| TASK-005 (AC-006) | ~~PostgreSQL: add `TABLES` DDL entry + `namespace_to_table_name` mapping + migration~~ **N/A — deployment uses Redis** (confirmed 2026-06-16). `RedisKVStorage` keys by generic `{prefix}:{workspace}_{namespace}`, so the new namespace works with no DDL/migration. JSON/Mongo likewise auto-handle it. PG migration only needed if a PG backend is later adopted. | — | done (Redis) |

### Phase 2: Checkpoint write (~5h)

| Task ID | Description | Effort | Dependencies |
|---------|-------------|--------|--------------|
| TASK-006 (AC-001) | In `extract_entities` (`operate.py:2912-3194`), after a chunk's extraction (and any gleaning) completes, upsert a checkpoint record `{full_doc_id, chunk_order_index, nodes, edges, created_at}` keyed by `chunk_id`. Write per-chunk so partial progress survives a later failure. | 3h | TASK-004 |
| TASK-007 (AC-001) | RED+GREEN tests: assert each completed chunk produces a checkpoint record with correct keys/content. | 2h | TASK-006 |

### Phase 3: Resume logic (~9h)

| Task ID | Description | Effort | Dependencies |
|---------|-------------|--------|--------------|
| TASK-008 (AC-002, AC-009) | Before extraction, load checkpoint entries for the document's chunk ids; build the extraction work-list from **only** un-checkpointed chunks. Missing checkpoint ⇒ cursor 0 (full run, backward compatible). Thread through `_process_extract_entities` (`lightrag.py:2357`) / `extract_entities`. | 4h | TASK-006 |
| TASK-009 (AC-003) | Feed the union of checkpointed + newly-extracted chunk results into `merge_nodes_and_edges` (`operate.py:2523`); confirm merge stays idempotent and order-independent. | 2h | TASK-008 |
| TASK-010 (AC-002, AC-003) | TC-001 tests: inject failure after N chunks, re-run, assert LLM invoked only for remaining chunks (instrument call count) and resulting graph is byte-equivalent to a clean run (build a deterministic graph-comparison helper). | 3h | TASK-009 |

### Phase 4: Lifecycle — clear, telemetry, from_scratch (~11.5h)

| Task ID | Description | Effort | Dependencies |
|---------|-------------|--------|--------------|
| TASK-011 (AC-004) | On transition to PROCESSED (`lightrag.py:2197-2220`), delete the document's checkpoint entries (using `chunks_list`). | 1.5h | TASK-008 |
| TASK-012 (AC-007) | Set `pipeline_phase` (`chunking`/`extraction`/`merge`) and `extracted_chunks` in `doc_status` metadata at each stage transition. | 2h | TASK-008 |
| TASK-013 (AC-005) | Add `LightRAG.aclear_extraction_checkpoint(doc_ids)` (+ reset cursor/phase, set status PENDING). Extend `POST /documents/reprocess_failed` (`document_routes.py:3386`) with optional body `{document_ids?, from_scratch?}` + request model; when `from_scratch`, clear targeted checkpoints before enqueue. | 3h | TASK-011 |
| TASK-014 (AC-004 edge) | Extend `delete_document` flow to remove checkpoint entries; on enqueue, clear stale checkpoints when content hash for a doc id changes (orphan prevention). | 2h | TASK-011 |
| TASK-015 (AC-004, AC-005, AC-009) | Tests: clear-on-success (TC-004), `from_scratch` re-extracts all (TC-002), legacy doc with no checkpoint (TC-005). | 3h | TASK-013, TASK-014 |

### Phase 5: API telemetry surface (~1.5h)

| Task ID | Description | Effort | Dependencies |
|---------|-------------|--------|--------------|
| TASK-016 (AC-007) | Add `pipeline_phase` + `extracted_chunks` to document response models for `GET /documents/paginated` (`:3180`) and `GET /documents/track_status/{track_id}` (`:3106`). | 1.5h | TASK-012 |

### Phase 6: WebUI (~9.5h)

| Task ID | Description | Effort | Dependencies |
|---------|-------------|--------|--------------|
| TASK-017 (AC-008) | API client (`lightrag_webui/src/api/lightrag.ts`): extend the reprocess call with `document_ids` + `from_scratch`; add `pipeline_phase`/`extracted_chunks` to `DocStatusResponse` types. | 1.5h | TASK-013, TASK-016 |
| TASK-018 (AC-008) | `DocumentManager.tsx`: render resume indicator (`extraction k/total`) beneath the status badge for PROCESSING/FAILED rows with a checkpoint. | 2h | TASK-017 |
| TASK-019 (AC-008) | `DocumentManager.tsx`: selection-based "Reprocess from scratch (N)" toolbar button (next to Delete) + new `ReprocessFromScratchDialog.tsx` mirroring `DeleteDocumentsDialog`. | 3h | TASK-017 |
| TASK-020 (AC-008) | i18n strings in `locales/en.json` (+ other locales) for button, dialog, indicator. | 1h | TASK-019 |
| TASK-021a (AC-008) | **Stand up Playwright E2E harness**: add Playwright dep + config, `tests/e2e/` scaffold, screenshot helper writing to `tests/screenshots/{feature}/`, and a failure-screenshot `afterEach` hook (per `quality-gates` screenshot protocol). Wire an `e2e` script and update `.add/config.json` (`environments.local.e2e`, `quality.e2e`, `quality.screenshot_protocol`). | 3h | TASK-019 |
| TASK-021b (AC-008) | WebUI component tests (`bun test`) for the client call + dialog behavior, **and** the TC-003 Playwright spec (`tests/e2e/resumable-ingestion.spec.ts`) capturing the three screenshot checkpoints. | 3h | TASK-021a, TASK-020 |

### Phase 7: Performance & polish (~5h)

| Task ID | Description | Effort | Dependencies |
|---------|-------------|--------|--------------|
| TASK-022 (AC-010) | Measure checkpoint-write overhead on a ~200-chunk document; batch/async the writes if it exceeds the 5% budget. | 2h | TASK-006 |
| TASK-023 | Docs: update ingestion notes in README/CLAUDE.md; append `.add/learnings.md` checkpoint. | 1h | Phase 6 |
| TASK-024 (VERIFY) | Full `pytest` (+ `--run-integration` where backends available), `ruff`, `mypy`, WebUI `eslint`/`tsc`; produce spec-compliance report (every AC ↔ passing test). | 2h | all |

## Effort Summary

| Phase | Hours |
|-------|-------|
| 0 — Prep/spikes | 3.0 |
| 1 — Storage | 4.25 |
| 2 — Checkpoint write | 5.0 |
| 3 — Resume logic | 9.0 |
| 4 — Lifecycle | 11.5 |
| 5 — API telemetry | 1.5 |
| 6 — WebUI (incl. Playwright E2E harness) | 13.5 |
| 7 — Perf & polish | 5.0 |
| **Subtotal** | **52.75** |
| +15% contingency | ~61 |

≈ **8 working days solo**.

## Critical Path & Sequencing (solo)

```
TASK-001/002 → TASK-003 → TASK-004 → TASK-006 → TASK-008 → TASK-009 → TASK-011 → TASK-013 → TASK-016 → TASK-017 → TASK-019 → TASK-024
```
- Storage (Phase 1) must precede checkpoint write; checkpoint write precedes resume; resume precedes clear/from_scratch.
- The **API contract** is fixed at TASK-013/016 — once frozen, WebUI (Phase 6) and remaining backend tests can interleave.
- Tests are written RED-first within each feature task per `tdd-enforcement` (paired tasks TASK-007/010/015/021).

## Dependencies

**External:** none (uses already-configured storage + LLM endpoints).
**Internal:** PostgreSQL migration must run before PG-backed deployments can use checkpoints (TASK-005). No other upstream work.

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| PG migration on existing deployments (new table) | Medium | High | Follow `_migrate_create_full_entities_relations_tables` precedent (`:1585`); test the upgrade path on a populated DB; idempotent DDL. |
| Resume-vs-clean graph equivalence hard to assert | Medium | Medium | Build a deterministic graph-comparison helper (sorted nodes/edges + source links); reuse across TC-001/002/004. |
| Standing up the first Playwright E2E harness (none exists today) | Medium | Medium | Decision made: build it in this feature (TASK-021a). Keep scaffold minimal (one spec + screenshot helper); budget 3h and treat harness as reusable infra, not throwaway. |
| Non-JSON-serializable fields in nodes/edges | Low | Medium | Covered by TASK-002 spike; serialize/normalize before upsert. |
| `from_scratch` on a doc mid-PROCESSING (race) | Medium | Medium | Guard: reject/queue clear for PROCESSING docs (spec Edge Cases). |
| Checkpoint orphans after content change | Medium | Low | Clear by `full_doc_id` on enqueue when content hash differs (TASK-014). |
| Checkpoint write overhead regresses throughput | Low | Medium | TASK-022 perf budget; batch writes if needed. |

## Testing Strategy

- **Unit/integration (pytest, `tests/test_resumable_ingestion.py`):** AC-001–005, AC-009 via TC-001/002/004/005; per-backend round-trip for AC-006. Default offline run uses JSON/NetworkX; `--run-integration` exercises PG/Redis/Mongo when available.
- **WebUI (`bun test`):** API client `from_scratch` call shape; `ReprocessFromScratchDialog` confirm/cancel; resume-indicator rendering logic.
- **TC-003 (UI E2E):** Playwright harness is stood up in this feature (TASK-021a). The `tests/e2e/resumable-ingestion.spec.ts` spec drives the selection → confirm → reprocess flow and captures the three screenshot checkpoints to `tests/screenshots/resumable-ingestion/`.
- **Quality gates (TASK-024):** coverage ≥ 80%, `ruff`, `mypy`, `eslint`, `tsc`, spec-compliance report.

## Deliverables

**Backend code:** `lightrag/namespace.py`, `lightrag/lightrag.py` (init + `_insert_done` + PROCESSED cleanup + resume threading + `aclear_extraction_checkpoint`), `lightrag/operate.py` (`extract_entities` checkpoint write + resume filter), `lightrag/kg/postgres_impl.py` (TABLES/DDL/migration), `lightrag/api/routers/document_routes.py` (reprocess body + telemetry fields), `lightrag/base.py` (doc_status metadata fields if promoted).
**Frontend code:** `lightrag_webui/src/api/lightrag.ts`, `features/DocumentManager.tsx`, `components/documents/ReprocessFromScratchDialog.tsx`, `locales/*.json`.
**Tests:** `tests/test_resumable_ingestion.py`, WebUI `*.test.ts(x)`.
**Docs:** README/CLAUDE.md ingestion notes; `.add/learnings.md` checkpoint.

## Success Metrics

- [ ] All 10 acceptance criteria implemented and traced to a passing test.
- [ ] TC-001 resume invokes LLM only for un-extracted chunks; graph equals baseline.
- [ ] `from_scratch` clears checkpoint and re-extracts all (TC-002).
- [ ] New namespace round-trips on every available KV backend (AC-006).
- [ ] Coverage ≥ 80%; all quality gates green.
- [ ] Checkpoint overhead < 5% on a ~200-chunk doc (AC-010).

## Resolved Decisions (2026-06-16)

1. **E2E for TC-003:** Stand up a Playwright E2E harness now, as part of this feature (TASK-021a/b). Updates `.add/config.json` e2e + screenshot-protocol settings.
2. **doc_status fields:** Store `pipeline_phase`/`extracted_chunks` inside the existing `DocProcessingStatus.metadata` dict — no dataclass change, no per-backend serialization impact.

## Next Steps

1. `/add:tdd-cycle specs/resumable-ingestion.md` — execute, starting at Phase 0/1 (RED-first per task).
2. Track actual vs. estimate; adjust if PG migration or graph-equivalence prove larger than scoped.

## Plan History

- 2026-06-16: Initial plan created from spec v0.1.1.
