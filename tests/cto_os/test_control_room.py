"""Phase 9 — control room aggregate."""
from __future__ import annotations

from cto_os_api.control_room import ControlRoom
from cto_os_api.models import (
    ProjectCreate,
    RiskCreate,
    TaskCreate,
    TaskStatus,
    TaskUpdate,
)


def test_control_room_counts_and_recommendations(store):
    project = store.create_project(ProjectCreate(name="A"))
    blocked = store.create_task(project.id, TaskCreate(title="blocked one"))
    store.update_task(project.id, blocked.id, TaskUpdate(status=TaskStatus.blocked))
    store.create_risk(project.id, RiskCreate(title="risk1"))

    summary = ControlRoom(store).build()

    assert summary.blocked_tasks_total >= 1
    assert summary.open_risks_total >= 1
    assert summary.recommended_next_actions  # should mention blocked
    assert any("blocked" in note.lower() for note in summary.recommended_next_actions)
