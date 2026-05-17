"""Phase 10 — MCP mode must work without OpenAI/Anthropic keys set.

The whole point of the MCP layer is to let Claude Code be the model. CTO OS
must not depend on having an API key in env for the MCP code paths to work.
"""
from __future__ import annotations

import json

from cto_os_api.mcp_server import MCPServer
from cto_os_api.mcp_tools import MCPToolset
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import ProjectCreate, TaskCreate


def _clear_keys(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("CTO_OS_LLM_PROVIDER", "deterministic")


def test_mcp_initialize_and_tools_list_without_keys(store, monkeypatch):
    _clear_keys(monkeypatch)
    server = MCPServer(toolset=MCPToolset(store=store, memory_engine=LocalMemoryEngine(store)))

    init = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init["result"]["serverInfo"]["name"] == "cto-os"

    listing = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    assert any(tool["name"] == "list_projects" for tool in listing["result"]["tools"])


def test_full_workflow_with_no_keys(store, monkeypatch):
    """Create project, create task, generate context bundle, save result — all
    without any LLM API key configured."""
    _clear_keys(monkeypatch)
    server = MCPServer(toolset=MCPToolset(store=store, memory_engine=LocalMemoryEngine(store)))

    project = store.create_project(ProjectCreate(name="No-Keys"))
    task = store.create_task(project.id, TaskCreate(title="ship without keys"))

    bundle_resp = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "review_diff_context",
                "arguments": {
                    "project_id": project.id,
                    "diff_text": "+ const x = 1;",
                    "task_id": task.id,
                },
            },
        }
    )
    text = bundle_resp["result"]["content"][0]["text"]
    bundle = json.loads(text)
    assert bundle["kind"] == "code_review"

    save_resp = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "save_code_review_result",
                "arguments": {
                    "project_id": project.id,
                    "diff_text": "+ const x = 1;",
                    "task_id": task.id,
                    "recommendation": "approve",
                    "summary": "lgtm",
                },
            },
        }
    )
    saved = json.loads(save_resp["result"]["content"][0]["text"])
    assert saved["approval_recommendation"] == "approve"


def test_unknown_method_returns_jsonrpc_error(store, monkeypatch):
    _clear_keys(monkeypatch)
    server = MCPServer(toolset=MCPToolset(store=store, memory_engine=LocalMemoryEngine(store)))
    response = server.handle({"jsonrpc": "2.0", "id": 99, "method": "no/such/method"})
    assert "error" in response
    assert response["error"]["code"] == -32601
