# Phase 15 Real-World Repository Usability

Phase 15 hardens CTO OS against real production repositories and removes
the friction discovered during dogfood. No new platform abstractions, no
new audit/policy infra, no orchestration layers — six targeted fixes that
make the existing loop behave honestly on arbitrary stacks (React Native,
Expo, Next.js, Python services, monorepos, mixed mobile/web).

## What changed

| Area | Module(s) | Fix |
|------|-----------|-----|
| Repo scan | `cto_os_api/repo_scanner.py` | Reads `.gitignore`, walks via `git ls-files` (falls back to `rglob`), and extends `IGNORE_DIRS` (Pods, DerivedData, .gradle, .expo, .turbo, .cache, vendor, target, …). Detects Expo, React Native, React Navigation, Firebase, TypeScript. |
| Candidate files | `cto_os_api/repo_operator.py` | New `_extract_filename_hints` + `_FILENAME_HINT_RE`; 2-char term floor; stopword filter; literal-filename and basename-match boosts; fallback uses `scan.key_files` + root config files instead of alphabetical first dozen. Slug drops stopwords and caps at 40 chars. |
| Build packet | `cto_os_api/execution_engine.py` | `generate_build_packet` derives `files_likely_involved` from the repo (via `_candidate_files` + `scan.key_files`) and `test_plan` from `scan.test/build/lint_commands`. The old CTO-OS defaults (`cto_os_api/*`, `compileall`, …) are gone. |
| Project brief | `cto_os_api/workspace_generators.py` | `current_brief` derives every field from the project's own state (repo scan → pinned-memory fallback → "Not detected yet" hint). The hardcoded `"FastAPI, Next.js, MemPalace/ChromaDB, local JSON metadata."` leak is removed; pinned-memory tech stack and `store.list_risks()` populate the brief. |
| Command runner | `cto_os_api/command_runner.py` | Removed blanket `git` block. Added `GIT_READ_SUBCOMMANDS = {status, diff, log, check-ignore, ls-files, show-ref, branch, rev-parse}` and matching `ALLOWED_PREFIXES`. Write verbs (commit, push, reset, checkout, merge, rebase, clean, pull, fetch) are explicitly blocked; `git branch -D/-d/--delete/-m/--move/-c/--copy/-f/--force` is special-cased. |
| Git reader | `cto_os_api/git_reader.py` | Added `read_diff`, `check_ignore` (with `--no-index --verbose`), and `ls_files` (`--cached --others --exclude-standard`). |
| Build session linkage | `cto_os_api/sqlite_store.py` | `create_build_session` auto-fills `linked_build_packet_id` and `linked_branch_plan_id` from the most recent task-scoped artifacts when the caller leaves them blank and `task_id` is set. Never overwrites explicit values. |

## New routes

```
POST /projects/{project_id}/repositories/{repository_id}/code-reviews/from-git
```

Reads the working-tree diff via `GitReader.read_diff` and hands it to
`RepoOperator.review_diff`. Returns `400` with a structured body when the
diff is empty (so the operator gets a sensible "nothing to review" instead
of a crash).

## New MCP tools

Nine new tools registered by `MCPToolset._register_phase15_entrypoints`,
bringing the toolset from 36 → 45. Seven are tagged in `WRITE_TOOL_NAMES`
so MCP read-only mode and the audit pipeline pick them up.

| Tool | Kind | Notes |
|------|------|-------|
| `create_project` | write | Idempotent on `name`. |
| `create_repository` | write | Idempotent on `local_path`. |
| `scan_repository` | write | Same handler as the HTTP scan. |
| `index_repo_to_memory` | write | Pushes the scan's key surfaces into the memory engine. |
| `summarize_build_session` | write | Wraps the existing summarizer. |
| `generate_retrospective` | write | Constructs a fresh `RetrospectiveGenerator`. |
| `review_diff_from_git` | write | Returns `{isError: True, reason: …}` when the diff is empty instead of throwing. |
| `git_check_ignore` | read | Read-only `git check-ignore --no-index --verbose`. |
| `git_ls_files` | read | Read-only `git ls-files --cached --others --exclude-standard`. |

## New env vars

None. Phase 15 is an internal-quality phase — no new toggles, no new
endpoints to authenticate, no new schedules.

## Safety behavior

- **Phase 7 GitHub write gate is unchanged.** CTO OS still does not commit,
  push, open PRs, or merge. The new git verbs added to `CommandRunner` are
  exclusively read-only.
- **Phase 11 MCP read-only mode and Phase 14 session read-only/revoke are
  honored.** The seven Phase 15 write tools are present in
  `WRITE_TOOL_NAMES`, so a read-only session still refuses them and the
  refusals are audited.
- **Phase 13 audit retention two-gate is unchanged.** Audit rows remain
  append-only; cron + retention behavior is untouched.
- **Empty-diff handling.** `review_diff_from_git` returns a structured
  `{isError: True, reason: "No working-tree diff to review …"}` payload
  instead of producing an empty review or 500. Same with the HTTP route
  (`400` with `{"detail": …}`).
- **`git check-ignore --no-index --verbose`** runs against the repository's
  configured `local_path`, never an arbitrary path supplied by the caller —
  the toolset resolves the repository row first.

## Verification

```
.venv/bin/python -m compileall -q cto_os_api          # clean
.venv/bin/python -m pytest tests/cto_os -q            # 267 passed
.venv/bin/python /tmp/phase15_neutral_smoke.py        # PASS (10 stages)
```

The 267 tests include 218 pre-Phase-15 tests plus 49 new tests across
eight modules (`tests/cto_os/test_phase15_*.py`): scanner gitignore
handling, candidate-file ranking + slug, build-packet derivation, brief
honesty, command-runner allow-list, git-reader round-trip, build-session
auto-linking, and the new MCP entrypoints.

The neutral end-to-end smoke runs the full setup → scan → branch-plan →
build-packet → diff-review flow against a synthetic Python+TypeScript
repo with a `vendor/third_party/` noise directory. The flow correctly:
detects Python + Node.js + TypeScript, surfaces real configs in
`key_files` (no vendor leak), produces `cto/refactor-service-auth-py-…`
as the branch slug, ranks `service/auth.py` first among recommended
files (basename-match boost), derives `npm run test` / `python -m pytest`
/ `npm run build` / `npm run lint` as the test plan from `package.json`
scripts (no `compileall` leak), and returns a structured empty-diff
payload before the working tree is modified.

The MCP toolset reports 45 tools and 18 writes after Phase 15
registration.

## Known limitations / next steps

- The `.gitignore` parser is intentionally a subset: directory suffixes,
  name globs, rooted paths. Negation, `**`, and character classes fall
  back to git's own `check-ignore`. This is fine because scanning uses
  `git ls-files --exclude-standard` as the primary source — the parser
  is only the secondary guard for directories `git` doesn't see.
- `_candidate_files` still uses simple substring scoring. A future phase
  could swap in a smaller embedding-based reranker; for now the
  basename-match + filename-hint boosts cover the common cases the
  dogfood found.
- The HTTP route returns `400` on empty diff to stay HTTP-conventional;
  the MCP tool returns `{isError: True}` because MCP clients expect
  structured payloads rather than HTTP status codes.
