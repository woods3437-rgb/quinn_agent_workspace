"""Phase 13 — no-anthropic regression + Phase 7 guard still in force."""
from __future__ import annotations

import pytest

from cto_os_api.backups import BackupService
from cto_os_api.cron_service import CronService
from cto_os_api.daily_review import DailyReviewService
from cto_os_api.github_reconciliation import GitHubReconciliation
from cto_os_api.github_write_guard import GitHubWriteError, GitHubWriteGuard
from cto_os_api.health import HealthService
from cto_os_api.health_history import HealthHistoryService
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.snapshots import SnapshotManager
from cto_os_api.workspace_generators import WorkspaceGenerator


def _cron(store):
    snapshots = SnapshotManager(store)
    backups = BackupService(store, snapshots)
    health = HealthService(store, snapshots, backups)
    return CronService(
        store,
        daily_review=DailyReviewService(store),
        backups=backups,
        health_history=HealthHistoryService(store, health),
        reconciliation=GitHubReconciliation(store),
        workspace_generator=WorkspaceGenerator(store, LocalMemoryEngine(store)),
    )


def test_phase13_paths_work_without_keys(store, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("CTO_OS_LLM_PROVIDER", "deterministic")
    cron = _cron(store)
    cron.ensure_defaults()
    jobs = store.list_cron_jobs()
    assert jobs


def test_phase7_guard_still_blocks_by_default(monkeypatch):
    monkeypatch.delenv("CTO_OS_ALLOW_GITHUB_WRITES", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "stub")
    with pytest.raises(GitHubWriteError):
        GitHubWriteGuard().require_writeable("create_issue", approved=True, dry_run=False)
