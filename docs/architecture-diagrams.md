# LightRAG Architecture Diagrams

## 1. Query Flow (with Native Tool Calling)

The primary retrieval path. When Excel tools are registered, LiteLLM handles tool dispatch; otherwise falls back to the configured LLM function.

```mermaid
sequenceDiagram
    participant C as Client
    participant QR as QueryRoutes
    participant Auth as AuthDependency
    participant LR as LightRAG
    participant KG as kg_query
    participant LL as LiteLLM
    participant TM as ToolManager
    participant LLM as LLM Provider

    C->>QR: POST /query
    QR->>Auth: validate credentials
    Auth-->>QR: OK

    QR->>LR: aquery_llm(query, param)
    LR->>KG: kg_query(query, ...)

    par Parallel keyword + embedding
        KG->>KG: get_keywords_from_query()
        KG->>KG: compute_query_embedding()
    end

    KG->>KG: _perform_kg_search()
    Note over KG: Batch embed query+keywords in single call

    alt Tools registered
        KG->>LL: acompletion(model, messages, tools, tool_choice=auto)
        LL->>LLM: Forward with provider prefix
        LLM-->>LL: Response with tool_calls

        alt LLM calls tools
            LL-->>KG: tool_calls in response
            KG->>TM: execute_tool_search(tool_calls)
            TM->>TM: Redis search per tool
            TM-->>KG: tool result messages

            KG->>LL: acompletion(messages + tool results)
            LL->>LLM: Second call with context
            LLM-->>LL: Final response
            LL-->>KG: response
        else LLM answers directly
            LL-->>KG: content response (no tools used)
        end
    else No tools
        KG->>LLM: use_model_func(query, system_prompt)
        LLM-->>KG: response
    end

    KG-->>LR: QueryResult
    LR-->>QR: response + references
    QR-->>C: JSON response
```

## 2. Document Insertion Pipeline

Documents are enqueued then processed in background with semaphore-controlled parallelism.

```mermaid
sequenceDiagram
    participant C as Client
    participant DR as DocumentRoutes
    participant BG as BackgroundTask
    participant LR as LightRAG
    participant CS as ChunkStorage
    participant VDB as VectorDB
    participant KG as GraphStorage
    participant LLM as LLM Provider

    C->>DR: POST /documents/text
    DR->>DR: Duplicate check (doc_status)
    DR->>DR: Generate track_id

    DR->>BG: schedule pipeline_index_texts()
    DR-->>C: 202 Accepted {track_id}

    Note over BG,LLM: Background processing begins

    BG->>LR: apipeline_enqueue_documents()
    LR->>LR: Sanitize, dedupe, create DocStatus
    LR->>LR: Upsert to doc_status storage

    BG->>LR: apipeline_process_enqueue_documents()
    LR->>LR: Acquire pipeline_status_lock
    LR->>LR: Create Semaphore(max_parallel_insert)

    loop For each document (semaphore-bounded)
        Note over LR: Stage 1: Parallel chunk operations
        LR->>LR: chunking_func(content)

        par Concurrent storage upserts
            LR->>CS: text_chunks.upsert(chunks)
            LR->>VDB: chunks_vdb.upsert(chunks)
            LR->>LR: doc_status = PROCESSING
        end

        Note over LR: Stage 2: Entity extraction
        LR->>LLM: extract_entities(chunk)
        LLM-->>LR: entities + relations

        opt Gleaning enabled
            LR->>LLM: continue extraction (history)
            LLM-->>LR: additional entities
        end

        LR->>KG: upsert nodes + edges
        LR->>LR: doc_status = PROCESSED
    end

    LR->>LR: index_done_callback()
```

## 3. Authentication Flow

Supports JWT tokens, API keys, and unauthenticated access. Token auto-renewal prevents active session expiration.

```mermaid
flowchart TD
    A[Incoming Request] --> B{Path in whitelist?}
    B -->|Yes| Z[Allow Access]
    B -->|No| C{JWT token provided?}

    C -->|Yes| D[validate_token]
    D -->|Invalid/Expired| X[401 Unauthorized]
    D -->|Valid| E{Token auto-renew?}

    E -->|Yes| F{Remaining < threshold?}
    F -->|Yes| G{Rate limit OK? >60s}
    G -->|Yes| H[create_token, set X-New-Token header]
    G -->|No| I[Skip renewal]
    F -->|No| I
    E -->|No| I

    H --> J{Role valid?}
    I --> J
    J -->|Yes| Z
    J -->|No| X

    C -->|No| K{Auth configured?}
    K -->|No API key, No auth| Z

    K -->|API key configured| L{X-API-Key header?}
    L -->|Yes| M{Key matches?}
    M -->|Yes| Z
    M -->|No| Y[403 Forbidden]
    L -->|No| Y

    K -->|Auth configured, no token| X
```

## 4. Storage Architecture

Pluggable storage backends with 4 storage types. Each can use a different implementation.

```mermaid
flowchart LR
    subgraph LightRAG Core
        LR[LightRAG Instance]
    end

    subgraph "4 Storage Types"
        KV[KV Storage<br/>LLM cache, chunks, docs]
        VDB[Vector Storage<br/>Entity/relation/chunk embeddings]
        GS[Graph Storage<br/>Entity-relation graph]
        DS[Doc Status Storage<br/>Processing state tracking]
    end

    subgraph "Backend Implementations"
        direction TB
        JSON[JSON/File]
        PG[PostgreSQL]
        Redis[Redis]
        Mongo[MongoDB]
        Neo4j[Neo4j]
        Milvus[Milvus]
        Qdrant[Qdrant]
        FAISS[FAISS]
        NanoVDB[NanoVectorDB]
        NetworkX[NetworkX]
        Memgraph[Memgraph]
        OpenSearch[OpenSearch]
    end

    LR --> KV
    LR --> VDB
    LR --> GS
    LR --> DS

    KV -.-> JSON
    KV -.-> PG
    KV -.-> Redis
    KV -.-> Mongo
    KV -.-> OpenSearch

    VDB -.-> NanoVDB
    VDB -.-> PG
    VDB -.-> Milvus
    VDB -.-> Qdrant
    VDB -.-> FAISS
    VDB -.-> Mongo
    VDB -.-> Redis
    VDB -.-> OpenSearch

    GS -.-> NetworkX
    GS -.-> Neo4j
    GS -.-> PG
    GS -.-> Mongo
    GS -.-> Memgraph
    GS -.-> Redis
    GS -.-> OpenSearch

    DS -.-> JSON
    DS -.-> PG
    DS -.-> Redis
    DS -.-> Mongo
    DS -.-> OpenSearch
```

## 5. LiteLLM Provider Routing

Maps `llm_binding` config to LiteLLM provider prefixes for native tool calling.

```mermaid
flowchart LR
    subgraph "Server Config"
        B[llm_binding]
        H[llm_binding_host]
        K[llm_binding_api_key]
        M[llm_model_name]
    end

    subgraph "BINDING_TO_LITELLM mapping"
        B --> |openai| P1["openai/"]
        B --> |azure_openai| P2["azure/"]
        B --> |ollama| P3["ollama/"]
        B --> |gemini| P4["gemini/"]
        B --> |lollms| P5["openai/"]
        B --> |bedrock| P6["bedrock/"]
    end

    P1 --> FM["prefix/model_name"]
    P2 --> FM
    P3 --> FM
    P4 --> FM
    P5 --> FM
    P6 --> FM
    M --> FM

    FM --> LC[litellm.acompletion]
    H --> LC
    K --> LC

    LC --> |"api_base + api_key"| EP[LLM Endpoint]
```

## 6. Excel Tool Lifecycle

Upload, configure, register, and use Excel-based tools in queries.

```mermaid
sequenceDiagram
    participant U as User
    participant API as Tools API
    participant TM as ExcelToolManager
    participant R as Redis
    participant KG as kg_query

    Note over U,KG: Tool Registration
    U->>API: POST /tools/upload (Excel file)
    API->>API: parse_excel_file()
    API-->>U: {file_id, columns, preview}

    U->>API: POST /tools {file_id, name, params}
    API->>TM: create_tool(definition, rows)
    TM->>R: SADD tool_ids
    TM->>R: SET tool:{id}:meta
    TM->>R: SET tool:{id}:data
    TM-->>API: tool created
    API-->>U: {tool_id}

    Note over U,KG: Tool Usage in Query
    U->>API: POST /query "find product X"
    API->>KG: kg_query(query, tool_manager, tool_definitions)
    KG->>KG: generate_tool_schema(definitions)
    KG->>KG: LiteLLM acompletion(tools=schemas)
    KG->>TM: execute_tool_search(tool_calls)
    TM->>R: GET tool data
    TM->>TM: Full-text search on rows
    TM-->>KG: search results
    KG->>KG: LiteLLM acompletion(messages + results)
    KG-->>API: final response
    API-->>U: answer with tool data
```

---

*Last updated: 2026-04-14*
