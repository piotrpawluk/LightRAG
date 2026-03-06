# Spec: Excel Tools

**Version:** 0.1.0
**Created:** 2026-03-06
**PRD Reference:** docs/prd.md
**Status:** Draft

## 1. Overview

A new "Tools" tab in the LightRAG WebUI that allows users to upload Excel files and register them as LLM-callable tools. Users define which columns are searchable, provide tool metadata (name, description, parameter names/descriptions), and the system persists everything in Redis. During RAG queries, the LLM can invoke any registered tool to look up matching rows via combined similarity search and full-text search on the designated columns.

### User Story

As a LightRAG user, I want to upload Excel files and define them as LLM tools with searchable columns, so that the LLM can look up structured data from my spreadsheets when answering queries.

## 2. Acceptance Criteria

| ID | Criterion | Priority |
|----|-----------|----------|
| AC-001 | A "Tools" tab is visible in the WebUI navigation alongside existing tabs | Must |
| AC-002 | User can upload an Excel file (.xlsx/.xls) via the Tools tab | Must |
| AC-003 | After upload, the system displays the list of column names from the file | Must |
| AC-004 | User can select one or more columns as "search-by" columns | Must |
| AC-005 | User can define a tool name (unique, non-empty) | Must |
| AC-006 | User can define a tool description | Must |
| AC-007 | User can define a parameter name and description for each search-by column | Must |
| AC-008 | On submission, the Excel data and tool definition are persisted in Redis | Must |
| AC-009 | A list of registered tools is displayed on the Tools tab with name and description | Must |
| AC-010 | User can delete a registered tool from the list | Must |
| AC-011 | The LLM is provided with all registered tool definitions during every RAG query | Must |
| AC-012 | When the LLM calls a tool, the system performs combined similarity + full-text search on the search-by columns | Must |
| AC-013 | Tool search returns up to 10 matching rows by default | Must |
| AC-014 | Tool results are returned to the LLM as structured data for inclusion in the response | Must |
| AC-015 | Duplicate tool names are rejected with an error message | Should |
| AC-016 | Invalid file formats (not .xlsx/.xls) are rejected with an error message | Should |
| AC-017 | Empty files or files with no columns show an appropriate error | Should |
| AC-018 | Tools persist across server restarts (Redis-backed) | Must |

## 3. User Test Cases

### TC-001: Create a tool from an Excel file

**Precondition:** User is logged in, no tools exist yet
**Steps:**
1. Navigate to the "Tools" tab
2. Click "Upload Excel" and select a valid .xlsx file
3. See column names listed from the file
4. Select 2 columns as search-by columns
5. Enter tool name: "product-lookup"
6. Enter tool description: "Look up product details by name or SKU"
7. Enter param name and description for each search-by column
8. Click "Create Tool"
**Expected Result:** Tool appears in the tools list with name "product-lookup" and description. Success notification shown.
**Screenshot Checkpoint:** tests/screenshots/excel-tools/step-08-tool-created.png
**Maps to:** TBD

### TC-002: Query uses registered tool

**Precondition:** "product-lookup" tool exists with Excel data loaded
**Steps:**
1. Navigate to the query/retrieval tab
2. Enter a query: "What is the price of Widget X?"
3. Submit the query
**Expected Result:** The LLM invokes the "product-lookup" tool, retrieves matching rows, and includes the structured data in its response.
**Screenshot Checkpoint:** tests/screenshots/excel-tools/step-03-query-with-tool.png
**Maps to:** TBD

### TC-003: Delete a tool

**Precondition:** At least one tool exists
**Steps:**
1. Navigate to the "Tools" tab
2. Click delete on an existing tool
3. Confirm deletion
**Expected Result:** Tool is removed from the list and from Redis. LLM no longer has access to it on subsequent queries.
**Screenshot Checkpoint:** tests/screenshots/excel-tools/step-03-tool-deleted.png
**Maps to:** TBD

### TC-004: Upload invalid file

**Precondition:** User is on the Tools tab
**Steps:**
1. Click "Upload Excel" and select a .csv file
2. Observe result
**Expected Result:** Error message: "Invalid file format. Please upload an .xlsx or .xls file."
**Screenshot Checkpoint:** tests/screenshots/excel-tools/step-02-invalid-format.png
**Maps to:** TBD

### TC-005: Duplicate tool name

**Precondition:** A tool named "product-lookup" already exists
**Steps:**
1. Upload a new Excel file
2. Enter tool name: "product-lookup"
3. Click "Create Tool"
**Expected Result:** Error message: "A tool with this name already exists."
**Screenshot Checkpoint:** tests/screenshots/excel-tools/step-03-duplicate-name.png
**Maps to:** TBD

## 4. Data Model

### ToolDefinition

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| tool_id | string (UUID) | Yes | Unique identifier for the tool |
| name | string | Yes | User-defined tool name (unique) |
| description | string | Yes | User-defined tool description for LLM |
| created_at | datetime | Yes | Creation timestamp |

### ToolParameter

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| tool_id | string (UUID) | Yes | Reference to parent tool |
| column_name | string | Yes | Original Excel column name |
| param_name | string | Yes | Parameter name exposed to LLM |
| param_description | string | Yes | Parameter description for LLM |

### ToolData

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| tool_id | string (UUID) | Yes | Reference to parent tool |
| rows | list[dict] | Yes | All rows from the Excel file as list of column->value dicts |
| column_names | list[string] | Yes | All column names from the Excel file |
| search_columns | list[string] | Yes | Column names designated as search-by |

### Storage

All entities are stored in Redis under a key prefix (e.g., `lightrag:tools:{tool_id}`). Tool data, definition, and parameters are stored together as a serialized JSON structure.

## 5. API Contract

### POST /tools/upload

**Description:** Upload an Excel file and extract column names

**Request:** multipart/form-data with `file` field (.xlsx/.xls)

**Response (200):**
```json
{
  "columns": ["Column A", "Column B", "Column C"],
  "row_count": 150,
  "file_id": "temp-uuid"
}
```

**Error Responses:**
- `400` - Invalid file format or empty file
- `413` - File too large

### POST /tools

**Description:** Create a tool definition from an uploaded file

**Request:**
```json
{
  "file_id": "temp-uuid",
  "name": "product-lookup",
  "description": "Look up product details by name or SKU",
  "parameters": [
    {
      "column_name": "Product Name",
      "param_name": "product_name",
      "param_description": "The name of the product to search for"
    },
    {
      "column_name": "SKU",
      "param_name": "sku",
      "param_description": "The product SKU code"
    }
  ]
}
```

**Response (201):**
```json
{
  "tool_id": "uuid",
  "name": "product-lookup",
  "description": "Look up product details by name or SKU",
  "parameters": [...],
  "row_count": 150,
  "created_at": "2026-03-06T12:00:00Z"
}
```

**Error Responses:**
- `400` - Missing required fields, invalid file_id
- `409` - Duplicate tool name

### GET /tools

**Description:** List all registered tools

**Response (200):**
```json
{
  "tools": [
    {
      "tool_id": "uuid",
      "name": "product-lookup",
      "description": "Look up product details by name or SKU",
      "parameters": [...],
      "row_count": 150,
      "created_at": "2026-03-06T12:00:00Z"
    }
  ]
}
```

### DELETE /tools/{tool_id}

**Description:** Delete a tool and its data

**Response (200):**
```json
{
  "deleted": true,
  "tool_id": "uuid"
}
```

**Error Responses:**
- `404` - Tool not found

### POST /tools/{tool_id}/search

**Description:** Search tool data (called internally by LLM tool execution)

**Request:**
```json
{
  "params": {
    "product_name": "Widget X",
    "sku": "WDG"
  },
  "top_k": 10
}
```

**Response (200):**
```json
{
  "rows": [
    {"Product Name": "Widget X", "SKU": "WDG-001", "Price": 29.99, "Stock": 150},
    {"Product Name": "Widget XL", "SKU": "WDG-002", "Price": 39.99, "Stock": 80}
  ],
  "total_matches": 2
}
```

## 6. UI Behavior

### States

- **Loading:** Spinner during file upload and tool creation
- **Empty:** "No tools registered yet. Upload an Excel file to create your first tool." with upload button
- **Error:** Toast notification for validation errors (invalid format, duplicate name, empty file)
- **Success:** Toast notification on tool creation/deletion, tools list updates immediately

### Tools Tab Layout

1. **Header:** "Tools" with "Upload Excel" button
2. **Tools List:** Table/cards showing name, description, parameter count, row count, created date, delete button
3. **Create Tool Form** (shown after file upload):
   - Column list with checkboxes for search-by selection
   - Tool name input
   - Tool description textarea
   - For each selected search-by column: param name input + param description input
   - "Create Tool" button

### Screenshot Checkpoints

| Step | Description | Path |
|------|-------------|------|
| 1 | Empty tools tab | tests/screenshots/excel-tools/step-01-empty-tab.png |
| 2 | Column preview after upload | tests/screenshots/excel-tools/step-02-column-preview.png |
| 3 | Create tool form filled | tests/screenshots/excel-tools/step-03-form-filled.png |
| 4 | Tool created in list | tests/screenshots/excel-tools/step-04-tool-in-list.png |
| 5 | Error states | tests/screenshots/excel-tools/step-05-error-state.png |

## 7. Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| Invalid file format (.csv, .txt, .pdf) | Reject with "Invalid file format" error |
| Empty Excel file (no rows) | Allow creation (tool exists but returns no results) |
| Excel file with no columns | Reject with "File contains no columns" error |
| Duplicate tool name | Reject with "Tool name already exists" error |
| Very large Excel file (>10k rows) | Accept but warn about memory usage |
| Column values contain special characters | Handle gracefully, no injection |
| Search returns no matches | Return empty rows array to LLM |
| Tool deleted while query in progress | Query completes with available tools at time of start |
| Server restart | Tools and data persist in Redis |
| Excel file with multiple sheets | Use first sheet only (document this) |

## 8. Dependencies

- **openpyxl** or **pandas** — for Excel file parsing (.xlsx)
- **xlrd** — for .xls file parsing (if supporting legacy format)
- **Redis** — for persisting tool definitions and data (already in use by LightRAG)
- **Embedding model** — for similarity search on column values (reuse existing LightRAG embedding)
- **LLM tool-calling support** — LLM provider must support function/tool calling

## 9. Revision History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2026-03-06 | 0.1.0 | peterpawluk | Initial spec from /add:spec interview |
