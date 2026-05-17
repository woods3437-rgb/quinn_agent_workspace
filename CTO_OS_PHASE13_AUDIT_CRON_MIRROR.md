# Phase 13 Audit, Cron, and Cold-Storage Mirror

Phase 13 adds accountability, scheduled operations, durable backups, and
health history so the CTO OS can run as a reliable internal operating
system.

## New modules

| Module | Purpose |
|--------|---------|
| `cto_os_api/mcp_audit.py` | Append-only MCP write audit recorder. Summary-only — no raw payloads. |
| `cto_os_api/cron_service.py` | Internal scheduler; default-off; per-job `WriterLease`. |
| `cto_os_api/backup_mirror.py` | Pluggable sink: local / rclone / s3 / scp. Three-gated. |
| `cto_os_api/health_history.py` | `HealthSnapshot` writer + 24h/7d summary. |
| `cto_os_api/resource_changes.py` | `ResourceChangeEvent` log + `list_changed_resources`. |

## New routes

```
GET   /system/mcp-audit
GET   /projects/{p}/mcp-audit
GET   /system/cron
POST  /system/cron
PATCH /system/cron/{id}
POST  /system/cron/{id}/run
POST  /system/backups/{snapshot_id}/mirror
GET   /system/backups/mirror-events
GET   /system/health/history
POST  /system/health/snapshot
GET   /system/resource-changes
```

## New MCP tool

```
list_changed_resources(since?: ISO-8601, limit?: int)
```

Returns `ResourceChangeEvent[]` filtered by timestamp; lets the host
refresh its cache of `cto-os://` URIs without polling each one. Recorded
on every MCP write (skipped under read-only).

## New environment variables

```
CTO_OS_BACKUP_SINK=local | rclone | s3 | scp    # default: local
CTO_OS_BACKUP_DESTINATION=                       # required for mirror
CTO_OS_ENABLE_BACKUP_MIRROR=0                    # off by default
```

(`CTO_OS_MCP_READONLY` from Phase 12 still applies and now causes
audit rows to be written with `blocked=true, readonly_mode=true`.)

## Audit safety behavior

- **Append-only**: `mcp_audit` table has `INSERT` + `SELECT` only — no
  delete/update route, no API for editing.
- **Summary-only**: each row stores `arg_keys` (sorted), `arg_count`,
  outcome (`ok`/`blocked`/`error`), tool name, and project id. **Never**
  raw arg values. Hard-truncated to 1 KB.
- **Always written**: every call to a tool in `WRITE_TOOL_NAMES` writes
  one row, including read-only blocked attempts.
- **Per-project query**: `/projects/{id}/mcp-audit` filters by
  `project_id` from the recorded summary.

## Cron safety behavior

- **Default off**: the worker seeds the six default jobs (`daily_review`,
  `weekly_review`, `backup`, `health_snapshot`, `risk_scan`,
  `github_reconcile`) all `enabled=false`.
- **Type whitelist**: `CronJobType` is a closed enum; unknown types
  reject at `POST /system/cron` with HTTP 400.
- **Worker dispatch**: `CronService.run_due()` runs jobs whose
  `enabled AND next_run_at <= now`. Each run is wrapped in a Phase 11
  `WriterLease(name=f"cron:{job_id}")` so concurrent workers can't fire
  the same job twice.
- **Deterministic-only by default**: `weekly_review` uses the configured
  `CTO_OS_LLM_PROVIDER` (defaults to `deterministic`, so zero API calls).
- **No GitHub writes**: `github_reconcile` calls the read-only reconcile;
  Phase 8's two-gate `auto_reconcile` rules still apply.
- **No shell**.

## Backup mirror safety behavior

- **Three gates**: `CTO_OS_ENABLE_BACKUP_MIRROR=1` + sink + non-empty
  `CTO_OS_BACKUP_DESTINATION`. Otherwise records `skipped` and returns.
- **Verifies first**: the snapshot must pass `SnapshotManager.verify`
  (`PRAGMA integrity_check == "ok"`) before any data is copied.
- **Sink whitelist + safe arguments**:
  - `local`: `shutil.copy2` to `mkdir -p`'d destination.
  - `rclone`: `subprocess.run(["rclone", "copy", <src>, <dst>], ...)` —
    explicit list args, never a shell string. Records `skipped` if the
    binary isn't on `PATH`.
  - `scp`: requires destination match `user@host:/path` regex; records
    `skipped` if scp binary missing.
  - `s3`: requires `boto3`; records `skipped` if not installed. Uses
    `client("s3").upload_file`.
- **Never mirrors WAL/SHM** sidecars — main `.sqlite3` file only.
- **Every attempt** writes a `BackupMirrorEvent` (`completed`,
  `skipped`, or `failed`). Append-only.

## Backup destination behavior

- `BackupPolicy.destination_path` is honored by `SnapshotManager`. When
  the policy is updated, `BackupService.update_policy` calls
  `SnapshotManager.refresh_destination()`.
- Empty path → default `cto_os_api/data/snapshots/`.
- Path is resolved; on any error (permission, invalid, etc.) the manager
  silently falls back to the default rather than writing to an
  unexpected location.
- Rotation (`delete_snapshot`) keeps its Phase 12 guard:
  `Path.resolve().relative_to(snapshot_dir.resolve())`, so a relocated
  destination is still safely constrained.

## Health history behavior

- `POST /system/health/snapshot` writes one `HealthSnapshot` row from
  the current `/system/health` rollup. Designed to be called by the
  `health_snapshot` cron job (hourly by default cadence; enable
  manually).
- `GET /system/health/history` returns `HealthHistorySummary`: last
  status, sample counts for 24h and 7d, degraded counts, down counts,
  latest degraded reasons, and the 30 most recent snapshots.

## Frontend changes

- `/system/mcp-audit` — filterable audit list.
- `/projects/[id]/mcp-audit` + ProjectTabs link — per-project audit.
- `/settings/cron` — list + toggle + cadence + project-id + run-now.
- `/system/health` — adds 24h / 7d / latest-reasons cards + "save
  snapshot now" button.
- `/settings/backups` — adds Mirror Events section.
- Nav: MCP Audit + Cron added at the top level.

## Verification

```bash
.venv/bin/python -m compileall -q cto_os_api
.venv/bin/python -m pytest tests/cto_os -q
(cd cto_os_web && npx tsc --noEmit)
```

## Recommended Phase 14

1. **MCP audit redaction proof** — sign each audit row with a per-process
   key so an attacker can't backdate or forge entries on the SQLite file.
2. **Per-session MCP tokens** — accept a session token on every
   `tools/call` and store it in `MCPAuditEvent.session_id` so a
   co-founder/advisor session is attributable.
3. **Pluggable scheduler** — accept cron-style expressions instead of
   the fixed cadence enum, so `daily @ 9am local` is expressible.
4. **Streaming backups** — mirror as snapshots stream out, instead of
   waiting for the whole file. Lets larger DBs ship to S3 without
   buffering.
5. **Health history retention policy** — currently we keep everything.
   Add a TTL (default 30 days) and a Phase 9-style notification rule
   that fires on sustained `degraded`.
