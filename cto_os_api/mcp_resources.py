"""Phase 11 — MCP resources for read-only context hydration.

Resources let the host pull state without burning a ``tools/call``. Every URI
is read-only; the resource layer never accepts writes. URIs use the
``cto-os://`` scheme.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from .control_room import ControlRoom
from .memory_engine import LocalMemoryEngine
from .shipped_dashboard import ShippedDashboard
from .sqlite_store import SQLiteStore
from .system_shipped import SystemShipped
from .workspace_generators import WorkspaceGenerator


@dataclass(frozen=True)
class MCPResource:
    uri: str
    name: str
    description: str
    mime_type: str = "application/json"


@dataclass(frozen=True)
class MCPResourceTemplate:
    uri_template: str
    name: str
    description: str
    mime_type: str = "application/json"


def _serialise(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, list):
        return [_serialise(item) for item in value]
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dump(mode="json")
    return value


class MCPResourceProvider:
    """Resource catalog + URI dispatch.

    URI shapes:
      cto-os://projects
      cto-os://projects/{project_id}/brief
      cto-os://projects/{project_id}/source-of-truth
      cto-os://projects/{project_id}/recent-activity
      cto-os://projects/{project_id}/risks
      cto-os://projects/{project_id}/tasks
      cto-os://projects/{project_id}/shipped
      cto-os://system/control-room
      cto-os://system/shipped
    """

    def __init__(
        self, store: SQLiteStore, memory_engine: LocalMemoryEngine
    ) -> None:
        self.store = store
        self.memory_engine = memory_engine
        self.workspace_generator = WorkspaceGenerator(store, memory_engine)
        self.shipped_dashboard = ShippedDashboard(store)
        self.system_shipped = SystemShipped(store)
        self.control_room = ControlRoom(store)

        self._patterns: list[tuple[re.Pattern[str], Callable[[re.Match[str]], Any]]] = [
            (re.compile(r"^cto-os://projects/?$"), lambda _m: self._projects()),
            (re.compile(r"^cto-os://system/control-room/?$"), lambda _m: self._system_control_room()),
            (re.compile(r"^cto-os://system/shipped/?$"), lambda _m: self._system_shipped()),
            (re.compile(r"^cto-os://projects/(?P<pid>[^/]+)/brief/?$"), lambda m: self._project_brief(m["pid"])),
            (re.compile(r"^cto-os://projects/(?P<pid>[^/]+)/source-of-truth/?$"), lambda m: self._project_source_of_truth(m["pid"])),
            (re.compile(r"^cto-os://projects/(?P<pid>[^/]+)/recent-activity/?$"), lambda m: self._project_recent_activity(m["pid"])),
            (re.compile(r"^cto-os://projects/(?P<pid>[^/]+)/risks/?$"), lambda m: self._project_risks(m["pid"])),
            (re.compile(r"^cto-os://projects/(?P<pid>[^/]+)/tasks/?$"), lambda m: self._project_tasks(m["pid"])),
            (re.compile(r"^cto-os://projects/(?P<pid>[^/]+)/shipped/?$"), lambda m: self._project_shipped(m["pid"])),
        ]

    # ---------------------------------------------------------------- catalog

    def static_resources(self) -> list[MCPResource]:
        """Resources whose URI does not require a project id."""
        return [
            MCPResource(
                uri="cto-os://projects",
                name="All projects",
                description="JSON list of every project in the CTO OS.",
            ),
            MCPResource(
                uri="cto-os://system/control-room",
                name="Control room",
                description="System-wide rollup across every project.",
            ),
            MCPResource(
                uri="cto-os://system/shipped",
                name="System shipped",
                description="Cross-project 'what we shipped' summary + velocity.",
            ),
        ]

    def resource_templates(self) -> list[MCPResourceTemplate]:
        """URI templates the host can fill with a project_id."""
        return [
            MCPResourceTemplate(
                uri_template="cto-os://projects/{project_id}/brief",
                name="Project brief",
                description="Composed brief (summary, goal, stack, roadmap, decisions, risks, next actions).",
            ),
            MCPResourceTemplate(
                uri_template="cto-os://projects/{project_id}/source-of-truth",
                name="Project source-of-truth",
                description="Pinned memories for the project.",
            ),
            MCPResourceTemplate(
                uri_template="cto-os://projects/{project_id}/recent-activity",
                name="Recent activity",
                description="Last 20 execution logs for the project.",
            ),
            MCPResourceTemplate(
                uri_template="cto-os://projects/{project_id}/risks",
                name="Open risks",
                description="Open risks for the project.",
            ),
            MCPResourceTemplate(
                uri_template="cto-os://projects/{project_id}/tasks",
                name="Project tasks",
                description="Tasks for the project (kanban view).",
            ),
            MCPResourceTemplate(
                uri_template="cto-os://projects/{project_id}/shipped",
                name="Project shipped",
                description="What the project has shipped (velocity, sessions, lessons).",
            ),
        ]

    # ----------------------------------------------------------------- read

    def read(self, uri: str) -> dict[str, Any]:
        for pattern, handler in self._patterns:
            match = pattern.match(uri)
            if match:
                data = handler(match)
                text = json.dumps(_serialise(data), default=str, ensure_ascii=False)
                return {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "application/json",
                            "text": text,
                        }
                    ]
                }
        raise KeyError(f"Unknown CTO OS resource URI: {uri}")

    # ------------------------------------------------------------- handlers

    def _projects(self):
        return self.store.list_projects()

    def _system_control_room(self):
        return self.control_room.build()

    def _system_shipped(self):
        return self.system_shipped.build()

    def _project_brief(self, project_id: str):
        return self.workspace_generator.current_brief(project_id)

    def _project_source_of_truth(self, project_id: str):
        return self.memory_engine.pinned_context(project_id)

    def _project_recent_activity(self, project_id: str):
        return self.store.list_logs(project_id)[:20]

    def _project_risks(self, project_id: str):
        return [
            risk for risk in self.store.list_risks(project_id) if risk.status.value == "open"
        ]

    def _project_tasks(self, project_id: str):
        return self.store.list_tasks(project_id)

    def _project_shipped(self, project_id: str):
        return self.shipped_dashboard.build(project_id)
