"""Phase 10 — MCP tool registry.

Each tool is a pure Python callable + a JSON schema describing its inputs.
``mcp_server.py`` translates JSON-RPC ``tools/call`` requests into these
calls. Tools share a single ``MCPToolset`` instance which holds a long-lived
``SQLiteStore`` and ``MempalaceMemoryEngine``.

Safety:
- Read tools are unrestricted.
- Write tools touch CTO OS internal state only (memory, tasks, code reviews,
  build sessions, lessons). They cannot run shell commands or write to
  GitHub.
- GitHub tools exposed here are PREVIEW only. The Phase 7 write guard still
  blocks any actual ``create_*`` path; ``create_*`` GitHub tools are
  deliberately NOT exposed via MCP in this phase.
- Phase 12: ``CTO_OS_MCP_READONLY=1`` blocks every write tool with a
  structured response; read + preview tools still work.
"""
from __future__ import annotations

import inspect
import os
from dataclasses import dataclass
from typing import Any, Callable

from .build_session_timeline import BuildSessionTimelineBuilder
from .context_builder import ContextBuilder
from .control_room import ControlRoom
from .execution_engine import ExecutionEngine
from .git_reader import GitReader
from .github_integration import GitHubIntegration
from .llm_results import LLMResultsService
from .mcp_audit import MCPAuditRecorder
from .mcp_notifications import MCPNotifier
from .mcp_sessions import (
    MCPSessionReadonly,
    MCPSessionResolver,
    MCPSessionRevoked,
    resolve_session_id,
)
from .memory_engine import LocalMemoryEngine, MempalaceMemoryEngine
from .resource_changes import ResourceChangeRecorder
from .models import (
    BranchPlanGenerateRequest,
    BuildPacketGenerateRequest,
    BuildSessionCreate,
    BuildSessionStatus,
    BuildPacketContextRequest,
    CodeReviewContextRequest,
    CodeReviewSaveRequest,
    ImplementationPlanContextRequest,
    MemoryCreate,
    PRPacketGenerateRequest,
    RetrospectiveContextRequest,
    TaskCategory,
    TaskCreate,
    TaskPriority,
    TaskStatus,
    TaskUpdate,
    TestRunCreate,
    TestRunStatus,
)
from .repo_operator import RepoOperator
from .sqlite_store import SQLiteStore
from .workspace_generators import WorkspaceGenerator


def _serialise(value: Any) -> Any:
    """Convert any Pydantic model / list of them into plain JSON."""
    if value is None:
        return None
    if isinstance(value, list):
        return [_serialise(item) for item in value]
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dump(mode="json")
    return value


@dataclass(frozen=True)
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Any]


class MCPReadOnlyBlocked:
    """Sentinel result returned when a write tool is invoked under read-only mode."""

    def __init__(self, tool: str) -> None:
        self.tool = tool

    def to_payload(self) -> dict[str, Any]:
        return {
            "isError": True,
            "blocked": True,
            "reason": (
                "MCP read-only mode is enabled (CTO_OS_MCP_READONLY=1); "
                "write tools refuse to mutate state."
            ),
            "tool": self.tool,
        }


WRITE_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "save_project_memory",
        "pin_memory",
        "create_task",
        "update_task",
        "generate_build_packet",
        "create_branch_plan",
        "create_pr_packet",
        "save_code_review_result",
        "create_test_run",
        "create_build_session",
        "save_lesson_to_memory",
        # Phase 15 entrypoints — first-time setup + scan + summarize-style writes.
        "create_project",
        "create_repository",
        "scan_repository",
        "index_repo_to_memory",
        "summarize_build_session",
        "generate_retrospective",
        "review_diff_from_git",
    }
)


def mcp_readonly_enabled() -> bool:
    return os.getenv("CTO_OS_MCP_READONLY", "0").strip() == "1"


class MCPToolset:
    """Container for all CTO OS MCP tools.

    Built once at process start by ``mcp_server.MCPServer``. Reuses a single
    ``SQLiteStore`` instance (per-call SQLite connections internally, so this
    is safe for the long-lived MCP process).
    """

    def __init__(
        self,
        store: SQLiteStore | None = None,
        memory_engine: LocalMemoryEngine | None = None,
        notifier: MCPNotifier | None = None,
    ) -> None:
        self.store = store or SQLiteStore()
        self.memory_engine = memory_engine or MempalaceMemoryEngine(self.store)
        self.notifier = notifier or MCPNotifier()
        self.audit_recorder = MCPAuditRecorder(self.store)
        self.change_recorder = ResourceChangeRecorder(self.store)
        self.session_resolver = MCPSessionResolver(self.store)
        self.workspace_generator = WorkspaceGenerator(self.store, self.memory_engine)
        self.repo_operator = RepoOperator(self.store, self.memory_engine)
        self.git_reader = GitReader()
        self.github = GitHubIntegration()
        self.timeline_builder = BuildSessionTimelineBuilder(self.store)
        self.context_builder = ContextBuilder(self.store, self.memory_engine)
        self.llm_results = LLMResultsService(self.store, self.memory_engine)
        self.execution_engine = ExecutionEngine(
            self.store,
            self.memory_engine,
            self.workspace_generator,
            lambda *args, **kwargs: None,
            self.repo_operator,
        )
        self._tools: dict[str, MCPTool] = {}
        self._register()

    # ----------------------------------------------------------------- register

    def _add(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Callable[..., Any],
    ) -> None:
        self._tools[name] = MCPTool(name, description, input_schema, handler)

    def tools(self) -> list[MCPTool]:
        return list(self._tools.values())

    def get(self, name: str) -> MCPTool:
        if name not in self._tools:
            raise KeyError(name)
        return self._tools[name]

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        tool = self.get(name)
        raw_args = arguments or {}
        # Phase 14: resolve & touch the MCP session before doing anything else.
        session_id = resolve_session_id(raw_args)
        try:
            session = self.session_resolver.touch(session_id)
        except Exception:  # noqa: BLE001 — fall back to a synthetic record
            from .models import MCPSession

            session = MCPSession(session_id=session_id)
        is_write = name in WRITE_TOOL_NAMES
        env_readonly = mcp_readonly_enabled()
        session_readonly = session.readonly
        readonly = env_readonly or session_readonly

        # Strip the transport-level session id before it reaches handlers / audit.
        args = {k: v for k, v in raw_args.items() if k != "_session_id"}

        # 1. Revoked session: refuse everything.
        if session.revoked:
            blocked = {
                "isError": True,
                "blocked": True,
                "reason": "session is revoked; refusing call.",
                "tool": name,
                "session_id": session.session_id,
            }
            self._audit(
                name, args, outcome="blocked", blocked=True, readonly=readonly,
                session_id=session.session_id,
            )
            return blocked

        # 2. Read-only (env or session): refuse writes.
        if is_write and readonly:
            blocked = MCPReadOnlyBlocked(name).to_payload()
            if session_readonly and not env_readonly:
                blocked["reason"] = "session is read-only; refusing write tool."
            blocked["session_id"] = session.session_id
            self._audit(
                name, args, outcome="blocked", blocked=True, readonly=True,
                session_id=session.session_id,
            )
            return blocked

        sig = inspect.signature(tool.handler)
        accepts_var_keyword = any(
            param.kind is inspect.Parameter.VAR_KEYWORD
            for param in sig.parameters.values()
        )
        if accepts_var_keyword:
            bound = dict(args)
        else:
            bound = {key: value for key, value in args.items() if key in sig.parameters}
        try:
            result = tool.handler(**bound)
        except Exception:
            if is_write:
                self._audit(
                    name, args, outcome="error", blocked=False, readonly=readonly,
                    session_id=session.session_id,
                )
            raise
        if is_write:
            self._notify_after_write(name, args, result)
            self._audit(
                name, args, outcome="ok", blocked=False, readonly=readonly,
                session_id=session.session_id,
            )
        return result

    def _notify_after_write(self, name: str, args: dict[str, Any], result: Any) -> None:
        project_id = args.get("project_id") if isinstance(args, dict) else None
        uris: list[str] = []
        if project_id:
            if name in {"create_task", "update_task"}:
                uris.append(f"cto-os://projects/{project_id}/tasks")
            elif name in {"save_project_memory", "pin_memory", "save_lesson_to_memory"}:
                uris.append(f"cto-os://projects/{project_id}/source-of-truth")
            elif name in {"create_build_session"}:
                uris.append(f"cto-os://projects/{project_id}/shipped")
            elif name in {"create_test_run", "save_code_review_result"}:
                uris.append(f"cto-os://projects/{project_id}/recent-activity")
            elif name in {"create_branch_plan", "create_pr_packet", "generate_build_packet"}:
                uris.append(f"cto-os://projects/{project_id}/tasks")
        uris.append("cto-os://system/control-room")
        self.notifier.notify_many(uris, reason=f"mcp.tool:{name}")
        # Phase 13: durable resource-change log for `list_changed_resources`.
        try:
            for uri in uris:
                self.change_recorder.record(uri, project_id=project_id)
        except Exception:  # noqa: BLE001 — audit-style: never fail on telemetry
            pass

    def _audit(
        self,
        name: str,
        args: dict[str, Any],
        *,
        outcome: str,
        blocked: bool,
        readonly: bool,
        session_id: str = "unknown",
    ) -> None:
        try:
            self.audit_recorder.record(
                tool_name=name,
                arguments=args,
                outcome=outcome,
                blocked=blocked,
                readonly_mode=readonly,
                session_id=session_id,
            )
        except Exception:  # noqa: BLE001
            pass

    # -------------------------------------------------------------- registration

    def _register(self) -> None:
        self._register_project_tools()
        self._register_memory_tools()
        self._register_task_tools()
        self._register_repo_tools()
        self._register_execution_tools()
        self._register_github_preview_tools()
        self._register_context_tools()
        self._register_llm_result_tools()
        self._register_safety_tools()
        self._register_resource_change_tools()
        self._register_phase15_entrypoints()
        self._register_phase16_classifier_tools()
        self._register_phase16_working_tree_tools()
        self._register_phase16_review_routing_tools()

    # -- project ---------------------------------------------------------------

    def _register_project_tools(self) -> None:
        self._add(
            "list_projects",
            "List every project the CTO OS knows about (id, name, status).",
            {"type": "object", "properties": {}, "additionalProperties": False},
            lambda: _serialise(self.store.list_projects()),
        )
        self._add(
            "get_project",
            "Fetch one project by id.",
            {
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
                "required": ["project_id"],
                "additionalProperties": False,
            },
            lambda project_id: _serialise(self.store.get_project(project_id)),
        )
        self._add(
            "get_project_brief",
            "Composed project brief (summary, goal, audience, stack, roadmap, decisions, risks, next actions).",
            {
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
                "required": ["project_id"],
                "additionalProperties": False,
            },
            lambda project_id: _serialise(self.workspace_generator.current_brief(project_id)),
        )
        self._add(
            "get_control_room_summary",
            "System-wide control-room rollup across every project.",
            {"type": "object", "properties": {}, "additionalProperties": False},
            lambda: _serialise(ControlRoom(self.store).build()),
        )

    # -- memory ----------------------------------------------------------------

    def _register_memory_tools(self) -> None:
        self._add(
            "search_project_memory",
            "Search a project's memory. cross_project must be explicitly true to widen scope.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "query": {"type": "string"},
                    "cross_project": {"type": "boolean", "default": False},
                    "limit": {"type": "integer", "default": 8},
                },
                "required": ["project_id", "query"],
                "additionalProperties": False,
            },
            lambda project_id, query, cross_project=False, limit=8: _serialise(
                self.memory_engine.search(
                    project_id, query, cross_project=cross_project, limit=limit
                )
            ),
        )
        self._add(
            "save_project_memory",
            "Save a memory into a specific project. Does NOT cross project boundaries.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "pinned": {"type": "boolean", "default": False},
                    "source": {"type": "string", "default": "mcp"},
                },
                "required": ["project_id", "title", "content"],
                "additionalProperties": False,
            },
            self._save_memory,
        )
        self._add(
            "list_source_of_truth_memory",
            "List pinned (source-of-truth) memory for a project.",
            {
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
                "required": ["project_id"],
                "additionalProperties": False,
            },
            lambda project_id: _serialise(self.memory_engine.pinned_context(project_id)),
        )
        self._add(
            "pin_memory",
            "Pin or unpin a memory as source-of-truth.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "memory_id": {"type": "string"},
                    "pinned": {"type": "boolean", "default": True},
                },
                "required": ["project_id", "memory_id"],
                "additionalProperties": False,
            },
            lambda project_id, memory_id, pinned=True: _serialise(
                self.store.update_memory_pin(project_id, memory_id, pinned)
            ),
        )

    def _save_memory(self, project_id, title, content, tags=None, pinned=False, source="mcp"):
        memory = self.store.create_memory(
            project_id,
            MemoryCreate(
                title=title, content=content, tags=list(tags or []), pinned=pinned, source=source
            ),
        )
        self.memory_engine.index_memory(memory)
        return _serialise(memory)

    # -- tasks -----------------------------------------------------------------

    def _register_task_tools(self) -> None:
        self._add(
            "list_tasks",
            "List all tasks for a project.",
            {
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
                "required": ["project_id"],
                "additionalProperties": False,
            },
            lambda project_id: _serialise(self.store.list_tasks(project_id)),
        )
        self._add(
            "get_task",
            "Fetch one task by id.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "task_id": {"type": "string"},
                },
                "required": ["project_id", "task_id"],
                "additionalProperties": False,
            },
            lambda project_id, task_id: _serialise(self.store.get_task(project_id, task_id)),
        )
        self._add(
            "create_task",
            "Create a new task in a project.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string", "default": ""},
                    "priority": {"type": "string", "default": "medium"},
                    "category": {"type": "string", "default": "product"},
                    "acceptance_criteria": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                    },
                },
                "required": ["project_id", "title"],
                "additionalProperties": False,
            },
            self._create_task,
        )
        self._add(
            "update_task",
            "Update an existing task. Pass only the fields you want to change.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "task_id": {"type": "string"},
                    "status": {"type": "string"},
                    "priority": {"type": "string"},
                    "category": {"type": "string"},
                    "description": {"type": "string"},
                    "title": {"type": "string"},
                },
                "required": ["project_id", "task_id"],
                "additionalProperties": False,
            },
            self._update_task,
        )
        self._add(
            "list_status_suggestions",
            "List unresolved status suggestions (open, awaiting apply/dismiss).",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "include_resolved": {"type": "boolean", "default": False},
                },
                "required": ["project_id"],
                "additionalProperties": False,
            },
            lambda project_id, include_resolved=False: _serialise(
                self.store.list_status_suggestions(project_id, include_resolved=include_resolved)
            ),
        )

    def _create_task(
        self,
        project_id,
        title,
        description="",
        priority="medium",
        category="product",
        acceptance_criteria=None,
    ):
        return _serialise(
            self.store.create_task(
                project_id,
                TaskCreate(
                    title=title,
                    description=description,
                    priority=TaskPriority(priority),
                    category=TaskCategory(category),
                    acceptance_criteria=list(acceptance_criteria or []),
                ),
            )
        )

    def _update_task(self, project_id, task_id, **patch):
        coerced: dict[str, Any] = {}
        for key, value in patch.items():
            if key == "status":
                coerced[key] = TaskStatus(value)
            elif key == "priority":
                coerced[key] = TaskPriority(value)
            elif key == "category":
                coerced[key] = TaskCategory(value)
            else:
                coerced[key] = value
        return _serialise(self.store.update_task(project_id, task_id, TaskUpdate(**coerced)))

    # -- repo ------------------------------------------------------------------

    def _register_repo_tools(self) -> None:
        self._add(
            "list_repositories",
            "List repositories registered for a project.",
            {
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
                "required": ["project_id"],
                "additionalProperties": False,
            },
            lambda project_id: _serialise(self.store.list_repositories(project_id)),
        )
        self._add(
            "get_repo_scan",
            "Latest repo scan for a repository (tech stack, routes, key files, commands, risks).",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "repository_id": {"type": "string"},
                },
                "required": ["project_id", "repository_id"],
                "additionalProperties": False,
            },
            self._latest_scan,
        )
        self._add(
            "search_repo_files",
            "Search indexed repo files by path/summary/role.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "repository_id": {"type": "string"},
                    "query": {"type": "string"},
                },
                "required": ["project_id", "repository_id", "query"],
                "additionalProperties": False,
            },
            lambda project_id, repository_id, query: _serialise(
                self.store.search_repo_files(project_id, repository_id, query)
            ),
        )
        self._add(
            "search_repo_symbols",
            "Search indexed code symbols (functions, classes, routes, components).",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "repository_id": {"type": "string"},
                    "query": {"type": "string"},
                },
                "required": ["project_id", "repository_id", "query"],
                "additionalProperties": False,
            },
            lambda project_id, repository_id, query: _serialise(
                self.store.search_code_symbols(project_id, repository_id, query)
            ),
        )
        self._add(
            "get_git_status",
            "Read-only git status: branch, changed/staged/unstaged files, recent commits.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "repository_id": {"type": "string"},
                },
                "required": ["project_id", "repository_id"],
                "additionalProperties": False,
            },
            lambda project_id, repository_id: _serialise(
                self.git_reader.status(self.store.get_repository(project_id, repository_id))
            ),
        )

    def _latest_scan(self, project_id, repository_id):
        scans = self.store.list_repo_scans(project_id, repository_id)
        return _serialise(scans[0]) if scans else None

    # -- execution -------------------------------------------------------------

    def _register_execution_tools(self) -> None:
        self._add(
            "generate_build_packet",
            "Generate a deterministic build packet (steps, files, acceptance, prompts).",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "task_id": {"type": "string"},
                    "source_text": {"type": "string", "default": ""},
                    "title": {"type": "string", "default": ""},
                    "save_to_memory": {"type": "boolean", "default": False},
                },
                "required": ["project_id"],
                "additionalProperties": False,
            },
            self._generate_build_packet,
        )
        self._add(
            "create_branch_plan",
            "Create a branch plan without writing to git or GitHub.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "repository_id": {"type": "string"},
                    "task_id": {"type": "string"},
                    "build_packet_id": {"type": "string"},
                    "objective": {"type": "string", "default": ""},
                },
                "required": ["project_id", "repository_id"],
                "additionalProperties": False,
            },
            self._create_branch_plan,
        )
        self._add(
            "create_pr_packet",
            "Create a PR packet (no GitHub PR is opened).",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "repository_id": {"type": "string"},
                    "branch_plan_id": {"type": "string"},
                    "task_id": {"type": "string"},
                    "title": {"type": "string", "default": ""},
                },
                "required": ["project_id", "repository_id"],
                "additionalProperties": False,
            },
            self._create_pr_packet,
        )
        self._add(
            "review_diff_context",
            "Assemble code-review context for the host model to complete.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "diff_text": {"type": "string"},
                    "task_id": {"type": "string"},
                    "branch_plan_id": {"type": "string"},
                    "repository_id": {"type": "string"},
                },
                "required": ["project_id", "diff_text"],
                "additionalProperties": False,
            },
            lambda project_id, diff_text, task_id=None, branch_plan_id=None, repository_id=None: _serialise(
                self.context_builder.code_review(
                    project_id,
                    CodeReviewContextRequest(
                        diff_text=diff_text,
                        task_id=task_id,
                        branch_plan_id=branch_plan_id,
                        repository_id=repository_id,
                    ),
                )
            ),
        )
        self._add(
            "save_code_review_result",
            "Persist a host-model code review result. recommendation must be approve|revise|block.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "diff_text": {"type": "string"},
                    "task_id": {"type": "string"},
                    "branch_plan_id": {"type": "string"},
                    "repository_id": {"type": "string"},
                    "recommendation": {"type": "string", "enum": ["approve", "revise", "block"]},
                    "summary": {"type": "string"},
                    "blocking_issues": {"type": "array", "items": {"type": "string"}},
                    "non_blocking_suggestions": {"type": "array", "items": {"type": "string"}},
                    "missing_tests": {"type": "array", "items": {"type": "string"}},
                    "security_concerns": {"type": "array", "items": {"type": "string"}},
                    "acceptance_criteria_check": {"type": "string"},
                    "confidence": {"type": "number"},
                    "create_follow_up_tasks": {"type": "boolean", "default": False},
                },
                "required": ["project_id", "diff_text", "recommendation"],
                "additionalProperties": False,
            },
            self._save_code_review,
        )
        self._add(
            "create_test_run",
            "Record a test run (caller already executed the command).",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "repository_id": {"type": "string"},
                    "task_id": {"type": "string"},
                    "command": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["not_run", "passed", "failed", "skipped"],
                    },
                    "output": {"type": "string", "default": ""},
                },
                "required": ["project_id", "repository_id", "command", "status"],
                "additionalProperties": False,
            },
            self._record_test_run,
        )
        self._add(
            "create_build_session",
            "Open a new build session.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "title": {"type": "string"},
                    "repository_id": {"type": "string"},
                    "task_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": [
                            "planning",
                            "in_progress",
                            "reviewing",
                            "completed",
                            "blocked",
                            "abandoned",
                        ],
                        "default": "planning",
                    },
                },
                "required": ["project_id", "title"],
                "additionalProperties": False,
            },
            self._create_build_session,
        )
        self._add(
            "summarize_build_session_context",
            "Return the build-session timeline as structured items.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "session_id": {"type": "string"},
                },
                "required": ["project_id", "session_id"],
                "additionalProperties": False,
            },
            lambda project_id, session_id: _serialise(
                self.timeline_builder.build(project_id, session_id)
            ),
        )
        self._add(
            "save_lesson_to_memory",
            "Save a lesson learned into project memory.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "pinned": {"type": "boolean", "default": False},
                },
                "required": ["project_id", "title", "content"],
                "additionalProperties": False,
            },
            self._save_lesson,
        )

    def _generate_build_packet(self, project_id, task_id=None, source_text="", title="", save_to_memory=False):
        return _serialise(
            self.execution_engine.generate_build_packet(
                project_id,
                BuildPacketGenerateRequest(
                    task_id=task_id, source_text=source_text, title=title, save_to_memory=save_to_memory
                ),
            )
        )

    def _create_branch_plan(self, project_id, repository_id, task_id=None, build_packet_id=None, objective=""):
        return _serialise(
            self.repo_operator.generate_branch_plan(
                project_id,
                BranchPlanGenerateRequest(
                    repository_id=repository_id,
                    task_id=task_id,
                    build_packet_id=build_packet_id,
                    objective=objective,
                ),
            )
        )

    def _create_pr_packet(self, project_id, repository_id, branch_plan_id=None, task_id=None, title=""):
        return _serialise(
            self.repo_operator.generate_pr_packet(
                project_id,
                PRPacketGenerateRequest(
                    repository_id=repository_id,
                    branch_plan_id=branch_plan_id,
                    task_id=task_id,
                    title=title,
                ),
            )
        )

    def _save_code_review(self, project_id, **payload):
        return _serialise(
            self.llm_results.save_code_review(project_id, CodeReviewSaveRequest(**payload))
        )

    def _record_test_run(self, project_id, repository_id, command, status, task_id=None, output=""):
        return _serialise(
            self.repo_operator.record_test_run(
                project_id,
                TestRunCreate(
                    repository_id=repository_id,
                    task_id=task_id,
                    command=command,
                    status=TestRunStatus(status),
                    output=output,
                ),
            )
        )

    def _create_build_session(self, project_id, title, repository_id=None, task_id=None, status="planning"):
        return _serialise(
            self.store.create_build_session(
                project_id,
                BuildSessionCreate(
                    title=title,
                    repository_id=repository_id,
                    task_id=task_id,
                    status=BuildSessionStatus(status),
                ),
            )
        )

    def _save_lesson(self, project_id, title, content, pinned=False):
        memory = self.store.create_memory(
            project_id,
            MemoryCreate(
                title=title, content=content, tags=["lesson"], pinned=pinned, source="mcp_lesson"
            ),
        )
        self.memory_engine.index_memory(memory)
        return _serialise(memory)

    # -- github preview only --------------------------------------------------

    def _register_github_preview_tools(self) -> None:
        self._add(
            "preview_github_issue",
            "Preview the GitHub issue payload that would be created for a task. Never calls GitHub.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "task_id": {"type": "string"},
                },
                "required": ["project_id", "task_id"],
                "additionalProperties": False,
            },
            lambda project_id, task_id: _serialise(
                self.repo_operator.preview_task_issue(project_id, task_id)
            ),
        )
        self._add(
            "preview_github_branch",
            "Preview the GitHub branch payload (sanitised name + base) for a branch plan. Never calls GitHub.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "branch_plan_id": {"type": "string"},
                },
                "required": ["project_id", "branch_plan_id"],
                "additionalProperties": False,
            },
            lambda project_id, branch_plan_id: _serialise(
                self.repo_operator.preview_branch(project_id, branch_plan_id, None)
            ),
        )
        self._add(
            "preview_github_draft_pr",
            "Preview the draft-PR payload for a PR packet. Never calls GitHub.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "pr_packet_id": {"type": "string"},
                },
                "required": ["project_id", "pr_packet_id"],
                "additionalProperties": False,
            },
            lambda project_id, pr_packet_id: _serialise(
                self.repo_operator.preview_draft_pr(project_id, pr_packet_id, None)
            ),
        )

    # -- context bundles (LLM brief assembly) ---------------------------------

    def _register_context_tools(self) -> None:
        self._add(
            "context_code_review",
            "Assemble code-review context (memory, pinned, decisions, schema, save_endpoint).",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "diff_text": {"type": "string"},
                    "task_id": {"type": "string"},
                    "branch_plan_id": {"type": "string"},
                    "repository_id": {"type": "string"},
                },
                "required": ["project_id", "diff_text"],
                "additionalProperties": False,
            },
            lambda project_id, diff_text, task_id=None, branch_plan_id=None, repository_id=None: _serialise(
                self.context_builder.code_review(
                    project_id,
                    CodeReviewContextRequest(
                        diff_text=diff_text,
                        task_id=task_id,
                        branch_plan_id=branch_plan_id,
                        repository_id=repository_id,
                    ),
                )
            ),
        )
        self._add(
            "context_retrospective",
            "Assemble retrospective context.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "build_session_id": {"type": "string"},
                    "task_id": {"type": "string"},
                },
                "required": ["project_id"],
                "additionalProperties": False,
            },
            lambda project_id, build_session_id=None, task_id=None: _serialise(
                self.context_builder.retrospective(
                    project_id,
                    RetrospectiveContextRequest(
                        build_session_id=build_session_id, task_id=task_id
                    ),
                )
            ),
        )
        self._add(
            "context_implementation_plan",
            "Assemble implementation-plan context.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "source_type": {"type": "string", "default": "task"},
                    "source_id": {"type": "string"},
                    "source_text": {"type": "string", "default": ""},
                },
                "required": ["project_id"],
                "additionalProperties": False,
            },
            lambda project_id, source_type="task", source_id=None, source_text="": _serialise(
                self.context_builder.implementation_plan(
                    project_id,
                    ImplementationPlanContextRequest(
                        source_type=source_type,
                        source_id=source_id,
                        source_text=source_text,
                    ),
                )
            ),
        )
        self._add(
            "context_build_packet",
            "Assemble build-packet context for the host model.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "task_id": {"type": "string"},
                    "source_text": {"type": "string", "default": ""},
                },
                "required": ["project_id"],
                "additionalProperties": False,
            },
            lambda project_id, task_id=None, source_text="": _serialise(
                self.context_builder.build_packet(
                    project_id,
                    BuildPacketContextRequest(task_id=task_id, source_text=source_text),
                )
            ),
        )

    # -- save-back wrappers ----------------------------------------------------

    def _register_llm_result_tools(self) -> None:
        # Currently we expose save_code_review_result in execution. The other
        # save-back endpoints stay HTTP-only for now to keep the MCP surface
        # focused; the host model can POST directly using its existing fetch.
        pass

    # -- safety / posture -----------------------------------------------------

    def _register_safety_tools(self) -> None:
        self._add(
            "get_mcp_safety_report",
            "Report current MCP safety posture (no GitHub writes, no shell, "
            "tool inventory, sqlite path, provider mode, memory isolation).",
            {"type": "object", "properties": {}, "additionalProperties": False},
            self._safety_report,
        )

    def _register_resource_change_tools(self) -> None:
        self._add(
            "list_changed_resources",
            "List cto-os:// resource URIs that have changed since the given "
            "ISO-8601 timestamp (UTC). Use this to incrementally refresh "
            "host-side caches without polling individual resources.",
            {
                "type": "object",
                "properties": {
                    "since": {
                        "type": "string",
                        "description": "ISO-8601 UTC timestamp. Returns changes strictly after this moment.",
                    },
                    "limit": {"type": "integer", "default": 200, "minimum": 1, "maximum": 1000},
                },
                "additionalProperties": False,
            },
            self._list_changed_resources,
        )

    def _list_changed_resources(self, since: str | None = None, limit: int = 200):
        events = self.change_recorder.list_since(since=since, limit=limit)
        return _serialise(events)

    def _safety_report(self):
        import os as _os
        from .models import MCPSafetyReport

        names = [tool.name for tool in self.tools()]
        github_writes = [n for n in names if "create_github" in n or "github_create" in n]
        shell = [n for n in names if n in {"run_command", "execute", "shell"}]

        write_tools = [
            n
            for n in names
            if n.startswith("save_")
            or n.startswith("create_")
            or n.startswith("update_")
            or n == "pin_memory"
        ]
        preview_tools = [n for n in names if n.startswith("preview_")]
        read_tools = sorted(set(names) - set(write_tools) - set(preview_tools))

        try:
            with self.store._connect() as conn:
                row = conn.execute("PRAGMA journal_mode").fetchone()
                journal_mode = row[0] if row else ""
        except Exception:
            journal_mode = ""

        payload = MCPSafetyReport(
            github_writes_in_mcp=bool(github_writes),
            shell_in_mcp=bool(shell),
            write_tools=sorted(write_tools),
            preview_tools=sorted(preview_tools),
            read_tools=read_tools,
            sqlite_path=str(self.store.path),
            sqlite_journal_mode=journal_mode,
            provider_mode=_os.getenv("CTO_OS_LLM_PROVIDER", "deterministic"),
            auto_reconcile_env=_os.getenv("CTO_OS_ALLOW_AUTO_RECONCILE", "0") == "1",
            github_writes_env=_os.getenv("CTO_OS_ALLOW_GITHUB_WRITES", "0") == "1",
            notifications_env=_os.getenv("CTO_OS_ENABLE_NOTIFICATIONS", "0") == "1",
            intake_env=_os.getenv("CTO_OS_ENABLE_WEBHOOK_INTAKE", "0") == "1",
        ).model_dump(mode="json")
        payload["read_only_mode"] = mcp_readonly_enabled()
        return payload

    # ---------------- Phase 15: entrypoint MCP tools (filling MCP coverage)

    def _register_phase15_entrypoints(self) -> None:
        self._add(
            "create_project",
            "Create a new CTO OS project. Idempotent on name.",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string", "default": ""},
                    "status": {"type": "string", "default": "active"},
                },
                "required": ["name"],
                "additionalProperties": False,
            },
            self._create_project,
        )
        self._add(
            "create_repository",
            "Register a local repository for an existing project.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "name": {"type": "string"},
                    "local_path": {"type": "string"},
                    "provider": {"type": "string", "default": "local"},
                    "url": {"type": "string", "default": ""},
                    "default_branch": {"type": "string", "default": "main"},
                    "notes": {"type": "string", "default": ""},
                },
                "required": ["project_id", "name", "local_path"],
                "additionalProperties": False,
            },
            self._create_repository,
        )
        self._add(
            "scan_repository",
            "Run a fresh repo scan: detect tech stack, route map, key files, "
            "code symbols, dependencies. Honors .gitignore.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "repository_id": {"type": "string"},
                },
                "required": ["project_id", "repository_id"],
                "additionalProperties": False,
            },
            self._scan_repository,
        )
        self._add(
            "index_repo_to_memory",
            "Persist the latest repo scan's summary/architecture/key-files/commands "
            "as project memories.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "repository_id": {"type": "string"},
                },
                "required": ["project_id", "repository_id"],
                "additionalProperties": False,
            },
            self._index_repo_to_memory,
        )
        self._add(
            "summarize_build_session",
            "Recompute the session's summary from currently-linked artifacts.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "session_id": {"type": "string"},
                },
                "required": ["project_id", "session_id"],
                "additionalProperties": False,
            },
            self._summarize_build_session,
        )
        self._add(
            "generate_retrospective",
            "Generate a post-ship retrospective for a build session or task.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "build_session_id": {"type": "string"},
                    "task_id": {"type": "string"},
                    "save_lessons_to_memory": {"type": "boolean", "default": True},
                    "create_decision": {"type": "boolean", "default": True},
                    "create_follow_up_tasks": {"type": "boolean", "default": True},
                    "pin_to_source_of_truth": {"type": "boolean", "default": False},
                },
                "required": ["project_id"],
                "additionalProperties": False,
            },
            self._generate_retrospective,
        )
        self._add(
            "review_diff_from_git",
            "Pull the working-tree diff for a repo and run review_diff on it. "
            "No GitHub writes. Read-only on git.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "repository_id": {"type": "string"},
                    "task_id": {"type": "string"},
                    "branch_plan_id": {"type": "string"},
                    "create_follow_up_tasks": {"type": "boolean", "default": False},
                },
                "required": ["project_id", "repository_id"],
                "additionalProperties": False,
            },
            self._review_diff_from_git,
        )
        self._add(
            "git_check_ignore",
            "Read-only: returns which of the given paths are gitignored.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "repository_id": {"type": "string"},
                    "paths": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["project_id", "repository_id", "paths"],
                "additionalProperties": False,
            },
            self._git_check_ignore,
        )
        self._add(
            "git_ls_files",
            "Read-only: list tracked + untracked-but-not-ignored files (capped).",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "repository_id": {"type": "string"},
                    "pattern": {"type": "string"},
                    "limit": {"type": "integer", "default": 500, "minimum": 1, "maximum": 5000},
                },
                "required": ["project_id", "repository_id"],
                "additionalProperties": False,
            },
            self._git_ls_files,
        )

    def _create_project(self, name, description="", status="active"):
        from .models import ProjectCreate

        existing = next((p for p in self.store.list_projects() if p.name == name), None)
        if existing is not None:
            return _serialise(existing)
        project = self.store.create_project(
            ProjectCreate(name=name, description=description, status=status)
        )
        return _serialise(project)

    def _create_repository(
        self,
        project_id,
        name,
        local_path,
        provider="local",
        url="",
        default_branch="main",
        notes="",
    ):
        from .models import RepositoryCreate, RepositoryProvider

        existing = next(
            (
                r
                for r in self.store.list_repositories(project_id)
                if r.local_path == local_path
            ),
            None,
        )
        if existing is not None:
            return _serialise(existing)
        try:
            provider_enum = RepositoryProvider(provider)
        except ValueError:
            provider_enum = RepositoryProvider.local
        repo = self.store.create_repository(
            project_id,
            RepositoryCreate(
                provider=provider_enum,
                name=name,
                local_path=local_path,
                url=url,
                default_branch=default_branch,
                notes=notes,
            ),
        )
        return _serialise(repo)

    def _scan_repository(self, project_id, repository_id):
        scan = self.repo_operator.scan_repository(project_id, repository_id)
        return _serialise(scan)

    def _index_repo_to_memory(self, project_id, repository_id):
        memories = self.repo_operator.index_repo_to_memory(project_id, repository_id)
        return _serialise(memories)

    def _summarize_build_session(self, project_id, session_id):
        session = self.repo_operator.summarize_build_session(project_id, session_id)
        return _serialise(session)

    def _generate_retrospective(self, project_id, **kwargs):
        from .models import RetrospectiveGenerateRequest
        from .retrospective_generator import RetrospectiveGenerator

        request = RetrospectiveGenerateRequest(**kwargs)
        generator = RetrospectiveGenerator(self.store, self.memory_engine)
        retro = generator.generate(project_id, request)
        return _serialise(retro)

    def _review_diff_from_git(
        self,
        project_id,
        repository_id,
        task_id=None,
        branch_plan_id=None,
        create_follow_up_tasks=False,
    ):
        from .models import CodeReviewCreate
        from .review_router import ReviewRouter

        repository = self.store.get_repository(project_id, repository_id)
        diff_text = self.git_reader.read_diff(repository)
        if not diff_text.strip():
            return {
                "isError": True,
                "blocked": False,
                "reason": "No working-tree diff to review (git diff was empty).",
                "tool": "review_diff_from_git",
            }
        # Phase 16.4: route BEFORE running the (potentially expensive)
        # full deterministic review. The routing decision is attached
        # to the CodeReview record so future audits can see why this
        # diff was tagged at the intensity it was.
        routing = ReviewRouter().route_from_working_tree(
            repository, include_working_tree_summary=False,
        )
        review = self.repo_operator.review_diff(
            project_id,
            CodeReviewCreate(
                diff_text=diff_text,
                repository_id=repository_id,
                task_id=task_id,
                branch_plan_id=branch_plan_id,
                create_follow_up_tasks=create_follow_up_tasks,
            ),
        )
        # Persist routing metadata on the saved review.
        review.routing = routing
        self.store.save_code_review(review)
        return _serialise(review)

    def _git_check_ignore(self, project_id, repository_id, paths):
        repository = self.store.get_repository(project_id, repository_id)
        return self.git_reader.check_ignore(repository, list(paths or []))

    def _git_ls_files(self, project_id, repository_id, pattern=None, limit=500):
        repository = self.store.get_repository(project_id, repository_id)
        return self.git_reader.ls_files(repository, pattern=pattern, limit=limit)

    # -- phase 16.5 — classifier audit -----------------------------------------

    def _register_phase16_classifier_tools(self) -> None:
        self._add(
            "classify_repo_files",
            "Read-only audit window into the file classifier. Returns the "
            "semantic type, confidence, and rules_triggered for each file in "
            "the repo's last scan. Filter by type or noise-only to see what "
            "the rest of CTO OS suppresses by default and why.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "repository_id": {"type": "string"},
                    "only_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "If set, return only files whose "
                                       "semantic_type matches one of these values.",
                    },
                    "only_noise": {
                        "type": "boolean",
                        "default": False,
                        "description": "If true, return only files classified "
                                       "as noise (lockfile / generated / "
                                       "vendored / snapshot / build_artifact).",
                    },
                    "limit": {
                        "type": "integer", "default": 500, "minimum": 1, "maximum": 5000,
                    },
                },
                "required": ["project_id", "repository_id"],
                "additionalProperties": False,
            },
            self._classify_repo_files,
        )

    def _classify_repo_files(
        self,
        project_id,
        repository_id,
        only_types=None,
        only_noise=False,
        limit=500,
    ):
        from .file_classifier import NOISE_TYPES

        files = self.store.list_repo_files(project_id, repository_id)
        wanted: set[str] | None = None
        if only_types:
            wanted = {str(t).lower() for t in only_types}
        noise_set = {t.value for t in NOISE_TYPES}
        out: list[dict[str, object]] = []
        for f in files:
            type_value = f.semantic_type.value
            if only_noise and type_value not in noise_set:
                continue
            if wanted is not None and type_value not in wanted:
                continue
            out.append({
                "path": f.path,
                "semantic_type": type_value,
                "confidence": f.classification_confidence.value,
                "rules_triggered": list(f.classification_rules),
                "is_noise": type_value in noise_set,
            })
            if len(out) >= limit:
                break
        return {
            "items": out,
            "returned": len(out),
            "total_files": len(files),
            "noise_types": sorted(noise_set),
        }

    # -- phase 16.1 — working tree intelligence --------------------------------

    def _register_phase16_working_tree_tools(self) -> None:
        self._add(
            "summarize_working_tree",
            "Read-only situational awareness for the current working tree: "
            "what changed since HEAD, grouped into clusters (directory + "
            "semantic) and tagged with risks (migration / schema / env / "
            "dependency_bump / auth / large_diff / infra / ci / "
            "source_changed_without_test). Every cluster and risk carries "
            "rules_triggered + evidence so the operator can verify each "
            "flag. Raw facts (full changed_files list, noise_suppressed "
            "list, raw `git diff --stat` output) are always included.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "repository_id": {"type": "string"},
                },
                "required": ["project_id", "repository_id"],
                "additionalProperties": False,
            },
            self._summarize_working_tree,
        )

    def _summarize_working_tree(self, project_id, repository_id):
        from .working_tree import WorkingTreeAnalyzer

        repository = self.store.get_repository(project_id, repository_id)
        analyzer = WorkingTreeAnalyzer.default()
        summary = analyzer.analyze(repository)
        return _serialise(summary)

    # -- phase 16.4 — real review routing --------------------------------------

    def _register_phase16_review_routing_tools(self) -> None:
        self._add(
            "route_review",
            "Read-only: pick an appropriate code-review intensity from "
            "the Phase 16.5 file classifier + Phase 16.1 working-tree "
            "risks. Returns selected_intensity, recommended_intensity "
            "(distinct only when an override is applied), confidence, "
            "rules_triggered, evidence, risks_considered, and the full "
            "routes_considered list. If diff_text is supplied the router "
            "parses that diff; otherwise it analyzes the current working "
            "tree. If intensity_override is supplied the operator's "
            "choice is honored but the recommended route is still "
            "reported so the override is auditable.",
            {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "repository_id": {"type": "string"},
                    "diff_text": {
                        "type": "string",
                        "description": "Optional raw unified diff. When "
                        "supplied, the router skips git and routes that "
                        "text. When omitted, uses the current working tree.",
                    },
                    "intensity_override": {
                        "type": "string",
                        "enum": [
                            "lightweight", "full", "security", "migration",
                            "dependency", "config", "docs_only",
                        ],
                        "description": "Override the routing decision. The "
                        "recommended route is still reported.",
                    },
                    "include_working_tree_summary": {
                        "type": "boolean",
                        "default": True,
                        "description": "Embed the full WorkingTreeSummary "
                        "on the result so the operator can drill into "
                        "raw facts. Ignored when diff_text is supplied.",
                    },
                },
                "required": ["project_id", "repository_id"],
                "additionalProperties": False,
            },
            self._route_review,
        )

    def _route_review(
        self,
        project_id,
        repository_id,
        diff_text=None,
        intensity_override=None,
        include_working_tree_summary=True,
    ):
        from .models import ReviewIntensity
        from .review_router import ReviewRouter

        override = (
            ReviewIntensity(intensity_override) if intensity_override else None
        )
        router = ReviewRouter()
        if diff_text:
            result = router.route_from_diff_text(diff_text, intensity_override=override)
        else:
            repository = self.store.get_repository(project_id, repository_id)
            result = router.route_from_working_tree(
                repository,
                intensity_override=override,
                include_working_tree_summary=include_working_tree_summary,
            )
        return _serialise(result)
