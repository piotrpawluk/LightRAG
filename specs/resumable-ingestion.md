# Spec: Resumable Ingestion with Per-Chunk Extraction Checkpoints

**Version:** 0.1.0
**Created:** 2026-06-16
**PRD Reference:** docs/prd.md
**Status:** Draft
**Maturity:** beta

## 1. Overview

Document ingestion runs in stages: **chunk → extract entities/relations (per-chunk LLM calls) → merge into graph + vector stores → PROCESSED** (`lightrag/lightrag.py:1779-2356`). Today, when an error occurs during extraction, the per-chunk extraction results are buffered in memory and **discarded** (`lightrag/operate.py:2912-3194`). On re-run, `_validate_and_fix_document_consistency()` resets the document FAILED→PENDING and re-runs **the entire document from scratch** (`lightrag/lightrag.py:1726-1777`), re-paying the expensive LLM extraction cost for chunks that already succeeded.

This feature persists each chunk's extraction result to a **dedicated checkpoint store** as soon as it completes. On re-run, the pipeline **resumes where it failed** — already-extracted chunks are loaded from the checkpoint and skipped, and only un-extracted chunks are sent to the LLM. A **force-full (`from_scratch`) option** lets the operator discard the checkpoint and reprocess the whole document from the beginning.

Chunks are already idempotent (MD5-keyed) and graph/vector upserts already merge idempotently — so the new durable state we must add is the **per-chunk extraction result** plus a **resume cursor**. No change is needed to make merge idempotent; it already is.

### User Story

As an **operator ingesting large documents**, I want **a failed ingestion to resume from the last successfully extracted chunk instead of restarting**, so that **a crash or LLM outage near the end of a long document doesn't force me to re-pay for all the LLM extraction work** — while still being able to **force a clean reprocess from scratch when I want to**.

## 2. Acceptance Criteria

| ID | Criterion | Priority |
|----|-----------|----------|
| AC-001 | As each chunk's entity/relation extraction completes, its result (nodes + edges) is persisted to a dedicated checkpoint store before the document advances to the merge stage. | Must |
| AC-002 | On re-run of a FAILED or abnormally-terminated (PROCESSING) document, chunks already present in the checkpoint store are NOT re-sent to the LLM; only un-extracted chunks are processed. | Must |
| AC-003 | After resume, the merge stage runs over the union of checkpointed + newly extracted chunk results, producing a knowledge graph identical to a clean single-pass run of the same document. | Must |
| AC-004 | When a document reaches PROCESSED, its checkpoint entries are deleted (no stale checkpoint data accumulates). | Must |
| AC-005 | A `from_scratch` (force-full) flag on the reprocess path clears the target document's checkpoint and resume cursor and re-extracts every chunk from the beginning, ignoring any saved progress. | Must |
| AC-006 | Checkpoint state is workspace-isolated and functions across all configured KV backends (JSON, PostgreSQL, Redis, MongoDB) using the existing storage abstraction. | Must |
| AC-007 | The document status record exposes resume telemetry: pipeline phase (`chunking` / `extraction` / `merge`) and extracted-vs-total chunk counts. | Should |
| AC-008 | The WebUI Document Manager shows resume progress for in-flight/failed documents and offers a per-document "Reprocess from scratch" action that calls the `from_scratch` path. | Should |
| AC-009 | Backward compatible: documents and installations with no checkpoint data process exactly as they do today (a FAILED doc with no checkpoint simply re-extracts all chunks). | Should |
| AC-010 | Checkpoint persistence on a successful clean run does not materially regress ingestion throughput (target: < 5% wall-clock overhead on a representative 200-chunk document). | Nice |

## 3. User Test Cases

### TC-001: Resume after mid-extraction failure

**Precondition:** A document large enough to produce ≥ 10 chunks is enqueued. A fault is injected so extraction raises after chunk 6 of 10 completes.
**Steps:**
1. Insert the document; let the pipeline run until it fails (status → FAILED).
2. Inspect the checkpoint store — assert it holds extraction results for the 6 completed chunks.
3. Trigger reprocessing (normal, not `from_scratch`).
4. Instrument the LLM extraction call to count invocations during the second run.
**Expected Result:** Only the 4 remaining chunks invoke the LLM; the document reaches PROCESSED; the resulting graph (entities, relations, source-chunk links) is identical to a clean run; checkpoint entries for the document are gone afterward.
**Screenshot Checkpoint:** N/A (backend)
**Maps to:** tests/test_resumable_ingestion.py → "test_ac001_002_003_resume_skips_extracted_chunks"

### TC-002: Force-full reprocess from scratch

**Precondition:** A PROCESSED (or FAILED-with-checkpoint) document exists with a populated checkpoint.
**Steps:**
1. Call the reprocess path for that document with `from_scratch=true`.
2. Instrument the LLM extraction call count.
**Expected Result:** The document's checkpoint and resume cursor are cleared before processing; every chunk is re-extracted (LLM invoked for all chunks); document ends PROCESSED with a freshly rebuilt graph.
**Screenshot Checkpoint:** N/A (backend)
**Maps to:** tests/test_resumable_ingestion.py → "test_ac005_from_scratch_reextracts_all_chunks"

### TC-003: WebUI reprocess-from-scratch and resume indicator

**Precondition:** WebUI running against a server with one FAILED document that has a partial checkpoint.
**Steps:**
1. Navigate to the Documents view.
2. Observe the failed document's row shows a resume indicator (e.g. "extraction 6/10").
3. Click the document's "Reprocess from scratch" action and confirm.
4. Watch the pipeline status update.
**Expected Result:** The action triggers a `from_scratch` reprocess; the indicator resets and the document reprocesses fully; on completion the row shows PROCESSED.
**Screenshot Checkpoint:** tests/screenshots/resumable-ingestion/step-01-resume-indicator.png, step-02-reprocess-from-scratch-confirm.png, step-03-processed.png
**Maps to:** tests/e2e/resumable-ingestion.spec.ts → "TC-003 reprocess from scratch from Document Manager"

### TC-004: Clean run leaves no checkpoint residue

**Precondition:** Empty store.
**Steps:**
1. Insert a document that processes successfully end-to-end with no injected fault.
2. Inspect the checkpoint store for that document's chunk ids.
**Expected Result:** Document reaches PROCESSED; checkpoint store contains no entries for the document; graph matches baseline.
**Screenshot Checkpoint:** N/A (backend)
**Maps to:** tests/test_resumable_ingestion.py → "test_ac004_clean_run_clears_checkpoint"

### TC-005: Backward compatibility for legacy FAILED documents

**Precondition:** A FAILED document exists with NO checkpoint entries (simulating data created before this feature).
**Steps:**
1. Trigger normal reprocessing.
**Expected Result:** Document re-extracts all chunks (full re-run, as today) and reaches PROCESSED without error — absence of a checkpoint is treated as "resume cursor at 0".
**Screenshot Checkpoint:** N/A (backend)
**Maps to:** tests/test_resumable_ingestion.py → "test_ac009_missing_checkpoint_falls_back_to_full_run"

## 4. Data Model

### ExtractionCheckpoint (new KV namespace)

New KV storage namespace `KV_STORE_EXTRACTION_CHECKPOINT` (e.g. `NameSpace.KV_STORE_EXTRACTION_CHECKPOINT`), instantiated as `self.extraction_checkpoint: BaseKVStorage` alongside the existing KV stores in `lightrag/lightrag.py` (~lines 705-739) and persisted in `_insert_done()` (`lightrag/lightrag.py:2378-2407`). One record per successfully extracted chunk.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| _key | str | Yes | The chunk id (`chunk-<md5>`), matching the id used in `text_chunks` / `chunks_vdb`. |
| full_doc_id | str | Yes | Parent document id — used to enumerate and clear a document's checkpoint. |
| chunk_order_index | int | Yes | 0-based position of the chunk in the document. |
| nodes | list[dict] | Yes | Serialized `maybe_nodes` extracted from this chunk (entity records prior to merge). |
| edges | list[dict] | Yes | Serialized `maybe_edges` extracted from this chunk (relation records prior to merge). |
| created_at | str (ISO) | Yes | When the chunk's extraction was checkpointed. |

### DocProcessingStatus additions (existing dataclass, `lightrag/base.py:762-806`)

Stored inside the existing `metadata: dict` (no schema migration of the dataclass required) or as first-class optional fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| pipeline_phase | str | No | One of `chunking` / `extraction` / `merge`; identifies where to resume. |
| extracted_chunks | int | No | Count of chunks with a checkpoint entry (resume telemetry). Total = existing `chunks_count`. |

### Relationships

- `ExtractionCheckpoint._key` ⇄ `text_chunks` key and `chunks_vdb` id (same chunk id) — the checkpoint is the durable record of "this chunk's LLM extraction is done".
- `ExtractionCheckpoint.full_doc_id` → `full_docs` key / `doc_status` key (the document).
- Checkpoint entries are transient: created during the extraction phase, consumed at the start of the merge phase, deleted on PROCESSED or on `from_scratch`.

## 5. API Contract

### POST /documents/reprocess_failed (extended)

**Description:** Extend the existing endpoint (`lightrag/api/routers/document_routes.py:3386`) to accept an optional body. With no body it behaves exactly as today (bulk resume of FAILED/PENDING/PROCESSING). With a body it can target specific documents and/or force a from-scratch reprocess.

**Request:**
```json
{
  "document_ids": ["doc-abc123"],
  "from_scratch": true
}
```
- `document_ids` (optional): limit reprocessing to these document ids. Omit/null = all eligible documents (current behavior).
- `from_scratch` (optional, default `false`): when `true`, clear the targeted documents' checkpoints and resume cursors before processing so every chunk is re-extracted.

**Response (200):**
```json
{
  "status": "reprocessing_started",
  "message": "Reprocessing initiated for 1 document(s) (from_scratch=true).",
  "track_id": ""
}
```

**Error Responses:**
- `400` — `from_scratch=true` with an empty/invalid `document_ids` filter that resolves to no documents.
- `401` — Unauthorized (existing `combined_auth`).
- `404` — A supplied `document_id` does not exist.
- `500` — Error initiating reprocessing.

### Resume telemetry on existing read endpoints

`GET /documents/paginated` (`:3180`) and `GET /documents/track_status/{track_id}` (`:3106`) responses include the new `pipeline_phase` and `extracted_chunks` fields (alongside existing `chunks_count`) so clients can render resume progress. No new endpoint required.

## 6. UI Behavior

> **UI design approved — see `specs/ux/resumable-ingestion-ux.md` (2026-06-16).** The design follows the existing **selection-based toolbar pattern**, not a per-row action menu.

### States (Document Manager — `lightrag_webui/src/features/DocumentManager.tsx`)

- **Loading:** Document rows show existing status badges; resume telemetry fetched with the existing paginated documents poll.
- **Empty:** Unchanged — no documents message; no toolbar action shown.
- **Error / Failed:** A FAILED or PROCESSING row with a partial checkpoint shows a resume indicator **beneath the status badge**, e.g. `extraction 62/100 chunks`. FAILED error message remains on hover (existing behavior).
- **Reprocess action:** Selecting one or more rows reveals a **"Reprocess from scratch (N)" toolbar button** next to Delete (greyed at 0 selected, mirroring Delete). It opens a **Delete-style confirmation dialog** (lists affected docs; warns saved progress is discarded and all chunks re-run through the LLM), then calls `reprocess_failed` with `{document_ids:[...], from_scratch:true}`. The normal resume path is unchanged and never wipes the checkpoint.
- **Success:** PROCESSED rows show no resume indicator (checkpoint cleared per AC-004); the from-scratch action remains available for deliberate full rebuilds.

The phase indicator also surfaces in `PipelineStatusDialog.tsx` for the actively-processing document.

### Screenshot Checkpoints

| Step | Description | Path |
|------|-------------|------|
| 1 | Failed document showing resume indicator (extracted/total) | tests/screenshots/resumable-ingestion/step-01-resume-indicator.png |
| 2 | "Reprocess from scratch" confirmation dialog | tests/screenshots/resumable-ingestion/step-02-reprocess-from-scratch-confirm.png |
| 3 | Document reaches PROCESSED after from-scratch run | tests/screenshots/resumable-ingestion/step-03-processed.png |

## 7. Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| FAILED doc with no checkpoint (legacy/pre-feature data) | Treated as resume cursor 0 → full re-extraction (current behavior). No error. (AC-009) |
| Failure during the merge phase (all chunks extracted) | On re-run, all chunk results load from checkpoint, zero LLM calls, merge re-runs (graph upserts are idempotent), doc → PROCESSED. |
| `from_scratch` requested for a document mid-processing | Reject or queue: do not clear a checkpoint for a document currently PROCESSING; return 409/400 with a clear message, or apply after current run yields. |
| Document content changed between runs (same doc id, new text) | Chunk ids change with content; stale checkpoint entries (old chunk ids) are orphaned. They must be cleared by `full_doc_id` on enqueue when content hash differs, preventing orphan accumulation. |
| Document deleted (`/delete_document`) | Its checkpoint entries are deleted as part of document deletion cleanup (no orphaned checkpoints). |
| Checkpoint KV backend unavailable mid-run | Extraction fails as today and the doc is marked FAILED; no silent data loss — a missing checkpoint just degrades to full re-run on retry. |
| Concurrent extraction of multiple chunks (existing semaphore) | Per-chunk checkpoint writes must be safe under concurrency; each chunk writes its own key, so no cross-chunk contention. |
| `multimodal_processed=False` / PREPROCESSED interplay (`base.py:791-806`) | Checkpointing applies to the entity/relation extraction phase only; the existing preprocessed→processed status conversion is unaffected. |

## 8. Dependencies

- Existing pipeline functions: `apipeline_process_enqueue_documents` (`lightrag/lightrag.py:1779`), `_process_extract_entities` (`:2357`), `extract_entities` (`lightrag/operate.py:2912`), `merge_nodes_and_edges` (`lightrag/operate.py:2523`), `_validate_and_fix_document_consistency` (`lightrag/lightrag.py:1726`), `_insert_done` (`:2378`).
- KV storage abstraction `BaseKVStorage` (`lightrag/base.py`) and the `NameSpace` registry; all four KV backends (JSON, PG, Redis, Mongo) must register the new namespace.
- WebUI: `DocumentManager.tsx`, `PipelineStatusDialog.tsx`, and the API client `lightrag_webui/src/api/lightrag.ts`.
- No new third-party libraries.

## 9. Infrastructure Prerequisites

| Category | Requirement |
|----------|-------------|
| Environment variables | None new. Honors existing `KV_STORAGE` backend selection and `WORKSPACE` isolation. |
| Registry images | N/A (no new image; ships in existing server image). |
| Cloud quotas | N/A. |
| Network reachability | N/A (uses already-configured storage + LLM endpoints). |
| CI status | `tests.yml` must run the new `tests/test_resumable_ingestion.py`; lint (`ruff`) and `tsc`/`eslint` for WebUI changes must pass. |
| External secrets | N/A. |
| Database migrations | PostgreSQL KV backend: the new `KV_STORE_EXTRACTION_CHECKPOINT` namespace requires its table/namespace to be created (verify the PG KV implementation auto-creates per-namespace tables; add migration if it does not). Redis/Mongo: namespace prefix/collection created on first write — verify. |

**Verification before implementation:** Confirm how each KV backend materializes a new namespace (auto-create vs. explicit DDL) by inspecting `lightrag/kg/` implementations; confirm `delete_document` already has a cleanup hook to extend; confirm `chunks_count` is populated before the extraction phase so `extracted/total` telemetry is meaningful.

## 10. Revision History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2026-06-16 | 0.1.0 | peterpawluk | Initial spec from /add:spec interview |
| 2026-06-16 | 0.1.1 | peterpawluk | UI design signed off (specs/ux/resumable-ingestion-ux.md); Section 6 realigned from per-row menu to selection-based toolbar pattern |
