"""Phase 8 — 'What we shipped' dashboard.

Server-computed aggregate over already-stored entities. No persistence here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import BuildSessionStatus, ShippedSummary, TaskStatus
from .sqlite_store import SQLiteStore


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class ShippedDashboard:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def build(self, project_id: str) -> ShippedSummary:
        self.store.get_project(project_id)
        now = datetime.now(timezone.utc)
        seven = now - timedelta(days=7)
        thirty = now - timedelta(days=30)

        sessions = [
            session
            for session in self.store.list_build_sessions(project_id)
            if session.status == BuildSessionStatus.completed
        ]
        prs = [
            pr
            for pr in self.store.list_github_pull_requests(project_id)
            if pr.merged
        ]
        issues = [
            issue
            for issue in self.store.list_github_issues(project_id)
            if (issue.state or "").lower() == "closed"
        ]
        tasks = [
            task
            for task in self.store.list_tasks(project_id)
            if task.status == TaskStatus.done
        ]
        outputs = [
            output
            for output in self.store.list_outputs(project_id)
            if (output.metadata or {}).get("output_type") in {"build_packet", "weekly_brief", "brief"}
        ]
        lessons = [
            memory
            for memory in self.store.list_memories(project_id=project_id)
            if "lesson" in memory.tags or memory.source in {"retrospective", "build_session"}
        ]
        follow_ups = [
            task
            for task in self.store.list_tasks(project_id)
            if "follow" in (task.description or "").lower()
            or "follow" in task.title.lower()
        ]

        velocity_7d = sum(
            1
            for task in tasks
            if _ensure_aware(task.updated_at) >= seven
        )
        velocity_30d = sum(
            1
            for task in tasks
            if _ensure_aware(task.updated_at) >= thirty
        )

        return ShippedSummary(
            project_id=project_id,
            completed_build_sessions=sessions,
            merged_pull_requests=prs,
            closed_issues=issues,
            completed_tasks=tasks,
            shipped_outputs=outputs,
            lessons_learned=lessons,
            follow_up_tasks=follow_ups,
            velocity_7d=velocity_7d,
            velocity_30d=velocity_30d,
        )
