export const API_BASE = process.env.NEXT_PUBLIC_CTO_OS_API ?? "http://localhost:8787";
const ADMIN_TOKEN = process.env.NEXT_PUBLIC_CTO_OS_ADMIN_TOKEN ?? "";

export type Project = {
  id: string;
  name: string;
  description: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type Memory = {
  id: string;
  project_id: string;
  title: string;
  content: string;
  tags: string[];
  pinned: boolean;
  source: string;
  created_at: string;
  updated_at: string;
};

export type Decision = {
  id: string;
  project_id: string;
  title: string;
  context: string;
  decision: string;
  decision_type: string;
  rationale: string;
  tradeoffs: string;
  alternatives_considered: string[];
  impact_level: string;
  consequences: string;
  tags: string[];
  linked_task_ids: string[];
  linked_output_ids: string[];
  supersedes_decision_id?: string | null;
  created_at: string;
};

export type Agent = {
  id: string;
  name: string;
  brief: string;
  system_prompt: string;
};

export type GeneratedOutput = {
  id: string;
  project_id: string;
  agent_id: string;
  prompt: string;
  output: string;
  memory_ids: string[];
  created_at: string;
  metadata: Record<string, unknown>;
};

export type Task = {
  id: string;
  project_id: string;
  title: string;
  description: string;
  status: "backlog" | "todo" | "in_progress" | "blocked" | "review" | "done";
  priority: "low" | "medium" | "high" | "urgent";
  category: "product" | "design" | "frontend" | "backend" | "data" | "ai" | "growth" | "research" | "ops";
  acceptance_criteria: string[];
  dependencies: string[];
  linked_memory_ids: string[];
  linked_decision_ids: string[];
  linked_output_ids: string[];
  created_at: string;
  updated_at: string;
  github_issue_number?: number | null;
  github_issue_url?: string;
  github_sync_status?: GitHubSyncStatus;
};

export type PromptTemplate = {
  id: string;
  project_id?: string | null;
  name: string;
  description: string;
  category: string;
  agent_type: string;
  template_body: string;
  input_variables: string[];
  template: string;
  agent_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectBrief = {
  project_id: string;
  project_summary: string;
  current_goal: string;
  audience_customer: string;
  product_thesis: string;
  monetization_thesis: string;
  current_tech_stack: string;
  active_roadmap: string[];
  key_decisions: string[];
  open_risks: string[];
  next_best_actions: string[];
};

export type ExecutionLog = {
  id: string;
  project_id: string;
  task_id?: string | null;
  output_id?: string | null;
  event_type: string;
  title: string;
  summary: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type Risk = {
  id: string;
  project_id: string;
  title: string;
  category: "technical" | "product" | "market" | "execution" | "financial" | "security" | "operational";
  severity: "low" | "medium" | "high" | "critical";
  likelihood: "low" | "medium" | "high";
  evidence: string;
  recommendation: string;
  linked_memory_ids: string[];
  linked_decision_ids: string[];
  linked_task_ids: string[];
  status: "open" | "watching" | "mitigated" | "accepted";
  created_at: string;
  updated_at: string;
  github_issue_number?: number | null;
  github_issue_url?: string;
  github_sync_status?: GitHubSyncStatus;
};

export type ImplementationReview = {
  id: string;
  project_id: string;
  task_id?: string | null;
  output_id?: string | null;
  build_packet_id?: string | null;
  attempted: boolean;
  execution_result: string;
  error_logs: string;
  implementation_notes: string;
  review_result: string;
  recommendation: "pass" | "revise" | "rollback" | "follow_up";
  follow_up_task_ids: string[];
  lessons_learned: string;
  created_at: string;
};

export type Job = {
  id: string;
  project_id: string;
  type: "semantic_indexing" | "llm_generation" | "weekly_brief" | "risk_scan" | "repo_scan" | "implementation_review" | "import_export" | "github_packet";
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  title: string;
  payload_json: Record<string, unknown>;
  result_json: Record<string, unknown>;
  error_message: string;
  attempts: number;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  completed_at?: string | null;
};

export type WorkflowRun = {
  id: string;
  project_id: string;
  name: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  steps: Array<Record<string, unknown>>;
  current_step: number;
  result_summary: string;
  payload_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
};

export type BuildPacket = {
  id: string;
  project_id: string;
  task_id?: string | null;
  title: string;
  summary: string;
  context: string;
  relevant_memories: string[];
  relevant_decisions: string[];
  architecture_notes: string;
  implementation_steps: string[];
  files_likely_involved: string[];
  acceptance_criteria: string[];
  test_plan: string[];
  rollback_plan: string;
  codex_prompt: string;
  claude_prompt: string;
  cursor_prompt: string;
  created_at: string;
};

export type Repository = {
  id: string;
  project_id: string;
  provider: "github" | "local" | "manual";
  name: string;
  url: string;
  default_branch: string;
  local_path?: string | null;
  notes: string;
  created_at: string;
  updated_at: string;
};

export type SnapshotManifest = {
  id: string;
  filename: string;
  path: string;
  created_at: string;
  app_version: string;
  sqlite_path: string;
  size_bytes: number;
};

export type RepoScan = {
  id: string;
  project_id: string;
  repository_id: string;
  summary: string;
  tech_stack: string[];
  package_managers: string[];
  frameworks: string[];
  routes: string[];
  key_files: string[];
  test_commands: string[];
  build_commands: string[];
  lint_commands: string[];
  risks: string[];
  created_at: string;
};

export type RepoFile = {
  id: string;
  project_id: string;
  repository_id: string;
  path: string;
  file_type: string;
  language: string;
  size_bytes: number;
  role: "entrypoint" | "route" | "component" | "service" | "model" | "config" | "test" | "doc" | "asset" | "unknown";
  summary: string;
  last_modified: string;
  hash: string;
};

export type BranchPlan = {
  id: string;
  project_id: string;
  repository_id: string;
  task_id?: string | null;
  build_packet_id?: string | null;
  branch_name: string;
  objective: string;
  files_to_change: string[];
  files_to_inspect: string[];
  implementation_steps: string[];
  test_commands: string[];
  risk_notes: string[];
  rollback_plan: string;
  created_at: string;
  github_branch_name?: string;
  github_branch_url?: string;
  github_sync_status?: GitHubSyncStatus;
};

export type PRPacket = {
  id: string;
  project_id: string;
  repository_id: string;
  branch_plan_id?: string | null;
  task_id?: string | null;
  title: string;
  summary: string;
  changes_expected: string[];
  test_plan: string[];
  acceptance_checklist: string[];
  reviewer_notes: string;
  risk_notes: string[];
  created_at: string;
  github_pr_number?: number | null;
  github_pr_url?: string;
  github_sync_status?: GitHubSyncStatus;
};

export type CodeReview = {
  id: string;
  project_id: string;
  repository_id?: string | null;
  task_id?: string | null;
  branch_plan_id?: string | null;
  diff_text: string;
  review_summary: string;
  findings: string[];
  risk_level: string;
  test_recommendations: string[];
  approval_recommendation: "approve" | "revise" | "block";
  follow_up_task_ids: string[];
  created_at: string;
};

export type TestRun = {
  id: string;
  project_id: string;
  repository_id: string;
  task_id?: string | null;
  command: string;
  status: "not_run" | "passed" | "failed" | "skipped";
  output: string;
  created_at: string;
};

export type CodeSymbol = {
  id: string;
  project_id: string;
  repository_id: string;
  file_id?: string | null;
  file_path: string;
  name: string;
  symbol_type: string;
  signature: string;
  line_start?: number | null;
  line_end?: number | null;
  language: string;
  metadata: Record<string, unknown>;
};

export type CodeDependency = {
  id: string;
  project_id: string;
  repository_id: string;
  file_path: string;
  dependency: string;
  dependency_type: string;
  source: string;
};

export type GitStatus = {
  repository_id: string;
  current_branch: string;
  status_summary: string;
  changed_files: string[];
  staged_files: string[];
  unstaged_files: string[];
  recent_commits: string[];
  diff_stats: string;
};

export type ApprovedCommand = {
  id: string;
  project_id: string;
  repository_id: string;
  command: string;
  command_type: "test" | "lint" | "typecheck" | "build";
  working_directory: string;
  created_at: string;
  last_run_at?: string | null;
};

export type BuildSession = {
  id: string;
  project_id: string;
  repository_id?: string | null;
  task_id?: string | null;
  title: string;
  status: "planning" | "in_progress" | "reviewing" | "completed" | "blocked" | "abandoned";
  summary: string;
  linked_branch_plan_id?: string | null;
  linked_build_packet_id?: string | null;
  linked_pr_packet_id?: string | null;
  linked_code_review_ids: string[];
  linked_test_run_ids: string[];
  linked_implementation_review_ids: string[];
  linked_github_write_event_ids: string[];
  lessons_learned: string;
  created_at: string;
  updated_at: string;
};

export type GitHubSyncStatus =
  | "none"
  | "previewed"
  | "pending"
  | "completed"
  | "failed"
  | "blocked";

export type GitHubWriteAction =
  | "preview_issue"
  | "create_issue"
  | "preview_branch"
  | "create_branch"
  | "preview_draft_pr"
  | "create_draft_pr";

export type GitHubWriteStatus = "previewed" | "completed" | "failed" | "blocked";

export type GitHubWriteEntityType = "task" | "risk" | "branch_plan" | "pr_packet";

export type GitHubWriteEvent = {
  id: string;
  project_id: string;
  repository_id?: string | null;
  entity_type: GitHubWriteEntityType;
  entity_id: string;
  action: GitHubWriteAction;
  dry_run: boolean;
  approved: boolean;
  payload_json: Record<string, unknown>;
  response_json: Record<string, unknown>;
  status: GitHubWriteStatus;
  error_message: string;
  build_session_id?: string | null;
  created_at: string;
};

export type GitHubIssueCreateRequest = {
  approved: boolean;
  dry_run: boolean;
  labels?: string[];
  build_session_id?: string | null;
};

export type GitHubBranchCreateRequest = {
  approved: boolean;
  dry_run: boolean;
  branch_name?: string | null;
  base_branch?: string | null;
  build_session_id?: string | null;
};

export type GitHubDraftPRCreateRequest = {
  approved: boolean;
  dry_run: boolean;
  head_branch?: string | null;
  base_branch?: string | null;
  reviewers?: string[];
  build_session_id?: string | null;
};

export type StatusSuggestion = {
  id: string;
  project_id: string;
  entity_type: "task" | "risk" | "build_session";
  entity_id: string;
  suggested_status: string;
  reason: string;
  evidence_json: Record<string, unknown>;
  applied: boolean;
  dismissed: boolean;
  created_at: string;
};

export type GitHubReconciliationEvent = {
  id: string;
  project_id: string;
  repository_id?: string | null;
  entity_type: string;
  entity_id: string;
  github_url: string;
  previous_state_json: Record<string, unknown>;
  new_state_json: Record<string, unknown>;
  recommendation: string;
  applied: boolean;
  suggestion_id?: string | null;
  created_at: string;
};

export type ReconciliationReport = {
  project_id: string;
  repository_id?: string | null;
  degraded: boolean;
  reason: string;
  events: GitHubReconciliationEvent[];
  suggestions: StatusSuggestion[];
  auto_applied: number;
  generated_at: string;
};

export type PostShipRetrospective = {
  id: string;
  project_id: string;
  build_session_id?: string | null;
  task_id?: string | null;
  title: string;
  summary: string;
  what_changed: string[];
  what_worked: string[];
  what_broke: string[];
  test_results: string;
  risks_found: string[];
  follow_up_tasks: string[];
  lessons_learned: string;
  memory_ids_created: string[];
  decision_ids_created: string[];
  follow_up_task_ids: string[];
  created_at: string;
};

export type RetrospectiveGenerateRequest = {
  build_session_id?: string | null;
  task_id?: string | null;
  save_lessons_to_memory?: boolean;
  create_follow_up_tasks?: boolean;
  create_decision?: boolean;
  pin_to_source_of_truth?: boolean;
  update_brief_after?: boolean;
};

export type ShippedSummary = {
  project_id: string;
  completed_build_sessions: BuildSession[];
  merged_pull_requests: Array<Record<string, unknown>>;
  closed_issues: Array<Record<string, unknown>>;
  completed_tasks: Task[];
  shipped_outputs: GeneratedOutput[];
  lessons_learned: Memory[];
  follow_up_tasks: Task[];
  velocity_7d: number;
  velocity_30d: number;
  generated_at: string;
};

export type BuildSessionTimelineItem = {
  kind: string;
  entity_id: string;
  title: string;
  detail: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type BuildSessionTimeline = {
  build_session_id: string;
  items: BuildSessionTimelineItem[];
};

// ------- Phase 9 -----------------------------------------------------------

export type Playbook = {
  id: string;
  source_project_id?: string | null;
  source_build_session_id?: string | null;
  name: string;
  description: string;
  category: string;
  trigger_conditions: string[];
  steps: string[];
  required_inputs: string[];
  expected_outputs: string[];
  risks: string[];
  acceptance_criteria: string[];
  created_at: string;
  updated_at: string;
};

export type OutcomeScoreType =
  | "retrospective_accuracy"
  | "decision_quality"
  | "risk_prediction"
  | "execution_quality";

export type OutcomeScore = {
  id: string;
  project_id: string;
  retrospective_id?: string | null;
  decision_id?: string | null;
  risk_id?: string | null;
  score_type: OutcomeScoreType;
  score: number;
  notes: string;
  created_at: string;
};

export type NotificationChannel = "slack" | "discord" | "email" | "webhook";

export type NotificationRule = {
  id: string;
  project_id?: string | null;
  channel: NotificationChannel;
  event_type: string;
  destination: string;
  enabled: boolean;
  secret_ref?: string | null;
  created_at: string;
  updated_at: string;
};

export type NotificationEvent = {
  id: string;
  project_id?: string | null;
  rule_id: string;
  event_type: string;
  payload_json: Record<string, unknown>;
  status: "skipped" | "sent" | "failed";
  error_message: string;
  created_at: string;
};

export type StalenessSignal = {
  project_id: string;
  kind: string;
  entity_type: string;
  entity_id: string;
  detail: string;
  days_stale: number;
  created_at: string;
};

export type StalenessReport = {
  signals: StalenessSignal[];
  generated_at: string;
};

export type ControlRoomProjectStat = {
  project_id: string;
  name: string;
  open_risks: number;
  blocked_tasks: number;
  pending_suggestions: number;
  completed_sessions_7d: number;
  last_activity_at?: string | null;
};

export type ControlRoomSummary = {
  active_projects: ControlRoomProjectStat[];
  open_risks_total: number;
  blocked_tasks_total: number;
  pending_suggestions_total: number;
  recent_github_write_events: GitHubWriteEvent[];
  recent_reconciliation_events: GitHubReconciliationEvent[];
  recent_completed_sessions: BuildSession[];
  recent_retrospectives: PostShipRetrospective[];
  jobs_needing_attention: Job[];
  stale_projects: ControlRoomProjectStat[];
  recommended_next_actions: string[];
  generated_at: string;
};

export type SystemShippedProject = {
  project_id: string;
  name: string;
  completed_build_sessions: number;
  merged_pull_requests: number;
  closed_issues: number;
  completed_tasks: number;
  velocity_7d: number;
  velocity_30d: number;
  velocity_90d: number;
};

export type SystemShippedSummary = {
  projects: SystemShippedProject[];
  velocity_7d: number;
  velocity_30d: number;
  velocity_90d: number;
  completed_build_sessions: number;
  merged_pull_requests: number;
  closed_issues: number;
  completed_tasks: number;
  generated_at: string;
};

export type RiskConcentrationGroup = {
  project_id: string;
  name: string;
  severity_counts: Record<string, number>;
  open_critical_high: number;
  risks_without_mitigation: string[];
  risks_linked_to_stale_tasks: string[];
};

export type RiskConcentrationSummary = {
  groups: RiskConcentrationGroup[];
  recurring_themes: string[];
  generated_at: string;
};

export type DecisionGraphNode = {
  id: string;
  kind: string;
  title: string;
  project_id?: string | null;
};

export type DecisionGraphEdge = {
  source: string;
  target: string;
  relation: string;
};

export type DecisionGraph = {
  nodes: DecisionGraphNode[];
  edges: DecisionGraphEdge[];
  generated_at: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(ADMIN_TOKEN ? { Authorization: `Bearer ${ADMIN_TOKEN}`, "X-CTO-OS-Token": ADMIN_TOKEN } : {}),
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export const api = {
  projects: () => request<Project[]>("/projects"),
  project: (id: string) => request<Project>(`/projects/${id}`),
  createProject: (body: { name: string; description: string }) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify(body) }),
  memories: (projectId: string) => request<Memory[]>(`/projects/${projectId}/memories`),
  createMemory: (projectId: string, body: { title: string; content: string; tags: string[]; pinned: boolean }) =>
    request<Memory>(`/projects/${projectId}/memories`, { method: "POST", body: JSON.stringify(body) }),
  pinMemory: (projectId: string, memoryId: string, pinned: boolean) =>
    request<Memory>(`/projects/${projectId}/memories/${memoryId}/pin?pinned=${pinned}`, { method: "PATCH" }),
  decisions: (projectId: string) => request<Decision[]>(`/projects/${projectId}/decisions`),
  createDecision: (projectId: string, body: Omit<Decision, "id" | "project_id" | "created_at">) =>
    request<Decision>(`/projects/${projectId}/decisions`, { method: "POST", body: JSON.stringify(body) }),
  agents: () => request<Agent[]>("/agents"),
  outputs: (projectId: string) => request<GeneratedOutput[]>(`/projects/${projectId}/outputs`),
  generate: (
    projectId: string,
    body: { agent_id: string; prompt: string; memory_query?: string; cross_project: boolean; save_output: boolean; save_as_memory: boolean }
  ) => request<GeneratedOutput>(`/projects/${projectId}/outputs/generate`, { method: "POST", body: JSON.stringify(body) }),
  generateArchitecture: (projectId: string, body: { agent_id?: string; prompt?: string; save_output: boolean; pin_to_memory: boolean }) =>
    request<GeneratedOutput>(`/projects/${projectId}/architecture/generate`, { method: "POST", body: JSON.stringify(body) }),
  generateRoadmap: (projectId: string, body: { agent_id?: string; prompt?: string; save_output: boolean; pin_to_memory: boolean }) =>
    request<GeneratedOutput>(`/projects/${projectId}/roadmap/generate`, { method: "POST", body: JSON.stringify(body) }),
  tasks: (projectId: string) => request<Task[]>(`/projects/${projectId}/tasks`),
  createTask: (projectId: string, body: Omit<Task, "id" | "project_id" | "created_at" | "updated_at">) =>
    request<Task>(`/projects/${projectId}/tasks`, { method: "POST", body: JSON.stringify(body) }),
  updateTask: (projectId: string, taskId: string, body: Partial<Task>) =>
    request<Task>(`/projects/${projectId}/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteTask: (projectId: string, taskId: string) =>
    request<{ status: string }>(`/projects/${projectId}/tasks/${taskId}`, { method: "DELETE" }),
  generateTasksFromRoadmap: (projectId: string, body: { output_id?: string | null; limit: number }) =>
    request<Task[]>(`/projects/${projectId}/tasks/generate-from-roadmap`, { method: "POST", body: JSON.stringify(body) }),
  generateTasksFromOutput: (projectId: string, outputId: string, body: { limit: number }) =>
    request<Task[]>(`/projects/${projectId}/tasks/generate-from-output/${outputId}`, { method: "POST", body: JSON.stringify(body) }),
  generateImplementationPlan: (projectId: string, body: { source_type: string; source_id?: string; source_text?: string; agent_id?: string; save_output: boolean }) =>
    request<GeneratedOutput>(`/projects/${projectId}/implementation-plan/generate`, { method: "POST", body: JSON.stringify(body) }),
  promptTemplates: (projectId?: string) =>
    request<PromptTemplate[]>(`/prompt-templates${projectId ? `?project_id=${projectId}&include_global=true` : ""}`),
  createPromptTemplate: (body: Partial<PromptTemplate>) =>
    request<PromptTemplate>("/prompt-templates", { method: "POST", body: JSON.stringify(body) }),
  duplicatePromptTemplate: (templateId: string, projectId?: string) =>
    request<PromptTemplate>(`/prompt-templates/${templateId}/duplicate${projectId ? `?project_id=${projectId}` : ""}`, { method: "POST" }),
  generatePromptFromTemplate: (projectId: string, body: { template_id: string; variables: Record<string, string>; agent_id?: string; save_output: boolean }) =>
    request<GeneratedOutput>(`/projects/${projectId}/prompts/generate`, { method: "POST", body: JSON.stringify(body) }),
  brief: (projectId: string) => request<ProjectBrief>(`/projects/${projectId}/brief`),
  generateBrief: (projectId: string, body: { agent_id?: string; save_output: boolean; pin_to_memory: boolean }) =>
    request<GeneratedOutput>(`/projects/${projectId}/brief/generate`, { method: "POST", body: JSON.stringify(body) }),
  logs: (projectId: string) => request<ExecutionLog[]>(`/projects/${projectId}/logs`),
  createLog: (projectId: string, body: { event_type: string; title: string; summary?: string; metadata?: Record<string, unknown> }) =>
    request<ExecutionLog>(`/projects/${projectId}/logs`, { method: "POST", body: JSON.stringify(body) }),
  risks: (projectId: string) => request<Risk[]>(`/projects/${projectId}/risks`),
  generateRisks: (projectId: string) => request<Risk[]>(`/projects/${projectId}/risks/generate`, { method: "POST" }),
  updateRisk: (projectId: string, riskId: string, body: Partial<Risk>) =>
    request<Risk>(`/projects/${projectId}/risks/${riskId}`, { method: "PATCH", body: JSON.stringify(body) }),
  briefs: (projectId: string) => request<GeneratedOutput[]>(`/projects/${projectId}/briefs`),
  generateWeeklyBrief: (projectId: string) =>
    request<GeneratedOutput>(`/projects/${projectId}/briefs/weekly/generate`, { method: "POST" }),
  implementationReviews: (projectId: string) => request<ImplementationReview[]>(`/projects/${projectId}/implementation-reviews`),
  createImplementationReview: (projectId: string, body: { task_id?: string; output_id?: string; build_packet_id?: string; attempted?: boolean; execution_result?: string; error_logs?: string; implementation_notes: string; save_lesson_to_memory?: boolean; create_follow_up_tasks?: boolean }) =>
    request<ImplementationReview>(`/projects/${projectId}/implementation-reviews`, { method: "POST", body: JSON.stringify(body) }),
  jobs: (projectId: string, filters?: { status?: string; type?: string }) =>
    request<Job[]>(`/projects/${projectId}/jobs${filters ? `?${new URLSearchParams(Object.entries(filters).filter(([, value]) => value) as [string, string][]).toString()}` : ""}`),
  createJob: (projectId: string, body: { type: Job["type"]; title: string; payload_json?: Record<string, unknown> }) =>
    request<Job>(`/projects/${projectId}/jobs`, { method: "POST", body: JSON.stringify(body) }),
  runJob: (projectId: string, jobId: string) => request<Job>(`/projects/${projectId}/jobs/${jobId}/run`, { method: "POST" }),
  cancelJob: (projectId: string, jobId: string) => request<Job>(`/projects/${projectId}/jobs/${jobId}/cancel`, { method: "POST" }),
  workflows: (projectId: string) => request<WorkflowRun[]>(`/projects/${projectId}/workflows`),
  defaultWorkflows: () => request<Record<string, Array<Record<string, unknown>>>>("/workflows/defaults"),
  runWorkflow: (projectId: string, body: { name: string; payload_json?: Record<string, unknown> }) =>
    request<WorkflowRun>(`/projects/${projectId}/workflows/run`, { method: "POST", body: JSON.stringify(body) }),
  buildPackets: (projectId: string) => request<BuildPacket[]>(`/projects/${projectId}/build-packets`),
  buildPacket: (projectId: string, packetId: string) => request<BuildPacket>(`/projects/${projectId}/build-packets/${packetId}`),
  generateBuildPacket: (projectId: string, body: { task_id?: string; output_id?: string; source_text?: string; title?: string; save_to_memory?: boolean }) =>
    request<BuildPacket>(`/projects/${projectId}/build-packets/generate`, { method: "POST", body: JSON.stringify(body) }),
  repositories: (projectId: string) => request<Repository[]>(`/projects/${projectId}/repositories`),
  createRepository: (projectId: string, body: Omit<Repository, "id" | "project_id" | "created_at" | "updated_at">) =>
    request<Repository>(`/projects/${projectId}/repositories`, { method: "POST", body: JSON.stringify(body) }),
  updateRepository: (projectId: string, repositoryId: string, body: Partial<Repository>) =>
    request<Repository>(`/projects/${projectId}/repositories/${repositoryId}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteRepository: (projectId: string, repositoryId: string) =>
    request<{ status: string }>(`/projects/${projectId}/repositories/${repositoryId}`, { method: "DELETE" }),
  scanRepository: (projectId: string, repositoryId: string) =>
    request<RepoScan>(`/projects/${projectId}/repositories/${repositoryId}/scan`, { method: "POST" }),
  repoScans: (projectId: string, repositoryId: string) =>
    request<RepoScan[]>(`/projects/${projectId}/repositories/${repositoryId}/scans`),
  repoFiles: (projectId: string, repositoryId: string) =>
    request<RepoFile[]>(`/projects/${projectId}/repositories/${repositoryId}/files`),
  searchRepoFiles: (projectId: string, repositoryId: string, q: string) =>
    request<RepoFile[]>(`/projects/${projectId}/repositories/${repositoryId}/files/search?q=${encodeURIComponent(q)}`),
  codeSymbols: (projectId: string, repositoryId: string) =>
    request<CodeSymbol[]>(`/projects/${projectId}/repositories/${repositoryId}/symbols`),
  searchCodeSymbols: (projectId: string, repositoryId: string, q: string) =>
    request<CodeSymbol[]>(`/projects/${projectId}/repositories/${repositoryId}/symbols/search?q=${encodeURIComponent(q)}`),
  codeDependencies: (projectId: string, repositoryId: string) =>
    request<CodeDependency[]>(`/projects/${projectId}/repositories/${repositoryId}/dependencies`),
  gitStatus: (projectId: string, repositoryId: string) =>
    request<GitStatus>(`/projects/${projectId}/repositories/${repositoryId}/git/status`),
  gitDiff: (projectId: string, repositoryId: string, include_diff: boolean) =>
    request<{ repository_id: string; diff_text: string; diff_stats: string }>(`/projects/${projectId}/repositories/${repositoryId}/git/diff`, { method: "POST", body: JSON.stringify({ include_diff }) }),
  commands: (projectId: string, repositoryId: string) =>
    request<ApprovedCommand[]>(`/projects/${projectId}/repositories/${repositoryId}/commands`),
  approveCommand: (projectId: string, repositoryId: string, body: { command: string; command_type: ApprovedCommand["command_type"]; working_directory?: string }) =>
    request<ApprovedCommand>(`/projects/${projectId}/repositories/${repositoryId}/commands`, { method: "POST", body: JSON.stringify(body) }),
  runCommand: (projectId: string, repositoryId: string, commandId: string) =>
    request<TestRun>(`/projects/${projectId}/repositories/${repositoryId}/commands/${commandId}/run`, { method: "POST" }),
  indexRepoToMemory: (projectId: string, repositoryId: string) =>
    request<Memory[]>(`/projects/${projectId}/repositories/${repositoryId}/index-to-memory`, { method: "POST" }),
  branchPlans: (projectId: string) => request<BranchPlan[]>(`/projects/${projectId}/branch-plans`),
  generateBranchPlan: (projectId: string, body: { repository_id: string; task_id?: string; build_packet_id?: string; objective?: string }) =>
    request<BranchPlan>(`/projects/${projectId}/branch-plans/generate`, { method: "POST", body: JSON.stringify(body) }),
  prPackets: (projectId: string) => request<PRPacket[]>(`/projects/${projectId}/pr-packets`),
  generatePRPacket: (projectId: string, body: { repository_id: string; branch_plan_id?: string; task_id?: string; title?: string }) =>
    request<PRPacket>(`/projects/${projectId}/pr-packets/generate`, { method: "POST", body: JSON.stringify(body) }),
  codeReviews: (projectId: string) => request<CodeReview[]>(`/projects/${projectId}/code-reviews`),
  createCodeReview: (projectId: string, body: { repository_id?: string; task_id?: string; branch_plan_id?: string; diff_text: string; create_follow_up_tasks?: boolean }) =>
    request<CodeReview>(`/projects/${projectId}/code-reviews`, { method: "POST", body: JSON.stringify(body) }),
  testRuns: (projectId: string) => request<TestRun[]>(`/projects/${projectId}/test-runs`),
  createTestRun: (projectId: string, body: { repository_id: string; task_id?: string; command: string; status: TestRun["status"]; output?: string }) =>
    request<TestRun>(`/projects/${projectId}/test-runs`, { method: "POST", body: JSON.stringify(body) }),
  githubStatus: () => request<Record<string, unknown>>("/system/integrations/github/status"),
  githubRepositories: () => request<Array<Record<string, unknown>>>("/system/integrations/github/repositories"),
  githubSync: (projectId: string, repositoryId: string) =>
    request<{ issues: number; pull_requests: number }>(`/projects/${projectId}/repositories/${repositoryId}/github/sync`, { method: "POST" }),
  buildSessions: (projectId: string) => request<BuildSession[]>(`/projects/${projectId}/build-sessions`),
  createBuildSession: (projectId: string, body: Partial<BuildSession> & { title: string }) =>
    request<BuildSession>(`/projects/${projectId}/build-sessions`, { method: "POST", body: JSON.stringify(body) }),
  updateBuildSession: (projectId: string, sessionId: string, body: Partial<BuildSession>) =>
    request<BuildSession>(`/projects/${projectId}/build-sessions/${sessionId}`, { method: "PATCH", body: JSON.stringify(body) }),
  summarizeBuildSession: (projectId: string, sessionId: string) =>
    request<BuildSession>(`/projects/${projectId}/build-sessions/${sessionId}/summarize`, { method: "POST" }),
  saveBuildSessionLessons: (projectId: string, sessionId: string) =>
    request<Memory[]>(`/projects/${projectId}/build-sessions/${sessionId}/save-lessons`, { method: "POST" }),
  snapshots: () => request<SnapshotManifest[]>("/system/snapshots"),
  createSnapshot: () => request<SnapshotManifest>("/system/snapshots/create", { method: "POST" }),
  restoreSnapshot: (snapshotId: string) => request<SnapshotManifest>(`/system/snapshots/${snapshotId}/restore`, { method: "POST" }),
  exportProject: (projectId: string) => request<Record<string, unknown>>(`/projects/${projectId}/export`),
  importProject: (bundle: Record<string, unknown>) => request<Project>("/projects/import", { method: "POST", body: JSON.stringify(bundle) }),
  githubWriteEvents: (projectId: string) =>
    request<GitHubWriteEvent[]>(`/projects/${projectId}/github/write-events`),
  githubPreviewTaskIssue: (projectId: string, taskId: string) =>
    request<GitHubWriteEvent>(`/projects/${projectId}/tasks/${taskId}/github/preview-issue`, { method: "POST" }),
  githubCreateTaskIssue: (projectId: string, taskId: string, body: GitHubIssueCreateRequest) =>
    request<GitHubWriteEvent>(`/projects/${projectId}/tasks/${taskId}/github/create-issue`, {
      method: "POST",
      body: JSON.stringify(body)
    }),
  githubPreviewRiskIssue: (projectId: string, riskId: string) =>
    request<GitHubWriteEvent>(`/projects/${projectId}/risks/${riskId}/github/preview-issue`, { method: "POST" }),
  githubCreateRiskIssue: (projectId: string, riskId: string, body: GitHubIssueCreateRequest) =>
    request<GitHubWriteEvent>(`/projects/${projectId}/risks/${riskId}/github/create-issue`, {
      method: "POST",
      body: JSON.stringify(body)
    }),
  githubPreviewBranch: (projectId: string, branchPlanId: string, body?: Partial<GitHubBranchCreateRequest>) =>
    request<GitHubWriteEvent>(`/projects/${projectId}/branch-plans/${branchPlanId}/github/preview-branch`, {
      method: "POST",
      body: JSON.stringify(body ?? {})
    }),
  githubCreateBranch: (projectId: string, branchPlanId: string, body: GitHubBranchCreateRequest) =>
    request<GitHubWriteEvent>(`/projects/${projectId}/branch-plans/${branchPlanId}/github/create-branch`, {
      method: "POST",
      body: JSON.stringify(body)
    }),
  githubPreviewDraftPR: (projectId: string, prPacketId: string, body?: Partial<GitHubDraftPRCreateRequest>) =>
    request<GitHubWriteEvent>(`/projects/${projectId}/pr-packets/${prPacketId}/github/preview-draft-pr`, {
      method: "POST",
      body: JSON.stringify(body ?? {})
    }),
  githubCreateDraftPR: (projectId: string, prPacketId: string, body: GitHubDraftPRCreateRequest) =>
    request<GitHubWriteEvent>(`/projects/${projectId}/pr-packets/${prPacketId}/github/create-draft-pr`, {
      method: "POST",
      body: JSON.stringify(body)
    }),
  githubReconcile: (projectId: string, body?: { repository_id?: string; auto_reconcile?: boolean }) =>
    request<ReconciliationReport>(`/projects/${projectId}/github/reconcile`, {
      method: "POST",
      body: JSON.stringify(body ?? {})
    }),
  reconciliationEvents: (projectId: string) =>
    request<GitHubReconciliationEvent[]>(`/projects/${projectId}/github/reconciliation-events`),
  statusSuggestions: (projectId: string, includeResolved = false) =>
    request<StatusSuggestion[]>(
      `/projects/${projectId}/status-suggestions${includeResolved ? "?include_resolved=true" : ""}`
    ),
  applyStatusSuggestion: (projectId: string, suggestionId: string) =>
    request<StatusSuggestion>(`/projects/${projectId}/status-suggestions/${suggestionId}/apply`, {
      method: "POST"
    }),
  dismissStatusSuggestion: (projectId: string, suggestionId: string) =>
    request<StatusSuggestion>(`/projects/${projectId}/status-suggestions/${suggestionId}/dismiss`, {
      method: "POST"
    }),
  buildSessionTimeline: (projectId: string, sessionId: string) =>
    request<BuildSessionTimeline>(`/projects/${projectId}/build-sessions/${sessionId}/timeline`),
  generateRetrospective: (projectId: string, body: RetrospectiveGenerateRequest) =>
    request<PostShipRetrospective>(`/projects/${projectId}/retrospectives/generate`, {
      method: "POST",
      body: JSON.stringify(body)
    }),
  retrospectives: (projectId: string) =>
    request<PostShipRetrospective[]>(`/projects/${projectId}/retrospectives`),
  shippedDashboard: (projectId: string) =>
    request<ShippedSummary>(`/projects/${projectId}/shipped`),
  systemControlRoom: () => request<ControlRoomSummary>("/system/control-room"),
  systemShipped: () => request<SystemShippedSummary>("/system/shipped"),
  systemRisks: () => request<RiskConcentrationSummary>("/system/risks"),
  systemDecisionGraph: () => request<DecisionGraph>("/system/decisions/graph"),
  systemStaleness: () => request<StalenessReport>("/system/staleness"),
  projectDecisionGraph: (projectId: string) =>
    request<DecisionGraph>(`/projects/${projectId}/decisions/graph`),
  systemPlaybooks: () => request<Playbook[]>("/system/playbooks"),
  projectPlaybooks: (projectId: string) => request<Playbook[]>(`/projects/${projectId}/playbooks`),
  generatePlaybook: (projectId: string, sessionId: string, body?: { name?: string; category?: string }) =>
    request<Playbook>(
      `/projects/${projectId}/build-sessions/${sessionId}/playbooks/generate`,
      { method: "POST", body: JSON.stringify(body ?? {}) }
    ),
  applyPlaybook: (projectId: string, taskId: string, body: { playbook_id: string }) =>
    request<GeneratedOutput>(
      `/projects/${projectId}/tasks/${taskId}/playbooks/apply`,
      { method: "POST", body: JSON.stringify(body) }
    ),
  createOutcomeScore: (
    projectId: string,
    body: Partial<OutcomeScore> & { score_type: OutcomeScoreType; score: number }
  ) =>
    request<OutcomeScore>(`/projects/${projectId}/outcome-scores`, {
      method: "POST",
      body: JSON.stringify(body)
    }),
  outcomeScores: (projectId: string) =>
    request<OutcomeScore[]>(`/projects/${projectId}/outcome-scores`),
  systemOutcomeScores: () => request<OutcomeScore[]>("/system/outcome-scores"),
  notificationRules: () => request<NotificationRule[]>("/system/notifications/rules"),
  createNotificationRule: (body: Omit<NotificationRule, "id" | "created_at" | "updated_at">) =>
    request<NotificationRule>("/system/notifications/rules", {
      method: "POST",
      body: JSON.stringify(body)
    }),
  updateNotificationRule: (ruleId: string, body: Partial<NotificationRule>) =>
    request<NotificationRule>(`/system/notifications/rules/${ruleId}`, {
      method: "PATCH",
      body: JSON.stringify(body)
    }),
  testNotification: (ruleId: string, payload: Record<string, unknown>) =>
    request<NotificationEvent>("/system/notifications/test", {
      method: "POST",
      body: JSON.stringify({ rule_id: ruleId, payload })
    }),
  notificationEvents: () => request<NotificationEvent[]>("/system/notifications/events"),
  intakeEvents: () => request<IntakeEvent[]>("/intake/events"),
  systemHealth: () => request<SystemHealth>("/system/health"),
  systemWorkers: () => request<WorkerHeartbeat[]>("/system/workers"),
  verifySnapshot: (snapshotId: string) =>
    request<SnapshotIntegrity>(`/system/snapshots/${snapshotId}/verify`, { method: "POST" }),
  restoreSnapshotPreview: (snapshotId: string) =>
    request<SnapshotRestorePreview>(`/system/snapshots/${snapshotId}/restore-preview`, { method: "POST" }),
  backupPolicy: () => request<BackupPolicy>("/system/backups/policy"),
  updateBackupPolicy: (body: BackupPolicyUpdate) =>
    request<BackupPolicy>("/system/backups/policy", { method: "PATCH", body: JSON.stringify(body) }),
  runBackup: (force = false) =>
    request<BackupRunResult>(`/system/backups/run${force ? "?force=true" : ""}`, { method: "POST" }),
  generateDailyReview: () =>
    request<DailyReview>("/system/daily-review/generate", { method: "POST" }),
  mcpAudit: (toolName?: string, limit = 200) =>
    request<MCPAuditEvent[]>(
      `/system/mcp-audit?limit=${limit}${toolName ? `&tool_name=${encodeURIComponent(toolName)}` : ""}`
    ),
  projectMcpAudit: (projectId: string, limit = 200) =>
    request<MCPAuditEvent[]>(`/projects/${projectId}/mcp-audit?limit=${limit}`),
  cronJobs: () => request<CronJob[]>("/system/cron"),
  createCronJob: (body: CronJobCreate) =>
    request<CronJob>("/system/cron", { method: "POST", body: JSON.stringify(body) }),
  updateCronJob: (jobId: string, body: CronJobUpdate) =>
    request<CronJob>(`/system/cron/${jobId}`, { method: "PATCH", body: JSON.stringify(body) }),
  runCronJob: (jobId: string) =>
    request<CronRunResult>(`/system/cron/${jobId}/run`, { method: "POST" }),
  mirrorSnapshot: (snapshotId: string) =>
    request<BackupMirrorEvent>(`/system/backups/${snapshotId}/mirror`, { method: "POST" }),
  backupMirrorEvents: (limit = 100) =>
    request<BackupMirrorEvent[]>(`/system/backups/mirror-events?limit=${limit}`),
  healthHistory: () => request<HealthHistorySummary>("/system/health/history"),
  healthSnapshot: () => request<HealthSnapshot>("/system/health/snapshot", { method: "POST" }),
  resourceChanges: (since?: string, limit = 200) =>
    request<ResourceChangeEvent[]>(
      `/system/resource-changes?limit=${limit}${since ? `&since=${encodeURIComponent(since)}` : ""}`
    ),
  mcpSessions: () => request<MCPSession[]>("/system/mcp-sessions"),
  createMCPSession: (body: MCPSessionCreate) =>
    request<MCPSession>("/system/mcp-sessions", { method: "POST", body: JSON.stringify(body) }),
  updateMCPSession: (sessionId: string, body: MCPSessionUpdate) =>
    request<MCPSession>(`/system/mcp-sessions/${sessionId}`, {
      method: "PATCH",
      body: JSON.stringify(body)
    }),
  revokeMCPSession: (sessionId: string) =>
    request<MCPSession>(`/system/mcp-sessions/${sessionId}/revoke`, { method: "POST" }),
  verifyMcpAudit: (limit = 500) =>
    request<AuditVerificationReport>(`/system/mcp-audit/verify?limit=${limit}`, {
      method: "POST"
    }),
  retentionPolicies: () => request<RetentionPolicy[]>("/system/retention"),
  updateRetentionPolicy: (target: RetentionTarget, body: RetentionPolicyUpdate) =>
    request<RetentionPolicy>(`/system/retention/${target}`, {
      method: "PATCH",
      body: JSON.stringify(body)
    }),
  runRetention: () =>
    request<RetentionRunResult>("/system/retention/run", { method: "POST" }),
  healthAlertRules: () => request<HealthAlertRule[]>("/system/health/alert-rules"),
  createHealthAlertRule: (body: HealthAlertRuleCreate) =>
    request<HealthAlertRule>("/system/health/alert-rules", {
      method: "POST",
      body: JSON.stringify(body)
    }),
  updateHealthAlertRule: (ruleId: string, body: HealthAlertRuleUpdate) =>
    request<HealthAlertRule>(`/system/health/alert-rules/${ruleId}`, {
      method: "PATCH",
      body: JSON.stringify(body)
    }),
  evaluateHealthAlertRules: () =>
    request<HealthAlertEvaluation[]>("/system/health/alert-rules/evaluate", {
      method: "POST"
    }),
  filteredMcpAudit: (params: {
    tool_name?: string;
    session_id?: string;
    blocked?: boolean;
    readonly?: boolean;
    limit?: number;
  }) => {
    const q = new URLSearchParams();
    if (params.tool_name) q.set("tool_name", params.tool_name);
    if (params.session_id) q.set("session_id", params.session_id);
    if (params.blocked !== undefined) q.set("blocked", String(params.blocked));
    if (params.readonly !== undefined) q.set("readonly", String(params.readonly));
    if (params.limit) q.set("limit", String(params.limit));
    return request<MCPAuditEvent[]>(`/system/mcp-audit/filtered?${q.toString()}`);
  }
};

export type IntakeSource =
  | "linear.issue.created"
  | "linear.issue.updated"
  | "sentry.issue.created"
  | "github.webhook.raw"
  | "manual.note";

export type IntakeEvent = {
  id: string;
  source: IntakeSource;
  project_id?: string | null;
  payload: Record<string, unknown>;
  note: string;
  suggestion_id?: string | null;
  received_at: string;
};

// ------- Phase 12 -----------------------------------------------------------

export type WorkerHeartbeat = {
  id: string;
  worker_name: string;
  pid: number;
  status: "starting" | "running" | "idle" | "stopped";
  last_seen_at: string;
  metadata_json: Record<string, unknown>;
};

export type BackupCadence = "manual" | "daily" | "weekly";

export type BackupPolicy = {
  id: string;
  enabled: boolean;
  cadence: BackupCadence;
  max_snapshots: number;
  last_run_at?: string | null;
  destination_path: string;
  created_at: string;
  updated_at: string;
};

export type BackupPolicyUpdate = Partial<Omit<BackupPolicy, "id" | "created_at" | "updated_at" | "last_run_at">>;

export type BackupRunResult = {
  ran: boolean;
  reason: string;
  snapshot_id?: string | null;
  deleted_snapshot_ids: string[];
  policy: BackupPolicy;
};

export type SnapshotIntegrity = {
  snapshot_id: string;
  file_exists: boolean;
  manifest_readable: boolean;
  sqlite_ok: boolean;
  integrity_check: string;
  size_bytes: number;
  issues: string[];
};

export type SnapshotRestorePreview = {
  snapshot_id: string;
  snapshot_size_bytes: number;
  current_db_size_bytes: number;
  snapshot_created_at?: string | null;
  current_project_count: number;
  notes: string[];
  safe_to_restore: boolean;
};

export type DailyReview = {
  generated_at: string;
  headline: string;
  projects_needing_attention: ControlRoomProjectStat[];
  blocked_tasks: Task[];
  high_risks: Risk[];
  stale_build_sessions: BuildSession[];
  failed_jobs: Job[];
  pending_suggestions: StatusSuggestion[];
  recent_shipped: BuildSession[];
  recommended_next_actions: string[];
  markdown: string;
};

export type SystemHealth = {
  status: "ok" | "degraded" | "down";
  generated_at: string;
  api: Record<string, unknown>;
  sqlite: Record<string, unknown>;
  mempalace: Record<string, unknown>;
  workers: WorkerHeartbeat[];
  mcp: Record<string, unknown>;
  github: Record<string, unknown>;
  intake: Record<string, unknown>;
  notifications: Record<string, unknown>;
  recent_failed_jobs: Job[];
  recent_failed_write_events: GitHubWriteEvent[];
  recent_blocked_suggestions: StatusSuggestion[];
  backups: Record<string, unknown>;
};

// ------- Phase 13 -----------------------------------------------------------

export type MCPAuditAction =
  | "create"
  | "update"
  | "save"
  | "pin"
  | "review"
  | "test_run"
  | "build_session"
  | "lesson"
  | "unknown";

export type MCPAuditEvent = {
  id: string;
  session_id: string;
  tool_name: string;
  project_id?: string | null;
  action_type: MCPAuditAction;
  request_summary: string;
  response_summary: string;
  blocked: boolean;
  readonly_mode: boolean;
  created_at: string;
  signature?: string;
  signing_key_id?: string;
};

export type CronJobType =
  | "daily_review"
  | "weekly_review"
  | "backup"
  | "health_snapshot"
  | "risk_scan"
  | "github_reconcile";

export type CronCadence = "manual" | "hourly" | "daily" | "weekly";

export type CronJobStatus = "idle" | "running" | "failed" | "completed";

export type CronJob = {
  id: string;
  name: string;
  job_type: CronJobType;
  cadence: CronCadence;
  enabled: boolean;
  project_id?: string | null;
  last_run_at?: string | null;
  next_run_at?: string | null;
  status: CronJobStatus;
  last_error: string;
  created_at: string;
  updated_at: string;
};

export type CronJobCreate = {
  name: string;
  job_type: CronJobType;
  cadence?: CronCadence;
  enabled?: boolean;
  project_id?: string | null;
};

export type CronJobUpdate = Partial<Omit<CronJobCreate, "job_type">>;

export type CronRunResult = {
  job: CronJob;
  ran: boolean;
  reason: string;
  output_summary: string;
};

export type BackupMirrorSink = "local" | "rclone" | "s3" | "scp";
export type BackupMirrorStatus = "skipped" | "completed" | "failed";

export type BackupMirrorEvent = {
  id: string;
  snapshot_id: string;
  sink: BackupMirrorSink;
  destination: string;
  status: BackupMirrorStatus;
  error_message: string;
  created_at: string;
};

export type HealthSnapshot = {
  id: string;
  status: "ok" | "degraded" | "down";
  summary_json: Record<string, unknown>;
  created_at: string;
};

export type HealthHistorySummary = {
  last_status: "ok" | "degraded" | "down";
  sample_count_24h: number;
  sample_count_7d: number;
  degraded_count_24h: number;
  degraded_count_7d: number;
  down_count_7d: number;
  latest_degraded_reasons: string[];
  recent: HealthSnapshot[];
};

export type ResourceChangeEvent = {
  id: string;
  uri: string;
  project_id?: string | null;
  change_type: "created" | "updated" | "deleted";
  created_at: string;
};

// ------- Phase 14 -----------------------------------------------------------

export type MCPSession = {
  id: string;
  session_id: string;
  label: string;
  readonly: boolean;
  revoked: boolean;
  created_at: string;
  last_seen_at: string;
};

export type MCPSessionCreate = { session_id: string; label?: string; readonly?: boolean };
export type MCPSessionUpdate = Partial<Pick<MCPSession, "label" | "readonly" | "revoked">>;

export type RetentionTarget =
  | "health_snapshots"
  | "resource_changes"
  | "execution_logs"
  | "mcp_audit"
  | "github_events"
  | "intake_events";

export type RetentionPolicy = {
  id: string;
  target: RetentionTarget;
  enabled: boolean;
  days_to_keep: number;
  hard_delete_allowed: boolean;
  last_run_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type RetentionPolicyUpdate = Partial<
  Pick<RetentionPolicy, "enabled" | "days_to_keep" | "hard_delete_allowed">
>;

export type RetentionRunOutcome = {
  target: RetentionTarget;
  deleted: number;
  skipped: boolean;
  reason: string;
};

export type RetentionRunResult = {
  outcomes: RetentionRunOutcome[];
  generated_at: string;
};

export type HealthAlertConditionType =
  | "degraded_samples"
  | "failed_jobs"
  | "backup_overdue"
  | "worker_stale";

export type HealthAlertRule = {
  id: string;
  name: string;
  enabled: boolean;
  condition_type: HealthAlertConditionType;
  threshold: number;
  window_minutes: number;
  notification_rule_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type HealthAlertRuleCreate = Omit<HealthAlertRule, "id" | "created_at" | "updated_at">;
export type HealthAlertRuleUpdate = Partial<Omit<HealthAlertRuleCreate, "condition_type">> & {
  condition_type?: HealthAlertConditionType;
};

export type HealthAlertEvaluation = {
  rule_id: string;
  triggered: boolean;
  reason: string;
  notification_event_ids: string[];
};

export type AuditVerificationResult = {
  event_id: string;
  signed: boolean;
  verified: boolean;
  status: "unsigned" | "valid" | "tampered" | "key_missing";
};

export type AuditVerificationReport = {
  checked: number;
  signed: number;
  valid: number;
  tampered: number;
  unsigned: number;
  key_missing: number;
  results: AuditVerificationResult[];
};
