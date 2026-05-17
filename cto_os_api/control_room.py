"""Phase 9 — system-wide control room aggregator."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import (
    BuildSessionStatus,
    ControlRoomProjectStat,
    ControlRoomSummary,
    JobStatus,
    RiskStatus,
    TaskStatus,
)
from .staleness import StalenessDetector, _ensure_aware
from .sqlite_store import SQLiteStore


class ControlRoom:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self.staleness = StalenessDetector(store)

    def build(self) -> ControlRoomSummary:
        now = datetime.now(timezone.utc)
        seven = now - timedelta(days=7)

        projects = self.store.list_projects()
        per_project: list[ControlRoomProjectStat] = []
        open_risks_total = 0
        blocked_tasks_total = 0
        pending_total = 0
        recent_sessions = []
        recent_retros = []
        recent_writes = []
        recent_recons = []
        jobs_attention = []

        for project in projects:
            risks = [r for r in self.store.list_risks(project.id) if r.status == RiskStatus.open]
            tasks = [t for t in self.store.list_tasks(project.id) if t.status == TaskStatus.blocked]
            suggestions = self.store.list_status_suggestions(project.id, include_resolved=False)
            sessions_done = [
                s
                for s in self.store.list_build_sessions(project.id)
                if s.status == BuildSessionStatus.completed
                and _ensure_aware(s.updated_at) >= seven
            ]
            retros = self.store.list_retrospectives(project.id)[:3]
            writes = self.store.list_github_write_events(project.id)[:3]
            recons = self.store.list_reconciliation_events(project.id)[:3]
            jobs = [j for j in self.store.list_jobs(project.id) if j.status == JobStatus.failed]

            per_project.append(
                ControlRoomProjectStat(
                    project_id=project.id,
                    name=project.name,
                    open_risks=len(risks),
                    blocked_tasks=len(tasks),
                    pending_suggestions=len(suggestions),
                    completed_sessions_7d=len(sessions_done),
                    last_activity_at=project.updated_at,
                )
            )
            open_risks_total += len(risks)
            blocked_tasks_total += len(tasks)
            pending_total += len(suggestions)
            recent_sessions.extend(sessions_done)
            recent_retros.extend(retros)
            recent_writes.extend(writes)
            recent_recons.extend(recons)
            jobs_attention.extend(jobs)

        per_project.sort(key=lambda stat: stat.open_risks + stat.blocked_tasks, reverse=True)
        stale_signals = self.staleness.detect()
        stale_project_ids = {
            signal.project_id
            for signal in stale_signals.signals
            if signal.kind == "project_inactive_14d"
        }
        stale = [stat for stat in per_project if stat.project_id in stale_project_ids]

        recommended: list[str] = []
        if blocked_tasks_total:
            recommended.append(
                f"{blocked_tasks_total} blocked task(s) across {len([s for s in per_project if s.blocked_tasks])} project(s) — unblock or reroute."
            )
        if pending_total:
            recommended.append(
                f"{pending_total} status suggestion(s) waiting — apply or dismiss them in /status-suggestions."
            )
        if any(stat.open_risks for stat in per_project):
            recommended.append("Open risks exist; review /system/risks for concentration.")
        if stale:
            recommended.append(f"{len(stale)} project(s) inactive for 14+ days — archive or revive.")
        if jobs_attention:
            recommended.append(
                f"{len(jobs_attention)} failed job(s) outstanding — diagnose or cancel."
            )

        return ControlRoomSummary(
            active_projects=per_project,
            open_risks_total=open_risks_total,
            blocked_tasks_total=blocked_tasks_total,
            pending_suggestions_total=pending_total,
            recent_github_write_events=recent_writes[:10],
            recent_reconciliation_events=recent_recons[:10],
            recent_completed_sessions=recent_sessions[:10],
            recent_retrospectives=recent_retros[:10],
            jobs_needing_attention=jobs_attention[:10],
            stale_projects=stale,
            recommended_next_actions=recommended,
        )
