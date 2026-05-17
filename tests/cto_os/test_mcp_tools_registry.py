"""Phase 10 — MCP tool registry shape + GitHub-write absence."""
from __future__ import annotations

import json

from cto_os_api.mcp_tools import MCPToolset
from cto_os_api.memory_engine import LocalMemoryEngine


EXPECTED_TOOLS = {
    # project
    "list_projects",
    "get_project",
    "get_project_brief",
    "get_control_room_summary",
    # memory
    "search_project_memory",
    "save_project_memory",
    "list_source_of_truth_memory",
    "pin_memory",
    # tasks
    "list_tasks",
    "get_task",
    "create_task",
    "update_task",
    "list_status_suggestions",
    # repo
    "list_repositories",
    "get_repo_scan",
    "search_repo_files",
    "search_repo_symbols",
    "get_git_status",
    # execution
    "generate_build_packet",
    "create_branch_plan",
    "create_pr_packet",
    "review_diff_context",
    "save_code_review_result",
    "create_test_run",
    "create_build_session",
    "summarize_build_session_context",
    "save_lesson_to_memory",
    # context bundles
    "context_code_review",
    "context_retrospective",
    "context_implementation_plan",
    "context_build_packet",
    # github preview only
    "preview_github_issue",
    "preview_github_branch",
    "preview_github_draft_pr",
}


def test_registry_contains_expected_tools(store):
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    names = {tool.name for tool in toolset.tools()}
    missing = EXPECTED_TOOLS - names
    assert not missing, f"MCP toolset is missing: {sorted(missing)}"


def test_no_github_create_tools_exposed(store):
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    names = {tool.name for tool in toolset.tools()}
    forbidden = {n for n in names if n.startswith("create_github") or n.startswith("github_create")}
    assert forbidden == set(), f"Phase 10 forbids GitHub create tools; got {forbidden}"


def test_all_input_schemas_are_json_serialisable(store):
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    for tool in toolset.tools():
        json.dumps(tool.input_schema)
        assert tool.input_schema.get("type") == "object"
        assert "properties" in tool.input_schema
