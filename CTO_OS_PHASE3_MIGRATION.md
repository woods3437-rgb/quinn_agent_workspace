# Phase 3 Migration

## Storage

CTO OS metadata now uses SQLite by default:

- default DB: `cto_os_api/data/cto_os.sqlite3`
- legacy JSON source: `cto_os_api/data/cto_os.json`
- JSON backup after migration: `cto_os_api/data/cto_os.phase3-backup.json`

The migration is automatic on API startup when SQLite has no projects and the JSON file exists.

## Auth

Set `CTO_OS_ADMIN_TOKEN` to enable internal token auth. The frontend sends `NEXT_PUBLIC_CTO_OS_ADMIN_TOKEN`.

Local development remains open when `CTO_OS_ADMIN_TOKEN` is absent.

## LLM

`CTO_OS_LLM_PROVIDER` supports `deterministic`, `openai`, and `anthropic`.

Live provider failures fall back to deterministic generation and are recorded in output metadata.
