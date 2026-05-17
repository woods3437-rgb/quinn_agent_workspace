"""Phase 10 — Save-back endpoints for host-model (Claude Code) results.

The four context-builder bundles return a `save_endpoint`; this module
implements those endpoints. Each one validates the host model's structured
JSON and persists it as a real CTO OS entity (CodeReview / Retrospective /
GeneratedOutput / BuildPacket).
"""
from __future__ import annotations

from .memory_engine import LocalMemoryEngine
from .models import (
    ApprovalRecommendation,
    BuildPacket,
    BuildPacketSaveRequest,
    CodeReview,
    CodeReviewSaveRequest,
    DecisionCreate,
    GeneratedOutput,
    ImpactLevel,
    ImplementationPlanSaveRequest,
    MemoryCreate,
    PostShipRetrospective,
    RetrospectiveSaveRequest,
    TaskCategory,
    TaskCreate,
    TaskPriority,
)
from .sqlite_store import SQLiteStore


_VALID_RECOMMENDATIONS = {"approve", "revise", "block"}


class LLMResultsService:
    def __init__(self, store: SQLiteStore, memory_engine: LocalMemoryEngine) -> None:
        self.store = store
        self.memory_engine = memory_engine

    # ----------------------------------------------------------- code review

    def save_code_review(
        self, project_id: str, request: CodeReviewSaveRequest
    ) -> CodeReview:
        if request.recommendation not in _VALID_RECOMMENDATIONS:
            raise ValueError(
                f"recommendation must be one of {sorted(_VALID_RECOMMENDATIONS)}"
            )
        findings: list[str] = []
        if request.blocking_issues:
            findings.extend(f"Blocking: {item}" for item in request.blocking_issues)
        if request.security_concerns:
            findings.extend(f"Security: {item}" for item in request.security_concerns)
        if request.non_blocking_suggestions:
            findings.extend(f"Suggestion: {item}" for item in request.non_blocking_suggestions)
        if not findings:
            findings.append("No issues recorded.")

        risk = "low"
        if request.recommendation == "block":
            risk = "high"
        elif request.recommendation == "revise":
            risk = "medium"

        follow_up_ids: list[str] = []
        if request.create_follow_up_tasks and request.recommendation != "approve":
            task = self.store.create_task(
                project_id,
                TaskCreate(
                    title="Follow up code review finding",
                    description="\n".join(findings),
                    priority=TaskPriority.high,
                    category=TaskCategory.backend,
                ),
            )
            follow_up_ids.append(task.id)

        review = CodeReview(
            project_id=project_id,
            repository_id=request.repository_id,
            task_id=request.task_id,
            branch_plan_id=request.branch_plan_id,
            diff_text=request.diff_text,
            review_summary=request.summary[:600] or "Host-model code review.",
            findings=findings,
            risk_level=risk,
            test_recommendations=request.missing_tests
            or ["Add targeted tests for modified behavior."],
            approval_recommendation=ApprovalRecommendation(request.recommendation),
            follow_up_task_ids=follow_up_ids,
        )
        return self.store.save_code_review(review)

    # ---------------------------------------------------------- retrospective

    def save_retrospective(
        self, project_id: str, request: RetrospectiveSaveRequest
    ) -> PostShipRetrospective:
        retro = PostShipRetrospective(
            project_id=project_id,
            build_session_id=request.build_session_id,
            task_id=request.task_id,
            title=request.title or "Retrospective",
            summary=request.summary,
            what_changed=request.what_changed,
            what_worked=request.what_worked,
            what_broke=request.what_broke,
            test_results=request.test_results,
            risks_found=request.risks_found,
            follow_up_tasks=request.follow_up_tasks,
            lessons_learned=request.lessons_learned,
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
                    rationale="Captured from host-model retrospective.",
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

    # --------------------------------------------------- implementation plan

    def save_implementation_plan(
        self, project_id: str, request: ImplementationPlanSaveRequest
    ) -> GeneratedOutput:
        project = self.store.get_project(project_id)
        title = request.title or f"Implementation plan ({request.source_type})"
        output = GeneratedOutput(
            project_id=project_id,
            agent_id="engineering-builder",
            prompt=title,
            output=request.plan_markdown,
            metadata={
                "output_type": "implementation_plan",
                "source_type": request.source_type,
                "source_id": request.source_id,
            },
        )
        if request.save_output:
            self.store.save_output(output)
        return output

    # ---------------------------------------------------------- build packet

    def save_build_packet(
        self, project_id: str, request: BuildPacketSaveRequest
    ) -> BuildPacket:
        self.store.get_project(project_id)
        packet = BuildPacket(
            project_id=project_id,
            task_id=request.task_id,
            title=request.title,
            summary=request.summary,
            context=request.context,
            relevant_memories=[],
            relevant_decisions=[],
            architecture_notes=request.architecture_notes,
            implementation_steps=request.implementation_steps,
            files_likely_involved=request.files_likely_involved,
            acceptance_criteria=request.acceptance_criteria,
            test_plan=request.test_plan,
            rollback_plan=request.rollback_plan,
            codex_prompt=request.codex_prompt,
            claude_prompt=request.claude_prompt,
            cursor_prompt=request.cursor_prompt,
        )
        # Persist with the same shape `ExecutionEngine.generate_build_packet`
        # uses so listing endpoints work unchanged.
        self.store._insert_model(
            "build_packets",
            packet,
            project_id=packet.project_id,
            created_at=packet.created_at,
            task_id=packet.task_id,
        )
        if request.save_to_memory:
            memory = self.store.create_memory(
                project_id,
                MemoryCreate(
                    title=f"Build packet: {packet.title}",
                    content=packet.summary or packet.title,
                    tags=["build-packet"],
                    source="build_packet",
                ),
            )
            self.memory_engine.index_memory(memory)
        return packet
