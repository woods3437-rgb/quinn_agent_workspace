"""Phase 11 — regression: new MCP paths must work without OpenAI/Anthropic keys."""
from __future__ import annotations

import json

from cto_os_api.mcp_server import MCPServer
from cto_os_api.mcp_tools import MCPToolset
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import ProjectCreate


def _clear_keys(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("CTO_OS_LLM_PROVIDER", "deterministic")


def test_resources_and_prompts_work_with_no_keys(store, monkeypatch):
    _clear_keys(monkeypatch)
    server = MCPServer(
        toolset=MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    )
    store.create_project(ProjectCreate(name="No-Keys-P11"))

    assert server.handle({"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}})["result"]
    assert server.handle({"jsonrpc": "2.0", "id": 2, "method": "prompts/list", "params": {}})["result"]
    read = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "resources/read",
            "params": {"uri": "cto-os://projects"},
        }
    )
    payload = json.loads(read["result"]["contents"][0]["text"])
    assert any(item["name"] == "No-Keys-P11" for item in payload)


def test_no_github_create_tools_in_safety_report(store, monkeypatch):
    _clear_keys(monkeypatch)
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    report = toolset.call("get_mcp_safety_report")
    assert report["github_writes_in_mcp"] is False
    assert report["shell_in_mcp"] is False
    all_tools = report["read_tools"] + report["write_tools"] + report["preview_tools"]
    assert all(not name.startswith("create_github") for name in all_tools)
