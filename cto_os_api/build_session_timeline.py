"""Phase 8 — derived build-session timeline view.

Pulls every entity linked to (or related to) a ``BuildSession`` and stitches
them into a chronological feed for the UI. Nothing is persisted here; the
timeline is computed on demand.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    BuildSession,
    BuildSessionTimeline,
    BuildSessionTimelineItem,
    BuildSessionTimelineItemKind,
)
from .sqlite_store import SQLiteStore


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class BuildSessionTimelineBuilder:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def build(self, project_id: str, session_id: str) -> BuildSessionTimeline:
        session = self._session(project_id, session_id)
        items: list[BuildSessionTimelineItem] = []

        # Task creation (if linked)
        if session.task_id:
            try:
                task = self.store.get_task(project_id, session.task_id)
                items.append(
                    BuildSessionTimelineItem(
                        kind=BuildSessionTimelineItemKind.task_created,
                        entity_id=task.id,
                        title=task.title,
                        detail=task.description,
                        metadata={"status": task.status.value},
                        created_at=task.created_at,
                    )
                )
            except KeyError:
                pass

        # Branch plan
        if session.linked_branch_plan_id:
            try:
                plan = self.store.get_branch_plan(project_id, session.linked_branch_plan_id)
                items.append(
                    BuildSessionTimelineItem(
                        kind=BuildSessionTimelineItemKind.branch_plan_created,
                        entity_id=plan.id,
                        title=plan.branch_name,
                        detail=plan.objective,
                        metadata={
                            "github_branch_url": plan.github_branch_url,
                            "github_sync_status": plan.github_sync_status.value
                            if hasattr(plan.github_sync_status, "value")
                            else str(plan.github_sync_status),
                        },
                        created_at=plan.created_at,
                    )
                )
            except KeyError:
                pass

        # Build packet
        if session.linked_build_packet_id:
            try:
                packet = self.store.get_build_packet(project_id, session.linked_build_packet_id)
                items.append(
                    BuildSessionTimelineItem(
                        kind=BuildSessionTimelineItemKind.build_packet_created,
                        entity_id=packet.id,
                        title=packet.title,
                        detail=packet.summary,
                        created_at=packet.created_at,
                    )
                )
            except KeyError:
                pass

        # PR packet
        if session.linked_pr_packet_id:
            try:
                pr_packet = self.store.get_pr_packet(project_id, session.linked_pr_packet_id)
                items.append(
                    BuildSessionTimelineItem(
                        kind=BuildSessionTimelineItemKind.pr_packet_created,
                        entity_id=pr_packet.id,
                        title=pr_packet.title,
                        detail=pr_packet.summary,
                        metadata={
                            "github_pr_url": pr_packet.github_pr_url,
                            "github_pr_number": pr_packet.github_pr_number,
                        },
                        created_at=pr_packet.created_at,
                    )
                )
            except KeyError:
                pass

        # Code reviews
        if session.linked_code_review_ids:
            review_index = {item.id: item for item in self.store.list_code_reviews(project_id)}
            for review_id in session.linked_code_review_ids:
                review = review_index.get(review_id)
                if review is None:
                    continue
                items.append(
                    BuildSessionTimelineItem(
                        kind=BuildSessionTimelineItemKind.code_review,
                        entity_id=review.id,
                        title=f"Code review: {review.approval_recommendation.value}",
                        detail=review.review_summary,
                        metadata={"risk_level": review.risk_level},
                        created_at=review.created_at,
                    )
                )

        # Test runs
        if session.linked_test_run_ids:
            run_index = {item.id: item for item in self.store.list_test_runs(project_id)}
            for run_id in session.linked_test_run_ids:
                run = run_index.get(run_id)
                if run is None:
                    continue
                items.append(
                    BuildSessionTimelineItem(
                        kind=BuildSessionTimelineItemKind.test_run,
                        entity_id=run.id,
                        title=f"Test run: {run.status.value}",
                        detail=run.command,
                        metadata={"status": run.status.value},
                        created_at=run.created_at,
                    )
                )

        # Implementation reviews
        if session.linked_implementation_review_ids:
            impl_index = {item.id: item for item in self.store.list_reviews(project_id)}
            for review_id in session.linked_implementation_review_ids:
                review = impl_index.get(review_id)
                if review is None:
                    continue
                items.append(
                    BuildSessionTimelineItem(
                        kind=BuildSessionTimelineItemKind.implementation_review,
                        entity_id=review.id,
                        title=f"Implementation review: {review.recommendation.value}",
                        detail=review.review_result,
                        created_at=review.created_at,
                    )
                )

        # GitHub write events
        if session.linked_github_write_event_ids:
            write_index = {item.id: item for item in self.store.list_github_write_events(project_id)}
            for event_id in session.linked_github_write_event_ids:
                event = write_index.get(event_id)
                if event is None:
                    continue
                items.append(
                    BuildSessionTimelineItem(
                        kind=BuildSessionTimelineItemKind.github_write,
                        entity_id=event.id,
                        title=f"GitHub {event.action.value}: {event.status.value}",
                        detail=event.error_message,
                        metadata={
                            "action": event.action.value,
                            "status": event.status.value,
                            "approved": event.approved,
                            "dry_run": event.dry_run,
                        },
                        created_at=event.created_at,
                    )
                )

        # Reconciliation events linked to the session via PR packet
        for recon in self.store.list_reconciliation_events(project_id):
            if (
                session.linked_pr_packet_id
                and recon.entity_type.value == "pr_packet"
                and recon.entity_id == session.linked_pr_packet_id
            ):
                items.append(
                    BuildSessionTimelineItem(
                        kind=BuildSessionTimelineItemKind.github_reconciliation,
                        entity_id=recon.id,
                        title=recon.recommendation or "GitHub state synced",
                        detail=recon.github_url,
                        metadata={"new_state": recon.new_state_json},
                        created_at=recon.created_at,
                    )
                )

        # Status suggestions targeting the session
        for suggestion in self.store.list_status_suggestions(
            project_id, include_resolved=True
        ):
            if (
                suggestion.entity_type.value == "build_session"
                and suggestion.entity_id == session.id
            ):
                items.append(
                    BuildSessionTimelineItem(
                        kind=BuildSessionTimelineItemKind.status_suggestion,
                        entity_id=suggestion.id,
                        title=f"Suggested → {suggestion.suggested_status}",
                        detail=suggestion.reason,
                        metadata={
                            "applied": suggestion.applied,
                            "dismissed": suggestion.dismissed,
                        },
                        created_at=suggestion.created_at,
                    )
                )

        # Retrospectives that cite this session
        for retro in self.store.list_retrospectives(project_id):
            if retro.build_session_id == session.id:
                items.append(
                    BuildSessionTimelineItem(
                        kind=BuildSessionTimelineItemKind.retrospective,
                        entity_id=retro.id,
                        title=retro.title or "Retrospective",
                        detail=retro.summary,
                        created_at=retro.created_at,
                    )
                )

        items.sort(key=lambda item: _ensure_aware(item.created_at))
        return BuildSessionTimeline(build_session_id=session.id, items=items)

    def _session(self, project_id: str, session_id: str) -> BuildSession:
        session = next(
            (item for item in self.store.list_build_sessions(project_id) if item.id == session_id),
            None,
        )
        if session is None:
            raise KeyError(session_id)
        return session
