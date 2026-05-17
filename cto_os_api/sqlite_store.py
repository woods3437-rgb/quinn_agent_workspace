from __future__ import annotations

import json
import os
import shutil
import sqlite3
from pathlib import Path
from threading import RLock
from typing import TypeVar

from pydantic import BaseModel

from .models import (
    ApprovedCommand,
    ApprovedCommandCreate,
    BranchPlan,
    BuildSession,
    BuildSessionCreate,
    BuildSessionUpdate,
    BuildPacket,
    CodeDependency,
    CodeReview,
    CodeSymbol,
    Decision,
    DecisionCreate,
    ExecutionLog,
    ExecutionLogCreate,
    GeneratedOutput,
    BackupCadence,
    BackupMirrorEvent,
    BackupPolicy,
    BackupPolicyUpdate,
    CronJob,
    CronJobCreate,
    CronJobUpdate,
    GitHubIssue,
    GitHubPullRequest,
    GitHubReconciliationEvent,
    GitHubWriteEvent,
    HealthAlertRule,
    HealthAlertRuleCreate,
    HealthAlertRuleUpdate,
    HealthSnapshot,
    IntakeEvent,
    MCPAuditEvent,
    MCPSession,
    MCPSessionCreate,
    MCPSessionUpdate,
    ResourceChangeEvent,
    RetentionPolicy,
    RetentionPolicyUpdate,
    RetentionTarget,
    WorkerHeartbeat,
    WorkerStatus,
    NotificationEvent,
    NotificationRule,
    NotificationRuleCreate,
    NotificationRuleUpdate,
    OutcomeScore,
    OutcomeScoreCreate,
    Playbook,
    PlaybookCreate,
    PostShipRetrospective,
    StatusSuggestion,
    WriterLeaseInfo,
    ImplementationReview,
    ImplementationReviewCreate,
    Job,
    JobCreate,
    JobStatus,
    Memory,
    MemoryCreate,
    Project,
    ProjectCreate,
    PromptTemplate,
    PromptTemplateCreate,
    PRPacket,
    Repository,
    RepositoryCreate,
    RepositoryUpdate,
    RepoFile,
    RepoScan,
    Risk,
    RiskCreate,
    RiskUpdate,
    Task,
    TaskCreate,
    TaskUpdate,
    TestRun,
    WorkflowRun,
    WorkflowRunCreate,
    WorkflowStatus,
    utc_now,
)
from .storage import JsonStore

T = TypeVar("T", bound=BaseModel)


class SQLiteStore:
    def __init__(self, path: str | None = None, json_path: str | None = None) -> None:
        default_path = Path(__file__).parent / "data" / "cto_os.sqlite3"
        self.path = Path(path or os.getenv("CTO_OS_SQLITE_PATH", default_path))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.json_path = Path(json_path or os.getenv("CTO_OS_DATA_PATH", Path(__file__).parent / "data" / "cto_os.json"))
        self.lock = RLock()
        self._init_schema()
        self._migrate_json_if_needed()

    def _connect(self) -> sqlite3.Connection:
        # Phase 11: WAL + a 5s busy_timeout makes concurrent FastAPI + worker +
        # MCP processes safe for short bursty writes. WAL is persistent on the
        # file once set, so re-applying every connection is cheap.
        conn = sqlite3.connect(self.path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def _init_schema(self) -> None:
        with self.lock, self._connect() as conn:
            # Phase 11: enable WAL once per DB file. Idempotent + persistent.
            try:
                conn.execute("PRAGMA journal_mode = WAL")
                conn.execute("PRAGMA synchronous = NORMAL")
            except sqlite3.OperationalError:
                pass
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    pinned INTEGER NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT 'manual'
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    decision_type TEXT NOT NULL,
                    impact_level TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outputs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    output_type TEXT
                );
                CREATE TABLE IF NOT EXISTS prompt_templates (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    category TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    category TEXT NOT NULL,
                    priority TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS execution_logs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    event_type TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS risks (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    likelihood TEXT NOT NULL,
                    status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS implementation_reviews (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    task_id TEXT,
                    output_id TEXT
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    type TEXT NOT NULL,
                    status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workflow_runs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    name TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS build_packets (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    task_id TEXT
                );
                CREATE TABLE IF NOT EXISTS repositories (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    provider TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS repo_scans (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    repository_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS repo_files (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    repository_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    data TEXT NOT NULL,
                    role TEXT NOT NULL,
                    language TEXT NOT NULL,
                    hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS branch_plans (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    repository_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pr_packets (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    repository_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS code_reviews (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    repository_id TEXT,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    risk_level TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS test_runs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    repository_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS code_symbols (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    repository_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    name TEXT NOT NULL,
                    symbol_type TEXT NOT NULL,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS code_dependencies (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    repository_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    dependency TEXT NOT NULL,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS approved_commands (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    repository_id TEXT NOT NULL,
                    command TEXT NOT NULL,
                    command_type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS github_issues (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    repository_id TEXT NOT NULL,
                    number INTEGER NOT NULL,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS github_pull_requests (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    repository_id TEXT NOT NULL,
                    number INTEGER NOT NULL,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS build_sessions (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    repository_id TEXT,
                    task_id TEXT,
                    status TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS github_write_events (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    repository_id TEXT,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reconciliation_events (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    repository_id TEXT,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    applied INTEGER NOT NULL DEFAULT 0,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS status_suggestions (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    suggested_status TEXT NOT NULL,
                    applied INTEGER NOT NULL DEFAULT 0,
                    dismissed INTEGER NOT NULL DEFAULT 0,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS retrospectives (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    build_session_id TEXT,
                    task_id TEXT,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS playbooks (
                    id TEXT PRIMARY KEY,
                    source_project_id TEXT,
                    source_build_session_id TEXT,
                    category TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outcome_scores (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    score_type TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notification_rules (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    channel TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notification_events (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    rule_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS writer_leases (
                    name TEXT PRIMARY KEY,
                    holder TEXT NOT NULL,
                    acquired_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS intake_events (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    project_id TEXT,
                    suggestion_id TEXT,
                    data TEXT NOT NULL,
                    received_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS worker_heartbeats (
                    id TEXT PRIMARY KEY,
                    worker_name TEXT NOT NULL,
                    pid INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS backup_policy (
                    id TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    cadence TEXT NOT NULL DEFAULT 'manual',
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS mcp_audit (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    project_id TEXT,
                    action_type TEXT NOT NULL,
                    blocked INTEGER NOT NULL DEFAULT 0,
                    readonly_mode INTEGER NOT NULL DEFAULT 0,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cron_jobs (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    cadence TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    project_id TEXT,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS backup_mirror_events (
                    id TEXT PRIMARY KEY,
                    snapshot_id TEXT NOT NULL,
                    sink TEXT NOT NULL,
                    status TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS health_snapshots (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS resource_change_events (
                    id TEXT PRIMARY KEY,
                    uri TEXT NOT NULL,
                    project_id TEXT,
                    change_type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS mcp_sessions (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL UNIQUE,
                    label TEXT NOT NULL,
                    readonly INTEGER NOT NULL DEFAULT 0,
                    revoked INTEGER NOT NULL DEFAULT 0,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS retention_policies (
                    id TEXT PRIMARY KEY,
                    target TEXT NOT NULL UNIQUE,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    days_to_keep INTEGER NOT NULL DEFAULT 30,
                    hard_delete_allowed INTEGER NOT NULL DEFAULT 0,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS health_alert_rules (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    condition_type TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at);
                CREATE INDEX IF NOT EXISTS idx_memories_project_id ON memories(project_id);
                CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at);
                CREATE INDEX IF NOT EXISTS idx_memories_pinned ON memories(pinned);
                CREATE INDEX IF NOT EXISTS idx_decisions_project_id ON decisions(project_id);
                CREATE INDEX IF NOT EXISTS idx_decisions_created_at ON decisions(created_at);
                CREATE INDEX IF NOT EXISTS idx_decisions_type ON decisions(decision_type);
                CREATE INDEX IF NOT EXISTS idx_decisions_impact ON decisions(impact_level);
                CREATE INDEX IF NOT EXISTS idx_outputs_project_id ON outputs(project_id);
                CREATE INDEX IF NOT EXISTS idx_outputs_created_at ON outputs(created_at);
                CREATE INDEX IF NOT EXISTS idx_templates_project_id ON prompt_templates(project_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks(project_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
                CREATE INDEX IF NOT EXISTS idx_tasks_category ON tasks(category);
                CREATE INDEX IF NOT EXISTS idx_logs_project_id ON execution_logs(project_id);
                CREATE INDEX IF NOT EXISTS idx_logs_created_at ON execution_logs(created_at);
                CREATE INDEX IF NOT EXISTS idx_risks_project_id ON risks(project_id);
                CREATE INDEX IF NOT EXISTS idx_risks_category ON risks(category);
                CREATE INDEX IF NOT EXISTS idx_risks_status ON risks(status);
                CREATE INDEX IF NOT EXISTS idx_reviews_project_id ON implementation_reviews(project_id);
                CREATE INDEX IF NOT EXISTS idx_jobs_project_id ON jobs(project_id);
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
                CREATE INDEX IF NOT EXISTS idx_jobs_type ON jobs(type);
                CREATE INDEX IF NOT EXISTS idx_workflows_project_id ON workflow_runs(project_id);
                CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflow_runs(status);
                CREATE INDEX IF NOT EXISTS idx_packets_project_id ON build_packets(project_id);
                CREATE INDEX IF NOT EXISTS idx_packets_task_id ON build_packets(task_id);
                CREATE INDEX IF NOT EXISTS idx_repositories_project_id ON repositories(project_id);
                CREATE INDEX IF NOT EXISTS idx_repo_scans_repo ON repo_scans(repository_id);
                CREATE INDEX IF NOT EXISTS idx_repo_files_repo ON repo_files(repository_id);
                CREATE INDEX IF NOT EXISTS idx_repo_files_path ON repo_files(path);
                CREATE INDEX IF NOT EXISTS idx_branch_plans_project ON branch_plans(project_id);
                CREATE INDEX IF NOT EXISTS idx_pr_packets_project ON pr_packets(project_id);
                CREATE INDEX IF NOT EXISTS idx_code_reviews_project ON code_reviews(project_id);
                CREATE INDEX IF NOT EXISTS idx_test_runs_project ON test_runs(project_id);
                CREATE INDEX IF NOT EXISTS idx_symbols_repo ON code_symbols(repository_id);
                CREATE INDEX IF NOT EXISTS idx_symbols_name ON code_symbols(name);
                CREATE INDEX IF NOT EXISTS idx_dependencies_repo ON code_dependencies(repository_id);
                CREATE INDEX IF NOT EXISTS idx_commands_repo ON approved_commands(repository_id);
                CREATE INDEX IF NOT EXISTS idx_build_sessions_project ON build_sessions(project_id);
                CREATE INDEX IF NOT EXISTS idx_build_sessions_status ON build_sessions(status);
                CREATE INDEX IF NOT EXISTS idx_ghwe_project ON github_write_events(project_id);
                CREATE INDEX IF NOT EXISTS idx_ghwe_entity ON github_write_events(entity_type, entity_id);
                CREATE INDEX IF NOT EXISTS idx_recon_project ON reconciliation_events(project_id);
                CREATE INDEX IF NOT EXISTS idx_recon_entity ON reconciliation_events(entity_type, entity_id);
                CREATE INDEX IF NOT EXISTS idx_sugg_project ON status_suggestions(project_id);
                CREATE INDEX IF NOT EXISTS idx_sugg_entity ON status_suggestions(entity_type, entity_id);
                CREATE INDEX IF NOT EXISTS idx_sugg_open ON status_suggestions(applied, dismissed);
                CREATE INDEX IF NOT EXISTS idx_retro_project ON retrospectives(project_id);
                CREATE INDEX IF NOT EXISTS idx_retro_session ON retrospectives(build_session_id);
                CREATE INDEX IF NOT EXISTS idx_ghissues_project ON github_issues(project_id);
                CREATE INDEX IF NOT EXISTS idx_ghprs_project ON github_pull_requests(project_id);
                CREATE INDEX IF NOT EXISTS idx_playbooks_category ON playbooks(category);
                CREATE INDEX IF NOT EXISTS idx_outcome_project ON outcome_scores(project_id);
                CREATE INDEX IF NOT EXISTS idx_outcome_type ON outcome_scores(score_type);
                CREATE INDEX IF NOT EXISTS idx_notif_rule_project ON notification_rules(project_id);
                CREATE INDEX IF NOT EXISTS idx_notif_event_rule ON notification_events(rule_id);
                CREATE INDEX IF NOT EXISTS idx_writer_leases_expires ON writer_leases(expires_at);
                CREATE INDEX IF NOT EXISTS idx_intake_source ON intake_events(source);
                CREATE INDEX IF NOT EXISTS idx_intake_project ON intake_events(project_id);
                CREATE INDEX IF NOT EXISTS idx_heartbeats_worker ON worker_heartbeats(worker_name);
                CREATE INDEX IF NOT EXISTS idx_heartbeats_seen ON worker_heartbeats(last_seen_at);
                CREATE INDEX IF NOT EXISTS idx_audit_project ON mcp_audit(project_id);
                CREATE INDEX IF NOT EXISTS idx_audit_tool ON mcp_audit(tool_name);
                CREATE INDEX IF NOT EXISTS idx_audit_created ON mcp_audit(created_at);
                CREATE INDEX IF NOT EXISTS idx_cron_enabled ON cron_jobs(enabled);
                CREATE INDEX IF NOT EXISTS idx_cron_type ON cron_jobs(job_type);
                CREATE INDEX IF NOT EXISTS idx_mirror_snapshot ON backup_mirror_events(snapshot_id);
                CREATE INDEX IF NOT EXISTS idx_health_created ON health_snapshots(created_at);
                CREATE INDEX IF NOT EXISTS idx_rce_uri ON resource_change_events(uri);
                CREATE INDEX IF NOT EXISTS idx_rce_created ON resource_change_events(created_at);
                CREATE INDEX IF NOT EXISTS idx_sess_seen ON mcp_sessions(last_seen_at);
                CREATE INDEX IF NOT EXISTS idx_retention_target ON retention_policies(target);
                CREATE INDEX IF NOT EXISTS idx_alert_enabled ON health_alert_rules(enabled);
                """
            )

    def _migrate_json_if_needed(self) -> None:
        with self._connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        if count or not self.json_path.exists():
            return
        backup = self.json_path.with_suffix(".phase3-backup.json")
        if not backup.exists():
            shutil.copy2(self.json_path, backup)
        old = JsonStore(path=str(self.json_path))
        for project in old.list_projects():
            self._insert_model("projects", project, status=project.status, created_at=project.created_at, updated_at=project.updated_at)
        for memory in old.list_memories(project_id=None):
            self._insert_model("memories", memory, project_id=memory.project_id, created_at=memory.created_at, updated_at=memory.updated_at, pinned=int(memory.pinned), source=memory.source)
        for project in old.list_projects():
            for decision in old.list_decisions(project.id):
                self._insert_model("decisions", decision, project_id=decision.project_id, created_at=decision.created_at, decision_type=decision.decision_type.value, impact_level=decision.impact_level.value)
            for output in old.list_outputs(project.id):
                self._insert_model("outputs", output, project_id=output.project_id, created_at=output.created_at, output_type=output.metadata.get("output_type"))
            for task in old.list_tasks(project.id):
                self._insert_model("tasks", task, project_id=task.project_id, created_at=task.created_at, updated_at=task.updated_at, status=task.status.value, category=task.category.value, priority=task.priority.value)
        for template in old.list_prompt_templates():
            self._insert_model("prompt_templates", template, project_id=template.project_id, created_at=template.created_at, updated_at=template.updated_at, category=template.category)

    def _insert_model(self, table: str, model: BaseModel, **columns) -> None:
        payload = model.model_dump(mode="json")
        base = {"id": payload["id"], "data": json.dumps(payload)}
        base.update({key: str(value) if value is not None else None for key, value in columns.items()})
        keys = list(base.keys())
        sql = f"INSERT OR REPLACE INTO {table} ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})"
        with self.lock, self._connect() as conn:
            conn.execute(sql, [base[key] for key in keys])

    def _load_model(self, row: sqlite3.Row, model: type[T]) -> T:
        return model.model_validate(json.loads(row["data"]))

    def list_projects(self) -> list[Project]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM projects ORDER BY updated_at DESC").fetchall()
        return [self._load_model(row, Project) for row in rows]

    def create_project(self, payload: ProjectCreate) -> Project:
        project = Project(**payload.model_dump())
        self._insert_model("projects", project, status=project.status, created_at=project.created_at, updated_at=project.updated_at)
        return project

    def get_project(self, project_id: str) -> Project:
        with self._connect() as conn:
            row = conn.execute("SELECT data FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not row:
            raise KeyError(project_id)
        return self._load_model(row, Project)

    def touch_project(self, project_id: str) -> None:
        project = self.get_project(project_id)
        project.updated_at = utc_now()
        self._insert_model("projects", project, status=project.status, created_at=project.created_at, updated_at=project.updated_at)

    def list_memories(self, project_id: str | None = None, pinned: bool | None = None) -> list[Memory]:
        where = []
        params: list[object] = []
        if project_id:
            where.append("project_id = ?")
            params.append(project_id)
        if pinned is not None:
            where.append("pinned = ?")
            params.append(1 if pinned else 0)
        sql = "SELECT data FROM memories"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY pinned DESC, updated_at DESC"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._load_model(row, Memory) for row in rows]

    def create_memory(self, project_id: str, payload: MemoryCreate) -> Memory:
        self.get_project(project_id)
        memory = Memory(project_id=project_id, **payload.model_dump())
        self._insert_model("memories", memory, project_id=memory.project_id, created_at=memory.created_at, updated_at=memory.updated_at, pinned=int(memory.pinned), source=memory.source)
        self.touch_project(project_id)
        return memory

    def update_memory_pin(self, project_id: str, memory_id: str, pinned: bool) -> Memory:
        memory = next((m for m in self.list_memories(project_id) if m.id == memory_id), None)
        if memory is None:
            raise KeyError(memory_id)
        memory.pinned = pinned
        memory.updated_at = utc_now()
        self._insert_model("memories", memory, project_id=memory.project_id, created_at=memory.created_at, updated_at=memory.updated_at, pinned=int(memory.pinned), source=memory.source)
        self.touch_project(project_id)
        return memory

    def list_decisions(self, project_id: str) -> list[Decision]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM decisions WHERE project_id = ? ORDER BY created_at DESC", (project_id,)).fetchall()
        return [self._load_model(row, Decision) for row in rows]

    def create_decision(self, project_id: str, payload: DecisionCreate) -> Decision:
        self.get_project(project_id)
        decision = Decision(project_id=project_id, **payload.model_dump())
        self._insert_model("decisions", decision, project_id=project_id, created_at=decision.created_at, decision_type=decision.decision_type.value, impact_level=decision.impact_level.value)
        self.touch_project(project_id)
        return decision

    def list_tasks(self, project_id: str) -> list[Task]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM tasks WHERE project_id = ? ORDER BY updated_at DESC", (project_id,)).fetchall()
        return [self._load_model(row, Task) for row in rows]

    def create_task(self, project_id: str, payload: TaskCreate) -> Task:
        self.get_project(project_id)
        task = Task(project_id=project_id, **payload.model_dump())
        self._save_task(task)
        self.touch_project(project_id)
        return task

    def _save_task(self, task: Task) -> None:
        self._insert_model("tasks", task, project_id=task.project_id, created_at=task.created_at, updated_at=task.updated_at, status=task.status.value, category=task.category.value, priority=task.priority.value)

    def update_task(self, project_id: str, task_id: str, payload: TaskUpdate) -> Task:
        task = next((t for t in self.list_tasks(project_id) if t.id == task_id), None)
        if task is None:
            raise KeyError(task_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(task, key, value)
        task.updated_at = utc_now()
        self._save_task(task)
        self.touch_project(project_id)
        return task

    def delete_task(self, project_id: str, task_id: str) -> None:
        with self.lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE project_id = ? AND id = ?", (project_id, task_id))
            if cur.rowcount == 0:
                raise KeyError(task_id)
        self.touch_project(project_id)

    def list_outputs(self, project_id: str) -> list[GeneratedOutput]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM outputs WHERE project_id = ? ORDER BY created_at DESC", (project_id,)).fetchall()
        return [self._load_model(row, GeneratedOutput) for row in rows]

    def save_output(self, output: GeneratedOutput) -> GeneratedOutput:
        self._insert_model("outputs", output, project_id=output.project_id, created_at=output.created_at, output_type=output.metadata.get("output_type"))
        self.touch_project(output.project_id)
        return output

    def get_output(self, project_id: str, output_id: str) -> GeneratedOutput:
        with self._connect() as conn:
            row = conn.execute("SELECT data FROM outputs WHERE project_id = ? AND id = ?", (project_id, output_id)).fetchone()
        if not row:
            raise KeyError(output_id)
        return self._load_model(row, GeneratedOutput)

    def list_prompt_templates(self, project_id: str | None = None, include_global: bool = True) -> list[PromptTemplate]:
        params: list[object] = []
        sql = "SELECT data FROM prompt_templates"
        if project_id:
            sql += " WHERE project_id = ?"
            params.append(project_id)
            if include_global:
                sql += " OR project_id IS NULL"
        sql += " ORDER BY updated_at DESC"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._load_model(row, PromptTemplate) for row in rows]

    def create_prompt_template(self, payload: PromptTemplateCreate) -> PromptTemplate:
        if not payload.template_body and payload.template:
            payload.template_body = payload.template
        if not payload.template and payload.template_body:
            payload.template = payload.template_body
        template = PromptTemplate(**payload.model_dump())
        return self.save_prompt_template(template)

    def save_prompt_template(self, template: PromptTemplate) -> PromptTemplate:
        self._insert_model("prompt_templates", template, project_id=template.project_id, created_at=template.created_at, updated_at=template.updated_at, category=template.category)
        return template

    def get_prompt_template(self, template_id: str) -> PromptTemplate:
        with self._connect() as conn:
            row = conn.execute("SELECT data FROM prompt_templates WHERE id = ?", (template_id,)).fetchone()
        if not row:
            raise KeyError(template_id)
        return self._load_model(row, PromptTemplate)

    def duplicate_prompt_template(self, template_id: str, project_id: str | None = None) -> PromptTemplate:
        original = self.get_prompt_template(template_id)
        return self.save_prompt_template(PromptTemplate(
            project_id=project_id if project_id is not None else original.project_id,
            name=f"{original.name} Copy",
            description=original.description,
            category=original.category,
            agent_type=original.agent_type,
            template_body=original.template_body or original.template,
            input_variables=original.input_variables,
            template=original.template or original.template_body,
            agent_id=original.agent_id,
        ))

    def list_logs(self, project_id: str) -> list[ExecutionLog]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM execution_logs WHERE project_id = ? ORDER BY created_at DESC", (project_id,)).fetchall()
        return [self._load_model(row, ExecutionLog) for row in rows]

    def create_log(self, project_id: str, payload: ExecutionLogCreate) -> ExecutionLog:
        self.get_project(project_id)
        log = ExecutionLog(project_id=project_id, **payload.model_dump())
        self._insert_model("execution_logs", log, project_id=project_id, created_at=log.created_at, event_type=log.event_type.value)
        return log

    def list_risks(self, project_id: str) -> list[Risk]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM risks WHERE project_id = ? ORDER BY updated_at DESC", (project_id,)).fetchall()
        return [self._load_model(row, Risk) for row in rows]

    def create_risk(self, project_id: str, payload: RiskCreate) -> Risk:
        self.get_project(project_id)
        risk = Risk(project_id=project_id, **payload.model_dump())
        self._save_risk(risk)
        return risk

    def _save_risk(self, risk: Risk) -> None:
        self._insert_model("risks", risk, project_id=risk.project_id, created_at=risk.created_at, updated_at=risk.updated_at, category=risk.category.value, severity=risk.severity.value, likelihood=risk.likelihood.value, status=risk.status.value)

    def update_risk(self, project_id: str, risk_id: str, payload: RiskUpdate) -> Risk:
        risk = next((r for r in self.list_risks(project_id) if r.id == risk_id), None)
        if risk is None:
            raise KeyError(risk_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(risk, key, value)
        risk.updated_at = utc_now()
        self._save_risk(risk)
        return risk

    def list_reviews(self, project_id: str) -> list[ImplementationReview]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM implementation_reviews WHERE project_id = ? ORDER BY created_at DESC", (project_id,)).fetchall()
        return [self._load_model(row, ImplementationReview) for row in rows]

    def save_review(self, review: ImplementationReview) -> ImplementationReview:
        self._insert_model("implementation_reviews", review, project_id=review.project_id, created_at=review.created_at, task_id=review.task_id, output_id=review.output_id)
        return review

    def list_jobs(self, project_id: str, status: str | None = None, job_type: str | None = None) -> list[Job]:
        params: list[object] = [project_id]
        sql = "SELECT data FROM jobs WHERE project_id = ?"
        if status:
            sql += " AND status = ?"
            params.append(status)
        if job_type:
            sql += " AND type = ?"
            params.append(job_type)
        sql += " ORDER BY updated_at DESC"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._load_model(row, Job) for row in rows]

    def create_job(self, project_id: str, payload: JobCreate) -> Job:
        self.get_project(project_id)
        job = Job(project_id=project_id, **payload.model_dump())
        return self.save_job(job)

    def get_job(self, project_id: str, job_id: str) -> Job:
        with self._connect() as conn:
            row = conn.execute("SELECT data FROM jobs WHERE project_id = ? AND id = ?", (project_id, job_id)).fetchone()
        if not row:
            raise KeyError(job_id)
        return self._load_model(row, Job)

    def save_job(self, job: Job) -> Job:
        job.updated_at = utc_now()
        self._insert_model("jobs", job, project_id=job.project_id, created_at=job.created_at, updated_at=job.updated_at, type=job.type.value, status=job.status.value)
        self.touch_project(job.project_id)
        return job

    def cancel_job(self, project_id: str, job_id: str) -> Job:
        job = self.get_job(project_id, job_id)
        if job.status in {JobStatus.completed, JobStatus.failed}:
            return job
        job.status = JobStatus.cancelled
        job.completed_at = utc_now()
        return self.save_job(job)

    def list_workflows(self, project_id: str) -> list[WorkflowRun]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM workflow_runs WHERE project_id = ? ORDER BY updated_at DESC", (project_id,)).fetchall()
        return [self._load_model(row, WorkflowRun) for row in rows]

    def create_workflow(self, project_id: str, payload: WorkflowRunCreate, steps: list[dict]) -> WorkflowRun:
        self.get_project(project_id)
        workflow = WorkflowRun(project_id=project_id, name=payload.name, payload_json=payload.payload_json, steps=steps)
        return self.save_workflow(workflow)

    def save_workflow(self, workflow: WorkflowRun) -> WorkflowRun:
        workflow.updated_at = utc_now()
        self._insert_model("workflow_runs", workflow, project_id=workflow.project_id, created_at=workflow.created_at, updated_at=workflow.updated_at, status=workflow.status.value, name=workflow.name)
        self.touch_project(workflow.project_id)
        return workflow

    def list_build_packets(self, project_id: str) -> list[BuildPacket]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM build_packets WHERE project_id = ? ORDER BY created_at DESC", (project_id,)).fetchall()
        return [self._load_model(row, BuildPacket) for row in rows]

    def get_build_packet(self, project_id: str, packet_id: str) -> BuildPacket:
        with self._connect() as conn:
            row = conn.execute("SELECT data FROM build_packets WHERE project_id = ? AND id = ?", (project_id, packet_id)).fetchone()
        if not row:
            raise KeyError(packet_id)
        return self._load_model(row, BuildPacket)

    def save_build_packet(self, packet: BuildPacket) -> BuildPacket:
        self._insert_model("build_packets", packet, project_id=packet.project_id, created_at=packet.created_at, task_id=packet.task_id)
        self.touch_project(packet.project_id)
        return packet

    def list_repositories(self, project_id: str) -> list[Repository]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM repositories WHERE project_id = ? ORDER BY updated_at DESC", (project_id,)).fetchall()
        return [self._load_model(row, Repository) for row in rows]

    def create_repository(self, project_id: str, payload: RepositoryCreate) -> Repository:
        self.get_project(project_id)
        repository = Repository(project_id=project_id, **payload.model_dump())
        return self.save_repository(repository)

    def update_repository(self, project_id: str, repository_id: str, payload: RepositoryUpdate) -> Repository:
        repository = next((repo for repo in self.list_repositories(project_id) if repo.id == repository_id), None)
        if repository is None:
            raise KeyError(repository_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(repository, key, value)
        repository.updated_at = utc_now()
        return self.save_repository(repository)

    def save_repository(self, repository: Repository) -> Repository:
        self._insert_model("repositories", repository, project_id=repository.project_id, created_at=repository.created_at, updated_at=repository.updated_at, provider=repository.provider.value)
        self.touch_project(repository.project_id)
        return repository

    def delete_repository(self, project_id: str, repository_id: str) -> None:
        with self.lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM repositories WHERE project_id = ? AND id = ?", (project_id, repository_id))
            if cur.rowcount == 0:
                raise KeyError(repository_id)
        self.touch_project(project_id)

    def get_repository(self, project_id: str, repository_id: str) -> Repository:
        repo = next((item for item in self.list_repositories(project_id) if item.id == repository_id), None)
        if repo is None:
            raise KeyError(repository_id)
        return repo

    def save_repo_scan(self, scan: RepoScan) -> RepoScan:
        self._insert_model("repo_scans", scan, project_id=scan.project_id, repository_id=scan.repository_id, created_at=scan.created_at)
        self.touch_project(scan.project_id)
        return scan

    def list_repo_scans(self, project_id: str, repository_id: str) -> list[RepoScan]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM repo_scans WHERE project_id = ? AND repository_id = ? ORDER BY created_at DESC", (project_id, repository_id)).fetchall()
        return [self._load_model(row, RepoScan) for row in rows]

    def replace_repo_files(self, project_id: str, repository_id: str, files: list[RepoFile]) -> None:
        with self.lock, self._connect() as conn:
            conn.execute("DELETE FROM repo_files WHERE project_id = ? AND repository_id = ?", (project_id, repository_id))
        for file in files:
            self._insert_model("repo_files", file, project_id=file.project_id, repository_id=file.repository_id, path=file.path, role=file.role.value, language=file.language, hash=file.hash)

    def list_repo_files(self, project_id: str, repository_id: str) -> list[RepoFile]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM repo_files WHERE project_id = ? AND repository_id = ? ORDER BY path ASC", (project_id, repository_id)).fetchall()
        return [self._load_model(row, RepoFile) for row in rows]

    def get_repo_file(self, project_id: str, repository_id: str, file_id: str) -> RepoFile:
        with self._connect() as conn:
            row = conn.execute("SELECT data FROM repo_files WHERE project_id = ? AND repository_id = ? AND id = ?", (project_id, repository_id, file_id)).fetchone()
        if not row:
            raise KeyError(file_id)
        return self._load_model(row, RepoFile)

    def search_repo_files(self, project_id: str, repository_id: str, query: str) -> list[RepoFile]:
        query_lower = query.lower()
        return [file for file in self.list_repo_files(project_id, repository_id) if query_lower in file.path.lower() or query_lower in file.summary.lower() or query_lower in file.role.value]

    def save_branch_plan(self, plan: BranchPlan) -> BranchPlan:
        self._insert_model("branch_plans", plan, project_id=plan.project_id, repository_id=plan.repository_id, created_at=plan.created_at)
        self.touch_project(plan.project_id)
        return plan

    def list_branch_plans(self, project_id: str) -> list[BranchPlan]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM branch_plans WHERE project_id = ? ORDER BY created_at DESC", (project_id,)).fetchall()
        return [self._load_model(row, BranchPlan) for row in rows]

    def get_branch_plan(self, project_id: str, plan_id: str) -> BranchPlan:
        plan = next((item for item in self.list_branch_plans(project_id) if item.id == plan_id), None)
        if plan is None:
            raise KeyError(plan_id)
        return plan

    def save_pr_packet(self, packet: PRPacket) -> PRPacket:
        self._insert_model("pr_packets", packet, project_id=packet.project_id, repository_id=packet.repository_id, created_at=packet.created_at)
        self.touch_project(packet.project_id)
        return packet

    def list_pr_packets(self, project_id: str) -> list[PRPacket]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM pr_packets WHERE project_id = ? ORDER BY created_at DESC", (project_id,)).fetchall()
        return [self._load_model(row, PRPacket) for row in rows]

    def save_code_review(self, review: CodeReview) -> CodeReview:
        self._insert_model("code_reviews", review, project_id=review.project_id, repository_id=review.repository_id, created_at=review.created_at, risk_level=review.risk_level)
        self.touch_project(review.project_id)
        return review

    def list_code_reviews(self, project_id: str) -> list[CodeReview]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM code_reviews WHERE project_id = ? ORDER BY created_at DESC", (project_id,)).fetchall()
        return [self._load_model(row, CodeReview) for row in rows]

    def save_test_run(self, test_run: TestRun) -> TestRun:
        self._insert_model("test_runs", test_run, project_id=test_run.project_id, repository_id=test_run.repository_id, created_at=test_run.created_at, status=test_run.status.value)
        self.touch_project(test_run.project_id)
        return test_run

    def list_test_runs(self, project_id: str) -> list[TestRun]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM test_runs WHERE project_id = ? ORDER BY created_at DESC", (project_id,)).fetchall()
        return [self._load_model(row, TestRun) for row in rows]

    def replace_code_intelligence(self, project_id: str, repository_id: str, symbols: list[CodeSymbol], dependencies: list[CodeDependency]) -> None:
        with self.lock, self._connect() as conn:
            conn.execute("DELETE FROM code_symbols WHERE project_id = ? AND repository_id = ?", (project_id, repository_id))
            conn.execute("DELETE FROM code_dependencies WHERE project_id = ? AND repository_id = ?", (project_id, repository_id))
        for symbol in symbols:
            self._insert_model("code_symbols", symbol, project_id=symbol.project_id, repository_id=symbol.repository_id, file_path=symbol.file_path, name=symbol.name, symbol_type=symbol.symbol_type)
        for dep in dependencies:
            self._insert_model("code_dependencies", dep, project_id=dep.project_id, repository_id=dep.repository_id, file_path=dep.file_path, dependency=dep.dependency)

    def list_code_symbols(self, project_id: str, repository_id: str) -> list[CodeSymbol]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM code_symbols WHERE project_id = ? AND repository_id = ? ORDER BY file_path, name", (project_id, repository_id)).fetchall()
        return [self._load_model(row, CodeSymbol) for row in rows]

    def search_code_symbols(self, project_id: str, repository_id: str, query: str) -> list[CodeSymbol]:
        query_lower = query.lower()
        return [symbol for symbol in self.list_code_symbols(project_id, repository_id) if query_lower in symbol.name.lower() or query_lower in symbol.file_path.lower() or query_lower in symbol.symbol_type.lower()]

    def list_code_dependencies(self, project_id: str, repository_id: str) -> list[CodeDependency]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM code_dependencies WHERE project_id = ? AND repository_id = ? ORDER BY file_path, dependency", (project_id, repository_id)).fetchall()
        return [self._load_model(row, CodeDependency) for row in rows]

    def list_approved_commands(self, project_id: str, repository_id: str) -> list[ApprovedCommand]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM approved_commands WHERE project_id = ? AND repository_id = ? ORDER BY created_at DESC", (project_id, repository_id)).fetchall()
        return [self._load_model(row, ApprovedCommand) for row in rows]

    def create_approved_command(self, project_id: str, repository_id: str, payload: ApprovedCommandCreate) -> ApprovedCommand:
        self.get_repository(project_id, repository_id)
        command = ApprovedCommand(project_id=project_id, repository_id=repository_id, **payload.model_dump())
        return self.save_approved_command(command)

    def save_approved_command(self, command: ApprovedCommand) -> ApprovedCommand:
        self._insert_model("approved_commands", command, project_id=command.project_id, repository_id=command.repository_id, command=command.command, command_type=command.command_type.value, created_at=command.created_at)
        self.touch_project(command.project_id)
        return command

    def get_approved_command(self, project_id: str, repository_id: str, command_id: str) -> ApprovedCommand:
        command = next((item for item in self.list_approved_commands(project_id, repository_id) if item.id == command_id), None)
        if command is None:
            raise KeyError(command_id)
        return command

    def replace_github_sync(self, project_id: str, repository_id: str, issues: list[GitHubIssue], prs: list[GitHubPullRequest]) -> None:
        with self.lock, self._connect() as conn:
            conn.execute("DELETE FROM github_issues WHERE project_id = ? AND repository_id = ?", (project_id, repository_id))
            conn.execute("DELETE FROM github_pull_requests WHERE project_id = ? AND repository_id = ?", (project_id, repository_id))
        for issue in issues:
            self._insert_model("github_issues", issue, project_id=project_id, repository_id=repository_id, number=issue.number)
        for pr in prs:
            self._insert_model("github_pull_requests", pr, project_id=project_id, repository_id=repository_id, number=pr.number)

    def create_build_session(self, project_id: str, payload: BuildSessionCreate) -> BuildSession:
        self.get_project(project_id)
        session = BuildSession(project_id=project_id, **payload.model_dump())
        # Phase 15: when the caller leaves linked_build_packet_id /
        # linked_branch_plan_id blank but supplies a task_id, auto-fill
        # with the most recent task-scoped artifacts so build session
        # summaries don't show "Branch plan: none / Build packet: none"
        # for work that obviously links together. Never overwrites
        # explicit caller values.
        if session.task_id:
            if not session.linked_build_packet_id:
                packet = next(
                    (
                        p
                        for p in self.list_build_packets(project_id)
                        if p.task_id == session.task_id
                    ),
                    None,
                )
                if packet is not None:
                    session.linked_build_packet_id = packet.id
            if not session.linked_branch_plan_id:
                plan = next(
                    (
                        p
                        for p in self.list_branch_plans(project_id)
                        if p.task_id == session.task_id
                    ),
                    None,
                )
                if plan is not None:
                    session.linked_branch_plan_id = plan.id
        return self.save_build_session(session)

    def save_build_session(self, session: BuildSession) -> BuildSession:
        session.updated_at = utc_now()
        self._insert_model("build_sessions", session, project_id=session.project_id, repository_id=session.repository_id, task_id=session.task_id, status=session.status.value, created_at=session.created_at, updated_at=session.updated_at)
        self.touch_project(session.project_id)
        return session

    def update_build_session(self, project_id: str, session_id: str, payload: BuildSessionUpdate) -> BuildSession:
        session = next((item for item in self.list_build_sessions(project_id) if item.id == session_id), None)
        if session is None:
            raise KeyError(session_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(session, key, value)
        return self.save_build_session(session)

    def list_build_sessions(self, project_id: str) -> list[BuildSession]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM build_sessions WHERE project_id = ? ORDER BY updated_at DESC", (project_id,)).fetchall()
        return [self._load_model(row, BuildSession) for row in rows]

    # ---------------------------------------------------------- Phase 7 writes

    def save_task(self, task: Task) -> Task:
        self._save_task(task)
        self.touch_project(task.project_id)
        return task

    def save_risk(self, risk: Risk) -> Risk:
        self._save_risk(risk)
        return risk

    def get_task(self, project_id: str, task_id: str) -> Task:
        task = next((item for item in self.list_tasks(project_id) if item.id == task_id), None)
        if task is None:
            raise KeyError(task_id)
        return task

    def get_risk(self, project_id: str, risk_id: str) -> Risk:
        risk = next((item for item in self.list_risks(project_id) if item.id == risk_id), None)
        if risk is None:
            raise KeyError(risk_id)
        return risk

    def get_pr_packet(self, project_id: str, pr_packet_id: str) -> PRPacket:
        packet = next((item for item in self.list_pr_packets(project_id) if item.id == pr_packet_id), None)
        if packet is None:
            raise KeyError(pr_packet_id)
        return packet

    def save_github_write_event(self, event: GitHubWriteEvent) -> GitHubWriteEvent:
        self._insert_model(
            "github_write_events",
            event,
            project_id=event.project_id,
            repository_id=event.repository_id,
            entity_type=event.entity_type.value,
            entity_id=event.entity_id,
            action=event.action.value,
            status=event.status.value,
            created_at=event.created_at,
        )
        return event

    def list_github_write_events(self, project_id: str) -> list[GitHubWriteEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM github_write_events WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        return [self._load_model(row, GitHubWriteEvent) for row in rows]

    def attach_github_event_to_session(
        self, project_id: str, session_id: str, event_id: str
    ) -> BuildSession | None:
        session = next(
            (item for item in self.list_build_sessions(project_id) if item.id == session_id),
            None,
        )
        if session is None:
            return None
        if event_id not in session.linked_github_write_event_ids:
            session.linked_github_write_event_ids.append(event_id)
        return self.save_build_session(session)

    # ---------------------------------------------------------- Phase 8 reads

    def list_github_issues(self, project_id: str) -> list[GitHubIssue]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM github_issues WHERE project_id = ? ORDER BY number DESC",
                (project_id,),
            ).fetchall()
        return [self._load_model(row, GitHubIssue) for row in rows]

    def list_github_pull_requests(self, project_id: str) -> list[GitHubPullRequest]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM github_pull_requests WHERE project_id = ? ORDER BY number DESC",
                (project_id,),
            ).fetchall()
        return [self._load_model(row, GitHubPullRequest) for row in rows]

    # -------------------------------------------------- reconciliation events

    def save_reconciliation_event(
        self, event: GitHubReconciliationEvent
    ) -> GitHubReconciliationEvent:
        self._insert_model(
            "reconciliation_events",
            event,
            project_id=event.project_id,
            repository_id=event.repository_id,
            entity_type=event.entity_type.value,
            entity_id=event.entity_id,
            applied=int(event.applied),
            created_at=event.created_at,
        )
        return event

    def list_reconciliation_events(
        self, project_id: str
    ) -> list[GitHubReconciliationEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM reconciliation_events WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        return [self._load_model(row, GitHubReconciliationEvent) for row in rows]

    # ----------------------------------------------------- status suggestions

    def save_status_suggestion(self, suggestion: StatusSuggestion) -> StatusSuggestion:
        self._insert_model(
            "status_suggestions",
            suggestion,
            project_id=suggestion.project_id,
            entity_type=suggestion.entity_type.value,
            entity_id=suggestion.entity_id,
            suggested_status=suggestion.suggested_status,
            applied=int(suggestion.applied),
            dismissed=int(suggestion.dismissed),
            created_at=suggestion.created_at,
        )
        return suggestion

    def list_status_suggestions(
        self,
        project_id: str,
        include_resolved: bool = False,
    ) -> list[StatusSuggestion]:
        with self._connect() as conn:
            if include_resolved:
                rows = conn.execute(
                    "SELECT data FROM status_suggestions WHERE project_id = ? ORDER BY created_at DESC",
                    (project_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT data FROM status_suggestions WHERE project_id = ? AND applied = 0 AND dismissed = 0 ORDER BY created_at DESC",
                    (project_id,),
                ).fetchall()
        return [self._load_model(row, StatusSuggestion) for row in rows]

    def get_status_suggestion(
        self, project_id: str, suggestion_id: str
    ) -> StatusSuggestion:
        suggestion = next(
            (
                item
                for item in self.list_status_suggestions(project_id, include_resolved=True)
                if item.id == suggestion_id
            ),
            None,
        )
        if suggestion is None:
            raise KeyError(suggestion_id)
        return suggestion

    # ----------------------------------------------------------- retrospectives

    def save_retrospective(self, retro: PostShipRetrospective) -> PostShipRetrospective:
        self._insert_model(
            "retrospectives",
            retro,
            project_id=retro.project_id,
            build_session_id=retro.build_session_id,
            task_id=retro.task_id,
            created_at=retro.created_at,
        )
        return retro

    def list_retrospectives(self, project_id: str) -> list[PostShipRetrospective]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM retrospectives WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        return [self._load_model(row, PostShipRetrospective) for row in rows]

    # ------------------------------------------------------ Phase 9 playbooks

    def save_playbook(self, playbook: Playbook) -> Playbook:
        self._insert_model(
            "playbooks",
            playbook,
            source_project_id=playbook.source_project_id,
            source_build_session_id=playbook.source_build_session_id,
            category=playbook.category,
            created_at=playbook.created_at,
            updated_at=playbook.updated_at,
        )
        return playbook

    def create_playbook(self, payload: PlaybookCreate) -> Playbook:
        playbook = Playbook(**payload.model_dump())
        return self.save_playbook(playbook)

    def list_playbooks(
        self,
        source_project_id: str | None = None,
        category: str | None = None,
    ) -> list[Playbook]:
        with self._connect() as conn:
            clauses = []
            params: list[str] = []
            if source_project_id is not None:
                clauses.append("source_project_id = ?")
                params.append(source_project_id)
            if category is not None:
                clauses.append("category = ?")
                params.append(category)
            where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = conn.execute(
                f"SELECT data FROM playbooks {where} ORDER BY updated_at DESC", params
            ).fetchall()
        return [self._load_model(row, Playbook) for row in rows]

    def get_playbook(self, playbook_id: str) -> Playbook:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM playbooks WHERE id = ?", (playbook_id,)
            ).fetchone()
        if row is None:
            raise KeyError(playbook_id)
        return self._load_model(row, Playbook)

    # -------------------------------------------------- Phase 9 outcome scores

    def create_outcome_score(
        self, project_id: str, payload: OutcomeScoreCreate
    ) -> OutcomeScore:
        self.get_project(project_id)
        clamped = max(1, min(5, int(payload.score)))
        score = OutcomeScore(project_id=project_id, **{**payload.model_dump(), "score": clamped})
        self._insert_model(
            "outcome_scores",
            score,
            project_id=project_id,
            score_type=score.score_type.value,
            score=score.score,
            created_at=score.created_at,
        )
        return score

    def list_outcome_scores(
        self, project_id: str | None = None
    ) -> list[OutcomeScore]:
        with self._connect() as conn:
            if project_id is None:
                rows = conn.execute(
                    "SELECT data FROM outcome_scores ORDER BY created_at DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT data FROM outcome_scores WHERE project_id = ? ORDER BY created_at DESC",
                    (project_id,),
                ).fetchall()
        return [self._load_model(row, OutcomeScore) for row in rows]

    # -------------------------------------------------- Phase 9 notifications

    def create_notification_rule(self, payload: NotificationRuleCreate) -> NotificationRule:
        rule = NotificationRule(**payload.model_dump())
        return self.save_notification_rule(rule)

    def save_notification_rule(self, rule: NotificationRule) -> NotificationRule:
        rule.updated_at = utc_now()
        self._insert_model(
            "notification_rules",
            rule,
            project_id=rule.project_id,
            channel=rule.channel.value,
            event_type=rule.event_type,
            enabled=int(rule.enabled),
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )
        return rule

    def update_notification_rule(
        self, rule_id: str, payload: NotificationRuleUpdate
    ) -> NotificationRule:
        rule = self.get_notification_rule(rule_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(rule, key, value)
        return self.save_notification_rule(rule)

    def list_notification_rules(self) -> list[NotificationRule]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM notification_rules ORDER BY updated_at DESC"
            ).fetchall()
        return [self._load_model(row, NotificationRule) for row in rows]

    def get_notification_rule(self, rule_id: str) -> NotificationRule:
        rule = next((item for item in self.list_notification_rules() if item.id == rule_id), None)
        if rule is None:
            raise KeyError(rule_id)
        return rule

    def save_notification_event(self, event: NotificationEvent) -> NotificationEvent:
        self._insert_model(
            "notification_events",
            event,
            project_id=event.project_id,
            rule_id=event.rule_id,
            event_type=event.event_type,
            status=event.status.value,
            created_at=event.created_at,
        )
        return event

    def list_notification_events(self) -> list[NotificationEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM notification_events ORDER BY created_at DESC LIMIT 200"
            ).fetchall()
        return [self._load_model(row, NotificationEvent) for row in rows]

    # ---------------------------------------------------- Phase 11 intake

    def save_intake_event(self, event: IntakeEvent) -> IntakeEvent:
        self._insert_model(
            "intake_events",
            event,
            source=event.source.value,
            project_id=event.project_id,
            suggestion_id=event.suggestion_id,
            received_at=event.received_at,
        )
        return event

    def list_intake_events(self, limit: int = 200) -> list[IntakeEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM intake_events ORDER BY received_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._load_model(row, IntakeEvent) for row in rows]

    # --------------------------------------------- Phase 11 writer leases

    def acquire_writer_lease(
        self, name: str, holder: str, ttl_seconds: int
    ) -> WriterLeaseInfo | None:
        from datetime import datetime as _dt, timedelta as _td, timezone as _tz

        now = _dt.now(_tz.utc)
        expires_at = now + _td(seconds=ttl_seconds)
        with self.lock, self._connect() as conn:
            existing = conn.execute(
                "SELECT holder, expires_at FROM writer_leases WHERE name = ?",
                (name,),
            ).fetchone()
            if existing is not None:
                existing_expires = _dt.fromisoformat(existing["expires_at"])
                if existing_expires.tzinfo is None:
                    existing_expires = existing_expires.replace(tzinfo=_tz.utc)
                if existing_expires > now and existing["holder"] != holder:
                    return None
            conn.execute(
                "INSERT OR REPLACE INTO writer_leases (name, holder, acquired_at, expires_at) VALUES (?, ?, ?, ?)",
                (name, holder, now.isoformat(), expires_at.isoformat()),
            )
        return WriterLeaseInfo(
            name=name, holder=holder, acquired_at=now, expires_at=expires_at
        )

    def release_writer_lease(self, name: str, holder: str) -> bool:
        with self.lock, self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM writer_leases WHERE name = ? AND holder = ?",
                (name, holder),
            )
            return cur.rowcount > 0

    def get_writer_lease(self, name: str) -> WriterLeaseInfo | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT name, holder, acquired_at, expires_at FROM writer_leases WHERE name = ?",
                (name,),
            ).fetchone()
        if row is None:
            return None
        return WriterLeaseInfo(
            name=row["name"],
            holder=row["holder"],
            acquired_at=row["acquired_at"],
            expires_at=row["expires_at"],
        )

    # ---------------------------------------------- Phase 12 worker heartbeats

    def upsert_worker_heartbeat(self, heartbeat: WorkerHeartbeat) -> WorkerHeartbeat:
        with self.lock, self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM worker_heartbeats WHERE worker_name = ?",
                (heartbeat.worker_name,),
            ).fetchone()
            if existing is not None:
                heartbeat.id = existing["id"]
        self._insert_model(
            "worker_heartbeats",
            heartbeat,
            worker_name=heartbeat.worker_name,
            pid=heartbeat.pid,
            status=heartbeat.status.value,
            last_seen_at=heartbeat.last_seen_at,
        )
        return heartbeat

    def list_worker_heartbeats(self) -> list[WorkerHeartbeat]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM worker_heartbeats ORDER BY last_seen_at DESC"
            ).fetchall()
        return [self._load_model(row, WorkerHeartbeat) for row in rows]

    # ------------------------------------------------- Phase 12 backup policy

    def get_backup_policy(self) -> BackupPolicy:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM backup_policy WHERE id = 'default'"
            ).fetchone()
        if row is not None:
            return self._load_model(row, BackupPolicy)
        # Initialize default singleton lazily.
        policy = BackupPolicy()
        self._save_backup_policy(policy)
        return policy

    def _save_backup_policy(self, policy: BackupPolicy) -> BackupPolicy:
        policy.updated_at = utc_now()
        self._insert_model(
            "backup_policy",
            policy,
            enabled=int(policy.enabled),
            cadence=policy.cadence.value,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )
        return policy

    def update_backup_policy(self, payload: BackupPolicyUpdate) -> BackupPolicy:
        policy = self.get_backup_policy()
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(policy, key, value)
        return self._save_backup_policy(policy)

    def mark_backup_run(self, when=None) -> BackupPolicy:
        policy = self.get_backup_policy()
        policy.last_run_at = when or utc_now()
        return self._save_backup_policy(policy)

    # ---------------------------------------------- Phase 13 MCP audit (append-only)

    def append_mcp_audit(self, event: MCPAuditEvent) -> MCPAuditEvent:
        self._insert_model(
            "mcp_audit",
            event,
            session_id=event.session_id,
            tool_name=event.tool_name,
            project_id=event.project_id,
            action_type=event.action_type.value,
            blocked=int(event.blocked),
            readonly_mode=int(event.readonly_mode),
            created_at=event.created_at,
        )
        return event

    def list_mcp_audit(
        self,
        project_id: str | None = None,
        tool_name: str | None = None,
        limit: int = 200,
    ) -> list[MCPAuditEvent]:
        clauses: list[str] = []
        params: list = []
        if project_id is not None:
            clauses.append("project_id = ?")
            params.append(project_id)
        if tool_name is not None:
            clauses.append("tool_name = ?")
            params.append(tool_name)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT data FROM mcp_audit {where} ORDER BY created_at DESC LIMIT ?",
                params + [limit],
            ).fetchall()
        return [self._load_model(row, MCPAuditEvent) for row in rows]

    # --------------------------------------------------- Phase 13 cron jobs

    def save_cron_job(self, job: CronJob) -> CronJob:
        job.updated_at = utc_now()
        self._insert_model(
            "cron_jobs",
            job,
            name=job.name,
            job_type=job.job_type.value,
            cadence=job.cadence.value,
            enabled=int(job.enabled),
            project_id=job.project_id,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
        return job

    def create_cron_job(self, payload: CronJobCreate) -> CronJob:
        job = CronJob(**payload.model_dump())
        return self.save_cron_job(job)

    def list_cron_jobs(self) -> list[CronJob]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM cron_jobs ORDER BY enabled DESC, name ASC"
            ).fetchall()
        return [self._load_model(row, CronJob) for row in rows]

    def get_cron_job(self, job_id: str) -> CronJob:
        job = next((item for item in self.list_cron_jobs() if item.id == job_id), None)
        if job is None:
            raise KeyError(job_id)
        return job

    def update_cron_job(self, job_id: str, payload: CronJobUpdate) -> CronJob:
        job = self.get_cron_job(job_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(job, key, value)
        return self.save_cron_job(job)

    # -------------------------------------------- Phase 13 backup mirror events

    def append_backup_mirror_event(self, event: BackupMirrorEvent) -> BackupMirrorEvent:
        self._insert_model(
            "backup_mirror_events",
            event,
            snapshot_id=event.snapshot_id,
            sink=event.sink.value,
            status=event.status.value,
            created_at=event.created_at,
        )
        return event

    def list_backup_mirror_events(self, limit: int = 100) -> list[BackupMirrorEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM backup_mirror_events ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._load_model(row, BackupMirrorEvent) for row in rows]

    # ----------------------------------------------- Phase 13 health snapshots

    def append_health_snapshot(self, snapshot: HealthSnapshot) -> HealthSnapshot:
        self._insert_model(
            "health_snapshots",
            snapshot,
            status=snapshot.status.value,
            created_at=snapshot.created_at,
        )
        return snapshot

    def list_health_snapshots(self, limit: int = 1000) -> list[HealthSnapshot]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM health_snapshots ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._load_model(row, HealthSnapshot) for row in rows]

    # -------------------------------------------- Phase 13 resource changes

    def append_resource_change(self, event: ResourceChangeEvent) -> ResourceChangeEvent:
        self._insert_model(
            "resource_change_events",
            event,
            uri=event.uri,
            project_id=event.project_id,
            change_type=event.change_type.value,
            created_at=event.created_at,
        )
        return event

    def list_resource_changes(
        self, since: str | None = None, limit: int = 200
    ) -> list[ResourceChangeEvent]:
        with self._connect() as conn:
            if since:
                rows = conn.execute(
                    "SELECT data FROM resource_change_events WHERE created_at > ? ORDER BY created_at ASC LIMIT ?",
                    (since, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT data FROM resource_change_events ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [self._load_model(row, ResourceChangeEvent) for row in rows]

    # --------------------------------------------- Phase 14 MCP sessions

    def upsert_mcp_session(self, session: MCPSession) -> MCPSession:
        self._insert_model(
            "mcp_sessions",
            session,
            session_id=session.session_id,
            label=session.label,
            readonly=int(session.readonly),
            revoked=int(session.revoked),
            created_at=session.created_at,
            last_seen_at=session.last_seen_at,
        )
        return session

    def list_mcp_sessions(self) -> list[MCPSession]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM mcp_sessions ORDER BY last_seen_at DESC"
            ).fetchall()
        return [self._load_model(row, MCPSession) for row in rows]

    def get_mcp_session(self, session_id: str) -> MCPSession | None:
        return next(
            (s for s in self.list_mcp_sessions() if s.session_id == session_id),
            None,
        )

    def update_mcp_session(self, session_id: str, payload: MCPSessionUpdate) -> MCPSession:
        session = self.get_mcp_session(session_id)
        if session is None:
            raise KeyError(session_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(session, key, value)
        return self.upsert_mcp_session(session)

    # ----------------------------------------- Phase 14 retention policies

    def get_retention_policy(self, target: RetentionTarget) -> RetentionPolicy | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM retention_policies WHERE target = ?",
                (target.value,),
            ).fetchone()
        if row is None:
            return None
        return self._load_model(row, RetentionPolicy)

    def list_retention_policies(self) -> list[RetentionPolicy]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM retention_policies ORDER BY target ASC"
            ).fetchall()
        return [self._load_model(row, RetentionPolicy) for row in rows]

    def save_retention_policy(self, policy: RetentionPolicy) -> RetentionPolicy:
        policy.updated_at = utc_now()
        self._insert_model(
            "retention_policies",
            policy,
            target=policy.target.value,
            enabled=int(policy.enabled),
            days_to_keep=policy.days_to_keep,
            hard_delete_allowed=int(policy.hard_delete_allowed),
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )
        return policy

    def update_retention_policy(
        self, target: RetentionTarget, payload: RetentionPolicyUpdate
    ) -> RetentionPolicy:
        policy = self.get_retention_policy(target)
        if policy is None:
            raise KeyError(target.value)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(policy, key, value)
        return self.save_retention_policy(policy)

    _RETENTION_SQL: dict[str, tuple[str, str]] = {
        "health_snapshots": ("health_snapshots", "created_at"),
        "resource_changes": ("resource_change_events", "created_at"),
        "execution_logs": ("execution_logs", "created_at"),
        "mcp_audit": ("mcp_audit", "created_at"),
        "github_events": ("github_write_events", "created_at"),
        "intake_events": ("intake_events", "received_at"),
    }

    def delete_older_than(self, target: RetentionTarget, cutoff_iso: str) -> int:
        if target.value not in self._RETENTION_SQL:
            raise KeyError(target.value)
        table, column = self._RETENTION_SQL[target.value]
        with self.lock, self._connect() as conn:
            cur = conn.execute(
                f"DELETE FROM {table} WHERE {column} < ?", (cutoff_iso,)
            )
            return cur.rowcount

    # ----------------------------------------- Phase 14 health alert rules

    def save_health_alert_rule(self, rule: HealthAlertRule) -> HealthAlertRule:
        rule.updated_at = utc_now()
        self._insert_model(
            "health_alert_rules",
            rule,
            name=rule.name,
            condition_type=rule.condition_type.value,
            enabled=int(rule.enabled),
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )
        return rule

    def create_health_alert_rule(
        self, payload: HealthAlertRuleCreate
    ) -> HealthAlertRule:
        rule = HealthAlertRule(**payload.model_dump())
        return self.save_health_alert_rule(rule)

    def list_health_alert_rules(self) -> list[HealthAlertRule]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM health_alert_rules ORDER BY enabled DESC, name ASC"
            ).fetchall()
        return [self._load_model(row, HealthAlertRule) for row in rows]

    def get_health_alert_rule(self, rule_id: str) -> HealthAlertRule:
        rule = next(
            (r for r in self.list_health_alert_rules() if r.id == rule_id), None
        )
        if rule is None:
            raise KeyError(rule_id)
        return rule

    def update_health_alert_rule(
        self, rule_id: str, payload: HealthAlertRuleUpdate
    ) -> HealthAlertRule:
        rule = self.get_health_alert_rule(rule_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(rule, key, value)
        return self.save_health_alert_rule(rule)

    def export_project_bundle(self, project_id: str) -> dict:
        project = self.get_project(project_id)
        return {
            "project": project.model_dump(mode="json"),
            "memories": [item.model_dump(mode="json") for item in self.list_memories(project_id)],
            "decisions": [item.model_dump(mode="json") for item in self.list_decisions(project_id)],
            "outputs": [item.model_dump(mode="json") for item in self.list_outputs(project_id)],
            "tasks": [item.model_dump(mode="json") for item in self.list_tasks(project_id)],
            "risks": [item.model_dump(mode="json") for item in self.list_risks(project_id)],
            "logs": [item.model_dump(mode="json") for item in self.list_logs(project_id)],
            "prompts": [item.model_dump(mode="json") for item in self.list_prompt_templates(project_id, include_global=False)],
            "build_packets": [item.model_dump(mode="json") for item in self.list_build_packets(project_id)],
            "repositories": [item.model_dump(mode="json") for item in self.list_repositories(project_id)],
            "workflow_runs": [item.model_dump(mode="json") for item in self.list_workflows(project_id)],
            "branch_plans": [item.model_dump(mode="json") for item in self.list_branch_plans(project_id)],
            "pr_packets": [item.model_dump(mode="json") for item in self.list_pr_packets(project_id)],
            "code_reviews": [item.model_dump(mode="json") for item in self.list_code_reviews(project_id)],
            "test_runs": [item.model_dump(mode="json") for item in self.list_test_runs(project_id)],
            "weekly_briefs": [item.model_dump(mode="json") for item in self.list_outputs(project_id) if item.metadata.get("output_type") == "weekly_brief"],
        }

    def import_project_bundle(self, bundle: dict) -> Project:
        project = Project.model_validate(bundle["project"])
        existing_ids = {item.id for item in self.list_projects()}
        if project.id in existing_ids:
            project.id = f"{project.id}_imported"
            project.name = f"{project.name} Imported"
            project.updated_at = utc_now()
        self._insert_model("projects", project, status=project.status, created_at=project.created_at, updated_at=project.updated_at)
        remapped_project_id = project.id
        for raw in bundle.get("memories", []):
            item = Memory.model_validate({**raw, "project_id": remapped_project_id})
            self._insert_model("memories", item, project_id=item.project_id, created_at=item.created_at, updated_at=item.updated_at, pinned=int(item.pinned), source=item.source)
        for raw in bundle.get("decisions", []):
            item = Decision.model_validate({**raw, "project_id": remapped_project_id})
            self._insert_model("decisions", item, project_id=item.project_id, created_at=item.created_at, decision_type=item.decision_type.value, impact_level=item.impact_level.value)
        for raw in bundle.get("outputs", []):
            item = GeneratedOutput.model_validate({**raw, "project_id": remapped_project_id})
            self._insert_model("outputs", item, project_id=item.project_id, created_at=item.created_at, output_type=item.metadata.get("output_type"))
        for raw in bundle.get("tasks", []):
            item = Task.model_validate({**raw, "project_id": remapped_project_id})
            self._save_task(item)
        for raw in bundle.get("risks", []):
            item = Risk.model_validate({**raw, "project_id": remapped_project_id})
            self._save_risk(item)
        for raw in bundle.get("prompts", []):
            item = PromptTemplate.model_validate({**raw, "project_id": remapped_project_id})
            self.save_prompt_template(item)
        for raw in bundle.get("build_packets", []):
            item = BuildPacket.model_validate({**raw, "project_id": remapped_project_id})
            self.save_build_packet(item)
        for raw in bundle.get("repositories", []):
            item = Repository.model_validate({**raw, "project_id": remapped_project_id})
            self.save_repository(item)
        for raw in bundle.get("workflow_runs", []):
            item = WorkflowRun.model_validate({**raw, "project_id": remapped_project_id})
            self.save_workflow(item)
        for raw in bundle.get("branch_plans", []):
            item = BranchPlan.model_validate({**raw, "project_id": remapped_project_id})
            self.save_branch_plan(item)
        for raw in bundle.get("pr_packets", []):
            item = PRPacket.model_validate({**raw, "project_id": remapped_project_id})
            self.save_pr_packet(item)
        for raw in bundle.get("code_reviews", []):
            item = CodeReview.model_validate({**raw, "project_id": remapped_project_id})
            self.save_code_review(item)
        for raw in bundle.get("test_runs", []):
            item = TestRun.model_validate({**raw, "project_id": remapped_project_id})
            self.save_test_run(item)
        return project
