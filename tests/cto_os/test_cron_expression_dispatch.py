"""Phase 14 — cron expression overrides cadence; retention_cleanup dispatch."""
from __future__ import annotations

from datetime import datetime, timezone

from cto_os_api.cron_service import CronService
from cto_os_api.daily_review import DailyReviewService
from cto_os_api.github_reconciliation import GitHubReconciliation
from cto_os_api.health import HealthService
from cto_os_api.health_history import HealthHistoryService
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import (
    CronCadence,
    CronJobCreate,
    CronJobType,
    CronJobUpdate,
)
from cto_os_api.retention_service import RetentionService
from cto_os_api.snapshots import SnapshotManager
from cto_os_api.workspace_generators import WorkspaceGenerator
from cto_os_api.backups import BackupService


def _service(store):
    snapshots = SnapshotManager(store)
    backups = BackupService(store, snapshots)
    return CronService(
        store,
        daily_review=DailyReviewService(store),
        backups=backups,
        health_history=HealthHistoryService(
            store, HealthService(store, snapshots, backups)
        ),
        reconciliation=GitHubReconciliation(store),
        workspace_generator=WorkspaceGenerator(store, LocalMemoryEngine(store)),
        retention_service=RetentionService(store),
    )


def test_cron_expression_overrides_cadence(store):
    cron = _service(store)
    cron.ensure_defaults()
    health = next(j for j in store.list_cron_jobs() if j.job_type == CronJobType.health_snapshot)
    cron.update(
        health.id,
        CronJobUpdate(enabled=True, cadence=CronCadence.hourly, cron_expression="0 9 * * *"),
    )
    result = cron.run_job(health.id)
    assert result.ran is True
    persisted = store.get_cron_job(health.id)
    # Next fire should land at 09:00 UTC of some day, not last_run + 1h.
    assert persisted.next_run_at.hour == 9
    assert persisted.next_run_at.minute == 0


def test_invalid_cron_expression_rejected_at_create(store):
    cron = _service(store)
    try:
        cron.create(
            CronJobCreate(
                name="bad", job_type=CronJobType.daily_review,
                cron_expression="not a cron",
            )
        )
    except ValueError as exc:
        assert "Invalid cron_expression" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_retention_cleanup_dispatch(store):
    cron = _service(store)
    cron.ensure_defaults()
    retention_job = next(
        j for j in store.list_cron_jobs() if j.job_type == CronJobType.retention_cleanup
    )
    cron.update(retention_job.id, CronJobUpdate(enabled=True, cadence=CronCadence.daily))
    result = cron.run_job(retention_job.id)
    assert result.ran is True
    assert "retention" in result.output_summary
