"""Phase 8 — regression check that Phase 7 write guard still blocks by default."""
from __future__ import annotations

import pytest

from cto_os_api.github_write_guard import GitHubWriteError, GitHubWriteGuard
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import (
    GitHubIssueCreateRequest,
    ProjectCreate,
    RepositoryCreate,
    RepositoryProvider,
    TaskCreate,
)
from cto_os_api.repo_operator import RepoOperator


def test_phase7_guard_still_blocks_by_default(store, monkeypatch):
    monkeypatch.delenv("CTO_OS_ALLOW_GITHUB_WRITES", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    project = store.create_project(ProjectCreate(name="phase8 safety"))
    repo = store.create_repository(
        project.id,
        RepositoryCreate(
            provider=RepositoryProvider.github,
            name="repo",
            url="https://github.com/octocat/repo.git",
        ),
    )
    task = store.create_task(project.id, TaskCreate(title="phase8 task"))

    operator = RepoOperator(store, LocalMemoryEngine(store))
    event = operator.create_task_issue(
        project.id,
        task.id,
        GitHubIssueCreateRequest(approved=True, dry_run=False),
    )

    assert event.status.value == "blocked"
    assert "CTO_OS_ALLOW_GITHUB_WRITES" in event.error_message


def test_auto_reconcile_env_flag_is_isolated_from_writes(monkeypatch):
    """Setting CTO_OS_ALLOW_AUTO_RECONCILE does NOT enable GitHub writes."""
    monkeypatch.setenv("CTO_OS_ALLOW_AUTO_RECONCILE", "1")
    monkeypatch.delenv("CTO_OS_ALLOW_GITHUB_WRITES", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "stub")
    guard = GitHubWriteGuard()
    with pytest.raises(GitHubWriteError, match="CTO_OS_ALLOW_GITHUB_WRITES"):
        guard.require_writeable("create_issue", approved=True, dry_run=False)
