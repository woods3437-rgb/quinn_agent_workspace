"""Phase 12 — backup policy + rotation. Phase 13 — mirror hook."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import (
    BackupCadence,
    BackupPolicy,
    BackupPolicyUpdate,
    BackupRunResult,
)
from .snapshots import SnapshotManager
from .sqlite_store import SQLiteStore


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


CADENCE_INTERVALS = {
    BackupCadence.daily: timedelta(hours=20),
    BackupCadence.weekly: timedelta(days=6, hours=12),
}


class BackupService:
    def __init__(self, store: SQLiteStore, snapshots: SnapshotManager) -> None:
        self.store = store
        self.snapshots = snapshots
        # Phase 13: lazy mirror to avoid a circular import.
        self._mirror_service = None

    def _mirror(self):
        if self._mirror_service is None:
            from .backup_mirror import BackupMirrorService

            self._mirror_service = BackupMirrorService(self.store, self.snapshots)
        return self._mirror_service

    def get_policy(self) -> BackupPolicy:
        return self.store.get_backup_policy()

    def update_policy(self, payload: BackupPolicyUpdate) -> BackupPolicy:
        updated = self.store.update_backup_policy(payload)
        # Phase 13: destination_path may have changed; refresh snapshot dir.
        try:
            self.snapshots.refresh_destination()
        except Exception:
            pass
        return updated

    def run(self, *, force: bool = False) -> BackupRunResult:
        policy = self.store.get_backup_policy()
        if not policy.enabled and not force:
            return BackupRunResult(
                ran=False,
                reason="Backup policy is disabled; pass force=true to override.",
                policy=policy,
            )
        if policy.cadence != BackupCadence.manual and not force:
            interval = CADENCE_INTERVALS.get(policy.cadence)
            if interval and policy.last_run_at is not None:
                next_due = _ensure_aware(policy.last_run_at) + interval
                if datetime.now(timezone.utc) < next_due:
                    return BackupRunResult(
                        ran=False,
                        reason=f"Not due yet (next run at {next_due.isoformat()}).",
                        policy=policy,
                    )

        # Phase 13: always re-read destination before creating.
        try:
            self.snapshots.refresh_destination()
        except Exception:
            pass
        manifest = self.snapshots.create_snapshot()
        policy = self.store.mark_backup_run(when=manifest.created_at)
        deleted = self._rotate(policy.max_snapshots)
        # Phase 13: best-effort cold-storage mirror; records its own event.
        try:
            self._mirror().mirror(manifest.id)
        except Exception:
            pass
        return BackupRunResult(
            ran=True,
            snapshot_id=manifest.id,
            deleted_snapshot_ids=deleted,
            policy=policy,
        )

    def _rotate(self, max_snapshots: int) -> list[str]:
        if max_snapshots <= 0:
            return []
        manifests = self.snapshots.list_snapshots()
        if len(manifests) <= max_snapshots:
            return []
        to_delete = manifests[max_snapshots:]
        deleted_ids: list[str] = []
        for manifest in to_delete:
            if self.snapshots.delete_snapshot(manifest.id):
                deleted_ids.append(manifest.id)
        return deleted_ids
