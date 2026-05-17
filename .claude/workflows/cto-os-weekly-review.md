# cto-os-weekly-review

Use to assemble a weekly portfolio review.

## Safety
- Cross-project surfaces expose metadata only — no memory content bleeds
  across projects.

## Steps

1. `resources/read cto-os://system/control-room`
2. `resources/read cto-os://system/shipped`
3. (Optional, per project) `resources/read cto-os://projects/{id}/shipped`
4. Produce a tight markdown summary:
   - **Shipped this week** — completed sessions + merged PRs per project
   - **Open risks** — concentration by severity, themes
   - **Blocked / stale** — anything from the control-room recommended
     actions
   - **Next best actions** — three concrete moves

## Expected output
Markdown the user can paste into a standup or weekly review note. CTO OS
already has a Phase 3 weekly-brief generator if you want a persisted
artifact instead — call `POST /projects/{id}/briefs/weekly/generate`.
