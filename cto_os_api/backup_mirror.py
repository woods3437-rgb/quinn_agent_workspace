"""Phase 13 — cold-storage backup mirror.

Three gates: ``CTO_OS_ENABLE_BACKUP_MIRROR=1`` + valid sink +
non-empty ``CTO_OS_BACKUP_DESTINATION``. Sink whitelist: local | rclone
| s3 | scp. Records every attempt (skipped/completed/failed). Mirrors
only **verified** snapshots and never touches WAL/SHM sidecars.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from .models import (
    BackupMirrorEvent,
    BackupMirrorSink,
    BackupMirrorStatus,
    SnapshotManifest,
)
from .snapshots import SnapshotManager
from .sqlite_store import SQLiteStore


_VALID_SCP = re.compile(r"^[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+:.+$")


def env_mirror_enabled() -> bool:
    return os.getenv("CTO_OS_ENABLE_BACKUP_MIRROR", "0").strip() == "1"


def env_sink() -> BackupMirrorSink:
    raw = (os.getenv("CTO_OS_BACKUP_SINK", "local") or "local").strip().lower()
    try:
        return BackupMirrorSink(raw)
    except ValueError:
        return BackupMirrorSink.local


def env_destination() -> str:
    return (os.getenv("CTO_OS_BACKUP_DESTINATION", "") or "").strip()


class BackupMirrorService:
    def __init__(self, store: SQLiteStore, snapshots: SnapshotManager) -> None:
        self.store = store
        self.snapshots = snapshots

    def mirror(self, snapshot_id: str) -> BackupMirrorEvent:
        sink = env_sink()
        destination = env_destination()
        if not env_mirror_enabled():
            return self._event(snapshot_id, sink, destination, "skipped: mirror disabled")
        if not destination:
            return self._event(snapshot_id, sink, destination, "skipped: destination empty")

        manifests = {m.id: m for m in self.snapshots.list_snapshots()}
        manifest = manifests.get(snapshot_id)
        if manifest is None:
            return self._event(snapshot_id, sink, destination, "failed: snapshot missing", failed=True)

        integrity = self.snapshots.verify(snapshot_id)
        if not integrity.sqlite_ok:
            issues = ", ".join(integrity.issues) or integrity.integrity_check
            return self._event(
                snapshot_id, sink, destination, f"skipped: integrity_check failed ({issues})"
            )

        bytes_copied = 0
        try:
            if sink == BackupMirrorSink.local:
                bytes_copied = self._copy_local(manifest, destination)
            elif sink == BackupMirrorSink.rclone:
                self._copy_rclone(manifest, destination)
                bytes_copied = manifest.size_bytes
            elif sink == BackupMirrorSink.scp:
                self._copy_scp(manifest, destination)
                bytes_copied = manifest.size_bytes
            elif sink == BackupMirrorSink.s3:
                bytes_copied = self._copy_s3(manifest, destination)
            else:  # pragma: no cover - whitelist guarded above
                raise RuntimeError(f"Unknown sink {sink}")
        except _MirrorSkip as exc:
            return self._event(snapshot_id, sink, destination, f"skipped: {exc}")
        except Exception as exc:  # noqa: BLE001
            return self._event(
                snapshot_id, sink, destination, f"failed: {exc}", failed=True
            )
        return self._event(
            snapshot_id, sink, destination, "", completed=True, bytes_copied=bytes_copied
        )

    # ---------------------------------------------------------------- sinks

    def _copy_local(self, manifest: SnapshotManifest, destination: str) -> int:
        """Phase 14: stream the snapshot in 1 MiB chunks; preserve mtime."""
        dest_dir = Path(destination).expanduser().resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)
        if not dest_dir.is_dir():
            raise RuntimeError(f"destination is not a directory: {dest_dir}")
        src = Path(manifest.path)
        dst = dest_dir / manifest.filename
        chunk_size = 1024 * 1024
        bytes_copied = 0
        with open(src, "rb") as src_fp, open(dst, "wb") as dst_fp:
            while True:
                chunk = src_fp.read(chunk_size)
                if not chunk:
                    break
                dst_fp.write(chunk)
                bytes_copied += len(chunk)
        # Preserve mtime/atime to match shutil.copy2's behavior.
        try:
            stat = src.stat()
            import os as _os

            _os.utime(dst, (stat.st_atime, stat.st_mtime))
        except Exception:
            pass
        return bytes_copied

    def _copy_rclone(self, manifest: SnapshotManifest, destination: str) -> None:
        if shutil.which("rclone") is None:
            raise _MirrorSkip("rclone binary not on PATH")
        result = subprocess.run(
            ["rclone", "copy", manifest.path, destination],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "rclone copy failed")

    def _copy_scp(self, manifest: SnapshotManifest, destination: str) -> None:
        if shutil.which("scp") is None:
            raise _MirrorSkip("scp binary not on PATH")
        if not _VALID_SCP.match(destination):
            raise RuntimeError(
                "scp destination must look like user@host:/path"
            )
        result = subprocess.run(
            ["scp", manifest.path, destination],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "scp copy failed")

    def _copy_s3(self, manifest: SnapshotManifest, destination: str) -> int:
        try:
            import boto3  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise _MirrorSkip(f"boto3 not installed ({exc})")
        if not destination.startswith("s3://"):
            raise RuntimeError("s3 destination must start with s3://bucket/prefix")
        bucket_path = destination[len("s3://") :]
        bucket, _, prefix = bucket_path.partition("/")
        key = f"{prefix.rstrip('/')}/{manifest.filename}" if prefix else manifest.filename
        s3 = boto3.client("s3")
        # Phase 14: upload as a streaming file object instead of buffering.
        with open(manifest.path, "rb") as src_fp:
            s3.upload_fileobj(src_fp, bucket, key)
        return manifest.size_bytes

    # ----------------------------------------------------------------- write

    def _event(
        self,
        snapshot_id: str,
        sink: BackupMirrorSink,
        destination: str,
        message: str = "",
        *,
        completed: bool = False,
        failed: bool = False,
        bytes_copied: int = 0,
    ) -> BackupMirrorEvent:
        if completed:
            status = BackupMirrorStatus.completed
            error = ""
        elif failed:
            status = BackupMirrorStatus.failed
            error = message
        else:
            status = BackupMirrorStatus.skipped
            error = message
        event = BackupMirrorEvent(
            snapshot_id=snapshot_id,
            sink=sink,
            destination=destination,
            status=status,
            error_message=error,
            bytes_copied=bytes_copied,
        )
        return self.store.append_backup_mirror_event(event)


class _MirrorSkip(Exception):
    """Convert an external-tool unavailability into a 'skipped' event."""
