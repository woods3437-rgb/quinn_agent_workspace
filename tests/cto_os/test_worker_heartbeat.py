"""Phase 12 — worker heartbeat helper."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cto_os_api.heartbeat import HeartbeatWriter, is_stale
from cto_os_api.models import WorkerStatus


def test_heartbeat_upserts_single_row(store):
    writer = HeartbeatWriter(store, worker_name="default")
    writer.beat()
    writer.beat(status=WorkerStatus.idle, metadata={"jobs": 0})
    rows = store.list_worker_heartbeats()
    assert sum(1 for r in rows if r.worker_name == "default") == 1
    only = next(r for r in rows if r.worker_name == "default")
    assert only.status == WorkerStatus.idle
    assert only.metadata_json.get("jobs") == 0


def test_is_stale(store):
    writer = HeartbeatWriter(store, worker_name="x")
    hb = writer.beat()
    assert is_stale(hb) is False
    hb.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=120)
    assert is_stale(hb) is True
