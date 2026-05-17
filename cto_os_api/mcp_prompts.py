"""Phase 11 — MCP prompt template registry.

Prompts are inert text the host can fetch with ``prompts/get``. They describe
which MCP tools/resources to call for a given workflow. They never execute
anything.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MCPPromptArgument:
    name: str
    description: str
    required: bool = True


@dataclass(frozen=True)
class MCPPromptDefinition:
    name: str
    description: str
    arguments: list[MCPPromptArgument]


def _msg(role: str, text: str) -> dict[str, Any]:
    return {"role": role, "content": {"type": "text", "text": text}}


class MCPPromptRegistry:
    def __init__(self) -> None:
        self._defs: dict[str, MCPPromptDefinition] = {}
        self._render: dict[str, Any] = {}
        self._register()

    def _add(
        self,
        name: str,
        description: str,
        arguments: list[MCPPromptArgument],
        renderer,
    ) -> None:
        self._defs[name] = MCPPromptDefinition(name, description, arguments)
        self._render[name] = renderer

    def list(self) -> list[MCPPromptDefinition]:
        return list(self._defs.values())

    def get(self, name: str, arguments: dict[str, str] | None = None) -> dict[str, Any]:
        if name not in self._defs:
            raise KeyError(name)
        args = arguments or {}
        defn = self._defs[name]
        for arg in defn.arguments:
            if arg.required and not args.get(arg.name):
                raise ValueError(f"Prompt '{name}' requires argument '{arg.name}'.")
        messages = self._render[name](args)
        return {"description": defn.description, "messages": messages}

    # --------------------------------------------------------- registration

    def _register(self) -> None:
        self._add(
            "cto_os_start_task",
            "Begin working on a task: hydrate project brief + source-of-truth, "
            "inspect repo, plan, generate a build packet.",
            [
                MCPPromptArgument("project_id", "Target project id"),
                MCPPromptArgument("task_id", "Task id to start", required=False),
            ],
            self._start_task,
        )
        self._add(
            "cto_os_review_diff",
            "Review a diff using the host model. CTO OS assembles full context; "
            "you produce structured JSON and call save_code_review_result.",
            [
                MCPPromptArgument("project_id", "Target project id"),
                MCPPromptArgument("diff", "Unified diff text to review"),
                MCPPromptArgument("task_id", "Linked task id", required=False),
            ],
            self._review_diff,
        )
        self._add(
            "cto_os_retrospective",
            "Generate a post-ship retrospective for a build session.",
            [
                MCPPromptArgument("project_id", "Target project id"),
                MCPPromptArgument("build_session_id", "Build session id", required=False),
            ],
            self._retrospective,
        )
        self._add(
            "cto_os_weekly_review",
            "Produce a weekly review: shipped + risks + suggestions + recommended actions.",
            [
                MCPPromptArgument("project_id", "Optional project filter", required=False),
            ],
            self._weekly_review,
        )
        self._add(
            "cto_os_save_lesson",
            "Persist a lesson learned to project memory.",
            [
                MCPPromptArgument("project_id", "Target project id"),
                MCPPromptArgument("lesson_title", "Short lesson title"),
                MCPPromptArgument("lesson_body", "Body of the lesson"),
            ],
            self._save_lesson,
        )
        self._add(
            "cto_os_generate_build_packet",
            "Assemble a build packet for a task and persist it via the host model.",
            [
                MCPPromptArgument("project_id", "Target project id"),
                MCPPromptArgument("task_id", "Task to packet", required=False),
                MCPPromptArgument("source_text", "Optional free-text source", required=False),
            ],
            self._build_packet,
        )
        self._add(
            "cto_os_daily_review",
            "Pull today's review (blocked tasks, risks, stale sessions, suggestions, shipped, next actions).",
            [],
            self._daily_review,
        )

    # ------------------------------------------------------------ renderers

    def _start_task(self, args: dict[str, str]) -> list[dict[str, Any]]:
        project_id = args["project_id"]
        task_id = args.get("task_id", "")
        return [
            _msg(
                "system",
                "You are operating inside the CTO OS via MCP. Always hydrate the "
                "project brief and pinned source-of-truth before acting. Project "
                "memory is project-scoped; do not widen scope. Never run shell or "
                "write to GitHub from MCP.",
            ),
            _msg(
                "user",
                "\n".join(
                    [
                        f"Start task for project {project_id}" + (f" / task {task_id}" if task_id else ""),
                        "",
                        "Steps:",
                        "1. Read resource cto-os://projects/{pid}/brief".format(pid=project_id),
                        "2. Read resource cto-os://projects/{pid}/source-of-truth".format(pid=project_id),
                        "3. Read resource cto-os://projects/{pid}/tasks and pick the task".format(pid=project_id),
                        "4. Call tool list_repositories + get_repo_scan + get_git_status",
                        "5. Call tool context_build_packet with project_id + task_id",
                        "6. Produce a JSON build packet matching the schema",
                        "7. POST it to the bundle's save_endpoint or call save_build_packet via REST",
                    ]
                ),
            ),
        ]

    def _review_diff(self, args: dict[str, str]) -> list[dict[str, Any]]:
        project_id = args["project_id"]
        diff = args["diff"]
        task_id = args.get("task_id", "")
        return [
            _msg(
                "system",
                "You are a careful senior code reviewer. Escalate (never "
                "de-escalate) any security finding. Reply with JSON only.",
            ),
            _msg(
                "user",
                "\n".join(
                    [
                        f"Project {project_id}" + (f", task {task_id}" if task_id else ""),
                        "",
                        "Steps:",
                        "1. Call tool context_code_review with project_id + diff_text + task_id",
                        "2. Read the bundle's output_schema",
                        "3. Produce JSON matching the schema",
                        "4. Call tool save_code_review_result with the JSON plus project_id and diff_text",
                        "",
                        "Diff:",
                        diff[:8000],
                    ]
                ),
            ),
        ]

    def _retrospective(self, args: dict[str, str]) -> list[dict[str, Any]]:
        project_id = args["project_id"]
        session_id = args.get("build_session_id", "")
        return [
            _msg(
                "system",
                "Generate a post-ship retrospective grounded in real artifacts. "
                "Reply with JSON matching the bundle's output_schema.",
            ),
            _msg(
                "user",
                "\n".join(
                    [
                        f"Retrospective for project {project_id}"
                        + (f" / session {session_id}" if session_id else ""),
                        "",
                        "Steps:",
                        "1. Call tool context_retrospective with project_id + build_session_id",
                        "2. Read the bundle (build_session, code_reviews, test_runs, source_of_truth, open_risks)",
                        "3. Produce JSON matching output_schema",
                        "4. POST it to the bundle's save_endpoint",
                    ]
                ),
            ),
        ]

    def _weekly_review(self, args: dict[str, str]) -> list[dict[str, Any]]:
        project_id = args.get("project_id", "")
        return [
            _msg(
                "system",
                "Summarise what shipped, what risks are open, and what the most "
                "valuable next actions are. Keep it concrete; cite artifacts.",
            ),
            _msg(
                "user",
                "\n".join(
                    [
                        "Steps:",
                        "1. Read resource cto-os://system/control-room",
                        "2. Read resource cto-os://system/shipped",
                        ("3. Read resource cto-os://projects/{pid}/shipped".format(pid=project_id) if project_id else "3. (optional) pick one project's cto-os://projects/{id}/shipped"),
                        "4. Produce a markdown summary: shipped, risks, blocked, next actions",
                    ]
                ),
            ),
        ]

    def _save_lesson(self, args: dict[str, str]) -> list[dict[str, Any]]:
        return [
            _msg("system", "Persist a lesson to project memory via MCP."),
            _msg(
                "user",
                "Call tool save_lesson_to_memory with:\n"
                f"  project_id={args['project_id']}\n"
                f"  title={args['lesson_title']}\n"
                f"  content={args['lesson_body']}\n"
                "Set pinned=true if this should join source-of-truth.",
            ),
        ]

    def _daily_review(self, args: dict[str, str]) -> list[dict[str, Any]]:
        return [
            _msg(
                "system",
                "Generate a short daily CTO review grounded in real CTO OS state. "
                "Use the resources for facts; the host model only formats + recommends.",
            ),
            _msg(
                "user",
                "\n".join(
                    [
                        "Steps:",
                        "1. POST /system/daily-review/generate (returns DailyReview with markdown).",
                        "2. Read cto-os://system/control-room for context.",
                        "3. Read cto-os://system/shipped for what shipped this week.",
                        "4. Reply with the markdown from step 1, then add 3-5 sharper recommended next actions.",
                    ]
                ),
            ),
        ]

    def _build_packet(self, args: dict[str, str]) -> list[dict[str, Any]]:
        project_id = args["project_id"]
        task_id = args.get("task_id", "")
        source_text = args.get("source_text", "")
        return [
            _msg(
                "system",
                "Produce a build packet a downstream coding agent can execute. "
                "Reply with JSON matching the bundle's output_schema.",
            ),
            _msg(
                "user",
                "\n".join(
                    [
                        f"Project {project_id}" + (f", task {task_id}" if task_id else ""),
                        "",
                        "Steps:",
                        "1. Call tool context_build_packet with project_id + task_id + source_text",
                        "2. Read the bundle (task, source_of_truth, recent_memory, decisions)",
                        "3. Produce JSON matching output_schema",
                        "4. POST it to the bundle's save_endpoint",
                        "",
                        f"source_text: {source_text}" if source_text else "",
                    ]
                ),
            ),
        ]
