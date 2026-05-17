"""Phase 15 — BuildSession auto-links packet + branch plan by task_id."""
from __future__ import annotations

from cto_os_api.models import (
    BranchPlan,
    BuildPacket,
    BuildSessionCreate,
    ProjectCreate,
    RepositoryCreate,
    RepositoryProvider,
    TaskCreate,
)


def _seed(store):
    project = store.create_project(ProjectCreate(name="autolink"))
    repo = store.create_repository(
        project.id,
        RepositoryCreate(provider=RepositoryProvider.manual, name="r"),
    )
    task = store.create_task(project.id, TaskCreate(title="ship X"))
    packet = BuildPacket(project_id=project.id, task_id=task.id, title="X packet")
    store._insert_model(
        "build_packets", packet, project_id=project.id, created_at=packet.created_at, task_id=task.id
    )
    plan = store.save_branch_plan(
        BranchPlan(
            project_id=project.id, repository_id=repo.id, task_id=task.id,
            branch_name="ship-x", objective="ship x",
        )
    )
    return project, repo, task, packet, plan


def test_autolinks_when_blank(store):
    project, repo, task, packet, plan = _seed(store)
    session = store.create_build_session(
        project.id,
        BuildSessionCreate(title="ship X session", repository_id=repo.id, task_id=task.id),
    )
    assert session.linked_build_packet_id == packet.id
    assert session.linked_branch_plan_id == plan.id


def test_does_not_overwrite_explicit_values(store):
    project, repo, task, packet, plan = _seed(store)
    other_plan = store.save_branch_plan(
        BranchPlan(
            project_id=project.id, repository_id=repo.id, task_id=task.id,
            branch_name="alt", objective="alt",
        )
    )
    session = store.create_build_session(
        project.id,
        BuildSessionCreate(
            title="ship X session", repository_id=repo.id, task_id=task.id,
            linked_branch_plan_id=other_plan.id,
        ),
    )
    assert session.linked_branch_plan_id == other_plan.id
    # Packet still auto-filled since it was blank.
    assert session.linked_build_packet_id == packet.id


def test_no_task_id_no_autolink(store):
    project, *_ = _seed(store)
    session = store.create_build_session(
        project.id, BuildSessionCreate(title="no task session"),
    )
    assert session.linked_build_packet_id is None
    assert session.linked_branch_plan_id is None
