from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from .memory_engine import LocalMemoryEngine
from .models import (
    ArchitectureGenerateRequest,
    BuildPacket,
    BuildPacketGenerateRequest,
    ExecutionEventType,
    ImplementationReviewCreate,
    Job,
    JobCreate,
    JobStatus,
    JobType,
    MemoryCreate,
    RoadmapGenerateRequest,
    TaskCategory,
    TaskCreate,
    TaskPriority,
    WorkflowRun,
    WorkflowRunCreate,
    WorkflowStatus,
)
from .sqlite_store import SQLiteStore
from .workspace_generators import WorkspaceGenerator
from .repo_operator import RepoOperator


LogCallback = Callable[[str, ExecutionEventType, str, str, str | None, str | None, dict | None], None]


DEFAULT_WORKFLOW_STEPS: dict[str, list[dict[str, Any]]] = {
    "Generate Product Build Packet": [
        {"type": "risk_scan", "title": "Refresh risks"},
        {"type": "github_packet", "title": "Generate build packet"},
    ],
    "Weekly CTO Review": [
        {"type": "risk_scan", "title": "Scan risk state"},
        {"type": "weekly_brief", "title": "Generate weekly CTO brief"},
    ],
    "Risk Scan + Mitigation Tasks": [
        {"type": "risk_scan", "title": "Generate risks"},
        {"type": "mitigation_tasks", "title": "Create mitigation tasks"},
    ],
    "Architecture Refresh": [
        {"type": "architecture_refresh", "title": "Generate architecture refresh"},
    ],
    "Roadmap to Tickets": [
        {"type": "roadmap_generate", "title": "Generate roadmap"},
        {"type": "roadmap_to_tasks", "title": "Create tickets"},
    ],
    "Implementation Review to Follow-up Tasks": [
        {"type": "implementation_review", "title": "Review implementation result"},
    ],
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class ExecutionEngine:
    def __init__(
        self,
        store: SQLiteStore,
        memory_engine: LocalMemoryEngine,
        workspace_generator: WorkspaceGenerator,
        log_event: LogCallback,
        repo_operator: RepoOperator | None = None,
    ) -> None:
        self.store = store
        self.memory_engine = memory_engine
        self.workspace_generator = workspace_generator
        self.log_event = log_event
        self.repo_operator = repo_operator

    def create_job(self, project_id: str, payload: JobCreate) -> Job:
        job = self.store.create_job(project_id, payload)
        self._log_job(job, "Job queued", f"{job.type.value}: {job.title}")
        return job

    def run_job(self, project_id: str, job_id: str) -> Job:
        job = self.store.get_job(project_id, job_id)
        if job.status == JobStatus.cancelled:
            return job
        job.status = JobStatus.running
        job.started_at = now_utc()
        job.attempts += 1
        self.store.save_job(job)
        self._log_job(job, "Job running", job.title)
        try:
            job.result_json = self._execute_job(job)
            job.status = JobStatus.completed
            job.completed_at = now_utc()
            job.error_message = ""
            self.store.save_job(job)
            self._log_job(job, "Job completed", job.title)
        except Exception as exc:
            job.status = JobStatus.failed
            job.error_message = str(exc)
            job.completed_at = now_utc()
            self.store.save_job(job)
            self._log_job(job, "Job failed", job.error_message, event_type=ExecutionEventType.error)
        return job

    def cancel_job(self, project_id: str, job_id: str) -> Job:
        job = self.store.cancel_job(project_id, job_id)
        self._log_job(job, "Job cancelled", job.title)
        return job

    def run_workflow(self, project_id: str, payload: WorkflowRunCreate) -> WorkflowRun:
        steps = DEFAULT_WORKFLOW_STEPS.get(payload.name, [{"type": "custom", "title": payload.name}])
        workflow = self.store.create_workflow(project_id, payload, steps)
        workflow.status = WorkflowStatus.running
        self.store.save_workflow(workflow)
        results: list[str] = []
        try:
            for index, step in enumerate(steps):
                workflow.current_step = index
                self.store.save_workflow(workflow)
                result = self._execute_workflow_step(project_id, step, payload.payload_json)
                step["status"] = "completed"
                step["result"] = result
                results.append(f"{step['title']}: completed")
            workflow.status = WorkflowStatus.completed
            workflow.completed_at = now_utc()
            workflow.result_summary = "\n".join(results) or "Workflow completed."
        except Exception as exc:
            workflow.status = WorkflowStatus.failed
            workflow.result_summary = str(exc)
        self.store.save_workflow(workflow)
        self.log_event(project_id, ExecutionEventType.generation, "Workflow run", workflow.result_summary, None, None, {"workflow_id": workflow.id, "status": workflow.status.value})
        return workflow

    def generate_build_packet(self, project_id: str, request: BuildPacketGenerateRequest) -> BuildPacket:
        project = self.store.get_project(project_id)
        task = self._get_task(project_id, request.task_id) if request.task_id else None
        output = self.store.get_output(project_id, request.output_id) if request.output_id else None
        target_title = request.title or (task.title if task else output.prompt if output else "Build Packet")
        source_text = request.source_text or (task.description if task else output.output if output else "")
        memories = self.memory_engine.pinned_context(project_id) + self.memory_engine.search(project_id, target_title, limit=5)
        decisions = self.store.list_decisions(project_id)[:5]
        architecture = next((item for item in self.store.list_outputs(project_id) if item.metadata.get("output_type") == "architecture"), None)
        acceptance = task.acceptance_criteria if task else ["The requested change is implemented.", "Relevant tests/checks pass.", "No project memory boundary is weakened."]
        steps = [
            f"Confirm scope for {target_title}.",
            "Read linked memory, decisions, architecture, and task context.",
            "Make the smallest coherent code changes.",
            "Run targeted tests and smoke checks.",
            "Record result, risks, and follow-up work in CTO OS.",
        ]
        context = "\n".join([m.content for m in memories[:5]]) or source_text or project.description
        prompt_base = f"""Project: {project.name}
Target: {target_title}

Context:
{context}

Implementation steps:
{chr(10).join(f"- {step}" for step in steps)}

Acceptance criteria:
{chr(10).join(f"- {item}" for item in acceptance)}
"""
        packet = BuildPacket(
            project_id=project_id,
            task_id=request.task_id,
            title=target_title,
            summary=f"Execution packet for {target_title}.",
            context=context,
            relevant_memories=[m.id for m in memories],
            relevant_decisions=[d.id for d in decisions],
            architecture_notes=architecture.output[:1800] if architecture else "No architecture output saved yet.",
            implementation_steps=steps,
            files_likely_involved=self._derive_packet_files(project_id, target_title, source_text, task),
            acceptance_criteria=acceptance,
            test_plan=self._derive_packet_test_plan(project_id),
            rollback_plan="Revert only the files touched for this packet and preserve unrelated user changes.",
            codex_prompt=f"You are Codex working in this repo. Implement this private CTO OS task.\n\n{prompt_base}",
            claude_prompt=f"Use this project-grounded context to plan and implement the task carefully.\n\n{prompt_base}",
            cursor_prompt=f"Open the relevant files and implement the following internal CTO OS build packet.\n\n{prompt_base}",
        )
        self.store.save_build_packet(packet)
        if request.save_to_memory:
            memory = self.store.create_memory(project_id, MemoryCreate(title=f"Build packet: {packet.title}", content=packet.codex_prompt, tags=["build-packet"], pinned=False, source="build_packet"))
            self.memory_engine.index_memory(memory)
        self.log_event(project_id, ExecutionEventType.generation, "Build packet generated", packet.title, None, None, {"build_packet_id": packet.id})
        return packet

    def _execute_job(self, job: Job) -> dict[str, Any]:
        if job.type == JobType.weekly_brief:
            output = self.workspace_generator.generate_weekly_brief(job.project_id)
            return {"output_id": output.id, "summary": output.output[:1000]}
        if job.type == JobType.risk_scan:
            risks = self.workspace_generator.generate_risks(job.project_id)
            return {"risk_ids": [risk.id for risk in risks], "count": len(risks)}
        if job.type == JobType.repo_scan:
            if not self.repo_operator:
                raise RuntimeError("Repo operator is not configured")
            repository_id = str(job.payload_json["repository_id"])
            scan = self.repo_operator.scan_repository(job.project_id, repository_id)
            return {"scan_id": scan.id, "summary": scan.summary}
        if job.type == JobType.github_packet:
            packet = self.generate_build_packet(job.project_id, BuildPacketGenerateRequest(**job.payload_json))
            return {"build_packet_id": packet.id, "title": packet.title}
        if job.type == JobType.semantic_indexing:
            count = 0
            for memory in self.store.list_memories(job.project_id):
                self.memory_engine.index_memory(memory)
                count += 1
            return {"indexed_memories": count}
        if job.type == JobType.implementation_review:
            review = self.workspace_generator.review_implementation(job.project_id, ImplementationReviewCreate(**job.payload_json["review"]))
            return {"review_id": review.id, "recommendation": review.recommendation.value}
        return {"message": f"No-op job handler for {job.type.value}", "payload": job.payload_json}

    def _execute_workflow_step(self, project_id: str, step: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        step_type = step["type"]
        if step_type == "risk_scan":
            risks = self.workspace_generator.generate_risks(project_id)
            return {"risk_count": len(risks)}
        if step_type == "weekly_brief":
            output = self.workspace_generator.generate_weekly_brief(project_id)
            return {"output_id": output.id}
        if step_type == "github_packet":
            packet = self.generate_build_packet(project_id, BuildPacketGenerateRequest(**payload.get("build_packet", {})))
            return {"build_packet_id": packet.id}
        if step_type == "architecture_refresh":
            output = self.workspace_generator.generate_architecture(project_id, ArchitectureGenerateRequest(**payload.get("architecture_request", {})))
            return {"output_id": output.id}
        if step_type == "roadmap_generate":
            output = self.workspace_generator.generate_roadmap(project_id, RoadmapGenerateRequest())
            payload["roadmap_output_id"] = output.id
            return {"output_id": output.id}
        if step_type == "roadmap_to_tasks":
            tasks = self.workspace_generator.tasks_from_roadmap(project_id, payload.get("roadmap_output_id"), 8)
            return {"task_ids": [task.id for task in tasks]}
        if step_type == "mitigation_tasks":
            created = []
            for risk in self.store.list_risks(project_id):
                task = self.store.create_task(project_id, TaskCreate(title=f"Mitigate: {risk.title}", description=risk.recommendation, priority=TaskPriority.high, category=TaskCategory.ops, linked_memory_ids=risk.linked_memory_ids, linked_decision_ids=risk.linked_decision_ids))
                created.append(task.id)
            return {"task_ids": created}
        return {"message": "Step acknowledged."}

    def _get_task(self, project_id: str, task_id: str | None):
        return next((task for task in self.store.list_tasks(project_id) if task.id == task_id), None)

    # ---------------- Phase 15: ground packet output in real repo intelligence

    def _derive_packet_files(
        self,
        project_id: str,
        target_title: str,
        source_text: str,
        task,
    ) -> list[str]:
        """Populate ``files_likely_involved`` from real repo signals.

        Order:
        1. Filename hints extracted from the task title + description.
        2. Top-scored candidate files from the repo operator (if any).
        3. ``RepoScan.key_files``.
        Falls through to an empty list rather than CTO OS defaults — better
        to say "we don't know" than to mis-suggest paths from another project.
        """
        if self.repo_operator is None:
            return []
        repositories = self.store.list_repositories(project_id)
        if not repositories:
            return []
        repo = repositories[0]
        objective = " ".join(
            piece for piece in (target_title, source_text or "", task.description if task else "") if piece
        )
        hints = self.repo_operator._extract_filename_hints(objective.lower())
        files = self.repo_operator._candidate_files(project_id, repo.id, objective)
        result: list[str] = []
        seen: set[str] = set()
        for hint in sorted(hints):
            for f in files:
                if f.path.lower() == hint or f.path.lower().endswith("/" + hint):
                    if f.path not in seen:
                        seen.add(f.path)
                        result.append(f.path)
        for f in files:
            if f.path not in seen:
                seen.add(f.path)
                result.append(f.path)
            if len(result) >= 12:
                break
        if len(result) < 12:
            scan = next(iter(self.store.list_repo_scans(project_id, repo.id)), None)
            if scan is not None:
                # Phase 16.5: defensive — old scans (persisted before the
                # noise-aware key_files build) may still contain lockfiles.
                # Classify lazily and drop noise unless explicitly hinted.
                from .file_classifier import FileClassifier, NOISE_TYPES
                classifier = FileClassifier()
                for path in scan.key_files:
                    if path in seen:
                        continue
                    cls = classifier.classify(path)
                    if cls.semantic_type in NOISE_TYPES:
                        path_lower = path.lower()
                        name_lower = path_lower.rsplit("/", 1)[-1]
                        if not any(
                            hint == name_lower or hint == path_lower
                            or path_lower.endswith("/" + hint)
                            for hint in hints
                        ):
                            continue
                    seen.add(path)
                    result.append(path)
                    if len(result) >= 12:
                        break
        return result[:12]

    def _derive_packet_test_plan(self, project_id: str) -> list[str]:
        """Pull test_plan from the project's most recent repo scan.

        If no scan exists or the scan found no test commands, return a
        single honest "no commands detected" line — never CTO OS defaults.
        """
        repositories = self.store.list_repositories(project_id)
        if not repositories:
            return [
                "No repository registered for this project — register one and run a scan to detect test commands."
            ]
        scan = next(iter(self.store.list_repo_scans(project_id, repositories[0].id)), None)
        if scan is None:
            return [
                "No repository scan yet — call /repositories/{id}/scan to populate test_plan."
            ]
        candidates = list(scan.test_commands) + list(scan.build_commands) + list(scan.lint_commands)
        if not candidates:
            return [
                "No test/build/lint commands detected by scan — add an approved command via /repositories/{id}/commands first."
            ]
        return candidates

    def _log_job(self, job: Job, title: str, summary: str, event_type: ExecutionEventType = ExecutionEventType.generation) -> None:
        self.log_event(job.project_id, event_type, title, summary, None, None, {"job_id": job.id, "job_status": job.status.value, "job_type": job.type.value})
