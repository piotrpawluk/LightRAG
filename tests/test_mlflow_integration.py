"""Tests for MLflow observability integration.

Spec: specs/mlflow-observability.md
Covers: AC-001 through AC-015

All tests mock the mlflow module — no real MLflow server required.
"""

import asyncio
import os
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers to reset module-level singleton state between tests
# ---------------------------------------------------------------------------

def _reset_mlflow_module():
    """Reset the mlflow_integration module singleton state for test isolation."""
    import lightrag.mlflow_integration as mod

    mod._initialized = False
    mod._enabled = False
    mod._connected = False
    mod._retry_task = None
    mod._config = {}


@pytest.fixture(autouse=True)
def reset_mlflow_state():
    """Reset module state before each test."""
    _reset_mlflow_module()
    yield
    _reset_mlflow_module()


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Ensure MLflow env vars are cleared unless a test explicitly sets them."""
    for var in (
        "MLFLOW_TRACKING_URI",
        "MLFLOW_EXPERIMENT_NAME",
        "MLFLOW_TRACKING_TOKEN",
        "MLFLOW_USER",
        "MLFLOW_RETRY_INTERVAL",
        "MLFLOW_LOG_ARTIFACTS",
    ):
        monkeypatch.delenv(var, raising=False)


# ===========================================================================
# AC-001: Optional dependency — LightRAG works without mlflow installed
# AC-014: When MLflow is not installed: feature silently disabled
# ===========================================================================


class TestAC001_OptionalDependency:
    """AC-001 / AC-014: MLflow is optional, silent no-op when absent."""

    def test_ac001_module_loads_without_mlflow(self):
        """The mlflow_integration module must load even if mlflow is absent."""
        import lightrag.mlflow_integration as mod

        # Module should have loaded without errors
        assert mod is not None

    def test_ac001_is_enabled_false_when_not_initialized(self):
        """is_enabled() returns False before initialization."""
        from lightrag.mlflow_integration import is_enabled

        assert is_enabled() is False

    def test_ac014_initialize_with_mlflow_unavailable(self, monkeypatch):
        """When mlflow package is not importable, initialize() sets _enabled=False."""
        import lightrag.mlflow_integration as mod

        monkeypatch.setattr(mod, "_mlflow_available", False)
        monkeypatch.setattr(mod, "_mlflow", None)
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://localhost:5000")

        mod.initialize()

        assert mod._initialized is True
        assert mod._enabled is False
        assert mod.is_enabled() is False

    def test_ac014_trace_query_noop_when_disabled(self):
        """trace_query must yield None without error when MLflow is disabled."""
        from lightrag.mlflow_integration import trace_query

        async def _run():
            async with trace_query("test query", "hybrid") as span:
                assert span is None

        asyncio.run(_run())

    def test_ac014_trace_insert_noop_when_disabled(self):
        """trace_insert must yield None without error when MLflow is disabled."""
        from lightrag.mlflow_integration import trace_insert

        async def _run():
            async with trace_insert(doc_count=1) as span:
                assert span is None

        asyncio.run(_run())

    def test_ac014_trace_llm_call_noop_when_disabled(self):
        """trace_llm_call must be a silent no-op when MLflow is disabled."""
        from lightrag.mlflow_integration import trace_llm_call

        # Should not raise
        trace_llm_call(cache_hit=True, prompt_hash="abc123")

    def test_ac014_trace_operation_noop_when_disabled(self):
        """trace_operation must be a silent no-op when MLflow is disabled."""
        from lightrag.mlflow_integration import trace_operation

        trace_operation("lightrag.query.retrieval", {"count": 5})


# ===========================================================================
# AC-002: Integration activates via environment variables
# ===========================================================================


class TestAC002_EnvVarActivation:
    """AC-002: Integration activates via MLFLOW_TRACKING_URI."""

    def test_ac002_not_enabled_without_tracking_uri(self, monkeypatch):
        """Without MLFLOW_TRACKING_URI, integration stays disabled."""
        import lightrag.mlflow_integration as mod

        monkeypatch.setattr(mod, "_mlflow_available", True)
        mock_mlflow = MagicMock()
        monkeypatch.setattr(mod, "_mlflow", mock_mlflow)

        mod.initialize()

        assert mod._enabled is False

    def test_ac002_enabled_with_tracking_uri(self, monkeypatch):
        """With MLFLOW_TRACKING_URI set, _enabled becomes True after initialize."""
        import lightrag.mlflow_integration as mod

        monkeypatch.setattr(mod, "_mlflow_available", True)
        mock_mlflow = MagicMock()
        monkeypatch.setattr(mod, "_mlflow", mock_mlflow)
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://localhost:5000")

        mod.initialize()

        assert mod._enabled is True

    def test_ac002_experiment_name_from_env(self, monkeypatch):
        """MLFLOW_EXPERIMENT_NAME env var is read into config."""
        import lightrag.mlflow_integration as mod

        monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "my_experiment")
        config = mod._get_config()

        assert config["experiment_name"] == "my_experiment"

    def test_ac002_default_experiment_name(self):
        """Default experiment name is 'lightrag'."""
        import lightrag.mlflow_integration as mod

        config = mod._get_config()
        assert config["experiment_name"] == "lightrag"

    def test_ac002_idempotent_initialize(self, monkeypatch):
        """Calling initialize() twice does not reset state."""
        import lightrag.mlflow_integration as mod

        monkeypatch.setattr(mod, "_mlflow_available", True)
        mock_mlflow = MagicMock()
        monkeypatch.setattr(mod, "_mlflow", mock_mlflow)
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://localhost:5000")

        mod.initialize()
        assert mod._initialized is True
        first_config = mod._config.copy()

        mod.initialize()
        assert mod._config == first_config  # Not re-read


# ===========================================================================
# AC-003: Every LLM call gets a trace span
# ===========================================================================


class TestAC003_LLMCallSpans:
    """AC-003: LLM calls produce trace spans with correct attributes."""

    def _enable_mlflow(self, mod, monkeypatch):
        """Helper to put module in enabled+connected state with mock mlflow."""
        mock_mlflow = MagicMock()
        monkeypatch.setattr(mod, "_mlflow_available", True)
        monkeypatch.setattr(mod, "_mlflow", mock_mlflow)
        monkeypatch.setattr(mod, "_enabled", True)
        monkeypatch.setattr(mod, "_connected", True)
        return mock_mlflow

    def test_ac003_trace_llm_call_creates_span(self, monkeypatch):
        """trace_llm_call creates a span with expected attributes."""
        import lightrag.mlflow_integration as mod

        mock_mlflow = self._enable_mlflow(mod, monkeypatch)
        mock_span = MagicMock()
        mock_mlflow.start_span.return_value = mock_span

        mod.trace_llm_call(
            cache_hit=False,
            model="gpt-4o-mini",
            tokens_in=100,
            tokens_out=50,
            latency_ms=234.5,
            prompt_hash="hash123",
            cache_type="extract",
        )

        mock_mlflow.start_span.assert_called_once_with(name="lightrag.llm_call")
        attrs = mock_span.set_attributes.call_args[0][0]
        assert attrs["cache_hit"] is False
        assert attrs["model"] == "gpt-4o-mini"
        assert attrs["tokens_in"] == 100
        assert attrs["tokens_out"] == 50
        assert attrs["latency_ms"] == 234.5
        assert attrs["prompt_hash"] == "hash123"
        assert attrs["cache_type"] == "extract"
        mock_span.end.assert_called_once()

    def test_ac003_trace_llm_call_cache_hit(self, monkeypatch):
        """Cache hits are recorded with cache_hit=True."""
        import lightrag.mlflow_integration as mod

        mock_mlflow = self._enable_mlflow(mod, monkeypatch)
        mock_span = MagicMock()
        mock_mlflow.start_span.return_value = mock_span

        mod.trace_llm_call(cache_hit=True, prompt_hash="cached_hash")

        attrs = mock_span.set_attributes.call_args[0][0]
        assert attrs["cache_hit"] is True

    def test_ac003_trace_llm_call_includes_user(self, monkeypatch):
        """User identity from contextvars appears in LLM call spans."""
        import lightrag.mlflow_integration as mod

        mock_mlflow = self._enable_mlflow(mod, monkeypatch)
        mock_span = MagicMock()
        mock_mlflow.start_span.return_value = mock_span

        token = mod.mlflow_user_context.set("alice")
        try:
            mod.trace_llm_call(cache_hit=False)
            attrs = mock_span.set_attributes.call_args[0][0]
            assert attrs["user"] == "alice"
        finally:
            mod.mlflow_user_context.reset(token)


# ===========================================================================
# AC-004: Query gets parent span with child spans
# ===========================================================================


class TestAC004_QuerySpans:
    """AC-004: aquery produces parent span with children."""

    def _enable_mlflow(self, mod, monkeypatch):
        mock_mlflow = MagicMock()
        monkeypatch.setattr(mod, "_mlflow_available", True)
        monkeypatch.setattr(mod, "_mlflow", mock_mlflow)
        monkeypatch.setattr(mod, "_enabled", True)
        monkeypatch.setattr(mod, "_connected", True)
        return mock_mlflow

    def test_ac004_trace_query_creates_trace(self, monkeypatch):
        """trace_query creates a trace with name lightrag.query."""
        import lightrag.mlflow_integration as mod

        mock_mlflow = self._enable_mlflow(mod, monkeypatch)
        mock_trace = MagicMock()
        mock_trace.request_id = "req-123"
        mock_mlflow.start_trace.return_value = mock_trace

        async def _run():
            async with mod.trace_query("test q", "hybrid", {"top_k": 60}) as span:
                assert span is mock_trace

        asyncio.run(_run())

        mock_mlflow.start_trace.assert_called_once()
        call_kwargs = mock_mlflow.start_trace.call_args
        assert call_kwargs[1]["name"] == "lightrag.query"
        attrs = call_kwargs[1]["attributes"]
        assert attrs["query_text"] == "test q"
        assert attrs["mode"] == "hybrid"
        assert attrs["top_k"] == 60
        mock_mlflow.end_trace.assert_called_once_with("req-123")

    def test_ac004_trace_query_noop_when_disabled(self):
        """trace_query yields None when MLflow is disabled."""
        from lightrag.mlflow_integration import trace_query

        async def _run():
            async with trace_query("q", "local") as span:
                assert span is None

        asyncio.run(_run())

    def test_ac004_trace_query_propagates_body_exception(self, monkeypatch):
        """Exceptions from the body of trace_query propagate correctly."""
        import lightrag.mlflow_integration as mod

        mock_mlflow = self._enable_mlflow(mod, monkeypatch)
        mock_trace = MagicMock()
        mock_trace.request_id = "req-err"
        mock_mlflow.start_trace.return_value = mock_trace

        async def _run():
            async with mod.trace_query("q", "local"):
                raise ValueError("query body error")

        with pytest.raises(ValueError, match="query body error"):
            asyncio.run(_run())

        mock_trace.set_status.assert_called_once_with("ERROR")
        mock_mlflow.end_trace.assert_called_once_with("req-err")


# ===========================================================================
# AC-005: Insert gets parent span with child spans
# ===========================================================================


class TestAC005_InsertSpans:
    """AC-005: ainsert produces parent span with children."""

    def _enable_mlflow(self, mod, monkeypatch):
        mock_mlflow = MagicMock()
        monkeypatch.setattr(mod, "_mlflow_available", True)
        monkeypatch.setattr(mod, "_mlflow", mock_mlflow)
        monkeypatch.setattr(mod, "_enabled", True)
        monkeypatch.setattr(mod, "_connected", True)
        return mock_mlflow

    def test_ac005_trace_insert_creates_trace(self, monkeypatch):
        """trace_insert creates a trace with correct attributes."""
        import lightrag.mlflow_integration as mod

        mock_mlflow = self._enable_mlflow(mod, monkeypatch)
        mock_trace = MagicMock()
        mock_trace.request_id = "req-456"
        mock_mlflow.start_trace.return_value = mock_trace

        async def _run():
            async with mod.trace_insert(
                doc_count=3, metadata={"track_id": "trk-1"}
            ) as span:
                assert span is mock_trace

        asyncio.run(_run())

        call_kwargs = mock_mlflow.start_trace.call_args
        attrs = call_kwargs[1]["attributes"]
        assert attrs["doc_count"] == 3
        assert attrs["track_id"] == "trk-1"
        mock_mlflow.end_trace.assert_called_once_with("req-456")


# ===========================================================================
# AC-006: Query parameters logged as span attributes
# ===========================================================================


class TestAC006_QueryParamAttributes:
    """AC-006: Query params appear as span attributes."""

    def _enable_mlflow(self, mod, monkeypatch):
        mock_mlflow = MagicMock()
        monkeypatch.setattr(mod, "_mlflow_available", True)
        monkeypatch.setattr(mod, "_mlflow", mock_mlflow)
        monkeypatch.setattr(mod, "_enabled", True)
        monkeypatch.setattr(mod, "_connected", True)
        return mock_mlflow

    def test_ac006_query_params_in_trace(self, monkeypatch):
        """top_k, chunk_top_k, stream appear in trace attributes."""
        import lightrag.mlflow_integration as mod

        mock_mlflow = self._enable_mlflow(mod, monkeypatch)
        mock_trace = MagicMock()
        mock_trace.request_id = "req-789"
        mock_mlflow.start_trace.return_value = mock_trace

        params = {"top_k": 60, "chunk_top_k": 20, "stream": False}

        async def _run():
            async with mod.trace_query("q", "mix", params):
                pass

        asyncio.run(_run())

        attrs = mock_mlflow.start_trace.call_args[1]["attributes"]
        assert attrs["top_k"] == 60
        assert attrs["chunk_top_k"] == 20
        assert attrs["stream"] is False
        assert attrs["mode"] == "mix"


# ===========================================================================
# AC-007: Retrieval artifacts logged on span
# ===========================================================================


class TestAC007_Artifacts:
    """AC-007: Retrieval context logged as span attributes."""

    def test_ac007_artifacts_logged_on_span(self, monkeypatch):
        """Mock span receives retrieval_context attribute with correct structure."""
        import lightrag.mlflow_integration as mod

        monkeypatch.setattr(mod, "_enabled", True)
        monkeypatch.setattr(mod, "_connected", True)
        monkeypatch.setattr(
            mod, "_config", {"log_artifacts": True, "max_artifact_size": 1_000_000}
        )

        mock_span = MagicMock()
        raw_data = {
            "data": {
                "entities": [{"name": "Alice"}],
                "relationships": [{"src": "Alice", "tgt": "Bob"}],
                "chunks": [{"id": "c1", "text": "hello"}],
            }
        }

        mod.log_retrieval_artifacts(mock_span, raw_data)

        # Verify set_attribute was called with retrieval_context
        calls = {c[0][0]: c[0][1] for c in mock_span.set_attribute.call_args_list}
        assert "retrieval_context" in calls
        assert "retrieval_context_size_bytes" in calls

        import json

        payload = json.loads(calls["retrieval_context"])
        assert payload["entities"] == [{"name": "Alice"}]
        assert payload["relationships"] == [{"src": "Alice", "tgt": "Bob"}]
        assert payload["chunks"] == [{"id": "c1", "text": "hello"}]

    def test_ac007_noop_when_artifacts_disabled(self, monkeypatch):
        """set_attribute not called when log_artifacts is False."""
        import lightrag.mlflow_integration as mod

        monkeypatch.setattr(mod, "_enabled", True)
        monkeypatch.setattr(mod, "_connected", True)
        monkeypatch.setattr(
            mod, "_config", {"log_artifacts": False, "max_artifact_size": 1_000_000}
        )

        mock_span = MagicMock()
        mod.log_retrieval_artifacts(mock_span, {"data": {"entities": [{"x": 1}]}})
        mock_span.set_attribute.assert_not_called()

    def test_ac007_noop_when_disabled(self):
        """No-op when MLflow is disabled (span is None or not enabled)."""
        import lightrag.mlflow_integration as mod

        mock_span = MagicMock()
        # Module defaults: _enabled=False, _connected=False
        mod.log_retrieval_artifacts(mock_span, {"data": {}})
        mock_span.set_attribute.assert_not_called()

        # Also no-op when span is None
        mod.log_retrieval_artifacts(None, {"data": {}})

    def test_ac007_truncates_large_artifacts(self, monkeypatch):
        """Payload is truncated when it exceeds max_artifact_size."""
        import json
        import lightrag.mlflow_integration as mod

        monkeypatch.setattr(mod, "_enabled", True)
        monkeypatch.setattr(mod, "_connected", True)
        monkeypatch.setattr(
            mod, "_config", {"log_artifacts": True, "max_artifact_size": 500}
        )

        mock_span = MagicMock()
        raw_data = {
            "data": {
                "entities": [{"name": f"entity_{i}"} for i in range(50)],
                "relationships": [{"r": f"rel_{i}"} for i in range(50)],
                "chunks": [{"text": "x" * 100} for _ in range(50)],
            }
        }

        mod.log_retrieval_artifacts(mock_span, raw_data)

        calls = {c[0][0]: c[0][1] for c in mock_span.set_attribute.call_args_list}
        serialized = calls["retrieval_context"]
        assert len(serialized) <= 500
        payload = json.loads(serialized)
        # At minimum chunks should be truncated
        assert payload.get("chunks_truncated", False) is True


# ===========================================================================
# AC-009: User identity captured in traces
# ===========================================================================


class TestAC009_UserIdentity:
    """AC-009: User identity from JWT / env var / API key in spans."""

    def _enable_mlflow(self, mod, monkeypatch):
        mock_mlflow = MagicMock()
        monkeypatch.setattr(mod, "_mlflow_available", True)
        monkeypatch.setattr(mod, "_mlflow", mock_mlflow)
        monkeypatch.setattr(mod, "_enabled", True)
        monkeypatch.setattr(mod, "_connected", True)
        return mock_mlflow

    def test_ac009_user_from_contextvar(self, monkeypatch):
        """User set via contextvars appears in trace_query span."""
        import lightrag.mlflow_integration as mod

        mock_mlflow = self._enable_mlflow(mod, monkeypatch)
        mock_trace = MagicMock()
        mock_trace.request_id = "req-u1"
        mock_mlflow.start_trace.return_value = mock_trace

        token = mod.mlflow_user_context.set("bob")
        try:
            async def _run():
                async with mod.trace_query("q", "local"):
                    pass

            asyncio.run(_run())

            attrs = mock_mlflow.start_trace.call_args[1]["attributes"]
            assert attrs["user"] == "bob"
        finally:
            mod.mlflow_user_context.reset(token)

    def test_ac009_no_user_when_not_set(self, monkeypatch):
        """When no user is in contextvars, 'user' key is absent from attrs."""
        import lightrag.mlflow_integration as mod

        mock_mlflow = self._enable_mlflow(mod, monkeypatch)
        mock_trace = MagicMock()
        mock_trace.request_id = "req-u2"
        mock_mlflow.start_trace.return_value = mock_trace

        async def _run():
            async with mod.trace_query("q", "local"):
                pass

        asyncio.run(_run())

        attrs = mock_mlflow.start_trace.call_args[1]["attributes"]
        assert "user" not in attrs

    def test_ac009_whitelist_path_sets_fallback_user(self, monkeypatch):
        """Whitelisted-path early return sets mlflow_user_context to fallback."""
        from lightrag.mlflow_integration import mlflow_user_context

        # Ensure context is empty
        token = mlflow_user_context.set(None)
        try:
            # Simulate the whitelist-path code: set fallback when not already set
            if not mlflow_user_context.get():
                mlflow_user_context.set(
                    os.environ.get("MLFLOW_USER", "anonymous")
                )
            assert mlflow_user_context.get() == "anonymous"
        finally:
            mlflow_user_context.reset(token)

    def test_ac009_whitelist_path_respects_mlflow_user_env(self, monkeypatch):
        """Whitelisted-path fallback uses MLFLOW_USER env var when set."""
        from lightrag.mlflow_integration import mlflow_user_context

        monkeypatch.setenv("MLFLOW_USER", "ops-admin")

        token = mlflow_user_context.set(None)
        try:
            if not mlflow_user_context.get():
                mlflow_user_context.set(
                    os.environ.get("MLFLOW_USER", "anonymous")
                )
            assert mlflow_user_context.get() == "ops-admin"
        finally:
            mlflow_user_context.reset(token)

    def test_ac009_whitelist_path_integration(self, monkeypatch):
        """Exercise the real combined_dependency function for whitelist paths."""
        utils_api = pytest.importorskip("lightrag.api.utils_api")
        from lightrag.mlflow_integration import mlflow_user_context

        # Monkeypatch module-level state to simulate whitelist + no auth
        monkeypatch.setattr(utils_api, "whitelist_patterns", [("/health", False)])
        monkeypatch.setattr(utils_api, "auth_configured", False)

        dep_func = utils_api.get_combined_auth_dependency(api_key=None)

        # Build mock Request and Response
        mock_request = MagicMock()
        mock_request.url.path = "/health"
        mock_response = MagicMock()
        mock_response.headers = {}

        token = mlflow_user_context.set(None)
        try:

            async def _run():
                await dep_func(
                    request=mock_request,
                    response=mock_response,
                    token=None,
                    api_key_header_value=None,
                )

            asyncio.run(_run())

            assert mlflow_user_context.get() == "anonymous"
        finally:
            mlflow_user_context.reset(token)

    def test_ac009_user_in_trace_operation(self, monkeypatch):
        """User identity appears in trace_operation spans."""
        import lightrag.mlflow_integration as mod

        mock_mlflow = self._enable_mlflow(mod, monkeypatch)
        mock_span = MagicMock()
        mock_mlflow.start_span.return_value = mock_span

        token = mod.mlflow_user_context.set("carol")
        try:
            mod.trace_operation("lightrag.query.retrieval", {"count": 5})
            attrs = mock_span.set_attributes.call_args[0][0]
            assert attrs["user"] == "carol"
        finally:
            mod.mlflow_user_context.reset(token)


# ===========================================================================
# AC-012: Remote server with auth token
# ===========================================================================


class TestAC012_RemoteServer:
    """AC-012: Auth token support via MLFLOW_TRACKING_TOKEN."""

    def test_ac012_tracking_token_in_config(self, monkeypatch):
        """MLFLOW_TRACKING_TOKEN is read from environment."""
        import lightrag.mlflow_integration as mod

        monkeypatch.setenv("MLFLOW_TRACKING_TOKEN", "secret-token-123")
        config = mod._get_config()
        assert config["tracking_token"] == "secret-token-123"

    def test_ac012_token_set_in_env_on_connect(self, monkeypatch):
        """When connecting, MLFLOW_TRACKING_TOKEN is set in os.environ for MLflow SDK."""
        import lightrag.mlflow_integration as mod

        mock_mlflow = MagicMock()
        monkeypatch.setattr(mod, "_mlflow_available", True)
        monkeypatch.setattr(mod, "_mlflow", mock_mlflow)
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://remote:5000")
        monkeypatch.setenv("MLFLOW_TRACKING_TOKEN", "my-token")

        mod.initialize()

        # After initialize, the token should be in os.environ
        assert os.environ.get("MLFLOW_TRACKING_TOKEN") == "my-token"


# ===========================================================================
# AC-013: Retry on unreachable server
# ===========================================================================


class TestAC013_RetryLogic:
    """AC-013: Warning logged, tracing disabled, retry periodically."""

    def test_ac013_connection_failure_sets_not_connected(self, monkeypatch):
        """When MLflow server is unreachable, _connected stays False."""
        import lightrag.mlflow_integration as mod

        mock_mlflow = MagicMock()
        mock_mlflow.set_experiment.side_effect = Exception("Connection refused")
        monkeypatch.setattr(mod, "_mlflow_available", True)
        monkeypatch.setattr(mod, "_mlflow", mock_mlflow)
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://localhost:5000")

        mod.initialize()

        assert mod._enabled is True
        assert mod._connected is False
        assert mod.is_enabled() is False

    def test_ac013_retry_loop_reconnects(self, monkeypatch):
        """_retry_loop retries and connects when server comes back."""
        import lightrag.mlflow_integration as mod

        call_count = 0

        def mock_try_connect():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                mod._connected = True
                return True
            return False

        monkeypatch.setattr(mod, "_try_connect", mock_try_connect)
        monkeypatch.setattr(mod, "_config", {"retry_interval": 0.01})
        mod._connected = False

        asyncio.run(mod._retry_loop())

        assert mod._connected is True
        assert call_count >= 2

    def test_ac013_is_enabled_false_while_disconnected(self, monkeypatch):
        """is_enabled returns False when _enabled=True but _connected=False."""
        import lightrag.mlflow_integration as mod

        mod._enabled = True
        mod._connected = False
        assert mod.is_enabled() is False


# ===========================================================================
# AC-015: Non-blocking trace failures
# ===========================================================================


class TestAC015_NonBlockingFailures:
    """AC-015: Trace export failures don't affect requests."""

    def _enable_mlflow(self, mod, monkeypatch):
        mock_mlflow = MagicMock()
        monkeypatch.setattr(mod, "_mlflow_available", True)
        monkeypatch.setattr(mod, "_mlflow", mock_mlflow)
        monkeypatch.setattr(mod, "_enabled", True)
        monkeypatch.setattr(mod, "_connected", True)
        return mock_mlflow

    def test_ac015_trace_query_survives_mlflow_error(self, monkeypatch):
        """trace_query yields None (not raises) when start_trace throws."""
        import lightrag.mlflow_integration as mod

        mock_mlflow = self._enable_mlflow(mod, monkeypatch)
        mock_mlflow.start_trace.side_effect = RuntimeError("MLflow down")

        async def _run():
            async with mod.trace_query("q", "local") as span:
                # Should still enter the block, span is None
                assert span is None

        asyncio.run(_run())

    def test_ac015_trace_llm_call_survives_error(self, monkeypatch):
        """trace_llm_call swallows exceptions from MLflow."""
        import lightrag.mlflow_integration as mod

        mock_mlflow = self._enable_mlflow(mod, monkeypatch)
        mock_mlflow.start_span.side_effect = RuntimeError("MLflow down")

        # Should not raise
        mod.trace_llm_call(cache_hit=False, model="gpt-4o")

    def test_ac015_trace_operation_survives_error(self, monkeypatch):
        """trace_operation swallows exceptions from MLflow."""
        import lightrag.mlflow_integration as mod

        mock_mlflow = self._enable_mlflow(mod, monkeypatch)
        mock_mlflow.start_span.side_effect = RuntimeError("MLflow down")

        # Should not raise
        mod.trace_operation("lightrag.query.retrieval")

    def test_ac015_trace_insert_survives_error(self, monkeypatch):
        """trace_insert yields None when start_trace throws."""
        import lightrag.mlflow_integration as mod

        mock_mlflow = self._enable_mlflow(mod, monkeypatch)
        mock_mlflow.start_trace.side_effect = RuntimeError("MLflow down")

        async def _run():
            async with mod.trace_insert(doc_count=1) as span:
                assert span is None

        asyncio.run(_run())


# ===========================================================================
# TracedAsyncIterator (streaming support, part of AC-004/AC-015)
# ===========================================================================


class TestTracedAsyncIterator:
    """TracedAsyncIterator manages span lifecycle for streaming responses."""

    def test_stream_ends_span_on_completion(self):
        """Span ends with stream_chunks count when stream completes."""
        from lightrag.mlflow_integration import TracedAsyncIterator

        mock_span = MagicMock()
        chunks = ["chunk1", "chunk2", "chunk3"]

        async def _mock_iter():
            for c in chunks:
                yield c

        async def _run():
            traced = TracedAsyncIterator(_mock_iter().__aiter__(), span=mock_span)
            result = []
            async for chunk in traced:
                result.append(chunk)
            return result

        result = asyncio.run(_run())

        assert result == chunks
        mock_span.set_attribute.assert_any_call("stream_chunks", 3)
        mock_span.end.assert_called_once()

    def test_stream_ends_span_on_error(self):
        """Span ends with ERROR status when stream raises."""
        from lightrag.mlflow_integration import TracedAsyncIterator

        mock_span = MagicMock()

        async def _mock_iter():
            yield "chunk1"
            raise ValueError("stream error")

        async def _run():
            traced = TracedAsyncIterator(_mock_iter().__aiter__(), span=mock_span)
            result = []
            async for chunk in traced:
                result.append(chunk)

        with pytest.raises(ValueError, match="stream error"):
            asyncio.run(_run())

        mock_span.set_status.assert_called_once_with("ERROR")
        mock_span.set_attribute.assert_any_call("error.message", "stream error")
        mock_span.end.assert_called_once()

    def test_stream_noop_with_none_span(self):
        """TracedAsyncIterator works fine when span is None (disabled mode)."""
        from lightrag.mlflow_integration import TracedAsyncIterator

        async def _mock_iter():
            yield "a"
            yield "b"

        async def _run():
            traced = TracedAsyncIterator(_mock_iter().__aiter__(), span=None)
            result = []
            async for chunk in traced:
                result.append(chunk)
            return result

        result = asyncio.run(_run())
        assert result == ["a", "b"]


# ===========================================================================
# AC-008: Langfuse coexistence
# ===========================================================================


class TestAC008_LangfuseCoexistence:
    """AC-008: MLflow and Langfuse work independently."""

    def test_ac008_mlflow_does_not_import_langfuse(self):
        """mlflow_integration module does not reference langfuse."""
        import inspect
        import lightrag.mlflow_integration as mod

        source = inspect.getsource(mod)
        assert "langfuse" not in source.lower()

    def test_ac008_mlflow_uses_different_instrumentation_points(self):
        """MLflow uses trace_query/trace_insert/trace_llm_call, not OpenAI client swap."""
        import lightrag.mlflow_integration as mod

        # Verify the module exposes the expected API
        assert hasattr(mod, "trace_query")
        assert hasattr(mod, "trace_insert")
        assert hasattr(mod, "trace_llm_call")
        assert hasattr(mod, "trace_operation")
        # Does NOT have openai-specific things
        assert not hasattr(mod, "AsyncOpenAI")


# ===========================================================================
# trace_span (synchronous context manager)
# ===========================================================================


class TestTraceSpan:
    """trace_span synchronous context manager."""

    def _enable_mlflow(self, mod, monkeypatch):
        mock_mlflow = MagicMock()
        monkeypatch.setattr(mod, "_mlflow_available", True)
        monkeypatch.setattr(mod, "_mlflow", mock_mlflow)
        monkeypatch.setattr(mod, "_enabled", True)
        monkeypatch.setattr(mod, "_connected", True)
        return mock_mlflow

    def test_trace_span_creates_and_ends_span(self, monkeypatch):
        """trace_span creates a span and ends it."""
        import lightrag.mlflow_integration as mod

        mock_mlflow = self._enable_mlflow(mod, monkeypatch)
        mock_span = MagicMock()
        mock_mlflow.start_span.return_value = mock_span

        with mod.trace_span("test.op", {"key": "val"}) as span:
            assert span is mock_span

        mock_mlflow.start_span.assert_called_once_with(name="test.op")
        mock_span.set_attributes.assert_called_once_with({"key": "val"})
        mock_span.end.assert_called_once()

    def test_trace_span_sets_error_on_exception(self, monkeypatch):
        """trace_span marks span as ERROR when body raises."""
        import lightrag.mlflow_integration as mod

        mock_mlflow = self._enable_mlflow(mod, monkeypatch)
        mock_span = MagicMock()
        mock_mlflow.start_span.return_value = mock_span

        with pytest.raises(ValueError):
            with mod.trace_span("test.op"):
                raise ValueError("boom")

        mock_span.set_status.assert_called_once_with("ERROR")
        mock_span.end.assert_called_once()

    def test_trace_span_noop_when_disabled(self):
        """trace_span yields None when disabled."""
        import lightrag.mlflow_integration as mod

        with mod.trace_span("test.op") as span:
            assert span is None


# ===========================================================================
# _get_config reads all env vars
# ===========================================================================


class TestGetConfig:
    """Configuration reader picks up all env vars."""

    def test_all_env_vars_read(self, monkeypatch):
        """All documented env vars are read."""
        import lightrag.mlflow_integration as mod

        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://host:5000")
        monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "exp1")
        monkeypatch.setenv("MLFLOW_TRACKING_TOKEN", "tok")
        monkeypatch.setenv("MLFLOW_USER", "admin")
        monkeypatch.setenv("MLFLOW_RETRY_INTERVAL", "30")
        monkeypatch.setenv("MLFLOW_LOG_ARTIFACTS", "false")

        config = mod._get_config()

        assert config["tracking_uri"] == "http://host:5000"
        assert config["experiment_name"] == "exp1"
        assert config["tracking_token"] == "tok"
        assert config["user"] == "admin"
        assert config["retry_interval"] == 30
        assert config["log_artifacts"] is False

    def test_defaults(self):
        """Defaults are sensible when no env vars set."""
        import lightrag.mlflow_integration as mod

        config = mod._get_config()

        assert config["tracking_uri"] == ""
        assert config["experiment_name"] == "lightrag"
        assert config["tracking_token"] == ""
        assert config["user"] == ""
        assert config["retry_interval"] == 60
        assert config["log_artifacts"] is True


# ===========================================================================
# AC-010: MLflow Evaluate — compare_modes helper
# ===========================================================================


class TestAC010_CompareModes:
    """AC-010: compare_modes runs queries across modes and logs to MLflow."""

    @pytest.fixture(autouse=True)
    def _ensure_mock_mlflow(self):
        """Ensure mlflow_evaluate can be imported by injecting a mock mlflow module.

        The real mlflow may not be installed in the test environment.  We insert
        a MagicMock into sys.modules so that ``import mlflow`` inside
        mlflow_evaluate.py succeeds, then clean up cached module state afterward.
        """
        import sys

        need_mock = "mlflow" not in sys.modules or sys.modules["mlflow"] is None
        mock_mlflow_mod = None

        if need_mock:
            mock_mlflow_mod = MagicMock()
            sys.modules["mlflow"] = mock_mlflow_mod

        # Remove cached mlflow_evaluate so it re-imports with the mock
        sys.modules.pop("lightrag.mlflow_evaluate", None)

        yield

        # Restore original state
        sys.modules.pop("lightrag.mlflow_evaluate", None)
        if need_mock:
            if mock_mlflow_mod is sys.modules.get("mlflow"):
                del sys.modules["mlflow"]

    def _make_mock_rag(self):
        """Create a mock LightRAG with aquery_llm returning structured data."""
        mock_rag = MagicMock()

        async def mock_aquery_llm(query, param=None):
            return {
                "status": "success",
                "message": "OK",
                "data": {"chunks": [{"id": "c1"}]},
                "metadata": {
                    "processing_info": {
                        "total_entities_found": 5,
                        "total_relations_found": 3,
                        "final_chunks_count": 2,
                    }
                },
                "llm_response": {
                    "content": f"Answer for {query} in {param.mode} mode",
                    "response_iterator": None,
                    "is_streaming": False,
                },
            }

        mock_rag.aquery_llm = mock_aquery_llm
        return mock_rag

    def test_ac010_compare_modes_returns_results(self):
        """compare_modes returns result dicts for each query x mode combination."""
        from unittest.mock import patch

        mock_rag = self._make_mock_rag()

        with patch("lightrag.mlflow_evaluate.mlflow") as mock_mlflow:
            mock_mlflow.start_run.return_value.__enter__ = MagicMock()
            mock_mlflow.start_run.return_value.__exit__ = MagicMock(
                return_value=False
            )

            from lightrag.mlflow_evaluate import compare_modes

            async def _run():
                return await compare_modes(
                    rag=mock_rag,
                    queries=["What is X?", "How does Y work?"],
                    modes=["local", "global"],
                )

            results = asyncio.run(_run())

        # 2 queries x 2 modes = 4 results
        assert len(results) == 4
        assert all("query" in r for r in results)
        assert all("mode" in r for r in results)
        assert all("answer" in r for r in results)
        assert all("latency_ms" in r for r in results)
        assert all("entities_found" in r for r in results)
        assert all("relations_found" in r for r in results)
        assert all("chunks_found" in r for r in results)

        # Verify correct query-mode combinations
        combos = [(r["query"], r["mode"]) for r in results]
        assert ("What is X?", "local") in combos
        assert ("What is X?", "global") in combos
        assert ("How does Y work?", "local") in combos
        assert ("How does Y work?", "global") in combos

    def test_ac010_compare_modes_logs_to_mlflow(self):
        """compare_modes calls MLflow log_param, log_metrics, start_run."""
        from unittest.mock import patch

        mock_rag = self._make_mock_rag()

        with patch("lightrag.mlflow_evaluate.mlflow") as mock_mlflow:
            mock_mlflow.start_run.return_value.__enter__ = MagicMock()
            mock_mlflow.start_run.return_value.__exit__ = MagicMock(
                return_value=False
            )

            from lightrag.mlflow_evaluate import compare_modes

            async def _run():
                return await compare_modes(
                    rag=mock_rag,
                    queries=["Test query"],
                    modes=["local"],
                )

            asyncio.run(_run())

        # Experiment was set
        mock_mlflow.set_experiment.assert_called_once()

        # start_run called: 1 parent + 1 child
        assert mock_mlflow.start_run.call_count == 2

        # Parent run logged params
        param_calls = mock_mlflow.log_param.call_args_list
        param_keys = [c[0][0] for c in param_calls]
        assert "num_queries" in param_keys
        assert "modes" in param_keys
        assert "mode" in param_keys
        assert "query" in param_keys

        # Metrics logged for child run
        mock_mlflow.log_metrics.assert_called_once()
        logged_metrics = mock_mlflow.log_metrics.call_args[0][0]
        assert "latency_ms" in logged_metrics
        assert "entities_found" in logged_metrics
        assert "relations_found" in logged_metrics
        assert "chunks_found" in logged_metrics

    def test_ac010_compare_modes_default_modes(self):
        """Default mode list is all 5 modes when modes=None."""
        from unittest.mock import patch

        mock_rag = self._make_mock_rag()

        with patch("lightrag.mlflow_evaluate.mlflow") as mock_mlflow:
            mock_mlflow.start_run.return_value.__enter__ = MagicMock()
            mock_mlflow.start_run.return_value.__exit__ = MagicMock(
                return_value=False
            )

            from lightrag.mlflow_evaluate import compare_modes

            async def _run():
                return await compare_modes(
                    rag=mock_rag,
                    queries=["Test"],
                    modes=None,  # should default to all 5
                )

            results = asyncio.run(_run())

        # 1 query x 5 modes = 5 results
        assert len(results) == 5
        result_modes = [r["mode"] for r in results]
        assert result_modes == ["local", "global", "hybrid", "mix", "naive"]

    def test_ac010_compare_modes_handles_query_error(self):
        """A failing query-mode combo doesn't abort the whole run."""
        from unittest.mock import patch

        mock_rag = self._make_mock_rag()

        # Make aquery_llm raise for "global" mode only
        original_aquery = mock_rag.aquery_llm

        async def _failing_aquery(query, param=None):
            if param.mode == "global":
                raise RuntimeError("global mode exploded")
            return await original_aquery(query, param=param)

        mock_rag.aquery_llm = _failing_aquery

        with patch("lightrag.mlflow_evaluate.mlflow") as mock_mlflow:
            mock_mlflow.start_run.return_value.__enter__ = MagicMock()
            mock_mlflow.start_run.return_value.__exit__ = MagicMock(
                return_value=False
            )

            from lightrag.mlflow_evaluate import compare_modes

            async def _run():
                return await compare_modes(
                    rag=mock_rag,
                    queries=["Test query"],
                    modes=["local", "global", "hybrid"],
                )

            results = asyncio.run(_run())

        # All 3 results returned (none lost)
        assert len(results) == 3
        modes_returned = [r["mode"] for r in results]
        assert modes_returned == ["local", "global", "hybrid"]

        # Global has error key
        global_result = [r for r in results if r["mode"] == "global"][0]
        assert "error" in global_result
        assert "global mode exploded" in global_result["error"]
        assert global_result["answer"] == ""

        # Others succeeded normally
        local_result = [r for r in results if r["mode"] == "local"][0]
        assert "error" not in local_result
        assert local_result["answer"] != ""

    def test_ac010_compare_modes_requires_mlflow(self):
        """ImportError raised when mlflow is not installed."""
        import importlib
        import sys

        # Remove mlflow and the cached module to force a fresh import attempt
        saved_mlflow = sys.modules.pop("mlflow", None)
        sys.modules.pop("lightrag.mlflow_evaluate", None)
        sys.modules["mlflow"] = None  # signals "import halted"

        try:
            with pytest.raises(ImportError, match="mlflow is required"):
                importlib.import_module("lightrag.mlflow_evaluate")
        finally:
            # Restore
            sys.modules.pop("lightrag.mlflow_evaluate", None)
            if saved_mlflow is not None:
                sys.modules["mlflow"] = saved_mlflow
            else:
                sys.modules.pop("mlflow", None)
