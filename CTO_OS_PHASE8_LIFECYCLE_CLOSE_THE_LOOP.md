# Phase 8 Lifecycle Close-the-Loop

Phase 8 pulls GitHub state back into the CTO OS and turns shipped work into
institutional memory. It introduces a reconciliation engine, a derived
build-session timeline, post-ship retrospectives, a "What we shipped"
dashboard, and a structured-output upgrade to the code review path.

## New Modules

| Module | Purpose |
|--------|---------|
| `cto_os_api/github_reconciliation.py` | Pull fresh GitHub state for tracked entities; emit `GitHubReconciliationEvent` + `StatusSuggestion`. |
| `cto_os_api/build_session_timeline.py` | Derived view stitching every related artifact into a chronological feed. |
| `cto_os_api/retrospective_generator.py` | Aggregate session/task context into a structured `PostShipRetrospective` with memory/decision/follow-up feedback. |
| `cto_os_api/shipped_dashboard.py` | Server-computed "What We Shipped" aggregate. |

## New Entities

- `StatusSuggestion` — proposed status change for a `task` / `risk` / `build_session`, with evidence; never applied automatically by default.
- `GitHubReconciliationEvent` — diff record for an entity's GitHub-derived state.
- `PostShipRetrospective` — structured retrospective per build session / task.
- Plus the derived view types: `BuildSessionTimeline`, `BuildSessionTimelineItem`, `ShippedSummary`, `ReconciliationReport`.

## Enriched Entities

- `GitHubIssue` — `labels`, `closed_at`, `linked_pr_number`.
- `GitHubPullRequest` — `draft`, `merged`, `merged_at`, `closed_at`, `base_branch`, `head_branch`, `additions`, `deletions`, `changed_files`.

## New Routes

```
POST  /projects/{p}/github/reconcile
GET   /projects/{p}/github/reconciliation-events
GET   /projects/{p}/status-suggestions
POST  /projects/{p}/status-suggestions/{sid}/apply
POST  /projects/{p}/status-suggestions/{sid}/dismiss
GET   /projects/{p}/build-sessions/{sid}/timeline
POST  /projects/{p}/retrospectives/generate
GET   /projects/{p}/retrospectives
GET   /projects/{p}/shipped
```

## Frontend

- `/projects/[id]/status-suggestions` — reconcile, list, apply, dismiss
- `/projects/[id]/retrospectives` — generate + browse, toggle memory/decision/task feedback
- `/projects/[id]/shipped` — counts, completed tasks, lessons, follow-ups, velocity (7d/30d)
- `ProjectTabs` adds `Suggestions`, `Retrospectives`, `Shipped` links

## Reconciliation Safety Model

- **Reads only.** Reconcile fetches issues/PRs via GitHub's read API and writes only `GitHubReconciliationEvent` + `StatusSuggestion` rows.
- **Two-gate auto-mutate:** entity status is only modified automatically when *both*
  1. `auto_reconcile: true` in the request body, AND
  2. `CTO_OS_ALLOW_AUTO_RECONCILE=1` in the environment.
  Otherwise every suggestion stays open until a human hits Apply.
- **Only `Task.status`, `Risk.status`, and `BuildSession.status` are mutable** through this path. No deletions. No GitHub mutations. No entity creation.
- **Degraded mode** — without `GITHUB_TOKEN`, reconcile uses cached GitHub state from `sync_repository`. The report exposes `degraded=true` and the reason.
- Every reconcile call writes an `ExecutionLog`. Every apply writes an `ExecutionLog`.
- Phase 7's `GitHubWriteGuard` remains untouched; Phase 8 introduces no new GitHub writes.

## Structured Code Review

`_llm_review` now requests JSON matching `StructuredCodeReviewOutput`. The
LLM verdict can only **escalate** the deterministic recommendation; it never
de-escalates a security finding. Deterministic provider / parse error /
schema mismatch falls back to the deterministic heuristic — security
patterns still flag and block.

## Memory Feedback Loop (Retrospectives)

When `RetrospectiveGenerateRequest` toggles are on:
- `save_lessons_to_memory` → creates a tagged `Memory` (`["retrospective", "lesson"]`), optionally pinned as source-of-truth.
- `create_decision` → creates a `Decision` of impact level `medium` if risks were found, else `low`.
- `create_follow_up_tasks` → each `follow_up_tasks` entry becomes an ops `Task` linked back to the new memory + decision.

## Verification

```bash
.venv/bin/python -m compileall cto_os_api mempalace
.venv/bin/python -m pytest tests/cto_os -q
(cd cto_os_web && npx tsc --noEmit)
```

Phase 8 tests stub `httpx.get` so no test contacts real GitHub.

## Environment additions

```
CTO_OS_ALLOW_AUTO_RECONCILE=0  # default off; required for auto-apply path
```

## Recommended Phase 9

Phase 8 closes the loop on a single shipped change. **Phase 9** could
extend the system to *operate at portfolio scale*:

1. **Cross-project rollups** — what shipped across every project this week, plus risk concentration heatmap.
2. **Decision graph** — visualise supersedes_decision_id and decision/task/memory linkage as a navigable graph.
3. **Reproducible playbooks** — when a `BuildSession` of a given category completes successfully, distil the steps into a reusable playbook template.
4. **Notifications** — opt-in webhook hooks for `Slack`/Discord/email on retrospective generated, suggestion blocked, write event status changed.
5. **Outcome scoring** — let humans rate a retrospective's accuracy; store the feedback to inform the next LLM call.
