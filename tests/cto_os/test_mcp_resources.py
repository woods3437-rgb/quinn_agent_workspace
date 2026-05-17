"""Phase 11 — MCP resources/list + resources/read."""
from __future__ import annotations

import json

from cto_os_api.mcp_resources import MCPResourceProvider
from cto_os_api.mcp_server import MCPServer
from cto_os_api.mcp_tools import MCPToolset
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import MemoryCreate, ProjectCreate


EXPECTED_STATIC_URIS = {
    "cto-os://projects",
    "cto-os://system/control-room",
    "cto-os://system/shipped",
}

EXPECTED_TEMPLATES = {
    "cto-os://projects/{project_id}/brief",
    "cto-os://projects/{project_id}/source-of-truth",
    "cto-os://projects/{project_id}/recent-activity",
    "cto-os://projects/{project_id}/risks",
    "cto-os://projects/{project_id}/tasks",
    "cto-os://projects/{project_id}/shipped",
}


def _server(store):
    return MCPServer(
        toolset=MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    )


def test_resources_list_returns_static_uris(store):
    response = _server(store).handle(
        {"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}}
    )
    uris = {item["uri"] for item in response["result"]["resources"]}
    missing = EXPECTED_STATIC_URIS - uris
    assert not missing, f"static resources missing: {missing}"


def test_resource_templates_list(store):
    response = _server(store).handle(
        {"jsonrpc": "2.0", "id": 2, "method": "resources/templates/list", "params": {}}
    )
    templates = {item["uriTemplate"] for item in response["result"]["resourceTemplates"]}
    missing = EXPECTED_TEMPLATES - templates
    assert not missing, f"resource templates missing: {missing}"


def test_resources_read_projects(store):
    store.create_project(ProjectCreate(name="P1"))
    server = _server(store)
    response = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "resources/read",
            "params": {"uri": "cto-os://projects"},
        }
    )
    content = response["result"]["contents"][0]
    assert content["mimeType"] == "application/json"
    payload = json.loads(content["text"])
    assert any(item["name"] == "P1" for item in payload)


def test_resources_read_project_source_of_truth(store):
    project = store.create_project(ProjectCreate(name="P2"))
    store.create_memory(
        project.id, MemoryCreate(title="north star", content="never break", pinned=True)
    )
    server = _server(store)
    response = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "resources/read",
            "params": {"uri": f"cto-os://projects/{project.id}/source-of-truth"},
        }
    )
    payload = json.loads(response["result"]["contents"][0]["text"])
    assert any(item["title"] == "north star" for item in payload)


def test_resources_read_invalid_uri_errors(store):
    server = _server(store)
    response = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "resources/read",
            "params": {"uri": "cto-os://nope/at/all"},
        }
    )
    assert "error" in response
    assert "Unknown" in response["error"]["message"]


def test_resource_provider_handles_all_static(store):
    project = store.create_project(ProjectCreate(name="P3"))
    provider = MCPResourceProvider(store, LocalMemoryEngine(store))
    for uri in [
        "cto-os://projects",
        "cto-os://system/control-room",
        "cto-os://system/shipped",
        f"cto-os://projects/{project.id}/brief",
        f"cto-os://projects/{project.id}/recent-activity",
        f"cto-os://projects/{project.id}/risks",
        f"cto-os://projects/{project.id}/tasks",
        f"cto-os://projects/{project.id}/shipped",
    ]:
        contents = provider.read(uri)["contents"][0]
        # Must always be valid JSON.
        json.loads(contents["text"])
