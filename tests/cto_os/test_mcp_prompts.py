"""Phase 11 — MCP prompts/list + prompts/get."""
from __future__ import annotations

import pytest

from cto_os_api.mcp_prompts import MCPPromptRegistry
from cto_os_api.mcp_server import MCPServer
from cto_os_api.mcp_tools import MCPToolset
from cto_os_api.memory_engine import LocalMemoryEngine


EXPECTED_PROMPT_NAMES = {
    "cto_os_start_task",
    "cto_os_review_diff",
    "cto_os_retrospective",
    "cto_os_weekly_review",
    "cto_os_save_lesson",
    "cto_os_generate_build_packet",
}


def _server(store):
    return MCPServer(
        toolset=MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    )


def test_prompts_list_returns_expected(store):
    response = _server(store).handle(
        {"jsonrpc": "2.0", "id": 1, "method": "prompts/list", "params": {}}
    )
    names = {item["name"] for item in response["result"]["prompts"]}
    missing = EXPECTED_PROMPT_NAMES - names
    assert not missing, f"prompts missing: {missing}"


def test_prompts_get_review_diff_interpolates(store):
    response = _server(store).handle(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "prompts/get",
            "params": {
                "name": "cto_os_review_diff",
                "arguments": {
                    "project_id": "proj_abc",
                    "diff": "+ const x = 1;",
                },
            },
        }
    )
    messages = response["result"]["messages"]
    user_text = next(msg["content"]["text"] for msg in messages if msg["role"] == "user")
    assert "proj_abc" in user_text
    assert "+ const x = 1;" in user_text


def test_prompts_get_missing_required_arg_errors(store):
    response = _server(store).handle(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "prompts/get",
            "params": {"name": "cto_os_review_diff", "arguments": {"project_id": "x"}},
        }
    )
    assert "error" in response
    assert "diff" in response["error"]["message"]


def test_registry_get_unknown_raises():
    registry = MCPPromptRegistry()
    with pytest.raises(KeyError):
        registry.get("nope")
