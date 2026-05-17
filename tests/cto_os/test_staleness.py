"""Phase 9 — staleness detection."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cto_os_api.models import (
    BuildSessionCreate,
    BuildSessionStatus,
    BuildSessionUpdate,
    ProjectCreate,
    RiskCreate,
    StatusSuggestion,
    StatusSuggestionEntityType,
    TaskCreate,
    TaskPriority,
)
from cto_os_api.staleness import StalenessDetector


def _backdate_task(store, task_id: str, days: int):
    task = next(t for t in store.list_tasks_all_projects() if t.id == task_id) if hasattr(store, "list_tasks_all_projects") else None
    # Fallback: re-save with rewound updated_at via direct insert
    if task is None:
        with store._connect() as conn:
            row = conn.execute("SELECT data FROM tasks WHERE id = ?", (task_id,)).fetchone()
        import json
        from cto_os_api.models import Task
        task = Task.model_validate(json.loads(row["data"]))
    task.updated_at = datetime.now(timezone.utc) - timedelta(days=days)
    store._save_task(task)


def test_high_priority_task_stale(store):
    project = store.create_project(ProjectCreate(name="S"))
    task = store.create_task(
        project.id, TaskCreate(title="urgent thing", priority=TaskPriority.urgent)
    )
    _backdate_task(store, task.id, 9)

    signals = StalenessDetector(store).detect()
    assert any(s.kind == "high_priority_task_7d" for s in signals.signals)


def test_risk_without_mitigation_surfaces(store):
    project = store.create_project(ProjectCreate(name="S2"))
    store.create_risk(project.id, RiskCreate(title="orphan risk"))
    signals = StalenessDetector(store).detect()
    assert any(s.kind == "risk_no_mitigation" for s in signals.signals)


def test_suggestion_pending_signal(store):
    project = store.create_project(ProjectCreate(name="S3"))
    sugg = StatusSuggestion(
        project_id=project.id,
        entity_type=StatusSuggestionEntityType.task,
        entity_id="t1",
        suggested_status="done",
        reason="stale",
    )
    sugg.created_at = datetime.now(timezone.utc) - timedelta(days=10)
    store.save_status_suggestion(sugg)

    signals = StalenessDetector(store).detect()
    assert any(s.kind == "suggestion_pending_7d" for s in signals.signals)


def test_build_session_stuck_reviewing(store):
    project = store.create_project(ProjectCreate(name="S4"))
    session = store.create_build_session(project.id, BuildSessionCreate(title="rev"))
    store.update_build_session(
        project.id,
        session.id,
        BuildSessionUpdate(status=BuildSessionStatus.reviewing),
    )
    # Rewind updated_at
    session = next(s for s in store.list_build_sessions(project.id) if s.id == session.id)
    session.updated_at = datetime.now(timezone.utc) - timedelta(days=9)
    store._insert_model(
        "build_sessions",
        session,
        project_id=session.project_id,
        repository_id=session.repository_id,
        task_id=session.task_id,
        status=session.status.value,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )

    signals = StalenessDetector(store).detect()
    assert any(s.kind == "session_reviewing_7d" for s in signals.signals)
