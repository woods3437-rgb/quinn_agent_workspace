"""Phase 14 — MCP server pulls session id from params._meta.sessionId."""
from __future__ import annotations

import json

from cto_os_api.mcp_server import MCPServer
from cto_os_api.mcp_tools import MCPToolset
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import ProjectCreate


def test_meta_session_id_threads_into_audit(store, monkeypatch):
    monkeypatch.delenv("CTO_OS_MCP_SESSION_ID", raising=False)
    monkeypatch.delenv("CTO_OS_MCP_READONLY", raising=False)
    project = store.create_project(ProjectCreate(name="MetaS"))
    server = MCPServer(toolset=MCPToolset(store=store, memory_engine=LocalMemoryEngine(store)))
    response = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "create_task",
                "arguments": {"project_id": project.id, "title": "via meta"},
                "_meta": {"sessionId": "claude-code-host-42"},
            },
        }
    )
    assert "result" in response
    audit = store.list_mcp_audit()
    matching = [e for e in audit if e.tool_name == "create_task"]
    assert matching and matching[0].session_id == "claude-code-host-42"


def test_server_version_is_phase14(store):
    from cto_os_api.mcp_server import SERVER_VERSION

    assert SERVER_VERSION == "0.14.0"
