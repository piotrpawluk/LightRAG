"""OpenAI-compatible API shim (/v1/models, /v1/chat/completions).

Lets OpenAI clients (e.g. LibreChat custom endpoints) talk to LightRAG.
Reuses the Ollama emulation's chat->RAG mapping: the last user message is the
query (with optional /local /global /hybrid /mix /naive /bypass prefixes via
parse_query_mode), all prior messages become conversation_history.

Auth is intentionally self-contained (not get_combined_auth_dependency):
OpenAI clients send `Authorization: Bearer <key>`, which the combined
dependency would treat as a LightRAG JWT. Here Bearer <api_key> and
X-API-Key: <api_key> are both accepted; with no api_key configured the
endpoints are open (matching the deployed default).
"""

import asyncio
import json
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict

from lightrag import LightRAG, QueryParam
from lightrag.utils import logger
from lightrag.api.routers.ollama_api import (
    SearchMode,
    estimate_tokens,
    parse_query_mode,
)


class ChatMessage(BaseModel):
    role: str
    content: Any
    model_config = ConfigDict(extra="ignore")


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: bool = False
    model_config = ConfigDict(extra="ignore")


def _error_response(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "message": message,
                "type": "invalid_request_error",
                "code": code,
            }
        },
    )


def _chunk_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex[:12]}"


def _stream_chunk(
    chunk_id: str, created: int, model: str, delta: Dict[str, Any],
    finish_reason: Optional[str] = None,
) -> str:
    payload = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


class OpenAIAPI:
    def __init__(self, rag: LightRAG, top_k: int = 60, api_key: Optional[str] = None):
        self.rag = rag
        self.ollama_server_infos = rag.ollama_server_infos
        self.top_k = top_k
        self.api_key = api_key
        self.router = APIRouter(tags=["openai"])
        self.setup_routes()

    def _auth_dependency(self):
        api_key = self.api_key

        async def verify(request: Request):
            if not api_key:
                return  # no key configured — open, like the rest of the server
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer ") and auth_header[len("Bearer "):] == api_key:
                return
            if request.headers.get("X-API-Key") == api_key:
                return
            raise HTTPException(
                status_code=401,
                detail={
                    "error": {
                        "message": "Invalid API key",
                        "type": "authentication_error",
                        "code": "invalid_api_key",
                    }
                },
            )

        return verify

    def setup_routes(self):
        auth = self._auth_dependency()

        @self.router.get("/models", dependencies=[Depends(auth)])
        async def list_models():
            return {
                "object": "list",
                "data": [
                    {
                        "id": self.ollama_server_infos.LIGHTRAG_MODEL,
                        "object": "model",
                        "created": int(time.time()),
                        "owned_by": "lightrag",
                    }
                ],
            }

        @self.router.post("/chat/completions", dependencies=[Depends(auth)])
        async def chat_completions(request: ChatCompletionRequest):
            messages = request.messages
            if not messages:
                return _error_response(400, "No messages provided", "invalid_request")
            for msg in messages:
                if not isinstance(msg.content, str):
                    return _error_response(
                        400,
                        "Only plain-string message content is supported",
                        "invalid_request",
                    )
            if messages[-1].role != "user":
                return _error_response(
                    400, "Last message must be from user role", "invalid_request"
                )

            query = messages[-1].content
            conversation_history = [
                {"role": msg.role, "content": msg.content} for msg in messages[:-1]
            ]

            cleaned_query, mode, only_need_context, user_prompt = parse_query_mode(query)

            param_dict = {
                "mode": mode.value,
                "stream": request.stream,
                "only_need_context": only_need_context,
                "conversation_history": conversation_history,
                "top_k": self.top_k,
            }
            if user_prompt is not None:
                param_dict["user_prompt"] = user_prompt
            query_param = QueryParam(**param_dict)

            try:
                if mode == SearchMode.bypass:
                    response = await self.rag.llm_model_func(
                        cleaned_query,
                        stream=request.stream,
                        history_messages=conversation_history,
                        **self.rag.llm_model_kwargs,
                    )
                else:
                    response = await self.rag.aquery(cleaned_query, param=query_param)
            except Exception as e:
                logger.error(f"[openai_api] query failed: {e}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": {
                            "message": str(e),
                            "type": "server_error",
                            "code": "internal_error",
                        }
                    },
                )

            chunk_id = _chunk_id()
            created = int(time.time())
            model = request.model

            if not request.stream:
                # aquery may still hand back an async generator — drain it
                if isinstance(response, str):
                    content = response
                else:
                    parts = []
                    async for part in response:
                        parts.append(part)
                    content = "".join(parts)
                prompt_tokens = estimate_tokens(cleaned_query)
                completion_tokens = estimate_tokens(content)
                return {
                    "id": chunk_id,
                    "object": "chat.completion",
                    "created": created,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": content},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens,
                    },
                }

            async def stream_generator():
                yield _stream_chunk(chunk_id, created, model, {"role": "assistant"})
                try:
                    if isinstance(response, str):
                        if response:
                            yield _stream_chunk(
                                chunk_id, created, model, {"content": response}
                            )
                    else:
                        async for chunk in response:
                            if chunk:
                                yield _stream_chunk(
                                    chunk_id, created, model, {"content": chunk}
                                )
                except (asyncio.CancelledError, Exception) as e:
                    logger.error(f"[openai_api] streaming failed: {e}")
                    yield _stream_chunk(
                        chunk_id, created, model, {"content": f"\n\n[error: {e}]"}
                    )
                yield _stream_chunk(chunk_id, created, model, {}, finish_reason="stop")
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                stream_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
