"""Build session lifecycle test (Phase 6 verification)."""
from __future__ import annotations

from cto_os_api.models import (
    BuildSessionCreate,
    BuildSessionStatus,
    BuildSessionUpdate,
    CodeReviewCreate,
    TaskCreate,
    TestRunCreate,
    TestRunStatus,
)
from cto_os_api.repo_operator import RepoOperator


def test_build_session_lifecycle(store, memory_engine, project, repository):
    operator = RepoOperator(store, memory_engine)
    task = store.create_task(project.id, TaskCreate(title="Phase 6 task"))

    session = store.create_build_session(
        project.id,
        BuildSessionCreate(
            title="Wire up Phase 6",
            repository_id=repository.id,
            task_id=task.id,
            status=BuildSessionStatus.planning,
        ),
    )
    assert session.status == BuildSessionStatus.planning

    review = operator.review_diff(
        project.id,
        CodeReviewCreate(
            repository_id=repository.id,
            task_id=task.id,
            diff_text="+ password = 'hunter2'",
        ),
    )
    test_run = operator.record_test_run(
        project.id,
        TestRunCreate(
            repository_id=repository.id,
            command="npm test",
            status=TestRunStatus.failed,
            output="boom",
        ),
    )

    session = store.update_build_session(
        project.id,
        session.id,
        BuildSessionUpdate(
            status=BuildSessionStatus.reviewing,
            linked_code_review_ids=[review.id],
            linked_test_run_ids=[test_run.id],
            lessons_learned="Never commit passwords to diffs.",
        ),
    )
    assert review.id in session.linked_code_review_ids

    summarised = operator.summarize_build_session(project.id, session.id)
    assert "Code reviews: 1" in summarised.summary
    assert "Test runs: 1 (failing: 1)" in summarised.summary

    saved = operator.save_build_session_lessons(project.id, session.id)
    assert saved, "save-lessons must persist at least one memory"
    assert any(m.tags == ["build-session", "lesson"] for m in saved)

    decisions = store.list_decisions(project.id)
    assert any(decision.title.startswith("Recorded lesson") for decision in decisions)
