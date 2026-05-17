from __future__ import annotations

import re

from .memory_engine import LocalMemoryEngine
from .code_intelligence import CodeIntelligence
from .file_classifier import NOISE_TYPES
from .llm import LLMService
from .github_integration import GitHubIntegration
from .github_write_guard import GitHubWriteError, sanitise_branch_name
from .structured_outputs import StructuredCodeReviewOutput, validate_structured_output
from .models import (
    ApprovalRecommendation,
    BranchPlan,
    BranchPlanGenerateRequest,
    BuildSession,
    BuildSessionCreate,
    BuildSessionStatus,
    BuildSessionUpdate,
    CodeReview,
    CodeReviewCreate,
    DecisionCreate,
    GitHubBranchCreateRequest,
    GitHubDraftPRCreateRequest,
    GitHubIssueCreateRequest,
    GitHubSyncStatus,
    GitHubWriteAction,
    GitHubWriteEntityType,
    GitHubWriteEvent,
    GitHubWriteStatus,
    ImpactLevel,
    MemoryCreate,
    PRPacket,
    PRPacketGenerateRequest,
    Risk,
    Task,
    TaskCategory,
    TaskCreate,
    TaskPriority,
    TestRun,
    TestRunCreate,
)
from .repo_scanner import RepoScanner
from .sqlite_store import SQLiteStore


class RepoOperator:
    def __init__(
        self,
        store: SQLiteStore,
        memory_engine: LocalMemoryEngine,
        github: GitHubIntegration | None = None,
    ) -> None:
        self.store = store
        self.memory_engine = memory_engine
        self.scanner = RepoScanner()
        self.intelligence = CodeIntelligence()
        self.llm = LLMService()
        self.github = github or GitHubIntegration()

    def scan_repository(self, project_id: str, repository_id: str):
        repository = self.store.get_repository(project_id, repository_id)
        scan, files = self.scanner.scan(project_id, repository)
        self.store.save_repo_scan(scan)
        self.store.replace_repo_files(project_id, repository_id, files)
        root = self.scanner.resolve_root(repository)
        symbols = []
        dependencies = []
        for repo_file in files:
            file_symbols, file_deps = self.intelligence.analyze(root, repo_file)
            symbols.extend(file_symbols)
            dependencies.extend(file_deps)
        self.store.replace_code_intelligence(project_id, repository_id, symbols, dependencies)
        scan.summary = self._enriched_scan_summary(scan.summary, symbols, dependencies)
        scan.risks.extend(self._dependency_risks(dependencies))
        self.store.save_repo_scan(scan)
        return scan

    def _enriched_scan_summary(self, base: str, symbols, dependencies) -> str:
        counts: dict[str, int] = {}
        for symbol in symbols:
            counts[symbol.symbol_type] = counts.get(symbol.symbol_type, 0) + 1
        components = counts.get("component", 0) + counts.get("react_component", 0)
        routes = counts.get("route", 0) + counts.get("route_handler", 0) + counts.get("api_endpoint", 0)
        services = counts.get("class", 0) + counts.get("export", 0)
        functions = counts.get("function", 0)
        return (
            f"{base} Symbols: functions={functions}, classes={counts.get('class', 0)}, "
            f"components={components}, routes/api={routes}, services/exports={services}. "
            f"Dependencies indexed: {len(dependencies)}."
        )

    def index_repo_to_memory(self, project_id: str, repository_id: str):
        scans = self.store.list_repo_scans(project_id, repository_id)
        if not scans:
            self.scan_repository(project_id, repository_id)
            scans = self.store.list_repo_scans(project_id, repository_id)
        scan = scans[0]
        files = self.store.list_repo_files(project_id, repository_id)
        entries = [
            ("Repo scan summary", scan.summary),
            ("Repo architecture facts", f"Tech stack: {', '.join(scan.tech_stack)}\nFrameworks: {', '.join(scan.frameworks)}\nRoutes: {', '.join(scan.routes[:30])}"),
            ("Repo key file map", "\n".join(f"- {f.path}: {f.role.value} {f.summary}" for f in files[:80])),
            ("Repo commands", f"Tests: {', '.join(scan.test_commands) or 'none detected'}\nBuild: {', '.join(scan.build_commands) or 'none detected'}\nLint: {', '.join(scan.lint_commands) or 'none detected'}"),
        ]
        created = []
        for title, content in entries:
            memory = self.store.create_memory(project_id, MemoryCreate(title=title, content=content, tags=["repo-context"], pinned=False, source="repo_scan"))
            self.memory_engine.index_memory(memory)
            created.append(memory)
        return created

    def generate_branch_plan(self, project_id: str, request: BranchPlanGenerateRequest) -> BranchPlan:
        repository = self.store.get_repository(project_id, request.repository_id)
        scans = self.store.list_repo_scans(project_id, request.repository_id)
        scan = scans[0] if scans else self.scan_repository(project_id, request.repository_id)
        task = next((item for item in self.store.list_tasks(project_id) if item.id == request.task_id), None)
        packet = self.store.get_build_packet(project_id, request.build_packet_id) if request.build_packet_id else None
        objective = request.objective or (task.title if task else packet.title if packet else "repo-aware-change")
        files = self._candidate_files(project_id, request.repository_id, objective)
        branch = BranchPlan(
            project_id=project_id,
            repository_id=request.repository_id,
            task_id=request.task_id,
            build_packet_id=request.build_packet_id,
            branch_name=f"cto/{self._slug(objective)}",
            objective=objective,
            files_to_inspect=[file.path for file in files[:12]],
            files_to_change=[file.path for file in files[:6]],
            implementation_steps=[
                "Create the branch manually if needed; CTO OS does not execute git writes.",
                "Inspect the listed files and confirm scope.",
                "Apply the minimal implementation for the task/build packet.",
                "Run the detected test/build commands.",
                "Paste the diff into Code Reviews for internal review.",
            ],
            test_commands=scan.test_commands or ["Add or run the narrowest relevant test command."],
            risk_notes=scan.risks or ["No scanner risks detected."],
            rollback_plan="Discard or revert only the files changed for this branch plan. Do not reset unrelated work.",
        )
        return self.store.save_branch_plan(branch)

    def generate_pr_packet(self, project_id: str, request: PRPacketGenerateRequest) -> PRPacket:
        branch_plan = self.store.get_branch_plan(project_id, request.branch_plan_id) if request.branch_plan_id else None
        task = next((item for item in self.store.list_tasks(project_id) if item.id == request.task_id), None)
        title = request.title or (branch_plan.objective if branch_plan else task.title if task else "Repo-aware implementation")
        packet = PRPacket(
            project_id=project_id,
            repository_id=request.repository_id,
            branch_plan_id=request.branch_plan_id,
            task_id=request.task_id,
            title=title,
            summary=f"PR handoff for {title}.",
            changes_expected=(branch_plan.files_to_change if branch_plan else []),
            test_plan=(branch_plan.test_commands if branch_plan else ["Run relevant tests before review."]),
            acceptance_checklist=(task.acceptance_criteria if task else ["Implementation matches the branch plan.", "Tests/checks are recorded.", "No secrets or env files are included."]),
            reviewer_notes="Review for scope control, project memory alignment, and regression risk.",
            risk_notes=(branch_plan.risk_notes if branch_plan else []),
        )
        return self.store.save_pr_packet(packet)

    def review_diff(self, project_id: str, request: CodeReviewCreate) -> CodeReview:
        diff = request.diff_text
        findings: list[str] = []
        risk = "low"
        recommendation = ApprovalRecommendation.approve
        if re.search(r"(^|\n)[+-].*(password|secret|api[_-]?key|token)", diff, flags=re.IGNORECASE):
            findings.append("Potential secret-like value appears in the diff.")
            risk = "high"
            recommendation = ApprovalRecommendation.block
        if len(diff) > 20_000:
            findings.append("Large diff; split or request deeper review before merge.")
            risk = "medium"
            recommendation = ApprovalRecommendation.revise
        if "TODO" in diff or "FIXME" in diff:
            findings.append("Diff includes TODO/FIXME markers that may need resolution.")
            if recommendation == ApprovalRecommendation.approve:
                recommendation = ApprovalRecommendation.revise
        if not findings:
            findings.append("No obvious high-risk pattern detected by deterministic review.")

        structured = self._structured_llm_review(project_id, request, findings)
        review_summary = f"Deterministic diff review found {len(findings)} finding(s)."
        test_recommendations = [
            "Run commands from the linked branch plan or repository scan.",
            "Add targeted tests for modified behavior.",
        ]
        if structured is not None:
            if structured.recommendation in {"approve", "revise", "block"}:
                llm_rec = ApprovalRecommendation(structured.recommendation)
                # An LLM "block" or "revise" can only escalate; never de-escalate
                # past a deterministic security finding.
                ordering = {
                    ApprovalRecommendation.approve: 0,
                    ApprovalRecommendation.revise: 1,
                    ApprovalRecommendation.block: 2,
                }
                if ordering[llm_rec] > ordering[recommendation]:
                    recommendation = llm_rec
                    risk = "high" if llm_rec == ApprovalRecommendation.block else (
                        "medium" if llm_rec == ApprovalRecommendation.revise else risk
                    )
            if structured.blocking_issues:
                findings.extend(f"Blocking: {item}" for item in structured.blocking_issues)
            if structured.security_concerns:
                findings.extend(f"Security: {item}" for item in structured.security_concerns)
                risk = "high"
            if structured.non_blocking_suggestions:
                findings.extend(f"Suggestion: {item}" for item in structured.non_blocking_suggestions)
            if structured.summary:
                review_summary = structured.summary[:600]
            if structured.missing_tests:
                test_recommendations.extend(structured.missing_tests)

        follow_up_ids: list[str] = []
        if request.create_follow_up_tasks and recommendation != ApprovalRecommendation.approve:
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
            diff_text=diff,
            review_summary=review_summary,
            findings=findings,
            risk_level=risk,
            test_recommendations=test_recommendations,
            approval_recommendation=recommendation,
            follow_up_task_ids=follow_up_ids,
        )
        return self.store.save_code_review(review)

    def record_test_run(self, project_id: str, payload: TestRunCreate) -> TestRun:
        self.store.get_repository(project_id, payload.repository_id)
        return self.store.save_test_run(TestRun(project_id=project_id, **payload.model_dump()))

    def summarize_build_session(self, project_id: str, session_id: str) -> BuildSession:
        session = next((item for item in self.store.list_build_sessions(project_id) if item.id == session_id), None)
        if session is None:
            raise KeyError(session_id)
        reviews = [review for review in self.store.list_code_reviews(project_id) if review.id in session.linked_code_review_ids]
        tests = [run for run in self.store.list_test_runs(project_id) if run.id in session.linked_test_run_ids]
        impl_reviews = [
            review
            for review in self.store.list_reviews(project_id)
            if review.id in session.linked_implementation_review_ids
        ]
        branch = None
        if session.linked_branch_plan_id:
            try:
                branch = self.store.get_branch_plan(project_id, session.linked_branch_plan_id)
            except KeyError:
                branch = None
        packet = None
        if session.linked_build_packet_id:
            try:
                packet = self.store.get_build_packet(project_id, session.linked_build_packet_id)
            except KeyError:
                packet = None
        pr_packet = None
        if session.linked_pr_packet_id:
            pr_packet = next(
                (item for item in self.store.list_pr_packets(project_id) if item.id == session.linked_pr_packet_id),
                None,
            )
        failing = len([run for run in tests if run.status.value == "failed"])
        blocked_reviews = len([r for r in reviews if r.approval_recommendation.value == "block"])
        session.summary = "\n".join(
            [
                f"Status: {session.status.value}",
                f"Branch plan: {branch.branch_name if branch else 'none'}",
                f"Build packet: {packet.title if packet else 'none'}",
                f"PR packet: {pr_packet.title if pr_packet else 'none'}",
                f"Code reviews: {len(reviews)} (blocking: {blocked_reviews})",
                f"Test runs: {len(tests)} (failing: {failing})",
                f"Implementation reviews: {len(impl_reviews)}",
                f"Lessons: {session.lessons_learned or 'No lessons recorded yet.'}",
            ]
        )
        return self.store.save_build_session(session)

    def save_build_session_lessons(self, project_id: str, session_id: str):
        session = next((item for item in self.store.list_build_sessions(project_id) if item.id == session_id), None)
        if session is None:
            raise KeyError(session_id)
        content = session.lessons_learned or session.summary or session.title
        memory = self.store.create_memory(
            project_id,
            MemoryCreate(
                title=f"Build session lesson: {session.title}",
                content=content,
                tags=["build-session", "lesson"],
                pinned=False,
                source="build_session",
            ),
        )
        self.memory_engine.index_memory(memory)
        decision = self.store.create_decision(
            project_id,
            DecisionCreate(
                title=f"Recorded lesson from {session.title}",
                context=session.summary or "",
                decision=content[:600],
                rationale="Captured automatically when build session lessons were saved.",
                impact_level=ImpactLevel.low,
            ),
        )
        if session.task_id and session.status == BuildSessionStatus.completed:
            self.store.create_task(
                project_id,
                TaskCreate(
                    title=f"Follow up from {session.title}",
                    description="Review saved build-session lesson and update architecture/brief if needed.",
                    priority=TaskPriority.medium,
                    category=TaskCategory.ops,
                    linked_decision_ids=[decision.id],
                    linked_memory_ids=[memory.id],
                ),
            )
        return [memory]

    # Tokens that should never count as scoring terms; otherwise "add"/"to"
    # noise causes irrelevant files to outrank real matches.
    _CANDIDATE_STOPWORDS = {
        "add", "the", "and", "for", "from", "with", "into", "this", "that",
        "to", "of", "on", "in", "is", "a", "an", "be", "do", "or",
    }

    # Root config files we surface when nothing scores. Better than the old
    # alphabetical files[:12] which kept recommending ios/Pods/boost headers.
    _FALLBACK_CONFIG_NAMES = {
        ".gitignore", "package.json", "tsconfig.json", "pyproject.toml",
        "requirements.txt", "README.md", "next.config.js", "app.json",
        "vercel.json", "firebase.json",
    }

    _FILENAME_HINT_RE = re.compile(r"[\w][\w.\-/]*\.[A-Za-z0-9]{1,8}")

    def _extract_filename_hints(self, objective: str) -> set[str]:
        """Find tokens that look like filenames in the task text.

        ``.gitignore`` and similar dotfiles aren't matched by the suffix
        regex, so accept any whitespace-separated token that starts with a
        dot and has more than one character.
        """
        hints: set[str] = set()
        for match in self._FILENAME_HINT_RE.findall(objective):
            hints.add(match.lower())
        for token in objective.split():
            stripped = token.strip(".,;:`\"'()[]{}").lower()
            if stripped.startswith(".") and len(stripped) > 1:
                hints.add(stripped)
        return hints

    def _candidate_files(self, project_id: str, repository_id: str, objective: str):
        objective_lower = objective.lower()
        terms = {
            term
            for term in re.split(r"[^a-zA-Z0-9_]+", objective_lower)
            if len(term) >= 2 and term not in self._CANDIDATE_STOPWORDS
        }
        hints = self._extract_filename_hints(objective_lower)
        files = self.store.list_repo_files(project_id, repository_id)
        scored: list[tuple[int, object]] = []
        for file in files:
            path_lower = file.path.lower()
            name_lower = path_lower.rsplit("/", 1)[-1]
            name_stem = name_lower.rsplit(".", 1)[0]
            # Phase 16.5: skip noise unless the operator explicitly named
            # the file (filename hint match). Without this, lockfiles +
            # generated stubs + vendored deps win on common task wording
            # ("update dependencies", "regenerate types").
            if file.semantic_type in NOISE_TYPES and not self._noise_hinted(
                hints, path_lower, name_lower
            ):
                continue
            haystack = f"{path_lower} {file.summary.lower()} {file.role.value}"
            score = sum(1 for term in terms if term in haystack)
            # A term that matches the basename (with or without extension) is
            # almost always more relevant than a generic substring or role bonus.
            score += 3 * sum(
                1 for term in terms if term == name_lower or term == name_stem
            )
            # Strong boost for literal filename mentions.
            for hint in hints:
                if hint == name_lower or hint == path_lower or path_lower.endswith("/" + hint):
                    score += 10
                elif hint and hint in path_lower:
                    score += 4
            if file.role.value in {"route", "component", "service", "model", "test"}:
                score += 1
            scored.append((score, file))
        scored.sort(key=lambda item: (item[0], item[1].path), reverse=True)
        matched = [file for score, file in scored if score > 0]
        if matched:
            return matched
        # Fallback: surface scan-detected key files + root config files,
        # NOT the alphabetical first dozen (which on a mobile repo was Pods).
        scan = next(iter(self.store.list_repo_scans(project_id, repository_id)), None)
        result: list = []
        seen: set[str] = set()
        if scan is not None:
            for path in scan.key_files:
                if path not in seen:
                    seen.add(path)
            for file in files:
                if file.path in seen and file.semantic_type not in NOISE_TYPES:
                    result.append(file)
        for file in files:
            if file.path in seen:
                continue
            if file.semantic_type in NOISE_TYPES:
                continue
            name = file.path.rsplit("/", 1)[-1]
            if name in self._FALLBACK_CONFIG_NAMES and "/" not in file.path:
                result.append(file)
                seen.add(file.path)
        non_noise = [f for f in files if f.semantic_type not in NOISE_TYPES]
        return result[:12] or non_noise[:12]

    @staticmethod
    def _noise_hinted(hints: set[str], path_lower: str, name_lower: str) -> bool:
        """Did the operator explicitly name a noise file?

        Used to decide whether to surface lockfiles / generated / vendored
        files in the candidate list. Keeps "update package-lock.json"
        working while still suppressing lockfiles from "fix the bug".
        """
        for hint in hints:
            if not hint:
                continue
            if hint == name_lower or hint == path_lower:
                return True
            if path_lower.endswith("/" + hint):
                return True
        return False

    _SLUG_STOPWORDS = {
        "to", "the", "and", "from", "for", "with", "of", "a", "an", "in", "on",
    }

    def _slug(self, value: str) -> str:
        words = re.split(r"[^a-zA-Z0-9]+", value.lower())
        kept = [w for w in words if w and w not in self._SLUG_STOPWORDS]
        slug = "-".join(kept).strip("-")
        return slug[:40] or "change"

    def _dependency_risks(self, dependencies) -> list[str]:
        risky = sorted({dep.dependency for dep in dependencies if dep.dependency in {"eval", "child_process", "subprocess", "pickle"}})
        return [f"Dependency risk: {item}" for item in risky]

    def _structured_llm_review(
        self,
        project_id: str,
        request: CodeReviewCreate,
        findings: list[str],
    ) -> StructuredCodeReviewOutput | None:
        """Call the LLM and parse it through ``StructuredCodeReviewOutput``.

        Returns ``None`` when no usable structured response was produced
        (deterministic provider, parse error, schema mismatch). Caller falls
        back to deterministic findings alone in that case.
        """
        task = next(
            (item for item in self.store.list_tasks(project_id) if item.id == request.task_id),
            None,
        )
        branch = (
            self.store.get_branch_plan(project_id, request.branch_plan_id)
            if request.branch_plan_id
            else None
        )
        memories = self.memory_engine.search(
            project_id, task.title if task else "code review", limit=4
        )
        decisions = self.store.list_decisions(project_id)[:5]
        prompt = (
            "Review this diff for an internal CTO OS. Return ONLY a JSON object "
            "matching this schema:\n"
            "{ \"recommendation\": \"approve|revise|block\", \"summary\": string, "
            "\"blocking_issues\": string[], \"non_blocking_suggestions\": string[], "
            "\"missing_tests\": string[], \"security_concerns\": string[], "
            "\"acceptance_criteria_check\": string, \"confidence\": number }\n\n"
            f"Task: {task.title if task else 'none'}\n"
            f"Branch plan: {branch.objective if branch else 'none'}\n"
            f"Existing deterministic findings: {findings}\n"
            f"Relevant memory: {[memory.title for memory in memories]}\n"
            f"Decisions: {[decision.title for decision in decisions]}\n\n"
            f"Diff:\n{request.diff_text[:12000]}\n"
        )
        result = self.llm.generate(
            "You are a careful senior code reviewer. Reply with JSON only.",
            prompt,
            {"project_id": project_id},
        )
        if result.get("fallback") or result.get("provider") == "deterministic":
            return None
        validated = validate_structured_output(StructuredCodeReviewOutput, result.text)
        if not validated.valid:
            return None
        return StructuredCodeReviewOutput.model_validate(validated.data)

    # ---------------------------------------------------------- Phase 7 writes

    # -- Issue from task -------------------------------------------------------

    def preview_task_issue(self, project_id: str, task_id: str) -> GitHubWriteEvent:
        task = self.store.get_task(project_id, task_id)
        payload = self._task_issue_payload(project_id, task)
        return self._record_event(
            project_id=project_id,
            repository_id=None,
            entity_type=GitHubWriteEntityType.task,
            entity_id=task.id,
            action=GitHubWriteAction.preview_issue,
            payload=payload,
            status=GitHubWriteStatus.previewed,
            dry_run=True,
            approved=False,
        )

    def create_task_issue(
        self,
        project_id: str,
        task_id: str,
        request: GitHubIssueCreateRequest,
    ) -> GitHubWriteEvent:
        task = self.store.get_task(project_id, task_id)
        payload = self._task_issue_payload(project_id, task)
        if request.labels:
            payload["labels"] = sorted(set(payload.get("labels", []) + request.labels))
        repository = self._repository_for_task(project_id, task)
        return self._execute_write(
            project_id=project_id,
            repository=repository,
            entity_type=GitHubWriteEntityType.task,
            entity_id=task.id,
            action=GitHubWriteAction.create_issue,
            payload=payload,
            request_dry_run=request.dry_run,
            request_approved=request.approved,
            build_session_id=request.build_session_id,
            on_success=lambda response: self._apply_issue_response(task, response),
        )

    # -- Issue from risk -------------------------------------------------------

    def preview_risk_issue(self, project_id: str, risk_id: str) -> GitHubWriteEvent:
        risk = self.store.get_risk(project_id, risk_id)
        payload = self._risk_issue_payload(project_id, risk)
        return self._record_event(
            project_id=project_id,
            repository_id=None,
            entity_type=GitHubWriteEntityType.risk,
            entity_id=risk.id,
            action=GitHubWriteAction.preview_issue,
            payload=payload,
            status=GitHubWriteStatus.previewed,
            dry_run=True,
            approved=False,
        )

    def create_risk_issue(
        self,
        project_id: str,
        risk_id: str,
        request: GitHubIssueCreateRequest,
    ) -> GitHubWriteEvent:
        risk = self.store.get_risk(project_id, risk_id)
        payload = self._risk_issue_payload(project_id, risk)
        if request.labels:
            payload["labels"] = sorted(set(payload.get("labels", []) + request.labels))
        repository = self._first_repository(project_id)
        return self._execute_write(
            project_id=project_id,
            repository=repository,
            entity_type=GitHubWriteEntityType.risk,
            entity_id=risk.id,
            action=GitHubWriteAction.create_issue,
            payload=payload,
            request_dry_run=request.dry_run,
            request_approved=request.approved,
            build_session_id=request.build_session_id,
            on_success=lambda response: self._apply_risk_response(risk, response),
        )

    # -- Branch from branch plan ----------------------------------------------

    def preview_branch(
        self,
        project_id: str,
        branch_plan_id: str,
        request: GitHubBranchCreateRequest | None = None,
    ) -> GitHubWriteEvent:
        plan = self.store.get_branch_plan(project_id, branch_plan_id)
        repository = self.store.get_repository(project_id, plan.repository_id)
        payload = self._branch_payload(plan, repository, request)
        return self._record_event(
            project_id=project_id,
            repository_id=repository.id,
            entity_type=GitHubWriteEntityType.branch_plan,
            entity_id=plan.id,
            action=GitHubWriteAction.preview_branch,
            payload=payload,
            status=GitHubWriteStatus.previewed,
            dry_run=True,
            approved=False,
        )

    def create_branch(
        self,
        project_id: str,
        branch_plan_id: str,
        request: GitHubBranchCreateRequest,
    ) -> GitHubWriteEvent:
        plan = self.store.get_branch_plan(project_id, branch_plan_id)
        repository = self.store.get_repository(project_id, plan.repository_id)
        payload = self._branch_payload(plan, repository, request)

        def do_call() -> dict:
            return self.github.create_branch(
                repository=repository,
                branch_name=payload["branch_name"],
                base_branch=payload["base_branch"],
                approved=request.approved,
                dry_run=request.dry_run,
            )

        return self._execute_write(
            project_id=project_id,
            repository=repository,
            entity_type=GitHubWriteEntityType.branch_plan,
            entity_id=plan.id,
            action=GitHubWriteAction.create_branch,
            payload=payload,
            request_dry_run=request.dry_run,
            request_approved=request.approved,
            build_session_id=request.build_session_id,
            call=do_call,
            on_success=lambda response: self._apply_branch_response(
                plan, repository, payload["branch_name"], response
            ),
        )

    # -- Draft PR from PR packet ----------------------------------------------

    def preview_draft_pr(
        self,
        project_id: str,
        pr_packet_id: str,
        request: GitHubDraftPRCreateRequest | None = None,
    ) -> GitHubWriteEvent:
        packet = self.store.get_pr_packet(project_id, pr_packet_id)
        repository = self.store.get_repository(project_id, packet.repository_id)
        payload = self._pr_payload(project_id, packet, repository, request)
        return self._record_event(
            project_id=project_id,
            repository_id=repository.id,
            entity_type=GitHubWriteEntityType.pr_packet,
            entity_id=packet.id,
            action=GitHubWriteAction.preview_draft_pr,
            payload=payload,
            status=GitHubWriteStatus.previewed,
            dry_run=True,
            approved=False,
        )

    def create_draft_pr(
        self,
        project_id: str,
        pr_packet_id: str,
        request: GitHubDraftPRCreateRequest,
    ) -> GitHubWriteEvent:
        packet = self.store.get_pr_packet(project_id, pr_packet_id)
        repository = self.store.get_repository(project_id, packet.repository_id)
        payload = self._pr_payload(project_id, packet, repository, request)

        def do_call() -> dict:
            return self.github.create_draft_pr(
                repository=repository,
                head_branch=payload["head"],
                base_branch=payload["base"],
                title=payload["title"],
                body=payload["body"],
                approved=request.approved,
                dry_run=request.dry_run,
                reviewers=request.reviewers,
            )

        return self._execute_write(
            project_id=project_id,
            repository=repository,
            entity_type=GitHubWriteEntityType.pr_packet,
            entity_id=packet.id,
            action=GitHubWriteAction.create_draft_pr,
            payload=payload,
            request_dry_run=request.dry_run,
            request_approved=request.approved,
            build_session_id=request.build_session_id,
            call=do_call,
            on_success=lambda response: self._apply_pr_response(packet, response),
        )

    # -- Payload builders ------------------------------------------------------

    def _task_issue_payload(self, project_id: str, task: Task) -> dict:
        memories = self.memory_engine.search(project_id, task.title or task.description, limit=4)
        decisions = self.store.list_decisions(project_id)[:3]
        risks = self.store.list_risks(project_id)[:3]
        criteria_lines = [f"- [ ] {item}" for item in task.acceptance_criteria] or ["- [ ] (none listed)"]
        lines = [
            "## Goal",
            task.description or task.title,
            "",
            "## Acceptance Criteria",
            *criteria_lines,
            "",
            f"**Priority:** {task.priority.value}  ·  **Category:** {task.category.value}  ·  **Status:** {task.status.value}",
        ]
        if memories:
            lines += ["", "## Linked Project Memory", *(f"- {m.title}" for m in memories)]
        if decisions:
            lines += ["", "## Recent Decisions", *(f"- {d.title}" for d in decisions)]
        if risks:
            lines += ["", "## Open Risks", *(f"- {r.title} ({r.severity.value})" for r in risks)]
        lines += ["", "---", f"_Generated by CTO OS · task {task.id}_"]
        return {
            "title": task.title,
            "body": "\n".join(lines),
            "labels": ["cto-os", task.category.value],
        }

    def _risk_issue_payload(self, project_id: str, risk: Risk) -> dict:
        memories = self.memory_engine.search(project_id, risk.title, limit=3)
        lines = [
            "## Risk",
            risk.title,
            "",
            f"**Category:** {risk.category.value}  ·  **Severity:** {risk.severity.value}  ·  **Likelihood:** {risk.likelihood.value}",
            "",
            "## Evidence",
            risk.evidence or "(none provided)",
            "",
            "## Recommendation",
            risk.recommendation or "(none provided)",
        ]
        if memories:
            lines += ["", "## Linked Project Memory", *(f"- {m.title}" for m in memories)]
        lines += ["", "---", f"_Generated by CTO OS · risk {risk.id}_"]
        return {
            "title": f"[risk] {risk.title}",
            "body": "\n".join(lines),
            "labels": ["cto-os", "risk", risk.category.value, risk.severity.value],
        }

    def _branch_payload(
        self,
        plan,
        repository,
        request: GitHubBranchCreateRequest | None,
    ) -> dict:
        requested_name = request.branch_name if request and request.branch_name else plan.branch_name
        base_branch = request.base_branch if request and request.base_branch else repository.default_branch or "main"
        return {
            "branch_name": sanitise_branch_name(requested_name, fallback=plan.branch_name or "cto-change"),
            "base_branch": base_branch,
            "branch_plan_id": plan.id,
            "objective": plan.objective,
        }

    def _pr_payload(
        self,
        project_id: str,
        packet,
        repository,
        request: GitHubDraftPRCreateRequest | None,
    ) -> dict:
        branch_plan = (
            self.store.get_branch_plan(project_id, packet.branch_plan_id)
            if packet.branch_plan_id
            else None
        )
        head = (
            request.head_branch
            if request and request.head_branch
            else (branch_plan.github_branch_name or branch_plan.branch_name if branch_plan else "")
        )
        base = request.base_branch if request and request.base_branch else repository.default_branch or "main"
        task = (
            self.store.get_task(project_id, packet.task_id) if packet.task_id else None
        )
        memories = self.memory_engine.search(project_id, packet.title, limit=4)

        body_lines = [
            f"## Summary",
            packet.summary or packet.title,
            "",
            "## Acceptance Checklist",
            *(f"- [ ] {item}" for item in (packet.acceptance_checklist or ["(none listed)"])),
            "",
            "## Test Plan",
            *(f"- {item}" for item in (packet.test_plan or ["(none listed)"])),
        ]
        if packet.risk_notes:
            body_lines += ["", "## Risk Notes", *(f"- {item}" for item in packet.risk_notes)]
        if task:
            body_lines += ["", "## Linked Task", f"- {task.title}"]
        if memories:
            body_lines += ["", "## Linked Memory", *(f"- {m.title}" for m in memories)]
        body_lines += ["", "---", f"_Generated by CTO OS · pr_packet {packet.id} · draft only_"]

        return {
            "title": packet.title,
            "body": "\n".join(body_lines),
            "head": head,
            "base": base,
            "draft": True,
            "reviewers": (request.reviewers if request else []),
            "pr_packet_id": packet.id,
        }

    # -- Execution + persistence ----------------------------------------------

    def _execute_write(
        self,
        *,
        project_id: str,
        repository,
        entity_type: GitHubWriteEntityType,
        entity_id: str,
        action: GitHubWriteAction,
        payload: dict,
        request_dry_run: bool,
        request_approved: bool,
        build_session_id: str | None,
        call=None,
        on_success=None,
    ) -> GitHubWriteEvent:
        dry_run = bool(request_dry_run)
        approved = bool(request_approved)
        response: dict = {}
        status = GitHubWriteStatus.completed
        error_message = ""
        try:
            if call is None:
                # Default to create_issue on the integration.
                def call() -> dict:
                    return self.github.create_issue(
                        repository=repository,
                        payload={"title": payload["title"], "body": payload["body"], "labels": payload.get("labels", [])},
                        approved=approved,
                        dry_run=dry_run,
                    )
            response = call()
            if on_success is not None:
                on_success(response)
        except GitHubWriteError as exc:
            status = GitHubWriteStatus.blocked
            error_message = str(exc)
        except Exception as exc:  # network, GitHub API errors
            status = GitHubWriteStatus.failed
            error_message = str(exc)

        event = self._record_event(
            project_id=project_id,
            repository_id=repository.id if repository else None,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            payload=payload,
            status=status,
            dry_run=dry_run,
            approved=approved,
            response=response,
            error_message=error_message,
            build_session_id=build_session_id,
        )
        if build_session_id:
            self.store.attach_github_event_to_session(project_id, build_session_id, event.id)
        return event

    def _record_event(
        self,
        *,
        project_id: str,
        repository_id: str | None,
        entity_type: GitHubWriteEntityType,
        entity_id: str,
        action: GitHubWriteAction,
        payload: dict,
        status: GitHubWriteStatus,
        dry_run: bool,
        approved: bool,
        response: dict | None = None,
        error_message: str = "",
        build_session_id: str | None = None,
    ) -> GitHubWriteEvent:
        event = GitHubWriteEvent(
            project_id=project_id,
            repository_id=repository_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            dry_run=dry_run,
            approved=approved,
            payload_json=payload,
            response_json=response or {},
            status=status,
            error_message=error_message,
            build_session_id=build_session_id,
        )
        return self.store.save_github_write_event(event)

    # -- Response application -------------------------------------------------

    def _apply_issue_response(self, task: Task, response: dict) -> None:
        number = response.get("number")
        url = response.get("html_url", "")
        if number is not None:
            task.github_issue_number = int(number)
        if url:
            task.github_issue_url = url
        task.github_sync_status = GitHubSyncStatus.completed if number else GitHubSyncStatus.failed
        self.store.save_task(task)

    def _apply_risk_response(self, risk: Risk, response: dict) -> None:
        number = response.get("number")
        url = response.get("html_url", "")
        if number is not None:
            risk.github_issue_number = int(number)
        if url:
            risk.github_issue_url = url
        risk.github_sync_status = GitHubSyncStatus.completed if number else GitHubSyncStatus.failed
        self.store.save_risk(risk)

    def _apply_branch_response(
        self, plan, repository, branch_name: str, response: dict
    ) -> None:
        plan.github_branch_name = branch_name
        ref = response.get("ref", "")
        if ref:
            owner = repository.url.rstrip("/").split("/")[-2] if repository.url else ""
            repo_name = (
                repository.url.rstrip("/").split("/")[-1].removesuffix(".git")
                if repository.url
                else repository.name
            )
            if owner:
                plan.github_branch_url = (
                    f"https://github.com/{owner}/{repo_name}/tree/{branch_name}"
                )
        plan.github_sync_status = GitHubSyncStatus.completed
        self.store.save_branch_plan(plan)

    def _apply_pr_response(self, packet, response: dict) -> None:
        number = response.get("number")
        url = response.get("html_url", "")
        if number is not None:
            packet.github_pr_number = int(number)
        if url:
            packet.github_pr_url = url
        packet.github_sync_status = GitHubSyncStatus.completed if number else GitHubSyncStatus.failed
        self.store.save_pr_packet(packet)

    # -- Repository lookup helpers --------------------------------------------

    def _repository_for_task(self, project_id: str, task: Task):
        for plan in self.store.list_branch_plans(project_id):
            if plan.task_id == task.id:
                try:
                    return self.store.get_repository(project_id, plan.repository_id)
                except KeyError:
                    continue
        return self._first_repository(project_id)

    def _first_repository(self, project_id: str):
        repos = self.store.list_repositories(project_id)
        if not repos:
            raise KeyError("No repository configured for this project; add one first.")
        return repos[0]
