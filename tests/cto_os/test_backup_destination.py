"""Phase 13 — BackupPolicy.destination_path honored by snapshots."""
from __future__ import annotations

from pathlib import Path

from cto_os_api.backups import BackupService
from cto_os_api.models import BackupPolicyUpdate, ProjectCreate
from cto_os_api.snapshots import SnapshotManager


def test_default_destination_used_when_empty(store):
    snapshots = SnapshotManager(store)
    snap = snapshots.create_snapshot()
    assert Path(snap.path).parent == snapshots.snapshot_dir
    assert snapshots.snapshot_dir == store.path.parent / "snapshots"


def test_custom_destination_honored_after_update(store, tmp_data_dir):
    snapshots = SnapshotManager(store)
    backups = BackupService(store, snapshots)
    custom = tmp_data_dir / "custom_snapshots"
    backups.update_policy(BackupPolicyUpdate(destination_path=str(custom)))

    store.create_project(ProjectCreate(name="dp"))
    snap = snapshots.create_snapshot()
    assert Path(snap.path).parent.resolve() == custom.resolve()
    assert (custom / snap.filename).exists()


def test_rotation_constrained_to_destination(store, tmp_data_dir):
    snapshots = SnapshotManager(store)
    backups = BackupService(store, snapshots)
    custom = tmp_data_dir / "rotated"
    backups.update_policy(
        BackupPolicyUpdate(enabled=True, destination_path=str(custom), max_snapshots=2)
    )
    store.create_project(ProjectCreate(name="rot"))
    for _ in range(4):
        backups.run(force=True)
    remaining = snapshots.list_snapshots()
    assert len(remaining) <= 2
    for manifest in remaining:
        assert Path(manifest.path).resolve().is_relative_to(custom.resolve())
