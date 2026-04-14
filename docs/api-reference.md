# LightRAG API Reference

Generated from codebase manifest. For interactive docs, start the server and visit `/docs`.

## Authentication

All endpoints (except `/health` and `/auth-status`) require authentication via one of:

- **JWT Token**: `Authorization: Bearer <token>` (obtained via `/login`)
- **API Key**: `X-API-Key: <key>` (configured via `LIGHTRAG_API_KEY` env var)

---

## Query Endpoints

### POST /query
Execute a knowledge graph query with optional tool calling.

**Request Body** (`QueryRequest`):
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | required | The question to ask |
| `mode` | string | `"global"` | Retrieval mode: `naive`, `local`, `global`, `hybrid`, `mix` |
| `stream` | bool | `true` | Enable streaming response |
| `top_k` | int | `40` | Number of KG entities/relations to retrieve |
| `chunk_top_k` | int | `20` | Number of text chunks to retrieve |
| `max_entity_tokens` | int | `6000` | Token budget for entity context |
| `max_relation_tokens` | int | `8000` | Token budget for relation context |
| `max_total_tokens` | int | `30000` | Total token budget for context |
| `enable_rerank` | bool | `true` | Enable reranker |
| `only_need_context` | bool | `false` | Return only retrieved context, skip LLM |
| `only_need_prompt` | bool | `false` | Return only constructed prompt |
| `user_prompt` | string | `""` | Additional instructions for the LLM |
| `conversation_history` | list | `[]` | Prior messages for multi-turn |
| `history_turns` | int | `0` | Number of history turns to include |
| `include_references` | bool | `false` | Include source references in response |
| `response_type` | string | `"Single Paragraph"` | Desired response format |

**Response**: `200 OK` with query response text (or SSE stream if `stream=true`)

### POST /query/stream
Same as `/query` but always returns Server-Sent Events stream.

### POST /query/data
Structured query returning detailed context data with metadata.

**Response**: `{"status": "success", "data": {...}, "metadata": {...}}`

---

## Document Endpoints

### POST /documents/text
Insert a single text document.

**Request Body** (`InsertTextRequest`):
| Field | Type | Description |
|-------|------|-------------|
| `text` | string | Document content |
| `file_source` | string | Optional source file path for citation |

**Response**: `202 Accepted` with `{status, message, track_id}`

### POST /documents/texts
Insert multiple text documents in batch.

**Request Body** (`InsertTextsRequest`):
| Field | Type | Description |
|-------|------|-------------|
| `texts` | list[string] | Document contents |
| `file_sources` | list[string] | Optional source paths per document |

### POST /documents/scan
Scan input directory for new documents to process.

### POST /documents/upload
Upload a file to the input directory.

**Request**: `multipart/form-data` with file

### GET /documents/pipeline_status
Get current document processing pipeline status.

### POST /documents/paginated
Get paginated list of documents with status.

### GET /documents/status_counts
Get counts by document status (pending, processing, processed, failed).

### GET /documents/track_status/{track_id}
Get processing status for a specific batch by track ID.

### POST /documents/reprocess_failed
Requeue all failed documents for reprocessing.

### POST /documents/cancel_pipeline
Cancel the current processing pipeline.

### DELETE /documents/delete_document
Delete a document and its extracted knowledge.

### DELETE /documents/delete_entity
Delete a specific entity from the knowledge graph.

### DELETE /documents/delete_relation
Delete a specific relation from the knowledge graph.

### POST /documents/clear_cache
Clear the LLM response cache.

---

## Graph Endpoints

### GET /graphs
Retrieve knowledge graph data (nodes and edges).

**Query Parameters**:
| Param | Type | Description |
|-------|------|-------------|
| `label` | string | Filter by entity label |
| `max_depth` | int | Maximum traversal depth |
| `max_nodes` | int | Maximum nodes to return |

**Response**: `KnowledgeGraph` with `nodes`, `edges`, `is_truncated`

### GET /graph/label/list
List all entity labels in the knowledge graph.

### GET /graph/label/popular
Get most popular (highest degree) entity labels.

### GET /graph/label/search
Search entity labels by substring.

### GET /graph/entity/exists
Check if a specific entity exists in the graph.

### POST /graph/entity/edit
Update an existing entity's properties.

**Request Body** (`EntityUpdateRequest`):
| Field | Type | Description |
|-------|------|-------------|
| `entity_name` | string | Entity to update |
| `updated_data` | dict | New property values |
| `allow_rename` | bool | Allow changing entity name |
| `allow_merge` | bool | Allow merging with existing entity |

### POST /graph/entity/create
Create a new entity in the knowledge graph.

### POST /graph/relation/edit
Update an existing relation's properties.

### POST /graph/relation/create
Create a new relation between entities.

### POST /graph/entities/merge
Merge multiple entities into one.

**Request Body** (`EntityMergeRequest`):
| Field | Type | Description |
|-------|------|-------------|
| `entities_to_change` | list[string] | Entity names to merge from |
| `entity_to_change_into` | string | Target entity name |

---

## Tools Endpoints

*Requires Redis. Only available when Redis is configured.*

### POST /tools/upload
Upload an Excel file for tool creation.

**Request**: `multipart/form-data` with `.xlsx` file

**Response**: `{file_id, columns, rows_preview, row_count}`

### POST /tools
Create a tool from an uploaded Excel file.

**Request Body** (`CreateToolRequest`):
| Field | Type | Description |
|-------|------|-------------|
| `file_id` | string | ID from upload step |
| `name` | string | Tool name (must be unique) |
| `description` | string | What the tool does |
| `parameters` | list | Column-to-parameter mappings |

### GET /tools
List all registered tools.

### DELETE /tools/{tool_id}
Delete a registered tool.

### POST /tools/{tool_id}/search
Search tool data with parameters.

**Request Body** (`SearchRequest`):
| Field | Type | Description |
|-------|------|-------------|
| `params` | dict | Search parameters (param_name: value) |
| `top_k` | int | Maximum results (default 10) |

---

## System Endpoints

### GET /health
Health check endpoint (no authentication required).

### GET /auth-status
Check authentication configuration and get guest token if auth is disabled.

### POST /login
Authenticate with username/password, receive JWT token.

**Request**: OAuth2 password flow (`username`, `password` form fields)

**Response**: `{access_token, token_type: "bearer"}`

---

*Generated from docs manifest on 2026-04-14*
