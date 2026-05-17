"""Phase 13 — health snapshot + history summary."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cto_os_api.backups import BackupService
from cto_os_api.health import HealthService
from cto_os_api.health_history import HealthHistoryService
from cto_os_api.models import HealthStatus
from cto_os_api.snapshots import SnapshotManager


def _service(store):
    snapshots = SnapshotManager(store)
    backups = BackupService(store, snapshots)
    return HealthHistoryService(store, HealthService(store, snapshots, backups))


def test_snapshot_writes_row(store):
    service = _service(store)
    snap = service.snapshot()
    assert snap.id
    persisted = store.list_health_snapshots()
    assert any(s.id == snap.id for s in persisted)


def test_summary_buckets_24h_and_7d(store):
    service = _service(store)
    now = datetime.now(timezone.utc)
    for offset_hours, status in [
        (1, HealthStatus.ok),
        (2, HealthStatus.degraded),
        (25, HealthStatus.degraded),
        (24 * 8, HealthStatus.ok),
    ]:
        snap = service.snapshot()
        snap.created_at = now - timedelta(hours=offset_hours)
        snap.status = status
        store.append_health_snapshot(snap)
    summary = service.summary()
    # The most recent (within 24h) inserted by `snapshot()` are also counted.
    assert summary.sample_count_24h >= 2
    assert summary.sample_count_7d >= 3
    assert summary.degraded_count_7d >= 2
