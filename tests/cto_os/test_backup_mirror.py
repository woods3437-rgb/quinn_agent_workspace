"""Phase 13 — backup mirror (env-gated, sink whitelist)."""
from __future__ import annotations

from pathlib import Path

import pytest

from cto_os_api import backup_mirror as bm_module
from cto_os_api.backup_mirror import BackupMirrorService
from cto_os_api.models import ProjectCreate
from cto_os_api.snapshots import SnapshotManager


def test_mirror_disabled_records_skipped(store, monkeypatch):
    monkeypatch.delenv("CTO_OS_ENABLE_BACKUP_MIRROR", raising=False)
    snapshots = SnapshotManager(store)
    store.create_project(ProjectCreate(name="M1"))
    snap = snapshots.create_snapshot()
    event = BackupMirrorService(store, snapshots).mirror(snap.id)
    assert event.status.value == "skipped"
    assert "disabled" in event.error_message.lower()
    persisted = store.list_backup_mirror_events()
    assert any(e.id == event.id for e in persisted)


def test_mirror_local_copies_file(store, monkeypatch, tmp_data_dir):
    snapshots = SnapshotManager(store)
    store.create_project(ProjectCreate(name="M2"))
    snap = snapshots.create_snapshot()
    destination = tmp_data_dir / "mirror_dest"
    monkeypatch.setenv("CTO_OS_ENABLE_BACKUP_MIRROR", "1")
    monkeypatch.setenv("CTO_OS_BACKUP_SINK", "local")
    monkeypatch.setenv("CTO_OS_BACKUP_DESTINATION", str(destination))

    event = BackupMirrorService(store, snapshots).mirror(snap.id)
    assert event.status.value == "completed"
    assert (destination / snap.filename).exists()


def test_mirror_unknown_sink_falls_back_to_local(store, monkeypatch, tmp_data_dir):
    snapshots = SnapshotManager(store)
    store.create_project(ProjectCreate(name="Mfb"))
    snap = snapshots.create_snapshot()
    destination = tmp_data_dir / "fallback_dest"
    monkeypatch.setenv("CTO_OS_ENABLE_BACKUP_MIRROR", "1")
    monkeypatch.setenv("CTO_OS_BACKUP_SINK", "nonsense")
    monkeypatch.setenv("CTO_OS_BACKUP_DESTINATION", str(destination))

    event = BackupMirrorService(store, snapshots).mirror(snap.id)
    assert event.status.value == "completed"
    assert (destination / snap.filename).exists()
    assert event.sink.value == "local"


def test_mirror_rclone_stubbed(store, monkeypatch):
    snapshots = SnapshotManager(store)
    store.create_project(ProjectCreate(name="Mrc"))
    snap = snapshots.create_snapshot()
    monkeypatch.setenv("CTO_OS_ENABLE_BACKUP_MIRROR", "1")
    monkeypatch.setenv("CTO_OS_BACKUP_SINK", "rclone")
    monkeypatch.setenv("CTO_OS_BACKUP_DESTINATION", "remote:bucket/cto-os")

    captured = {}

    class _Result:
        returncode = 0
        stderr = ""
        stdout = ""

    def fake_which(name):
        return "/usr/local/bin/rclone" if name == "rclone" else None

    def fake_run(args, **kwargs):
        captured["args"] = args
        return _Result()

    monkeypatch.setattr(bm_module.shutil, "which", fake_which)
    monkeypatch.setattr(bm_module.subprocess, "run", fake_run)

    event = BackupMirrorService(store, snapshots).mirror(snap.id)
    assert event.status.value == "completed"
    assert captured["args"][:2] == ["rclone", "copy"]
    assert captured["args"][-1] == "remote:bucket/cto-os"


def test_mirror_invalid_snapshot_recorded(store, monkeypatch, tmp_data_dir):
    monkeypatch.setenv("CTO_OS_ENABLE_BACKUP_MIRROR", "1")
    monkeypatch.setenv("CTO_OS_BACKUP_DESTINATION", str(tmp_data_dir))
    event = BackupMirrorService(store, SnapshotManager(store)).mirror("snap_nope")
    assert event.status.value == "failed"
    assert "missing" in event.error_message.lower()
