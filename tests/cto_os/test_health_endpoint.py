"""Phase 12 — system health aggregator + rollup."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cto_os_api.backups import BackupService
from cto_os_api.health import HealthService
from cto_os_api.heartbeat import HeartbeatWriter
from cto_os_api.models import (
    HealthStatus,
    JobCreate,
    JobStatus,
    ProjectCreate,
    WorkerStatus,
)
from cto_os_api.snapshots import SnapshotManager


def _services(store):
    snapshots = SnapshotManager(store)
    backups = BackupService(store, snapshots)
    return HealthService(store, snapshots, backups)


def test_health_ok_when_nothing_broken(store, monkeypatch):
    monkeypatch.delenv("CTO_OS_ALLOW_GITHUB_WRITES", raising=False)
    report = _services(store).build()
    assert report.status == HealthStatus.ok
    assert report.sqlite["reachable"] is True
    assert report.sqlite["journal_mode"] == "wal"


def test_health_degraded_when_worker_stale(store, monkeypatch):
    writer = HeartbeatWriter(store, worker_name="stale_worker")
    hb = writer.beat(status=WorkerStatus.idle)
    # Force the heartbeat into the past.
    hb.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=120)
    store.upsert_worker_heartbeat(hb)
    report = _services(store).build()
    assert report.status == HealthStatus.degraded


def test_health_degraded_when_failed_job_present(store):
    project = store.create_project(ProjectCreate(name="HJ"))
    # Insert a job and mark it failed by re-saving.
    from cto_os_api.execution_engine import ExecutionEngine
    from cto_os_api.memory_engine import LocalMemoryEngine
    from cto_os_api.repo_operator import RepoOperator
    from cto_os_api.workspace_generators import WorkspaceGenerator

    engine = ExecutionEngine(
        store,
        LocalMemoryEngine(store),
        WorkspaceGenerator(store, LocalMemoryEngine(store)),
        lambda *a, **k: None,
        RepoOperator(store, LocalMemoryEngine(store)),
    )
    job = engine.create_job(project.id, JobCreate(type="risk_scan", title="boom"))
    job.status = JobStatus.failed
    job.error_message = "boom"
    store.save_job(job)

    report = _services(store).build()
    assert report.status == HealthStatus.degraded
    assert any(j.id == job.id for j in report.recent_failed_jobs)
