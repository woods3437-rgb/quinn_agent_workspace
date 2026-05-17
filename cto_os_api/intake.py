"""Phase 11 — opt-in webhook intake boundary.

Two-gate kill switch:

1. ``CTO_OS_ENABLE_WEBHOOK_INTAKE=1`` in env
2. The request HMAC matches a non-empty ``CTO_OS_WEBHOOK_SECRET``

Without both, ``/intake/events`` returns an error and persists nothing.
Even with both gates open we **never** trigger an LLM automatically — we
only store the ``IntakeEvent`` and optionally create a single
``StatusSuggestion`` the user can apply or dismiss.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os

from .models import (
    IntakeEvent,
    IntakeEventCreate,
    IntakeSource,
    StatusSuggestion,
    StatusSuggestionEntityType,
)
from .sqlite_store import SQLiteStore


class IntakeDisabledError(RuntimeError):
    """The intake endpoint is disabled (env flag off or secret missing)."""


class IntakeAuthError(RuntimeError):
    """The intake request failed HMAC validation."""


def env_intake_enabled() -> bool:
    return os.getenv("CTO_OS_ENABLE_WEBHOOK_INTAKE", "0").strip() == "1"


def intake_secret() -> str:
    return os.getenv("CTO_OS_WEBHOOK_SECRET", "").strip()


def compute_signature(raw_body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


class IntakeService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def assert_enabled(self) -> None:
        if not env_intake_enabled():
            raise IntakeDisabledError(
                "Intake is disabled; set CTO_OS_ENABLE_WEBHOOK_INTAKE=1."
            )
        if not intake_secret():
            raise IntakeDisabledError(
                "Intake secret missing; set CTO_OS_WEBHOOK_SECRET to a non-empty value."
            )

    def verify_signature(self, raw_body: bytes, provided_signature: str | None) -> None:
        secret = intake_secret()
        expected = compute_signature(raw_body, secret)
        if not provided_signature or not hmac.compare_digest(expected, provided_signature):
            raise IntakeAuthError("Invalid intake signature.")

    def record(
        self,
        payload: IntakeEventCreate,
        *,
        create_suggestion: bool = False,
    ) -> IntakeEvent:
        suggestion_id: str | None = None
        if create_suggestion and payload.project_id:
            suggestion = StatusSuggestion(
                project_id=payload.project_id,
                entity_type=StatusSuggestionEntityType.task,
                entity_id="(intake)",
                suggested_status="triage",
                reason=f"Intake event from {payload.source.value}",
                evidence_json={"source": payload.source.value, "note": payload.note},
            )
            self.store.save_status_suggestion(suggestion)
            suggestion_id = suggestion.id
        event = IntakeEvent(
            source=payload.source,
            project_id=payload.project_id,
            payload=payload.payload,
            note=payload.note,
            suggestion_id=suggestion_id,
        )
        return self.store.save_intake_event(event)

    def list_events(self, limit: int = 100) -> list[IntakeEvent]:
        return self.store.list_intake_events(limit=limit)


_VALID_SOURCES = {member.value for member in IntakeSource}


def parse_intake_body(raw_body: bytes) -> IntakeEventCreate:
    try:
        body = json.loads(raw_body or b"{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}")
    source = body.get("source")
    if source not in _VALID_SOURCES:
        raise ValueError(
            f"source must be one of {sorted(_VALID_SOURCES)} (got {source!r})"
        )
    return IntakeEventCreate(
        source=IntakeSource(source),
        project_id=body.get("project_id"),
        payload=body.get("payload") or {},
        note=body.get("note") or "",
    )
