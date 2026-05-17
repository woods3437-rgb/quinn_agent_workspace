"""Phase 14 — HMAC-SHA256 audit row signing.

When ``CTO_OS_AUDIT_SIGNING_KEY`` is set, every persisted ``MCPAuditEvent``
carries an HMAC over a canonical JSON of its stable fields. A verify
endpoint recomputes and compares; tampering with any signed field flips
the verification status to ``tampered``.

If the key is missing, signatures stay empty and the verify report
flags the row as ``unsigned``.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime

from .models import MCPAuditEvent


_SIGNED_FIELDS = (
    "id",
    "session_id",
    "tool_name",
    "project_id",
    "action_type",
    "request_summary",
    "response_summary",
    "blocked",
    "readonly_mode",
    "created_at",
)


def _iso(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def canonical_payload(event: MCPAuditEvent) -> str:
    dump = event.model_dump(mode="json")
    payload = {field: _iso(dump.get(field)) for field in _SIGNED_FIELDS}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def signing_key() -> str:
    return (os.getenv("CTO_OS_AUDIT_SIGNING_KEY") or "").strip()


def signing_key_id(key: str | None = None) -> str:
    key = key if key is not None else signing_key()
    if not key:
        return ""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def sign(event: MCPAuditEvent, key: str | None = None) -> tuple[str, str]:
    key = key if key is not None else signing_key()
    if not key:
        return "", ""
    digest = hmac.new(
        key.encode("utf-8"),
        canonical_payload(event).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}", signing_key_id(key)


def verify(event: MCPAuditEvent, key: str | None = None) -> str:
    """Return one of: ``unsigned`` | ``valid`` | ``tampered`` | ``key_missing``."""
    if not event.signature:
        return "unsigned"
    key = key if key is not None else signing_key()
    if not key:
        return "key_missing"
    expected, _ = sign(event, key=key)
    return "valid" if hmac.compare_digest(expected, event.signature) else "tampered"
