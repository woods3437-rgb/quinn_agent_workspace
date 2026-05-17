"""Phase 13 — cron service: defaults, due detection, run."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cto_os_api.backups import BackupService
from cto_os_api.cron_service import CronService
from cto_os_api.daily_review import DailyReviewService
from cto_os_api.github_reconciliation import GitHubReconciliation
from cto_os_api.health import HealthService
from cto_os_api.health_history import HealthHistoryService
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import CronCadence, CronJobCreate, CronJobType, CronJobUpdate
from cto_os_api.snapshots import SnapshotManager
from cto_os_api.workspace_generators import WorkspaceGenerator


def _service(store):
    snapshots = SnapshotManager(store)
    backups = BackupService(store, snapshots)
    health = HealthService(store, snapshots, backups)
    health_history = HealthHistoryService(store, health)
    memory = LocalMemoryEngine(store)
    workspace = WorkspaceGenerator(store, memory)
    reconciliation = GitHubReconciliation(store)
    return CronService(
        store,
        daily_review=DailyReviewService(store),
        backups=backups,
        health_history=health_history,
        reconciliation=reconciliation,
        workspace_generator=workspace,
    )


def test_ensure_defaults_seeds_six_disabled_jobs(store):
    cron = _service(store)
    cron.ensure_defaults()
    jobs = store.list_cron_jobs()
    types = {job.job_type for job in jobs}
    # Phase 14: retention_cleanup added as a default; covers every enum value.
    assert types == set(CronJobType)
    assert all(job.enabled is False for job in jobs)
    expected_count = len(list(CronJobType))
    # Idempotent re-seed
    cron.ensure_defaults()
    assert len(store.list_cron_jobs()) == expected_count


def test_disabled_job_skipped(store):
    cron = _service(store)
    cron.ensure_defaults()
    daily = next(j for j in store.list_cron_jobs() if j.job_type == CronJobType.daily_review)
    result = cron.run_job(daily.id)
    assert result.ran is False
    assert "disabled" in result.reason.lower()


def test_enabled_due_job_runs_and_updates_next(store):
    cron = _service(store)
    cron.ensure_defaults()
    daily = next(j for j in store.list_cron_jobs() if j.job_type == CronJobType.daily_review)
    cron.update(daily.id, CronJobUpdate(enabled=True, cadence=CronCadence.daily))
    result = cron.run_job(daily.id)
    assert result.ran is True
    assert "daily review" in result.output_summary.lower()
    persisted = store.get_cron_job(daily.id)
    assert persisted.last_run_at is not None
    assert persisted.next_run_at is not None
    assert persisted.next_run_at > persisted.last_run_at


def test_run_due_only_picks_enabled_due_jobs(store):
    cron = _service(store)
    cron.ensure_defaults()
    health = next(j for j in store.list_cron_jobs() if j.job_type == CronJobType.health_snapshot)
    cron.update(health.id, CronJobUpdate(enabled=True, cadence=CronCadence.hourly))
    results = cron.run_due()
    assert any(r.ran and r.job.job_type == CronJobType.health_snapshot for r in results)
    # Re-running immediately should not re-fire (next_run_at in future).
    later = cron.run_due()
    assert not any(r.ran and r.job.id == health.id for r in later)


def test_unknown_job_type_rejected(store):
    cron = _service(store)
    with pytest.raises(Exception):
        cron.create(CronJobCreate(name="weird", job_type="cleanup"))  # type: ignore[arg-type]
