"""Phase 9 — playbook generate + apply, with secret sanitisation."""
from __future__ import annotations

from cto_os_api.models import (
    BranchPlan,
    BuildPacket,
    BuildSessionCreate,
    BuildSessionStatus,
    PlaybookApplyRequest,
    PlaybookGenerateRequest,
    ProjectCreate,
    RepositoryCreate,
    RepositoryProvider,
    TaskCreate,
)
from cto_os_api.playbook_service import PlaybookService, sanitise_steps


def test_sanitise_steps_drops_secrets_and_env_paths():
    cleaned = sanitise_steps(
        [
            "Run npm test",
            "Set api_key = 'sk-XYZ'",
            "Copy values from .env.production",
            "Push final patch",
        ]
    )
    assert "Run npm test" in cleaned
    assert "Push final patch" in cleaned
    assert all("api_key" not in step.lower() for step in cleaned)
    assert all(".env" not in step.lower() for step in cleaned)


def test_generate_playbook_from_session_and_apply(store):
    project = store.create_project(ProjectCreate(name="PB"))
    repo = store.create_repository(
        project.id, RepositoryCreate(provider=RepositoryProvider.manual, name="repo")
    )
    task = store.create_task(project.id, TaskCreate(title="ship feature X"))
    packet = BuildPacket(
        project_id=project.id,
        task_id=task.id,
        title="feature X packet",
        implementation_steps=[
            "Wire endpoints",
            "Add tests",
            "Copy .env.production to staging",  # sensitive — should be dropped
        ],
        acceptance_criteria=["Endpoints respond", "Tests pass"],
    )
    store._insert_model("build_packets", packet, project_id=project.id, created_at=packet.created_at, task_id=task.id)
    branch = store.save_branch_plan(
        BranchPlan(
            project_id=project.id,
            repository_id=repo.id,
            task_id=task.id,
            branch_name="feature-x",
            objective="ship feature X",
            implementation_steps=["Open branch plan", "Write code"],
            risk_notes=["Migration is large"],
        )
    )
    session = store.create_build_session(
        project.id,
        BuildSessionCreate(
            title="ship feature X session",
            repository_id=repo.id,
            task_id=task.id,
            linked_build_packet_id=packet.id,
            linked_branch_plan_id=branch.id,
            status=BuildSessionStatus.completed,
        ),
    )

    service = PlaybookService(store)
    playbook = service.generate(
        project.id, session.id, PlaybookGenerateRequest(name="Feature X playbook")
    )

    assert playbook.source_project_id == project.id
    assert playbook.source_build_session_id == session.id
    assert "Wire endpoints" in playbook.steps
    assert "Write code" in playbook.steps
    assert all(".env" not in step.lower() for step in playbook.steps)

    # Apply produces a GeneratedOutput linked to the task.
    output = service.apply(project.id, task.id, PlaybookApplyRequest(playbook_id=playbook.id))
    assert output.metadata["playbook_id"] == playbook.id
    assert "Feature X playbook" in output.output or playbook.name in output.output
