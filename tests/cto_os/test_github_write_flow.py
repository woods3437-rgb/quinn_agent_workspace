"""Phase 7 — preview/create flow tests with stubbed GitHub HTTP layer."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from cto_os_api import github_integration as gh_module
from cto_os_api.github_integration import GitHubIntegration
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import (
    BranchPlan,
    GitHubBranchCreateRequest,
    GitHubDraftPRCreateRequest,
    GitHubIssueCreateRequest,
    GitHubSyncStatus,
    PRPacket,
    ProjectCreate,
    RepositoryCreate,
    RepositoryProvider,
    RiskCreate,
    TaskCreate,
)
from cto_os_api.repo_operator import RepoOperator


class _StubResponse:
    def __init__(self, status_code: int = 201, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._payload


@pytest.fixture
def fake_github(monkeypatch):
    """Replace httpx.get/post on the github_integration module."""
    calls: list[dict] = []

    def fake_get(url: str, headers=None, timeout=None):
        calls.append({"method": "GET", "url": url})
        if "/git/ref/heads/" in url:
            return _StubResponse(200, {"object": {"sha": "deadbeef"}})
        return _StubResponse(200, [])

    def fake_post(url: str, headers=None, json=None, timeout=None):
        calls.append({"method": "POST", "url": url, "body": json})
        if url.endswith("/issues"):
            return _StubResponse(201, {"number": 42, "html_url": "https://example/issue/42"})
        if url.endswith("/git/refs"):
            return _StubResponse(201, {"ref": json["ref"]})
        if url.endswith("/pulls"):
            return _StubResponse(201, {"number": 7, "html_url": "https://example/pr/7"})
        if "/requested_reviewers" in url:
            return _StubResponse(201, {})
        return _StubResponse(404, {})

    monkeypatch.setattr(gh_module.httpx, "get", fake_get)
    monkeypatch.setattr(gh_module.httpx, "post", fake_post)
    return calls


@pytest.fixture
def operator(store):
    return RepoOperator(store, LocalMemoryEngine(store), GitHubIntegration())


@pytest.fixture
def github_repo(store):
    project = store.create_project(ProjectCreate(name="GH project"))
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


def _open_gates(monkeypatch):
    monkeypatch.setenv("CTO_OS_ALLOW_GITHUB_WRITES", "1")
    monkeypatch.setenv("GITHUB_TOKEN", "stub-token")
    monkeypatch.setenv("GITHUB_DEFAULT_OWNER", "octocat")


# ---------- task issues -----------------------------------------------------


def test_preview_task_issue_never_calls_github(store, operator, github_repo, fake_github):
    project, _repo = github_repo
    task = store.create_task(project.id, TaskCreate(title="ship Phase 7", description="do it"))

    event = operator.preview_task_issue(project.id, task.id)

    assert event.status.value == "previewed"
    assert event.dry_run is True
    assert event.action.value == "preview_issue"
    assert "ship Phase 7" == event.payload_json["title"]
    assert fake_github == []  # no HTTP traffic


def test_create_task_issue_blocked_when_env_off(
    store, operator, github_repo, fake_github, monkeypatch
):
    project, _repo = github_repo
    task = store.create_task(project.id, TaskCreate(title="ship Phase 7"))
    monkeypatch.setenv("CTO_OS_ALLOW_GITHUB_WRITES", "0")
    monkeypatch.setenv("GITHUB_TOKEN", "stub")

    event = operator.create_task_issue(
        project.id,
        task.id,
        GitHubIssueCreateRequest(approved=True, dry_run=False),
    )

    assert event.status.value == "blocked"
    assert "CTO_OS_ALLOW_GITHUB_WRITES" in event.error_message
    assert fake_github == []
    # Task should not be marked synced
    refreshed = store.get_task(project.id, task.id)
    assert refreshed.github_sync_status == GitHubSyncStatus.none


def test_create_task_issue_with_gates_open_posts_and_updates_task(
    store, operator, github_repo, fake_github, monkeypatch
):
    project, _repo = github_repo
    task = store.create_task(project.id, TaskCreate(title="ship Phase 7"))
    _open_gates(monkeypatch)

    event = operator.create_task_issue(
        project.id,
        task.id,
        GitHubIssueCreateRequest(approved=True, dry_run=False),
    )

    assert event.status.value == "completed"
    assert event.response_json["number"] == 42
    refreshed = store.get_task(project.id, task.id)
    assert refreshed.github_issue_number == 42
    assert refreshed.github_issue_url == "https://example/issue/42"
    assert refreshed.github_sync_status == GitHubSyncStatus.completed
    # One POST to /issues (no PR/branch traffic)
    posts = [call for call in fake_github if call["method"] == "POST"]
    assert len(posts) == 1
    assert posts[0]["url"].endswith("/issues")


# ---------- risk issues -----------------------------------------------------


def test_risk_issue_preview_payload_includes_severity(store, operator, github_repo, fake_github):
    project, _repo = github_repo
    risk = store.create_risk(project.id, RiskCreate(title="db blowup", recommendation="add backups"))

    event = operator.preview_risk_issue(project.id, risk.id)
    assert "db blowup" in event.payload_json["title"]
    body = event.payload_json["body"]
    assert "Severity:" in body
    assert "add backups" in body
    assert fake_github == []


# ---------- branch creation -------------------------------------------------


def test_preview_branch_returns_sanitised_name(store, operator, github_repo, fake_github):
    project, repo = github_repo
    plan = store.save_branch_plan(
        BranchPlan(
            project_id=project.id,
            repository_id=repo.id,
            branch_name="Feature/Phase 7!!",
            objective="ship phase 7",
        )
    )
    event = operator.preview_branch(project.id, plan.id)
    payload = event.payload_json
    assert payload["base_branch"] == "main"
    assert payload["branch_name"]
    assert " " not in payload["branch_name"]
    assert "!" not in payload["branch_name"]
    assert fake_github == []


def test_create_branch_posts_and_updates_plan(
    store, operator, github_repo, fake_github, monkeypatch
):
    project, repo = github_repo
    plan = store.save_branch_plan(
        BranchPlan(
            project_id=project.id,
            repository_id=repo.id,
            branch_name="phase-7-flow",
            objective="ship phase 7",
        )
    )
    _open_gates(monkeypatch)

    event = operator.create_branch(
        project.id,
        plan.id,
        GitHubBranchCreateRequest(approved=True, dry_run=False),
    )

    assert event.status.value == "completed"
    posts = [c for c in fake_github if c["method"] == "POST" and c["url"].endswith("/git/refs")]
    assert len(posts) == 1
    assert posts[0]["body"]["sha"] == "deadbeef"
    refreshed = store.get_branch_plan(project.id, plan.id)
    assert refreshed.github_branch_name == "phase-7-flow"
    assert "octocat/repo" in refreshed.github_branch_url


# ---------- draft PR --------------------------------------------------------


def test_preview_draft_pr_includes_draft_flag(store, operator, github_repo, fake_github):
    project, repo = github_repo
    plan = store.save_branch_plan(
        BranchPlan(
            project_id=project.id,
            repository_id=repo.id,
            branch_name="feature-x",
            objective="x",
        )
    )
    packet = store.save_pr_packet(
        PRPacket(
            project_id=project.id,
            repository_id=repo.id,
            branch_plan_id=plan.id,
            title="Draft PR for X",
            summary="adds X",
            acceptance_checklist=["X works"],
            test_plan=["npm test"],
        )
    )

    event = operator.preview_draft_pr(project.id, packet.id)
    assert event.payload_json["draft"] is True
    assert event.payload_json["head"] == "feature-x"
    assert event.payload_json["base"] == "main"
    assert fake_github == []


def test_create_draft_pr_posts_and_updates_packet(
    store, operator, github_repo, fake_github, monkeypatch
):
    project, repo = github_repo
    plan = store.save_branch_plan(
        BranchPlan(
            project_id=project.id,
            repository_id=repo.id,
            branch_name="feature-x",
            objective="x",
        )
    )
    packet = store.save_pr_packet(
        PRPacket(
            project_id=project.id,
            repository_id=repo.id,
            branch_plan_id=plan.id,
            title="Draft PR for X",
            summary="adds X",
        )
    )
    _open_gates(monkeypatch)

    event = operator.create_draft_pr(
        project.id,
        packet.id,
        GitHubDraftPRCreateRequest(approved=True, dry_run=False),
    )

    assert event.status.value == "completed"
    refreshed = store.get_pr_packet(project.id, packet.id)
    assert refreshed.github_pr_number == 7
    assert refreshed.github_pr_url == "https://example/pr/7"
    posts = [c for c in fake_github if c["url"].endswith("/pulls")]
    assert posts and posts[0]["body"]["draft"] is True


# ---------- write event log + build session attach --------------------------


def test_events_listed_and_attached_to_build_session(
    store, operator, github_repo, fake_github, monkeypatch
):
    from cto_os_api.models import BuildSessionCreate

    project, repo = github_repo
    task = store.create_task(project.id, TaskCreate(title="phase 7 work"))
    session = store.create_build_session(
        project.id,
        BuildSessionCreate(title="phase 7 build", repository_id=repo.id, task_id=task.id),
    )
    _open_gates(monkeypatch)

    event = operator.create_task_issue(
        project.id,
        task.id,
        GitHubIssueCreateRequest(approved=True, dry_run=False, build_session_id=session.id),
    )

    events = store.list_github_write_events(project.id)
    assert event.id in {item.id for item in events}
    refreshed_session = next(
        item for item in store.list_build_sessions(project.id) if item.id == session.id
    )
    assert event.id in refreshed_session.linked_github_write_event_ids


# ---------- read-only fallbacks -------------------------------------------


def test_github_status_advertises_writes_disabled_by_default(monkeypatch):
    monkeypatch.delenv("CTO_OS_ALLOW_GITHUB_WRITES", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    status = GitHubIntegration().status()
    assert status["writes_enabled"] is False
    assert status["configured"] is False
    assert "merge_pr" in status["disabled_capabilities"]
