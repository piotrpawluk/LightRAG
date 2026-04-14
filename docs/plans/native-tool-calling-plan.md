# Implementation Plan: Native Tool Calling via LiteLLM

**Spec:** specs/native-tool-calling.md v0.1.0
**Created:** 2026-03-12
**Team Size:** Solo
**Estimated Duration:** 1 day

## Overview

Replace custom `<tool_call>` XML text-parsing with LiteLLM's native `acompletion(tools=...)` in the `kg_query()` tool-calling path. Fixes tool calls not executing in streaming mode.

## Success Criteria

- [ ] All 14 acceptance criteria addressed
- [ ] All tests passing
- [ ] Lint clean (`ruff check`)
- [ ] Tool calls work in both streaming and non-streaming modes

## Implementation Phases

### Phase 1: Dependency & Cleanup (30min)

| Task ID | Description | AC | Effort |
|---------|-------------|-----|--------|
| TASK-001 | Add `litellm` to `api` extras in `pyproject.toml` | AC-010 | 5min |
| TASK-002 | Delete `build_tool_prompt_section()` from `operate.py` (lines 3040-3069) | AC-011 | 5min |
| TASK-003 | Delete `parse_tool_calls()` from `operate.py` (lines 3072-3108) | AC-011 | 5min |
| TASK-004 | Delete `execute_tool_calls()` from `operate.py` (lines 3111-3147) | AC-011 | 5min |
| TASK-005 | Delete `format_tool_results()` from `operate.py` (lines 3150-3179) | AC-011 | 5min |

**Dependencies:** None

### Phase 2: Core Implementation (2h)

| Task ID | Description | AC | Effort |
|---------|-------------|-----|--------|
| TASK-006 | Replace tool prompt injection block (lines 3346-3358) with LiteLLM tools list construction using `generate_tool_schema()` | AC-003, AC-008 | 30min |
| TASK-007 | Replace LLM call block (lines 3400-3439) — when tools defined, use `litellm.acompletion()` with `tools` param instead of `use_model_func`; first call always non-streaming to capture tool_calls | AC-001, AC-003, AC-009 | 45min |
| TASK-008 | Add tool execution logic — iterate `response.choices[0].message.tool_calls`, resolve tool_id via name, call `tool_manager.search()`, build tool-role messages | AC-001, AC-004, AC-012, AC-013 | 30min |
| TASK-009 | Add second LLM call — `acompletion()` with tool results in messages, `stream=query_param.stream` | AC-004, AC-005 | 15min |
| TASK-010 | Handle no-tool-call path — when LLM returns no tool_calls, extract `choices[0].message.content` as response string | AC-006 | 10min |
| TASK-011 | Handle no-tools path — when `tool_definitions` is empty or `tool_manager` is None, use existing `use_model_func` unchanged | AC-007 | 5min |

**Dependencies:** TASK-001 (litellm installed)

#### TASK-007 Detail (the core change in `kg_query()`):

```python
# When tools are available, use LiteLLM for native tool calling
if tool_definitions and tool_manager is not None:
    from litellm import acompletion
    from lightrag.tools.excel_tool_manager import generate_tool_schema

    tools = [generate_tool_schema(td) for td in tool_definitions]
    model_name = global_config.get("llm_model_name", "gpt-4o-mini")

    # Build messages
    messages = []
    if sys_prompt:
        messages.append({"role": "system", "content": sys_prompt})
    for msg in (query_param.conversation_history or []):
        messages.append(msg)
    messages.append({"role": "user", "content": user_query})

    # First call — non-streaming to capture tool_calls
    llm_start = time.perf_counter()
    first_response = await acompletion(
        model=model_name,
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )
    assistant_msg = first_response.choices[0].message

    if assistant_msg.tool_calls:
        # Execute each tool call
        name_to_id = {td.name: td.tool_id for td in tool_definitions}
        messages.append(assistant_msg)

        for tc in assistant_msg.tool_calls:
            func_name = tc.function.name
            func_args = json.loads(tc.function.arguments)
            logger.info(f"[kg_query] Executing tool: {func_name}({func_args})")

            tool_id = name_to_id.get(func_name)
            rows = []
            if tool_id:
                try:
                    rows = await tool_manager.search(tool_id, func_args, top_k=10)
                except Exception as e:
                    logger.warning(f"[kg_query] Tool search failed: {e}")

            messages.append({
                "tool_call_id": tc.id,
                "role": "tool",
                "name": func_name,
                "content": json.dumps(rows, default=str),
            })

        # Second call — with tool results, respects original stream setting
        response = await acompletion(
            model=model_name,
            messages=messages,
            stream=query_param.stream,
        )
        # Extract string for non-streaming, pass through iterator for streaming
        if not query_param.stream:
            response = response.choices[0].message.content or ""
    else:
        # LLM chose not to call tools — use response directly
        response = assistant_msg.content or ""

else:
    # No tools — existing use_model_func path (unchanged)
    response = await use_model_func(...)
```

#### Response type handling:
- **Non-streaming + no tool calls:** `response` is a `str` → existing `QueryResult(content=response)` path
- **Non-streaming + tool calls:** second `acompletion` returns response object → extract `.content` as `str`
- **Streaming + tool calls:** second `acompletion(stream=True)` returns async iterator → needs wrapper to yield text chunks from LiteLLM format

#### TASK-009 Detail (streaming adapter):
LiteLLM streaming returns chunks with `chunk.choices[0].delta.content`. The existing `QueryResult` expects a raw async iterator yielding strings. Need a thin adapter:

```python
if query_param.stream:
    litellm_stream = response  # async iterator of chunks

    async def _litellm_to_text_stream():
        async for chunk in litellm_stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content

    response = _litellm_to_text_stream()
```

### Phase 3: Test Updates (1h)

| Task ID | Description | AC | Effort |
|---------|-------------|-----|--------|
| TASK-012 | Delete tests for removed functions: `test_ac012_parse_tool_calls_*` (4 tests), `test_ac014_format_tool_results_for_prompt` (1 test) | AC-011 | 10min |
| TASK-013 | Update `test_ac014_execute_tool_calls` — mock `litellm.acompletion` instead of calling `execute_tool_calls` directly | AC-001, AC-004 | 20min |
| TASK-014 | Add test: tool call with no matches returns empty result | AC-013 | 15min |
| TASK-015 | Add test: no tools registered skips LiteLLM path | AC-007 | 10min |

**Dependencies:** TASK-006 through TASK-011

### Phase 4: Verify (15min)

| Task ID | Description | Effort |
|---------|-------------|--------|
| TASK-016 | Run `python -m pytest tests/test_excel_tools.py -v` | 5min |
| TASK-017 | Run `ruff check lightrag/operate.py tests/test_excel_tools.py` | 2min |
| TASK-018 | Verify no other imports of deleted functions exist | 5min |

## Effort Summary

| Phase | Tasks | Estimated |
|-------|-------|-----------|
| Phase 1: Cleanup | 5 | 30min |
| Phase 2: Implementation | 6 | 2h |
| Phase 3: Tests | 4 | 1h |
| Phase 4: Verify | 3 | 15min |
| **Total** | **18** | **~4h** |

## Critical Path

TASK-001 → TASK-002..005 (parallel) → TASK-006 → TASK-007 → TASK-008 → TASK-009 → TASK-012..015 → TASK-016

## Key Files

| File | Change |
|------|--------|
| `pyproject.toml` (line 57) | Add `"litellm"` to `api` extras |
| `lightrag/operate.py` (lines 3040-3179) | Delete 4 functions |
| `lightrag/operate.py` (lines 3346-3467) | Replace tool injection + execution with LiteLLM `acompletion()` |
| `tests/test_excel_tools.py` (lines 381-448) | Delete old tests, add new LiteLLM-based tests |

## Reused Existing Code

| Function | File | Purpose |
|----------|------|---------|
| `generate_tool_schema()` | `lightrag/tools/excel_tool_manager.py:91` | Produces OpenAI-format tool schema — used directly as LiteLLM `tools` param |
| `tool_manager.search()` | `lightrag/tools/excel_tool_manager.py:218` | Full-text search on tool data — called from tool execution loop |
| `tool_manager.get_all_tool_definitions()` | `lightrag/tools/excel_tool_manager.py:296` | Loads all tools — already called in kg_query |
| `global_config["llm_model_name"]` | `lightrag/lightrag.py:328` | Model name string — used as LiteLLM model identifier |

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| LiteLLM streaming format differs from existing iterator contract | Medium | High | Adapter function wraps LiteLLM chunks to yield plain text |
| Provider doesn't support native tools | Low | Medium | LiteLLM handles fallback for most providers |
| LiteLLM adds significant import time | Low | Low | Lazy import inside the tool-calling branch only |
| Cache interaction with tool calls | Medium | Medium | Tool queries bypass LLM cache (non-deterministic); only cache non-tool responses |

## Verification

```bash
python -m pytest tests/test_excel_tools.py -v
ruff check lightrag/operate.py tests/test_excel_tools.py pyproject.toml
```

Manual E2E (post-deploy):
1. Register Excel tool via WebUI
2. Query via WebUI (streaming) — verify tool executes, no raw markup
3. Query via /query (non-streaming) — verify same
4. Query that doesn't need tools — verify no regression
