# Phase 14 Identity, Retention, and Trust Hardening

Phase 14 adds per-session MCP identity, HMAC-signed audit rows,
retention policies, cron expression support, streaming backups, and
health alert rules.

## New modules

| Module | Purpose |
|--------|---------|
| `cto_os_api/mcp_sessions.py` | Resolve session id; touch row; revoke / read-only gates. |
| `cto_os_api/audit_signing.py` | Canonical payload + HMAC-SHA256 sign + verify. |
| `cto_os_api/retention_service.py` | Defaults + cleanup with audit two-gate. |
| `cto_os_api/cron_expression.py` | Minimal cron parser + next-fire (no `croniter`). |
| `cto_os_api/health_alerts.py` | Rule evaluator wired into health snapshots. |

## New routes

```
GET   /system/mcp-sessions
POST  /system/mcp-sessions
PATCH /system/mcp-sessions/{session_id}
POST  /system/mcp-sessions/{session_id}/revoke
POST  /system/mcp-audit/verify
GET   /system/mcp-audit/filtered
GET   /system/retention
PATCH /system/retention/{target}
POST  /system/retention/run
GET   /system/health/alert-rules
POST  /system/health/alert-rules
PATCH /system/health/alert-rules/{id}
POST  /system/health/alert-rules/evaluate
```

## New env vars

```
CTO_OS_MCP_SESSION_ID=          # fallback when params._meta.sessionId is absent
CTO_OS_AUDIT_SIGNING_KEY=       # HMAC-SHA256 key; signatures disabled if empty
```

## Safety behavior

### MCP sessions
- Resolution order: `arguments._session_id` (injected by `mcp_server` from `params._meta.sessionId`) → `CTO_OS_MCP_SESSION_ID` env → `"unknown"`. Truncated to 128 chars.
- Auto-create + touch on every call; `last_seen_at` updated.
- `session.revoked` → refuse all tools with structured blocked payload, write audit row.
- `session.readonly` (per-session) OR `CTO_OS_MCP_READONLY` env → refuse write tools only; reads + previews still work; audit row tagged `blocked=true, readonly_mode=true`.
- Phase 12 read-only env is still respected; session-level read-only is additive.

### Audit signing
- Canonical payload = `json.dumps({id, session_id, tool_name, project_id, action_type, request_summary, response_summary, blocked, readonly_mode, created_at}, sort_keys=True, separators=(",", ":"))`.
- Signature = `"sha256=" + hmac.sha256(key, payload)` when `CTO_OS_AUDIT_SIGNING_KEY` is set.
- `signing_key_id` = `sha256(key)[:12]` so rotated keys are distinguishable.
- `verify` returns one of `unsigned | valid | tampered | key_missing` per row.
- Signature absent ≠ failure; tamper of any signed field flips status to `tampered`.

### Retention
- Per-target policies seeded once with the defaults from the spec.
- `RetentionService.run()` iterates enabled policies; skips disabled ones.
- **`mcp_audit` two-gate**: even when enabled, only deletes if `hard_delete_allowed=true`. Otherwise records `skipped: mcp_audit deletion requires hard_delete_allowed=true`.
- Per-target SQL deletes are bounded to the specific table; no cross-table effects.
- New `retention_cleanup` cron type dispatches `RetentionService.run()` — itself cron-gated and off by default.

### Cron expressions
- Subset of standard cron, validated at create + update.
- `cron_expression` overrides `cadence` when set; cadence remains the fallback.
- Next-fire calculator caps at 366 days of forward minute-scan; never freezes the worker.
- Invalid expression falls back to the cadence interval rather than wedging the job.

### Health alerts
- Evaluator runs at the end of `HealthHistoryService.snapshot()` (and on demand via REST).
- Conditions: `degraded_samples`, `failed_jobs`, `backup_overdue`, `worker_stale`.
- On trigger, emits a `NotificationService.notify(event_type=f"health.alert.{rule.name}", ...)` call. The Phase 9 three-gate still applies — without `CTO_OS_ENABLE_NOTIFICATIONS=1` + an enabled rule matching the event type, the notification lands as `skipped`.
- No GitHub writes, no shell, no LLM call.

### Streaming backups
- `_copy_local` now streams in 1 MiB chunks, preserves mtime, records `bytes_copied`.
- `_copy_s3` switches to `upload_fileobj` for streamed uploads.
- `rclone` / `scp` still use `subprocess.run` with explicit list args — no `shell=True` anywhere.

## Frontend

- `/system/mcp-audit` rebuilt with filters (tool, session, blocked, readonly, signature), JSON export, and a "Verify signatures" rollup.
- `/system/mcp-sessions` — list, pre-create, toggle read-only, revoke.
- `/settings/retention` — per-target toggle, days-to-keep, `hard_delete_allowed`, run-now.
- `/settings/health-alerts` — list, create, toggle, evaluate-now.
- Nav gets MCP Sessions, Retention, Health Alerts.

## Verification

```bash
.venv/bin/python -m compileall -q cto_os_api
.venv/bin/python -m pytest tests/cto_os -q
(cd cto_os_web && npx tsc --noEmit)
```

## Recommended Phase 15

> Note: feature-build pause recommended after Phase 14 — dogfood on dscvr before adding more surface area. Phase 15 ideas captured here for whenever you're ready.

1. **Audit chain hashes** — link each `MCPAuditEvent.signature` to the previous one (Merkle-style) so a deletion in the middle of the log is detectable, not just a field tamper.
2. **Session-scoped API tokens** — accept `Authorization: Bearer <token>` on REST routes and resolve to an `MCPSession`, so a co-founder/advisor can hold a read-only token without seeing the admin token.
3. **Cron expression UI** — replace the text input with a builder that previews the next 5 fires; useful for non-engineers.
4. **Health alert routing** — `notification_rule_id` is currently advisory (`event_type` matching). Make it a hard route: only the named rule receives the event regardless of event_type.
5. **Retention dry-run** — return how many rows *would* be deleted without actually deleting, so policy changes don't surprise you.
