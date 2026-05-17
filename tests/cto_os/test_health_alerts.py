"""Phase 14 — health alert evaluator + notification handoff."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cto_os_api.health_alerts import HealthAlertEvaluator
from cto_os_api.models import (
    HealthAlertConditionType,
    HealthAlertRuleCreate,
    HealthSnapshot,
    HealthStatus,
    NotificationRuleCreate,
)
from cto_os_api.notifications import NotificationService


def _seed_degraded(store, count: int, *, hours_ago: int = 0):
    for _ in range(count):
        snap = HealthSnapshot(status=HealthStatus.degraded)
        snap.created_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        store.append_health_snapshot(snap)


def test_degraded_samples_triggers(store):
    _seed_degraded(store, 3)
    store.create_health_alert_rule(
        HealthAlertRuleCreate(
            name="too_many_degraded",
            enabled=True,
            condition_type=HealthAlertConditionType.degraded_samples,
            threshold=2,
            window_minutes=60,
        )
    )
    notifier = NotificationService(store)
    results = HealthAlertEvaluator(store, notifier).evaluate()
    assert any(r.triggered for r in results)


def test_disabled_rule_not_evaluated(store):
    _seed_degraded(store, 5)
    store.create_health_alert_rule(
        HealthAlertRuleCreate(
            name="off_rule",
            enabled=False,
            condition_type=HealthAlertConditionType.degraded_samples,
            threshold=1,
        )
    )
    notifier = NotificationService(store)
    results = HealthAlertEvaluator(store, notifier).evaluate()
    assert results == []


def test_backup_overdue_triggers_from_latest_snapshot(store):
    snap = HealthSnapshot(status=HealthStatus.degraded, summary_json={"backups_overdue": True})
    store.append_health_snapshot(snap)
    store.create_health_alert_rule(
        HealthAlertRuleCreate(
            name="backups",
            enabled=True,
            condition_type=HealthAlertConditionType.backup_overdue,
            threshold=1,
        )
    )
    results = HealthAlertEvaluator(store, NotificationService(store)).evaluate()
    assert any(r.triggered for r in results)


def test_notification_event_recorded_even_when_skipped(store, monkeypatch):
    monkeypatch.delenv("CTO_OS_ENABLE_NOTIFICATIONS", raising=False)
    rule_record = store.create_notification_rule(
        NotificationRuleCreate(
            channel="webhook",
            event_type="health.alert.too_many_degraded",
            destination="https://example.com",
            enabled=True,
        )
    )
    _seed_degraded(store, 3)
    store.create_health_alert_rule(
        HealthAlertRuleCreate(
            name="too_many_degraded",
            enabled=True,
            condition_type=HealthAlertConditionType.degraded_samples,
            threshold=2,
            window_minutes=60,
            notification_rule_id=rule_record.id,
        )
    )
    results = HealthAlertEvaluator(store, NotificationService(store)).evaluate()
    triggered = [r for r in results if r.triggered]
    assert triggered
    event_ids = triggered[0].notification_event_ids
    assert event_ids
    events = store.list_notification_events()
    assert any(e.id in event_ids and e.status.value == "skipped" for e in events)
