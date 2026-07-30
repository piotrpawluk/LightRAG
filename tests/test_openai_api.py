"""Offline tests for the OpenAI-compatible shim (/v1/models, /v1/chat/completions)."""

import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# lightrag.api.config argparses sys.argv at import time and chokes on pytest's
# arguments — import the router (which pulls config transitively) under a
# clean argv, same workaround family as test_token_auto_renewal.py.
_orig_argv = sys.argv
sys.argv = ["lightrag-test"]
try:
    from lightrag.api.routers.openai_api import OpenAIAPI
finally:
    sys.argv = _orig_argv

pytestmark = pytest.mark.offline


def _make_rag(aquery_result="odpowiedź RAG", llm_result="odpowiedź LLM"):
    rag = SimpleNamespace()
    rag.ollama_server_infos = SimpleNamespace(LIGHTRAG_MODEL="lightrag:latest")

    async def aquery(query, param=None):
        rag.last_query = query
        rag.last_param = param
        if param is not None and param.stream and not isinstance(aquery_result, str):
            return aquery_result
        if param is not None and param.stream:
            async def gen():
                for token in aquery_result.split(" "):
                    yield token + " "
            return gen()
        return aquery_result

    rag.aquery = aquery
    rag.llm_model_func = AsyncMock(return_value=llm_result)
    rag.llm_model_kwargs = {}
    return rag


def _client(rag, api_key=None):
    app = FastAPI()
    api = OpenAIAPI(rag, top_k=7, api_key=api_key)
    app.include_router(api.router, prefix="/v1")
    return TestClient(app)


def _sse_events(text):
    events = []
    for block in text.split("\n\n"):
        if block.startswith("data: "):
            events.append(block[len("data: "):])
    return events


class TestModels:
    def test_models_shape(self):
        client = _client(_make_rag())
        resp = client.get("/v1/models")
        assert resp.status_code == 200
        body = resp.json()
        assert body["object"] == "list"
        assert body["data"][0]["id"] == "lightrag:latest"
        assert body["data"][0]["object"] == "model"


class TestChatCompletions:
    def test_non_stream_response_shape(self):
        rag = _make_rag(aquery_result="Wynik zapytania.")
        client = _client(rag)
        resp = client.post("/v1/chat/completions", json={
            "model": "lightrag:latest",
            "messages": [{"role": "user", "content": "Jakie są procedury?"}],
            "stream": False,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["object"] == "chat.completion"
        assert body["id"].startswith("chatcmpl-")
        assert body["choices"][0]["message"] == {
            "role": "assistant", "content": "Wynik zapytania.",
        }
        assert body["choices"][0]["finish_reason"] == "stop"
        assert body["usage"]["total_tokens"] > 0

    def test_history_and_top_k_passed(self):
        rag = _make_rag()
        client = _client(rag)
        client.post("/v1/chat/completions", json={
            "model": "m",
            "messages": [
                {"role": "system", "content": "Bądź zwięzły."},
                {"role": "user", "content": "pierwsze"},
                {"role": "assistant", "content": "odp"},
                {"role": "user", "content": "drugie pytanie"},
            ],
        })
        assert rag.last_query == "drugie pytanie"
        assert rag.last_param.conversation_history == [
            {"role": "system", "content": "Bądź zwięzły."},
            {"role": "user", "content": "pierwsze"},
            {"role": "assistant", "content": "odp"},
        ]
        assert rag.last_param.top_k == 7
        assert rag.last_param.mode == "mix"

    def test_mode_prefix_selects_mode(self):
        rag = _make_rag()
        client = _client(rag)
        client.post("/v1/chat/completions", json={
            "model": "m",
            "messages": [{"role": "user", "content": "/hybrid co to jest OWU?"}],
        })
        assert rag.last_param.mode == "hybrid"
        assert rag.last_query == "co to jest OWU?"

    def test_bypass_uses_llm_directly(self):
        rag = _make_rag(llm_result="prosto z LLM")
        client = _client(rag)
        resp = client.post("/v1/chat/completions", json={
            "model": "m",
            "messages": [{"role": "user", "content": "/bypass powiedz cześć"}],
        })
        assert resp.json()["choices"][0]["message"]["content"] == "prosto z LLM"
        rag.llm_model_func.assert_awaited_once()
        assert not hasattr(rag, "last_query")  # aquery not called

    def test_streaming_sse_sequence(self):
        rag = _make_rag(aquery_result="jeden dwa trzy")
        client = _client(rag)
        resp = client.post("/v1/chat/completions", json={
            "model": "m",
            "messages": [{"role": "user", "content": "pytanie"}],
            "stream": True,
        })
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        events = _sse_events(resp.text)
        assert events[-1] == "[DONE]"
        chunks = [json.loads(e) for e in events[:-1]]
        assert chunks[0]["choices"][0]["delta"] == {"role": "assistant"}
        content = "".join(
            c["choices"][0]["delta"].get("content", "") for c in chunks[1:-1]
        )
        assert content.strip() == "jeden dwa trzy"
        assert chunks[-1]["choices"][0]["finish_reason"] == "stop"
        assert all(c["object"] == "chat.completion.chunk" for c in chunks)

    def test_last_message_not_user_400(self):
        client = _client(_make_rag())
        resp = client.post("/v1/chat/completions", json={
            "model": "m",
            "messages": [{"role": "assistant", "content": "hej"}],
        })
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "invalid_request"

    def test_array_content_400(self):
        client = _client(_make_rag())
        resp = client.post("/v1/chat/completions", json={
            "model": "m",
            "messages": [{"role": "user", "content": [{"type": "text", "text": "x"}]}],
        })
        assert resp.status_code == 400


class TestAuth:
    def test_bearer_api_key_accepted(self):
        client = _client(_make_rag(), api_key="sekret")
        resp = client.get("/v1/models", headers={"Authorization": "Bearer sekret"})
        assert resp.status_code == 200

    def test_x_api_key_accepted(self):
        client = _client(_make_rag(), api_key="sekret")
        resp = client.get("/v1/models", headers={"X-API-Key": "sekret"})
        assert resp.status_code == 200

    def test_wrong_key_401(self):
        client = _client(_make_rag(), api_key="sekret")
        resp = client.get("/v1/models", headers={"Authorization": "Bearer zly"})
        assert resp.status_code == 401

    def test_missing_key_401(self):
        client = _client(_make_rag(), api_key="sekret")
        assert client.get("/v1/models").status_code == 401

    def test_open_when_no_key_configured(self):
        client = _client(_make_rag())
        assert client.get("/v1/models").status_code == 200
