"""Phase 14 regression — no anthropic, no shell, no github writes."""
from __future__ import annotations

import pytest

from cto_os_api.cron_service import CronService
from cto_os_api.daily_review import DailyReviewService
from cto_os_api.github_reconciliation import GitHubReconciliation
from cto_os_api.github_write_guard import GitHubWriteError, GitHubWriteGuard
from cto_os_api.health import HealthService
from cto_os_api.health_history import HealthHistoryService
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import CronJobCreate, CronJobType
from cto_os_api.retention_service import RetentionService
from cto_os_api.snapshots import SnapshotManager
from cto_os_api.workspace_generators import WorkspaceGenerator
from cto_os_api.backups import BackupService


def test_no_anthropic_or_openai_required(store, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("CTO_OS_LLM_PROVIDER", "deterministic")
    snapshots = SnapshotManager(store)
    backups = BackupService(store, snapshots)
    retention = RetentionService(store)
    cron = CronService(
        store,
        daily_review=DailyReviewService(store),
        backups=backups,
        health_history=HealthHistoryService(
            store, HealthService(store, snapshots, backups)
        ),
        reconciliation=GitHubReconciliation(store),
        workspace_generator=WorkspaceGenerator(store, LocalMemoryEngine(store)),
        retention_service=retention,
    )
    cron.ensure_defaults()
    retention.ensure_defaults()
    # retention_cleanup default exists
    assert any(j.job_type == CronJobType.retention_cleanup for j in store.list_cron_jobs())


def test_unknown_cron_type_rejected(store):
    cron = CronService(
        store,
        daily_review=DailyReviewService(store),
        backups=BackupService(store, SnapshotManager(store)),
        health_history=HealthHistoryService(
            store, HealthService(store, SnapshotManager(store), BackupService(store, SnapshotManager(store)))
        ),
        reconciliation=GitHubReconciliation(store),
        workspace_generator=WorkspaceGenerator(store, LocalMemoryEngine(store)),
        retention_service=RetentionService(store),
    )
    with pytest.raises(Exception):
        cron.create(CronJobCreate(name="bogus", job_type="not_a_real_type"))  # type: ignore[arg-type]


def test_phase7_guard_still_blocks(monkeypatch):
    monkeypatch.delenv("CTO_OS_ALLOW_GITHUB_WRITES", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "stub")
    with pytest.raises(GitHubWriteError):
        GitHubWriteGuard().require_writeable("create_issue", approved=True, dry_run=False)
