# Project Learnings — LightRAG

> **Tier 3: Project-Specific Knowledge**
>
> This file is maintained automatically by ADD agents. Entries are added at checkpoints
> (after verify, TDD cycles, deployments, away sessions) and reviewed during retrospectives.
>
> This is one of three knowledge tiers agents read before starting work:
> 1. **Tier 1: Plugin-Global** (`knowledge/global.md`) — universal ADD best practices
> 2. **Tier 2: User-Local** (`~/.claude/add/library.md`) — your cross-project wisdom
> 3. **Tier 3: Project-Specific** (this file) — discoveries specific to this project
>
> **Agents:** Read ALL three tiers before starting any task.
> **Humans:** Review with `/add:retro --agent-summary` or during full `/add:retro`.

## Technical Discoveries
<!-- Things learned about the tech stack, libraries, APIs, infrastructure -->
- 2026-02-10: Always call `await rag.initialize_storages()` after creating a LightRAG instance. Source: CLAUDE.md.
- 2026-02-10: Embedding models must be consistent across indexing and querying — changing models requires clearing vector storage. Source: CLAUDE.md.
- 2026-02-10: Ollama models default to 8k context; LightRAG requires 32k+. Configure via `llm_model_kwargs={"options": {"num_ctx": 32768}}`. Source: CLAUDE.md.
- 2026-02-10: Cannot wrap already-decorated embedding functions. Use `.func` to access the underlying function. Source: CLAUDE.md.
- 2026-02-10: `orjson` is used as an optional performance optimization for JSON serialization. Source: git log.
- 2026-02-10: Query handling separates embedding and keyword extraction with parallel execution for improved latency. Source: git log.

## Architecture Decisions
<!-- Decisions made and their rationale -->
- 2026-02-10: Pluggable storage backends via abstract base classes (BaseKVStorage, BaseVectorStorage, BaseGraphStorage, BaseDocStatusStorage). Source: CLAUDE.md.
- 2026-02-10: Workspace isolation per storage type (subdirectories for file-based, prefixes for collections, fields for relational DBs). Source: CLAUDE.md.

## What Worked
<!-- Patterns, approaches, tools that proved effective -->
- 2026-02-10: Async/await patterns throughout the codebase for consistent non-blocking I/O. Source: CLAUDE.md.
- 2026-02-10: Redis key prefix for multi-instance isolation. Source: git log.

## What Didn't Work
<!-- Patterns, approaches, tools that caused problems -->

## Agent Checkpoints
<!-- Automatic entries from verification, TDD cycles, deploys, away sessions -->
<!-- These are processed and archived during /add:retro -->

## Profile Update Candidates
<!-- Cross-project patterns flagged for promotion to ~/.claude/add/profile.md -->
<!-- Only promoted during /add:retro with human confirmation -->
