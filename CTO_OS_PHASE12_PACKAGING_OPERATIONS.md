# Phase 12 Packaging + Daily Operations

Phase 12 ships the operational layer: one-command start/stop/status,
single-glance health, worker heartbeats, hardened snapshots, a backup
policy, a daily-review aggregator, a demo seed, MCP read-only mode, and
lightweight MCP change notifications.

## New modules

| Module | Purpose |
|--------|---------|
| `cto_os_api/heartbeat.py` | Best-effort `HeartbeatWriter` for long-running processes. |
| `cto_os_api/health.py` | `/system/health` aggregator with rollup. |
| `cto_os_api/backups.py` | Backup policy + rotation. |
| `cto_os_api/daily_review.py` | Aggregator + deterministic markdown render. |
| `cto_os_api/mcp_notifications.py` | In-process change-notification publisher. |

## New routes

```
GET   /system/health
GET   /system/workers
POST  /system/snapshots/{id}/verify
POST  /system/snapshots/{id}/restore-preview
GET   /system/backups/policy
PATCH /system/backups/policy
POST  /system/backups/run
POST  /system/daily-review/generate
```

## New scripts

```
scripts/start_cto_os.sh        # api + worker + web
scripts/stop_cto_os.sh         # graceful TERM, then KILL after 3s
scripts/status_cto_os.sh       # PID + port probe per process
scripts/start_api.sh           # uvicorn on :8787
scripts/start_web.sh           # next dev on :3000
scripts/start_worker.sh        # worker poll loop
scripts/start_mcp.sh           # MCP smoke runner + .mcp.json snippet
scripts/seed_demo_project.py   # idempotent demo seed
```

PIDs land in `.cto_os/run/`, logs in `.cto_os/logs/`. Override ports via
`CTO_OS_API_PORT` / `CTO_OS_WEB_PORT`.

## How to start / stop / status

```bash
bash scripts/start_cto_os.sh   # starts api → worker → web
bash scripts/status_cto_os.sh  # prints state of all three
bash scripts/stop_cto_os.sh    # graceful shutdown
```

Daily check-in:

```bash
curl -s http://127.0.0.1:8787/system/health | jq .
```

## Health dashboard behavior

`/system/health` returns `SystemHealth` with status rollup:

- **down**  SQLite unreachable.
- **degraded**  any worker heartbeat older than 60s, any recent failed
  job, any failed/blocked GitHub write event, or backup overdue.
- **ok**  everything green.

The UI at `/system/health` renders each subsystem card and the workers
list, plus three "recent failures" panels (jobs, GitHub writes, dismissed
suggestions).

## Worker heartbeat

The worker upserts a `worker_heartbeats` row each polling iteration via
`HeartbeatWriter.beat(...)`. Errors are swallowed — heartbeats are
observability, not correctness. The health aggregator marks any heartbeat
older than 60s as stale and downgrades to `degraded`.

## Snapshot safety upgrade

`SnapshotManager.create_snapshot` now runs `PRAGMA wal_checkpoint(TRUNCATE)`
before copying so the snapshot captures a consistent view across FastAPI +
worker + MCP. Manifest includes app version and the source SQLite path.

New endpoints:

- `POST /system/snapshots/{id}/verify` → `SnapshotIntegrity` (file
  presence, SQLite open + `PRAGMA integrity_check`).
- `POST /system/snapshots/{id}/restore-preview` → `SnapshotRestorePreview`
  (size delta, project-count delta, safety notes). Never mutates — the
  existing `POST /system/snapshots/{id}/restore` remains the only write path.

## Backup policy

A singleton `backup_policy` row. Defaults: `enabled=false`, `cadence=manual`,
`max_snapshots=10`. `POST /system/backups/run` honors `cadence` via
`last_run_at` unless `force=true`. On a successful run, snapshots are
rotated down to `max_snapshots` newest; rotation only deletes files under
the snapshot dir.

UI: `/settings/backups`.

## Daily CTO review

`POST /system/daily-review/generate` returns a structured `DailyReview`
plus a pre-rendered markdown brief. Sections: projects needing attention,
blocked tasks, high/critical risks, stale build sessions, failed jobs,
pending status suggestions, recent shipped (7d), recommended next actions.

- UI: `/control-room/daily-review`.
- MCP prompt: `cto_os_daily_review` (no args).
- Workflow doc: `.claude/workflows/cto-os-daily-review.md`.

## MCP read-only mode

`CTO_OS_MCP_READONLY=1` flips a process-wide flag. Any call to a tool in
`WRITE_TOOL_NAMES` returns a structured blocked response:

```json
{"isError": true, "blocked": true,
 "reason": "MCP read-only mode is enabled (CTO_OS_MCP_READONLY=1); write tools refuse to mutate state.",
 "tool": "create_task"}
```

Read + preview tools unaffected. The safety report's `read_only_mode`
field reflects the env so the host can verify before a co-founder/advisor
session. Notifications are still emitted only for actual writes.

## MCP change notifications

After every `tools/call`, the MCP server drains the `MCPNotifier` queue
and writes JSON-RPC notifications to stdout:

```
{"jsonrpc":"2.0","method":"notifications/resources/updated",
 "params":{"uri":"cto-os://projects/{id}/tasks","reason":"mcp.tool:create_task"}}
```

Hosts that don't process notifications drop them harmlessly. The drain is
synchronous between requests; no polling, no streaming.

## Demo seed

```bash
.venv/bin/python scripts/seed_demo_project.py
```

Creates a "Demo · CTO OS Tour" project with 3 memories (2 pinned), 3
tasks, 1 decision, 1 risk, 1 local repo record, 1 build session.
Idempotent on re-run.

## Environment additions

```
CTO_OS_MCP_READONLY=0       # set to 1 to refuse write tools over MCP
CTO_OS_WORKER_NAME=default  # heartbeat row label
CTO_OS_API_PORT=8787        # scripts override
CTO_OS_WEB_PORT=3000        # scripts override
```

## Recommended Phase 13

1. **Multi-user audit log** — per-token MCP writes attributed in a new
   append-only `mcp_audit` table; query by token, session, time window.
2. **Cron / scheduler** — opt-in cron table that runs the daily review
   each morning and feeds the result into a notification rule (already
   gated by Phase 9 notifications).
3. **Cloud snapshot mirror** — pluggable backend (S3, rclone) that copies
   newest snapshot to cold storage on successful run.
4. **`/system/health` history** — store rollup status every minute so the
   UI can render a sparkline; surface SLO-style "minutes degraded" on the
   dashboard.
5. **MCP resources push** — emit `notifications/resources/list_changed`
   when a project or task is created/deleted so the host can refresh
   surfaced URIs without polling.
