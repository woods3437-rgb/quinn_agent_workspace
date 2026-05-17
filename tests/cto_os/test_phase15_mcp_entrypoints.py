"""Phase 15 — new MCP entrypoint tools complete the setup→scan→review flow."""
from __future__ import annotations

import subprocess
from pathlib import Path

from cto_os_api.mcp_tools import MCPToolset, WRITE_TOOL_NAMES
from cto_os_api.memory_engine import LocalMemoryEngine


def _git_init(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"], cwd=path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init"],
        cwd=path, check=True,
    )


def test_phase15_tools_are_registered_and_listed_as_writes(store):
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    names = {t.name for t in toolset.tools()}
    for tool in [
        "create_project", "create_repository", "scan_repository",
        "index_repo_to_memory", "summarize_build_session",
        "generate_retrospective", "review_diff_from_git",
        "git_check_ignore", "git_ls_files",
    ]:
        assert tool in names, tool
    # The mutating ones are tagged as writes (so MCP read-only mode + audit pick them up).
    write_only = {
        "create_project", "create_repository", "scan_repository",
        "index_repo_to_memory", "summarize_build_session",
        "generate_retrospective", "review_diff_from_git",
    }
    assert write_only <= WRITE_TOOL_NAMES


def test_setup_scan_through_mcp_only(store, tmp_data_dir):
    repo_path = tmp_data_dir / "mcp_setup"
    repo_path.mkdir()
    (repo_path / ".gitignore").write_text("")
    (repo_path / "package.json").write_text('{"name":"x","scripts":{"test":"echo ok"}}')
    (repo_path / "README.md").write_text("# x")
    _git_init(repo_path)

    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    project = toolset.call("create_project", {"name": "via-mcp"})
    repo = toolset.call(
        "create_repository",
        {"project_id": project["id"], "name": "r", "local_path": str(repo_path)},
    )
    scan = toolset.call(
        "scan_repository",
        {"project_id": project["id"], "repository_id": repo["id"]},
    )
    assert "Node.js" in scan["tech_stack"]

    # Idempotent re-create returns the existing rows.
    again = toolset.call("create_project", {"name": "via-mcp"})
    assert again["id"] == project["id"]
    again_repo = toolset.call(
        "create_repository",
        {"project_id": project["id"], "name": "r", "local_path": str(repo_path)},
    )
    assert again_repo["id"] == repo["id"]

    ls = toolset.call(
        "git_ls_files",
        {"project_id": project["id"], "repository_id": repo["id"]},
    )
    assert "README.md" in ls

    ignored = toolset.call(
        "git_check_ignore",
        {
            "project_id": project["id"],
            "repository_id": repo["id"],
            "paths": ["README.md"],
        },
    )
    assert "README.md" in ignored["not_ignored"]


def test_review_diff_from_git_empty_returns_structured_error(store, tmp_data_dir):
    repo_path = tmp_data_dir / "mcp_diff"
    repo_path.mkdir()
    (repo_path / ".gitignore").write_text("")
    (repo_path / "README.md").write_text("# clean")
    _git_init(repo_path)

    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    project = toolset.call("create_project", {"name": "diff-empty"})
    repo = toolset.call(
        "create_repository",
        {"project_id": project["id"], "name": "r", "local_path": str(repo_path)},
    )
    result = toolset.call(
        "review_diff_from_git",
        {"project_id": project["id"], "repository_id": repo["id"]},
    )
    assert isinstance(result, dict) and result.get("isError") is True
    assert "empty" in result.get("reason", "").lower()
