# Phase 2 Storage Recommendation

## Decision

Keep JSON for Phase 2 app metadata, but harden writes with:

- atomic temp-file replacement
- timestamped backup snapshots before writes
- schema key migration defaults for newly added collections

MemPalace/ChromaDB remains the semantic retrieval layer. CTO OS JSON stores operational metadata: projects, decisions, tasks, generated outputs, and prompt templates.

## Why Not SQLite Yet

Phase 2 adds a broad product surface: architecture generation, roadmaps, tasks, prompts, implementation plans, richer decisions, and project briefs. Migrating persistence at the same time would increase regression risk before the execution model has settled.

JSON is still acceptable while this is:

- private/internal
- local-first
- low concurrency
- easy to inspect and recover

## Migration Trigger

Move to SQLite before:

- multiple humans edit the same workspace concurrently
- tasks become high-volume
- outputs become large enough to require pagination/search
- auditability or transactional updates matter
- internal auth and deployment are added

## SQLite Migration Shape

When ready:

- keep the API contract stable
- create a `SqliteStore` beside `JsonStore`
- migrate from `cto_os_api/data/cto_os.json` on first run
- preserve JSON backups
- keep MemPalace/ChromaDB unchanged for semantic memory
