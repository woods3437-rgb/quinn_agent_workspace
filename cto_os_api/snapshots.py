from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import SnapshotIntegrity, SnapshotManifest, SnapshotRestorePreview
from .sqlite_store import SQLiteStore


APP_VERSION = "0.13.0"


class SnapshotManager:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self._default_dir = store.path.parent / "snapshots"
        self._default_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_dir = self._resolve_snapshot_dir()

    def _resolve_snapshot_dir(self) -> Path:
        """Phase 13: honor BackupPolicy.destination_path when non-empty.

        Falls back to the default ``data/snapshots`` directory. Resolves the
        configured path; if it cannot be created safely, falls back rather
        than writing to the filesystem in unexpected places.
        """
        configured = ""
        try:
            policy = self.store.get_backup_policy()
            configured = (policy.destination_path or "").strip()
        except Exception:
            configured = ""
        if not configured:
            return self._default_dir
        try:
            path = Path(configured).expanduser().resolve()
            path.mkdir(parents=True, exist_ok=True)
            return path
        except Exception:
            return self._default_dir

    def refresh_destination(self) -> Path:
        """Re-read BackupPolicy.destination_path; used after a PATCH."""
        self.snapshot_dir = self._resolve_snapshot_dir()
        return self.snapshot_dir

    # ------------------------------------------------------------ create

    def create_snapshot(self) -> SnapshotManifest:
        created_at = datetime.now(timezone.utc)
        snapshot_id = f"snap_{created_at.strftime('%Y%m%d%H%M%S%f')}"
        filename = f"{snapshot_id}.sqlite3"
        destination = self.snapshot_dir / filename
        wal_checkpointed = False
        if self.store.path.exists():
            # Phase 12: checkpoint WAL into the main file so the snapshot
            # captures a consistent view without needing to copy *-wal / *-shm.
            try:
                with self.store._connect() as conn:
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                wal_checkpointed = True
            except Exception:
                wal_checkpointed = False
            shutil.copy2(self.store.path, destination)
        else:
            destination.touch()
        return self._manifest(
            snapshot_id,
            destination,
            created_at,
            wal_checkpointed=wal_checkpointed,
        )

    # ------------------------------------------------------------- list

    def list_snapshots(self) -> list[SnapshotManifest]:
        manifests: list[SnapshotManifest] = []
        for path in sorted(self.snapshot_dir.glob("snap_*.sqlite3"), reverse=True):
            created_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            manifests.append(self._manifest(path.stem, path, created_at))
        return manifests

    # ---------------------------------------------------------- restore

    def restore_snapshot(self, snapshot_id: str) -> SnapshotManifest:
        snapshot = self.snapshot_dir / f"{snapshot_id}.sqlite3"
        if not snapshot.exists():
            raise KeyError(snapshot_id)
        backup = self.store.path.with_suffix(
            f".pre-restore-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.sqlite3"
        )
        if self.store.path.exists():
            shutil.copy2(self.store.path, backup)
        shutil.copy2(snapshot, self.store.path)
        return self._manifest(
            snapshot_id,
            snapshot,
            datetime.fromtimestamp(snapshot.stat().st_mtime, tz=timezone.utc),
        )

    # ---------------------------------------------------- verify + preview

    def verify(self, snapshot_id: str) -> SnapshotIntegrity:
        snapshot = self.snapshot_dir / f"{snapshot_id}.sqlite3"
        report = SnapshotIntegrity(snapshot_id=snapshot_id)
        if not snapshot.exists():
            report.issues.append("Snapshot file is missing.")
            return report
        report.file_exists = True
        report.size_bytes = snapshot.stat().st_size

        try:
            self._manifest(
                snapshot_id,
                snapshot,
                datetime.fromtimestamp(snapshot.stat().st_mtime, tz=timezone.utc),
            )
            report.manifest_readable = True
        except Exception as exc:
            report.issues.append(f"Manifest unreadable: {exc}")

        try:
            conn = sqlite3.connect(snapshot)
            conn.row_factory = sqlite3.Row
            row = conn.execute("PRAGMA integrity_check").fetchone()
            report.integrity_check = row[0] if row else ""
            report.sqlite_ok = (report.integrity_check or "").lower() == "ok"
            if not report.sqlite_ok:
                report.issues.append(f"integrity_check returned: {report.integrity_check}")
            conn.close()
        except Exception as exc:
            report.issues.append(f"SQLite open failed: {exc}")
        return report

    def restore_preview(self, snapshot_id: str) -> SnapshotRestorePreview:
        snapshot = self.snapshot_dir / f"{snapshot_id}.sqlite3"
        if not snapshot.exists():
            raise KeyError(snapshot_id)
        preview = SnapshotRestorePreview(snapshot_id=snapshot_id)
        preview.snapshot_size_bytes = snapshot.stat().st_size
        preview.snapshot_created_at = datetime.fromtimestamp(
            snapshot.stat().st_mtime, tz=timezone.utc
        )
        if self.store.path.exists():
            preview.current_db_size_bytes = self.store.path.stat().st_size
        try:
            preview.current_project_count = len(self.store.list_projects())
        except Exception:
            preview.current_project_count = 0
        if preview.snapshot_size_bytes < preview.current_db_size_bytes:
            preview.notes.append(
                "Snapshot is smaller than the current database; restoring will discard rows."
            )
            preview.safe_to_restore = False
        try:
            conn = sqlite3.connect(snapshot)
            cur = conn.execute("SELECT COUNT(*) FROM projects")
            snapshot_projects = int(cur.fetchone()[0])
            conn.close()
            preview.notes.append(
                f"Snapshot contains {snapshot_projects} project(s); current has {preview.current_project_count}."
            )
        except Exception as exc:
            preview.notes.append(f"Could not enumerate snapshot projects: {exc}")
        return preview

    def delete_snapshot(self, snapshot_id: str) -> bool:
        snapshot = self.snapshot_dir / f"{snapshot_id}.sqlite3"
        if not snapshot.exists():
            return False
        # Guard against escaping the snapshot directory.
        try:
            snapshot.resolve().relative_to(self.snapshot_dir.resolve())
        except ValueError:
            return False
        snapshot.unlink()
        return True

    # ------------------------------------------------------------ helpers

    def _manifest(
        self,
        snapshot_id: str,
        path: Path,
        created_at: datetime,
        *,
        wal_checkpointed: bool | None = None,
    ) -> SnapshotManifest:
        manifest = SnapshotManifest(
            id=snapshot_id,
            filename=path.name,
            path=str(path),
            created_at=created_at,
            app_version=APP_VERSION,
            sqlite_path=str(self.store.path),
            size_bytes=path.stat().st_size if path.exists() else 0,
        )
        # SnapshotManifest is a fixed schema today; we don't introduce new
        # required fields. Per-snapshot extras (`wal_checkpointed`,
        # `mcp_config_present`, `includes_chroma`) are surfaced by /system/health
        # and the verify route instead of stuffed into the bundle file.
        return manifest

    @staticmethod
    def mcp_config_present(repo_root: Path | str | None = None) -> bool:
        root = Path(repo_root or Path.cwd())
        return (root / ".mcp.json").exists() or (root / ".mcp.example.json").exists()

    @staticmethod
    def chroma_path_present() -> bool:
        path = os.getenv("CTO_OS_CHROMA_CACHE_DIR", "")
        return bool(path) and Path(path).exists()
