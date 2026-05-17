# cto-os-retrospective

Use to write a post-ship retrospective for a build session.

## Safety
- Memory writes are project-scoped.
- New decisions + follow-up tasks land in the same project.

## Steps

1. `tools/call context_retrospective { project_id, build_session_id?, task_id? }`
2. Read the bundle (`build_session`, `task`, `code_reviews`, `test_runs`,
   `source_of_truth`, `open_risks`).
3. Produce JSON matching `StructuredRetrospectiveOutput`:
   `summary, what_changed, what_worked, what_broke, test_results,
   risks_found, follow_up_tasks, lessons_learned`.
4. POST it to `/projects/{project_id}/llm-results/retrospective`. The
   optional flags `save_lessons_to_memory`, `create_decision`,
   `create_follow_up_tasks`, `pin_to_source_of_truth` control the
   feedback loop.

## Expected output
A `PostShipRetrospective` row + optional `Memory`, `Decision`, and
follow-up `Task`s.
