from __future__ import annotations

import re
from datetime import datetime, timezone

from .agents import get_agent
from .llm import LLMService
from .memory_engine import LocalMemoryEngine
from .models import (
    ArchitectureGenerateRequest,
    BriefGenerateRequest,
    GeneratedOutput,
    ImplementationPlanRequest,
    ImplementationReview,
    ImplementationReviewCreate,
    ImplementationReviewRecommendation,
    MemoryCreate,
    ProjectBrief,
    RoadmapGenerateRequest,
    Risk,
    RiskCategory,
    RiskCreate,
    RiskLikelihood,
    RiskSeverity,
    TaskStatus,
    Task,
    TaskCategory,
    TaskCreate,
    TaskPriority,
)
from .structured_outputs import (
    StructuredArchitectureOutput,
    StructuredRoadmapOutput,
    StructuredWeeklyBriefOutput,
    validate_structured_output,
)
from .storage import JsonStore


class WorkspaceGenerator:
    def __init__(self, store: JsonStore, memory_engine: LocalMemoryEngine) -> None:
        self.store = store
        self.memory_engine = memory_engine
        self.llm = LLMService()
        self._last_llm_metadata: dict = {"provider": "deterministic"}

    def generate_architecture(self, project_id: str, request: ArchitectureGenerateRequest) -> GeneratedOutput:
        project = self.store.get_project(project_id)
        agent = get_agent(request.agent_id)
        context = self._context(project_id, request.prompt or "architecture")
        decisions = self.store.list_decisions(project_id)[:8]
        decision_block = "\n".join(f"- {d.title}: {d.decision}" for d in decisions) or "- No decisions logged yet."
        prompt = f"""Generate a structured architecture recommendation for this internal project.

Project: {project.name}
Agent: {agent.name.value if agent else request.agent_id}

Required sections:
- recommended tech stack
- frontend architecture
- backend architecture
- database schema
- API structure
- integration map
- infrastructure/deployment plan
- security considerations
- scalability risks
- cost considerations
- build complexity score

Relevant memory:
{context}

Decision context:
{decision_block}

Additional instruction:
{request.prompt or "Use the strongest project-grounded recommendation."}
"""
        fallback = f"""Architecture Recommendation

Project: {project.name}
Agent: {agent.name.value if agent else request.agent_id}

Recommended tech stack
- Frontend: Next.js app router, TypeScript, internal-first component system.
- Backend: FastAPI service layer over the existing MemPalace memory engine.
- Data: local JSON for Phase 2 metadata with atomic writes and backups; SQLite is the next persistence step.
- Semantic memory: MemPalace/ChromaDB with project_id mapped to wing.

Frontend architecture
- Project command center routes under /projects/[id].
- Thin API client in cto_os_web/lib/api.ts.
- Reusable project navigation and focused internal work screens.

Backend architecture
- FastAPI routes grouped by project resource.
- JsonStore owns app metadata and migration defaults.
- MempalaceMemoryEngine owns semantic retrieval and project isolation.
- WorkspaceGenerator converts memory, decisions, and selected agent context into execution artifacts.

Database schema
- projects, memories, decisions, outputs, prompt_templates, tasks.
- Chroma collection mempalace_drawers stores semantic memory with wing=project_id.

API structure
- /projects/{{id}}/architecture/generate
- /projects/{{id}}/roadmap/generate
- /projects/{{id}}/tasks/*
- /projects/{{id}}/implementation-plan/generate
- /projects/{{id}}/brief
- /projects/{{id}}/brief/generate

Integration map
- CTO OS API -> JsonStore for metadata.
- CTO OS API -> MemPalace/Chroma for semantic retrieval.
- Next.js UI -> FastAPI over localhost/internal network.

Infrastructure/deployment plan
- Run API and web behind localhost, VPN, or internal reverse proxy.
- Persist cto_os_api/data and MemPalace palace path on durable local/internal storage.
- Add internal auth proxy before network exposure.

Security considerations
- No public signup, billing, or tenant marketplace.
- Default memory retrieval is project-scoped.
- Treat cross-project search as privileged internal behavior.
- Back up local app metadata and Chroma palace data.

Scalability risks
- JSON metadata writes are acceptable for Phase 2 but not for concurrent team editing.
- Chroma local model download can slow first use.
- Large output bodies need pruning and archival conventions.

Cost considerations
- Local semantic retrieval keeps baseline cost low.
- Model generation cost depends on future LLM provider wiring.
- SQLite migration is low-cost and should precede multi-user internal rollout.

Build complexity score
- 6/10 now: straightforward internal system, but persistence and auth should harden before broader use.

Relevant memory
{context}

Decision context
{decision_block}
"""
        output = self._llm_or_fallback("You are a pragmatic private CTO architecture planner.", prompt, fallback)
        return self._save_generated(
            project_id,
            request.agent_id,
            prompt,
            output,
            "architecture",
            request.save_output,
            request.pin_to_memory,
        )

    def generate_roadmap(self, project_id: str, request: RoadmapGenerateRequest) -> GeneratedOutput:
        project = self.store.get_project(project_id)
        context = self._context(project_id, request.prompt or "roadmap")
        prompt = f"""Generate a project roadmap from source-of-truth memory.

Project: {project.name}

Required structure:
- phases
- milestones
- features
- dependencies
- risks
- acceptance criteria
- estimated difficulty
- recommended build order

Relevant memory:
{context}

Additional instruction:
{request.prompt or "Optimize for internal execution clarity."}
"""
        fallback = f"""Product Roadmap

Project: {project.name}

Phase 1: Foundation
Milestones
- Confirm source-of-truth project brief.
- Lock core architecture and internal data model.
Features
- Memory pinning, decisions, architecture generation, task management.
Dependencies
- MemPalace retrieval must stay project-scoped.
Risks
- Weak project brief creates noisy generated plans.
Acceptance criteria
- Project owner can understand current state and next work from one screen.
Estimated difficulty
- Medium
Recommended build order
- Brief -> architecture -> roadmap -> task generation.

Phase 2: Execution Workspace
Milestones
- Turn roadmap and outputs into actionable tickets.
- Add implementation plans for high-priority work.
Features
- Kanban tasks, generated implementation plans, prompt library.
Dependencies
- Task links to memory, decisions, and outputs.
Risks
- Generated tickets need human review before implementation.
Acceptance criteria
- Every major output can become executable work.
Estimated difficulty
- Medium-high
Recommended build order
- Tasks -> prompts -> implementation planner.

Phase 3: Operating System
Milestones
- Add review loops, build logs, status reporting, and internal auth.
Features
- Weekly CTO brief, risk dashboard, test/release checklists.
Dependencies
- SQLite or Postgres metadata store.
Risks
- Process clutter if dashboards outgrow actual decisions.
Acceptance criteria
- The workspace drives daily product and engineering execution.
Estimated difficulty
- High
Recommended build order
- Storage hardening -> auth -> reporting -> automation.

Relevant memory
{context}
"""
        output = self._llm_or_fallback("You are a product strategist turning memory into executable roadmap decisions.", prompt, fallback)
        return self._save_generated(
            project_id,
            request.agent_id,
            prompt,
            output,
            "roadmap",
            request.save_output,
            request.pin_to_memory,
        )

    def tasks_from_roadmap(self, project_id: str, output_id: str | None = None, limit: int = 8) -> list[Task]:
        output = self._latest_output(project_id, "roadmap", output_id)
        return self._create_tasks_from_text(project_id, output.output, output.id, limit)

    def tasks_from_output(self, project_id: str, output_id: str, limit: int = 8) -> list[Task]:
        output = self.store.get_output(project_id, output_id)
        return self._create_tasks_from_text(project_id, output.output, output.id, limit)

    def generate_implementation_plan(self, project_id: str, request: ImplementationPlanRequest) -> GeneratedOutput:
        source = request.source_text
        linked_output_ids: list[str] = []
        if request.source_type == "task" and request.source_id:
            task = next((task for task in self.store.list_tasks(project_id) if task.id == request.source_id), None)
            if task:
                source = f"{task.title}\n\n{task.description}\n\nAcceptance criteria: {', '.join(task.acceptance_criteria)}"
        elif request.source_type == "output" and request.source_id:
            output = self.store.get_output(project_id, request.source_id)
            linked_output_ids.append(output.id)
            source = output.output

        context = self._context(project_id, source or "implementation")
        prompt = f"""Generate a step-by-step implementation plan.

Required sections:
- objective
- files likely involved
- implementation steps
- test plan
- rollback plan
- risks
- Codex prompt
- Claude/Cursor prompt
- acceptance criteria checklist

Source:
{source or "No source text supplied."}

Relevant memory:
{context}
"""
        fallback = f"""Implementation Plan

Objective
- Convert the selected work item into a shippable internal increment.

Source
{source or "No source text supplied."}

Files likely involved
- cto_os_api/models.py
- cto_os_api/storage.py
- cto_os_api/main.py
- cto_os_web/lib/api.ts
- cto_os_web/app/projects/[id]/*

Implementation steps
1. Confirm the user-facing workflow and data shape.
2. Add or update backend models and storage helpers.
3. Expose the smallest useful API route.
4. Wire the frontend action and state.
5. Save generated artifacts back to project outputs.
6. Verify project-scoped memory behavior.

Test plan
- Python compile.
- Backend endpoint smoke test with temporary app data.
- Project isolation check for memory retrieval.
- TypeScript no-emit check.
- Route 200 checks for affected screens.

Rollback plan
- Revert the route and UI entry point.
- Keep existing outputs and memories; do not delete user-authored project data.
- Restore the previous JSON backup from cto_os_api/data/backups if metadata is corrupted.

Risks
- Generated implementation steps may over-assume code structure.
- Linked memory can become stale if source-of-truth pins are not maintained.

Codex prompt
Build this task inside the existing private CTO OS repo. Preserve MemPalace integration and project-scoped retrieval. Implement only the smallest useful backend and UI changes needed for the task, then run compile and smoke checks.

Claude/Cursor prompt
You are working in a private internal CTO OS. Use pinned project memory and decisions as source of truth. Produce a careful implementation plan, edit the relevant files, and verify the workflow end to end without adding SaaS, billing, or tenant complexity.

Acceptance criteria checklist
- [ ] User can trigger the workflow from the relevant screen.
- [ ] Output is saved to the project.
- [ ] Project memory isolation is preserved.
- [ ] Tests/checks pass.

Relevant memory
{context}
"""
        output_text = self._llm_or_fallback("You are an execution-focused engineering planner.", prompt, fallback)
        generated = self._save_generated(project_id, request.agent_id, "Generate implementation plan", output_text, "implementation_plan", request.save_output, False)
        if linked_output_ids:
            generated.metadata["linked_output_ids"] = linked_output_ids
        return generated

    def current_brief(self, project_id: str) -> ProjectBrief:
        project = self.store.get_project(project_id)
        pinned = self.store.list_memories(project_id=project_id, pinned=True)
        decisions = self.store.list_decisions(project_id)[:6]
        tasks = [task for task in self.store.list_tasks(project_id) if task.status.value not in {"done"}][:8]
        architecture = self._latest_output(project_id, "architecture", None, required=False)
        roadmap = self._latest_output(project_id, "roadmap", None, required=False)
        risks = self.store.list_risks(project_id)
        pinned_text = "\n".join(memory.content for memory in pinned)

        # Phase 15: derive every field from this project's own state.
        # The previous defaults leaked CTO OS's own stack/risks/etc into
        # every project's brief.
        tech_stack = self._project_tech_stack(project_id, pinned, architecture)
        goal_memory = next(
            (m for m in pinned if any(token in m.title.lower() for token in ("goal", "north star", "objective"))),
            None,
        )
        audience_memory = next(
            (m for m in pinned if any(token in m.title.lower() for token in ("audience", "customer", "user"))),
            None,
        )
        thesis_memory = next(
            (m for m in pinned if "thesis" in m.title.lower() or "why" in m.title.lower()),
            None,
        )
        monetization_memory = next(
            (m for m in pinned if any(token in m.title.lower() for token in ("monetiz", "pricing", "revenue", "business model"))),
            None,
        )
        open_risks = [f"{r.title} ({r.severity.value})" for r in risks if r.status.value == "open"][:5]
        if not open_risks:
            open_risks = ["No open risks recorded — call /risks/generate or add one manually."]

        return ProjectBrief(
            project_id=project_id,
            project_summary=project.description or self._first_line(pinned_text, "No project summary pinned yet."),
            current_goal=(goal_memory.content if goal_memory else self._first_line(pinned_text, "Clarify the next execution milestone.")),
            audience_customer=(audience_memory.content if audience_memory else "Not pinned yet — add a memory titled with 'audience' or 'customer' to populate this."),
            product_thesis=(thesis_memory.content if thesis_memory else "Not pinned yet — add a memory titled with 'thesis' or 'why' to populate this."),
            monetization_thesis=(monetization_memory.content if monetization_memory else "Not pinned yet — add a memory tagged with 'monetization', 'pricing', or 'revenue' to populate this."),
            current_tech_stack=tech_stack,
            active_roadmap=self._bullets(roadmap.output if roadmap else "", 6) or ["Generate a roadmap to populate this section."],
            key_decisions=[f"{d.title}: {d.decision}" for d in decisions] or ["No decisions logged yet."],
            open_risks=open_risks,
            next_best_actions=[task.title for task in tasks[:5]] or ["Generate tasks from the roadmap."],
        )

    def _project_tech_stack(self, project_id: str, pinned, architecture) -> str:
        """Phase 15: derive tech stack from real signals, not a hardcoded string.

        Priority:
        1. The project's most recent repo scan (``tech_stack + frameworks``).
        2. Pinned memory whose title or tags mention stack / tech / framework.
        3. The first line of the most recent architecture output.
        4. Empty string with a "not detected yet" hint — NEVER CTO OS's own stack.
        """
        try:
            repositories = self.store.list_repositories(project_id)
        except Exception:
            repositories = []
        for repo in repositories:
            scans = self.store.list_repo_scans(project_id, repo.id)
            if scans:
                scan = scans[0]
                parts = list(scan.tech_stack) + list(scan.frameworks)
                if parts:
                    return ", ".join(parts)
        stack_memory = next(
            (
                m
                for m in pinned
                if any(token in m.title.lower() for token in ("stack", "tech", "framework"))
                or any(tag in {"stack", "tech", "framework"} for tag in m.tags)
            ),
            None,
        )
        if stack_memory:
            return self._first_line(stack_memory.content, stack_memory.content[:200])
        if architecture and architecture.output:
            return self._first_line(architecture.output, "")
        return "Not detected yet — register a repository and run a scan, or pin a memory titled 'stack'."

    def generate_brief(self, project_id: str, request: BriefGenerateRequest) -> GeneratedOutput:
        brief = self.current_brief(project_id)
        prompt = f"""Generate a source-of-truth project brief using these fields.

Project summary: {brief.project_summary}
Current goal: {brief.current_goal}
Audience/customer: {brief.audience_customer}
Product thesis: {brief.product_thesis}
Monetization thesis: {brief.monetization_thesis}
Current tech stack: {brief.current_tech_stack}
Active roadmap: {self._format_list(brief.active_roadmap)}
Key decisions: {self._format_list(brief.key_decisions)}
Open risks: {self._format_list(brief.open_risks)}
Next best actions: {self._format_list(brief.next_best_actions)}
"""
        fallback = f"""Project Brief

Project summary
{brief.project_summary}

Current goal
{brief.current_goal}

Audience/customer
{brief.audience_customer}

Product thesis
{brief.product_thesis}

Monetization thesis
{brief.monetization_thesis}

Current tech stack
{brief.current_tech_stack}

Active roadmap
{self._format_list(brief.active_roadmap)}

Key decisions
{self._format_list(brief.key_decisions)}

Open risks
{self._format_list(brief.open_risks)}

Next best actions
{self._format_list(brief.next_best_actions)}
"""
        output = self._llm_or_fallback("You are a concise CTO chief-of-staff producing an internal source-of-truth brief.", prompt, fallback)
        return self._save_generated(project_id, request.agent_id, "Generate project brief", output, "brief", request.save_output, request.pin_to_memory)

    def generate_risks(self, project_id: str) -> list[Risk]:
        memories = self.store.list_memories(project_id)
        pinned = [memory for memory in memories if memory.pinned]
        decisions = self.store.list_decisions(project_id)
        tasks = self.store.list_tasks(project_id)
        outputs = self.store.list_outputs(project_id)
        risks: list[RiskCreate] = []
        if any(task.status == TaskStatus.blocked for task in tasks):
            blocked = [task.id for task in tasks if task.status == TaskStatus.blocked]
            risks.append(RiskCreate(
                title="Blocked execution is accumulating",
                category=RiskCategory.execution,
                severity=RiskSeverity.high,
                likelihood=RiskLikelihood.high,
                evidence=f"{len(blocked)} blocked task(s).",
                recommendation="Review blockers, assign owner, and generate implementation plans for each blocked item.",
                linked_task_ids=blocked,
            ))
        if any(task.priority.value in {"high", "urgent"} and task.status.value not in {"done", "review"} for task in tasks):
            hot = [task.id for task in tasks if task.priority.value in {"high", "urgent"} and task.status.value not in {"done", "review"}]
            risks.append(RiskCreate(
                title="High-priority work is still incomplete",
                category=RiskCategory.execution,
                severity=RiskSeverity.medium,
                likelihood=RiskLikelihood.medium,
                evidence=f"{len(hot)} high/urgent task(s) are not complete.",
                recommendation="Use the weekly brief to force rank the next implementation slice.",
                linked_task_ids=hot[:8],
            ))
        if not pinned:
            risks.append(RiskCreate(
                title="No pinned source-of-truth memory",
                category=RiskCategory.product,
                severity=RiskSeverity.medium,
                likelihood=RiskLikelihood.high,
                evidence="Project has no pinned memory.",
                recommendation="Pin the project thesis, target user, current goal, and architectural constraints.",
            ))
        if not decisions:
            risks.append(RiskCreate(
                title="Decision trail is thin",
                category=RiskCategory.operational,
                severity=RiskSeverity.low,
                likelihood=RiskLikelihood.medium,
                evidence="No decisions have been logged.",
                recommendation="Log technical and product decisions before generating more implementation work.",
            ))
        if not any(output.metadata.get("output_type") == "architecture" for output in outputs):
            risks.append(RiskCreate(
                title="Architecture has not been generated",
                category=RiskCategory.technical,
                severity=RiskSeverity.medium,
                likelihood=RiskLikelihood.medium,
                evidence="No architecture output exists for this project.",
                recommendation="Generate architecture before expanding the task backlog.",
            ))
        if not risks:
            risks.append(RiskCreate(
                title="Operational risk watch",
                category=RiskCategory.operational,
                severity=RiskSeverity.low,
                likelihood=RiskLikelihood.low,
                evidence="No obvious blocked tasks, missing source-of-truth memory, or missing architecture found.",
                recommendation="Keep monitoring decisions, task age, and architecture drift weekly.",
            ))
        return [self.store.create_risk(project_id, risk) for risk in risks]

    def generate_weekly_brief(self, project_id: str) -> GeneratedOutput:
        logs = self.store.list_logs(project_id)[:20]
        decisions = self.store.list_decisions(project_id)[:10]
        tasks = self.store.list_tasks(project_id)
        risks = self.store.list_risks(project_id)
        completed = [task.title for task in tasks if task.status.value == "done"][:8]
        blocked = [task.title for task in tasks if task.status.value == "blocked"][:8]
        open_risks = [risk.title for risk in risks if risk.status.value in {"open", "watching"}][:8]
        prompt = f"""Generate a weekly CTO brief.

What changed:
{self._format_list([log.title for log in logs[:8]] or ["No logs yet."])}

Decisions made:
{self._format_list([f"{d.title}: {d.decision}" for d in decisions] or ["No decisions this week."])}

Completed tasks:
{self._format_list(completed or ["No completed tasks logged."])}

Blocked tasks:
{self._format_list(blocked or ["No blocked tasks."])}

Open risks:
{self._format_list(open_risks or ["No open risks logged."])}

Include next recommended actions, architecture concerns, product concerns, and suggested focus for next week.
"""
        fallback = f"""Weekly CTO Brief

What changed
{self._format_list([log.title for log in logs[:8]] or ["No execution logs yet."])}

Decisions made
{self._format_list([f"{d.title}: {d.decision}" for d in decisions] or ["No decisions logged."])}

Completed tasks
{self._format_list(completed or ["No completed tasks."])}

Blocked tasks
{self._format_list(blocked or ["No blocked tasks."])}

Open risks
{self._format_list(open_risks or ["No open risks."])}

Next recommended actions
- Review high-priority incomplete tasks.
- Generate or refresh the project brief.
- Close or mitigate open risks.

Architecture concerns
- Watch for metadata persistence and auth gaps before broader use.

Product concerns
- Keep pinned memory current so generated work stays grounded.

Suggested focus for next week
- Ship one narrow implementation slice and review the outcome.
"""
        output = self._llm_or_fallback("You are a CTO chief-of-staff writing a weekly operating brief.", prompt, fallback)
        return self._save_generated(project_id, "technical-cto", prompt, output, "weekly_brief", True, False)

    def review_implementation(self, project_id: str, request: ImplementationReviewCreate) -> ImplementationReview:
        prompt = f"""Review this implementation attempt.

Attempted: {request.attempted}

Execution result:
{request.execution_result}

Error logs:
{request.error_logs}

Notes:
{request.implementation_notes}

Suggest one recommendation: pass, revise, rollback, or follow_up.
Also extract lessons learned and possible follow-up tasks.
"""
        fallback = f"""Implementation Review

Review result
The implementation attempt needs human review against the task acceptance criteria.

Recommendation
revise

Suggested follow-up tasks
- Reproduce the issue or verify the completed behavior.
- Add or update tests for the affected path.
- Capture any durable lesson in project memory.

Lessons learned
{request.implementation_notes[:800]}
"""
        text = self._llm_or_fallback("You are a careful engineering reviewer.", prompt, fallback)
        lower = text.lower()
        if "rollback" in lower:
            rec = ImplementationReviewRecommendation.rollback
        elif "follow_up" in lower or "follow-up" in lower:
            rec = ImplementationReviewRecommendation.follow_up
        elif "pass" in lower and "revise" not in lower:
            rec = ImplementationReviewRecommendation.pass_
        else:
            rec = ImplementationReviewRecommendation.revise
        follow_up_ids: list[str] = []
        if request.create_follow_up_tasks:
            task = self.store.create_task(project_id, TaskCreate(
                title="Follow up implementation review",
                description=text,
                status=TaskStatus.backlog,
                priority=TaskPriority.medium,
                category=TaskCategory.backend,
                linked_output_ids=[request.output_id] if request.output_id else [],
            ))
            follow_up_ids.append(task.id)
        lesson = self._first_line(text, request.implementation_notes)
        if request.save_lesson_to_memory:
            memory = self.store.create_memory(project_id, MemoryCreate(title="Implementation lesson learned", content=lesson, tags=["implementation_review"], pinned=False, source="implementation_review"))
            self.memory_engine.index_memory(memory)
        review = ImplementationReview(
            project_id=project_id,
            task_id=request.task_id,
            output_id=request.output_id,
            build_packet_id=request.build_packet_id,
            attempted=request.attempted,
            execution_result=request.execution_result,
            error_logs=request.error_logs,
            implementation_notes=request.implementation_notes,
            review_result=text,
            recommendation=rec,
            follow_up_task_ids=follow_up_ids,
            lessons_learned=lesson,
        )
        return self.store.save_review(review)

    def _context(self, project_id: str, query: str) -> str:
        memories = self.memory_engine.pinned_context(project_id) + self.memory_engine.search(project_id, query, cross_project=False)
        deduped = []
        seen = set()
        for memory in memories:
            if memory.id not in seen:
                deduped.append(memory)
                seen.add(memory.id)
        return "\n".join(f"- {memory.title}: {memory.content}" for memory in deduped[:10]) or "- No relevant memory yet."

    def _save_generated(self, project_id: str, agent_id: str, prompt: str, output: str, output_type: str, save: bool, pin: bool) -> GeneratedOutput:
        schemas = {
            "architecture": StructuredArchitectureOutput,
            "roadmap": StructuredRoadmapOutput,
            "brief": StructuredWeeklyBriefOutput,
            "weekly_brief": StructuredWeeklyBriefOutput,
        }
        validation = validate_structured_output(schemas[output_type], output) if output_type in schemas else None
        generated = GeneratedOutput(
            project_id=project_id,
            agent_id=agent_id,
            prompt=prompt,
            output=output,
            metadata={
                "output_type": output_type,
                "raw_prompt": prompt,
                "llm": self._last_llm_metadata,
                "structured_validation": validation.model_dump(mode="json") if validation else None,
            },
        )
        if save:
            self.store.save_output(generated)
        if pin:
            memory = self.store.create_memory(project_id, MemoryCreate(title=f"{output_type.replace('_', ' ').title()} Output", content=output, tags=[output_type], pinned=True, source="generated_output"))
            self.memory_engine.index_memory(memory)
        return generated

    def _llm_or_fallback(self, system: str, prompt: str, fallback: str) -> str:
        result = self.llm.generate(system, prompt)
        self._last_llm_metadata = {key: value for key, value in result.items() if key not in {"text", "raw"}}
        if result.get("fallback") and result.text.strip() == f"{system}\n\n{prompt}".strip():
            return fallback
        return result.text or fallback

    def _latest_output(self, project_id: str, output_type: str, output_id: str | None, required: bool = True) -> GeneratedOutput | None:
        if output_id:
            return self.store.get_output(project_id, output_id)
        for output in self.store.list_outputs(project_id):
            if output.metadata.get("output_type") == output_type:
                return output
        if required:
            raise KeyError(output_type)
        return None

    def _create_tasks_from_text(self, project_id: str, text: str, output_id: str, limit: int) -> list[Task]:
        candidates = self._task_titles(text)[:limit]
        tasks = []
        for index, title in enumerate(candidates, 1):
            category = self._category_for(title)
            task = self.store.create_task(
                project_id,
                TaskCreate(
                    title=title,
                    description=f"Generated from roadmap/output. Review and refine before build.\n\nSource excerpt:\n{self._first_line(text, '')}",
                    priority=TaskPriority.high if index <= 3 else TaskPriority.medium,
                    category=category,
                    acceptance_criteria=[
                        "Scope is clear enough for implementation.",
                        "Relevant memory, decisions, or outputs are linked.",
                        "Work can be verified with a concrete check.",
                    ],
                    linked_output_ids=[output_id],
                ),
            )
            tasks.append(task)
        return tasks

    def _task_titles(self, text: str) -> list[str]:
        titles: list[str] = []
        for line in text.splitlines():
            clean = re.sub(r"^[\s\-\*\d\.]+", "", line).strip()
            if not clean or len(clean) < 8:
                continue
            if clean.lower() in {"milestones", "features", "dependencies", "risks", "acceptance criteria", "recommended build order"}:
                continue
            if any(word in clean.lower() for word in ["add ", "build", "create", "generate", "wire", "confirm", "lock", "turn", "move", "implement"]):
                titles.append(clean[:120])
        return titles or ["Review roadmap and define next implementation slice"]

    def _category_for(self, title: str) -> TaskCategory:
        lower = title.lower()
        if "frontend" in lower or "ui" in lower or "screen" in lower:
            return TaskCategory.frontend
        if "api" in lower or "backend" in lower or "storage" in lower:
            return TaskCategory.backend
        if "memory" in lower or "ai" in lower or "prompt" in lower:
            return TaskCategory.ai
        if "design" in lower or "ux" in lower:
            return TaskCategory.design
        if "growth" in lower or "market" in lower:
            return TaskCategory.growth
        return TaskCategory.product

    def _first_line(self, text: str, fallback: str) -> str:
        for line in text.splitlines():
            if line.strip():
                return line.strip()[:500]
        return fallback

    def _bullets(self, text: str, limit: int) -> list[str]:
        bullets = []
        for line in text.splitlines():
            clean = re.sub(r"^[\s\-\*\d\.]+", "", line).strip()
            if len(clean) > 10:
                bullets.append(clean[:180])
            if len(bullets) >= limit:
                break
        return bullets

    def _format_list(self, items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items)
