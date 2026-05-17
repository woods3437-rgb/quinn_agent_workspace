"""Phase 12 — worker heartbeat helpers.

The worker writes a heartbeat row each polling iteration. The health
aggregator considers a heartbeat older than ``STALE_AFTER_SECONDS`` to be
stale, which surfaces in `/system/health` and degrades overall status.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from .models import WorkerHeartbeat, WorkerStatus
from .sqlite_store import SQLiteStore


STALE_AFTER_SECONDS = 60


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def is_stale(heartbeat: WorkerHeartbeat, now: datetime | None = None) -> bool:
    moment = now or datetime.now(timezone.utc)
    return (moment - _ensure_aware(heartbeat.last_seen_at)).total_seconds() > STALE_AFTER_SECONDS


class HeartbeatWriter:
    """Best-effort heartbeat writer used by long-running processes.

    Errors never bubble — heartbeats are observability, not correctness.
    """

    def __init__(self, store: SQLiteStore, worker_name: str) -> None:
        self.store = store
        self.worker_name = worker_name
        self.pid = os.getpid()

    def beat(
        self,
        status: WorkerStatus = WorkerStatus.running,
        metadata: dict[str, Any] | None = None,
    ) -> WorkerHeartbeat | None:
        heartbeat = WorkerHeartbeat(
            worker_name=self.worker_name,
            pid=self.pid,
            status=status,
            metadata_json=metadata or {},
        )
        try:
            return self.store.upsert_worker_heartbeat(heartbeat)
        except Exception:
            return None
