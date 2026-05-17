# Phase 4 Execution Engine

Phase 4 turns the private CTO OS into a local operational build system.

## Added

- Local in-process jobs stored in SQLite.
- Workflow runs for repeatable CTO operations.
- Build packets for Codex, Claude, Cursor, or developer handoff.
- Repository records as a clean future GitHub/local repo boundary.
- Manual SQLite snapshots and restore safeguards.
- Project import/export bundles.
- Structured LLM validation helpers with deterministic fallback behavior.

## Safety

The system remains internal-only. There is no billing, public signup, SaaS tenant model, or external GitHub API integration.

Snapshots copy the active SQLite DB before restore operations create a pre-restore backup.

## Worker

Jobs run synchronously through the API for now. This keeps Phase 4 simple and local-first. A durable background worker can be added later without changing the Job schema.
