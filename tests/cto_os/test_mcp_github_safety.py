"""Phase 10 — MCP GitHub preview-only safety."""
from __future__ import annotations

from cto_os_api.mcp_tools import MCPToolset
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import (
    BranchPlan,
    ProjectCreate,
    RepositoryCreate,
    RepositoryProvider,
    TaskCreate,
)


def test_preview_github_issue_does_not_call_github(store):
    project = store.create_project(ProjectCreate(name="P"))
    task = store.create_task(project.id, TaskCreate(title="ship X"))
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))

    # No httpx stub needed — preview routes are pure-local by construction.
    event = toolset.call(
        "preview_github_issue", {"project_id": project.id, "task_id": task.id}
    )
    assert event["status"] == "previewed"
    assert event["dry_run"] is True


def test_preview_github_branch_returns_sanitised_payload(store):
    project = store.create_project(ProjectCreate(name="B"))
    repo = store.create_repository(
        project.id,
        RepositoryCreate(
            provider=RepositoryProvider.github,
            name="repo",
            url="https://github.com/me/repo.git",
            default_branch="main",
        ),
    )
    plan = store.save_branch_plan(
        BranchPlan(
            project_id=project.id,
            repository_id=repo.id,
            branch_name="Feature: With spaces!",
            objective="x",
        )
    )
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    event = toolset.call(
        "preview_github_branch", {"project_id": project.id, "branch_plan_id": plan.id}
    )
    payload = event["payload_json"]
    assert " " not in payload["branch_name"]
    assert payload["base_branch"] == "main"


def test_no_create_github_tools_in_registry(store):
    names = {tool.name for tool in MCPToolset(store=store, memory_engine=LocalMemoryEngine(store)).tools()}
    bad = [n for n in names if "create_github" in n or "github_create" in n]
    assert bad == []
