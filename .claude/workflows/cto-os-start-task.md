# cto-os-start-task

Use when starting work on a CTO OS task. The MCP prompt
`cto_os_start_task` returns the structured version of this recipe.

## Safety
- No GitHub writes from MCP.
- No shell commands from MCP.
- Project memory is project-scoped; don't widen scope without being asked.

## Steps

1. `resources/read cto-os://projects/{project_id}/brief`
2. `resources/read cto-os://projects/{project_id}/source-of-truth`
3. `tools/call list_tasks { project_id }` → pick a task (or use the one
   the user named).
4. `tools/call list_repositories { project_id }` and
   `tools/call get_repo_scan { project_id, repository_id }` for the repo
   you'll touch.
5. `tools/call get_git_status { project_id, repository_id }` so you know
   what's already pending locally.
6. `tools/call context_build_packet { project_id, task_id }`
7. Produce JSON matching the bundle's `output_schema`.
8. POST it to the bundle's `save_endpoint` (or call
   `tools/call save_build_packet_result …` via REST).

## Expected output
A persisted `BuildPacket` in CTO OS the user can hand to a coding
agent or implement directly.

## Save-back
The bundle's `save_endpoint` is
`/projects/{project_id}/llm-results/build-packet`.
