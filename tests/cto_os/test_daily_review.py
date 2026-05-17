"""Phase 12 — daily review aggregator."""
from __future__ import annotations

from cto_os_api.daily_review import DailyReviewService
from cto_os_api.models import (
    ProjectCreate,
    RiskCreate,
    RiskSeverity,
    TaskCreate,
    TaskStatus,
    TaskUpdate,
)


def test_daily_review_picks_up_blocked_and_high_risks(store):
    project = store.create_project(ProjectCreate(name="DR"))
    task = store.create_task(project.id, TaskCreate(title="blocked one"))
    store.update_task(project.id, task.id, TaskUpdate(status=TaskStatus.blocked))
    store.create_risk(
        project.id, RiskCreate(title="prod fire", severity=RiskSeverity.critical)
    )

    review = DailyReviewService(store).build()
    assert any(t.id == task.id for t in review.blocked_tasks)
    assert any(r.severity == RiskSeverity.critical for r in review.high_risks)
    assert "blocked" in review.headline.lower() or "critical" in review.headline.lower() or "risk" in review.headline.lower()
    assert "# Daily CTO Review" in review.markdown
    assert review.recommended_next_actions


def test_daily_review_quiet_state(store):
    review = DailyReviewService(store).build()
    assert "quiet" in review.headline.lower() or "pick the next" in review.headline.lower() or review.headline.startswith("Today:")
    assert review.markdown.startswith("# Daily CTO Review")
