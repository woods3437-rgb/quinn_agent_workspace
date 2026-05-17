"""Phase 14 — per-session MCP identity.

Resolves a session id for each MCP call (from ``params._meta.sessionId``
forwarded as ``_session_id`` arg, then env, then ``"unknown"``), upserts
the session row, updates ``last_seen_at``, and enforces revoked /
readonly gates.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from .models import MCPSession
from .sqlite_store import SQLiteStore


MAX_SESSION_ID_LEN = 128
DEFAULT_SESSION_ID = "unknown"


class MCPSessionRevoked(RuntimeError):
    """Raised when the resolved MCP session has been revoked."""


class MCPSessionReadonly(RuntimeError):
    """Raised when a write tool is invoked under a read-only session."""


def resolve_session_id(arguments: dict | None) -> str:
    if isinstance(arguments, dict):
        candidate = arguments.get("_session_id")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()[:MAX_SESSION_ID_LEN]
    env = (os.getenv("CTO_OS_MCP_SESSION_ID") or "").strip()
    if env:
        return env[:MAX_SESSION_ID_LEN]
    return DEFAULT_SESSION_ID


class MCPSessionResolver:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def touch(self, session_id: str) -> MCPSession:
        session_id = (session_id or DEFAULT_SESSION_ID)[:MAX_SESSION_ID_LEN]
        existing = self.store.get_mcp_session(session_id)
        if existing is None:
            session = MCPSession(session_id=session_id)
            self.store.upsert_mcp_session(session)
            return session
        existing.last_seen_at = datetime.now(timezone.utc)
        self.store.upsert_mcp_session(existing)
        return existing

    def gate(self, session: MCPSession, *, is_write_tool: bool) -> None:
        if session.revoked:
            raise MCPSessionRevoked(
                f"session '{session.session_id}' is revoked; refusing call."
            )
        if is_write_tool and session.readonly:
            raise MCPSessionReadonly(
                f"session '{session.session_id}' is read-only; refusing write tool."
            )
