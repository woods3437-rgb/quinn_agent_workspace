"""Phase 11 — short-lived writer leases for destructive ops.

Intended for genuinely-destructive coarse-grained operations only:
- snapshot restore
- project import / export
- bulk reindex

Per-row writes do not take a lease — SQLite WAL + busy_timeout (set in
``SQLiteStore._connect``) is enough. The lease prevents two destructive ops
overwriting each other concurrently across the FastAPI / worker / MCP
processes.

Usage::

    with WriterLease(store, "snapshot_restore", holder="mcp:abc") as info:
        ... # do the destructive thing
"""
from __future__ import annotations

import os
import socket
import uuid
from contextlib import AbstractContextManager
from dataclasses import dataclass

from .sqlite_store import SQLiteStore


DEFAULT_TTL_SECONDS = 30


class WriterLeaseBusy(RuntimeError):
    """A non-expired lease is held by another holder."""


def default_holder() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


@dataclass
class WriterLease(AbstractContextManager):
    store: SQLiteStore
    name: str
    holder: str | None = None
    ttl_seconds: int = DEFAULT_TTL_SECONDS

    def __post_init__(self) -> None:
        self.holder = self.holder or default_holder()
        self._acquired = False

    def __enter__(self):
        info = self.store.acquire_writer_lease(
            self.name, self.holder, self.ttl_seconds
        )
        if info is None:
            raise WriterLeaseBusy(
                f"Writer lease '{self.name}' is held by another process; "
                "retry after the current operation finishes."
            )
        self._acquired = True
        return info

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._acquired:
            self.store.release_writer_lease(self.name, self.holder)
        # Don't swallow exceptions.
        return None
