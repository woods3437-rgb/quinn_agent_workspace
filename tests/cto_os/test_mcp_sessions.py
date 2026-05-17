"""Phase 14 — MCP session identity + revoke/readonly gates."""
from __future__ import annotations

from cto_os_api.mcp_sessions import MCPSessionResolver, resolve_session_id
from cto_os_api.mcp_tools import MCPToolset
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import MCPSessionUpdate, ProjectCreate


def test_resolve_session_id_precedence(monkeypatch):
    assert resolve_session_id({"_session_id": "host-id"}) == "host-id"
    monkeypatch.delenv("CTO_OS_MCP_SESSION_ID", raising=False)
    assert resolve_session_id({}) == "unknown"
    monkeypatch.setenv("CTO_OS_MCP_SESSION_ID", "env-id")
    assert resolve_session_id({}) == "env-id"


def test_touch_auto_creates_and_updates_last_seen(store):
    resolver = MCPSessionResolver(store)
    first = resolver.touch("alice")
    assert first.session_id == "alice"
    second = resolver.touch("alice")
    assert second.id == first.id
    assert second.last_seen_at >= first.last_seen_at


def test_call_records_session_id_in_audit(store, monkeypatch):
    monkeypatch.delenv("CTO_OS_MCP_READONLY", raising=False)
    monkeypatch.delenv("CTO_OS_MCP_SESSION_ID", raising=False)
    project = store.create_project(ProjectCreate(name="SessAud"))
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    toolset.call(
        "create_task",
        {"project_id": project.id, "title": "session-id", "_session_id": "bob"},
    )
    audit = store.list_mcp_audit()
    matching = [e for e in audit if e.tool_name == "create_task"]
    assert matching
    assert matching[0].session_id == "bob"
    # _session_id should not appear in the persisted summary.
    assert "_session_id" not in matching[0].request_summary


def test_revoked_session_blocks_all_tools(store, monkeypatch):
    monkeypatch.delenv("CTO_OS_MCP_READONLY", raising=False)
    project = store.create_project(ProjectCreate(name="RevS"))
    resolver = MCPSessionResolver(store)
    resolver.touch("revoked-one")
    store.update_mcp_session("revoked-one", MCPSessionUpdate(revoked=True))
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))

    # Write tool is blocked.
    write_result = toolset.call(
        "create_task",
        {"project_id": project.id, "title": "nope", "_session_id": "revoked-one"},
    )
    assert isinstance(write_result, dict) and write_result.get("blocked") is True
    assert "revoked" in write_result.get("reason", "")

    # Read tool is also blocked for revoked sessions.
    read_result = toolset.call("list_projects", {"_session_id": "revoked-one"})
    assert isinstance(read_result, dict) and read_result.get("blocked") is True


def test_readonly_session_blocks_only_writes(store, monkeypatch):
    monkeypatch.delenv("CTO_OS_MCP_READONLY", raising=False)
    project = store.create_project(ProjectCreate(name="RoSes"))
    resolver = MCPSessionResolver(store)
    resolver.touch("ro-one")
    store.update_mcp_session("ro-one", MCPSessionUpdate(readonly=True))
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))

    # Write is blocked with session-readonly reason.
    write_result = toolset.call(
        "create_task",
        {"project_id": project.id, "title": "no", "_session_id": "ro-one"},
    )
    assert isinstance(write_result, dict) and write_result.get("blocked") is True
    assert "read-only" in write_result.get("reason", "")

    # Read works.
    out = toolset.call("list_projects", {"_session_id": "ro-one"})
    assert isinstance(out, list)
