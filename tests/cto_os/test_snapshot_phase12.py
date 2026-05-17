"""Phase 12 — snapshot verify + restore-preview."""
from __future__ import annotations

import pytest

from cto_os_api.models import ProjectCreate
from cto_os_api.snapshots import SnapshotManager


def test_create_verify_and_preview(store):
    store.create_project(ProjectCreate(name="snap-test"))
    manager = SnapshotManager(store)
    snapshot = manager.create_snapshot()

    integrity = manager.verify(snapshot.id)
    assert integrity.file_exists is True
    assert integrity.manifest_readable is True
    assert integrity.sqlite_ok is True
    assert integrity.integrity_check.lower() == "ok"
    assert integrity.issues == []

    preview = manager.restore_preview(snapshot.id)
    assert preview.snapshot_id == snapshot.id
    assert preview.snapshot_size_bytes > 0
    assert preview.current_project_count >= 1
    assert preview.safe_to_restore is True


def test_verify_missing_snapshot_reports_issue(store):
    integrity = SnapshotManager(store).verify("snap_does_not_exist")
    assert integrity.file_exists is False
    assert integrity.issues
    assert "missing" in integrity.issues[0].lower()


def test_restore_preview_unknown_raises(store):
    with pytest.raises(KeyError):
        SnapshotManager(store).restore_preview("snap_does_not_exist")
