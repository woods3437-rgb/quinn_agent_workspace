"""Phase 14 — HMAC audit signing + verify + tamper detection."""
from __future__ import annotations

from cto_os_api.audit_signing import canonical_payload, sign, signing_key_id, verify
from cto_os_api.mcp_tools import MCPToolset
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import MCPAuditEvent, ProjectCreate


def test_unsigned_when_key_missing(monkeypatch):
    monkeypatch.delenv("CTO_OS_AUDIT_SIGNING_KEY", raising=False)
    event = MCPAuditEvent(tool_name="x")
    signature, key_id = sign(event)
    assert signature == ""
    assert key_id == ""
    assert verify(event) == "unsigned"


def test_signed_event_verifies(monkeypatch):
    monkeypatch.setenv("CTO_OS_AUDIT_SIGNING_KEY", "secret-key-1")
    event = MCPAuditEvent(tool_name="create_task", session_id="alice")
    signature, key_id = sign(event)
    assert signature.startswith("sha256=")
    assert key_id == signing_key_id("secret-key-1")
    event.signature = signature
    event.signing_key_id = key_id
    assert verify(event) == "valid"


def test_tampered_field_detected(monkeypatch):
    monkeypatch.setenv("CTO_OS_AUDIT_SIGNING_KEY", "secret-key-1")
    event = MCPAuditEvent(tool_name="create_task", session_id="alice")
    sig, key_id = sign(event)
    event.signature = sig
    event.signing_key_id = key_id
    # Tamper.
    event.tool_name = "delete_everything"
    assert verify(event) == "tampered"


def test_key_missing_after_signing(monkeypatch):
    monkeypatch.setenv("CTO_OS_AUDIT_SIGNING_KEY", "secret-key-1")
    event = MCPAuditEvent(tool_name="x")
    sig, _ = sign(event)
    event.signature = sig
    monkeypatch.delenv("CTO_OS_AUDIT_SIGNING_KEY", raising=False)
    assert verify(event) == "key_missing"


def test_canonical_payload_is_stable():
    event = MCPAuditEvent(
        tool_name="create_task",
        session_id="alice",
        project_id="proj_x",
        request_summary='{"a":1}',
        response_summary='{"b":2}',
    )
    a = canonical_payload(event)
    b = canonical_payload(event)
    assert a == b
    assert '"tool_name":"create_task"' in a


def test_tool_call_persists_signature_when_key_set(store, monkeypatch):
    monkeypatch.delenv("CTO_OS_MCP_READONLY", raising=False)
    monkeypatch.setenv("CTO_OS_AUDIT_SIGNING_KEY", "deadbeef")
    project = store.create_project(ProjectCreate(name="SignP"))
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    toolset.call("create_task", {"project_id": project.id, "title": "sign me"})
    audit = store.list_mcp_audit()
    matching = [e for e in audit if e.tool_name == "create_task"]
    assert matching
    assert matching[0].signature.startswith("sha256=")
    assert verify(matching[0]) == "valid"
