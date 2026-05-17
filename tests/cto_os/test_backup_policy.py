"""Phase 12 — backup policy + rotation."""
from __future__ import annotations

from datetime import datetime, timezone

from cto_os_api.backups import BackupService
from cto_os_api.models import BackupCadence, BackupPolicyUpdate, ProjectCreate
from cto_os_api.snapshots import SnapshotManager


def _service(store):
    return BackupService(store, SnapshotManager(store))


def test_default_policy_is_disabled(store):
    policy = _service(store).get_policy()
    assert policy.enabled is False
    assert policy.cadence == BackupCadence.manual
    assert policy.max_snapshots == 10


def test_update_policy(store):
    service = _service(store)
    updated = service.update_policy(
        BackupPolicyUpdate(enabled=True, cadence=BackupCadence.daily, max_snapshots=3)
    )
    assert updated.enabled is True
    assert updated.cadence == BackupCadence.daily
    assert updated.max_snapshots == 3


def test_disabled_policy_blocks_run_unless_forced(store):
    service = _service(store)
    result = service.run()
    assert result.ran is False
    assert "disabled" in result.reason

    forced = service.run(force=True)
    assert forced.ran is True
    assert forced.snapshot_id


def test_rotation_keeps_only_max_snapshots(store):
    store.create_project(ProjectCreate(name="rot"))
    service = _service(store)
    service.update_policy(BackupPolicyUpdate(enabled=True, max_snapshots=2))

    snapshots_created = []
    for _ in range(4):
        result = service.run(force=True)
        if result.snapshot_id:
            snapshots_created.append(result.snapshot_id)

    manager = SnapshotManager(store)
    remaining = manager.list_snapshots()
    assert len(remaining) <= 2


def test_cadence_throttle(store):
    service = _service(store)
    service.update_policy(BackupPolicyUpdate(enabled=True, cadence=BackupCadence.daily))
    # First run goes through under force=true; second non-forced is throttled.
    first = service.run(force=True)
    assert first.ran is True
    blocked = service.run()
    assert blocked.ran is False
    assert "due" in blocked.reason.lower()
