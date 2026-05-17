"""Phase 10 — CTO OS MCP server (stdio JSON-RPC).

Run with:

    python -m cto_os_api.mcp_server

Then point your MCP client (Claude Code, Cowork, Claude Desktop) at this
process via stdio. No ANTHROPIC_API_KEY is required for this mode — Claude
Code provides the reasoning layer; CTO OS provides tools + memory + state.

Protocol: JSON-RPC 2.0 over stdio, one message per line, UTF-8.
Implements the subset of MCP host->server methods most clients call:

- ``initialize`` — return server capabilities
- ``initialized`` (notification) — acknowledge
- ``tools/list`` — enumerate registered tools
- ``tools/call`` — invoke a tool by name with arguments
- ``resources/list`` / ``prompts/list`` — empty stubs (we don't expose
  resources or prompts in this phase)
- ``ping`` — heartbeat

Anything else returns a method-not-found error.
"""
from __future__ import annotations

import json
import logging
import sys
import traceback
from typing import Any, Iterable

from .mcp_prompts import MCPPromptRegistry
from .mcp_resources import MCPResourceProvider
from .mcp_tools import MCPToolset


PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "cto-os"
SERVER_VERSION = "0.14.0"

logger = logging.getLogger("cto_os.mcp")


class MCPServer:
    def __init__(
        self,
        toolset: MCPToolset | None = None,
        resources: MCPResourceProvider | None = None,
        prompts: MCPPromptRegistry | None = None,
    ) -> None:
        self.toolset = toolset or MCPToolset()
        self.resources = resources or MCPResourceProvider(
            self.toolset.store, self.toolset.memory_engine
        )
        self.prompts = prompts or MCPPromptRegistry()

    # --------------------------------------------------------------- dispatch

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        method = request.get("method")
        request_id = request.get("id")
        params = request.get("params") or {}

        # Notifications carry no id and never get a response.
        is_notification = "id" not in request

        try:
            if method == "initialize":
                result = self._on_initialize(params)
            elif method == "initialized" or method == "notifications/initialized":
                # Acknowledgement notification from the client; no response.
                return None
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = self._on_tools_list()
            elif method == "tools/call":
                result = self._on_tools_call(params)
            elif method == "resources/list":
                result = self._on_resources_list()
            elif method == "resources/templates/list":
                result = self._on_resource_templates_list()
            elif method == "resources/read":
                result = self._on_resources_read(params)
            elif method == "prompts/list":
                result = self._on_prompts_list()
            elif method == "prompts/get":
                result = self._on_prompts_get(params)
            elif method == "shutdown":
                result = {}
            else:
                if is_notification:
                    return None
                return self._error(request_id, -32601, f"Method not found: {method}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("MCP handler failed: %s", method)
            if is_notification:
                return None
            return self._error(request_id, -32000, str(exc), data={"traceback": traceback.format_exc()})

        if is_notification:
            return None
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    # ------------------------------------------------------------- handlers

    def _on_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        # We ignore the client's requested protocolVersion and return ours; MCP
        # clients negotiate gracefully.
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"listChanged": False, "subscribe": False},
                "prompts": {"listChanged": False},
                "logging": {},
            },
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }

    def _on_tools_list(self) -> dict[str, Any]:
        return {
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.input_schema,
                }
                for tool in self.toolset.tools()
            ]
        }

    def _on_resources_list(self) -> dict[str, Any]:
        return {
            "resources": [
                {
                    "uri": resource.uri,
                    "name": resource.name,
                    "description": resource.description,
                    "mimeType": resource.mime_type,
                }
                for resource in self.resources.static_resources()
            ]
        }

    def _on_resource_templates_list(self) -> dict[str, Any]:
        return {
            "resourceTemplates": [
                {
                    "uriTemplate": template.uri_template,
                    "name": template.name,
                    "description": template.description,
                    "mimeType": template.mime_type,
                }
                for template in self.resources.resource_templates()
            ]
        }

    def _on_resources_read(self, params: dict[str, Any]) -> dict[str, Any]:
        uri = params.get("uri")
        if not isinstance(uri, str) or not uri:
            raise ValueError("resources/read requires a string 'uri'.")
        try:
            return self.resources.read(uri)
        except KeyError as exc:
            raise ValueError(str(exc))

    def _on_prompts_list(self) -> dict[str, Any]:
        return {
            "prompts": [
                {
                    "name": prompt.name,
                    "description": prompt.description,
                    "arguments": [
                        {
                            "name": arg.name,
                            "description": arg.description,
                            "required": arg.required,
                        }
                        for arg in prompt.arguments
                    ],
                }
                for prompt in self.prompts.list()
            ]
        }

    def _on_prompts_get(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("prompts/get requires a string 'name'.")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise ValueError("prompts/get 'arguments' must be an object.")
        try:
            return self.prompts.get(name, arguments)
        except KeyError:
            raise ValueError(f"Unknown prompt: {name}")

    def _on_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("tools/call requires a string 'name'.")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise ValueError("tools/call 'arguments' must be an object.")
        # Phase 14: extract MCP session id from params._meta.sessionId and
        # inject as a hidden _session_id arg so MCPToolset can resolve it.
        meta = params.get("_meta")
        if isinstance(meta, dict):
            sid = meta.get("sessionId") or meta.get("session_id")
            if isinstance(sid, str) and sid and "_session_id" not in arguments:
                arguments = {**arguments, "_session_id": sid}
        try:
            result = self.toolset.call(name, arguments)
        except KeyError:
            raise ValueError(f"Unknown tool: {name}")
        is_error = isinstance(result, dict) and result.get("isError") is True
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, default=str, ensure_ascii=False),
                }
            ],
            "isError": is_error,
        }

    def drain_notifications(self) -> list[dict[str, Any]]:
        """Return pending MCP change notifications as JSON-RPC messages."""
        return [
            {
                "jsonrpc": "2.0",
                "method": "notifications/resources/updated",
                "params": {"uri": item.uri, "reason": item.reason},
            }
            for item in self.toolset.notifier.drain()
        ]

    # ------------------------------------------------------------- errors

    def _error(self, request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
        error: dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {"jsonrpc": "2.0", "id": request_id, "error": error}


def _read_messages(stream) -> Iterable[dict[str, Any]]:
    for line in stream:
        text = line.strip()
        if not text:
            continue
        try:
            yield json.loads(text)
        except json.JSONDecodeError as exc:
            logger.warning("MCP: ignoring non-JSON line: %s", exc)
            continue


def serve(stdin=None, stdout=None) -> None:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    server = MCPServer()
    for request in _read_messages(stdin):
        response = server.handle(request)
        if response is not None:
            stdout.write(json.dumps(response, default=str, ensure_ascii=False) + "\n")
            stdout.flush()
        # Phase 12: drain pending change notifications after every message.
        for notif in server.drain_notifications():
            stdout.write(json.dumps(notif, default=str, ensure_ascii=False) + "\n")
            stdout.flush()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    serve()


if __name__ == "__main__":
    main()
