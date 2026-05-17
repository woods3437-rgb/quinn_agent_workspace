"""Phase 8 — post-ship retrospective generator.

Aggregates everything tied to a ``BuildSession`` (or a free-standing task)
into a structured ``PostShipRetrospective`` row, with optional feedback into
memory + decisions + follow-up tasks + project brief metadata.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .llm import LLMService
from .memory_engine import LocalMemoryEngine
from .models import (
    BuildSession,
    BuildSessionStatus,
    DecisionCreate,
    ImpactLevel,
    MemoryCreate,
    PostShipRetrospective,
    RetrospectiveGenerateRequest,
    Task,
    TaskCategory,
    TaskCreate,
    TaskPriority,
)
from .sqlite_store import SQLiteStore
from .structured_outputs import (
    StructuredRetrospectiveOutput,
    validate_structured_output,
)


class RetrospectiveGenerator:
    def __init__(
        self,
        store: SQLiteStore,
        memory_engine: LocalMemoryEngine,
        llm: LLMService | None = None,
    ) -> None:
        self.store = store
        self.memory_engine = memory_engine
        self.llm = llm or LLMService()

    def generate(
        self, project_id: str, request: RetrospectiveGenerateRequest
    ) -> PostShipRetrospective:
        session = self._resolve_session(project_id, request)
        task = self._resolve_task(project_id, request, session)
        context = self._collect_context(project_id, session, task)

        structured = self._call_llm(project_id, context)
        retro = PostShipRetrospective(
            project_id=project_id,
            build_session_id=session.id if session else None,
            task_id=task.id if task else None,
            title=self._title(session, task),
            summary=structured.summary or self._fallback_summary(context),
            what_changed=structured.what_changed or context["changed_files"],
            what_worked=structured.what_worked or self._derive_worked(context),
            what_broke=structured.what_broke or self._derive_broke(context),
            test_results=structured.test_results or self._test_summary(context),
            risks_found=structured.risks_found or [risk.title for risk in context["open_risks"]],
            follow_up_tasks=structured.follow_up_tasks,
            lessons_learned=structured.lessons_learned
            or (session.lessons_learned if session else ""),
        )

        if request.save_lessons_to_memory and retro.lessons_learned:
            memory = self.store.create_memory(
                project_id,
                MemoryCreate(
                    title=f"Retrospective lessons: {retro.title}",
                    content=retro.lessons_learned,
                    tags=["retrospective", "lesson"],
                    pinned=request.pin_to_source_of_truth,
                    source="retrospective",
                ),
            )
            self.memory_engine.index_memory(memory)
            retro.memory_ids_created.append(memory.id)

        if request.create_decision and retro.summary:
            decision = self.store.create_decision(
                project_id,
                DecisionCreate(
                    title=f"Retrospective: {retro.title}",
                    context=retro.summary,
                    decision=retro.lessons_learned or retro.summary[:600],
                    rationale="Captured automatically from build session retrospective.",
                    impact_level=ImpactLevel.medium if retro.risks_found else ImpactLevel.low,
                ),
            )
            retro.decision_ids_created.append(decision.id)

        if request.create_follow_up_tasks and retro.follow_up_tasks:
            for follow_up in retro.follow_up_tasks:
                followup_task = self.store.create_task(
                    project_id,
                    TaskCreate(
                        title=follow_up[:140],
                        description=f"Auto-generated follow-up from retrospective {retro.title}.",
                        priority=TaskPriority.medium,
                        category=TaskCategory.ops,
                        linked_memory_ids=retro.memory_ids_created,
                        linked_decision_ids=retro.decision_ids_created,
                    ),
                )
                retro.follow_up_task_ids.append(followup_task.id)

        return self.store.save_retrospective(retro)

    # ------------------------------------------------------------ collectors

    def _resolve_session(
        self,
        project_id: str,
        request: RetrospectiveGenerateRequest,
    ) -> BuildSession | None:
        if not request.build_session_id:
            return None
        return next(
            (
                item
                for item in self.store.list_build_sessions(project_id)
                if item.id == request.build_session_id
            ),
            None,
        )

    def _resolve_task(
        self,
        project_id: str,
        request: RetrospectiveGenerateRequest,
        session: BuildSession | None,
    ) -> Task | None:
        task_id = request.task_id or (session.task_id if session else None)
        if not task_id:
            return None
        try:
            return self.store.get_task(project_id, task_id)
        except KeyError:
            return None

    def _collect_context(
        self,
        project_id: str,
        session: BuildSession | None,
        task: Task | None,
    ) -> dict[str, Any]:
        reviews = []
        tests = []
        impl_reviews = []
        changed_files: list[str] = []
        if session is not None:
            review_index = {item.id: item for item in self.store.list_code_reviews(project_id)}
            reviews = [
                review_index[rid]
                for rid in session.linked_code_review_ids
                if rid in review_index
            ]
            run_index = {item.id: item for item in self.store.list_test_runs(project_id)}
            tests = [
                run_index[tid] for tid in session.linked_test_run_ids if tid in run_index
            ]
            impl_index = {item.id: item for item in self.store.list_reviews(project_id)}
            impl_reviews = [
                impl_index[iid]
                for iid in session.linked_implementation_review_ids
                if iid in impl_index
            ]

        branch_plan = None
        if session and session.linked_branch_plan_id:
            try:
                branch_plan = self.store.get_branch_plan(project_id, session.linked_branch_plan_id)
                changed_files = branch_plan.files_to_change[:20]
            except KeyError:
                branch_plan = None

        pr_packet = None
        if session and session.linked_pr_packet_id:
            try:
                pr_packet = self.store.get_pr_packet(project_id, session.linked_pr_packet_id)
            except KeyError:
                pr_packet = None

        open_risks = self.store.list_risks(project_id)[:5]

        return {
            "session": session,
            "task": task,
            "reviews": reviews,
            "tests": tests,
            "impl_reviews": impl_reviews,
            "branch_plan": branch_plan,
            "pr_packet": pr_packet,
            "open_risks": open_risks,
            "changed_files": changed_files,
        }

    # ----------------------------------------------------------------- text

    def _title(self, session: BuildSession | None, task: Task | None) -> str:
        if session:
            return session.title
        if task:
            return f"Retrospective for {task.title}"
        return "Retrospective"

    def _fallback_summary(self, context: dict[str, Any]) -> str:
        parts: list[str] = []
        session = context["session"]
        if session:
            parts.append(f"Build session '{session.title}' ({session.status.value}).")
        task = context["task"]
        if task:
            parts.append(f"Task: {task.title} ({task.status.value}).")
        if context["pr_packet"]:
            packet = context["pr_packet"]
            parts.append(
                f"PR packet: {packet.title} (#{packet.github_pr_number or 'n/a'})."
            )
        return " ".join(parts) or "Retrospective generated."

    def _derive_worked(self, context: dict[str, Any]) -> list[str]:
        worked: list[str] = []
        passed = [run for run in context["tests"] if run.status.value == "passed"]
        if passed:
            worked.append(f"{len(passed)} test run(s) passed.")
        approved_reviews = [
            review
            for review in context["reviews"]
            if review.approval_recommendation.value == "approve"
        ]
        if approved_reviews:
            worked.append(f"{len(approved_reviews)} code review(s) approved.")
        session = context["session"]
        if session and session.status == BuildSessionStatus.completed:
            worked.append("Build session reached completed status.")
        return worked

    def _derive_broke(self, context: dict[str, Any]) -> list[str]:
        broke: list[str] = []
        failed = [run for run in context["tests"] if run.status.value == "failed"]
        if failed:
            broke.append(f"{len(failed)} test run(s) failed.")
        blocked_reviews = [
            review
            for review in context["reviews"]
            if review.approval_recommendation.value == "block"
        ]
        if blocked_reviews:
            broke.append(f"{len(blocked_reviews)} code review(s) blocked.")
        session = context["session"]
        if session and session.status == BuildSessionStatus.blocked:
            broke.append("Build session ended in 'blocked' state.")
        return broke

    def _test_summary(self, context: dict[str, Any]) -> str:
        if not context["tests"]:
            return "No test runs recorded."
        passed = sum(1 for run in context["tests"] if run.status.value == "passed")
        failed = sum(1 for run in context["tests"] if run.status.value == "failed")
        return f"{passed} passed, {failed} failed, {len(context['tests'])} total."

    # ---------------------------------------------------------------- LLM

    def _call_llm(
        self, project_id: str, context: dict[str, Any]
    ) -> StructuredRetrospectiveOutput:
        prompt = self._build_prompt(context)
        result = self.llm.generate(
            "You are a careful CTO writing a post-ship retrospective. "
            "Return STRICT JSON matching the requested schema.",
            prompt,
            {"project_id": project_id},
        )
        if result.get("fallback") or result.get("provider") == "deterministic":
            return StructuredRetrospectiveOutput()
        validated = validate_structured_output(StructuredRetrospectiveOutput, result.text)
        if not validated.valid:
            return StructuredRetrospectiveOutput()
        return StructuredRetrospectiveOutput.model_validate(validated.data)

    def _build_prompt(self, context: dict[str, Any]) -> str:
        session = context["session"]
        task = context["task"]
        tests = context["tests"]
        reviews = context["reviews"]
        return (
            "Generate a JSON object with keys: summary, what_changed, what_worked, "
            "what_broke, test_results, risks_found, follow_up_tasks, lessons_learned.\n\n"
            f"Build session: {session.title if session else 'n/a'} "
            f"({session.status.value if session else 'n/a'})\n"
            f"Task: {task.title if task else 'n/a'}\n"
            f"Test runs: {len(tests)} ("
            f"{sum(1 for r in tests if r.status.value == 'passed')} passed, "
            f"{sum(1 for r in tests if r.status.value == 'failed')} failed)\n"
            f"Code reviews: {len(reviews)}\n"
            f"Open risks: {[r.title for r in context['open_risks']]}\n"
        )
