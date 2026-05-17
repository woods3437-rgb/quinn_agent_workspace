# Phase 5 Repo-Aware Operator

Phase 5 adds safe local repository awareness to the private CTO OS.

## Added

- Local repository scanner using `Repository.local_path`.
- Repo scan summaries and repo file indexing.
- Repo context indexing into project memory.
- Branch plan generation for tasks/build packets.
- PR packet generation without GitHub mutation.
- Pasted diff/patch review.
- Test run tracking.
- Durable job polling entry point: `python -m cto_os_api.worker`.
- GitHub status-only integration boundary.

## Safety Rules

- No destructive git commands.
- No commits.
- No pushes.
- No PR creation.
- Repo scanning ignores `.git`, `node_modules`, build outputs, virtualenvs, env files, and large/binary files.
- Scanner stores summaries and metadata, not raw secret/env content.

## Worker

Run:

```bash
python -m cto_os_api.worker
```

The worker polls queued SQLite jobs and handles repo scans, semantic indexing, risk scans, weekly briefs, implementation reviews, and build packet generation.
