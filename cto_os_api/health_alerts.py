"""Phase 14 — health alert rule evaluation.

Rules are evaluated against recent ``HealthSnapshot`` rows. When a rule
triggers we call ``NotificationService.notify`` with a stable event_type
(``health.alert.<name>``). The Phase 9 three-gate model still applies —
without env + an enabled rule, the notification event lands as
``skipped``.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .heartbeat import _ensure_aware
from .models import (
    HealthAlertConditionType,
    HealthAlertEvaluation,
    HealthAlertRule,
    HealthStatus,
)
from .notifications import NotificationService
from .sqlite_store import SQLiteStore


class HealthAlertEvaluator:
    def __init__(self, store: SQLiteStore, notifier: NotificationService) -> None:
        self.store = store
        self.notifier = notifier

    def evaluate(self) -> list[HealthAlertEvaluation]:
        results: list[HealthAlertEvaluation] = []
        rules = [r for r in self.store.list_health_alert_rules() if r.enabled]
        if not rules:
            return results
        snapshots = self.store.list_health_snapshots(limit=500)
        latest = snapshots[0] if snapshots else None
        for rule in rules:
            triggered, reason = self._check(rule, snapshots, latest)
            ids: list[str] = []
            if triggered:
                events = self.notifier.notify(
                    event_type=f"health.alert.{rule.name}",
                    payload={
                        "rule_id": rule.id,
                        "condition_type": rule.condition_type.value,
                        "threshold": rule.threshold,
                        "reason": reason,
                    },
                )
                ids = [event.id for event in events]
            results.append(
                HealthAlertEvaluation(
                    rule_id=rule.id,
                    triggered=triggered,
                    reason=reason,
                    notification_event_ids=ids,
                )
            )
        return results

    def _check(
        self,
        rule: HealthAlertRule,
        snapshots: list,
        latest,
    ) -> tuple[bool, str]:
        if rule.condition_type == HealthAlertConditionType.degraded_samples:
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(minutes=max(rule.window_minutes, 1))
            count = sum(
                1
                for s in snapshots
                if s.status == HealthStatus.degraded
                and _ensure_aware(s.created_at) >= cutoff
            )
            if count >= rule.threshold:
                return True, f"{count} degraded samples in last {rule.window_minutes} min"
            return False, ""
        if rule.condition_type == HealthAlertConditionType.failed_jobs:
            if latest is None:
                return False, "no health snapshots"
            failed = latest.summary_json.get("recent_failed_jobs") or []
            if len(failed) >= rule.threshold:
                return True, f"{len(failed)} failed jobs in latest snapshot"
            return False, ""
        if rule.condition_type == HealthAlertConditionType.backup_overdue:
            if latest is None:
                return False, "no health snapshots"
            if bool(latest.summary_json.get("backups_overdue")):
                return True, "backups are overdue"
            return False, ""
        if rule.condition_type == HealthAlertConditionType.worker_stale:
            if latest is None:
                return False, "no health snapshots"
            if bool(latest.summary_json.get("workers_stale")):
                return True, "worker heartbeats are stale"
            return False, ""
        return False, ""
