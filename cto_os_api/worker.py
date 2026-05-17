from __future__ import annotations

import os
import time

from .execution_engine import ExecutionEngine
from .heartbeat import HeartbeatWriter
from .main import cron_service, execution_engine, store
from .models import JobStatus, WorkerStatus


def run_once(engine: ExecutionEngine = execution_engine) -> int:
    ran = 0
    for project in store.list_projects():
        jobs = store.list_jobs(project.id, status=JobStatus.queued.value)
        for job in jobs:
            if job.attempts >= int(os.getenv("CTO_OS_JOB_MAX_ATTEMPTS", "3")):
                continue
            engine.run_job(project.id, job.id)
            ran += 1
    return ran


def run_cron_once() -> int:
    """Phase 13: run due cron jobs and report how many fired."""
    try:
        results = cron_service.run_due()
    except Exception:  # noqa: BLE001
        return 0
    return sum(1 for r in results if r.ran)


def main() -> None:
    interval = float(os.getenv("CTO_OS_WORKER_POLL_SECONDS", "2"))
    worker_name = os.getenv("CTO_OS_WORKER_NAME", "default")
    heartbeat = HeartbeatWriter(store, worker_name=worker_name)
    print(f"CTO OS worker '{worker_name}' started (pid {os.getpid()}). Press Ctrl+C to stop.")
    heartbeat.beat(status=WorkerStatus.starting, metadata={"interval": interval})
    # Phase 13: ensure default cron rows exist (all disabled) on first boot.
    try:
        cron_service.ensure_defaults()
    except Exception:
        pass
    while True:
        try:
            ran = run_once()
            cron_ran = run_cron_once()
        except Exception as exc:  # noqa: BLE001
            heartbeat.beat(
                status=WorkerStatus.running, metadata={"last_error": str(exc)[:200]}
            )
            time.sleep(interval)
            continue
        heartbeat.beat(
            status=WorkerStatus.idle if (ran + cron_ran) == 0 else WorkerStatus.running,
            metadata={
                "last_batch_jobs": ran,
                "last_batch_cron": cron_ran,
                "interval": interval,
            },
        )
        if (ran + cron_ran) == 0:
            time.sleep(interval)


if __name__ == "__main__":
    main()
