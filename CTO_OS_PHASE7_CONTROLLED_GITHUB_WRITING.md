# Phase 7 Controlled GitHub Writing

Phase 7 extends the private CTO OS with a narrow, audit-logged set of GitHub
write actions. Every write is off by default, off without a token, and off
without explicit per-call approval. There is no merge, no delete, no force
push, no visibility change, no collaborator change — and no method to add
those operations.

## New Module

- `cto_os_api/github_write_guard.py` — `GitHubWriteGuard` enforces the three
  gates and exposes `BLOCKED_GITHUB_OPS` plus `sanitise_branch_name`.

## Allowed Write Actions

| Action            | Source entity | Endpoint                                                                        |
|-------------------|---------------|---------------------------------------------------------------------------------|
| create_issue      | Task          | `POST /projects/{p}/tasks/{t}/github/{preview-issue,create-issue}`              |
| create_issue      | Risk          | `POST /projects/{p}/risks/{r}/github/{preview-issue,create-issue}`              |
| create_branch     | Branch plan   | `POST /projects/{p}/branch-plans/{b}/github/{preview-branch,create-branch}`     |
| create_draft_pr   | PR packet     | `POST /projects/{p}/pr-packets/{pr}/github/{preview-draft-pr,create-draft-pr}`  |

Plus `GET /projects/{p}/github/write-events` for the audit log.

## Three-Gate Safety Model

Every write must pass **all three** gates. Otherwise the call records a
`GitHubWriteEvent` with `status=blocked` and returns HTTP 400.

1. **Process kill switch** — `CTO_OS_ALLOW_GITHUB_WRITES=1`. Default is `0`.
2. **Auth present** — `GITHUB_TOKEN` set.
3. **Per-call approval** — request body has `approved: true` AND
   `dry_run: false`.

## Preview vs Create

- `preview-*` endpoints **always** run dry. They build the exact payload the
  create endpoint would send and persist a `GitHubWriteEvent` with
  `status=previewed`. They do not contact GitHub.
- `create-*` endpoints attempt to send if the three gates pass. They persist
  a `GitHubWriteEvent` regardless of outcome (`completed`, `blocked`,
  `failed`). On success they update the source entity (`Task`, `Risk`,
  `BranchPlan`, `PRPacket`) with `github_*_url`, `github_*_number`, and
  `github_sync_status`.

Every create call also writes an `ExecutionLog` (event_type `generation`).
When the caller passes `build_session_id`, the event is attached to the
linked build session.

## Permanently Blocked Operations

Hard-coded in `github_write_guard.BLOCKED_GITHUB_OPS`. No method ever added:

- `merge_pr`
- `delete_repo`
- `delete_branch`
- `force_push`
- `update_secrets`
- `change_visibility`
- `invite_collaborator`
- `create_public_repo`

## Entity Changes

- `Task`, `Risk` — `github_issue_number`, `github_issue_url`,
  `github_sync_status`.
- `BranchPlan` — `github_branch_name`, `github_branch_url`,
  `github_sync_status`.
- `PRPacket` — `github_pr_number`, `github_pr_url`, `github_sync_status`.
- `BuildSession` — `linked_github_write_event_ids` keeps the timeline of
  write activity attached to a session.

## New Entity

`GitHubWriteEvent` — append-only audit row stored in `github_write_events`:

```
id, project_id, repository_id, entity_type, entity_id, action,
dry_run, approved, payload_json, response_json, status,
error_message, build_session_id, created_at
```

## Frontend

- `cto_os_web/app/projects/[id]/github-events/page.tsx` — list, filter, and
  inspect every write event.
- `tasks`, `risks`, `branch-plans`, `pr-packets` pages each gained a Preview
  → Confirm-and-create button pair. Preview must run before Create is shown.
- `ProjectTabs` adds the `GitHub Events` link.

## Environment

```
GITHUB_TOKEN=                 # required for any GitHub call (read or write)
GITHUB_DEFAULT_OWNER=         # used when repository.url is empty
CTO_OS_ALLOW_GITHUB_WRITES=0  # set to 1 to enable writes (default off)
```

## Verification

```bash
.venv/bin/python -m compileall cto_os_api mempalace
.venv/bin/python -m pytest tests/cto_os -q
(cd cto_os_web && npx tsc --noEmit)
```

Phase 7 tests stub `httpx.post` / `httpx.get` so no test ever contacts real
GitHub. The suite covers:
- Guard enforcement (env off, no token, no approval, dry-run defaults).
- Branch-name sanitiser.
- Preview routes produce payloads, write `previewed` events, never call
  GitHub.
- Create routes with the gates open POST to fake GitHub and update entity
  sync fields.
- Create routes with the gates closed record `blocked` events and 400.
- BLOCKED_GITHUB_OPS rejection.

## Recommended Phase 8

A natural follow-on is **Decision-driven retrospective + lifecycle
management**: once issues, branches, and PRs flow back from GitHub, the
build session timeline knows when work *actually* shipped vs. only
planned. Phase 8 could:

1. Sync PR merge/close state back into `BuildSession` lifecycle.
2. Auto-close CTO OS tasks when their linked GitHub issue closes (still
   read-only on the GitHub side).
3. Generate post-ship retrospectives from `BuildSession` + closed
   `GitHubPullRequest` + executed `TestRun` data.
4. Expose a "What did we actually ship this week?" dashboard distinct from
   the existing weekly brief (which is plan-centric).
