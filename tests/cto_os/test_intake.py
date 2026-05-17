"""Phase 11 — webhook intake (disabled by default, HMAC-validated)."""
from __future__ import annotations

import json

import pytest

from cto_os_api.intake import (
    IntakeAuthError,
    IntakeDisabledError,
    IntakeService,
    compute_signature,
    parse_intake_body,
)


def test_disabled_by_default(store, monkeypatch):
    monkeypatch.delenv("CTO_OS_ENABLE_WEBHOOK_INTAKE", raising=False)
    service = IntakeService(store)
    with pytest.raises(IntakeDisabledError):
        service.assert_enabled()


def test_disabled_when_secret_missing(store, monkeypatch):
    monkeypatch.setenv("CTO_OS_ENABLE_WEBHOOK_INTAKE", "1")
    monkeypatch.delenv("CTO_OS_WEBHOOK_SECRET", raising=False)
    with pytest.raises(IntakeDisabledError):
        IntakeService(store).assert_enabled()


def test_invalid_signature_rejected(store, monkeypatch):
    monkeypatch.setenv("CTO_OS_ENABLE_WEBHOOK_INTAKE", "1")
    monkeypatch.setenv("CTO_OS_WEBHOOK_SECRET", "shh")
    body = json.dumps({"source": "manual.note", "note": "hi"}).encode()
    service = IntakeService(store)
    service.assert_enabled()
    with pytest.raises(IntakeAuthError):
        service.verify_signature(body, "sha256=deadbeef")


def test_valid_signature_records_event(store, monkeypatch):
    monkeypatch.setenv("CTO_OS_ENABLE_WEBHOOK_INTAKE", "1")
    monkeypatch.setenv("CTO_OS_WEBHOOK_SECRET", "shh")
    body = json.dumps({"source": "manual.note", "note": "hi", "payload": {"k": 1}}).encode()
    sig = compute_signature(body, "shh")
    service = IntakeService(store)
    service.assert_enabled()
    service.verify_signature(body, sig)
    event = service.record(parse_intake_body(body))
    persisted = store.list_intake_events()
    assert any(item.id == event.id for item in persisted)


def test_parse_rejects_unknown_source():
    with pytest.raises(ValueError, match="source must be"):
        parse_intake_body(json.dumps({"source": "linkedin.post"}).encode())


def test_create_suggestion_flag(store, monkeypatch):
    from cto_os_api.models import ProjectCreate

    monkeypatch.setenv("CTO_OS_ENABLE_WEBHOOK_INTAKE", "1")
    monkeypatch.setenv("CTO_OS_WEBHOOK_SECRET", "shh")
    project = store.create_project(ProjectCreate(name="X"))
    body = json.dumps(
        {
            "source": "sentry.issue.created",
            "project_id": project.id,
            "note": "boom",
            "payload": {"issue_id": "x"},
        }
    ).encode()
    payload = parse_intake_body(body)
    event = IntakeService(store).record(payload, create_suggestion=True)
    assert event.suggestion_id
    suggestions = store.list_status_suggestions(project.id)
    assert any(s.id == event.suggestion_id for s in suggestions)
