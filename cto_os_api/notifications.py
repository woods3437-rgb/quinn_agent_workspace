"""Phase 9 — gated notification boundary.

Three-gate model:
1. ``CTO_OS_ENABLE_NOTIFICATIONS=1`` in env (process kill-switch)
2. The rule's ``enabled`` flag is True
3. ``destination`` validates per channel (HTTPS-only for webhook-likes, email
   regex for email)

Without all three, ``notify`` writes a ``NotificationEvent(status=skipped)``
and returns. No outbound HTTP. No email send. Test endpoint follows the same
gate.
"""
from __future__ import annotations

import os
import re
from typing import Any

import httpx

from .models import (
    NotificationChannel,
    NotificationEvent,
    NotificationRule,
    NotificationStatus,
)
from .sqlite_store import SQLiteStore


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def env_notifications_enabled() -> bool:
    return os.getenv("CTO_OS_ENABLE_NOTIFICATIONS", "0").strip() == "1"


def _destination_valid(rule: NotificationRule) -> bool:
    dest = (rule.destination or "").strip()
    if not dest:
        return False
    if rule.channel == NotificationChannel.email:
        return bool(_EMAIL_RE.match(dest))
    return dest.startswith("https://")


class NotificationService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def notify(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        project_id: str | None = None,
    ) -> list[NotificationEvent]:
        rules = [
            rule
            for rule in self.store.list_notification_rules()
            if rule.event_type == event_type
            and (rule.project_id is None or rule.project_id == project_id)
        ]
        events: list[NotificationEvent] = []
        for rule in rules:
            events.append(self._deliver(rule, event_type, payload, project_id))
        return events

    def test(self, rule_id: str, payload: dict[str, Any]) -> NotificationEvent:
        rule = self.store.get_notification_rule(rule_id)
        return self._deliver(rule, "test", payload or {"hello": "from cto_os"}, rule.project_id)

    def _deliver(
        self,
        rule: NotificationRule,
        event_type: str,
        payload: dict[str, Any],
        project_id: str | None,
    ) -> NotificationEvent:
        gate_reason = self._gate_reason(rule)
        if gate_reason is not None:
            event = NotificationEvent(
                project_id=project_id,
                rule_id=rule.id,
                event_type=event_type,
                payload_json=payload,
                status=NotificationStatus.skipped,
                error_message=gate_reason,
            )
            return self.store.save_notification_event(event)
        try:
            self._send(rule, payload)
            status = NotificationStatus.sent
            error_message = ""
        except Exception as exc:
            status = NotificationStatus.failed
            error_message = str(exc)
        event = NotificationEvent(
            project_id=project_id,
            rule_id=rule.id,
            event_type=event_type,
            payload_json=payload,
            status=status,
            error_message=error_message,
        )
        return self.store.save_notification_event(event)

    def _gate_reason(self, rule: NotificationRule) -> str | None:
        if not env_notifications_enabled():
            return "CTO_OS_ENABLE_NOTIFICATIONS is not 1; not sending."
        if not rule.enabled:
            return "Rule is disabled; not sending."
        if not _destination_valid(rule):
            return (
                f"Destination is not valid for channel {rule.channel.value}; "
                "must be HTTPS or a valid email."
            )
        return None

    def _send(self, rule: NotificationRule, payload: dict[str, Any]) -> None:
        if rule.channel in {
            NotificationChannel.webhook,
            NotificationChannel.slack,
            NotificationChannel.discord,
        }:
            response = httpx.post(rule.destination, json=payload, timeout=15)
            response.raise_for_status()
            return
        # email: Phase 9 only validates the address; actual SMTP is out of scope.
        raise RuntimeError(
            "Email channel is recognised but SMTP delivery is not configured in Phase 9."
        )
