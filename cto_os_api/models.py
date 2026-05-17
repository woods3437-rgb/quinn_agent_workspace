from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class AgentRole(str, Enum):
    product_strategist = "Product Strategist"
    technical_cto = "Technical CTO"
    engineering_builder = "Engineering Builder"
    ux_ui_designer = "UX/UI Designer"
    growth_strategist = "Growth Strategist"
    research_analyst = "Research Analyst"
    finance_monetization_analyst = "Finance / Monetization Analyst"


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    status: str = "active"


class Project(ProjectCreate):
    id: str = Field(default_factory=lambda: new_id("proj"))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class MemoryCreate(BaseModel):
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    pinned: bool = False
    source: str = "manual"


class Memory(MemoryCreate):
    id: str = Field(default_factory=lambda: new_id("mem"))
    project_id: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class DecisionType(str, Enum):
    product = "product"
    technical = "technical"
    design = "design"
    business = "business"
    growth = "growth"
    financial = "financial"
    operational = "operational"


class ImpactLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class DecisionCreate(BaseModel):
    title: str
    context: str = ""
    decision: str
    decision_type: DecisionType = DecisionType.technical
    rationale: str = ""
    tradeoffs: str = ""
    alternatives_considered: list[str] = Field(default_factory=list)
    impact_level: ImpactLevel = ImpactLevel.medium
    consequences: str = ""
    tags: list[str] = Field(default_factory=list)
    linked_task_ids: list[str] = Field(default_factory=list)
    linked_output_ids: list[str] = Field(default_factory=list)
    supersedes_decision_id: str | None = None


class Decision(DecisionCreate):
    id: str = Field(default_factory=lambda: new_id("dec"))
    project_id: str
    created_at: datetime = Field(default_factory=utc_now)


class Agent(BaseModel):
    id: str
    name: AgentRole
    brief: str
    system_prompt: str


class PromptTemplateCreate(BaseModel):
    project_id: str | None = None
    name: str
    description: str = ""
    category: str = "general"
    agent_type: str = ""
    template_body: str = ""
    input_variables: list[str] = Field(default_factory=list)
    template: str = ""
    agent_id: str | None = None


class PromptTemplate(PromptTemplateCreate):
    id: str = Field(default_factory=lambda: new_id("tmpl"))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class GenerateRequest(BaseModel):
    agent_id: str
    prompt: str
    template_id: str | None = None
    memory_query: str = ""
    cross_project: bool = False
    save_output: bool = True
    save_as_memory: bool = False


class GeneratedOutput(BaseModel):
    id: str = Field(default_factory=lambda: new_id("out"))
    project_id: str
    agent_id: str
    prompt: str
    output: str
    memory_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResult(BaseModel):
    memories: list[Memory]
    cross_project: bool = False


class TaskStatus(str, Enum):
    backlog = "backlog"
    todo = "todo"
    in_progress = "in_progress"
    blocked = "blocked"
    review = "review"
    done = "done"


class TaskPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class TaskCategory(str, Enum):
    product = "product"
    design = "design"
    frontend = "frontend"
    backend = "backend"
    data = "data"
    ai = "ai"
    growth = "growth"
    research = "research"
    ops = "ops"


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.backlog
    priority: TaskPriority = TaskPriority.medium
    category: TaskCategory = TaskCategory.product
    acceptance_criteria: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    linked_memory_ids: list[str] = Field(default_factory=list)
    linked_decision_ids: list[str] = Field(default_factory=list)
    linked_output_ids: list[str] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    category: TaskCategory | None = None
    acceptance_criteria: list[str] | None = None
    dependencies: list[str] | None = None
    linked_memory_ids: list[str] | None = None
    linked_decision_ids: list[str] | None = None
    linked_output_ids: list[str] | None = None


class GitHubSyncStatus(str, Enum):
    none = "none"
    previewed = "previewed"
    pending = "pending"
    completed = "completed"
    failed = "failed"
    blocked = "blocked"


class Task(TaskCreate):
    id: str = Field(default_factory=lambda: new_id("task"))
    project_id: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    github_issue_number: int | None = None
    github_issue_url: str = ""
    github_sync_status: GitHubSyncStatus = GitHubSyncStatus.none


class ArchitectureGenerateRequest(BaseModel):
    agent_id: str = "technical-cto"
    prompt: str = ""
    save_output: bool = True
    pin_to_memory: bool = False


class RoadmapGenerateRequest(BaseModel):
    agent_id: str = "product-strategist"
    prompt: str = ""
    save_output: bool = True
    pin_to_memory: bool = False


class GenerateTasksRequest(BaseModel):
    output_id: str | None = None
    limit: int = 8


class ImplementationPlanRequest(BaseModel):
    source_type: str = "task"
    source_id: str | None = None
    source_text: str = ""
    agent_id: str = "engineering-builder"
    save_output: bool = True


class BriefGenerateRequest(BaseModel):
    agent_id: str = "technical-cto"
    save_output: bool = True
    pin_to_memory: bool = False


class PromptGenerateFromTemplateRequest(BaseModel):
    template_id: str
    project_id: str | None = None
    variables: dict[str, str] = Field(default_factory=dict)
    agent_id: str = "technical-cto"
    save_output: bool = True


class ProjectBrief(BaseModel):
    project_id: str
    project_summary: str
    current_goal: str
    audience_customer: str
    product_thesis: str
    monetization_thesis: str
    current_tech_stack: str
    active_roadmap: list[str]
    key_decisions: list[str]
    open_risks: list[str]
    next_best_actions: list[str]


class ExecutionEventType(str, Enum):
    generation = "generation"
    task_update = "task_update"
    decision_created = "decision_created"
    memory_added = "memory_added"
    architecture_generated = "architecture_generated"
    roadmap_generated = "roadmap_generated"
    implementation_plan_generated = "implementation_plan_generated"
    error = "error"


class ExecutionLogCreate(BaseModel):
    task_id: str | None = None
    output_id: str | None = None
    event_type: ExecutionEventType = ExecutionEventType.generation
    title: str
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionLog(ExecutionLogCreate):
    id: str = Field(default_factory=lambda: new_id("log"))
    project_id: str
    created_at: datetime = Field(default_factory=utc_now)


class RiskCategory(str, Enum):
    technical = "technical"
    product = "product"
    market = "market"
    execution = "execution"
    financial = "financial"
    security = "security"
    operational = "operational"


class RiskSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RiskLikelihood(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class RiskStatus(str, Enum):
    open = "open"
    watching = "watching"
    mitigated = "mitigated"
    accepted = "accepted"


class RiskCreate(BaseModel):
    title: str
    category: RiskCategory = RiskCategory.execution
    severity: RiskSeverity = RiskSeverity.medium
    likelihood: RiskLikelihood = RiskLikelihood.medium
    evidence: str = ""
    recommendation: str = ""
    linked_memory_ids: list[str] = Field(default_factory=list)
    linked_decision_ids: list[str] = Field(default_factory=list)
    linked_task_ids: list[str] = Field(default_factory=list)
    status: RiskStatus = RiskStatus.open


class RiskUpdate(BaseModel):
    title: str | None = None
    category: RiskCategory | None = None
    severity: RiskSeverity | None = None
    likelihood: RiskLikelihood | None = None
    evidence: str | None = None
    recommendation: str | None = None
    linked_memory_ids: list[str] | None = None
    linked_decision_ids: list[str] | None = None
    linked_task_ids: list[str] | None = None
    status: RiskStatus | None = None


class Risk(RiskCreate):
    id: str = Field(default_factory=lambda: new_id("risk"))
    project_id: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    github_issue_number: int | None = None
    github_issue_url: str = ""
    github_sync_status: GitHubSyncStatus = GitHubSyncStatus.none


class WeeklyBrief(GeneratedOutput):
    pass


class ImplementationReviewRecommendation(str, Enum):
    pass_ = "pass"
    revise = "revise"
    rollback = "rollback"
    follow_up = "follow_up"


class ImplementationReviewCreate(BaseModel):
    task_id: str | None = None
    output_id: str | None = None
    build_packet_id: str | None = None
    attempted: bool = False
    execution_result: str = ""
    error_logs: str = ""
    implementation_notes: str
    save_lesson_to_memory: bool = False
    create_follow_up_tasks: bool = False


class ImplementationReview(BaseModel):
    id: str = Field(default_factory=lambda: new_id("review"))
    project_id: str
    task_id: str | None = None
    output_id: str | None = None
    build_packet_id: str | None = None
    attempted: bool = False
    execution_result: str = ""
    error_logs: str = ""
    implementation_notes: str
    review_result: str
    recommendation: ImplementationReviewRecommendation = ImplementationReviewRecommendation.revise
    follow_up_task_ids: list[str] = Field(default_factory=list)
    lessons_learned: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class JobType(str, Enum):
    semantic_indexing = "semantic_indexing"
    llm_generation = "llm_generation"
    weekly_brief = "weekly_brief"
    risk_scan = "risk_scan"
    repo_scan = "repo_scan"
    implementation_review = "implementation_review"
    import_export = "import_export"
    github_packet = "github_packet"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class JobCreate(BaseModel):
    type: JobType = JobType.llm_generation
    title: str
    payload_json: dict[str, Any] = Field(default_factory=dict)


class Job(JobCreate):
    id: str = Field(default_factory=lambda: new_id("job"))
    project_id: str
    status: JobStatus = JobStatus.queued
    result_json: dict[str, Any] = Field(default_factory=dict)
    error_message: str = ""
    attempts: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class WorkflowStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class WorkflowRunCreate(BaseModel):
    name: str
    payload_json: dict[str, Any] = Field(default_factory=dict)


class WorkflowRun(BaseModel):
    id: str = Field(default_factory=lambda: new_id("wf"))
    project_id: str
    name: str
    status: WorkflowStatus = WorkflowStatus.queued
    steps: list[dict[str, Any]] = Field(default_factory=list)
    current_step: int = 0
    result_summary: str = ""
    payload_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class BuildPacketGenerateRequest(BaseModel):
    task_id: str | None = None
    output_id: str | None = None
    source_text: str = ""
    title: str = ""
    save_to_memory: bool = False


class BuildPacket(BaseModel):
    id: str = Field(default_factory=lambda: new_id("packet"))
    project_id: str
    task_id: str | None = None
    title: str
    summary: str = ""
    context: str = ""
    relevant_memories: list[str] = Field(default_factory=list)
    relevant_decisions: list[str] = Field(default_factory=list)
    architecture_notes: str = ""
    implementation_steps: list[str] = Field(default_factory=list)
    files_likely_involved: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    test_plan: list[str] = Field(default_factory=list)
    rollback_plan: str = ""
    codex_prompt: str = ""
    claude_prompt: str = ""
    cursor_prompt: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class RepositoryProvider(str, Enum):
    github = "github"
    local = "local"
    manual = "manual"


class RepositoryCreate(BaseModel):
    provider: RepositoryProvider = RepositoryProvider.manual
    name: str
    url: str = ""
    default_branch: str = "main"
    local_path: str | None = None
    notes: str = ""


class RepositoryUpdate(BaseModel):
    provider: RepositoryProvider | None = None
    name: str | None = None
    url: str | None = None
    default_branch: str | None = None
    local_path: str | None = None
    notes: str | None = None


class Repository(RepositoryCreate):
    id: str = Field(default_factory=lambda: new_id("repo"))
    project_id: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SnapshotManifest(BaseModel):
    id: str
    filename: str
    path: str
    created_at: datetime
    app_version: str = "0.1.0"
    sqlite_path: str
    size_bytes: int = 0


class StructuredValidationResult(BaseModel):
    valid: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: str = ""


class RepoScan(BaseModel):
    id: str = Field(default_factory=lambda: new_id("scan"))
    project_id: str
    repository_id: str
    summary: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    package_managers: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    routes: list[str] = Field(default_factory=list)
    key_files: list[str] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)
    build_commands: list[str] = Field(default_factory=list)
    lint_commands: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class RepoFileRole(str, Enum):
    entrypoint = "entrypoint"
    route = "route"
    component = "component"
    service = "service"
    model = "model"
    config = "config"
    test = "test"
    doc = "doc"
    asset = "asset"
    unknown = "unknown"


# Phase 16.5: file classification types live in file_classifier.py so
# the classifier and the persisted model share one source of truth.
# Re-exported here for callers that already `from cto_os_api.models
# import ...`. Older RepoFile rows (pre-Phase-16) load fine because the
# new fields default on RepoFile below.
from .file_classifier import (  # noqa: E402 — re-export
    ClassificationConfidence,
    FileSemanticType,
)


class RepoFile(BaseModel):
    id: str = Field(default_factory=lambda: new_id("file"))
    project_id: str
    repository_id: str
    path: str
    file_type: str = ""
    language: str = ""
    size_bytes: int = 0
    role: RepoFileRole = RepoFileRole.unknown
    summary: str = ""
    last_modified: datetime
    hash: str
    # Phase 16.5 — semantic classification. Carries evidence so any
    # consumer that filters noise can also surface "what was filtered
    # and why" via classification_rules.
    semantic_type: FileSemanticType = FileSemanticType.unknown
    classification_confidence: ClassificationConfidence = ClassificationConfidence.low
    classification_rules: list[str] = Field(default_factory=list)


# ----------------------------------------------------------------- Phase 16.1
# Working Tree Intelligence — what changed since HEAD, grouped + risk-tagged.
# Every cluster and risk carries rules_triggered + evidence so the operator
# can verify exactly why CTO OS flagged each thing. Raw facts (full file
# list, raw `git diff --stat`, suppressed-noise list) are always reachable
# alongside the synthesized view.


class ChangedFileStatus(str, Enum):
    added = "A"
    modified = "M"
    deleted = "D"
    renamed = "R"
    copied = "C"
    untracked = "?"
    unknown = "X"


class ChangedFile(BaseModel):
    path: str
    status: ChangedFileStatus = ChangedFileStatus.unknown
    added_lines: int = 0
    deleted_lines: int = 0
    semantic_type: FileSemanticType = FileSemanticType.unknown
    classification_confidence: ClassificationConfidence = ClassificationConfidence.low
    classification_rules: list[str] = Field(default_factory=list)
    is_noise: bool = False


class DiffClusterType(str, Enum):
    directory = "directory"
    semantic = "semantic"


class DiffCluster(BaseModel):
    name: str
    cluster_type: DiffClusterType
    files: list[str]
    rules_triggered: list[str] = Field(default_factory=list)
    confidence: ClassificationConfidence = ClassificationConfidence.medium
    evidence: list[str] = Field(default_factory=list)


class RiskKind(str, Enum):
    migration_change = "migration_change"
    schema_change = "schema_change"
    env_change = "env_change"
    dependency_bump = "dependency_bump"
    lockfile_only_change = "lockfile_only_change"
    auth_path_touched = "auth_path_touched"
    large_diff = "large_diff"
    source_changed_without_test = "source_changed_without_test"
    infra_change = "infra_change"
    ci_change = "ci_change"


class RiskyChange(BaseModel):
    """A single rule-driven risk flag attached to a working-tree summary.

    ``severity`` reuses the project-wide :class:`RiskSeverity` enum
    (low / medium / high / critical) so this slots into the same risk
    vocabulary the rest of CTO OS uses. Working-tree risks currently
    never fire ``critical`` — that level is reserved for risks an
    operator has classified manually.
    """

    kind: RiskKind
    severity: RiskSeverity
    confidence: ClassificationConfidence = ClassificationConfidence.medium
    files: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    rules_triggered: list[str] = Field(default_factory=list)


class WorkingTreeSummary(BaseModel):
    repository_id: str
    repository_path: str
    current_branch: str = ""
    changed_files: list[ChangedFile] = Field(default_factory=list)
    clusters: list[DiffCluster] = Field(default_factory=list)
    risks: list[RiskyChange] = Field(default_factory=list)
    # Raw facts always available: what got filtered out, and the unvarnished
    # `git diff --stat` output. The operator can always reconstruct the
    # full picture from these.
    noise_suppressed: list[ChangedFile] = Field(default_factory=list)
    raw_diff_stat: str = ""
    summary_lines: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


# ----------------------------------------------------------------- Phase 16.4
# Real Review Routing — picks an appropriate review intensity from the
# rules already established in 16.5 (file classifier) and 16.1 (working-tree
# risk detectors). No new classifications; this layer only ROUTES.
#
# Every routing decision exposes: selected_intensity, recommended_intensity
# (what the router would have chosen pre-override), confidence,
# rules_triggered, evidence, risks_considered, routes_considered. The full
# working-tree summary that informed the decision is referenced (by id) or
# embedded, depending on the caller's preference.


class ReviewIntensity(str, Enum):
    lightweight = "lightweight"
    full = "full"
    security = "security"
    migration = "migration"
    dependency = "dependency"
    config = "config"
    docs_only = "docs_only"


class ReviewRoute(BaseModel):
    """One rule firing during routing.

    Multiple routes can fire for a single diff; the router then picks
    the highest-priority intensity per the documented priority order.
    All fired routes remain visible in ``routes_considered`` so the
    operator can audit the decision.
    """

    rule_name: str
    intensity: ReviewIntensity
    confidence: ClassificationConfidence = ClassificationConfidence.medium
    evidence: list[str] = Field(default_factory=list)


class ReviewRoutingResult(BaseModel):
    selected_intensity: ReviewIntensity
    recommended_intensity: ReviewIntensity
    confidence: ClassificationConfidence = ClassificationConfidence.medium
    rules_triggered: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    risks_considered: list[RiskKind] = Field(default_factory=list)
    routes_considered: list[ReviewRoute] = Field(default_factory=list)
    override_applied: bool = False
    # ``working_tree`` for the live WT path, ``diff_text`` when the caller
    # supplied a raw unified diff. Useful for downstream filtering /
    # debugging.
    diff_source: str = "working_tree"
    working_tree_summary: WorkingTreeSummary | None = None
    generated_at: datetime = Field(default_factory=utc_now)


class BranchPlanGenerateRequest(BaseModel):
    repository_id: str
    task_id: str | None = None
    build_packet_id: str | None = None
    objective: str = ""


class BranchPlan(BaseModel):
    id: str = Field(default_factory=lambda: new_id("branch"))
    project_id: str
    repository_id: str
    task_id: str | None = None
    build_packet_id: str | None = None
    branch_name: str
    objective: str = ""
    files_to_change: list[str] = Field(default_factory=list)
    files_to_inspect: list[str] = Field(default_factory=list)
    implementation_steps: list[str] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    rollback_plan: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    github_branch_name: str = ""
    github_branch_url: str = ""
    github_sync_status: GitHubSyncStatus = GitHubSyncStatus.none


class PRPacketGenerateRequest(BaseModel):
    repository_id: str
    branch_plan_id: str | None = None
    task_id: str | None = None
    title: str = ""


class PRPacket(BaseModel):
    id: str = Field(default_factory=lambda: new_id("prpkt"))
    project_id: str
    repository_id: str
    branch_plan_id: str | None = None
    task_id: str | None = None
    title: str
    summary: str = ""
    changes_expected: list[str] = Field(default_factory=list)
    test_plan: list[str] = Field(default_factory=list)
    acceptance_checklist: list[str] = Field(default_factory=list)
    reviewer_notes: str = ""
    risk_notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    github_pr_number: int | None = None
    github_pr_url: str = ""
    github_sync_status: GitHubSyncStatus = GitHubSyncStatus.none


class ApprovalRecommendation(str, Enum):
    approve = "approve"
    revise = "revise"
    block = "block"


class CodeReviewCreate(BaseModel):
    repository_id: str | None = None
    task_id: str | None = None
    branch_plan_id: str | None = None
    diff_text: str
    create_follow_up_tasks: bool = False


class CodeReview(BaseModel):
    id: str = Field(default_factory=lambda: new_id("reviewcode"))
    project_id: str
    repository_id: str | None = None
    task_id: str | None = None
    branch_plan_id: str | None = None
    diff_text: str
    review_summary: str = ""
    findings: list[str] = Field(default_factory=list)
    risk_level: str = "medium"
    test_recommendations: list[str] = Field(default_factory=list)
    approval_recommendation: ApprovalRecommendation = ApprovalRecommendation.revise
    follow_up_task_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    # Phase 16.4: when the review was created via review_diff_from_git the
    # routing decision (intensity, rules_triggered, evidence) is preserved
    # so future audits can see WHY this review was tagged as it was.
    # Optional + defaulted, so older persisted CodeReview rows still load.
    routing: "ReviewRoutingResult | None" = None


class TestRunStatus(str, Enum):
    not_run = "not_run"
    passed = "passed"
    failed = "failed"
    skipped = "skipped"


class TestRunCreate(BaseModel):
    repository_id: str
    task_id: str | None = None
    command: str
    status: TestRunStatus = TestRunStatus.not_run
    output: str = ""


class TestRun(TestRunCreate):
    id: str = Field(default_factory=lambda: new_id("testrun"))
    project_id: str
    created_at: datetime = Field(default_factory=utc_now)


class CodeSymbol(BaseModel):
    id: str = Field(default_factory=lambda: new_id("sym"))
    project_id: str
    repository_id: str
    file_id: str | None = None
    file_path: str
    name: str
    symbol_type: str
    signature: str = ""
    line_start: int | None = None
    line_end: int | None = None
    language: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class CodeDependency(BaseModel):
    id: str = Field(default_factory=lambda: new_id("dep"))
    project_id: str
    repository_id: str
    file_id: str | None = None
    file_path: str
    dependency: str
    dependency_type: str = "import"
    source: str = ""


class GitStatus(BaseModel):
    repository_id: str
    current_branch: str = ""
    status_summary: str = ""
    changed_files: list[str] = Field(default_factory=list)
    staged_files: list[str] = Field(default_factory=list)
    unstaged_files: list[str] = Field(default_factory=list)
    recent_commits: list[str] = Field(default_factory=list)
    diff_stats: str = ""


class GitDiffRequest(BaseModel):
    include_diff: bool = False


class GitDiff(BaseModel):
    repository_id: str
    diff_text: str = ""
    diff_stats: str = ""


class ApprovedCommandType(str, Enum):
    test = "test"
    lint = "lint"
    typecheck = "typecheck"
    build = "build"


class ApprovedCommandCreate(BaseModel):
    command: str
    command_type: ApprovedCommandType = ApprovedCommandType.test
    working_directory: str = "."


class ApprovedCommand(ApprovedCommandCreate):
    id: str = Field(default_factory=lambda: new_id("cmd"))
    project_id: str
    repository_id: str
    created_at: datetime = Field(default_factory=utc_now)
    last_run_at: datetime | None = None


class GitHubIssue(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ghi"))
    project_id: str
    repository_id: str
    number: int
    title: str
    state: str = ""
    url: str = ""
    updated_at: datetime = Field(default_factory=utc_now)
    labels: list[str] = Field(default_factory=list)
    closed_at: datetime | None = None
    linked_pr_number: int | None = None


class GitHubPullRequest(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ghpr"))
    project_id: str
    repository_id: str
    number: int
    title: str
    state: str = ""
    url: str = ""
    summary: str = ""
    updated_at: datetime = Field(default_factory=utc_now)
    draft: bool = False
    merged: bool = False
    merged_at: datetime | None = None
    closed_at: datetime | None = None
    base_branch: str = ""
    head_branch: str = ""
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0


class BuildSessionStatus(str, Enum):
    planning = "planning"
    in_progress = "in_progress"
    reviewing = "reviewing"
    completed = "completed"
    blocked = "blocked"
    abandoned = "abandoned"


class BuildSessionCreate(BaseModel):
    repository_id: str | None = None
    task_id: str | None = None
    title: str
    status: BuildSessionStatus = BuildSessionStatus.planning
    summary: str = ""
    linked_branch_plan_id: str | None = None
    linked_build_packet_id: str | None = None
    linked_pr_packet_id: str | None = None
    linked_code_review_ids: list[str] = Field(default_factory=list)
    linked_test_run_ids: list[str] = Field(default_factory=list)
    linked_implementation_review_ids: list[str] = Field(default_factory=list)
    lessons_learned: str = ""


class BuildSessionUpdate(BaseModel):
    repository_id: str | None = None
    task_id: str | None = None
    title: str | None = None
    status: BuildSessionStatus | None = None
    summary: str | None = None
    linked_branch_plan_id: str | None = None
    linked_build_packet_id: str | None = None
    linked_pr_packet_id: str | None = None
    linked_code_review_ids: list[str] | None = None
    linked_test_run_ids: list[str] | None = None
    linked_implementation_review_ids: list[str] | None = None
    lessons_learned: str | None = None


class BuildSession(BuildSessionCreate):
    id: str = Field(default_factory=lambda: new_id("session"))
    project_id: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    linked_github_write_event_ids: list[str] = Field(default_factory=list)


class GitHubWriteAction(str, Enum):
    preview_issue = "preview_issue"
    create_issue = "create_issue"
    preview_branch = "preview_branch"
    create_branch = "create_branch"
    preview_draft_pr = "preview_draft_pr"
    create_draft_pr = "create_draft_pr"


class GitHubWriteStatus(str, Enum):
    previewed = "previewed"
    completed = "completed"
    failed = "failed"
    blocked = "blocked"


class GitHubWriteEntityType(str, Enum):
    task = "task"
    risk = "risk"
    branch_plan = "branch_plan"
    pr_packet = "pr_packet"


class GitHubWriteEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ghwev"))
    project_id: str
    repository_id: str | None = None
    entity_type: GitHubWriteEntityType
    entity_id: str
    action: GitHubWriteAction
    dry_run: bool = True
    approved: bool = False
    payload_json: dict[str, Any] = Field(default_factory=dict)
    response_json: dict[str, Any] = Field(default_factory=dict)
    status: GitHubWriteStatus = GitHubWriteStatus.previewed
    error_message: str = ""
    build_session_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class GitHubIssueCreateRequest(BaseModel):
    approved: bool = False
    dry_run: bool = True
    labels: list[str] = Field(default_factory=list)
    build_session_id: str | None = None


class GitHubBranchCreateRequest(BaseModel):
    approved: bool = False
    dry_run: bool = True
    branch_name: str | None = None
    base_branch: str | None = None
    build_session_id: str | None = None


class GitHubDraftPRCreateRequest(BaseModel):
    approved: bool = False
    dry_run: bool = True
    head_branch: str | None = None
    base_branch: str | None = None
    reviewers: list[str] = Field(default_factory=list)
    build_session_id: str | None = None


# ---------------------------------------------------------------- Phase 8


class StatusSuggestionEntityType(str, Enum):
    task = "task"
    risk = "risk"
    build_session = "build_session"


class StatusSuggestion(BaseModel):
    id: str = Field(default_factory=lambda: new_id("sugg"))
    project_id: str
    entity_type: StatusSuggestionEntityType
    entity_id: str
    suggested_status: str
    reason: str = ""
    evidence_json: dict[str, Any] = Field(default_factory=dict)
    applied: bool = False
    dismissed: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class ReconciliationEntityType(str, Enum):
    task = "task"
    risk = "risk"
    build_session = "build_session"
    branch_plan = "branch_plan"
    pr_packet = "pr_packet"
    github_issue = "github_issue"
    github_pull_request = "github_pull_request"


class GitHubReconciliationEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("recon"))
    project_id: str
    repository_id: str | None = None
    entity_type: ReconciliationEntityType
    entity_id: str
    github_url: str = ""
    previous_state_json: dict[str, Any] = Field(default_factory=dict)
    new_state_json: dict[str, Any] = Field(default_factory=dict)
    recommendation: str = ""
    applied: bool = False
    suggestion_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class ReconcileRequest(BaseModel):
    repository_id: str | None = None
    auto_reconcile: bool = False


class PostShipRetrospective(BaseModel):
    id: str = Field(default_factory=lambda: new_id("retro"))
    project_id: str
    build_session_id: str | None = None
    task_id: str | None = None
    title: str = ""
    summary: str = ""
    what_changed: list[str] = Field(default_factory=list)
    what_worked: list[str] = Field(default_factory=list)
    what_broke: list[str] = Field(default_factory=list)
    test_results: str = ""
    risks_found: list[str] = Field(default_factory=list)
    follow_up_tasks: list[str] = Field(default_factory=list)
    lessons_learned: str = ""
    memory_ids_created: list[str] = Field(default_factory=list)
    decision_ids_created: list[str] = Field(default_factory=list)
    follow_up_task_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class RetrospectiveGenerateRequest(BaseModel):
    build_session_id: str | None = None
    task_id: str | None = None
    save_lessons_to_memory: bool = True
    create_follow_up_tasks: bool = True
    create_decision: bool = True
    pin_to_source_of_truth: bool = False
    update_brief_after: bool = False


class BuildSessionTimelineItemKind(str, Enum):
    task_created = "task_created"
    branch_plan_created = "branch_plan_created"
    build_packet_created = "build_packet_created"
    pr_packet_created = "pr_packet_created"
    code_review = "code_review"
    test_run = "test_run"
    implementation_review = "implementation_review"
    github_write = "github_write"
    github_reconciliation = "github_reconciliation"
    status_suggestion = "status_suggestion"
    lessons_saved = "lessons_saved"
    retrospective = "retrospective"


class BuildSessionTimelineItem(BaseModel):
    kind: BuildSessionTimelineItemKind
    entity_id: str
    title: str = ""
    detail: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class BuildSessionTimeline(BaseModel):
    build_session_id: str
    items: list[BuildSessionTimelineItem] = Field(default_factory=list)


class ShippedSummary(BaseModel):
    project_id: str
    completed_build_sessions: list[BuildSession] = Field(default_factory=list)
    merged_pull_requests: list[GitHubPullRequest] = Field(default_factory=list)
    closed_issues: list[GitHubIssue] = Field(default_factory=list)
    completed_tasks: list[Task] = Field(default_factory=list)
    shipped_outputs: list[GeneratedOutput] = Field(default_factory=list)
    lessons_learned: list[Memory] = Field(default_factory=list)
    follow_up_tasks: list[Task] = Field(default_factory=list)
    velocity_7d: int = 0
    velocity_30d: int = 0
    generated_at: datetime = Field(default_factory=utc_now)


class ReconciliationReport(BaseModel):
    project_id: str
    repository_id: str | None = None
    degraded: bool = False
    reason: str = ""
    events: list[GitHubReconciliationEvent] = Field(default_factory=list)
    suggestions: list[StatusSuggestion] = Field(default_factory=list)
    auto_applied: int = 0
    generated_at: datetime = Field(default_factory=utc_now)


# ---------------------------------------------------------------- Phase 9


class PlaybookCreate(BaseModel):
    source_project_id: str | None = None
    source_build_session_id: str | None = None
    name: str
    description: str = ""
    category: str = "engineering"
    trigger_conditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)


class Playbook(PlaybookCreate):
    id: str = Field(default_factory=lambda: new_id("play"))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PlaybookGenerateRequest(BaseModel):
    name: str | None = None
    category: str = "engineering"


class PlaybookApplyRequest(BaseModel):
    playbook_id: str


class OutcomeScoreType(str, Enum):
    retrospective_accuracy = "retrospective_accuracy"
    decision_quality = "decision_quality"
    risk_prediction = "risk_prediction"
    execution_quality = "execution_quality"


class OutcomeScoreCreate(BaseModel):
    retrospective_id: str | None = None
    decision_id: str | None = None
    risk_id: str | None = None
    score_type: OutcomeScoreType = OutcomeScoreType.execution_quality
    score: int = 3
    notes: str = ""


class OutcomeScore(OutcomeScoreCreate):
    id: str = Field(default_factory=lambda: new_id("score"))
    project_id: str
    created_at: datetime = Field(default_factory=utc_now)


class NotificationChannel(str, Enum):
    slack = "slack"
    discord = "discord"
    email = "email"
    webhook = "webhook"


class NotificationRuleCreate(BaseModel):
    project_id: str | None = None
    channel: NotificationChannel = NotificationChannel.webhook
    event_type: str
    destination: str
    enabled: bool = False
    secret_ref: str | None = None


class NotificationRuleUpdate(BaseModel):
    channel: NotificationChannel | None = None
    event_type: str | None = None
    destination: str | None = None
    enabled: bool | None = None
    secret_ref: str | None = None


class NotificationRule(NotificationRuleCreate):
    id: str = Field(default_factory=lambda: new_id("notif"))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class NotificationStatus(str, Enum):
    skipped = "skipped"
    sent = "sent"
    failed = "failed"


class NotificationEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("nevt"))
    project_id: str | None = None
    rule_id: str
    event_type: str
    payload_json: dict[str, Any] = Field(default_factory=dict)
    status: NotificationStatus = NotificationStatus.skipped
    error_message: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class NotificationTestRequest(BaseModel):
    rule_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


# ----- Aggregate response models --------------------------------------------


class StalenessSignal(BaseModel):
    project_id: str
    kind: str  # e.g. "project_inactive_14d", "blocked_task_7d"
    entity_type: str
    entity_id: str
    detail: str
    days_stale: int
    created_at: datetime = Field(default_factory=utc_now)


class StalenessReport(BaseModel):
    signals: list[StalenessSignal] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


class ControlRoomProjectStat(BaseModel):
    project_id: str
    name: str
    open_risks: int = 0
    blocked_tasks: int = 0
    pending_suggestions: int = 0
    completed_sessions_7d: int = 0
    last_activity_at: datetime | None = None


class ControlRoomSummary(BaseModel):
    active_projects: list[ControlRoomProjectStat] = Field(default_factory=list)
    open_risks_total: int = 0
    blocked_tasks_total: int = 0
    pending_suggestions_total: int = 0
    recent_github_write_events: list[GitHubWriteEvent] = Field(default_factory=list)
    recent_reconciliation_events: list[GitHubReconciliationEvent] = Field(default_factory=list)
    recent_completed_sessions: list[BuildSession] = Field(default_factory=list)
    recent_retrospectives: list[PostShipRetrospective] = Field(default_factory=list)
    jobs_needing_attention: list[Job] = Field(default_factory=list)
    stale_projects: list[ControlRoomProjectStat] = Field(default_factory=list)
    recommended_next_actions: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


class SystemShippedProject(BaseModel):
    project_id: str
    name: str
    completed_build_sessions: int = 0
    merged_pull_requests: int = 0
    closed_issues: int = 0
    completed_tasks: int = 0
    velocity_7d: int = 0
    velocity_30d: int = 0
    velocity_90d: int = 0


class SystemShippedSummary(BaseModel):
    projects: list[SystemShippedProject] = Field(default_factory=list)
    velocity_7d: int = 0
    velocity_30d: int = 0
    velocity_90d: int = 0
    completed_build_sessions: int = 0
    merged_pull_requests: int = 0
    closed_issues: int = 0
    completed_tasks: int = 0
    generated_at: datetime = Field(default_factory=utc_now)


class RiskConcentrationGroup(BaseModel):
    project_id: str
    name: str
    severity_counts: dict[str, int] = Field(default_factory=dict)
    open_critical_high: int = 0
    risks_without_mitigation: list[str] = Field(default_factory=list)
    risks_linked_to_stale_tasks: list[str] = Field(default_factory=list)


class RiskConcentrationSummary(BaseModel):
    groups: list[RiskConcentrationGroup] = Field(default_factory=list)
    recurring_themes: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


class DecisionGraphNode(BaseModel):
    id: str
    kind: str  # decision | task | memory | retrospective | build_session | risk
    title: str
    project_id: str | None = None


class DecisionGraphEdge(BaseModel):
    source: str
    target: str
    relation: str  # supersedes | linked_to_task | linked_to_memory | produced_by_retrospective | mitigates_risk | influenced_architecture


class DecisionGraph(BaseModel):
    nodes: list[DecisionGraphNode] = Field(default_factory=list)
    edges: list[DecisionGraphEdge] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


# --------------------------------------------------------------- Phase 10

class LLMContextKind(str, Enum):
    code_review = "code_review"
    retrospective = "retrospective"
    implementation_plan = "implementation_plan"
    build_packet = "build_packet"


class LLMContextBundle(BaseModel):
    """Structured prompt bundle the host model (Claude Code) will complete.

    Phase 10's whole point: CTO OS never calls Anthropic in MCP mode. We
    return rich context + schema + save-back URL, and the host model
    produces the structured output then posts it back.
    """

    kind: LLMContextKind
    project_id: str
    system_instructions: str
    user_prompt: str
    context: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    save_endpoint: str
    save_payload_keys: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


class CodeReviewContextRequest(BaseModel):
    diff_text: str
    task_id: str | None = None
    branch_plan_id: str | None = None
    repository_id: str | None = None


class CodeReviewSaveRequest(BaseModel):
    diff_text: str
    task_id: str | None = None
    branch_plan_id: str | None = None
    repository_id: str | None = None
    recommendation: str = "revise"
    summary: str = ""
    blocking_issues: list[str] = Field(default_factory=list)
    non_blocking_suggestions: list[str] = Field(default_factory=list)
    missing_tests: list[str] = Field(default_factory=list)
    security_concerns: list[str] = Field(default_factory=list)
    acceptance_criteria_check: str = ""
    confidence: float | None = None
    create_follow_up_tasks: bool = False


class RetrospectiveContextRequest(BaseModel):
    build_session_id: str | None = None
    task_id: str | None = None


class RetrospectiveSaveRequest(BaseModel):
    build_session_id: str | None = None
    task_id: str | None = None
    title: str = ""
    summary: str = ""
    what_changed: list[str] = Field(default_factory=list)
    what_worked: list[str] = Field(default_factory=list)
    what_broke: list[str] = Field(default_factory=list)
    test_results: str = ""
    risks_found: list[str] = Field(default_factory=list)
    follow_up_tasks: list[str] = Field(default_factory=list)
    lessons_learned: str = ""
    save_lessons_to_memory: bool = True
    create_follow_up_tasks: bool = True
    create_decision: bool = True
    pin_to_source_of_truth: bool = False


class ImplementationPlanContextRequest(BaseModel):
    source_type: str = "task"
    source_id: str | None = None
    source_text: str = ""


class ImplementationPlanSaveRequest(BaseModel):
    source_type: str = "task"
    source_id: str | None = None
    title: str = ""
    plan_markdown: str
    save_output: bool = True


class BuildPacketContextRequest(BaseModel):
    task_id: str | None = None
    output_id: str | None = None
    source_text: str = ""


class BuildPacketSaveRequest(BaseModel):
    task_id: str | None = None
    title: str
    summary: str = ""
    context: str = ""
    architecture_notes: str = ""
    implementation_steps: list[str] = Field(default_factory=list)
    files_likely_involved: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    test_plan: list[str] = Field(default_factory=list)
    rollback_plan: str = ""
    codex_prompt: str = ""
    claude_prompt: str = ""
    cursor_prompt: str = ""
    save_to_memory: bool = False


# ---------------------------------------------------------------- Phase 11


class IntakeSource(str, Enum):
    linear_issue_created = "linear.issue.created"
    linear_issue_updated = "linear.issue.updated"
    sentry_issue_created = "sentry.issue.created"
    github_webhook_raw = "github.webhook.raw"
    manual_note = "manual.note"


class IntakeEventCreate(BaseModel):
    source: IntakeSource
    project_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    note: str = ""


class IntakeEvent(IntakeEventCreate):
    id: str = Field(default_factory=lambda: new_id("intake"))
    suggestion_id: str | None = None
    received_at: datetime = Field(default_factory=utc_now)


class MCPSafetyReport(BaseModel):
    generated_at: datetime = Field(default_factory=utc_now)
    github_writes_in_mcp: bool = False
    shell_in_mcp: bool = False
    write_tools: list[str] = Field(default_factory=list)
    preview_tools: list[str] = Field(default_factory=list)
    read_tools: list[str] = Field(default_factory=list)
    sqlite_path: str = ""
    sqlite_journal_mode: str = ""
    provider_mode: str = ""
    memory_isolation: str = (
        "project-scoped by default; cross_project must be set explicitly."
    )
    auto_reconcile_env: bool = False
    github_writes_env: bool = False
    notifications_env: bool = False
    intake_env: bool = False


class WriterLeaseInfo(BaseModel):
    name: str
    holder: str
    acquired_at: datetime
    expires_at: datetime


# ---------------------------------------------------------------- Phase 12


class WorkerStatus(str, Enum):
    starting = "starting"
    running = "running"
    idle = "idle"
    stopped = "stopped"


class WorkerHeartbeat(BaseModel):
    id: str = Field(default_factory=lambda: new_id("hb"))
    worker_name: str
    pid: int
    status: WorkerStatus = WorkerStatus.running
    last_seen_at: datetime = Field(default_factory=utc_now)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class BackupCadence(str, Enum):
    manual = "manual"
    daily = "daily"
    weekly = "weekly"


class BackupPolicyUpdate(BaseModel):
    enabled: bool | None = None
    cadence: BackupCadence | None = None
    max_snapshots: int | None = None
    destination_path: str | None = None


class BackupPolicy(BaseModel):
    id: str = "default"
    enabled: bool = False
    cadence: BackupCadence = BackupCadence.manual
    max_snapshots: int = 10
    last_run_at: datetime | None = None
    destination_path: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class BackupRunResult(BaseModel):
    ran: bool
    reason: str = ""
    snapshot_id: str | None = None
    deleted_snapshot_ids: list[str] = Field(default_factory=list)
    policy: BackupPolicy


class SnapshotIntegrity(BaseModel):
    snapshot_id: str
    file_exists: bool = False
    manifest_readable: bool = False
    sqlite_ok: bool = False
    integrity_check: str = ""
    size_bytes: int = 0
    issues: list[str] = Field(default_factory=list)


class SnapshotRestorePreview(BaseModel):
    snapshot_id: str
    snapshot_size_bytes: int = 0
    current_db_size_bytes: int = 0
    snapshot_created_at: datetime | None = None
    current_project_count: int = 0
    notes: list[str] = Field(default_factory=list)
    safe_to_restore: bool = True


class DailyReviewSection(BaseModel):
    title: str
    items: list[str] = Field(default_factory=list)


class DailyReview(BaseModel):
    generated_at: datetime = Field(default_factory=utc_now)
    headline: str
    projects_needing_attention: list[ControlRoomProjectStat] = Field(default_factory=list)
    blocked_tasks: list[Task] = Field(default_factory=list)
    high_risks: list[Risk] = Field(default_factory=list)
    stale_build_sessions: list[BuildSession] = Field(default_factory=list)
    failed_jobs: list[Job] = Field(default_factory=list)
    pending_suggestions: list[StatusSuggestion] = Field(default_factory=list)
    recent_shipped: list[BuildSession] = Field(default_factory=list)
    recommended_next_actions: list[str] = Field(default_factory=list)
    markdown: str = ""


class HealthStatus(str, Enum):
    ok = "ok"
    degraded = "degraded"
    down = "down"


class SystemHealth(BaseModel):
    status: HealthStatus = HealthStatus.ok
    generated_at: datetime = Field(default_factory=utc_now)
    api: dict[str, Any] = Field(default_factory=dict)
    sqlite: dict[str, Any] = Field(default_factory=dict)
    mempalace: dict[str, Any] = Field(default_factory=dict)
    workers: list[WorkerHeartbeat] = Field(default_factory=list)
    mcp: dict[str, Any] = Field(default_factory=dict)
    github: dict[str, Any] = Field(default_factory=dict)
    intake: dict[str, Any] = Field(default_factory=dict)
    notifications: dict[str, Any] = Field(default_factory=dict)
    recent_failed_jobs: list[Job] = Field(default_factory=list)
    recent_failed_write_events: list[GitHubWriteEvent] = Field(default_factory=list)
    recent_blocked_suggestions: list[StatusSuggestion] = Field(default_factory=list)
    backups: dict[str, Any] = Field(default_factory=dict)


class MCPChangeNotification(BaseModel):
    uri: str
    reason: str = ""
    created_at: datetime = Field(default_factory=utc_now)


# ---------------------------------------------------------------- Phase 13


class MCPAuditAction(str, Enum):
    create = "create"
    update = "update"
    save = "save"
    pin = "pin"
    review = "review"
    test_run = "test_run"
    build_session = "build_session"
    lesson = "lesson"
    unknown = "unknown"


class MCPAuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("audit"))
    session_id: str = "unknown"
    tool_name: str
    project_id: str | None = None
    action_type: MCPAuditAction = MCPAuditAction.unknown
    request_summary: str = ""
    response_summary: str = ""
    blocked: bool = False
    readonly_mode: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    # Phase 14: HMAC-SHA256 over canonical payload of the fields above.
    signature: str = ""
    signing_key_id: str = ""


class CronJobType(str, Enum):
    daily_review = "daily_review"
    weekly_review = "weekly_review"
    backup = "backup"
    health_snapshot = "health_snapshot"
    risk_scan = "risk_scan"
    github_reconcile = "github_reconcile"
    retention_cleanup = "retention_cleanup"


class CronCadence(str, Enum):
    manual = "manual"
    hourly = "hourly"
    daily = "daily"
    weekly = "weekly"


class CronJobStatus(str, Enum):
    idle = "idle"
    running = "running"
    failed = "failed"
    completed = "completed"


class CronJobCreate(BaseModel):
    name: str
    job_type: CronJobType
    cadence: CronCadence = CronCadence.manual
    enabled: bool = False
    project_id: str | None = None
    cron_expression: str = ""
    timezone: str = ""


class CronJobUpdate(BaseModel):
    name: str | None = None
    cadence: CronCadence | None = None
    enabled: bool | None = None
    project_id: str | None = None
    cron_expression: str | None = None
    timezone: str | None = None


class CronJob(CronJobCreate):
    id: str = Field(default_factory=lambda: new_id("cron"))
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    status: CronJobStatus = CronJobStatus.idle
    last_error: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CronRunResult(BaseModel):
    job: CronJob
    ran: bool
    reason: str = ""
    output_summary: str = ""


class BackupMirrorSink(str, Enum):
    local = "local"
    rclone = "rclone"
    s3 = "s3"
    scp = "scp"


class BackupMirrorStatus(str, Enum):
    skipped = "skipped"
    completed = "completed"
    failed = "failed"


class BackupMirrorEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("mirror"))
    snapshot_id: str
    sink: BackupMirrorSink = BackupMirrorSink.local
    destination: str = ""
    status: BackupMirrorStatus = BackupMirrorStatus.skipped
    error_message: str = ""
    bytes_copied: int = 0
    created_at: datetime = Field(default_factory=utc_now)


class HealthSnapshot(BaseModel):
    id: str = Field(default_factory=lambda: new_id("hsnap"))
    status: HealthStatus = HealthStatus.ok
    summary_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class HealthHistorySummary(BaseModel):
    last_status: HealthStatus = HealthStatus.ok
    sample_count_24h: int = 0
    sample_count_7d: int = 0
    degraded_count_24h: int = 0
    degraded_count_7d: int = 0
    down_count_7d: int = 0
    latest_degraded_reasons: list[str] = Field(default_factory=list)
    recent: list[HealthSnapshot] = Field(default_factory=list)


class ResourceChangeType(str, Enum):
    created = "created"
    updated = "updated"
    deleted = "deleted"


class ResourceChangeEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("rce"))
    uri: str
    project_id: str | None = None
    change_type: ResourceChangeType = ResourceChangeType.updated
    created_at: datetime = Field(default_factory=utc_now)


# ---------------------------------------------------------------- Phase 14


class MCPSessionCreate(BaseModel):
    session_id: str
    label: str = ""
    readonly: bool = False


class MCPSessionUpdate(BaseModel):
    label: str | None = None
    readonly: bool | None = None
    revoked: bool | None = None


class MCPSession(MCPSessionCreate):
    id: str = Field(default_factory=lambda: new_id("sess"))
    revoked: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    last_seen_at: datetime = Field(default_factory=utc_now)


class RetentionTarget(str, Enum):
    health_snapshots = "health_snapshots"
    resource_changes = "resource_changes"
    execution_logs = "execution_logs"
    mcp_audit = "mcp_audit"
    github_events = "github_events"
    intake_events = "intake_events"


class RetentionPolicyUpdate(BaseModel):
    enabled: bool | None = None
    days_to_keep: int | None = None
    hard_delete_allowed: bool | None = None


class RetentionPolicy(BaseModel):
    id: str
    target: RetentionTarget
    enabled: bool = False
    days_to_keep: int = 30
    hard_delete_allowed: bool = False
    last_run_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RetentionRunOutcome(BaseModel):
    target: RetentionTarget
    deleted: int = 0
    skipped: bool = False
    reason: str = ""


class RetentionRunResult(BaseModel):
    outcomes: list[RetentionRunOutcome] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


class HealthAlertConditionType(str, Enum):
    degraded_samples = "degraded_samples"
    failed_jobs = "failed_jobs"
    backup_overdue = "backup_overdue"
    worker_stale = "worker_stale"


class HealthAlertRuleCreate(BaseModel):
    name: str
    enabled: bool = False
    condition_type: HealthAlertConditionType = HealthAlertConditionType.degraded_samples
    threshold: int = 1
    window_minutes: int = 60
    notification_rule_id: str | None = None


class HealthAlertRuleUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    condition_type: HealthAlertConditionType | None = None
    threshold: int | None = None
    window_minutes: int | None = None
    notification_rule_id: str | None = None


class HealthAlertRule(HealthAlertRuleCreate):
    id: str = Field(default_factory=lambda: new_id("alert"))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class HealthAlertEvaluation(BaseModel):
    rule_id: str
    triggered: bool
    reason: str = ""
    notification_event_ids: list[str] = Field(default_factory=list)


class AuditVerificationResult(BaseModel):
    event_id: str
    signed: bool = False
    verified: bool = False
    status: str = "unsigned"  # unsigned | valid | tampered | key_missing


class AuditVerificationReport(BaseModel):
    checked: int = 0
    signed: int = 0
    valid: int = 0
    tampered: int = 0
    unsigned: int = 0
    key_missing: int = 0
    results: list[AuditVerificationResult] = Field(default_factory=list)


# Phase 16.4: resolve the forward reference on CodeReview now that
# ReviewRoutingResult is defined further down. Avoids implicit
# resolution at first-use time (which can race with reloads).
CodeReview.model_rebuild()

