"""Phase 10 — invoke a representative slice of MCP tools end-to-end."""
from __future__ import annotations

from cto_os_api.mcp_tools import MCPToolset
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import ProjectCreate, RepositoryCreate, RepositoryProvider, TaskCreate


def _toolset(store):
    return MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))


def test_list_projects_round_trip(store):
    project = store.create_project(ProjectCreate(name="MCP P"))
    out = _toolset(store).call("list_projects")
    assert any(item["id"] == project.id for item in out)


def test_create_task_via_mcp_persists(store):
    project = store.create_project(ProjectCreate(name="MCP T"))
    out = _toolset(store).call(
        "create_task",
        {
            "project_id": project.id,
            "title": "via mcp",
            "description": "from host",
            "priority": "high",
            "acceptance_criteria": ["builds"],
        },
    )
    assert out["title"] == "via mcp"
    persisted = store.list_tasks(project.id)
    assert any(task.title == "via mcp" for task in persisted)


def test_save_project_memory_persists_and_is_searchable(store):
    project = store.create_project(ProjectCreate(name="MCP M"))
    ts = _toolset(store)
    ts.call(
        "save_project_memory",
        {
            "project_id": project.id,
            "title": "alpha note",
            "content": "alpha-only knowledge",
            "tags": ["mcp"],
        },
    )
    found = ts.call(
        "search_project_memory", {"project_id": project.id, "query": "alpha"}
    )
    assert any("alpha-only" in (item["content"] or "") for item in found)


def test_review_diff_context_returns_bundle(store):
    project = store.create_project(ProjectCreate(name="MCP CR"))
    store.create_repository(project.id, RepositoryCreate(provider=RepositoryProvider.manual, name="r"))
    bundle = _toolset(store).call(
        "review_diff_context",
        {"project_id": project.id, "diff_text": "+ const x = 1;"},
    )
    assert bundle["kind"] == "code_review"
    assert bundle["save_endpoint"].endswith("/llm-results/code-review")
    assert bundle["output_schema"]
    assert "recommendation" in bundle["save_payload_keys"]


def test_save_code_review_result_persists(store):
    project = store.create_project(ProjectCreate(name="MCP CR2"))
    out = _toolset(store).call(
        "save_code_review_result",
        {
            "project_id": project.id,
            "diff_text": "+ const x = 1;",
            "recommendation": "approve",
            "summary": "looks fine",
            "non_blocking_suggestions": ["add jsdoc"],
        },
    )
    assert out["approval_recommendation"] == "approve"
    persisted = store.list_code_reviews(project.id)
    assert any(review.review_summary == "looks fine" for review in persisted)


def test_summarize_build_session_context_returns_timeline(store):
    project = store.create_project(ProjectCreate(name="MCP BS"))
    session = store.create_build_session(
        project.id,
        # imported lazily to avoid an extra top-level import
        __import__("cto_os_api.models", fromlist=["BuildSessionCreate"]).BuildSessionCreate(
            title="mcp session"
        ),
    )
    timeline = _toolset(store).call(
        "summarize_build_session_context",
        {"project_id": project.id, "session_id": session.id},
    )
    assert timeline["build_session_id"] == session.id
    assert "items" in timeline
