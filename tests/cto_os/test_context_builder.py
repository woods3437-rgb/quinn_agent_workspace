"""Phase 10 — context-builder bundles."""
from __future__ import annotations

from cto_os_api.context_builder import ContextBuilder
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import (
    BuildSessionCreate,
    CodeReviewContextRequest,
    MemoryCreate,
    ProjectCreate,
    RetrospectiveContextRequest,
    TaskCreate,
)


def test_code_review_bundle_includes_pinned_and_schema(store):
    project = store.create_project(ProjectCreate(name="ctx"))
    store.create_memory(
        project.id,
        MemoryCreate(title="north star", content="never break the build", pinned=True),
    )
    task = store.create_task(project.id, TaskCreate(title="ship X"))

    bundle = ContextBuilder(store, LocalMemoryEngine(store)).code_review(
        project.id,
        CodeReviewContextRequest(diff_text="+ const x = 1;", task_id=task.id),
    )
    assert bundle.kind.value == "code_review"
    assert bundle.save_endpoint.endswith("/llm-results/code-review")
    assert any(
        memory["title"] == "north star"
        for memory in bundle.context["source_of_truth"]
    )
    assert "recommendation" in bundle.output_schema["properties"]
    assert "diff_text" in bundle.save_payload_keys


def test_retrospective_bundle_uses_session_links(store):
    project = store.create_project(ProjectCreate(name="ctx2"))
    session = store.create_build_session(
        project.id,
        BuildSessionCreate(title="ship X session"),
    )
    bundle = ContextBuilder(store, LocalMemoryEngine(store)).retrospective(
        project.id,
        RetrospectiveContextRequest(build_session_id=session.id),
    )
    assert bundle.context["build_session"]["id"] == session.id
    assert "what_changed" in bundle.save_payload_keys
