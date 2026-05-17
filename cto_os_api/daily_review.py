"""Phase 12 — daily CTO review aggregator.

Builds the "what should I look at today" view and renders it as markdown
so the host model (Claude Code) can post it verbatim into a standup, or
the user can read it in the UI.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .control_room import ControlRoom
from .heartbeat import _ensure_aware
from .models import (
    BuildSessionStatus,
    DailyReview,
    JobStatus,
    RiskSeverity,
    RiskStatus,
    TaskStatus,
)
from .sqlite_store import SQLiteStore


class DailyReviewService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self.control_room = ControlRoom(store)

    def build(self) -> DailyReview:
        now = datetime.now(timezone.utc)
        seven = now - timedelta(days=7)
        cr = self.control_room.build()

        projects_needing_attention = [
            stat
            for stat in cr.active_projects
            if stat.open_risks or stat.blocked_tasks or stat.pending_suggestions
        ][:6]

        blocked_tasks = []
        high_risks = []
        stale_sessions = []
        failed_jobs = []
        pending_suggestions = []
        recent_shipped = []

        for project in self.store.list_projects():
            blocked_tasks.extend(
                t
                for t in self.store.list_tasks(project.id)
                if t.status == TaskStatus.blocked
            )
            high_risks.extend(
                r
                for r in self.store.list_risks(project.id)
                if r.status == RiskStatus.open
                and r.severity in {RiskSeverity.high, RiskSeverity.critical}
            )
            stale_sessions.extend(
                s
                for s in self.store.list_build_sessions(project.id)
                if s.status == BuildSessionStatus.reviewing
                and (now - _ensure_aware(s.updated_at)).days >= 7
            )
            failed_jobs.extend(
                j for j in self.store.list_jobs(project.id) if j.status == JobStatus.failed
            )
            pending_suggestions.extend(
                self.store.list_status_suggestions(project.id, include_resolved=False)
            )
            recent_shipped.extend(
                s
                for s in self.store.list_build_sessions(project.id)
                if s.status == BuildSessionStatus.completed
                and _ensure_aware(s.updated_at) >= seven
            )

        headline = self._headline(
            projects_needing_attention,
            blocked_tasks,
            high_risks,
            failed_jobs,
        )
        recommended = list(cr.recommended_next_actions)
        if not recommended:
            if not (blocked_tasks or high_risks or failed_jobs or pending_suggestions):
                recommended.append("Pick the next item from any active project's backlog.")
            else:
                recommended.append("Review the lists below and triage what's blocked first.")

        review = DailyReview(
            headline=headline,
            projects_needing_attention=projects_needing_attention,
            blocked_tasks=blocked_tasks[:20],
            high_risks=high_risks[:20],
            stale_build_sessions=stale_sessions[:10],
            failed_jobs=failed_jobs[:10],
            pending_suggestions=pending_suggestions[:20],
            recent_shipped=recent_shipped[:10],
            recommended_next_actions=recommended,
        )
        review.markdown = self._render(review)
        return review

    def _headline(
        self,
        projects: list,
        blocked: list,
        high_risks: list,
        failed_jobs: list,
    ) -> str:
        if not (projects or blocked or high_risks or failed_jobs):
            return "All quiet — pick the next task from your backlog."
        bits: list[str] = []
        if projects:
            bits.append(f"{len(projects)} project(s) need attention")
        if blocked:
            bits.append(f"{len(blocked)} blocked task(s)")
        if high_risks:
            bits.append(f"{len(high_risks)} high/critical risk(s)")
        if failed_jobs:
            bits.append(f"{len(failed_jobs)} failed job(s)")
        return "Today: " + ", ".join(bits) + "."

    def _render(self, review: DailyReview) -> str:
        lines = [
            "# Daily CTO Review",
            "",
            f"_{review.generated_at.isoformat(timespec='minutes')}_",
            "",
            f"**{review.headline}**",
            "",
            "## Projects needing attention",
        ]
        if not review.projects_needing_attention:
            lines.append("- (none)")
        else:
            for stat in review.projects_needing_attention:
                lines.append(
                    f"- **{stat.name}** — {stat.open_risks} risk(s), "
                    f"{stat.blocked_tasks} blocked, "
                    f"{stat.pending_suggestions} pending suggestion(s)"
                )
        lines += ["", "## Blocked tasks"]
        if not review.blocked_tasks:
            lines.append("- (none)")
        else:
            for task in review.blocked_tasks:
                lines.append(f"- `{task.id}` {task.title}")
        lines += ["", "## High / critical risks"]
        if not review.high_risks:
            lines.append("- (none)")
        else:
            for risk in review.high_risks:
                lines.append(f"- `{risk.id}` ({risk.severity.value}) {risk.title}")
        lines += ["", "## Stale build sessions"]
        if not review.stale_build_sessions:
            lines.append("- (none)")
        else:
            for session in review.stale_build_sessions:
                lines.append(f"- `{session.id}` {session.title}")
        lines += ["", "## Failed jobs"]
        if not review.failed_jobs:
            lines.append("- (none)")
        else:
            for job in review.failed_jobs:
                lines.append(f"- `{job.id}` {job.title}")
        lines += ["", "## Pending status suggestions"]
        if not review.pending_suggestions:
            lines.append("- (none)")
        else:
            for sugg in review.pending_suggestions:
                lines.append(
                    f"- `{sugg.id}` {sugg.entity_type.value} → {sugg.suggested_status} ({sugg.reason})"
                )
        lines += ["", "## Recent shipped (7d)"]
        if not review.recent_shipped:
            lines.append("- (none)")
        else:
            for session in review.recent_shipped:
                lines.append(f"- `{session.id}` {session.title}")
        lines += ["", "## Recommended next actions"]
        for action in review.recommended_next_actions:
            lines.append(f"- {action}")
        return "\n".join(lines)
