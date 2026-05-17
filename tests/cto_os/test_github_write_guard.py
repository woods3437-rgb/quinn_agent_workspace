"""Phase 7 — GitHub write guard tests."""
from __future__ import annotations

import pytest

from cto_os_api.github_write_guard import (
    BLOCKED_GITHUB_OPS,
    GitHubWriteError,
    GitHubWriteGuard,
    sanitise_branch_name,
)


@pytest.fixture
def guard():
    return GitHubWriteGuard()


def test_dry_run_is_always_blocked(guard, monkeypatch):
    monkeypatch.setenv("CTO_OS_ALLOW_GITHUB_WRITES", "1")
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    with pytest.raises(GitHubWriteError, match="dry_run"):
        guard.require_writeable("create_issue", approved=True, dry_run=True)


def test_unapproved_is_blocked(guard, monkeypatch):
    monkeypatch.setenv("CTO_OS_ALLOW_GITHUB_WRITES", "1")
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    with pytest.raises(GitHubWriteError, match="approved"):
        guard.require_writeable("create_issue", approved=False, dry_run=False)


def test_missing_env_flag_is_blocked(guard, monkeypatch):
    monkeypatch.setenv("CTO_OS_ALLOW_GITHUB_WRITES", "0")
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    with pytest.raises(GitHubWriteError, match="CTO_OS_ALLOW_GITHUB_WRITES"):
        guard.require_writeable("create_issue", approved=True, dry_run=False)


def test_missing_token_is_blocked(guard, monkeypatch):
    monkeypatch.setenv("CTO_OS_ALLOW_GITHUB_WRITES", "1")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(GitHubWriteError, match="GITHUB_TOKEN"):
        guard.require_writeable("create_issue", approved=True, dry_run=False)


def test_full_open_lets_it_through(guard, monkeypatch):
    monkeypatch.setenv("CTO_OS_ALLOW_GITHUB_WRITES", "1")
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    guard.require_writeable("create_issue", approved=True, dry_run=False)


@pytest.mark.parametrize("blocked", sorted(BLOCKED_GITHUB_OPS))
def test_blocked_ops_always_rejected(guard, blocked, monkeypatch):
    monkeypatch.setenv("CTO_OS_ALLOW_GITHUB_WRITES", "1")
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    with pytest.raises(GitHubWriteError, match="permanently blocked"):
        guard.require_writeable(blocked, approved=True, dry_run=False)


def test_unknown_action_rejected(guard, monkeypatch):
    monkeypatch.setenv("CTO_OS_ALLOW_GITHUB_WRITES", "1")
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    with pytest.raises(GitHubWriteError, match="Unknown GitHub write action"):
        guard.require_writeable("create_workflow_run", approved=True, dry_run=False)


@pytest.mark.parametrize(
    "raw,expected_prefix",
    [
        ("Add: Phase 7 stuff!", "Add-Phase-7-stuff"),
        ("../escape", "escape"),
        ("nice/branch-name_ok", "nice/branch-name_ok"),
        ("", "cto-fallback"),  # empty falls back
        ("   ", "cto-fallback"),
    ],
)
def test_sanitise_branch_name(raw, expected_prefix):
    cleaned = sanitise_branch_name(raw, fallback="cto-fallback")
    assert cleaned.startswith(expected_prefix.rstrip("-"))
    assert ".." not in cleaned
    assert not cleaned.startswith("/")
    assert " " not in cleaned
