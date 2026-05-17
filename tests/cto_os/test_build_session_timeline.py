"""Phase 8 — build session timeline composition."""
from __future__ import annotations

from cto_os_api.build_session_timeline import BuildSessionTimelineBuilder
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import (
    BuildSessionCreate,
    BuildSessionStatus,
    BuildSessionUpdate,
    CodeReviewCreate,
    ProjectCreate,
    RepositoryCreate,
    RepositoryProvider,
    TaskCreate,
    TestRunCreate,
    TestRunStatus,
)
from cto_os_api.repo_operator import RepoOperator


def test_timeline_orders_events_chronologically(store):
    project = store.create_project(ProjectCreate(name="timeline"))
    repo = store.create_repository(
        project.id,
        RepositoryCreate(provider=RepositoryProvider.manual, name="repo"),
    )
    task = store.create_task(project.id, TaskCreate(title="timeline task"))
    session = store.create_build_session(
        project.id,
        BuildSessionCreate(
            title="timeline session",
            repository_id=repo.id,
            task_id=task.id,
            status=BuildSessionStatus.planning,
        ),
    )

    operator = RepoOperator(store, LocalMemoryEngine(store))
    review = operator.review_diff(
        project.id,
        CodeReviewCreate(repository_id=repo.id, diff_text="+ console.log('hi');"),
    )
    test_run = operator.record_test_run(
        project.id,
        TestRunCreate(
            repository_id=repo.id, command="npm test", status=TestRunStatus.passed
        ),
    )
    store.update_build_session(
        project.id,
        session.id,
        BuildSessionUpdate(
            linked_code_review_ids=[review.id],
            linked_test_run_ids=[test_run.id],
        ),
    )

    timeline = BuildSessionTimelineBuilder(store).build(project.id, session.id)
    kinds = [item.kind.value for item in timeline.items]
    assert "task_created" in kinds
    assert "code_review" in kinds
    assert "test_run" in kinds
    # Chronological ordering preserved (timestamps monotonic-ish, fall back to
    # checking that task_created appears first if it carries the earliest ts).
    timestamps = [item.created_at for item in timeline.items]
    assert timestamps == sorted(timestamps)
