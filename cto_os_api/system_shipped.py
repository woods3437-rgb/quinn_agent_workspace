"""Phase 9 — cross-project 'What we shipped' aggregate."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import (
    BuildSessionStatus,
    SystemShippedProject,
    SystemShippedSummary,
    TaskStatus,
)
from .sqlite_store import SQLiteStore


def _ensure_aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class SystemShipped:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def build(self) -> SystemShippedSummary:
        now = datetime.now(timezone.utc)
        seven = now - timedelta(days=7)
        thirty = now - timedelta(days=30)
        ninety = now - timedelta(days=90)
        projects = self.store.list_projects()
        per_project: list[SystemShippedProject] = []
        agg = {
            "completed_build_sessions": 0,
            "merged_pull_requests": 0,
            "closed_issues": 0,
            "completed_tasks": 0,
            "velocity_7d": 0,
            "velocity_30d": 0,
            "velocity_90d": 0,
        }

        for project in projects:
            sessions = [
                s
                for s in self.store.list_build_sessions(project.id)
                if s.status == BuildSessionStatus.completed
            ]
            prs = [pr for pr in self.store.list_github_pull_requests(project.id) if pr.merged]
            issues = [
                issue
                for issue in self.store.list_github_issues(project.id)
                if (issue.state or "").lower() == "closed"
            ]
            tasks = [t for t in self.store.list_tasks(project.id) if t.status == TaskStatus.done]
            v7 = sum(1 for t in tasks if _ensure_aware(t.updated_at) >= seven)
            v30 = sum(1 for t in tasks if _ensure_aware(t.updated_at) >= thirty)
            v90 = sum(1 for t in tasks if _ensure_aware(t.updated_at) >= ninety)
            per_project.append(
                SystemShippedProject(
                    project_id=project.id,
                    name=project.name,
                    completed_build_sessions=len(sessions),
                    merged_pull_requests=len(prs),
                    closed_issues=len(issues),
                    completed_tasks=len(tasks),
                    velocity_7d=v7,
                    velocity_30d=v30,
                    velocity_90d=v90,
                )
            )
            agg["completed_build_sessions"] += len(sessions)
            agg["merged_pull_requests"] += len(prs)
            agg["closed_issues"] += len(issues)
            agg["completed_tasks"] += len(tasks)
            agg["velocity_7d"] += v7
            agg["velocity_30d"] += v30
            agg["velocity_90d"] += v90

        per_project.sort(key=lambda item: item.velocity_30d, reverse=True)
        return SystemShippedSummary(projects=per_project, **agg)
