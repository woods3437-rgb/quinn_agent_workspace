"""Phase 13 — resource change events + `list_changed_resources`.

Internal helper used by the MCP toolset to record which `cto-os://` URIs
moved as a result of a write. The MCP server exposes a
`list_changed_resources(since=?)` tool that filters by the timestamp the
host last polled.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .models import ResourceChangeEvent, ResourceChangeType
from .sqlite_store import SQLiteStore


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


class ResourceChangeRecorder:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def record(
        self,
        uri: str,
        *,
        project_id: str | None = None,
        change_type: ResourceChangeType = ResourceChangeType.updated,
    ) -> ResourceChangeEvent:
        return self.store.append_resource_change(
            ResourceChangeEvent(
                uri=uri, project_id=project_id, change_type=change_type
            )
        )

    def list_since(
        self,
        since: str | datetime | None = None,
        limit: int = 200,
    ) -> list[ResourceChangeEvent]:
        if isinstance(since, datetime):
            since = _iso(since)
        return self.store.list_resource_changes(since=since, limit=limit)
