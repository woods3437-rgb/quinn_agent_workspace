"""Phase 9 — notifications (off by default, gated on three checks)."""
from __future__ import annotations

import pytest

from cto_os_api import notifications as notif_module
from cto_os_api.models import NotificationRuleCreate
from cto_os_api.notifications import NotificationService


@pytest.fixture
def webhook_rule(store):
    return store.create_notification_rule(
        NotificationRuleCreate(
            channel="webhook",
            event_type="retrospective_generated",
            destination="https://example.com/hook",
            enabled=True,
        )
    )


def test_disabled_by_default_env_off(store, webhook_rule, monkeypatch):
    monkeypatch.delenv("CTO_OS_ENABLE_NOTIFICATIONS", raising=False)
    calls: list[str] = []
    monkeypatch.setattr(
        notif_module.httpx, "post", lambda *a, **kw: calls.append("posted") or None
    )
    service = NotificationService(store)

    events = service.notify("retrospective_generated", {"hi": 1})
    assert events and events[0].status.value == "skipped"
    assert "CTO_OS_ENABLE_NOTIFICATIONS" in events[0].error_message
    assert calls == []


def test_rule_disabled_skips(store, monkeypatch):
    monkeypatch.setenv("CTO_OS_ENABLE_NOTIFICATIONS", "1")
    rule = store.create_notification_rule(
        NotificationRuleCreate(
            channel="webhook",
            event_type="x",
            destination="https://example.com",
            enabled=False,
        )
    )
    monkeypatch.setattr(notif_module.httpx, "post", lambda *a, **kw: pytest.fail("called"))
    events = NotificationService(store).notify("x", {})
    assert events and events[0].status.value == "skipped"
    assert "disabled" in events[0].error_message.lower()


def test_invalid_destination_skips(store, monkeypatch):
    monkeypatch.setenv("CTO_OS_ENABLE_NOTIFICATIONS", "1")
    rule = store.create_notification_rule(
        NotificationRuleCreate(
            channel="webhook",
            event_type="x",
            destination="http://insecure",  # not HTTPS
            enabled=True,
        )
    )
    events = NotificationService(store).notify("x", {})
    assert events and events[0].status.value == "skipped"
    assert "valid" in events[0].error_message.lower()


def test_enabled_path_posts(store, webhook_rule, monkeypatch):
    monkeypatch.setenv("CTO_OS_ENABLE_NOTIFICATIONS", "1")
    captured = {}

    class _Resp:
        def raise_for_status(self):
            return None

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _Resp()

    monkeypatch.setattr(notif_module.httpx, "post", fake_post)
    events = NotificationService(store).notify(
        "retrospective_generated", {"summary": "ok"}
    )
    assert events and events[0].status.value == "sent"
    assert captured["url"] == "https://example.com/hook"
