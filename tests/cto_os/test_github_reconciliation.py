"""Phase 8 — reconciliation tests with stubbed GitHub HTTP."""
from __future__ import annotations

import pytest

from cto_os_api import github_integration as gh_module
from cto_os_api.github_integration import GitHubIntegration
from cto_os_api.github_reconciliation import GitHubReconciliation
from cto_os_api.models import (
    BuildSessionCreate,
    BuildSessionStatus,
    GitHubSyncStatus,
    PRPacket,
    ProjectCreate,
    ReconcileRequest,
    RepositoryCreate,
    RepositoryProvider,
    RiskCreate,
    TaskCreate,
    TaskStatus,
)


class _StubResponse:
    def __init__(self, status_code: int = 200, payload=None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


@pytest.fixture
def github_repo(store):
    project = store.create_project(ProjectCreate(name="phase8"))
    repo = store.create_repository(
        project.id,
        RepositoryCreate(
            provider=RepositoryProvider.github,
            name="repo",
            url="https://github.com/octocat/repo.git",
            default_branch="main",
        ),
    )
    return project, repo


@pytest.fixture
def patcher(monkeypatch):
    def _patch(issue_state=None, pr_state=None):
        def fake_get(url, headers=None, timeout=None):
            if "/issues/" in url and issue_state is not None:
                return _StubResponse(200, issue_state)
            if "/pulls/" in url and pr_state is not None:
                return _StubResponse(200, pr_state)
            return _StubResponse(404, {})

        monkeypatch.setattr(gh_module.httpx, "get", fake_get)

    return _patch


def test_closed_issue_suggests_task_done(store, github_repo, patcher, monkeypatch):
    project, repo = github_repo
    task = store.create_task(project.id, TaskCreate(title="ship X"))
    task.github_issue_number = 11
    task.github_sync_status = GitHubSyncStatus.completed
    store.save_task(task)

    monkeypatch.setenv("GITHUB_TOKEN", "stub")
    patcher(issue_state={"state": "closed", "html_url": "https://example/issue/11", "closed_at": "2026-05-10T00:00:00Z"})

    service = GitHubReconciliation(store, GitHubIntegration())
    report = service.reconcile(project.id, ReconcileRequest())

    assert any(suggestion.suggested_status == TaskStatus.done.value for suggestion in report.suggestions)
    assert report.events and report.events[0].recommendation
    # default: nothing applied
    refreshed = store.get_task(project.id, task.id)
    assert refreshed.status != TaskStatus.done


def test_merged_pr_suggests_session_completed(store, github_repo, patcher, monkeypatch):
    project, repo = github_repo
    packet = store.save_pr_packet(
        PRPacket(
            project_id=project.id,
            repository_id=repo.id,
            title="ship X PR",
        )
    )
    packet.github_pr_number = 42
    packet.github_sync_status = GitHubSyncStatus.completed
    store.save_pr_packet(packet)
    session = store.create_build_session(
        project.id,
        BuildSessionCreate(
            title="ship X session",
            repository_id=repo.id,
            linked_pr_packet_id=packet.id,
            status=BuildSessionStatus.in_progress,
        ),
    )

    monkeypatch.setenv("GITHUB_TOKEN", "stub")
    patcher(pr_state={
        "state": "closed",
        "merged": True,
        "draft": False,
        "merged_at": "2026-05-10T00:00:00Z",
        "html_url": "https://example/pr/42",
    })

    service = GitHubReconciliation(store, GitHubIntegration())
    report = service.reconcile(project.id, ReconcileRequest())

    assert any(
        suggestion.suggested_status == BuildSessionStatus.completed.value
        and suggestion.entity_id == session.id
        for suggestion in report.suggestions
    )


def test_closed_unmerged_pr_suggests_session_abandoned(store, github_repo, patcher, monkeypatch):
    project, repo = github_repo
    packet = store.save_pr_packet(
        PRPacket(project_id=project.id, repository_id=repo.id, title="abandoned PR")
    )
    packet.github_pr_number = 7
    store.save_pr_packet(packet)
    session = store.create_build_session(
        project.id,
        BuildSessionCreate(title="abandoned session", linked_pr_packet_id=packet.id),
    )

    monkeypatch.setenv("GITHUB_TOKEN", "stub")
    patcher(pr_state={"state": "closed", "merged": False, "draft": False, "html_url": "https://example/pr/7"})

    service = GitHubReconciliation(store, GitHubIntegration())
    report = service.reconcile(project.id, ReconcileRequest())

    assert any(
        suggestion.suggested_status == BuildSessionStatus.abandoned.value
        for suggestion in report.suggestions
    )


def test_open_draft_pr_suggests_session_reviewing(store, github_repo, patcher, monkeypatch):
    project, repo = github_repo
    packet = store.save_pr_packet(
        PRPacket(project_id=project.id, repository_id=repo.id, title="draft PR")
    )
    packet.github_pr_number = 19
    store.save_pr_packet(packet)
    session = store.create_build_session(
        project.id,
        BuildSessionCreate(
            title="draft session",
            linked_pr_packet_id=packet.id,
            status=BuildSessionStatus.in_progress,
        ),
    )

    monkeypatch.setenv("GITHUB_TOKEN", "stub")
    patcher(pr_state={"state": "open", "merged": False, "draft": True, "html_url": "https://example/pr/19"})

    service = GitHubReconciliation(store, GitHubIntegration())
    report = service.reconcile(project.id, ReconcileRequest())

    assert any(
        suggestion.suggested_status == BuildSessionStatus.reviewing.value
        for suggestion in report.suggestions
    )


def test_degraded_without_token(store, github_repo, monkeypatch):
    project, repo = github_repo
    task = store.create_task(project.id, TaskCreate(title="no token"))
    task.github_issue_number = 5
    store.save_task(task)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("CTO_OS_ALLOW_AUTO_RECONCILE", raising=False)

    report = GitHubReconciliation(store).reconcile(project.id, ReconcileRequest())
    assert report.degraded is True
    assert "GITHUB_TOKEN" in report.reason


def test_no_repo_is_degraded(store, monkeypatch):
    project = store.create_project(ProjectCreate(name="empty"))
    monkeypatch.setenv("GITHUB_TOKEN", "stub")
    report = GitHubReconciliation(store).reconcile(project.id, ReconcileRequest())
    assert report.degraded is True
    assert "No repository" in report.reason


def test_auto_reconcile_requires_env_flag(store, github_repo, patcher, monkeypatch):
    project, repo = github_repo
    task = store.create_task(project.id, TaskCreate(title="auto X"))
    task.github_issue_number = 99
    store.save_task(task)
    monkeypatch.setenv("GITHUB_TOKEN", "stub")
    monkeypatch.delenv("CTO_OS_ALLOW_AUTO_RECONCILE", raising=False)
    patcher(issue_state={"state": "closed", "html_url": "https://example/issue/99"})

    service = GitHubReconciliation(store, GitHubIntegration())
    report = service.reconcile(project.id, ReconcileRequest(auto_reconcile=True))
    assert report.auto_applied == 0
    assert store.get_task(project.id, task.id).status != TaskStatus.done

    monkeypatch.setenv("CTO_OS_ALLOW_AUTO_RECONCILE", "1")
    report2 = service.reconcile(project.id, ReconcileRequest(auto_reconcile=True))
    # The new run produces a fresh suggestion (task still not done) and applies it.
    assert report2.auto_applied >= 1
    assert store.get_task(project.id, task.id).status == TaskStatus.done


def test_apply_dismiss_lifecycle(store, github_repo, patcher, monkeypatch):
    project, repo = github_repo
    risk = store.create_risk(project.id, RiskCreate(title="risk1"))
    risk.github_issue_number = 30
    store.save_risk(risk)

    monkeypatch.setenv("GITHUB_TOKEN", "stub")
    patcher(issue_state={"state": "closed", "html_url": "https://example/issue/30"})
    service = GitHubReconciliation(store, GitHubIntegration())
    report = service.reconcile(project.id, ReconcileRequest())

    suggestion = report.suggestions[0]
    dismissed = service.dismiss_suggestion(project.id, suggestion.id)
    assert dismissed.dismissed is True
    # Applying a dismissed suggestion is a no-op.
    again = service.apply_suggestion(project.id, suggestion.id)
    assert again is None
