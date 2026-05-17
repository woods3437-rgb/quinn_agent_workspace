"""Phase 13 — health snapshots + history summary."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .health import HealthService
from .heartbeat import _ensure_aware
from .models import HealthHistorySummary, HealthSnapshot, HealthStatus
from .sqlite_store import SQLiteStore


class HealthHistoryService:
    def __init__(
        self,
        store: SQLiteStore,
        health: HealthService,
        alert_evaluator=None,
    ) -> None:
        self.store = store
        self.health = health
        # Phase 14: optional alert evaluator; runs after snapshot.
        self.alert_evaluator = alert_evaluator

    def snapshot(self) -> HealthSnapshot:
        from .heartbeat import is_stale  # local import to avoid cycle

        report = self.health.build()
        summary = {
            "status": report.status.value,
            "workers": [w.worker_name for w in report.workers],
            "workers_stale": any(is_stale(w) for w in report.workers),
            "recent_failed_jobs": [j.id for j in report.recent_failed_jobs],
            "recent_failed_write_events": [e.id for e in report.recent_failed_write_events],
            "backups_overdue": bool(report.backups.get("overdue")),
            "sqlite_journal_mode": report.sqlite.get("journal_mode"),
        }
        snapshot = HealthSnapshot(status=report.status, summary_json=summary)
        self.store.append_health_snapshot(snapshot)
        # Phase 14: best-effort alert evaluation.
        if self.alert_evaluator is not None:
            try:
                self.alert_evaluator.evaluate()
            except Exception:  # noqa: BLE001
                pass
        return snapshot

    def summary(self) -> HealthHistorySummary:
        snapshots = self.store.list_health_snapshots(limit=1000)
        now = datetime.now(timezone.utc)
        cutoff_24 = now - timedelta(hours=24)
        cutoff_7d = now - timedelta(days=7)

        within_24 = [s for s in snapshots if _ensure_aware(s.created_at) >= cutoff_24]
        within_7d = [s for s in snapshots if _ensure_aware(s.created_at) >= cutoff_7d]
        degraded_24 = [s for s in within_24 if s.status == HealthStatus.degraded]
        degraded_7d = [s for s in within_7d if s.status == HealthStatus.degraded]
        down_7d = [s for s in within_7d if s.status == HealthStatus.down]

        latest_reasons: list[str] = []
        for s in within_24:
            if s.status == HealthStatus.degraded:
                reasons = self._reasons_from(s.summary_json)
                for reason in reasons:
                    if reason not in latest_reasons:
                        latest_reasons.append(reason)
                if len(latest_reasons) >= 5:
                    break

        last_status = snapshots[0].status if snapshots else HealthStatus.ok
        return HealthHistorySummary(
            last_status=last_status,
            sample_count_24h=len(within_24),
            sample_count_7d=len(within_7d),
            degraded_count_24h=len(degraded_24),
            degraded_count_7d=len(degraded_7d),
            down_count_7d=len(down_7d),
            latest_degraded_reasons=latest_reasons[:5],
            recent=snapshots[:30],
        )

    def _reasons_from(self, summary: dict) -> list[str]:
        out: list[str] = []
        if summary.get("recent_failed_jobs"):
            out.append(f"failed_jobs={len(summary['recent_failed_jobs'])}")
        if summary.get("recent_failed_write_events"):
            out.append(f"failed_writes={len(summary['recent_failed_write_events'])}")
        if summary.get("backups_overdue"):
            out.append("backups_overdue")
        return out
