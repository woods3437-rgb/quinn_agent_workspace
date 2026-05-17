"""Phase 12 — lightweight MCP change notifications.

In-process publisher. The MCP server drains pending notifications after
each ``tools/call`` and emits them as JSON-RPC notifications:

    {"jsonrpc":"2.0","method":"notifications/resources/updated","params":{"uri":"cto-os://..."}}

If the host doesn't process notifications, they're harmlessly dropped on
the next drain — this is observability, not correctness.
"""
from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timezone
from typing import Iterable

from .models import MCPChangeNotification


class MCPNotifier:
    def __init__(self, max_pending: int = 200) -> None:
        self._pending: deque[MCPChangeNotification] = deque(maxlen=max_pending)
        self._lock = threading.Lock()

    def notify_resource_updated(self, uri: str, reason: str = "") -> None:
        with self._lock:
            self._pending.append(
                MCPChangeNotification(
                    uri=uri, reason=reason, created_at=datetime.now(timezone.utc)
                )
            )

    def notify_many(self, uris: Iterable[str], reason: str = "") -> None:
        for uri in uris:
            self.notify_resource_updated(uri, reason=reason)

    def drain(self) -> list[MCPChangeNotification]:
        with self._lock:
            items = list(self._pending)
            self._pending.clear()
        return items

    def pending(self) -> int:
        with self._lock:
            return len(self._pending)
