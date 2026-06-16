"""Tests for resumable ingestion — per-chunk extraction checkpoints.

Spec: specs/resumable-ingestion.md
Cycle 1 scope (extraction layer in lightrag/operate.py):
  - AC-001: each chunk's extraction result is persisted to the checkpoint store
  - AC-002: a re-run skips chunks already present in the checkpoint store
            (no LLM call for them) and only extracts the missing chunks
  - AC-003: the returned results are the union of checkpointed + freshly
            extracted chunks, matching a clean single-pass run
  - AC-009: with no checkpoint store, behavior is unchanged (full extraction)

These exercise extract_entities() directly with a mock LLM, mirroring
tests/test_extract_entities.py.
"""

import json

from unittest.mock import AsyncMock, patch

import pytest

from lightrag.utils import Tokenizer, TokenizerInterface


class DummyTokenizer(TokenizerInterface):
    """Simple 1:1 character-to-token mapping for testing."""

    def encode(self, content: str):
        return [ord(ch) for ch in content]

    def decode(self, tokens):
        return "".join(chr(token) for token in tokens)


# Minimal valid extraction result that _process_extraction_result can parse.
_EXTRACTION_RESULT = "(entity<|#|>TEST_ENTITY<|#|>CONCEPT<|#|>A test entity)<|COMPLETE|>"


class FakeCheckpointStore:
    """In-memory BaseKVStorage stand-in.

    upsert() round-trips through JSON so any non-serializable value (e.g. a
    tuple edge key) would surface immediately as a TypeError.
    """

    def __init__(self):
        self.data: dict[str, dict] = {}

    async def filter_keys(self, keys: set[str]) -> set[str]:
        # Returns the subset of `keys` NOT already stored (keys needing work).
        return {k for k in keys if k not in self.data}

    async def get_by_id(self, id: str):
        return self.data.get(id)

    async def get_by_ids(self, ids: list[str]):
        return [self.data.get(i) for i in ids]

    async def upsert(self, data: dict[str, dict]) -> None:
        for k, v in data.items():
            self.data[k] = json.loads(json.dumps(v))  # enforce JSON-serializable

    async def delete(self, ids: list[str]) -> None:
        for i in ids:
            self.data.pop(i, None)


def _make_global_config(entity_extract_max_gleaning: int = 0) -> dict:
    return {
        "llm_model_func": AsyncMock(return_value=_EXTRACTION_RESULT),
        "entity_extract_max_gleaning": entity_extract_max_gleaning,
        "addon_params": {},
        "tokenizer": Tokenizer("dummy", DummyTokenizer()),
        "max_extract_input_tokens": 999999,
        "llm_model_max_async": 4,
    }


def _make_chunks(n: int = 3) -> dict[str, dict]:
    return {
        f"chunk-{i:03d}": {
            "tokens": 10,
            "content": f"Chunk {i} content.",
            "full_doc_id": "doc-001",
            "chunk_order_index": i,
        }
        for i in range(n)
    }


def _entity_names(results: list) -> set[str]:
    names: set[str] = set()
    for maybe_nodes, _maybe_edges in results:
        names.update(maybe_nodes.keys())
    return names


@pytest.mark.offline
@pytest.mark.asyncio
async def test_ac001_each_chunk_extraction_is_checkpointed():
    """AC-001: every successfully extracted chunk is persisted to the store."""
    from lightrag.operate import extract_entities

    gc = _make_global_config()
    store = FakeCheckpointStore()
    chunks = _make_chunks(3)

    with patch("lightrag.operate.logger"):
        results = await extract_entities(
            chunks=chunks, global_config=gc, extraction_checkpoint=store
        )

    assert set(store.data.keys()) == set(chunks.keys())
    for rec in store.data.values():
        assert rec["full_doc_id"] == "doc-001"
        assert "nodes" in rec and "edges" in rec
    assert len(results) == 3


@pytest.mark.offline
@pytest.mark.asyncio
async def test_ac002_full_resume_calls_no_llm():
    """AC-002: when all chunks are already checkpointed, the LLM is not called."""
    from lightrag.operate import extract_entities

    chunks = _make_chunks(3)
    store = FakeCheckpointStore()

    gc1 = _make_global_config()
    with patch("lightrag.operate.logger"):
        await extract_entities(
            chunks=chunks, global_config=gc1, extraction_checkpoint=store
        )
    assert gc1["llm_model_func"].await_count == 3  # clean run extracts all

    gc2 = _make_global_config()
    with patch("lightrag.operate.logger"):
        results = await extract_entities(
            chunks=chunks, global_config=gc2, extraction_checkpoint=store
        )
    assert gc2["llm_model_func"].await_count == 0  # fully resumed
    assert len(results) == 3


@pytest.mark.offline
@pytest.mark.asyncio
async def test_ac002_partial_resume_only_processes_missing_chunks():
    """AC-002: a re-run after a mid-extraction failure only re-extracts the
    chunk(s) missing from the checkpoint."""
    from lightrag.operate import extract_entities

    chunks = _make_chunks(3)
    store = FakeCheckpointStore()

    gc1 = _make_global_config()
    with patch("lightrag.operate.logger"):
        await extract_entities(
            chunks=chunks, global_config=gc1, extraction_checkpoint=store
        )

    # Simulate that one chunk's extraction was lost when the run failed.
    await store.delete(["chunk-002"])

    gc2 = _make_global_config()
    with patch("lightrag.operate.logger"):
        results = await extract_entities(
            chunks=chunks, global_config=gc2, extraction_checkpoint=store
        )

    assert gc2["llm_model_func"].await_count == 1  # only the missing chunk
    assert len(results) == 3  # 2 checkpointed + 1 freshly extracted
    assert set(store.data.keys()) == set(chunks.keys())  # re-checkpointed


@pytest.mark.offline
@pytest.mark.asyncio
async def test_ac003_resume_union_matches_clean_run():
    """AC-003: a partially-resumed run yields the same entities as a clean run."""
    from lightrag.operate import extract_entities

    chunks = _make_chunks(3)

    gc_clean = _make_global_config()
    with patch("lightrag.operate.logger"):
        clean = await extract_entities(chunks=chunks, global_config=gc_clean)

    store = FakeCheckpointStore()
    gc_a = _make_global_config()
    with patch("lightrag.operate.logger"):
        await extract_entities(
            chunks=chunks, global_config=gc_a, extraction_checkpoint=store
        )
    await store.delete(["chunk-001"])  # force one chunk to be re-extracted

    gc_b = _make_global_config()
    with patch("lightrag.operate.logger"):
        resumed = await extract_entities(
            chunks=chunks, global_config=gc_b, extraction_checkpoint=store
        )

    assert len(resumed) == len(clean) == 3
    assert _entity_names(resumed) == _entity_names(clean)


@pytest.mark.offline
@pytest.mark.asyncio
async def test_ac009_no_checkpoint_store_processes_all_chunks():
    """AC-009: without a checkpoint store, every chunk is extracted (legacy path)."""
    from lightrag.operate import extract_entities

    chunks = _make_chunks(3)
    gc = _make_global_config()

    with patch("lightrag.operate.logger"):
        results = await extract_entities(chunks=chunks, global_config=gc)

    assert gc["llm_model_func"].await_count == 3
    assert len(results) == 3


@pytest.mark.offline
def test_edge_tuple_keys_survive_checkpoint_roundtrip():
    """AC-001/AC-003: edges keyed by (src, tgt) tuples must serialize to JSON and
    reconstruct exactly — the core serialization concern for the checkpoint store."""
    from lightrag.operate import (
        _deserialize_extraction_checkpoint,
        _serialize_extraction_for_checkpoint,
    )

    maybe_nodes = {
        "A": [{"entity_name": "A", "entity_type": "X"}],
        "B": [{"entity_name": "B", "entity_type": "Y"}],
    }
    maybe_edges = {
        ("A", "B"): [{"src_id": "A", "tgt_id": "B", "weight": 1.0}],
    }

    record = _serialize_extraction_for_checkpoint("doc-1", 0, maybe_nodes, maybe_edges)
    # Must round-trip through JSON (tuple dict keys are NOT JSON-serializable).
    record = json.loads(json.dumps(record))

    nodes2, edges2 = _deserialize_extraction_checkpoint(record)
    assert nodes2 == maybe_nodes
    assert edges2 == maybe_edges  # tuple key reconstructed
