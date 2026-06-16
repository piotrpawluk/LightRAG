# UX Design: Resumable Ingestion with Per-Chunk Extraction Checkpoints

**Spec:** specs/resumable-ingestion.md
**Status:** APPROVED
**Approved:** 2026-06-16
**Iterations:** 1

## Scope

This feature adds a UI surface to the existing **Document Manager** (`lightrag_webui/src/features/DocumentManager.tsx`). No new screens are introduced; the work is (1) a **resume progress indicator** on document rows and (2) a **selection-based "Reprocess from scratch" toolbar action** with a confirmation dialog. The design deliberately follows the existing selection-driven toolbar pattern (as used by Delete) rather than introducing per-row action menus, which the app does not currently use.

## Screens

### Screen 1 — Document Manager: list view (resume indicator)

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  [⟳ Scan]  [▣ Pipeline Status]                              [🗑 Delete (0)]      │
│  Filter:  (All) (Processed) (Preprocessed) (Processing) (Pending) (Failed)       │
├──────────────┬───────────┬──────────────┬────────┬────────┬─────────┬─────┬─────┤
│  File Name ▲ │ Summary   │ Status       │ Length │ Chunks │ Created │ Upd │ ☐   │
├──────────────┼───────────┼──────────────┼────────┼────────┼─────────┼─────┼─────┤
│ report.pdf   │ Q3 fin... │ ● PROCESSED  │ 84,120 │  42    │ 06-14   │ ... │ ☐   │
│ manual.pdf   │ Setup ... │ ◐ PROCESSING │ 120,400│  68    │ 06-16   │ ... │ ☐   │
│              │           │  extraction  │        │        │         │     │     │
│              │           │  41/68 chunks│        │        │         │     │     │
│ big-doc.pdf  │ Policy... │ ✕ FAILED     │ 210,000│ 100    │ 06-15   │ ... │ ☐   │
│              │           │  extraction  │        │        │         │     │     │
│              │           │  62/100      │        │        │         │     │     │
└──────────────┴───────────┴──────────────┴────────┴────────┴─────────┴─────┴─────┘
```

Notes:
- The resume sub-label (`extraction k/total chunks`) renders **beneath the status badge** and **only** for PROCESSING/FAILED rows that have a checkpoint (`extracted_chunks` present and `< chunks_count`). PROCESSED and PENDING rows show the badge alone.
- FAILED rows keep the existing error-message-on-hover behavior.
- Columns are unchanged (the Chunks column keeps its plain total).

### Screen 2 — Selection active: toolbar action revealed

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  [⟳ Scan]  [▣ Pipeline Status]   [↻ Reprocess from scratch (2)]  [🗑 Delete (2)] │
│  Filter:  (All) (Processed) ...                                                  │
├──────────────┬───────────┬──────────────┬────────┬────────┬─────────┬─────┬─────┤
│ big-doc.pdf  │ Policy... │ ✕ FAILED      │ 210,000│ 100    │ 06-15   │ ... │ ☑   │
│              │           │  extraction   │        │        │         │     │     │
│              │           │  62/100       │        │        │         │     │     │
│ report.pdf   │ Q3 fin... │ ● PROCESSED   │ 84,120 │  42    │ 06-14   │ ... │ ☑   │
└──────────────┴───────────┴──────────────┴────────┴────────┴─────────┴─────┴─────┘
```

Notes:
- `Reprocess from scratch (N)` appears next to Delete, enabled when ≥1 row is selected (greyed at 0, mirroring Delete).
- Any selectable row is eligible (FAILED, PROCESSING, PROCESSED) — supports both failure recovery and deliberate full rebuilds.

### Screen 3 — Confirmation dialog (Delete-style)

```
        ┌────────────────────────────────────────────────┐
        │  Reprocess 2 documents from scratch?            │
        ├────────────────────────────────────────────────┤
        │  This discards saved extraction progress and    │
        │  re-runs ALL chunks through the LLM:            │
        │                                                 │
        │    • big-doc.pdf   (62/100 chunks checkpointed) │
        │    • report.pdf    (fully processed)            │
        │                                                 │
        │  ⚠ Saved progress will be lost and LLM usage    │
        │    will be incurred for every chunk.            │
        │                                                 │
        │                      [ Cancel ]  [ Reprocess ]  │
        └────────────────────────────────────────────────┘
```

Notes:
- Confirm calls `POST /documents/reprocess_failed` with `{ document_ids: [...selected], from_scratch: true }`.
- New dialog component mirrors `DeleteDocumentsDialog` / `ClearDocumentsDialog` structure and copy conventions.
- The normal (resume) reprocess path is unchanged and never wipes the checkpoint.

### Screen 4 — Post-confirm feedback

```
  Toast: "Reprocessing 2 documents from scratch — track via Pipeline Status."
  → Rows reset to PENDING (resume sub-label cleared), then PROCESSING with a
    fresh 'extraction k/total' climbing from 0. The Pipeline Status dialog shows
    the active document's phase (chunking → extraction → merge).
```

## State Matrix

| State | Behavior | Notes |
|-------|----------|-------|
| Loading | Existing skeleton/poll on the documents table; resume sub-labels render when data arrives. | No change to load mechanics. |
| Empty | Unchanged "no documents" message; no toolbar action shown. | Nothing selectable. |
| Error (FAILED) | Badge `✕ FAILED` + resume sub-label `extraction k/total`; error msg on hover. | Selectable for reprocess. |
| In-flight (PROCESSING) | Badge `◐ PROCESSING` + live `extraction k/total`. | Phase visible in Pipeline Status dialog. |
| Success (PROCESSED) | Badge `● PROCESSED`, no resume sub-label (checkpoint cleared, AC-004). | Still selectable for deliberate rebuild. |
| Action disabled | `Reprocess from scratch` greyed when 0 rows selected. | Mirrors Delete button. |

## Flow

Document Manager (list) → user selects one or more rows → toolbar reveals `Reprocess from scratch (N)` → click → confirmation dialog → confirm → API call (`from_scratch:true`) → toast + rows transition PENDING → PROCESSING (live resume counter) → PROCESSED. Cancel returns to the list with selection intact.

## Key Decisions

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| Selection-based toolbar button for "Reprocess from scratch" | Matches the existing Delete pattern; avoids introducing a per-row menu paradigm the app doesn't use. | Per-row "⋮" action menu (rejected — larger, inconsistent change). |
| Resume indicator under the Status badge | Keeps resume state adjacent to the status it qualifies; avoids overloading the Chunks column. | Repurpose Chunks column to "extracted/total" (rejected — overloads column meaning). |
| Delete-style confirmation dialog | Strong safeguard for a destructive action that discards saved work and incurs LLM cost; reuses a known component. | Inline confirm (rejected — too weak for a costly/destructive action). |

## Figma Reference

N/A — wireframes generated in session.

## Spec Notes

- spec Section 6 ("UI Behavior") originally described a "per-row action menu," which contradicts the codebase. Updated to the approved selection-based toolbar pattern and noted UI sign-off.
- AC-008 wording ("per-document action") remains valid in intent (the action operates per selected document) but the mechanism is selection-based, not a per-row menu.
