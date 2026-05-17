# cto-os-save-lesson

Use to persist a lesson learned into project memory.

## Safety
- Project-scoped only.
- Optionally pin as source-of-truth.

## Steps

1. Confirm the `project_id`.
2. `tools/call save_lesson_to_memory { project_id, title, content, pinned? }`

## Expected output
A `Memory` row tagged `lesson`, indexed in the engine, optionally pinned
as source-of-truth.
