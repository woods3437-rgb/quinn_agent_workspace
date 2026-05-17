"""Phase 13 — resource change log + list_changed_resources MCP tool."""
from __future__ import annotations

import time

from cto_os_api.mcp_tools import MCPToolset
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import ProjectCreate


def test_write_records_resource_change(store, monkeypatch):
    monkeypatch.delenv("CTO_OS_MCP_READONLY", raising=False)
    project = store.create_project(ProjectCreate(name="Rc"))
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))

    toolset.call("create_task", {"project_id": project.id, "title": "tracked"})

    events = store.list_resource_changes()
    uris = {e.uri for e in events}
    assert f"cto-os://projects/{project.id}/tasks" in uris
    assert "cto-os://system/control-room" in uris


def test_list_changed_resources_tool_filters_by_since(store, monkeypatch):
    monkeypatch.delenv("CTO_OS_MCP_READONLY", raising=False)
    project = store.create_project(ProjectCreate(name="Rc2"))
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))

    toolset.call("create_task", {"project_id": project.id, "title": "first"})
    time.sleep(0.01)
    cutoff = store.list_resource_changes()[-1].created_at  # ascending? list returns newest first
    cutoff_iso = cutoff.isoformat()
    time.sleep(0.01)
    toolset.call("create_task", {"project_id": project.id, "title": "second"})

    result = toolset.call("list_changed_resources", {"since": cutoff_iso})
    assert isinstance(result, list)
    # Every returned event happens strictly after the cutoff.
    assert all(item["created_at"] > cutoff_iso for item in result)


def test_readonly_blocked_write_does_not_record_change(store, monkeypatch):
    monkeypatch.setenv("CTO_OS_MCP_READONLY", "1")
    project = store.create_project(ProjectCreate(name="Rro"))
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    before = len(store.list_resource_changes())
    toolset.call("create_task", {"project_id": project.id, "title": "blocked"})
    after = len(store.list_resource_changes())
    assert after == before
