# CTO OS API

Private internal FastAPI layer for Phase 1: Founder Brain.

## Run

```bash
pip install -r cto_os_api/requirements.txt
uvicorn cto_os_api.main:app --reload --port 8787
```

Phase 3 stores app metadata in SQLite at `cto_os_api/data/cto_os.sqlite3` unless `CTO_OS_SQLITE_PATH` is set. If `cto_os_api/data/cto_os.json` exists and SQLite is empty, it is migrated on startup and preserved as `cto_os_api/data/cto_os.phase3-backup.json`.

## Scope

This API is intentionally internal-only. It has no billing, public signup, or complex tenant permissions. Project-scoped retrieval is the default; cross-project memory search requires `cross_project=true`.

## Internal Auth

Set `CTO_OS_ADMIN_TOKEN` to require a bearer token or `X-CTO-OS-Token` header on API requests. Leave it unset for local development.

## LLM Provider

Set:

```bash
CTO_OS_LLM_PROVIDER=openai
OPENAI_API_KEY=...
CTO_OS_MODEL=gpt-4.1-mini
```

or:

```bash
CTO_OS_LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=...
CTO_OS_MODEL=claude-3-5-sonnet-latest
```

If provider configuration is missing or the call fails, generation falls back to deterministic local output.

## Phase 4 Execution Engine

The API includes local SQLite-backed jobs, workflow runs, build packets, repository records, project import/export, and system snapshots.

Useful routes:

- `GET /projects/{project_id}/jobs`
- `POST /projects/{project_id}/workflows/run`
- `POST /projects/{project_id}/build-packets/generate`
- `GET /projects/{project_id}/repositories`
- `POST /system/snapshots/create`
- `GET /projects/{project_id}/export`
- `POST /projects/import`

## Phase 5 Repo-Aware Operator

Local repo support is read-only and safe by default. It can scan `Repository.local_path`, index repo summaries into memory, generate branch plans and PR packets, review pasted diffs, and record test runs.

Worker:

```bash
python -m cto_os_api.worker
```

GitHub integration is status-only in Phase 5:

- `GET /system/integrations/github/status`
