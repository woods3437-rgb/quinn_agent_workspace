"""Phase 8 — GitHub state reconciliation.

Pulls fresh state from GitHub for entities the CTO OS already tracks
(`Task.github_issue_number`, `Risk.github_issue_number`,
`PRPacket.github_pr_number`) and produces:

- ``GitHubReconciliationEvent`` rows describing the observed state change
- ``StatusSuggestion`` rows the user must apply or dismiss

By default the only mutation is creating these two record types — entity
status is **not** changed. Setting ``auto_reconcile=True`` in the request
AND ``CTO_OS_ALLOW_AUTO_RECONCILE=1`` in the environment opens the door
to applying suggestions automatically.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from .github_integration import GitHubIntegration, _parse_iso
from .models import (
    BuildSession,
    BuildSessionStatus,
    GitHubReconciliationEvent,
    PRPacket,
    ReconcileRequest,
    ReconciliationEntityType,
    ReconciliationReport,
    Repository,
    Risk,
    RiskStatus,
    StatusSuggestion,
    StatusSuggestionEntityType,
    Task,
    TaskStatus,
)
from .sqlite_store import SQLiteStore


def _auto_reconcile_env_allowed() -> bool:
    return os.getenv("CTO_OS_ALLOW_AUTO_RECONCILE", "0").strip() == "1"


class GitHubReconciliation:
    def __init__(self, store: SQLiteStore, github: GitHubIntegration | None = None) -> None:
        self.store = store
        self.github = github or GitHubIntegration()

    def reconcile(self, project_id: str, request: ReconcileRequest) -> ReconciliationReport:
        token = os.getenv("GITHUB_TOKEN", "").strip()
        report = ReconciliationReport(
            project_id=project_id, repository_id=request.repository_id
        )

        repositories = self._target_repositories(project_id, request.repository_id)
        if not repositories:
            report.degraded = True
            report.reason = "No repository configured for this project."
            return report

        if not token:
            # Still useful: emit local-only suggestions based on already-cached
            # GitHub state we synced earlier.
            report.degraded = True
            report.reason = "GITHUB_TOKEN not configured; using cached GitHub state."

        suggestions: list[StatusSuggestion] = []
        events: list[GitHubReconciliationEvent] = []

        for repository in repositories:
            for event, suggestion in self._reconcile_tasks(project_id, repository, token):
                events.append(event)
                if suggestion is not None:
                    suggestions.append(suggestion)
            for event, suggestion in self._reconcile_risks(project_id, repository, token):
                events.append(event)
                if suggestion is not None:
                    suggestions.append(suggestion)
            for event, suggestion in self._reconcile_pr_packets(
                project_id, repository, token
            ):
                events.append(event)
                if suggestion is not None:
                    suggestions.append(suggestion)

        # Persist
        for event in events:
            self.store.save_reconciliation_event(event)
        for suggestion in suggestions:
            self.store.save_status_suggestion(suggestion)

        # Auto-apply path
        if request.auto_reconcile and _auto_reconcile_env_allowed():
            for suggestion in suggestions:
                applied = self.apply_suggestion(project_id, suggestion.id)
                if applied is not None:
                    report.auto_applied += 1

        report.events = events
        report.suggestions = suggestions
        return report

    # ------------------------------------------------------ task reconciliation

    def _reconcile_tasks(
        self, project_id: str, repository: Repository, token: str
    ):
        for task in self.store.list_tasks(project_id):
            number = task.github_issue_number
            if not number:
                continue
            current = self._issue_state(repository, number, token)
            if current is None:
                continue
            previous = {"status": task.status.value, "github_issue_state": ""}
            new_state = {
                "github_issue_state": current.get("state", ""),
                "github_issue_url": current.get("html_url", task.github_issue_url),
                "github_closed_at": current.get("closed_at"),
            }
            recommendation = ""
            suggestion: StatusSuggestion | None = None
            if current.get("state") == "closed" and task.status != TaskStatus.done:
                recommendation = "Task linked GitHub issue is closed; mark task as done."
                suggestion = StatusSuggestion(
                    project_id=project_id,
                    entity_type=StatusSuggestionEntityType.task,
                    entity_id=task.id,
                    suggested_status=TaskStatus.done.value,
                    reason=recommendation,
                    evidence_json={
                        "github_issue_url": new_state["github_issue_url"],
                        "closed_at": new_state["github_closed_at"],
                    },
                )
            event = GitHubReconciliationEvent(
                project_id=project_id,
                repository_id=repository.id,
                entity_type=ReconciliationEntityType.task,
                entity_id=task.id,
                github_url=new_state["github_issue_url"] or "",
                previous_state_json=previous,
                new_state_json=new_state,
                recommendation=recommendation,
                suggestion_id=(suggestion.id if suggestion else None),
            )
            yield event, suggestion

    def _reconcile_risks(
        self, project_id: str, repository: Repository, token: str
    ):
        for risk in self.store.list_risks(project_id):
            number = risk.github_issue_number
            if not number:
                continue
            current = self._issue_state(repository, number, token)
            if current is None:
                continue
            previous = {"status": risk.status.value, "github_issue_state": ""}
            new_state = {
                "github_issue_state": current.get("state", ""),
                "github_issue_url": current.get("html_url", risk.github_issue_url),
                "github_closed_at": current.get("closed_at"),
            }
            recommendation = ""
            suggestion: StatusSuggestion | None = None
            if current.get("state") == "closed" and risk.status != RiskStatus.mitigated:
                recommendation = "Linked GitHub issue is closed; consider marking risk as mitigated."
                suggestion = StatusSuggestion(
                    project_id=project_id,
                    entity_type=StatusSuggestionEntityType.risk,
                    entity_id=risk.id,
                    suggested_status=RiskStatus.mitigated.value,
                    reason=recommendation,
                    evidence_json={"github_issue_url": new_state["github_issue_url"]},
                )
            event = GitHubReconciliationEvent(
                project_id=project_id,
                repository_id=repository.id,
                entity_type=ReconciliationEntityType.risk,
                entity_id=risk.id,
                github_url=new_state["github_issue_url"] or "",
                previous_state_json=previous,
                new_state_json=new_state,
                recommendation=recommendation,
                suggestion_id=(suggestion.id if suggestion else None),
            )
            yield event, suggestion

    # ------------------------------------------------- PR packet reconciliation

    def _reconcile_pr_packets(
        self, project_id: str, repository: Repository, token: str
    ):
        sessions_by_pr: dict[str, BuildSession] = {}
        for session in self.store.list_build_sessions(project_id):
            if session.linked_pr_packet_id:
                sessions_by_pr[session.linked_pr_packet_id] = session

        for packet in self.store.list_pr_packets(project_id):
            number = packet.github_pr_number
            if not number:
                continue
            current = self._pr_state(repository, number, token)
            if current is None:
                continue
            session = sessions_by_pr.get(packet.id)
            previous = {
                "build_session_status": session.status.value if session else "",
                "pr_state": "",
            }
            merged = bool(current.get("merged"))
            state = current.get("state", "")
            draft = bool(current.get("draft", False))
            new_state = {
                "pr_state": state,
                "pr_merged": merged,
                "pr_draft": draft,
                "merged_at": current.get("merged_at"),
                "closed_at": current.get("closed_at"),
                "html_url": current.get("html_url", packet.github_pr_url),
            }

            recommended_status: BuildSessionStatus | None = None
            recommendation = ""
            if merged:
                recommended_status = BuildSessionStatus.completed
                recommendation = "Linked PR was merged; mark build session as completed."
            elif state == "closed" and not merged:
                recommended_status = BuildSessionStatus.abandoned
                recommendation = (
                    "Linked PR was closed without merging; mark build session as abandoned."
                )
            elif draft and state == "open":
                recommended_status = BuildSessionStatus.reviewing
                recommendation = "Linked PR is an open draft; move build session to reviewing."

            suggestion: StatusSuggestion | None = None
            if (
                session is not None
                and recommended_status is not None
                and session.status != recommended_status
            ):
                suggestion = StatusSuggestion(
                    project_id=project_id,
                    entity_type=StatusSuggestionEntityType.build_session,
                    entity_id=session.id,
                    suggested_status=recommended_status.value,
                    reason=recommendation,
                    evidence_json={
                        "pr_packet_id": packet.id,
                        "pr_url": new_state["html_url"],
                        "pr_state": state,
                        "pr_merged": merged,
                    },
                )

            event = GitHubReconciliationEvent(
                project_id=project_id,
                repository_id=repository.id,
                entity_type=ReconciliationEntityType.pr_packet,
                entity_id=packet.id,
                github_url=new_state["html_url"] or "",
                previous_state_json=previous,
                new_state_json=new_state,
                recommendation=recommendation,
                suggestion_id=(suggestion.id if suggestion else None),
            )
            yield event, suggestion

    # ------------------------------------------------------- apply suggestions

    def apply_suggestion(
        self, project_id: str, suggestion_id: str
    ) -> StatusSuggestion | None:
        suggestion = self.store.get_status_suggestion(project_id, suggestion_id)
        if suggestion.dismissed or suggestion.applied:
            return None
        if suggestion.entity_type == StatusSuggestionEntityType.task:
            task = self.store.get_task(project_id, suggestion.entity_id)
            task.status = TaskStatus(suggestion.suggested_status)
            self.store.save_task(task)
        elif suggestion.entity_type == StatusSuggestionEntityType.risk:
            risk = self.store.get_risk(project_id, suggestion.entity_id)
            risk.status = RiskStatus(suggestion.suggested_status)
            self.store.save_risk(risk)
        elif suggestion.entity_type == StatusSuggestionEntityType.build_session:
            session = next(
                (
                    item
                    for item in self.store.list_build_sessions(project_id)
                    if item.id == suggestion.entity_id
                ),
                None,
            )
            if session is None:
                return None
            session.status = BuildSessionStatus(suggestion.suggested_status)
            self.store.save_build_session(session)
        suggestion.applied = True
        return self.store.save_status_suggestion(suggestion)

    def dismiss_suggestion(
        self, project_id: str, suggestion_id: str
    ) -> StatusSuggestion:
        suggestion = self.store.get_status_suggestion(project_id, suggestion_id)
        if suggestion.applied:
            return suggestion
        suggestion.dismissed = True
        return self.store.save_status_suggestion(suggestion)

    # ----------------------------------------------------------------- helpers

    def _target_repositories(
        self, project_id: str, repository_id: str | None
    ) -> list[Repository]:
        repos = self.store.list_repositories(project_id)
        if repository_id:
            repos = [item for item in repos if item.id == repository_id]
        return repos

    def _issue_state(
        self, repository: Repository, number: int, token: str
    ) -> dict[str, Any] | None:
        if not token:
            # Fall back to whatever sync_repository last stored for us.
            for issue in self.store.list_github_issues(repository.project_id):
                if issue.repository_id == repository.id and issue.number == number:
                    return {
                        "state": issue.state,
                        "html_url": issue.url,
                        "closed_at": issue.closed_at.isoformat() if issue.closed_at else None,
                    }
            return None
        try:
            return self.github.fetch_issue_state(repository, number)
        except Exception:
            return None

    def _pr_state(
        self, repository: Repository, number: int, token: str
    ) -> dict[str, Any] | None:
        if not token:
            for pr in self.store.list_github_pull_requests(repository.project_id):
                if pr.repository_id == repository.id and pr.number == number:
                    return {
                        "state": pr.state,
                        "merged": pr.merged,
                        "draft": pr.draft,
                        "html_url": pr.url,
                        "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                        "closed_at": pr.closed_at.isoformat() if pr.closed_at else None,
                    }
            return None
        try:
            return self.github.fetch_pr_state(repository, number)
        except Exception:
            return None
