"""MLflow observability integration for LightRAG.

Provides tracing spans for LLM calls, queries, document ingestion,
entity extraction, and merge operations. Integration is optional —
activates via environment variables and gracefully degrades when
MLflow is not installed or the server is unreachable.

Environment Variables:
    MLFLOW_TRACKING_URI: MLflow server URL (required to enable)
    MLFLOW_EXPERIMENT_NAME: Experiment name (default: "lightrag")
    MLFLOW_TRACKING_TOKEN: Auth token for remote server
    MLFLOW_USER: Fallback user identity
    MLFLOW_RETRY_INTERVAL: Seconds between reconnection attempts (default: 60)
    MLFLOW_LOG_ARTIFACTS: Enable/disable artifact logging (default: "true")
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from typing import Any

logger = logging.getLogger("lightrag")

# -- Context variables for trace propagation and user identity --
# These are set in API middleware and read throughout the pipeline.
mlflow_user_context: ContextVar[str | None] = ContextVar(
    "mlflow_user_context", default=None
)

# -- MLflow availability detection --
_mlflow_available = False
_mlflow = None

try:
    import mlflow as _mlflow_module

    _mlflow = _mlflow_module
    _mlflow_available = True
except ImportError:
    pass


# -- Configuration --
def _get_config() -> dict[str, Any]:
    """Read MLflow configuration from environment variables."""
    return {
        "tracking_uri": os.environ.get("MLFLOW_TRACKING_URI", ""),
        "experiment_name": os.environ.get("MLFLOW_EXPERIMENT_NAME", "lightrag"),
        "tracking_token": os.environ.get("MLFLOW_TRACKING_TOKEN", ""),
        "user": os.environ.get("MLFLOW_USER", ""),
        "retry_interval": int(os.environ.get("MLFLOW_RETRY_INTERVAL", "60")),
        "log_artifacts": os.environ.get("MLFLOW_LOG_ARTIFACTS", "true").lower()
        == "true",
        "max_artifact_size": int(
            os.environ.get("MLFLOW_MAX_ARTIFACT_SIZE", "1000000")
        ),
    }


# -- Singleton client state --
_initialized = False
_enabled = False
_connected = False
_retry_task: asyncio.Task | None = None
_config: dict[str, Any] = {}


def is_enabled() -> bool:
    """Return True if MLflow tracing is active."""
    return _enabled and _connected


def _try_connect() -> bool:
    """Attempt to connect to the MLflow tracking server.

    Returns True if connection succeeds.
    """
    global _connected
    if not _mlflow_available or not _config.get("tracking_uri"):
        return False
    try:
        _mlflow.set_tracking_uri(_config["tracking_uri"])

        if _config.get("tracking_token"):
            os.environ["MLFLOW_TRACKING_TOKEN"] = _config["tracking_token"]

        _mlflow.set_experiment(_config["experiment_name"])
        _connected = True
        logger.info(
            f"MLflow tracing connected to {_config['tracking_uri']} "
            f"(experiment: {_config['experiment_name']})"
        )
        return True
    except Exception as e:
        _connected = False
        logger.warning(f"MLflow connection failed: {e}")
        return False


async def _retry_loop() -> None:
    """Background task that periodically retries connection."""
    interval = _config.get("retry_interval", 60)
    while not _connected:
        await asyncio.sleep(interval)
        if _try_connect():
            logger.info("MLflow reconnection succeeded")
            break
        else:
            logger.debug(f"MLflow reconnection failed, retrying in {interval}s")


def initialize() -> None:
    """Initialize MLflow integration. Call once at startup.

    Reads environment variables and attempts to connect.
    If the server is unreachable, starts a background retry loop.
    """
    global _initialized, _enabled, _config, _retry_task

    if _initialized:
        return

    _initialized = True
    _config = _get_config()

    if not _mlflow_available:
        logger.debug("MLflow not available (not installed)")
        return

    if not _config["tracking_uri"]:
        logger.debug("MLflow not configured (MLFLOW_TRACKING_URI not set)")
        return

    _enabled = True

    if not _try_connect():
        logger.warning(
            "MLflow server unreachable — tracing disabled, "
            f"retrying every {_config['retry_interval']}s"
        )
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                _retry_task = loop.create_task(_retry_loop())
        except RuntimeError:
            pass


# -- Span context managers --
# These are no-ops when MLflow is disabled or unavailable.


@contextmanager
def trace_span(name: str, attributes: dict[str, Any] | None = None):
    """Synchronous span context manager.

    Wraps mlflow.start_span() with graceful fallback.
    """
    if not is_enabled():
        yield None
        return

    span = None
    try:
        span = _mlflow.start_span(name=name)
        if attributes:
            span.set_attributes(attributes)
        user = mlflow_user_context.get()
        if user:
            span.set_attribute("user", user)
    except Exception:
        # Setup failure — yield None so the body still runs
        yield None
        return

    try:
        yield span
    except Exception as e:
        try:
            span.set_status("ERROR")
            span.set_attribute("error.message", str(e))
        except Exception:
            pass
        raise
    finally:
        try:
            span.end()
        except Exception:
            pass


@asynccontextmanager
async def trace_query(
    query: str, mode: str, params: dict[str, Any] | None = None
):
    """Trace a query operation as a parent span.

    Args:
        query: The query text
        mode: Query mode (local, global, hybrid, mix, naive, bypass)
        params: Query parameters to log as attributes
    """
    if not is_enabled():
        yield None
        return

    attrs = {"query_text": query, "mode": mode}
    if params:
        attrs.update(params)
    user = mlflow_user_context.get()
    if user:
        attrs["user"] = user

    trace = None
    try:
        trace = _mlflow.start_trace(name="lightrag.query", attributes=attrs)
    except Exception:
        yield None
        return

    try:
        yield trace
    except Exception as e:
        try:
            trace.set_status("ERROR")
            trace.set_attribute("error.message", str(e))
        except Exception:
            pass
        raise
    finally:
        try:
            _mlflow.end_trace(trace.request_id)
        except Exception:
            pass


@asynccontextmanager
async def trace_insert(doc_count: int = 0, metadata: dict[str, Any] | None = None):
    """Trace a document ingestion operation as a parent span.

    Args:
        doc_count: Number of documents being inserted
        metadata: Additional metadata to log
    """
    if not is_enabled():
        yield None
        return

    attrs = {"doc_count": doc_count}
    if metadata:
        attrs.update(metadata)
    user = mlflow_user_context.get()
    if user:
        attrs["user"] = user

    trace = None
    try:
        trace = _mlflow.start_trace(name="lightrag.insert", attributes=attrs)
    except Exception:
        yield None
        return

    try:
        yield trace
    except Exception as e:
        try:
            trace.set_status("ERROR")
            trace.set_attribute("error.message", str(e))
        except Exception:
            pass
        raise
    finally:
        try:
            _mlflow.end_trace(trace.request_id)
        except Exception:
            pass


def trace_llm_call(
    *,
    cache_hit: bool = False,
    model: str = "",
    tokens_in: int = 0,
    tokens_out: int = 0,
    latency_ms: float = 0,
    prompt_hash: str = "",
    cache_type: str = "",
) -> None:
    """Record an LLM call as a child span (fire-and-forget).

    This is called from use_llm_func_with_cache and direct LLM calls.
    """
    if not is_enabled():
        return

    try:
        attrs = {
            "cache_hit": cache_hit,
            "model": model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latency_ms": latency_ms,
            "prompt_hash": prompt_hash,
            "cache_type": cache_type,
        }
        user = mlflow_user_context.get()
        if user:
            attrs["user"] = user

        span = _mlflow.start_span(name="lightrag.llm_call")
        span.set_attributes(attrs)
        span.end()
    except Exception:
        pass


def trace_operation(
    name: str, attributes: dict[str, Any] | None = None
) -> None:
    """Record a pipeline operation as a child span (fire-and-forget).

    Used for chunking, extraction, merge, retrieval, reranking, etc.
    """
    if not is_enabled():
        return

    try:
        attrs = attributes or {}
        user = mlflow_user_context.get()
        if user:
            attrs["user"] = user

        span = _mlflow.start_span(name=name)
        span.set_attributes(attrs)
        span.end()
    except Exception:
        pass


def log_retrieval_artifacts(
    span: Any, raw_data: dict[str, Any] | None = None
) -> None:
    """Log retrieval context (entities, relationships, chunks) as span attributes.

    Called after query retrieval completes. Extracts structured data from
    raw_data and attaches it to the trace span. Large payloads are
    progressively truncated to stay within max_artifact_size.

    Args:
        span: MLflow trace span (or None if disabled).
        raw_data: Query result dict containing 'data' with entities,
            relationships, and chunks.
    """
    if not is_enabled() or span is None:
        return
    if not _config.get("log_artifacts", True):
        return

    try:
        import json

        data = (raw_data or {}).get("data", {})
        entities = data.get("entities", [])
        relationships = data.get("relationships", [])
        chunks = data.get("chunks", [])

        max_size = _config.get("max_artifact_size", 1_000_000)

        payload = {
            "entities": entities,
            "relationships": relationships,
            "chunks": chunks,
        }

        serialized = json.dumps(payload, default=str)

        # Progressive truncation: chunks first, then relationships, then entities
        if len(serialized) > max_size:
            payload["chunks"] = []
            payload["chunks_truncated"] = True
            serialized = json.dumps(payload, default=str)

        if len(serialized) > max_size:
            payload["relationships"] = []
            payload["relationships_truncated"] = True
            serialized = json.dumps(payload, default=str)

        if len(serialized) > max_size:
            payload["entities"] = []
            payload["entities_truncated"] = True
            serialized = json.dumps(payload, default=str)

        span.set_attribute("retrieval_context", serialized)
        span.set_attribute("retrieval_context_size_bytes", len(serialized))
    except Exception:
        pass


class TracedAsyncIterator:
    """Wraps an AsyncIterator to keep a trace span open until the stream completes.

    When the stream is fully consumed or an error occurs, the span is ended.
    This ensures streaming responses are properly traced.
    """

    def __init__(self, iterator: AsyncIterator, span: Any = None):
        self._iterator = iterator
        self._span = span
        self._start_time = time.perf_counter()
        self._chunk_count = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            chunk = await self._iterator.__anext__()
            self._chunk_count += 1
            return chunk
        except StopAsyncIteration:
            self._end_span()
            raise
        except Exception as e:
            self._end_span(error=str(e))
            raise

    def _end_span(self, error: str | None = None):
        if self._span is None:
            return
        try:
            elapsed_ms = (time.perf_counter() - self._start_time) * 1000
            self._span.set_attribute("stream_chunks", self._chunk_count)
            self._span.set_attribute("stream_latency_ms", elapsed_ms)
            if error:
                self._span.set_status("ERROR")
                self._span.set_attribute("error.message", error)
            self._span.end()
        except Exception:
            pass
        finally:
            self._span = None
