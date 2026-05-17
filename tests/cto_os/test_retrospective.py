"""Phase 8 — retrospective generation + memory feedback loop."""
from __future__ import annotations

from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import (
    BuildSessionCreate,
    BuildSessionStatus,
    BuildSessionUpdate,
    CodeReviewCreate,
    ProjectCreate,
    RepositoryCreate,
    RepositoryProvider,
    RetrospectiveGenerateRequest,
    TaskCreate,
    TestRunCreate,
    TestRunStatus,
)
from cto_os_api.repo_operator import RepoOperator
from cto_os_api.retrospective_generator import RetrospectiveGenerator


def _seed_session(store):
    project = store.create_project(ProjectCreate(name="retro"))
    repo = store.create_repository(
        project.id,
        RepositoryCreate(provider=RepositoryProvider.manual, name="repo"),
    )
    task = store.create_task(project.id, TaskCreate(title="retro task"))
    session = store.create_build_session(
        project.id,
        BuildSessionCreate(
            title="retro session",
            repository_id=repo.id,
            task_id=task.id,
            status=BuildSessionStatus.completed,
            lessons_learned="Keep diffs small.",
        ),
    )
    operator = RepoOperator(store, LocalMemoryEngine(store))
    review = operator.review_diff(
        project.id,
        CodeReviewCreate(repository_id=repo.id, diff_text="+ const x = 1;\n"),
    )
    passing = operator.record_test_run(
        project.id,
        TestRunCreate(
            repository_id=repo.id, command="npm test", status=TestRunStatus.passed
        ),
    )
    failing = operator.record_test_run(
        project.id,
        TestRunCreate(
            repository_id=repo.id, command="npm run e2e", status=TestRunStatus.failed
        ),
    )
    store.update_build_session(
        project.id,
        session.id,
        BuildSessionUpdate(
            linked_code_review_ids=[review.id],
            linked_test_run_ids=[passing.id, failing.id],
        ),
    )
    return project, session


def test_deterministic_retrospective_includes_summary_and_test_counts(store, monkeypatch):
    monkeypatch.setenv("CTO_OS_LLM_PROVIDER", "deterministic")
    project, session = _seed_session(store)
    generator = RetrospectiveGenerator(store, LocalMemoryEngine(store))

    retro = generator.generate(
        project.id,
        RetrospectiveGenerateRequest(
            build_session_id=session.id,
            save_lessons_to_memory=True,
            create_decision=True,
            create_follow_up_tasks=False,
        ),
    )

    assert retro.title == session.title
    assert retro.summary
    assert "1 passed, 1 failed" in retro.test_results
    assert any("test run(s) passed" in item for item in retro.what_worked)
    assert any("test run(s) failed" in item for item in retro.what_broke)
    assert retro.memory_ids_created
    assert retro.decision_ids_created
    # Verify the new memory is searchable in the same project.
    memories = LocalMemoryEngine(store).search(project.id, "Retrospective lessons")
    assert any(memory.id in retro.memory_ids_created for memory in memories)


def test_retrospective_pin_to_source_of_truth(store, monkeypatch):
    monkeypatch.setenv("CTO_OS_LLM_PROVIDER", "deterministic")
    project, session = _seed_session(store)
    generator = RetrospectiveGenerator(store, LocalMemoryEngine(store))

    retro = generator.generate(
        project.id,
        RetrospectiveGenerateRequest(
            build_session_id=session.id,
            save_lessons_to_memory=True,
            pin_to_source_of_truth=True,
        ),
    )
    memories = {memory.id: memory for memory in store.list_memories(project_id=project.id)}
    pinned = [memories[mid] for mid in retro.memory_ids_created]
    assert pinned and all(memory.pinned for memory in pinned)
