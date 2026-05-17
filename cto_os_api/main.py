from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from .agents import DEFAULT_AGENTS
from .auth import InternalAuthMiddleware
from .backup_mirror import BackupMirrorService
from .backups import BackupService
from .build_session_timeline import BuildSessionTimelineBuilder
from .command_runner import CommandRunner, CommandSafetyError
from .context_builder import ContextBuilder
from .control_room import ControlRoom
from .cron_service import CronService
from .daily_review import DailyReviewService
from .decision_graph import DecisionGraphBuilder
from .execution_engine import DEFAULT_WORKFLOW_STEPS, ExecutionEngine
from .github_integration import GitHubIntegration
from .github_reconciliation import GitHubReconciliation
from .github_write_guard import GitHubWriteError
from .audit_signing import verify as audit_verify
from .health import HealthService
from .health_alerts import HealthAlertEvaluator
from .health_history import HealthHistoryService
from .mcp_sessions import MCPSessionResolver
from .retention_service import RetentionService
from .intake import (
    IntakeAuthError,
    IntakeDisabledError,
    IntakeService,
    parse_intake_body,
)
from .llm import LLMService
from .llm_results import LLMResultsService
from .notifications import NotificationService
from .outcome_scoring import OutcomeScoringService
from .playbook_service import PlaybookService
from .retrospective_generator import RetrospectiveGenerator
from .risk_concentration import RiskConcentrationService
from .shipped_dashboard import ShippedDashboard
from .staleness import StalenessDetector
from .system_shipped import SystemShipped
from .memory_engine import MempalaceMemoryEngine
from .models import (
    ApprovedCommand,
    ApprovedCommandCreate,
    ArchitectureGenerateRequest,
    BranchPlan,
    BranchPlanGenerateRequest,
    BriefGenerateRequest,
    BuildPacket,
    BuildPacketGenerateRequest,
    CodeReview,
    CodeReviewCreate,
    CodeDependency,
    CodeSymbol,
    Decision,
    DecisionCreate,
    ExecutionEventType,
    ExecutionLog,
    ExecutionLogCreate,
    GenerateRequest,
    GenerateTasksRequest,
    GeneratedOutput,
    BackupPolicy,
    BackupPolicyUpdate,
    BackupRunResult,
    BuildPacketSaveRequest,
    BuildPacketContextRequest,
    BuildSessionTimeline,
    DailyReview,
    CodeReviewContextRequest,
    CodeReviewSaveRequest,
    ControlRoomSummary,
    DecisionGraph,
    ImplementationPlanContextRequest,
    ImplementationPlanSaveRequest,
    LLMContextBundle,
    RetrospectiveContextRequest,
    RetrospectiveSaveRequest,
    GitDiff,
    GitDiffRequest,
    GitHubBranchCreateRequest,
    GitHubDraftPRCreateRequest,
    GitHubIssueCreateRequest,
    GitHubReconciliationEvent,
    GitHubWriteEvent,
    GitStatus,
    IntakeEvent,
    NotificationEvent,
    NotificationRule,
    NotificationRuleCreate,
    NotificationRuleUpdate,
    NotificationTestRequest,
    OutcomeScore,
    OutcomeScoreCreate,
    Playbook,
    PlaybookApplyRequest,
    PlaybookGenerateRequest,
    PostShipRetrospective,
    ReconcileRequest,
    ReconciliationReport,
    RetrospectiveGenerateRequest,
    RiskConcentrationSummary,
    ShippedSummary,
    SnapshotIntegrity,
    SnapshotRestorePreview,
    StalenessReport,
    StatusSuggestion,
    SystemHealth,
    SystemShippedSummary,
    WorkerHeartbeat,
    BackupMirrorEvent,
    CronJob,
    CronJobCreate,
    CronJobUpdate,
    CronRunResult,
    HealthHistorySummary,
    HealthSnapshot,
    MCPAuditEvent,
    ResourceChangeEvent,
    AuditVerificationReport,
    AuditVerificationResult,
    HealthAlertEvaluation,
    HealthAlertRule,
    HealthAlertRuleCreate,
    HealthAlertRuleUpdate,
    MCPSession,
    MCPSessionCreate,
    MCPSessionUpdate,
    RetentionPolicy,
    RetentionPolicyUpdate,
    RetentionRunResult,
    RetentionTarget,
    ImplementationPlanRequest,
    ImplementationReview,
    ImplementationReviewCreate,
    Job,
    JobCreate,
    Memory,
    MemoryCreate,
    ProjectBrief,
    Project,
    ProjectCreate,
    PromptGenerateFromTemplateRequest,
    PromptTemplate,
    PromptTemplateCreate,
    PRPacket,
    PRPacketGenerateRequest,
    Repository,
    RepositoryCreate,
    RepositoryUpdate,
    RepoFile,
    RepoScan,
    RoadmapGenerateRequest,
    Risk,
    RiskUpdate,
    SearchResult,
    SnapshotManifest,
    Task,
    TaskCreate,
    TaskUpdate,
    TestRun,
    TestRunCreate,
    BuildSession,
    BuildSessionCreate,
    BuildSessionUpdate,
    WorkflowRun,
    WorkflowRunCreate,
)
from .prompting import PromptService
from .repo_operator import RepoOperator
from .git_reader import GitReader
from .snapshots import SnapshotManager
from .sqlite_store import SQLiteStore
from .workspace_generators import WorkspaceGenerator

store = SQLiteStore()
memory_engine = MempalaceMemoryEngine(store)
prompt_service = PromptService(store, memory_engine)
workspace_generator = WorkspaceGenerator(store, memory_engine)
llm_service = LLMService()
snapshot_manager = SnapshotManager(store)
repo_operator = RepoOperator(store, memory_engine)
github_integration = GitHubIntegration()
git_reader = GitReader()
command_runner = CommandRunner(store)
reconciliation_service = GitHubReconciliation(store, github_integration)
timeline_builder = BuildSessionTimelineBuilder(store)
retrospective_generator = RetrospectiveGenerator(store, memory_engine)
shipped_dashboard = ShippedDashboard(store)
control_room = ControlRoom(store)
system_shipped_view = SystemShipped(store)
risk_concentration_service = RiskConcentrationService(store)
decision_graph_builder = DecisionGraphBuilder(store)
playbook_service = PlaybookService(store)
outcome_scoring = OutcomeScoringService(store)
notification_service = NotificationService(store)
staleness_detector = StalenessDetector(store)
context_builder = ContextBuilder(store, memory_engine)
llm_results = LLMResultsService(store, memory_engine)
intake_service = IntakeService(store)
backup_service = BackupService(store, snapshot_manager)
daily_review_service = DailyReviewService(store)
health_service = HealthService(store, snapshot_manager, backup_service)
health_alert_evaluator = HealthAlertEvaluator(store, notification_service)
health_history_service = HealthHistoryService(
    store, health_service, alert_evaluator=health_alert_evaluator
)
backup_mirror_service = BackupMirrorService(store, snapshot_manager)
retention_service = RetentionService(store)
session_resolver = MCPSessionResolver(store)
cron_service = CronService(
    store,
    daily_review=daily_review_service,
    backups=backup_service,
    health_history=health_history_service,
    reconciliation=reconciliation_service,
    workspace_generator=workspace_generator,
    retention_service=retention_service,
)
try:
    cron_service.ensure_defaults()
except Exception:
    pass
try:
    retention_service.ensure_defaults()
except Exception:
    pass

app = FastAPI(title="Private CTO OS API", version="0.1.0")
app.add_middleware(InternalAuthMiddleware)

origins = os.getenv("CTO_OS_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


DEFAULT_PROMPT_TEMPLATES = [
    ("Deep Codebase Audit", "engineering", "technical-cto", "Audit {{project}} for architecture, risks, coupling, missing tests, and the next highest-leverage fixes.\n\nFocus: {{prompt}}", ["project", "prompt"]),
    ("Build Feature from Task", "engineering", "engineering-builder", "Turn this task into a build plan for {{project}}:\n\n{{task}}\n\nInclude files, steps, tests, and rollback.", ["project", "task"]),
    ("Debug Runtime Error", "engineering", "engineering-builder", "Debug this runtime error in {{project}}. Include probable root causes, checks, and a minimal fix path.\n\n{{error}}", ["project", "error"]),
    ("Generate Investor Deck", "business", "finance-monetization-analyst", "Generate an investor deck narrative for {{project}} using source-of-truth memory. Include problem, market, product, traction, model, and ask.", ["project"]),
    ("Generate Product Roadmap", "product", "product-strategist", "Generate a phased product roadmap for {{project}} with milestones, dependencies, risks, and acceptance criteria.", ["project"]),
    ("Generate Landing Page", "growth", "growth-strategist", "Generate landing page copy and structure for {{project}}. Keep claims grounded in project memory.", ["project"]),
    ("Generate UX Audit", "design", "ux-ui-designer", "Audit the UX for {{project}}. Focus on workflows, hierarchy, friction, and concrete redesign moves.", ["project"]),
    ("Generate Market Research Brief", "research", "research-analyst", "Generate a market research brief for {{project}} with evidence, assumptions, competitors, and open questions.", ["project"]),
    ("Generate Claude/Cursor Build Prompt", "engineering", "engineering-builder", "Write a Claude/Cursor build prompt for {{project}} from this implementation target:\n\n{{target}}", ["project", "target"]),
    ("Generate Codex Implementation Prompt", "engineering", "engineering-builder", "Write a Codex implementation prompt for {{project}}. Preserve MemPalace isolation and internal-only constraints.\n\nTarget:\n{{target}}", ["project", "target"]),
]


def seed_default_prompt_templates() -> None:
    existing = {template.name for template in store.list_prompt_templates()}
    for name, category, agent_type, body, variables in DEFAULT_PROMPT_TEMPLATES:
        if name not in existing:
            store.create_prompt_template(
                PromptTemplateCreate(
                    name=name,
                    description=f"Default {category} prompt for the private CTO OS.",
                    category=category,
                    agent_type=agent_type,
                    template_body=body,
                    template=body,
                    input_variables=variables,
                )
            )


seed_default_prompt_templates()


def not_found(entity: str, entity_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{entity} not found: {entity_id}")


def log_event(project_id: str, event_type: ExecutionEventType, title: str, summary: str = "", task_id: str | None = None, output_id: str | None = None, metadata: dict | None = None) -> None:
    try:
        store.create_log(
            project_id,
            ExecutionLogCreate(
                event_type=event_type,
                title=title,
                summary=summary,
                task_id=task_id,
                output_id=output_id,
                metadata=metadata or {},
            ),
        )
    except Exception:
        pass


execution_engine = ExecutionEngine(store, memory_engine, workspace_generator, log_event, repo_operator)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "mode": "private-internal",
        "memory_backend": memory_engine.backend_name,
    }


@app.get("/projects", response_model=list[Project])
def list_projects() -> list[Project]:
    return store.list_projects()


@app.post("/projects", response_model=Project)
def create_project(payload: ProjectCreate) -> Project:
    return store.create_project(payload)


@app.get("/projects/{project_id}", response_model=Project)
def get_project(project_id: str) -> Project:
    try:
        return store.get_project(project_id)
    except KeyError:
        raise not_found("project", project_id)


@app.get("/projects/{project_id}/memories", response_model=list[Memory])
def list_memories(project_id: str, pinned: bool | None = None) -> list[Memory]:
    try:
        store.get_project(project_id)
        return store.list_memories(project_id=project_id, pinned=pinned)
    except KeyError:
        raise not_found("project", project_id)


@app.post("/projects/{project_id}/memories", response_model=Memory)
def create_memory(project_id: str, payload: MemoryCreate) -> Memory:
    try:
        memory = store.create_memory(project_id, payload)
        memory_engine.index_memory(memory)
        log_event(project_id, ExecutionEventType.memory_added, "Memory added", memory.title, metadata={"memory_id": memory.id, "pinned": memory.pinned})
        return memory
    except KeyError:
        raise not_found("project", project_id)


@app.patch("/projects/{project_id}/memories/{memory_id}/pin", response_model=Memory)
def pin_memory(project_id: str, memory_id: str, pinned: bool = True) -> Memory:
    try:
        memory = store.update_memory_pin(project_id, memory_id, pinned)
        memory_engine.index_memory(memory)
        log_event(project_id, ExecutionEventType.memory_added, "Memory pin updated", memory.title, metadata={"memory_id": memory.id, "pinned": pinned})
        return memory
    except KeyError:
        raise not_found("memory", memory_id)


@app.get("/projects/{project_id}/memories/search", response_model=SearchResult)
def search_memories(
    project_id: str,
    q: str = "",
    cross_project: bool = Query(default=False, description="Explicitly allow cross-project memory retrieval."),
) -> SearchResult:
    try:
        store.get_project(project_id)
    except KeyError:
        raise not_found("project", project_id)
    return SearchResult(memories=memory_engine.search(project_id, q, cross_project=cross_project), cross_project=cross_project)


@app.get("/projects/{project_id}/decisions", response_model=list[Decision])
def list_decisions(project_id: str) -> list[Decision]:
    try:
        store.get_project(project_id)
        return store.list_decisions(project_id)
    except KeyError:
        raise not_found("project", project_id)


@app.post("/projects/{project_id}/decisions", response_model=Decision)
def create_decision(project_id: str, payload: DecisionCreate) -> Decision:
    try:
        decision = store.create_decision(project_id, payload)
        log_event(project_id, ExecutionEventType.decision_created, "Decision created", decision.title, metadata={"decision_id": decision.id, "decision_type": decision.decision_type.value, "impact_level": decision.impact_level.value})
        return decision
    except KeyError:
        raise not_found("project", project_id)


@app.post("/projects/{project_id}/architecture/generate", response_model=GeneratedOutput)
def generate_architecture(project_id: str, payload: ArchitectureGenerateRequest) -> GeneratedOutput:
    try:
        output = workspace_generator.generate_architecture(project_id, payload)
        log_event(project_id, ExecutionEventType.architecture_generated, "Architecture generated", "Architecture output saved.", output_id=output.id)
        return output
    except KeyError as exc:
        raise not_found("entity", str(exc))


@app.post("/projects/{project_id}/roadmap/generate", response_model=GeneratedOutput)
def generate_roadmap(project_id: str, payload: RoadmapGenerateRequest) -> GeneratedOutput:
    try:
        output = workspace_generator.generate_roadmap(project_id, payload)
        log_event(project_id, ExecutionEventType.roadmap_generated, "Roadmap generated", "Roadmap output saved.", output_id=output.id)
        return output
    except KeyError as exc:
        raise not_found("entity", str(exc))


@app.get("/projects/{project_id}/tasks", response_model=list[Task])
def list_tasks(project_id: str) -> list[Task]:
    try:
        store.get_project(project_id)
        return store.list_tasks(project_id)
    except KeyError:
        raise not_found("project", project_id)


@app.post("/projects/{project_id}/tasks", response_model=Task)
def create_task(project_id: str, payload: TaskCreate) -> Task:
    try:
        task = store.create_task(project_id, payload)
        log_event(project_id, ExecutionEventType.task_update, "Task created", task.title, task_id=task.id, metadata={"status": task.status.value})
        return task
    except KeyError:
        raise not_found("project", project_id)


@app.patch("/projects/{project_id}/tasks/{task_id}", response_model=Task)
def update_task(project_id: str, task_id: str, payload: TaskUpdate) -> Task:
    try:
        task = store.update_task(project_id, task_id, payload)
        log_event(project_id, ExecutionEventType.task_update, "Task updated", task.title, task_id=task.id, metadata={"status": task.status.value})
        return task
    except KeyError:
        raise not_found("task", task_id)


@app.delete("/projects/{project_id}/tasks/{task_id}")
def delete_task(project_id: str, task_id: str) -> dict[str, str]:
    try:
        store.delete_task(project_id, task_id)
        return {"status": "deleted"}
    except KeyError:
        raise not_found("task", task_id)


@app.post("/projects/{project_id}/tasks/generate-from-roadmap", response_model=list[Task])
def generate_tasks_from_roadmap(project_id: str, payload: GenerateTasksRequest) -> list[Task]:
    try:
        tasks = workspace_generator.tasks_from_roadmap(project_id, payload.output_id, payload.limit)
        log_event(project_id, ExecutionEventType.task_update, "Tasks generated from roadmap", f"Created {len(tasks)} task(s).")
        return tasks
    except KeyError as exc:
        raise not_found("output", str(exc))


@app.post("/projects/{project_id}/tasks/generate-from-output/{output_id}", response_model=list[Task])
def generate_tasks_from_output(project_id: str, output_id: str, payload: GenerateTasksRequest | None = None) -> list[Task]:
    try:
        tasks = workspace_generator.tasks_from_output(project_id, output_id, payload.limit if payload else 8)
        log_event(project_id, ExecutionEventType.task_update, "Tasks generated from output", f"Created {len(tasks)} task(s).", output_id=output_id)
        return tasks
    except KeyError:
        raise not_found("output", output_id)


@app.post("/projects/{project_id}/implementation-plan/generate", response_model=GeneratedOutput)
def generate_implementation_plan(project_id: str, payload: ImplementationPlanRequest) -> GeneratedOutput:
    try:
        output = workspace_generator.generate_implementation_plan(project_id, payload)
        log_event(project_id, ExecutionEventType.implementation_plan_generated, "Implementation plan generated", "Implementation plan output saved.", output_id=output.id, metadata={"source_type": payload.source_type, "source_id": payload.source_id})
        return output
    except KeyError as exc:
        raise not_found("entity", str(exc))


@app.get("/agents")
def list_agents():
    return DEFAULT_AGENTS


@app.get("/projects/{project_id}/outputs", response_model=list[GeneratedOutput])
def list_outputs(project_id: str) -> list[GeneratedOutput]:
    try:
        store.get_project(project_id)
        return store.list_outputs(project_id)
    except KeyError:
        raise not_found("project", project_id)


@app.post("/projects/{project_id}/outputs/generate", response_model=GeneratedOutput)
def generate_output(project_id: str, payload: GenerateRequest) -> GeneratedOutput:
    try:
        generated = prompt_service.generate(project_id, payload)
        for memory in store.list_memories(project_id=project_id):
            if memory.source == "generated_output" and memory.content == generated.output:
                memory_engine.index_memory(memory)
                break
        log_event(project_id, ExecutionEventType.generation, "Workspace output generated", generated.prompt[:160], output_id=generated.id)
        return generated
    except KeyError as exc:
        raise not_found("entity", str(exc))


@app.get("/prompt-templates", response_model=list[PromptTemplate])
def list_prompt_templates(project_id: str | None = None, include_global: bool = True) -> list[PromptTemplate]:
    return store.list_prompt_templates(project_id=project_id, include_global=include_global)


@app.post("/prompt-templates", response_model=PromptTemplate)
def create_prompt_template(payload: PromptTemplateCreate) -> PromptTemplate:
    return store.create_prompt_template(payload)


@app.post("/prompt-templates/{template_id}/duplicate", response_model=PromptTemplate)
def duplicate_prompt_template(template_id: str, project_id: str | None = None) -> PromptTemplate:
    try:
        return store.duplicate_prompt_template(template_id, project_id=project_id)
    except KeyError:
        raise not_found("prompt_template", template_id)


@app.post("/projects/{project_id}/prompts/generate", response_model=GeneratedOutput)
def generate_prompt_from_template(project_id: str, payload: PromptGenerateFromTemplateRequest) -> GeneratedOutput:
    try:
        project = store.get_project(project_id)
        template = store.get_prompt_template(payload.template_id)
    except KeyError as exc:
        raise not_found("entity", str(exc))
    body = template.template_body or template.template
    variables = {"project": project.name, **payload.variables}
    for key, value in variables.items():
        body = body.replace("{{" + key + "}}", value)
    llm_result = llm_service.generate(
        "You are a prompt engineer for an internal CTO OS. Return only the final reusable prompt.",
        f"Improve and ground this prompt for project {project.name}:\n\n{body}",
        {"project_id": project_id, "template_id": template.id},
    )
    output_body = body if llm_result.get("fallback") else llm_result.text
    generated = GeneratedOutput(
        project_id=project_id,
        agent_id=payload.agent_id or template.agent_type or "technical-cto",
        prompt=f"Generate prompt from template: {template.name}",
        output=output_body,
        metadata={"output_type": "prompt", "template_id": template.id, "raw_prompt": body, "llm": {key: value for key, value in llm_result.items() if key not in {"text", "raw"}}},
    )
    if payload.save_output:
        store.save_output(generated)
        log_event(project_id, ExecutionEventType.generation, "Prompt generated", template.name, output_id=generated.id)
    return generated


@app.get("/projects/{project_id}/brief", response_model=ProjectBrief)
def get_project_brief(project_id: str) -> ProjectBrief:
    try:
        return workspace_generator.current_brief(project_id)
    except KeyError:
        raise not_found("project", project_id)


@app.post("/projects/{project_id}/brief/generate", response_model=GeneratedOutput)
def generate_project_brief(project_id: str, payload: BriefGenerateRequest) -> GeneratedOutput:
    try:
        output = workspace_generator.generate_brief(project_id, payload)
        log_event(project_id, ExecutionEventType.generation, "Project brief generated", "Project brief output saved.", output_id=output.id)
        return output
    except KeyError as exc:
        raise not_found("entity", str(exc))


@app.get("/projects/{project_id}/logs", response_model=list[ExecutionLog])
def list_logs(project_id: str) -> list[ExecutionLog]:
    try:
        store.get_project(project_id)
        return store.list_logs(project_id)
    except KeyError:
        raise not_found("project", project_id)


@app.post("/projects/{project_id}/logs", response_model=ExecutionLog)
def create_log(project_id: str, payload: ExecutionLogCreate) -> ExecutionLog:
    try:
        return store.create_log(project_id, payload)
    except KeyError:
        raise not_found("project", project_id)


@app.get("/projects/{project_id}/risks", response_model=list[Risk])
def list_risks(project_id: str) -> list[Risk]:
    try:
        store.get_project(project_id)
        return store.list_risks(project_id)
    except KeyError:
        raise not_found("project", project_id)


@app.post("/projects/{project_id}/risks/generate", response_model=list[Risk])
def generate_risks(project_id: str) -> list[Risk]:
    try:
        risks = workspace_generator.generate_risks(project_id)
        log_event(project_id, ExecutionEventType.generation, "Risks generated", f"Generated {len(risks)} risk(s).")
        return risks
    except KeyError:
        raise not_found("project", project_id)


@app.patch("/projects/{project_id}/risks/{risk_id}", response_model=Risk)
def update_risk(project_id: str, risk_id: str, payload: RiskUpdate) -> Risk:
    try:
        return store.update_risk(project_id, risk_id, payload)
    except KeyError:
        raise not_found("risk", risk_id)


@app.get("/projects/{project_id}/briefs", response_model=list[GeneratedOutput])
def list_briefs(project_id: str) -> list[GeneratedOutput]:
    try:
        store.get_project(project_id)
        return [output for output in store.list_outputs(project_id) if output.metadata.get("output_type") in {"weekly_brief", "brief"}]
    except KeyError:
        raise not_found("project", project_id)


@app.post("/projects/{project_id}/briefs/weekly/generate", response_model=GeneratedOutput)
def generate_weekly_brief(project_id: str) -> GeneratedOutput:
    try:
        output = workspace_generator.generate_weekly_brief(project_id)
        log_event(project_id, ExecutionEventType.generation, "Weekly CTO brief generated", "Weekly CTO brief output saved.", output_id=output.id)
        return output
    except KeyError as exc:
        raise not_found("entity", str(exc))


@app.get("/projects/{project_id}/implementation-reviews", response_model=list[ImplementationReview])
def list_implementation_reviews(project_id: str) -> list[ImplementationReview]:
    try:
        store.get_project(project_id)
        return store.list_reviews(project_id)
    except KeyError:
        raise not_found("project", project_id)


@app.post("/projects/{project_id}/implementation-reviews", response_model=ImplementationReview)
def create_implementation_review(project_id: str, payload: ImplementationReviewCreate) -> ImplementationReview:
    try:
        review = workspace_generator.review_implementation(project_id, payload)
        log_event(project_id, ExecutionEventType.generation, "Implementation reviewed", review.recommendation.value, task_id=review.task_id, output_id=review.output_id)
        return review
    except KeyError as exc:
        raise not_found("entity", str(exc))


@app.get("/projects/{project_id}/jobs", response_model=list[Job])
def list_jobs(project_id: str, status: str | None = None, type: str | None = None) -> list[Job]:
    try:
        store.get_project(project_id)
        return store.list_jobs(project_id, status=status, job_type=type)
    except KeyError:
        raise not_found("project", project_id)


@app.post("/projects/{project_id}/jobs", response_model=Job)
def create_job(project_id: str, payload: JobCreate) -> Job:
    try:
        return execution_engine.create_job(project_id, payload)
    except KeyError:
        raise not_found("project", project_id)


@app.post("/projects/{project_id}/jobs/{job_id}/run", response_model=Job)
def run_job(project_id: str, job_id: str) -> Job:
    try:
        return execution_engine.run_job(project_id, job_id)
    except KeyError:
        raise not_found("job", job_id)


@app.post("/projects/{project_id}/jobs/{job_id}/cancel", response_model=Job)
def cancel_job(project_id: str, job_id: str) -> Job:
    try:
        return execution_engine.cancel_job(project_id, job_id)
    except KeyError:
        raise not_found("job", job_id)


@app.get("/projects/{project_id}/workflows", response_model=list[WorkflowRun])
def list_workflows(project_id: str) -> list[WorkflowRun]:
    try:
        store.get_project(project_id)
        return store.list_workflows(project_id)
    except KeyError:
        raise not_found("project", project_id)


@app.get("/workflows/defaults")
def default_workflows() -> dict[str, list[dict]]:
    return DEFAULT_WORKFLOW_STEPS


@app.post("/projects/{project_id}/workflows/run", response_model=WorkflowRun)
def run_workflow(project_id: str, payload: WorkflowRunCreate) -> WorkflowRun:
    try:
        return execution_engine.run_workflow(project_id, payload)
    except KeyError:
        raise not_found("project", project_id)


@app.get("/projects/{project_id}/build-packets", response_model=list[BuildPacket])
def list_build_packets(project_id: str) -> list[BuildPacket]:
    try:
        store.get_project(project_id)
        return store.list_build_packets(project_id)
    except KeyError:
        raise not_found("project", project_id)


@app.get("/projects/{project_id}/build-packets/{packet_id}", response_model=BuildPacket)
def get_build_packet(project_id: str, packet_id: str) -> BuildPacket:
    try:
        return store.get_build_packet(project_id, packet_id)
    except KeyError:
        raise not_found("build_packet", packet_id)


@app.post("/projects/{project_id}/build-packets/generate", response_model=BuildPacket)
def generate_build_packet(project_id: str, payload: BuildPacketGenerateRequest) -> BuildPacket:
    try:
        return execution_engine.generate_build_packet(project_id, payload)
    except KeyError as exc:
        raise not_found("entity", str(exc))


@app.get("/projects/{project_id}/repositories", response_model=list[Repository])
def list_repositories(project_id: str) -> list[Repository]:
    try:
        store.get_project(project_id)
        return store.list_repositories(project_id)
    except KeyError:
        raise not_found("project", project_id)


@app.post("/projects/{project_id}/repositories", response_model=Repository)
def create_repository(project_id: str, payload: RepositoryCreate) -> Repository:
    try:
        repository = store.create_repository(project_id, payload)
        log_event(project_id, ExecutionEventType.generation, "Repository added", repository.name, metadata={"repository_id": repository.id, "provider": repository.provider.value})
        return repository
    except KeyError:
        raise not_found("project", project_id)


@app.patch("/projects/{project_id}/repositories/{repository_id}", response_model=Repository)
def update_repository(project_id: str, repository_id: str, payload: RepositoryUpdate) -> Repository:
    try:
        return store.update_repository(project_id, repository_id, payload)
    except KeyError:
        raise not_found("repository", repository_id)


@app.delete("/projects/{project_id}/repositories/{repository_id}")
def delete_repository(project_id: str, repository_id: str) -> dict[str, str]:
    try:
        store.delete_repository(project_id, repository_id)
        return {"status": "deleted"}
    except KeyError:
        raise not_found("repository", repository_id)


@app.post("/projects/{project_id}/repositories/{repository_id}/scan", response_model=RepoScan)
def scan_repository(project_id: str, repository_id: str) -> RepoScan:
    try:
        scan = repo_operator.scan_repository(project_id, repository_id)
        log_event(project_id, ExecutionEventType.generation, "Repository scanned", scan.summary, metadata={"repository_id": repository_id, "scan_id": scan.id})
        return scan
    except KeyError:
        raise not_found("repository", repository_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/projects/{project_id}/repositories/{repository_id}/scans", response_model=list[RepoScan])
def list_repo_scans(project_id: str, repository_id: str) -> list[RepoScan]:
    try:
        store.get_repository(project_id, repository_id)
        return store.list_repo_scans(project_id, repository_id)
    except KeyError:
        raise not_found("repository", repository_id)


@app.get("/projects/{project_id}/repositories/{repository_id}/files", response_model=list[RepoFile])
def list_repo_files(project_id: str, repository_id: str) -> list[RepoFile]:
    try:
        store.get_repository(project_id, repository_id)
        return store.list_repo_files(project_id, repository_id)
    except KeyError:
        raise not_found("repository", repository_id)


@app.get("/projects/{project_id}/repositories/{repository_id}/files/search", response_model=list[RepoFile])
def search_repo_files(project_id: str, repository_id: str, q: str = "") -> list[RepoFile]:
    try:
        store.get_repository(project_id, repository_id)
        return store.search_repo_files(project_id, repository_id, q)
    except KeyError:
        raise not_found("repository", repository_id)


@app.get("/projects/{project_id}/repositories/{repository_id}/files/{file_id}", response_model=RepoFile)
def get_repo_file(project_id: str, repository_id: str, file_id: str) -> RepoFile:
    try:
        return store.get_repo_file(project_id, repository_id, file_id)
    except KeyError:
        raise not_found("repo_file", file_id)


@app.get("/projects/{project_id}/repositories/{repository_id}/symbols", response_model=list[CodeSymbol])
def list_symbols(project_id: str, repository_id: str) -> list[CodeSymbol]:
    try:
        store.get_repository(project_id, repository_id)
        return store.list_code_symbols(project_id, repository_id)
    except KeyError:
        raise not_found("repository", repository_id)


@app.get("/projects/{project_id}/repositories/{repository_id}/symbols/search", response_model=list[CodeSymbol])
def search_symbols(project_id: str, repository_id: str, q: str = "") -> list[CodeSymbol]:
    try:
        store.get_repository(project_id, repository_id)
        return store.search_code_symbols(project_id, repository_id, q)
    except KeyError:
        raise not_found("repository", repository_id)


@app.get("/projects/{project_id}/repositories/{repository_id}/dependencies", response_model=list[CodeDependency])
def list_dependencies(project_id: str, repository_id: str) -> list[CodeDependency]:
    try:
        store.get_repository(project_id, repository_id)
        return store.list_code_dependencies(project_id, repository_id)
    except KeyError:
        raise not_found("repository", repository_id)


@app.get("/projects/{project_id}/repositories/{repository_id}/git/status", response_model=GitStatus)
def git_status(project_id: str, repository_id: str) -> GitStatus:
    try:
        return git_reader.status(store.get_repository(project_id, repository_id))
    except KeyError:
        raise not_found("repository", repository_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/projects/{project_id}/repositories/{repository_id}/git/diff", response_model=GitDiff)
def git_diff(project_id: str, repository_id: str, payload: GitDiffRequest) -> GitDiff:
    try:
        return git_reader.diff(store.get_repository(project_id, repository_id), include_diff=payload.include_diff)
    except KeyError:
        raise not_found("repository", repository_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/projects/{project_id}/repositories/{repository_id}/commands", response_model=list[ApprovedCommand])
def list_commands(project_id: str, repository_id: str) -> list[ApprovedCommand]:
    try:
        store.get_repository(project_id, repository_id)
        return store.list_approved_commands(project_id, repository_id)
    except KeyError:
        raise not_found("repository", repository_id)


@app.post("/projects/{project_id}/repositories/{repository_id}/commands", response_model=ApprovedCommand)
def approve_command(project_id: str, repository_id: str, payload: ApprovedCommandCreate) -> ApprovedCommand:
    try:
        return command_runner.approve(project_id, repository_id, payload)
    except KeyError:
        raise not_found("repository", repository_id)
    except CommandSafetyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/projects/{project_id}/repositories/{repository_id}/commands/{command_id}/run", response_model=TestRun)
def run_command(project_id: str, repository_id: str, command_id: str) -> TestRun:
    try:
        return command_runner.run(project_id, repository_id, command_id)
    except KeyError:
        raise not_found("command", command_id)
    except CommandSafetyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/projects/{project_id}/repositories/{repository_id}/index-to-memory", response_model=list[Memory])
def index_repo_to_memory(project_id: str, repository_id: str) -> list[Memory]:
    try:
        memories = repo_operator.index_repo_to_memory(project_id, repository_id)
        log_event(project_id, ExecutionEventType.memory_added, "Repository context indexed", f"Saved {len(memories)} repo context memories.", metadata={"repository_id": repository_id})
        return memories
    except KeyError:
        raise not_found("repository", repository_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/projects/{project_id}/branch-plans/generate", response_model=BranchPlan)
def generate_branch_plan(project_id: str, payload: BranchPlanGenerateRequest) -> BranchPlan:
    try:
        return repo_operator.generate_branch_plan(project_id, payload)
    except KeyError as exc:
        raise not_found("entity", str(exc))


@app.get("/projects/{project_id}/branch-plans", response_model=list[BranchPlan])
def list_branch_plans(project_id: str) -> list[BranchPlan]:
    try:
        store.get_project(project_id)
        return store.list_branch_plans(project_id)
    except KeyError:
        raise not_found("project", project_id)


@app.post("/projects/{project_id}/pr-packets/generate", response_model=PRPacket)
def generate_pr_packet(project_id: str, payload: PRPacketGenerateRequest) -> PRPacket:
    try:
        return repo_operator.generate_pr_packet(project_id, payload)
    except KeyError as exc:
        raise not_found("entity", str(exc))


@app.get("/projects/{project_id}/pr-packets", response_model=list[PRPacket])
def list_pr_packets(project_id: str) -> list[PRPacket]:
    try:
        store.get_project(project_id)
        return store.list_pr_packets(project_id)
    except KeyError:
        raise not_found("project", project_id)


@app.post("/projects/{project_id}/code-reviews", response_model=CodeReview)
def create_code_review(project_id: str, payload: CodeReviewCreate) -> CodeReview:
    try:
        return repo_operator.review_diff(project_id, payload)
    except KeyError as exc:
        raise not_found("entity", str(exc))


# Phase 15: convenience — pull current git diff for a repo and review it
# in one round trip. Saves callers from shelling out themselves.
@app.post(
    "/projects/{project_id}/repositories/{repository_id}/code-reviews/from-git",
    response_model=CodeReview,
)
def code_review_from_git(
    project_id: str,
    repository_id: str,
    task_id: str | None = None,
    branch_plan_id: str | None = None,
    create_follow_up_tasks: bool = False,
) -> CodeReview:
    try:
        repository = store.get_repository(project_id, repository_id)
    except KeyError:
        raise not_found("repository", repository_id)
    diff_text = git_reader.read_diff(repository)
    if not diff_text.strip():
        raise HTTPException(
            status_code=400,
            detail="No working-tree diff to review (git diff was empty).",
        )
    return repo_operator.review_diff(
        project_id,
        CodeReviewCreate(
            diff_text=diff_text,
            repository_id=repository_id,
            task_id=task_id,
            branch_plan_id=branch_plan_id,
            create_follow_up_tasks=create_follow_up_tasks,
        ),
    )


@app.get("/projects/{project_id}/code-reviews", response_model=list[CodeReview])
def list_code_reviews(project_id: str) -> list[CodeReview]:
    try:
        store.get_project(project_id)
        return store.list_code_reviews(project_id)
    except KeyError:
        raise not_found("project", project_id)


@app.post("/projects/{project_id}/test-runs", response_model=TestRun)
def create_test_run(project_id: str, payload: TestRunCreate) -> TestRun:
    try:
        return repo_operator.record_test_run(project_id, payload)
    except KeyError as exc:
        raise not_found("entity", str(exc))


@app.get("/projects/{project_id}/test-runs", response_model=list[TestRun])
def list_test_runs(project_id: str) -> list[TestRun]:
    try:
        store.get_project(project_id)
        return store.list_test_runs(project_id)
    except KeyError:
        raise not_found("project", project_id)


@app.get("/projects/{project_id}/build-sessions", response_model=list[BuildSession])
def list_build_sessions(project_id: str) -> list[BuildSession]:
    try:
        store.get_project(project_id)
        return store.list_build_sessions(project_id)
    except KeyError:
        raise not_found("project", project_id)


@app.post("/projects/{project_id}/build-sessions", response_model=BuildSession)
def create_build_session(project_id: str, payload: BuildSessionCreate) -> BuildSession:
    try:
        return store.create_build_session(project_id, payload)
    except KeyError:
        raise not_found("project", project_id)


@app.patch("/projects/{project_id}/build-sessions/{session_id}", response_model=BuildSession)
def update_build_session(project_id: str, session_id: str, payload: BuildSessionUpdate) -> BuildSession:
    try:
        return store.update_build_session(project_id, session_id, payload)
    except KeyError:
        raise not_found("build_session", session_id)


@app.post("/projects/{project_id}/build-sessions/{session_id}/summarize", response_model=BuildSession)
def summarize_build_session(project_id: str, session_id: str) -> BuildSession:
    try:
        return repo_operator.summarize_build_session(project_id, session_id)
    except KeyError:
        raise not_found("build_session", session_id)


@app.post("/projects/{project_id}/build-sessions/{session_id}/save-lessons", response_model=list[Memory])
def save_build_session_lessons(project_id: str, session_id: str) -> list[Memory]:
    try:
        return repo_operator.save_build_session_lessons(project_id, session_id)
    except KeyError:
        raise not_found("build_session", session_id)


@app.get("/system/integrations/github/status")
def github_status() -> dict[str, object]:
    return github_integration.status()


@app.get("/system/integrations/github/repositories")
def github_repositories() -> list[dict]:
    try:
        return github_integration.list_repositories()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/projects/{project_id}/repositories/{repository_id}/github/sync")
def github_sync(project_id: str, repository_id: str) -> dict[str, int]:
    try:
        repo = store.get_repository(project_id, repository_id)
        issues, prs = github_integration.sync_repository(project_id, repo)
        store.replace_github_sync(project_id, repository_id, issues, prs)
        return {"issues": len(issues), "pull_requests": len(prs)}
    except KeyError:
        raise not_found("repository", repository_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/system/snapshots/create", response_model=SnapshotManifest)
def create_snapshot() -> SnapshotManifest:
    return snapshot_manager.create_snapshot()


@app.get("/system/snapshots", response_model=list[SnapshotManifest])
def list_snapshots() -> list[SnapshotManifest]:
    return snapshot_manager.list_snapshots()


@app.post("/system/snapshots/{snapshot_id}/restore", response_model=SnapshotManifest)
def restore_snapshot(snapshot_id: str) -> SnapshotManifest:
    try:
        return snapshot_manager.restore_snapshot(snapshot_id)
    except KeyError:
        raise not_found("snapshot", snapshot_id)


@app.get("/projects/{project_id}/export")
def export_project(project_id: str) -> dict:
    try:
        return store.export_project_bundle(project_id)
    except KeyError:
        raise not_found("project", project_id)


@app.post("/projects/import", response_model=Project)
async def import_project(request: Request) -> Project:
    bundle = await request.json()
    try:
        return store.import_project_bundle(bundle)
    except KeyError as exc:
        raise not_found("import", str(exc))


# ---------------------------------------------------------------- Phase 7 writes

def _log_github_write(project_id: str, event: GitHubWriteEvent) -> None:
    log_event(
        project_id,
        ExecutionEventType.generation,
        f"GitHub {event.action.value}",
        f"{event.entity_type.value} {event.entity_id} → {event.status.value}",
        metadata={
            "github_write_event_id": event.id,
            "entity_type": event.entity_type.value,
            "entity_id": event.entity_id,
            "action": event.action.value,
            "status": event.status.value,
            "dry_run": event.dry_run,
            "approved": event.approved,
            "error_message": event.error_message,
        },
    )


def _phase7_event_or_400(event: GitHubWriteEvent) -> GitHubWriteEvent:
    if event.status.value in {"blocked", "failed"} and not event.dry_run:
        # We still persisted the event for audit; surface the failure to caller.
        raise HTTPException(status_code=400, detail=event.error_message or "GitHub write was not permitted.")
    return event


@app.post("/projects/{project_id}/tasks/{task_id}/github/preview-issue", response_model=GitHubWriteEvent)
def github_preview_task_issue(project_id: str, task_id: str) -> GitHubWriteEvent:
    try:
        event = repo_operator.preview_task_issue(project_id, task_id)
        _log_github_write(project_id, event)
        return event
    except KeyError:
        raise not_found("task", task_id)


@app.post("/projects/{project_id}/tasks/{task_id}/github/create-issue", response_model=GitHubWriteEvent)
def github_create_task_issue(
    project_id: str, task_id: str, payload: GitHubIssueCreateRequest
) -> GitHubWriteEvent:
    try:
        event = repo_operator.create_task_issue(project_id, task_id, payload)
    except KeyError:
        raise not_found("task", task_id)
    _log_github_write(project_id, event)
    return _phase7_event_or_400(event)


@app.post("/projects/{project_id}/risks/{risk_id}/github/preview-issue", response_model=GitHubWriteEvent)
def github_preview_risk_issue(project_id: str, risk_id: str) -> GitHubWriteEvent:
    try:
        event = repo_operator.preview_risk_issue(project_id, risk_id)
        _log_github_write(project_id, event)
        return event
    except KeyError:
        raise not_found("risk", risk_id)


@app.post("/projects/{project_id}/risks/{risk_id}/github/create-issue", response_model=GitHubWriteEvent)
def github_create_risk_issue(
    project_id: str, risk_id: str, payload: GitHubIssueCreateRequest
) -> GitHubWriteEvent:
    try:
        event = repo_operator.create_risk_issue(project_id, risk_id, payload)
    except KeyError:
        raise not_found("risk", risk_id)
    _log_github_write(project_id, event)
    return _phase7_event_or_400(event)


@app.post(
    "/projects/{project_id}/branch-plans/{branch_plan_id}/github/preview-branch",
    response_model=GitHubWriteEvent,
)
def github_preview_branch(
    project_id: str,
    branch_plan_id: str,
    payload: GitHubBranchCreateRequest | None = None,
) -> GitHubWriteEvent:
    try:
        event = repo_operator.preview_branch(project_id, branch_plan_id, payload)
        _log_github_write(project_id, event)
        return event
    except KeyError:
        raise not_found("branch_plan", branch_plan_id)


@app.post(
    "/projects/{project_id}/branch-plans/{branch_plan_id}/github/create-branch",
    response_model=GitHubWriteEvent,
)
def github_create_branch(
    project_id: str, branch_plan_id: str, payload: GitHubBranchCreateRequest
) -> GitHubWriteEvent:
    try:
        event = repo_operator.create_branch(project_id, branch_plan_id, payload)
    except KeyError:
        raise not_found("branch_plan", branch_plan_id)
    _log_github_write(project_id, event)
    return _phase7_event_or_400(event)


@app.post(
    "/projects/{project_id}/pr-packets/{pr_packet_id}/github/preview-draft-pr",
    response_model=GitHubWriteEvent,
)
def github_preview_draft_pr(
    project_id: str,
    pr_packet_id: str,
    payload: GitHubDraftPRCreateRequest | None = None,
) -> GitHubWriteEvent:
    try:
        event = repo_operator.preview_draft_pr(project_id, pr_packet_id, payload)
        _log_github_write(project_id, event)
        return event
    except KeyError:
        raise not_found("pr_packet", pr_packet_id)


@app.post(
    "/projects/{project_id}/pr-packets/{pr_packet_id}/github/create-draft-pr",
    response_model=GitHubWriteEvent,
)
def github_create_draft_pr(
    project_id: str, pr_packet_id: str, payload: GitHubDraftPRCreateRequest
) -> GitHubWriteEvent:
    try:
        event = repo_operator.create_draft_pr(project_id, pr_packet_id, payload)
    except KeyError:
        raise not_found("pr_packet", pr_packet_id)
    _log_github_write(project_id, event)
    return _phase7_event_or_400(event)


@app.get("/projects/{project_id}/github/write-events", response_model=list[GitHubWriteEvent])
def list_github_write_events(project_id: str) -> list[GitHubWriteEvent]:
    try:
        store.get_project(project_id)
        return store.list_github_write_events(project_id)
    except KeyError:
        raise not_found("project", project_id)


# ------------------------------------------------------- Phase 8 reconciliation


@app.post("/projects/{project_id}/github/reconcile", response_model=ReconciliationReport)
def github_reconcile(
    project_id: str, payload: ReconcileRequest | None = None
) -> ReconciliationReport:
    request = payload or ReconcileRequest()
    try:
        store.get_project(project_id)
        report = reconciliation_service.reconcile(project_id, request)
    except KeyError:
        raise not_found("project", project_id)
    log_event(
        project_id,
        ExecutionEventType.generation,
        "GitHub reconcile",
        f"events={len(report.events)} suggestions={len(report.suggestions)} auto_applied={report.auto_applied} degraded={report.degraded}",
        metadata={
            "events": len(report.events),
            "suggestions": len(report.suggestions),
            "auto_applied": report.auto_applied,
            "degraded": report.degraded,
            "reason": report.reason,
        },
    )
    return report


@app.get(
    "/projects/{project_id}/github/reconciliation-events",
    response_model=list[GitHubReconciliationEvent],
)
def list_reconciliation_events(project_id: str) -> list[GitHubReconciliationEvent]:
    try:
        store.get_project(project_id)
        return store.list_reconciliation_events(project_id)
    except KeyError:
        raise not_found("project", project_id)


@app.get(
    "/projects/{project_id}/status-suggestions",
    response_model=list[StatusSuggestion],
)
def list_status_suggestions(
    project_id: str, include_resolved: bool = False
) -> list[StatusSuggestion]:
    try:
        store.get_project(project_id)
        return store.list_status_suggestions(project_id, include_resolved=include_resolved)
    except KeyError:
        raise not_found("project", project_id)


@app.post(
    "/projects/{project_id}/status-suggestions/{suggestion_id}/apply",
    response_model=StatusSuggestion,
)
def apply_status_suggestion(project_id: str, suggestion_id: str) -> StatusSuggestion:
    try:
        store.get_project(project_id)
        applied = reconciliation_service.apply_suggestion(project_id, suggestion_id)
    except KeyError:
        raise not_found("status_suggestion", suggestion_id)
    if applied is None:
        raise HTTPException(
            status_code=400,
            detail="Suggestion is already applied or dismissed.",
        )
    log_event(
        project_id,
        ExecutionEventType.task_update,
        "Status suggestion applied",
        f"{applied.entity_type.value} {applied.entity_id} → {applied.suggested_status}",
        metadata={
            "suggestion_id": applied.id,
            "entity_type": applied.entity_type.value,
            "entity_id": applied.entity_id,
            "suggested_status": applied.suggested_status,
        },
    )
    return applied


@app.post(
    "/projects/{project_id}/status-suggestions/{suggestion_id}/dismiss",
    response_model=StatusSuggestion,
)
def dismiss_status_suggestion(project_id: str, suggestion_id: str) -> StatusSuggestion:
    try:
        store.get_project(project_id)
        return reconciliation_service.dismiss_suggestion(project_id, suggestion_id)
    except KeyError:
        raise not_found("status_suggestion", suggestion_id)


@app.get(
    "/projects/{project_id}/build-sessions/{session_id}/timeline",
    response_model=BuildSessionTimeline,
)
def get_build_session_timeline(project_id: str, session_id: str) -> BuildSessionTimeline:
    try:
        store.get_project(project_id)
        return timeline_builder.build(project_id, session_id)
    except KeyError:
        raise not_found("build_session", session_id)


@app.post(
    "/projects/{project_id}/retrospectives/generate",
    response_model=PostShipRetrospective,
)
def generate_retrospective(
    project_id: str, payload: RetrospectiveGenerateRequest
) -> PostShipRetrospective:
    try:
        store.get_project(project_id)
        retro = retrospective_generator.generate(project_id, payload)
    except KeyError as exc:
        raise not_found("entity", str(exc))
    log_event(
        project_id,
        ExecutionEventType.generation,
        "Retrospective generated",
        retro.title,
        metadata={
            "retrospective_id": retro.id,
            "build_session_id": retro.build_session_id,
            "memory_ids_created": retro.memory_ids_created,
            "decision_ids_created": retro.decision_ids_created,
            "follow_up_task_ids": retro.follow_up_task_ids,
        },
    )
    return retro


@app.get(
    "/projects/{project_id}/retrospectives",
    response_model=list[PostShipRetrospective],
)
def list_retrospectives(project_id: str) -> list[PostShipRetrospective]:
    try:
        store.get_project(project_id)
        return store.list_retrospectives(project_id)
    except KeyError:
        raise not_found("project", project_id)


@app.get("/projects/{project_id}/shipped", response_model=ShippedSummary)
def get_shipped_dashboard(project_id: str) -> ShippedSummary:
    try:
        return shipped_dashboard.build(project_id)
    except KeyError:
        raise not_found("project", project_id)


# ---------------------------------------------------------------- Phase 9


@app.get("/system/control-room", response_model=ControlRoomSummary)
def system_control_room() -> ControlRoomSummary:
    return control_room.build()


@app.get("/system/shipped", response_model=SystemShippedSummary)
def system_shipped() -> SystemShippedSummary:
    return system_shipped_view.build()


@app.get("/system/risks", response_model=RiskConcentrationSummary)
def system_risks() -> RiskConcentrationSummary:
    return risk_concentration_service.build()


@app.get("/system/decisions/graph", response_model=DecisionGraph)
def system_decision_graph() -> DecisionGraph:
    return decision_graph_builder.system()


@app.get("/system/staleness", response_model=StalenessReport)
def system_staleness() -> StalenessReport:
    return staleness_detector.detect()


@app.get("/projects/{project_id}/decisions/graph", response_model=DecisionGraph)
def project_decision_graph(project_id: str) -> DecisionGraph:
    try:
        return decision_graph_builder.project(project_id)
    except KeyError:
        raise not_found("project", project_id)


# ----- Playbooks -----------------------------------------------------------


@app.get("/system/playbooks", response_model=list[Playbook])
def system_playbooks() -> list[Playbook]:
    return store.list_playbooks()


@app.get("/projects/{project_id}/playbooks", response_model=list[Playbook])
def project_playbooks(project_id: str) -> list[Playbook]:
    try:
        store.get_project(project_id)
        return store.list_playbooks(source_project_id=project_id)
    except KeyError:
        raise not_found("project", project_id)


@app.post(
    "/projects/{project_id}/build-sessions/{session_id}/playbooks/generate",
    response_model=Playbook,
)
def generate_playbook(
    project_id: str, session_id: str, payload: PlaybookGenerateRequest | None = None
) -> Playbook:
    try:
        store.get_project(project_id)
        return playbook_service.generate(project_id, session_id, payload or PlaybookGenerateRequest())
    except KeyError:
        raise not_found("build_session", session_id)


@app.post(
    "/projects/{project_id}/tasks/{task_id}/playbooks/apply",
    response_model=GeneratedOutput,
)
def apply_playbook(
    project_id: str, task_id: str, payload: PlaybookApplyRequest
) -> GeneratedOutput:
    try:
        store.get_project(project_id)
        return playbook_service.apply(project_id, task_id, payload)
    except KeyError as exc:
        raise not_found("entity", str(exc))


# ----- Outcome scoring -----------------------------------------------------


@app.post("/projects/{project_id}/outcome-scores", response_model=OutcomeScore)
def create_outcome_score(project_id: str, payload: OutcomeScoreCreate) -> OutcomeScore:
    try:
        return outcome_scoring.record(project_id, payload)
    except KeyError:
        raise not_found("project", project_id)


@app.get("/projects/{project_id}/outcome-scores", response_model=list[OutcomeScore])
def list_outcome_scores(project_id: str) -> list[OutcomeScore]:
    try:
        store.get_project(project_id)
        return outcome_scoring.project_scores(project_id)
    except KeyError:
        raise not_found("project", project_id)


@app.get("/system/outcome-scores", response_model=list[OutcomeScore])
def list_system_outcome_scores() -> list[OutcomeScore]:
    return outcome_scoring.system_scores()


# ----- Notifications -------------------------------------------------------


@app.get("/system/notifications/rules", response_model=list[NotificationRule])
def list_notification_rules() -> list[NotificationRule]:
    return store.list_notification_rules()


@app.post("/system/notifications/rules", response_model=NotificationRule)
def create_notification_rule(payload: NotificationRuleCreate) -> NotificationRule:
    return store.create_notification_rule(payload)


@app.patch(
    "/system/notifications/rules/{rule_id}", response_model=NotificationRule
)
def update_notification_rule(rule_id: str, payload: NotificationRuleUpdate) -> NotificationRule:
    try:
        return store.update_notification_rule(rule_id, payload)
    except KeyError:
        raise not_found("notification_rule", rule_id)


@app.post(
    "/system/notifications/test", response_model=NotificationEvent
)
def test_notification(payload: NotificationTestRequest) -> NotificationEvent:
    try:
        return notification_service.test(payload.rule_id, payload.payload)
    except KeyError:
        raise not_found("notification_rule", payload.rule_id)


@app.get(
    "/system/notifications/events", response_model=list[NotificationEvent]
)
def list_notification_events() -> list[NotificationEvent]:
    return store.list_notification_events()


# ---------------------------------------------------------------- Phase 10


@app.post(
    "/projects/{project_id}/context/code-review", response_model=LLMContextBundle
)
def context_code_review(project_id: str, payload: CodeReviewContextRequest) -> LLMContextBundle:
    try:
        return context_builder.code_review(project_id, payload)
    except KeyError:
        raise not_found("project", project_id)


@app.post(
    "/projects/{project_id}/context/retrospective", response_model=LLMContextBundle
)
def context_retrospective(project_id: str, payload: RetrospectiveContextRequest) -> LLMContextBundle:
    try:
        return context_builder.retrospective(project_id, payload)
    except KeyError:
        raise not_found("project", project_id)


@app.post(
    "/projects/{project_id}/context/implementation-plan", response_model=LLMContextBundle
)
def context_implementation_plan(
    project_id: str, payload: ImplementationPlanContextRequest
) -> LLMContextBundle:
    try:
        return context_builder.implementation_plan(project_id, payload)
    except KeyError:
        raise not_found("project", project_id)


@app.post(
    "/projects/{project_id}/context/build-packet", response_model=LLMContextBundle
)
def context_build_packet(project_id: str, payload: BuildPacketContextRequest) -> LLMContextBundle:
    try:
        return context_builder.build_packet(project_id, payload)
    except KeyError:
        raise not_found("project", project_id)


@app.post(
    "/projects/{project_id}/llm-results/code-review", response_model=CodeReview
)
def save_code_review_result(project_id: str, payload: CodeReviewSaveRequest) -> CodeReview:
    try:
        return llm_results.save_code_review(project_id, payload)
    except KeyError:
        raise not_found("project", project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post(
    "/projects/{project_id}/llm-results/retrospective", response_model=PostShipRetrospective
)
def save_retrospective_result(
    project_id: str, payload: RetrospectiveSaveRequest
) -> PostShipRetrospective:
    try:
        return llm_results.save_retrospective(project_id, payload)
    except KeyError:
        raise not_found("project", project_id)


@app.post(
    "/projects/{project_id}/llm-results/implementation-plan", response_model=GeneratedOutput
)
def save_implementation_plan_result(
    project_id: str, payload: ImplementationPlanSaveRequest
) -> GeneratedOutput:
    try:
        return llm_results.save_implementation_plan(project_id, payload)
    except KeyError:
        raise not_found("project", project_id)


@app.post(
    "/projects/{project_id}/llm-results/build-packet", response_model=BuildPacket
)
def save_build_packet_result(project_id: str, payload: BuildPacketSaveRequest) -> BuildPacket:
    try:
        return llm_results.save_build_packet(project_id, payload)
    except KeyError:
        raise not_found("project", project_id)


# ---------------------------------------------------------------- Phase 11


@app.post("/intake/events", response_model=IntakeEvent)
async def intake_events(request: Request) -> IntakeEvent:
    raw_body = await request.body()
    try:
        intake_service.assert_enabled()
    except IntakeDisabledError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    provided_signature = request.headers.get("X-CTO-OS-Signature") or request.headers.get(
        "x-cto-os-signature"
    )
    try:
        intake_service.verify_signature(raw_body, provided_signature)
    except IntakeAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    try:
        payload = parse_intake_body(raw_body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    create_suggestion = bool(request.query_params.get("create_suggestion"))
    event = intake_service.record(payload, create_suggestion=create_suggestion)
    log_event(
        payload.project_id or "system",
        ExecutionEventType.generation,
        f"Intake event: {event.source.value}",
        event.note[:200],
        metadata={
            "intake_event_id": event.id,
            "source": event.source.value,
            "suggestion_id": event.suggestion_id,
        },
    ) if payload.project_id else None
    return event


@app.get("/intake/events", response_model=list[IntakeEvent])
def list_intake_events(limit: int = 100) -> list[IntakeEvent]:
    return intake_service.list_events(limit=limit)


# ---------------------------------------------------------------- Phase 12


@app.get("/system/health", response_model=SystemHealth)
def system_health() -> SystemHealth:
    return health_service.build()


@app.get("/system/workers", response_model=list[WorkerHeartbeat])
def list_workers() -> list[WorkerHeartbeat]:
    return store.list_worker_heartbeats()


@app.post(
    "/system/snapshots/{snapshot_id}/verify", response_model=SnapshotIntegrity
)
def verify_snapshot(snapshot_id: str) -> SnapshotIntegrity:
    return snapshot_manager.verify(snapshot_id)


@app.post(
    "/system/snapshots/{snapshot_id}/restore-preview", response_model=SnapshotRestorePreview
)
def restore_snapshot_preview(snapshot_id: str) -> SnapshotRestorePreview:
    try:
        return snapshot_manager.restore_preview(snapshot_id)
    except KeyError:
        raise not_found("snapshot", snapshot_id)


@app.get("/system/backups/policy", response_model=BackupPolicy)
def get_backup_policy() -> BackupPolicy:
    return backup_service.get_policy()


@app.patch("/system/backups/policy", response_model=BackupPolicy)
def update_backup_policy(payload: BackupPolicyUpdate) -> BackupPolicy:
    return backup_service.update_policy(payload)


@app.post("/system/backups/run", response_model=BackupRunResult)
def run_backup(force: bool = False) -> BackupRunResult:
    return backup_service.run(force=force)


@app.post("/system/daily-review/generate", response_model=DailyReview)
def generate_daily_review() -> DailyReview:
    return daily_review_service.build()


# ---------------------------------------------------------------- Phase 13


@app.get("/system/mcp-audit", response_model=list[MCPAuditEvent])
def list_mcp_audit(tool_name: str | None = None, limit: int = 200) -> list[MCPAuditEvent]:
    return store.list_mcp_audit(tool_name=tool_name, limit=limit)


@app.get(
    "/projects/{project_id}/mcp-audit", response_model=list[MCPAuditEvent]
)
def list_project_mcp_audit(
    project_id: str, tool_name: str | None = None, limit: int = 200
) -> list[MCPAuditEvent]:
    try:
        store.get_project(project_id)
    except KeyError:
        raise not_found("project", project_id)
    return store.list_mcp_audit(project_id=project_id, tool_name=tool_name, limit=limit)


@app.get("/system/cron", response_model=list[CronJob])
def list_cron_jobs() -> list[CronJob]:
    return store.list_cron_jobs()


@app.post("/system/cron", response_model=CronJob)
def create_cron_job(payload: CronJobCreate) -> CronJob:
    try:
        return cron_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.patch("/system/cron/{job_id}", response_model=CronJob)
def update_cron_job(job_id: str, payload: CronJobUpdate) -> CronJob:
    try:
        return cron_service.update(job_id, payload)
    except KeyError:
        raise not_found("cron_job", job_id)


@app.post("/system/cron/{job_id}/run", response_model=CronRunResult)
def run_cron_job(job_id: str) -> CronRunResult:
    try:
        return cron_service.run_job(job_id)
    except KeyError:
        raise not_found("cron_job", job_id)


@app.post(
    "/system/backups/{snapshot_id}/mirror", response_model=BackupMirrorEvent
)
def mirror_snapshot(snapshot_id: str) -> BackupMirrorEvent:
    return backup_mirror_service.mirror(snapshot_id)


@app.get(
    "/system/backups/mirror-events", response_model=list[BackupMirrorEvent]
)
def list_backup_mirror_events(limit: int = 100) -> list[BackupMirrorEvent]:
    return store.list_backup_mirror_events(limit=limit)


@app.post("/system/health/snapshot", response_model=HealthSnapshot)
def health_snapshot() -> HealthSnapshot:
    return health_history_service.snapshot()


@app.get("/system/health/history", response_model=HealthHistorySummary)
def health_history() -> HealthHistorySummary:
    return health_history_service.summary()


@app.get("/system/resource-changes", response_model=list[ResourceChangeEvent])
def list_resource_changes(since: str | None = None, limit: int = 200) -> list[ResourceChangeEvent]:
    return store.list_resource_changes(since=since, limit=limit)


# ---------------------------------------------------------------- Phase 14


# -- MCP sessions ---------------------------------------------------------

@app.get("/system/mcp-sessions", response_model=list[MCPSession])
def list_mcp_sessions() -> list[MCPSession]:
    return store.list_mcp_sessions()


@app.post("/system/mcp-sessions", response_model=MCPSession)
def create_mcp_session(payload: MCPSessionCreate) -> MCPSession:
    existing = store.get_mcp_session(payload.session_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="session_id already exists")
    session = MCPSession(**payload.model_dump())
    return store.upsert_mcp_session(session)


@app.patch("/system/mcp-sessions/{session_id}", response_model=MCPSession)
def update_mcp_session(session_id: str, payload: MCPSessionUpdate) -> MCPSession:
    try:
        return store.update_mcp_session(session_id, payload)
    except KeyError:
        raise not_found("mcp_session", session_id)


@app.post("/system/mcp-sessions/{session_id}/revoke", response_model=MCPSession)
def revoke_mcp_session(session_id: str) -> MCPSession:
    try:
        return store.update_mcp_session(session_id, MCPSessionUpdate(revoked=True))
    except KeyError:
        raise not_found("mcp_session", session_id)


# -- Audit signing verification ------------------------------------------

@app.post(
    "/system/mcp-audit/verify",
    response_model=AuditVerificationReport,
)
def verify_mcp_audit(limit: int = 500) -> AuditVerificationReport:
    events = store.list_mcp_audit(limit=limit)
    report = AuditVerificationReport(checked=len(events))
    for event in events:
        status = audit_verify(event)
        signed = bool(event.signature)
        verified = status == "valid"
        report.results.append(
            AuditVerificationResult(
                event_id=event.id, signed=signed, verified=verified, status=status
            )
        )
        if signed:
            report.signed += 1
        if status == "valid":
            report.valid += 1
        elif status == "tampered":
            report.tampered += 1
        elif status == "unsigned":
            report.unsigned += 1
        elif status == "key_missing":
            report.key_missing += 1
    return report


# -- Retention ------------------------------------------------------------

@app.get("/system/retention", response_model=list[RetentionPolicy])
def list_retention_policies() -> list[RetentionPolicy]:
    return retention_service.list_policies()


@app.patch("/system/retention/{target}", response_model=RetentionPolicy)
def update_retention_policy_route(
    target: RetentionTarget, payload: RetentionPolicyUpdate
) -> RetentionPolicy:
    try:
        return retention_service.update(target, payload)
    except KeyError:
        raise not_found("retention_policy", target.value)


@app.post("/system/retention/run", response_model=RetentionRunResult)
def run_retention() -> RetentionRunResult:
    return retention_service.run()


# -- Health alert rules ---------------------------------------------------

@app.get("/system/health/alert-rules", response_model=list[HealthAlertRule])
def list_health_alert_rules() -> list[HealthAlertRule]:
    return store.list_health_alert_rules()


@app.post("/system/health/alert-rules", response_model=HealthAlertRule)
def create_health_alert_rule(payload: HealthAlertRuleCreate) -> HealthAlertRule:
    return store.create_health_alert_rule(payload)


@app.patch(
    "/system/health/alert-rules/{rule_id}", response_model=HealthAlertRule
)
def update_health_alert_rule(
    rule_id: str, payload: HealthAlertRuleUpdate
) -> HealthAlertRule:
    try:
        return store.update_health_alert_rule(rule_id, payload)
    except KeyError:
        raise not_found("health_alert_rule", rule_id)


@app.post(
    "/system/health/alert-rules/evaluate",
    response_model=list[HealthAlertEvaluation],
)
def evaluate_health_alert_rules() -> list[HealthAlertEvaluation]:
    return health_alert_evaluator.evaluate()


# -- Phase 14 MCP audit filters -------------------------------------------
# Replaces the Phase 13 listing with optional filters. Old route name kept.

@app.get("/system/mcp-audit/filtered", response_model=list[MCPAuditEvent])
def filtered_mcp_audit(
    tool_name: str | None = None,
    session_id: str | None = None,
    blocked: bool | None = None,
    readonly: bool | None = None,
    limit: int = 500,
) -> list[MCPAuditEvent]:
    events = store.list_mcp_audit(tool_name=tool_name, limit=limit)
    if session_id is not None:
        events = [e for e in events if e.session_id == session_id]
    if blocked is not None:
        events = [e for e in events if e.blocked == blocked]
    if readonly is not None:
        events = [e for e in events if e.readonly_mode == readonly]
    return events
