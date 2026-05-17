"""Phase 8 — shipped dashboard aggregate."""
from __future__ import annotations

from datetime import datetime, timezone

from cto_os_api.models import (
    BuildSessionCreate,
    BuildSessionStatus,
    GitHubPullRequest,
    MemoryCreate,
    ProjectCreate,
    RepositoryCreate,
    RepositoryProvider,
    TaskCreate,
    TaskStatus,
    TaskUpdate,
)
from cto_os_api.shipped_dashboard import ShippedDashboard


def test_shipped_dashboard_counts(store):
    project = store.create_project(ProjectCreate(name="shipped"))
    repo = store.create_repository(
        project.id,
        RepositoryCreate(provider=RepositoryProvider.manual, name="repo"),
    )
    store.create_build_session(
        project.id,
        BuildSessionCreate(
            title="completed", repository_id=repo.id, status=BuildSessionStatus.completed
        ),
    )
    # Mark a task as done
    task = store.create_task(project.id, TaskCreate(title="done task"))
    store.update_task(project.id, task.id, TaskUpdate(status=TaskStatus.done))
    # A follow-up task
    store.create_task(project.id, TaskCreate(title="follow up later"))

    # Seed a merged PR row + a closed issue row directly via the sync helper.
    store.replace_github_sync(
        project.id,
        repo.id,
        [],
        [
            GitHubPullRequest(
                project_id=project.id,
                repository_id=repo.id,
                number=1,
                title="merged thing",
                state="closed",
                merged=True,
            )
        ],
    )

    store.create_memory(
        project.id,
        MemoryCreate(title="lesson 1", content="never deploy fridays", tags=["lesson"]),
    )

    summary = ShippedDashboard(store).build(project.id)
    assert len(summary.completed_build_sessions) == 1
    assert len(summary.completed_tasks) == 1
    assert len(summary.merged_pull_requests) == 1
    assert len(summary.lessons_learned) == 1
    assert summary.velocity_7d >= 1
