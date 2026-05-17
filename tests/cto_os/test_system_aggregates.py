"""Phase 9 — system shipped + risk concentration + decision graph."""
from __future__ import annotations

from cto_os_api.decision_graph import DecisionGraphBuilder
from cto_os_api.models import (
    BuildSessionCreate,
    BuildSessionStatus,
    DecisionCreate,
    GitHubPullRequest,
    ProjectCreate,
    RepositoryCreate,
    RepositoryProvider,
    RiskCreate,
    TaskCreate,
    TaskStatus,
    TaskUpdate,
)
from cto_os_api.risk_concentration import RiskConcentrationService
from cto_os_api.system_shipped import SystemShipped


def test_system_shipped_aggregates_across_projects(store):
    p1 = store.create_project(ProjectCreate(name="P1"))
    p2 = store.create_project(ProjectCreate(name="P2"))
    repo1 = store.create_repository(p1.id, RepositoryCreate(provider=RepositoryProvider.manual, name="r1"))
    store.create_repository(p2.id, RepositoryCreate(provider=RepositoryProvider.manual, name="r2"))

    store.create_build_session(
        p1.id,
        BuildSessionCreate(
            title="done", repository_id=repo1.id, status=BuildSessionStatus.completed
        ),
    )
    store.replace_github_sync(
        p1.id,
        repo1.id,
        [],
        [
            GitHubPullRequest(
                project_id=p1.id,
                repository_id=repo1.id,
                number=1,
                title="m",
                state="closed",
                merged=True,
            )
        ],
    )
    task = store.create_task(p1.id, TaskCreate(title="t"))
    store.update_task(p1.id, task.id, TaskUpdate(status=TaskStatus.done))

    summary = SystemShipped(store).build()
    assert summary.completed_build_sessions == 1
    assert summary.merged_pull_requests == 1
    assert summary.completed_tasks == 1
    assert len(summary.projects) == 2
    # velocity_7d covers the just-completed task
    assert summary.velocity_7d >= 1


def test_risk_concentration_flags_missing_mitigation(store):
    p = store.create_project(ProjectCreate(name="RC"))
    store.create_risk(p.id, RiskCreate(title="latency risk"))
    summary = RiskConcentrationService(store).build()
    group = summary.groups[0]
    assert group.risks_without_mitigation, "open risks with no linked task must surface"


def test_decision_graph_project_and_system(store):
    p = store.create_project(ProjectCreate(name="G"))
    decision = store.create_decision(p.id, DecisionCreate(title="d1", decision="pick A"))
    task = store.create_task(p.id, TaskCreate(title="implement d1"))
    decision.linked_task_ids.append(task.id)
    # Persist linked task on the decision
    store._insert_model(
        "decisions",
        decision,
        project_id=decision.project_id,
        created_at=decision.created_at,
        decision_type=decision.decision_type.value,
        impact_level=decision.impact_level.value,
    )

    builder = DecisionGraphBuilder(store)
    g_project = builder.project(p.id)
    g_system = builder.system()
    assert any(node.kind == "decision" and node.id == decision.id for node in g_project.nodes)
    assert any(edge.relation == "linked_to_task" for edge in g_project.edges)
    assert len(g_system.nodes) >= len(g_project.nodes)
