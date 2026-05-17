"""Phase 13 — internal cron jobs.

Off by default. Worker calls ``run_due()`` each polling loop. Each
runnable job is wrapped in a Phase 11 ``WriterLease(name=f"cron:{id}")``
so multiple workers can't fire the same job at once.

Job types are a closed whitelist; unknown types are rejected at create.
``weekly_review`` uses the configured ``CTO_OS_LLM_PROVIDER`` — which
defaults to ``deterministic``, so no API call is made.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .backups import BackupService
from .daily_review import DailyReviewService
from .github_reconciliation import GitHubReconciliation
from .health_history import HealthHistoryService
from .heartbeat import _ensure_aware
from .models import (
    CronCadence,
    CronJob,
    CronJobCreate,
    CronJobStatus,
    CronJobType,
    CronJobUpdate,
    CronRunResult,
    ReconcileRequest,
)
from .sqlite_store import SQLiteStore
from .workspace_generators import WorkspaceGenerator
from .writer_lease import WriterLease, WriterLeaseBusy


logger = logging.getLogger("cto_os.cron")


CADENCE_INTERVALS = {
    CronCadence.hourly: timedelta(hours=1),
    CronCadence.daily: timedelta(hours=24),
    CronCadence.weekly: timedelta(days=7),
}


DEFAULT_JOBS = [
    ("Daily CTO Review", CronJobType.daily_review, CronCadence.daily),
    ("Weekly Review", CronJobType.weekly_review, CronCadence.weekly),
    ("Backup", CronJobType.backup, CronCadence.daily),
    ("Health Snapshot", CronJobType.health_snapshot, CronCadence.hourly),
    ("Risk Scan", CronJobType.risk_scan, CronCadence.weekly),
    ("GitHub Reconcile", CronJobType.github_reconcile, CronCadence.daily),
    ("Retention Cleanup", CronJobType.retention_cleanup, CronCadence.daily),
]


class CronService:
    def __init__(
        self,
        store: SQLiteStore,
        *,
        daily_review: DailyReviewService,
        backups: BackupService,
        health_history: HealthHistoryService,
        reconciliation: GitHubReconciliation,
        workspace_generator: WorkspaceGenerator,
        retention_service=None,
    ) -> None:
        self.store = store
        self.daily_review = daily_review
        self.backups = backups
        self.health_history = health_history
        self.reconciliation = reconciliation
        self.workspace_generator = workspace_generator
        # Phase 14: optional retention service for the retention_cleanup job.
        self.retention_service = retention_service

    # --------------------------------------------------------------- defaults

    def ensure_defaults(self) -> list[CronJob]:
        """Idempotently seed the six default cron jobs (all disabled)."""
        existing_types = {job.job_type for job in self.store.list_cron_jobs()}
        created: list[CronJob] = []
        for name, job_type, cadence in DEFAULT_JOBS:
            if job_type in existing_types:
                continue
            created.append(
                self.store.create_cron_job(
                    CronJobCreate(name=name, job_type=job_type, cadence=cadence, enabled=False)
                )
            )
        return created

    # ------------------------------------------------------------ run-due path

    def run_due(self) -> list[CronRunResult]:
        results: list[CronRunResult] = []
        now = datetime.now(timezone.utc)
        for job in self.store.list_cron_jobs():
            if not self._is_due(job, now):
                continue
            results.append(self.run_job(job.id))
        return results

    def run_job(self, job_id: str) -> CronRunResult:
        job = self.store.get_cron_job(job_id)
        if not job.enabled:
            return CronRunResult(job=job, ran=False, reason="Job is disabled.")
        try:
            with WriterLease(self.store, name=f"cron:{job.id}", ttl_seconds=120):
                summary = self._dispatch(job)
                job.last_run_at = datetime.now(timezone.utc)
                job.next_run_at = self._next_run_for(job, job.last_run_at)
                job.status = CronJobStatus.completed
                job.last_error = ""
                self.store.save_cron_job(job)
                return CronRunResult(job=job, ran=True, output_summary=summary)
        except WriterLeaseBusy as exc:
            return CronRunResult(job=job, ran=False, reason=str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Cron job '%s' failed", job.name)
            job.status = CronJobStatus.failed
            job.last_error = str(exc)[:500]
            job.last_run_at = datetime.now(timezone.utc)
            job.next_run_at = self._next_run_for(job, job.last_run_at)
            self.store.save_cron_job(job)
            return CronRunResult(job=job, ran=False, reason=f"failed: {exc}")

    # --------------------------------------------------------- internal helpers

    def _is_due(self, job: CronJob, now: datetime) -> bool:
        if not job.enabled:
            return False
        # Phase 14: cron_expression takes precedence over cadence if set.
        if job.cron_expression:
            if job.next_run_at is None:
                return True
            return _ensure_aware(job.next_run_at) <= now
        if job.cadence == CronCadence.manual:
            return False
        if job.next_run_at is None:
            return True
        return _ensure_aware(job.next_run_at) <= now

    def _next_run_for(self, job: CronJob, after: datetime) -> datetime | None:
        # Phase 14: prefer cron_expression when supplied; fall back to cadence.
        if job.cron_expression:
            from .cron_expression import CronExpressionError, next_fire

            try:
                return next_fire(job.cron_expression, after=after)
            except CronExpressionError:
                # Bad expression — fall through to cadence (or None).
                pass
        interval = CADENCE_INTERVALS.get(job.cadence)
        if interval is None:
            return None
        return after + interval

    def _dispatch(self, job: CronJob) -> str:
        if job.job_type == CronJobType.daily_review:
            review = self.daily_review.build()
            return f"daily review headline: {review.headline}"
        if job.job_type == CronJobType.weekly_review:
            if job.project_id:
                output = self.workspace_generator.generate_weekly_brief(job.project_id)
                return f"weekly brief generated: {output.id}"
            return "weekly review: no project_id configured; skipped LLM call"
        if job.job_type == CronJobType.backup:
            result = self.backups.run(force=False)
            return f"backup ran={result.ran} snapshot={result.snapshot_id} reason={result.reason}"
        if job.job_type == CronJobType.health_snapshot:
            snapshot = self.health_history.snapshot()
            return f"health snapshot status={snapshot.status.value}"
        if job.job_type == CronJobType.risk_scan:
            if job.project_id:
                risks = self.workspace_generator.generate_risks(job.project_id)
                return f"risk scan: generated {len(risks)} risk(s)"
            return "risk scan: no project_id configured; skipped"
        if job.job_type == CronJobType.github_reconcile:
            if not job.project_id:
                return "github reconcile: no project_id configured; skipped"
            report = self.reconciliation.reconcile(
                job.project_id, ReconcileRequest(auto_reconcile=False)
            )
            return (
                f"reconcile events={len(report.events)} suggestions={len(report.suggestions)} "
                f"degraded={report.degraded}"
            )
        if job.job_type == CronJobType.retention_cleanup:
            if self.retention_service is None:
                return "retention_cleanup: retention service not wired; skipped"
            result = self.retention_service.run()
            deleted = sum(o.deleted for o in result.outcomes)
            skipped = sum(1 for o in result.outcomes if o.skipped)
            return f"retention: deleted={deleted} skipped={skipped}"
        return f"unknown job_type: {job.job_type}"

    # --------------------------------------------------------- public helpers

    def create(self, payload: CronJobCreate) -> CronJob:
        if payload.job_type not in {member for member in CronJobType}:
            raise ValueError(f"Unknown cron job_type: {payload.job_type}")
        # Phase 14: validate cron_expression at create time.
        if payload.cron_expression:
            from .cron_expression import CronExpressionError, parse

            try:
                parse(payload.cron_expression)
            except CronExpressionError as exc:
                raise ValueError(f"Invalid cron_expression: {exc}")
        return self.store.create_cron_job(payload)

    def update(self, job_id: str, payload: CronJobUpdate) -> CronJob:
        # Phase 14: validate cron_expression on update too.
        if payload.cron_expression:
            from .cron_expression import CronExpressionError, parse

            try:
                parse(payload.cron_expression)
            except CronExpressionError as exc:
                raise ValueError(f"Invalid cron_expression: {exc}")
        return self.store.update_cron_job(job_id, payload)
