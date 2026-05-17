# cto-os-daily-review

Use first thing in the morning. Combines control room + shipped + the
deterministic `DailyReview` aggregator into a tight standup brief.

## Safety
- Read-only on CTO OS state.
- Cross-project metadata only — no memory content bleeds across projects.

## Steps

1. POST `/system/daily-review/generate` (no body) — returns a
   `DailyReview` with a pre-rendered `markdown` field.
2. (Optional) `resources/read cto-os://system/control-room` for context.
3. (Optional) `resources/read cto-os://system/shipped` for the
   what-shipped-this-week view.
4. Reply with the `markdown` from step 1, then append 3–5 sharper
   recommended next actions in your own voice (these supplement, never
   replace, the aggregator's `recommended_next_actions`).

## Expected output
A daily standup-ready markdown brief with concrete IDs the user can
click through.
