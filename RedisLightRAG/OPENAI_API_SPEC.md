# OpenAI Embeddings API Specification
## For Internal API Compatibility with OpenAI Client v1.109.1

This document specifies the exact format required for OpenAI-compatible embedding APIs.

## 1. HTTP Response Requirements

### Status Code
- **Must be**: `200 OK` for successful requests
- Error responses: `400`, `401`, `429`, `500` with error object

### Headers
```
Content-Type: application/json; charset=utf-8
```

**Optional but recommended:**
```
x-request-id: <unique-request-id>
openai-version: 2020-10-01
openai-organization: <org-name>
```

## 2. Request Format

### Endpoint
```
POST /v1/embeddings
```

### Headers
```
Authorization: Bearer <api-key>
Content-Type: application/json
```

### Body
```json
{
  "model": "text-embedding-ada-002",
  "input": "The food was delicious and the waiter..."
}
```

**Alternative with array:**
```json
{
  "model": "text-embedding-ada-002",
  "input": ["Text 1", "Text 2", "Text 3"]
}
```

## 3. Response Format (CRITICAL)

### Exact Structure
```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "embedding": [
        0.0023064255,
        -0.009327292,
        ...
        -0.0028842222
      ],
      "index": 0
    }
  ],
  "model": "text-embedding-ada-002",
  "usage": {
    "prompt_tokens": 8,
    "total_tokens": 8
  }
}
```

### Field-by-Field Specification

#### Top Level (Required)
| Field | Type | Value | Description |
|-------|------|-------|-------------|
| `object` | string | `"list"` | Must be exactly "list" |
| `data` | array | Array of embedding objects | Must be array, even for single input |
| `model` | string | Model identifier | The model that generated embeddings |
| `usage` | object | Token usage stats | Required for OpenAI compatibility |

#### Data Array Items (Required)
| Field | Type | Description |
|-------|------|-------------|
| `object` | string | Must be exactly `"embedding"` |
| `embedding` | array of floats | The embedding vector (e.g., 1536 dims for ada-002) |
| `index` | integer | Zero-based index, matches input order |

#### Usage Object (Required)
| Field | Type | Description |
|-------|------|-------------|
| `prompt_tokens` | integer | Number of tokens in input |
| `total_tokens` | integer | Total tokens (usually same as prompt_tokens) |

### Important Notes

1. **Field Order (Recommended)**:
   ```json
   {
     "object": "list",      // First
     "data": [...],         // Second
     "model": "...",        // Third
     "usage": {...}         // Fourth
   }
   ```
   While JSON is order-independent, OpenAI returns fields in this order, and some strict parsers may expect it.

2. **Data Types**:
   - All token counts MUST be integers, not strings
   - All embedding values MUST be floats (not strings)
   - Indexes MUST be integers starting from 0

3. **No Extra Fields**:
   - Don't add extra fields at the top level
   - Extra fields in `data` items or `usage` may cause Pydantic validation errors

4. **Multiple Inputs**:
   If input is an array of 3 texts, `data` must have 3 items with indexes 0, 1, 2:
   ```json
   {
     "object": "list",
     "data": [
       {"object": "embedding", "embedding": [...], "index": 0},
       {"object": "embedding", "embedding": [...], "index": 1},
       {"object": "embedding", "embedding": [...], "index": 2}
     ],
     "model": "...",
     "usage": {"prompt_tokens": 24, "total_tokens": 24}
   }
   ```

## 4. Error Response Format

### 4xx/5xx Status Codes with Error Object
```json
{
  "error": {
    "message": "Invalid API key provided",
    "type": "invalid_request_error",
    "param": null,
    "code": "invalid_api_key"
  }
}
```

### Error Types
- `invalid_request_error` - Bad request (400)
- `authentication_error` - Auth failed (401)
- `rate_limit_error` - Too many requests (429)
- `api_error` - Server error (500)

## 5. Validation Checklist for Your API

Use this checklist to ensure compatibility:

- [ ] HTTP 200 status code for success
- [ ] `Content-Type: application/json` header
- [ ] Response is a JSON object (not array)
- [ ] Top-level field `"object": "list"` exists and is exactly "list"
- [ ] Top-level field `"data"` is an array
- [ ] Each data item has `"object": "embedding"`
- [ ] Each data item has `"embedding"` as array of floats
- [ ] Each data item has `"index"` as integer (0-based)
- [ ] Top-level field `"model"` is a string
- [ ] Top-level field `"usage"` is an object
- [ ] Usage has `"prompt_tokens"` as integer
- [ ] Usage has `"total_tokens"` as integer
- [ ] No extra fields at top level
- [ ] All numbers are proper numeric types (not strings)
- [ ] Field order matches OpenAI: object, data, model, usage

## 6. Testing Your API

Run the compatibility checker:
```bash
python test_api_compatibility.py
```

This will validate all requirements and show exactly what needs to be fixed.

## 7. Common Compatibility Issues

### Issue 1: Wrong Field Order
**Your API:**
```json
{"model": "...", "object": "list", "usage": {...}, "data": [...]}
```

**Should be:**
```json
{"object": "list", "data": [...], "model": "...", "usage": {...}}
```

### Issue 2: Missing "object" Field
**Your API:**
```json
{"data": [...], "model": "...", "usage": {...}}
```

**Should be:**
```json
{"object": "list", "data": [...], "model": "...", "usage": {...}}
```

### Issue 3: Token Counts as Strings
**Your API:**
```json
{"usage": {"prompt_tokens": "8", "total_tokens": "8"}}
```

**Should be:**
```json
{"usage": {"prompt_tokens": 8, "total_tokens": 8}}
```

### Issue 4: Extra Top-Level Fields
**Your API:**
```json
{"object": "list", "data": [...], "model": "...", "usage": {...}, "version": "1.0"}
```

**Should be (remove extra fields):**
```json
{"object": "list", "data": [...], "model": "...", "usage": {...}}
```

## 8. OpenAI Python Client Behavior (v1.109.1)

The latest OpenAI client uses **Pydantic v2** for strict response validation:

1. **Strict Type Checking**: All fields must match exact types
2. **No Extra Fields**: Pydantic rejects unexpected fields by default
3. **Field Validation**: Custom validators check value constraints
4. **Object Parsing**: Response is parsed into Python objects, not dicts

This means your API must be **100% compliant** with the spec above.

## 9. References

- [OpenAI Embeddings API Documentation](https://platform.openai.com/docs/api-reference/embeddings)
- [OpenAI Python Client Source](https://github.com/openai/openai-python)
- OpenAI Client Version: 1.109.1
- Pydantic Version: 2.x

## 10. Contact

For questions about this specification or compatibility issues, contact:
- Your DevOps/Platform team
- OpenAI API documentation: https://platform.openai.com/docs
