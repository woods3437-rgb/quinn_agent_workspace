"""Phase 14 — local backup mirror streams + records bytes_copied."""
from __future__ import annotations

from pathlib import Path

from cto_os_api.backup_mirror import BackupMirrorService
from cto_os_api.models import ProjectCreate
from cto_os_api.snapshots import SnapshotManager


def test_local_mirror_streams_and_records_bytes(store, monkeypatch, tmp_data_dir):
    snapshots = SnapshotManager(store)
    store.create_project(ProjectCreate(name="stream"))
    snap = snapshots.create_snapshot()
    destination = tmp_data_dir / "stream_dest"
    monkeypatch.setenv("CTO_OS_ENABLE_BACKUP_MIRROR", "1")
    monkeypatch.setenv("CTO_OS_BACKUP_SINK", "local")
    monkeypatch.setenv("CTO_OS_BACKUP_DESTINATION", str(destination))

    event = BackupMirrorService(store, snapshots).mirror(snap.id)
    assert event.status.value == "completed"
    assert event.bytes_copied == snap.size_bytes > 0
    target = destination / snap.filename
    assert target.exists()
    assert target.stat().st_size == snap.size_bytes


def test_no_shell_true_in_subprocess_calls():
    """Regression: backup_mirror.py must never use shell=True."""
    source = Path("cto_os_api/backup_mirror.py").read_text()
    assert "shell=True" not in source
