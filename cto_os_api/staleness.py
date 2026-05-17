"""Phase 9 — staleness detection across projects.

Pure read pass. Returns ``StalenessSignal`` rows describing places where work
appears to have stalled. Nothing is persisted here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import (
    BuildSessionStatus,
    JobStatus,
    StalenessReport,
    StalenessSignal,
    TaskPriority,
    TaskStatus,
)
from .sqlite_store import SQLiteStore


def _ensure_aware(value: datetime) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class StalenessDetector:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def detect(self, project_id: str | None = None) -> StalenessReport:
        now = datetime.now(timezone.utc)
        signals: list[StalenessSignal] = []

        projects = (
            [self.store.get_project(project_id)]
            if project_id
            else self.store.list_projects()
        )

        for project in projects:
            # 1. project_inactive_14d
            updated = _ensure_aware(project.updated_at)
            days = (now - updated).days
            if days >= 14:
                signals.append(
                    StalenessSignal(
                        project_id=project.id,
                        kind="project_inactive_14d",
                        entity_type="project",
                        entity_id=project.id,
                        detail=f"Project '{project.name}' has had no updates in {days} days.",
                        days_stale=days,
                    )
                )

            tasks = self.store.list_tasks(project.id)
            risks = self.store.list_risks(project.id)
            sessions = self.store.list_build_sessions(project.id)
            suggestions = self.store.list_status_suggestions(project.id, include_resolved=False)
            jobs = self.store.list_jobs(project.id)

            # 2. blocked_task_7d (high priority untouched)
            for task in tasks:
                if (
                    task.priority in {TaskPriority.high, TaskPriority.urgent}
                    and task.status != TaskStatus.done
                ):
                    age = (now - _ensure_aware(task.updated_at)).days
                    if age >= 7:
                        signals.append(
                            StalenessSignal(
                                project_id=project.id,
                                kind="high_priority_task_7d",
                                entity_type="task",
                                entity_id=task.id,
                                detail=f"High-priority task '{task.title}' untouched for {age} days.",
                                days_stale=age,
                            )
                        )

            # 3. risk_without_mitigation_task
            for risk in risks:
                if risk.status.value in {"mitigated", "accepted"}:
                    continue
                if not risk.linked_task_ids:
                    signals.append(
                        StalenessSignal(
                            project_id=project.id,
                            kind="risk_no_mitigation",
                            entity_type="risk",
                            entity_id=risk.id,
                            detail=f"Open risk '{risk.title}' has no linked mitigation task.",
                            days_stale=(now - _ensure_aware(risk.updated_at)).days,
                        )
                    )

            # 4. build_session_stuck_reviewing_7d
            for session in sessions:
                if session.status != BuildSessionStatus.reviewing:
                    continue
                age = (now - _ensure_aware(session.updated_at)).days
                if age >= 7:
                    signals.append(
                        StalenessSignal(
                            project_id=project.id,
                            kind="session_reviewing_7d",
                            entity_type="build_session",
                            entity_id=session.id,
                            detail=f"Build session '{session.title}' has been in reviewing for {age} days.",
                            days_stale=age,
                        )
                    )

            # 5. suggestion_pending_7d
            for suggestion in suggestions:
                age = (now - _ensure_aware(suggestion.created_at)).days
                if age >= 7:
                    signals.append(
                        StalenessSignal(
                            project_id=project.id,
                            kind="suggestion_pending_7d",
                            entity_type="status_suggestion",
                            entity_id=suggestion.id,
                            detail=f"Status suggestion → {suggestion.suggested_status} pending {age} days.",
                            days_stale=age,
                        )
                    )

            # 6. failed_job_unresolved
            for job in jobs:
                if job.status != JobStatus.failed:
                    continue
                age = (now - _ensure_aware(job.updated_at)).days
                signals.append(
                    StalenessSignal(
                        project_id=project.id,
                        kind="failed_job",
                        entity_type="job",
                        entity_id=job.id,
                        detail=f"Failed job '{job.title}' unresolved ({age} days).",
                        days_stale=max(age, 0),
                    )
                )

        return StalenessReport(signals=signals)
