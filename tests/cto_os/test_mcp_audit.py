"""Phase 13 — MCP write audit (append-only, summary-only)."""
from __future__ import annotations

from cto_os_api.mcp_tools import MCPToolset
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import ProjectCreate


def test_write_tool_creates_audit_row(store, monkeypatch):
    monkeypatch.delenv("CTO_OS_MCP_READONLY", raising=False)
    project = store.create_project(ProjectCreate(name="P"))
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))

    toolset.call("create_task", {"project_id": project.id, "title": "audit me"})

    audit = store.list_mcp_audit()
    assert any(
        ev.tool_name == "create_task" and ev.project_id == project.id and not ev.blocked
        for ev in audit
    )


def test_readonly_blocked_attempt_is_audited(store, monkeypatch):
    monkeypatch.setenv("CTO_OS_MCP_READONLY", "1")
    project = store.create_project(ProjectCreate(name="ROaudit"))
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))

    result = toolset.call(
        "save_project_memory",
        {"project_id": project.id, "title": "blocked", "content": "x"},
    )
    assert isinstance(result, dict) and result.get("blocked") is True

    audit = store.list_mcp_audit()
    blocked_rows = [ev for ev in audit if ev.tool_name == "save_project_memory"]
    assert blocked_rows
    assert blocked_rows[0].blocked is True
    assert blocked_rows[0].readonly_mode is True
    # The memory itself must not have been written.
    assert not store.list_memories(project_id=project.id)


def test_audit_summary_does_not_contain_values(store, monkeypatch):
    monkeypatch.delenv("CTO_OS_MCP_READONLY", raising=False)
    project = store.create_project(ProjectCreate(name="Psecret"))
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))

    secret_value = "very-secret-do-not-store"
    toolset.call(
        "save_project_memory",
        {"project_id": project.id, "title": secret_value, "content": secret_value},
    )

    audit = store.list_mcp_audit()
    for ev in audit:
        assert secret_value not in ev.request_summary
        assert secret_value not in ev.response_summary


def test_per_project_audit_listing(store, monkeypatch):
    monkeypatch.delenv("CTO_OS_MCP_READONLY", raising=False)
    p1 = store.create_project(ProjectCreate(name="A"))
    p2 = store.create_project(ProjectCreate(name="B"))
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    toolset.call("create_task", {"project_id": p1.id, "title": "a"})
    toolset.call("create_task", {"project_id": p2.id, "title": "b"})

    audit_a = store.list_mcp_audit(project_id=p1.id)
    audit_b = store.list_mcp_audit(project_id=p2.id)
    assert all(ev.project_id == p1.id for ev in audit_a)
    assert all(ev.project_id == p2.id for ev in audit_b)
