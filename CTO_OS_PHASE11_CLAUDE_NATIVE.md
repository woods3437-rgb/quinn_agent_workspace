# Phase 11 Claude-Native Operating Mode

Phase 11 makes the Phase 10 MCP layer pleasant to use inside Claude Code /
Cowork: a dedicated subagent, workflow recipes, MCP **resources** and
**prompts**, a posture self-check tool, hardened SQLite for concurrent
processes, and an opt-in webhook intake boundary.

## New modules

| Module | Purpose |
|--------|---------|
| `cto_os_api/mcp_resources.py` | URI dispatch + read handlers for `cto-os://` resources. |
| `cto_os_api/mcp_prompts.py` | Prompt template registry (`prompts/list`, `prompts/get`). |
| `cto_os_api/writer_lease.py` | Short-lived writer lease context manager. |
| `cto_os_api/intake.py` | Three-gated webhook intake (env + secret + HMAC). |

## New MCP capabilities

### Resources
Read-only URI hydration without burning a `tools/call`:

```
cto-os://projects
cto-os://projects/{id}/brief
cto-os://projects/{id}/source-of-truth
cto-os://projects/{id}/recent-activity
cto-os://projects/{id}/risks
cto-os://projects/{id}/tasks
cto-os://projects/{id}/shipped
cto-os://system/control-room
cto-os://system/shipped
```

### Prompts
Server-defined templates for the canonical CTO OS flows:

```
cto_os_start_task
cto_os_review_diff
cto_os_retrospective
cto_os_weekly_review
cto_os_save_lesson
cto_os_generate_build_packet
```

### Safety self-check tool
`get_mcp_safety_report` returns a structured `MCPSafetyReport` with the
current MCP posture: `github_writes_in_mcp`, `shell_in_mcp`,
`write_tools`, `preview_tools`, `read_tools`, `sqlite_path`,
`sqlite_journal_mode`, `provider_mode`, plus the four env-gate states.

## SQLite concurrency

`SQLiteStore` now:
- Sets `PRAGMA journal_mode = WAL` once at schema init (persistent on the file).
- Sets `PRAGMA synchronous = NORMAL` (durable + fast enough for an internal tool).
- Sets `PRAGMA busy_timeout = 5000` on every connection so short writer collisions block rather than error.

`writer_lease.WriterLease` provides a context-managed coarse lease for the
truly-destructive ops (snapshot restore, project import). Per-row writes
do **not** take a lease — WAL + busy_timeout is enough.

```python
from cto_os_api.writer_lease import WriterLease

with WriterLease(store, "snapshot_restore") as lease:
    ...  # destructive op
```

## Webhook intake boundary

`POST /intake/events`. Off by default.

Three gates (all required):
1. `CTO_OS_ENABLE_WEBHOOK_INTAKE=1` in env.
2. `CTO_OS_WEBHOOK_SECRET` non-empty.
3. Request includes header
   `X-CTO-OS-Signature: sha256=<hex hmac-sha256(raw_body, secret)>`.

Without all three, the endpoint returns 503 (gate off) or 401 (bad
signature) and persists nothing.

Accepted `source` values:
- `linear.issue.created`
- `linear.issue.updated`
- `sentry.issue.created`
- `github.webhook.raw`
- `manual.note`

**Never runs an LLM.** Only stores the event as `IntakeEvent`. Pass
`?create_suggestion=1` to additionally file one `StatusSuggestion` for
the user to triage. UI at `/settings/intake`.

## Claude Code subagent + workflows

- `.claude/agents/cto-os.md` — the subagent definition. Use it whenever
  you operate CTO OS through Claude Code. Pre-loads the safety rules,
  forbids GitHub writes / shell out of MCP, asks for `project_id` when
  missing, defaults to project-scoped memory.
- `.claude/workflows/cto-os-*.md` — five recipe docs: start task, review
  diff, retrospective, weekly review, save lesson.

## Safety behavior

- **No new outbound HTTP** in MCP. Resources + prompts are local.
- **No new write surface** in MCP. The safety report tool enumerates the
  exact write tools (audit-friendly).
- **Memory isolation** preserved: `MCPResourceProvider` always reads
  per-project; cross-project surfaces still expose metadata only.
- **Intake** never autostarts an LLM; suggestions are off by default.
- **Phase 7 + Phase 10 invariants unchanged**: no `create_github_*`
  tools, no shell tools.

## How to use inside Claude Code

1. Copy `.mcp.example.json` to `.mcp.json` (or merge) and adjust paths.
2. Open a Claude Code session in the project; the `cto-os` subagent + MCP
   server attach automatically.
3. Ask: *"Use the cto-os subagent to start the next task in project X."*
4. The agent will read the brief + source-of-truth via resources, fetch
   the `cto_os_start_task` prompt, then walk through the build-packet flow.
5. For ad-hoc work, fetch any prompt: `prompts/get cto_os_review_diff
   project_id=… diff=…`.

## Verification

```bash
.venv/bin/python -m compileall -q cto_os_api
.venv/bin/python -m pytest tests/cto_os -q
(cd cto_os_web && npx tsc --noEmit)
```

Smoke check (MCP resources + prompts over stdio):

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}
{"jsonrpc":"2.0","id":2,"method":"resources/list","params":{}}
{"jsonrpc":"2.0","id":3,"method":"prompts/list","params":{}}
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_mcp_safety_report","arguments":{}}}
```

## Recommended Phase 12

Phase 11 makes CTO OS a Claude-native operating system. Phase 12 should
make it **multi-session safe and observable**:

1. **MCP completion notifications** — emit `notifications/resources/updated`
   when projects/tasks/build sessions change so the host can refresh
   without polling.
2. **Streaming tool results** for expensive aggregates (system shipped,
   decision graph) so long renders don't block the host turn.
3. **WAL checkpoint hook** on `SnapshotManager.create_snapshot` so hot
   snapshots are guaranteed consistent.
4. **Audit log** for every MCP write — append-only, signed by the
   writer lease holder so cross-process attribution survives.
5. **Token-scoped read-only mode** — boot the MCP server with
   `CTO_OS_MCP_READONLY=1` and every write tool becomes a clean no-op
   that returns a structured "blocked: read-only" content block.
