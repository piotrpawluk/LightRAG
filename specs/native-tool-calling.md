# Spec: Native Tool Calling via LiteLLM

**Version:** 0.1.0
**Created:** 2026-03-12
**PRD Reference:** docs/prd.md
**Status:** Draft

## 1. Overview

Replace the custom text-parsing tool-calling mechanism (`<tool_call>` XML tags) with LiteLLM's native tool/function calling API. The current implementation fails in streaming mode (WebUI default) because `<tool_call>` tags are never parsed from async iterators — the LLM's tool invocation passes through as raw text to the user. LiteLLM provides a unified, provider-agnostic tool calling API that works with streaming, thinking modes, and structured responses out of the box.

**Scope:** Only the tool-calling LLM path in `kg_query()` uses LiteLLM. All other LLM calls (entity extraction, keyword extraction, non-tool queries) remain unchanged.

### User Story

As a LightRAG user with registered Excel tools, I want tool calls to execute correctly regardless of streaming mode, so that the LLM can look up structured data and include it in responses without showing raw markup.

## 2. Acceptance Criteria

| ID | Criterion | Priority |
|----|-----------|----------|
| AC-001 | When tools are registered and the LLM decides to call a tool, the tool executes and results are returned to the LLM — in both streaming and non-streaming modes | Must |
| AC-002 | The user never sees raw `<tool_call>` markup or LiteLLM internal structure in the response | Must |
| AC-003 | Tool definitions are passed to the LLM as native OpenAI-format `tools` parameter via LiteLLM `acompletion()` | Must |
| AC-004 | Tool results are sent back as LiteLLM tool-role messages (not injected into system prompt) | Must |
| AC-005 | The second LLM call (with tool results) respects the original stream setting from the query | Must |
| AC-006 | When the LLM does NOT call any tools, the response is returned normally with no regression | Must |
| AC-007 | When no tools are registered, the query path is unchanged (uses existing `use_model_func`) | Must |
| AC-008 | The model name for LiteLLM is resolved from `global_config["llm_model_name"]` (already exists) | Must |
| AC-009 | LiteLLM API keys are read from existing environment variables (OPENAI_API_KEY, etc.) — no new config required | Must |
| AC-010 | `litellm` is added as a dependency in the `api` extras group | Must |
| AC-011 | The old text-parsing functions (`build_tool_prompt_section`, `parse_tool_calls`, `execute_tool_calls`, `format_tool_results`) are removed from `operate.py` | Must |
| AC-012 | Tool call execution is logged at INFO level with tool name and argument summary | Should |
| AC-013 | If a tool call fails (e.g., tool_id not found, search error), the error is logged and an empty result is returned to the LLM — no crash | Should |
| AC-014 | Works with OpenAI, Anthropic, Ollama, and Gemini providers via LiteLLM's unified API | Should |

## 3. User Test Cases

### TC-001: Tool executes in streaming mode (WebUI)

**Precondition:** Excel tool "product-lookup" is registered with Product Name and SKU columns. Server running.
**Steps:**
1. Open WebUI, navigate to query tab
2. Enter query: "What is the price of Widget X?"
3. Submit query (WebUI uses /query/stream by default)
**Expected Result:** Response includes actual product data from the Excel file. No `<tool_call>` tags visible. Server logs show tool execution.
**Screenshot Checkpoint:** tests/screenshots/native-tool-calling/step-03-streaming-tool-result.png
**Maps to:** TBD

### TC-002: Tool executes in non-streaming mode

**Precondition:** Same as TC-001
**Steps:**
1. Send POST to /query with `{"query": "What is the price of Widget X?", "mode": "hybrid"}`
2. Inspect response
**Expected Result:** Response includes product data. No raw tool markup.
**Screenshot Checkpoint:** N/A (API test)
**Maps to:** TBD

### TC-003: Query without tool invocation

**Precondition:** Excel tool registered, but query doesn't need tool data
**Steps:**
1. Enter query: "What is the meaning of life?"
2. Submit query
**Expected Result:** Normal response with no tool execution. No errors. No regression.
**Screenshot Checkpoint:** N/A
**Maps to:** TBD

### TC-004: Query with no tools registered

**Precondition:** No Excel tools registered
**Steps:**
1. Enter any query
2. Submit query
**Expected Result:** Normal query flow via existing `use_model_func` — completely unchanged behavior.
**Screenshot Checkpoint:** N/A
**Maps to:** TBD

### TC-005: Tool search returns no matches

**Precondition:** Tool registered, query triggers tool call with no matching rows
**Steps:**
1. Enter query: "What is the price of Nonexistent Product XYZ?"
2. Submit query
**Expected Result:** LLM receives empty results, responds appropriately (e.g., "No matching products found").
**Screenshot Checkpoint:** N/A
**Maps to:** TBD

## 4. Data Model

No new data entities. Reuses existing:

### Existing: ToolDefinition (`lightrag/tools/excel_tool_manager.py`)
- `generate_tool_schema(tool_def)` already produces OpenAI-compatible tool format — reused directly as LiteLLM `tools` parameter.

### Existing: global_config
- `llm_model_name` (str) — already exists on LightRAG dataclass (default: `"gpt-4o-mini"`, set from `LLM_MODEL` env var). Used as LiteLLM model identifier.

## 5. API Contract

No new API endpoints. Changes are internal to the query pipeline.

**Affected internal function:** `kg_query()` in `lightrag/operate.py`

**LiteLLM call signature (new):**
```python
from litellm import acompletion

# First call — with tools
response = await acompletion(
    model=global_config["llm_model_name"],
    messages=[...],
    tools=[generate_tool_schema(td) for td in tool_definitions],
    tool_choice="auto",
)

# If tool_calls in response → execute tools → second call with results
# Second call — with tool results, streaming matches original request
response = await acompletion(
    model=global_config["llm_model_name"],
    messages=[..., assistant_msg, tool_result_msgs...],
    stream=query_param.stream,
)
```

## 6. UI Behavior

No UI changes. The fix is transparent — users see correct responses instead of raw `<tool_call>` tags.

## 7. Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| LLM returns tool call for unknown/deleted tool | Log warning, return empty result to LLM, let LLM respond without data |
| LLM returns multiple tool calls in one response | Execute all tools, return all results as separate tool messages |
| LiteLLM model name doesn't match provider format | LiteLLM auto-routes common names (gpt-4o → OpenAI, gemini-* → Google); user can use explicit `provider/model` format |
| Tool search raises exception | Catch, log warning, return empty result — no crash |
| Streaming second call with tool results | LiteLLM returns async iterator; existing QueryResult streaming path handles it |
| Non-streaming second call | LiteLLM returns response object; extract `.choices[0].message.content` as string |
| Provider doesn't support native tool calling | LiteLLM handles fallback internally for most providers |
| `llm_model_name` not set | Falls back to default `"gpt-4o-mini"` (existing LightRAG default) |

## 8. Dependencies

- **litellm** — Unified LLM API with native tool calling support (new dependency, `api` extras group)
- **Redis** — For tool data persistence (existing)
- **ExcelToolManager** — For tool definitions and search (existing, `lightrag/tools/excel_tool_manager.py`)
- **generate_tool_schema()** — Produces OpenAI-compatible tool format (existing, same file)

## 9. Files to Modify

| File | Change |
|------|--------|
| `pyproject.toml` | Add `litellm` to `api` extras |
| `lightrag/operate.py` | Replace tool prompt/parse/execute functions with LiteLLM `acompletion()` in `kg_query()` |
| `tests/test_excel_tools.py` | Update tool execution tests to mock LiteLLM instead of text parsing |

## 10. Revision History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2026-03-12 | 0.1.0 | peterpawluk | Initial spec |
