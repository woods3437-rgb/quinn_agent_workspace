"""Phase 12 — MCP read-only mode + notifications drain."""
from __future__ import annotations

import json

from cto_os_api.mcp_server import MCPServer
from cto_os_api.mcp_tools import MCPToolset, mcp_readonly_enabled
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import ProjectCreate


def test_readonly_blocks_write_tools(store, monkeypatch):
    monkeypatch.setenv("CTO_OS_MCP_READONLY", "1")
    assert mcp_readonly_enabled() is True
    project = store.create_project(ProjectCreate(name="RO"))
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))

    result = toolset.call(
        "create_task",
        {"project_id": project.id, "title": "should not be created"},
    )
    assert isinstance(result, dict)
    assert result.get("blocked") is True
    assert result.get("isError") is True
    assert result.get("tool") == "create_task"
    assert not any(t.title == "should not be created" for t in store.list_tasks(project.id))


def test_readonly_allows_read_tools(store, monkeypatch):
    monkeypatch.setenv("CTO_OS_MCP_READONLY", "1")
    project = store.create_project(ProjectCreate(name="ROread"))
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    out = toolset.call("list_projects")
    assert any(item["id"] == project.id for item in out)


def test_readonly_reflected_in_safety_report(store, monkeypatch):
    monkeypatch.setenv("CTO_OS_MCP_READONLY", "1")
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    report = toolset.call("get_mcp_safety_report")
    assert report["read_only_mode"] is True


def test_mcp_server_emits_notifications_after_write(store, monkeypatch):
    monkeypatch.delenv("CTO_OS_MCP_READONLY", raising=False)
    project = store.create_project(ProjectCreate(name="NotifyP"))
    server = MCPServer(toolset=MCPToolset(store=store, memory_engine=LocalMemoryEngine(store)))
    server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    server.handle(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "create_task",
                "arguments": {"project_id": project.id, "title": "notify me"},
            },
        }
    )
    notifications = server.drain_notifications()
    assert notifications
    methods = {n["method"] for n in notifications}
    assert "notifications/resources/updated" in methods
    uris = {n["params"]["uri"] for n in notifications}
    assert f"cto-os://projects/{project.id}/tasks" in uris
    # second drain returns nothing
    assert server.drain_notifications() == []


def test_readonly_does_not_emit_notifications(store, monkeypatch):
    monkeypatch.setenv("CTO_OS_MCP_READONLY", "1")
    project = store.create_project(ProjectCreate(name="ROnotify"))
    server = MCPServer(toolset=MCPToolset(store=store, memory_engine=LocalMemoryEngine(store)))
    server.handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "save_project_memory",
                "arguments": {
                    "project_id": project.id,
                    "title": "blocked",
                    "content": "blocked",
                },
            },
        }
    )
    assert server.drain_notifications() == []
