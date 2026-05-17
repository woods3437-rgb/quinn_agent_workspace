"""GitHub status test with no token (Phase 6 verification)."""
from __future__ import annotations

from cto_os_api.github_integration import GitHubIntegration


def test_github_status_without_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_DEFAULT_OWNER", raising=False)
    monkeypatch.delenv("CTO_OS_ALLOW_GITHUB_WRITES", raising=False)
    status = GitHubIntegration().status()
    assert status["configured"] is False
    # Permanently-blocked ops must always appear (Phase 7 BLOCKED_GITHUB_OPS).
    assert "merge_pr" in status["disabled_capabilities"]
    assert "delete_branch" in status["disabled_capabilities"]
    assert "force_push" in status["disabled_capabilities"]
    # Write capabilities exist but are gated behind CTO_OS_ALLOW_GITHUB_WRITES.
    assert status["writes_enabled"] is False
    assert "create_issue" in status["write_capabilities"]


def test_list_repositories_without_token_returns_empty(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_DEFAULT_OWNER", raising=False)
    assert GitHubIntegration().list_repositories() == []


def test_sync_without_token_returns_no_records(monkeypatch, repository, project):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    issues, prs = GitHubIntegration().sync_repository(project.id, repository)
    assert issues == []
    assert prs == []
