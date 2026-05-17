# cto-os-review-diff

Use to review a diff using the host model with full CTO OS context.

## Safety
- Read-only on GitHub. No PR is opened from this flow.
- The deterministic CTO OS path will still flag secrets even if your
  review says approve; CTO OS escalates, never de-escalates.

## Steps

1. `tools/call context_code_review { project_id, diff_text, task_id?, branch_plan_id? }`
2. Read the bundle (`memories`, `source_of_truth`, `decisions`,
   `diff_text`, `output_schema`).
3. Produce JSON matching `StructuredCodeReviewOutput` — `recommendation`
   is one of `approve | revise | block`. Escalate (never de-escalate) any
   deterministic security finding visible in the diff.
4. `tools/call save_code_review_result { project_id, diff_text,
   recommendation, summary, blocking_issues, … }` — or POST to
   `/projects/{project_id}/llm-results/code-review` with the same body.

## Expected output
A persisted `CodeReview` in CTO OS with risk level, findings, and
optional auto-created follow-up tasks.
