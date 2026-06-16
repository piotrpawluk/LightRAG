"""Pipeline-level tests for resumable ingestion (Cycle 2).

Spec: specs/resumable-ingestion.md
Scope (wiring the extraction-layer checkpoint into the live pipeline):
  - AC-006: a dedicated extraction-checkpoint KV store is initialized on LightRAG
  - AC-001: the live pipeline writes per-chunk checkpoints, and they SURVIVE a
            mid-document failure (here: merge failure after extraction)
  - AC-004: checkpoints are cleared once the document reaches PROCESSED
  - AC-005: aclear_extraction_checkpoint(doc_ids) discards a document's saved
            progress (the core of the from_scratch reprocess path)

Uses the same offline harness style as tests/test_doc_status_chunk_preservation.py.
"""

from datetime import datetime, timezone
from uuid import uuid4

import numpy as np
import pytest

import lightrag.lightrag as lightrag_module
from lightrag.base import DocStatus
from lightrag.lightrag import LightRAG
from lightrag.namespace import NameSpace
from lightrag.utils import EmbeddingFunc, Tokenizer, compute_mdhash_id

pytestmark = pytest.mark.offline


class _SimpleTokenizerImpl:
    def encode(self, content: str) -> list[int]:
        return [ord(ch) for ch in content]

    def decode(self, tokens: list[int]) -> str:
        return "".join(chr(t) for t in tokens)


async def _dummy_embedding(texts: list[str]) -> np.ndarray:
    return np.ones((len(texts), 8), dtype=float)


# Valid extraction output so the real extraction phase yields a node and writes
# a (non-empty) checkpoint for each chunk.
_EXTRACTION_RESULT = "(entity<|#|>TEST_ENTITY<|#|>CONCEPT<|#|>A test entity)<|COMPLETE|>"


async def _dummy_llm(*args, **kwargs) -> str:
    return _EXTRACTION_RESULT


def _deterministic_chunking(
    tokenizer,
    content: str,
    split_by_character,
    split_by_character_only: bool,
    chunk_overlap_token_size: int,
    chunk_token_size: int,
) -> list[dict]:
    return [
        {"tokens": 1, "content": f"{content}::chunk1", "chunk_order_index": 0},
        {"tokens": 1, "content": f"{content}::chunk2", "chunk_order_index": 1},
    ]


def _status_to_text(status: object) -> str:
    if isinstance(status, DocStatus):
        return status.value
    return str(status).replace("DocStatus.", "").lower()


async def _build_rag(tmp_path, test_name: str) -> LightRAG:
    workspace = f"{test_name}_{uuid4().hex[:8]}"
    rag = LightRAG(
        working_dir=str(tmp_path / test_name),
        workspace=workspace,
        llm_model_func=_dummy_llm,
        embedding_func=EmbeddingFunc(
            embedding_dim=8, max_token_size=8192, func=_dummy_embedding
        ),
        tokenizer=Tokenizer("test-tokenizer", _SimpleTokenizerImpl()),
        chunking_func=_deterministic_chunking,
        max_parallel_insert=1,
    )
    await rag.initialize_storages()
    return rag


@pytest.mark.asyncio
async def test_ac006_extraction_checkpoint_store_initialized(tmp_path):
    """AC-006: LightRAG exposes a working dedicated extraction-checkpoint store."""
    rag = await _build_rag(tmp_path, "ckpt_init")
    try:
        assert rag.extraction_checkpoint is not None
        assert (
            NameSpace.KV_STORE_EXTRACTION_CHECKPOINT
            in rag.extraction_checkpoint.namespace
        )
        await rag.extraction_checkpoint.upsert({"k": {"v": 1}})
        record = await rag.extraction_checkpoint.get_by_id("k")
        assert record is not None and record["v"] == 1
    finally:
        await rag.finalize_storages()


@pytest.mark.asyncio
async def test_ac001_pipeline_writes_checkpoints_surviving_merge_failure(
    tmp_path, monkeypatch
):
    """AC-001: per-chunk checkpoints are written during extraction and persist when
    a later stage (merge) fails — so a re-run can resume from them."""
    rag = await _build_rag(tmp_path, "ckpt_write_on_failure")
    try:
        content = "checkpoint write document"
        doc_id = compute_mdhash_id(content, prefix="doc-")
        await rag.apipeline_enqueue_documents(input=content, file_paths="ckpt.txt")

        async def fail_merge(**kwargs):
            raise RuntimeError("merge fail sentinel")

        monkeypatch.setattr(lightrag_module, "merge_nodes_and_edges", fail_merge)

        await rag.apipeline_process_enqueue_documents()

        status = await rag.doc_status.get_by_id(doc_id)
        assert status is not None
        assert _status_to_text(status["status"]) == "failed"
        chunk_ids = status["chunks_list"]
        assert len(chunk_ids) == 2

        records = await rag.extraction_checkpoint.get_by_ids(chunk_ids)
        assert all(r is not None for r in records)  # survived the failure
    finally:
        await rag.finalize_storages()


@pytest.mark.asyncio
async def test_ac004_checkpoints_cleared_after_processed(tmp_path):
    """AC-004: a fully processed document leaves no checkpoint residue."""
    rag = await _build_rag(tmp_path, "ckpt_clear_on_processed")
    try:
        content = "successful processing document"
        doc_id = compute_mdhash_id(content, prefix="doc-")
        await rag.apipeline_enqueue_documents(input=content, file_paths="ok.txt")

        await rag.apipeline_process_enqueue_documents()

        status = await rag.doc_status.get_by_id(doc_id)
        assert status is not None
        assert _status_to_text(status["status"]) == "processed"
        chunk_ids = status["chunks_list"]
        assert len(chunk_ids) == 2

        records = await rag.extraction_checkpoint.get_by_ids(chunk_ids)
        assert all(r is None for r in records)  # cleared on PROCESSED
    finally:
        await rag.finalize_storages()


@pytest.mark.asyncio
async def test_ac007_telemetry_on_processed(tmp_path):
    """AC-007: a processed document records pipeline_phase + extracted_chunks."""
    rag = await _build_rag(tmp_path, "telemetry_processed")
    try:
        content = "telemetry processed document"
        doc_id = compute_mdhash_id(content, prefix="doc-")
        await rag.apipeline_enqueue_documents(input=content, file_paths="t.txt")
        await rag.apipeline_process_enqueue_documents()

        status = await rag.doc_status.get_by_id(doc_id)
        assert _status_to_text(status["status"]) == "processed"
        meta = status["metadata"]
        assert meta["pipeline_phase"] == "completed"
        assert meta["extracted_chunks"] == status["chunks_count"] == 2
    finally:
        await rag.finalize_storages()


@pytest.mark.asyncio
async def test_ac007_telemetry_on_merge_failure(tmp_path, monkeypatch):
    """AC-007: a merge failure records phase 'merge' and how many chunks were extracted."""
    rag = await _build_rag(tmp_path, "telemetry_merge_failure")
    try:
        content = "telemetry merge failure document"
        doc_id = compute_mdhash_id(content, prefix="doc-")
        await rag.apipeline_enqueue_documents(input=content, file_paths="t.txt")

        async def fail_merge(**kwargs):
            raise RuntimeError("merge fail sentinel")

        monkeypatch.setattr(lightrag_module, "merge_nodes_and_edges", fail_merge)
        await rag.apipeline_process_enqueue_documents()

        status = await rag.doc_status.get_by_id(doc_id)
        assert _status_to_text(status["status"]) == "failed"
        meta = status["metadata"]
        assert meta["pipeline_phase"] == "merge"
        assert meta["extracted_chunks"] == 2  # both chunks were extracted before merge
    finally:
        await rag.finalize_storages()


@pytest.mark.asyncio
async def test_ac005_reprocess_from_scratch_resets_status_and_clears_checkpoint(
    tmp_path,
):
    """AC-005: reprocess-from-scratch clears checkpoints and resets the doc to PENDING."""
    rag = await _build_rag(tmp_path, "reprocess_from_scratch")
    try:
        doc_id = "doc-reprocess"
        chunk_ids = ["chunk-a", "chunk-b"]
        now = datetime.now(timezone.utc).isoformat()
        await rag.doc_status.upsert(
            {
                doc_id: {
                    "status": DocStatus.PROCESSED,
                    "content_summary": "s",
                    "content_length": 1,
                    "chunks_count": 2,
                    "chunks_list": chunk_ids,
                    "created_at": now,
                    "updated_at": now,
                    "file_path": "fs.txt",
                    "track_id": "t",
                    "error_msg": "",
                    "metadata": {"pipeline_phase": "completed", "extracted_chunks": 2},
                }
            }
        )
        await rag.extraction_checkpoint.upsert(
            {
                "chunk-a": {"full_doc_id": doc_id, "nodes": {}, "edges": []},
                "chunk-b": {"full_doc_id": doc_id, "nodes": {}, "edges": []},
            }
        )

        await rag.areprocess_documents_from_scratch([doc_id])

        status = await rag.doc_status.get_by_id(doc_id)
        assert _status_to_text(status["status"]) == "pending"
        assert status["metadata"] == {}
        assert all(
            r is None for r in await rag.extraction_checkpoint.get_by_ids(chunk_ids)
        )
    finally:
        await rag.finalize_storages()


@pytest.mark.asyncio
async def test_ac005_aclear_extraction_checkpoint_removes_doc_chunks(tmp_path):
    """AC-005: clearing a document's checkpoint discards its saved progress."""
    rag = await _build_rag(tmp_path, "ckpt_from_scratch")
    try:
        doc_id = "doc-from-scratch"
        chunk_ids = ["chunk-a", "chunk-b"]
        now = datetime.now(timezone.utc).isoformat()
        await rag.doc_status.upsert(
            {
                doc_id: {
                    "status": DocStatus.PROCESSED,
                    "content_summary": "s",
                    "content_length": 1,
                    "chunks_count": 2,
                    "chunks_list": chunk_ids,
                    "created_at": now,
                    "updated_at": now,
                    "file_path": "fs.txt",
                    "track_id": "t",
                    "error_msg": "",
                    "metadata": {},
                }
            }
        )
        await rag.extraction_checkpoint.upsert(
            {
                "chunk-a": {"full_doc_id": doc_id, "nodes": {}, "edges": []},
                "chunk-b": {"full_doc_id": doc_id, "nodes": {}, "edges": []},
            }
        )

        await rag.aclear_extraction_checkpoint([doc_id])

        records = await rag.extraction_checkpoint.get_by_ids(chunk_ids)
        assert all(r is None for r in records)
    finally:
        await rag.finalize_storages()
