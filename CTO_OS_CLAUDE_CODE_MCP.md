# Phase 10 — Claude Code / Cowork Native MCP

Phase 10 lets Claude Code (or any MCP host) use the CTO OS as its local
operating system **without an Anthropic or OpenAI key inside the CTO OS**.

```
Claude Code / Cowork           ← the reasoning/model layer
        │
        ▼  stdio JSON-RPC
   CTO OS MCP server (python -m cto_os_api.mcp_server)
        │
        ▼  in-process
   SQLiteStore · MemPalace · repo scanner · GitHub read boundary
```

## Why this exists

- **No CTO OS calls Anthropic.** In MCP mode the host model does all the
  reasoning. The CTO OS still uses the deterministic provider for any
  ambient automation (workers, schedulers).
- **Deterministic fallback is preserved.** `CTO_OS_LLM_PROVIDER=deterministic`
  keeps everything working when MCP isn't connected.
- **OpenAI / Anthropic providers stay optional.** Set the env vars if you
  want the FastAPI to also drive LLM calls; ignore them otherwise.

## Run

```bash
python -m cto_os_api.mcp_server
```

The server speaks JSON-RPC 2.0 on stdio (one message per line, UTF-8). Logs
go to stderr.

## Connect Claude Code (project-scoped)

Copy `.mcp.example.json` to `.mcp.json` (or merge into an existing one) at
the project root. Claude Code will pick it up.

```json
{
  "mcpServers": {
    "cto-os": {
      "command": "/abs/path/to/.venv/bin/python",
      "args": ["-m", "cto_os_api.mcp_server"],
      "cwd": "/abs/path/to/we-are-building-an-internal-only",
      "env": {
        "CTO_OS_LLM_PROVIDER": "deterministic",
        "CTO_OS_SQLITE_PATH": "cto_os_api/data/cto_os.sqlite3",
        "CTO_OS_DATA_PATH": "cto_os_api/data/cto_os.json",
        "CTO_OS_CHROMA_CACHE_DIR": "cto_os_api/data/chroma_cache"
      }
    }
  }
}
```

## Connect Claude Desktop

Drop `claude_desktop_config.example.json` into your Claude Desktop config
directory (`~/Library/Application Support/Claude/claude_desktop_config.json`
on macOS).

## Exposed tools

**Project**
- `list_projects`
- `get_project`
- `get_project_brief`
- `get_control_room_summary`

**Memory**
- `search_project_memory` (project-scoped by default; `cross_project=true`
  must be explicit)
- `save_project_memory`
- `list_source_of_truth_memory`
- `pin_memory`

**Tasks**
- `list_tasks`
- `get_task`
- `create_task`
- `update_task`
- `list_status_suggestions`

**Repo**
- `list_repositories`
- `get_repo_scan`
- `search_repo_files`
- `search_repo_symbols`
- `get_git_status`  *(read-only `git status --porcelain`)*

**Execution**
- `generate_build_packet`
- `create_branch_plan`
- `create_pr_packet`
- `review_diff_context`  *(returns context bundle)*
- `save_code_review_result`  *(persists host-model verdict)*
- `create_test_run`
- `create_build_session`
- `summarize_build_session_context`  *(returns the timeline)*
- `save_lesson_to_memory`

**Context bundles** (return prompt + schema + save_endpoint)
- `context_code_review`
- `context_retrospective`
- `context_implementation_plan`
- `context_build_packet`

**GitHub — PREVIEW ONLY**
- `preview_github_issue`
- `preview_github_branch`
- `preview_github_draft_pr`

> `create_github_*` tools are **not** exposed in MCP. GitHub mutations
> remain gated behind Phase 7's three checks
> (`CTO_OS_ALLOW_GITHUB_WRITES=1` + token + per-call approval) and are
> only callable via the UI / REST.

## Example workflow

1. `list_projects` → pick `proj_abc123`.
2. `list_tasks(project_id=proj_abc123)` → identify the next task.
3. `get_git_status(project_id, repository_id)` → see what's pending locally.
4. `generate_build_packet(project_id, task_id)` → CTO OS produces a packet.
5. **Edit code locally**, then ask the host to run an approved command via
   the FastAPI `/commands` endpoint (still required for shell execution).
6. `review_diff_context(project_id, diff_text="<git diff output>", task_id)`
   → CTO OS returns the structured context bundle.
7. The host model produces a JSON object matching
   `StructuredCodeReviewOutput`.
8. `save_code_review_result(project_id, ..., recommendation=..., ...)` →
   CTO OS persists a real `CodeReview` row.
9. `create_test_run(...)` → record the result of the approved command.
10. `summarize_build_session_context(project_id, session_id)` → see the
    timeline of everything that happened.
11. `save_lesson_to_memory(project_id, title, content)` → close the loop.

## Safety model

- **Shell**: MCP cannot run shell commands. The Phase 6 `CommandRunner`
  approval flow remains the only path; the host calls it via REST when it
  wants to run an approved test/lint/typecheck/build command.
- **GitHub writes**: MCP exposes only `preview_*` tools. Phase 7's
  guard is unchanged and enforced by `repo_operator`.
- **Memory**: project-scoped by default. The host has to pass
  `cross_project=true` explicitly to widen scope; aggregators in Phases 8/9
  never do that.
- **Auth**: the MCP server runs in-process under the same user that owns
  `cto_os.sqlite3`. No tokens are forwarded; FastAPI's internal auth is
  irrelevant in MCP mode.
- **No new outbound HTTP**: the MCP code paths don't introduce any new
  external calls. GitHub read sync still requires `GITHUB_TOKEN` if invoked.

## Verification

```bash
.venv/bin/python -m pytest tests/cto_os -q
.venv/bin/python -m cto_os_api.mcp_server   # interactive smoke (Ctrl+C to exit)
```

Smoke check (paste into stdin once running):

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"list_projects","arguments":{}}}
```
