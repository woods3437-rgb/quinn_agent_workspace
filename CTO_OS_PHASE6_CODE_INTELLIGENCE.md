# Phase 6 Code Intelligence + Controlled Execution

Phase 6 upgrades the private CTO OS so it can reason about repository
structure, observe local git state without mutating it, run a narrow set of
approved test/lint/build/typecheck commands, sync GitHub read-only metadata,
and stitch the whole flow together with Build Sessions.

## Added Modules

| Module | Purpose |
|--------|---------|
| `cto_os_api/code_intelligence.py` | AST-aware Python parsing + regex/TS export parsing. Detects functions, classes, components, route handlers, FastAPI/Flask endpoints, imports, dependencies. |
| `cto_os_api/git_reader.py` | Read-only `git` invocations: branch, status, recent commits, diff stats, optional diff body. |
| `cto_os_api/command_runner.py` | Approval gate + sandbox-friendly `subprocess.run` of allow-listed commands. Stores each run as a `TestRun`. |
| `cto_os_api/github_integration.py` | Status, list-repos, and read-only issue/PR sync. Never POSTs to GitHub. |
| `cto_os_api/repo_operator.py` (extended) | Build Session lifecycle: summarize + save-lessons feedback loop into memory + decisions + follow-up tasks. |

## Added Entities

- `CodeSymbol`, `CodeDependency`
- `ApprovedCommand` (with `ApprovedCommandType` enum: test / lint / typecheck / build)
- `GitStatus`, `GitDiff`, `GitDiffRequest`
- `GitHubIssue`, `GitHubPullRequest`
- `BuildSession` (+ create/update DTOs, `BuildSessionStatus` enum)

## New Routes

```
GET    /projects/{project_id}/repositories/{repository_id}/symbols
GET    /projects/{project_id}/repositories/{repository_id}/symbols/search?q=
GET    /projects/{project_id}/repositories/{repository_id}/dependencies
GET    /projects/{project_id}/repositories/{repository_id}/git/status
POST   /projects/{project_id}/repositories/{repository_id}/git/diff
GET    /projects/{project_id}/repositories/{repository_id}/commands
POST   /projects/{project_id}/repositories/{repository_id}/commands
POST   /projects/{project_id}/repositories/{repository_id}/commands/{command_id}/run
GET    /system/integrations/github/status
GET    /system/integrations/github/repositories
POST   /projects/{project_id}/repositories/{repository_id}/github/sync
GET    /projects/{project_id}/build-sessions
POST   /projects/{project_id}/build-sessions
PATCH  /projects/{project_id}/build-sessions/{session_id}
POST   /projects/{project_id}/build-sessions/{session_id}/summarize
POST   /projects/{project_id}/build-sessions/{session_id}/save-lessons
```

## New Frontend Pages

- `/projects/[id]/symbols`
- `/projects/[id]/commands`
- `/projects/[id]/build-sessions`
- `/projects/[id]/repositories` (Git Status + GitHub Sync buttons inline)

Navigation entries added to `components/ProjectTabs.tsx`: Commands,
Build Sessions, Symbols.

## Safety Model

### Git

`GitReader` only runs:
- `git branch --show-current`
- `git status --porcelain`
- `git log --oneline -5`
- `git diff --stat`
- `git diff` (only when the POST body sets `include_diff: true`)

No writes — no `add`, `commit`, `push`, `reset`, `checkout`, `merge`, or
`rebase` ever execute via Phase 6 code paths.

### Approved Commands

`CommandRunner.validate_command` enforces:

1. Tokenises with `shlex` and rejects shell control characters
   (`| > < ; & ` `` ` `` `$(`).
2. Rejects any token in `BLOCKED_WORDS`:
   `rm, sudo, curl, wget, ssh, scp, git, publish, install, add, commit, push, reset, checkout`.
3. Must start with one of `ALLOWED_PREFIXES`:
   `npm run, pnpm run, yarn, python -m pytest, pytest, npx tsc, npm test, pnpm test, yarn test`.
4. `working_directory` is resolved with `Path.resolve` and clamped inside the
   repository root.
5. Execution uses `subprocess.run(args, ...)` (no shell), with a timeout from
   `CTO_OS_COMMAND_TIMEOUT_SECONDS` (default 60s).
6. Every approved run creates an immutable `TestRun` row including captured
   stdout/stderr.

### GitHub

Read-only. Token (`GITHUB_TOKEN`) + owner (`GITHUB_DEFAULT_OWNER`) are
optional. Without them every endpoint degrades gracefully:
- `status` returns `configured: false`
- `list_repositories` returns `[]`
- `sync_repository` returns empty issue/PR lists

No GitHub POST/PATCH/PUT/DELETE is implemented in Phase 6.

## Build Sessions

A `BuildSession` ties a task to its branch plan, build packet, PR packet,
code reviews, test runs, implementation reviews, and lessons. Two helpers
on `RepoOperator`:

- `summarize_build_session` pulls live counts from related tables and
  writes a human-readable summary onto the session.
- `save_build_session_lessons` creates a memory tagged
  `build-session, lesson`, opens a low-impact `Decision` capturing the
  takeaway, and (when the session is `completed` and linked to a task)
  files a medium-priority ops follow-up `Task` linked to both.

## Verification

Run from the repo root:

```bash
.venv/bin/python -m compileall cto_os_api mempalace
.venv/bin/python -m pytest tests/cto_os -q
(cd cto_os_web && npx tsc --noEmit)
```

The Phase 6 test suite covers AST parsing (Python + TS), git status
read-only behavior, command runner block/allow paths, build session
lifecycle (summarize + save lessons), AI code review deterministic
fallback, GitHub-status-without-token, and project-scoped memory isolation.

## Recommended Phase 7

Controlled GitHub *writing* gated behind explicit human approval:

- Create GitHub issues from CTO OS tasks.
- Draft (but never send) PR descriptions from PR packets.
- Optionally create branches via the API.
- Never auto-merge, never auto-push.
