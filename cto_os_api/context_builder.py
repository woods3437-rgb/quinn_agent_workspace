"""Phase 10 — Context bundles for the host model (Claude Code) to complete.

CTO OS assembles every artifact relevant to a task (memory, pinned source of
truth, decisions, repo intelligence, structured output schema, save-back URL)
into a single bundle. The host model fills in the JSON; the save endpoint
turns it back into a CTO OS entity.

In MCP mode, CTO OS itself never calls Anthropic / OpenAI for these flows.
"""
from __future__ import annotations

from typing import Any

from .memory_engine import LocalMemoryEngine
from .models import (
    BuildPacketContextRequest,
    CodeReviewContextRequest,
    ImplementationPlanContextRequest,
    LLMContextBundle,
    LLMContextKind,
    RetrospectiveContextRequest,
)
from .sqlite_store import SQLiteStore
from .structured_outputs import (
    StructuredCodeReviewOutput,
    StructuredRetrospectiveOutput,
)


def _schema(model) -> dict[str, Any]:
    try:
        return model.model_json_schema()
    except Exception:
        return {}


class ContextBuilder:
    def __init__(self, store: SQLiteStore, memory_engine: LocalMemoryEngine) -> None:
        self.store = store
        self.memory_engine = memory_engine

    # ---------------------------------------------------- code review context

    def code_review(
        self, project_id: str, request: CodeReviewContextRequest
    ) -> LLMContextBundle:
        project = self.store.get_project(project_id)
        task = (
            self.store.get_task(project_id, request.task_id)
            if request.task_id
            else None
        )
        branch = (
            self.store.get_branch_plan(project_id, request.branch_plan_id)
            if request.branch_plan_id
            else None
        )
        memories = self.memory_engine.search(
            project_id, task.title if task else "code review", limit=4
        )
        pinned = self.memory_engine.pinned_context(project_id)
        decisions = self.store.list_decisions(project_id)[:5]

        context = {
            "project": {"id": project.id, "name": project.name, "description": project.description},
            "task": (task.model_dump(mode="json") if task else None),
            "branch_plan": (branch.model_dump(mode="json") if branch else None),
            "memories": [m.model_dump(mode="json") for m in memories],
            "source_of_truth": [m.model_dump(mode="json") for m in pinned],
            "decisions": [d.model_dump(mode="json") for d in decisions],
            "diff_text": request.diff_text[:12000],
        }
        return LLMContextBundle(
            kind=LLMContextKind.code_review,
            project_id=project_id,
            system_instructions=(
                "You are a careful senior code reviewer for an internal CTO OS. "
                "Return ONLY a JSON object matching the schema. The reviewer's "
                "recommendation MUST escalate (not de-escalate) any deterministic "
                "security finding present in the diff."
            ),
            user_prompt=(
                "Review the diff using the context. Be concise and concrete. "
                "Follow the schema exactly."
            ),
            context=context,
            output_schema=_schema(StructuredCodeReviewOutput),
            save_endpoint=f"/projects/{project_id}/llm-results/code-review",
            save_payload_keys=[
                "diff_text",
                "task_id",
                "branch_plan_id",
                "repository_id",
                "recommendation",
                "summary",
                "blocking_issues",
                "non_blocking_suggestions",
                "missing_tests",
                "security_concerns",
                "acceptance_criteria_check",
                "confidence",
            ],
        )

    # ---------------------------------------------------- retrospective context

    def retrospective(
        self, project_id: str, request: RetrospectiveContextRequest
    ) -> LLMContextBundle:
        session = None
        if request.build_session_id:
            session = next(
                (s for s in self.store.list_build_sessions(project_id) if s.id == request.build_session_id),
                None,
            )
        task = (
            self.store.get_task(project_id, request.task_id or (session.task_id if session else ""))
            if (request.task_id or (session and session.task_id))
            else None
        )
        reviews = []
        tests = []
        if session:
            review_index = {r.id: r for r in self.store.list_code_reviews(project_id)}
            reviews = [review_index[r] for r in session.linked_code_review_ids if r in review_index]
            run_index = {r.id: r for r in self.store.list_test_runs(project_id)}
            tests = [run_index[r] for r in session.linked_test_run_ids if r in run_index]

        pinned = self.memory_engine.pinned_context(project_id)
        recent_memory = self.memory_engine.search(
            project_id, (task.title if task else (session.title if session else "retrospective")), limit=5
        )

        context = {
            "build_session": (session.model_dump(mode="json") if session else None),
            "task": (task.model_dump(mode="json") if task else None),
            "code_reviews": [r.model_dump(mode="json") for r in reviews],
            "test_runs": [t.model_dump(mode="json") for t in tests],
            "source_of_truth": [m.model_dump(mode="json") for m in pinned],
            "recent_memory": [m.model_dump(mode="json") for m in recent_memory],
            "open_risks": [
                r.model_dump(mode="json")
                for r in self.store.list_risks(project_id)
                if r.status.value == "open"
            ][:5],
        }
        return LLMContextBundle(
            kind=LLMContextKind.retrospective,
            project_id=project_id,
            system_instructions=(
                "You are writing a post-ship retrospective for an internal CTO OS. "
                "Return ONLY a JSON object matching the schema. Be honest about "
                "what broke and what worked; cite concrete artifacts from context."
            ),
            user_prompt="Produce the retrospective JSON for this build session.",
            context=context,
            output_schema=_schema(StructuredRetrospectiveOutput),
            save_endpoint=f"/projects/{project_id}/llm-results/retrospective",
            save_payload_keys=[
                "build_session_id",
                "task_id",
                "title",
                "summary",
                "what_changed",
                "what_worked",
                "what_broke",
                "test_results",
                "risks_found",
                "follow_up_tasks",
                "lessons_learned",
            ],
        )

    # ---------------------------------------------- implementation-plan context

    def implementation_plan(
        self, project_id: str, request: ImplementationPlanContextRequest
    ) -> LLMContextBundle:
        source_title = request.source_text or ""
        if request.source_type == "task" and request.source_id:
            try:
                task = self.store.get_task(project_id, request.source_id)
                source_title = task.title
            except KeyError:
                task = None
        else:
            task = None

        pinned = self.memory_engine.pinned_context(project_id)
        memories = self.memory_engine.search(project_id, source_title, limit=4)
        repos = self.store.list_repositories(project_id)

        context = {
            "task": (task.model_dump(mode="json") if task else None),
            "source_text": request.source_text,
            "source_of_truth": [m.model_dump(mode="json") for m in pinned],
            "recent_memory": [m.model_dump(mode="json") for m in memories],
            "repositories": [r.model_dump(mode="json") for r in repos],
        }
        return LLMContextBundle(
            kind=LLMContextKind.implementation_plan,
            project_id=project_id,
            system_instructions=(
                "You are the engineering builder for an internal CTO OS. "
                "Return a focused markdown implementation plan: files to change, "
                "steps in order, test commands, rollback. Keep it tight."
            ),
            user_prompt="Generate the implementation plan as markdown only.",
            context=context,
            output_schema={"type": "string", "format": "markdown"},
            save_endpoint=f"/projects/{project_id}/llm-results/implementation-plan",
            save_payload_keys=["source_type", "source_id", "title", "plan_markdown", "save_output"],
        )

    # -------------------------------------------------- build-packet context

    def build_packet(
        self, project_id: str, request: BuildPacketContextRequest
    ) -> LLMContextBundle:
        task = (
            self.store.get_task(project_id, request.task_id)
            if request.task_id
            else None
        )
        source_text = request.source_text or (task.description if task else "")
        pinned = self.memory_engine.pinned_context(project_id)
        memories = self.memory_engine.search(
            project_id, task.title if task else source_text[:80], limit=4
        )
        decisions = self.store.list_decisions(project_id)[:5]

        context = {
            "task": (task.model_dump(mode="json") if task else None),
            "source_text": source_text,
            "source_of_truth": [m.model_dump(mode="json") for m in pinned],
            "recent_memory": [m.model_dump(mode="json") for m in memories],
            "decisions": [d.model_dump(mode="json") for d in decisions],
        }
        return LLMContextBundle(
            kind=LLMContextKind.build_packet,
            project_id=project_id,
            system_instructions=(
                "You are producing a build packet (a handoff a downstream coding "
                "agent can execute). Return JSON matching the schema."
            ),
            user_prompt="Produce the build packet JSON for this task.",
            context=context,
            output_schema={
                "type": "object",
                "required": ["title", "implementation_steps", "acceptance_criteria"],
                "properties": {
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "context": {"type": "string"},
                    "architecture_notes": {"type": "string"},
                    "implementation_steps": {"type": "array", "items": {"type": "string"}},
                    "files_likely_involved": {"type": "array", "items": {"type": "string"}},
                    "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
                    "test_plan": {"type": "array", "items": {"type": "string"}},
                    "rollback_plan": {"type": "string"},
                    "codex_prompt": {"type": "string"},
                    "claude_prompt": {"type": "string"},
                    "cursor_prompt": {"type": "string"},
                },
            },
            save_endpoint=f"/projects/{project_id}/llm-results/build-packet",
            save_payload_keys=[
                "task_id",
                "title",
                "summary",
                "context",
                "architecture_notes",
                "implementation_steps",
                "files_likely_involved",
                "acceptance_criteria",
                "test_plan",
                "rollback_plan",
                "codex_prompt",
                "claude_prompt",
                "cursor_prompt",
                "save_to_memory",
            ],
        )
