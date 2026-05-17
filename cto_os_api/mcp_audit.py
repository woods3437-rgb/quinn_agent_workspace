"""Phase 13 — append-only MCP write audit.

Every ``MCPToolset.call`` for a tool in ``WRITE_TOOL_NAMES`` records an
``MCPAuditEvent`` — including blocked read-only attempts. Never stores
raw payloads. Only the tool name, arg key names (not values), project id,
and outcome.

There is **no** delete or update path. The CRUD on ``SQLiteStore`` is
``append_mcp_audit`` + ``list_mcp_audit`` only.
"""
from __future__ import annotations

import json
from typing import Any

from .audit_signing import sign as audit_sign
from .models import MCPAuditAction, MCPAuditEvent
from .sqlite_store import SQLiteStore


_ACTION_BY_TOOL: dict[str, MCPAuditAction] = {
    "save_project_memory": MCPAuditAction.save,
    "pin_memory": MCPAuditAction.pin,
    "create_task": MCPAuditAction.create,
    "update_task": MCPAuditAction.update,
    "generate_build_packet": MCPAuditAction.save,
    "create_branch_plan": MCPAuditAction.create,
    "create_pr_packet": MCPAuditAction.create,
    "save_code_review_result": MCPAuditAction.review,
    "create_test_run": MCPAuditAction.test_run,
    "create_build_session": MCPAuditAction.build_session,
    "save_lesson_to_memory": MCPAuditAction.lesson,
}


_MAX_SUMMARY_BYTES = 1024


def _truncate(s: str, limit: int = _MAX_SUMMARY_BYTES) -> str:
    if len(s) <= limit:
        return s
    return s[: limit - 3] + "..."


def summarize_request(tool_name: str, arguments: dict[str, Any] | None) -> str:
    args = arguments or {}
    summary = {
        "tool": tool_name,
        "arg_keys": sorted(args.keys()),
        "arg_count": len(args),
    }
    return _truncate(json.dumps(summary, default=str, ensure_ascii=False))


def summarize_response(tool_name: str, outcome: str, project_id: str | None) -> str:
    summary = {
        "tool": tool_name,
        "outcome": outcome,
        "project_id": project_id,
    }
    return _truncate(json.dumps(summary, default=str, ensure_ascii=False))


def classify(tool_name: str) -> MCPAuditAction:
    return _ACTION_BY_TOOL.get(tool_name, MCPAuditAction.unknown)


class MCPAuditRecorder:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def record(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any] | None,
        outcome: str,
        blocked: bool,
        readonly_mode: bool,
        session_id: str = "unknown",
    ) -> MCPAuditEvent:
        project_id = None
        if arguments and isinstance(arguments.get("project_id"), str):
            project_id = arguments["project_id"]
        event = MCPAuditEvent(
            session_id=session_id or "unknown",
            tool_name=tool_name,
            project_id=project_id,
            action_type=classify(tool_name),
            request_summary=summarize_request(tool_name, arguments),
            response_summary=summarize_response(tool_name, outcome, project_id),
            blocked=bool(blocked),
            readonly_mode=bool(readonly_mode),
        )
        # Phase 14: HMAC-sign when CTO_OS_AUDIT_SIGNING_KEY is set.
        signature, key_id = audit_sign(event)
        if signature:
            event.signature = signature
            event.signing_key_id = key_id
        return self.store.append_mcp_audit(event)
