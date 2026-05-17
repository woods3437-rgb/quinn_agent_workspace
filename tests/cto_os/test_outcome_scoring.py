"""Phase 9 — outcome scoring + prompt hint."""
from __future__ import annotations

from cto_os_api.models import OutcomeScoreCreate, ProjectCreate
from cto_os_api.outcome_scoring import OutcomeScoringService


def test_outcome_score_clamps_and_averages(store):
    project = store.create_project(ProjectCreate(name="O"))
    service = OutcomeScoringService(store)

    service.record(project.id, OutcomeScoreCreate(score_type="execution_quality", score=10))
    service.record(project.id, OutcomeScoreCreate(score_type="execution_quality", score=-3))
    service.record(project.id, OutcomeScoreCreate(score_type="decision_quality", score=4))

    scores = service.project_scores(project.id)
    assert all(1 <= score.score <= 5 for score in scores)

    averages = service.system_averages()
    assert "execution_quality" in averages
    assert "decision_quality" in averages
    hint = service.prompt_hint(project.id)
    assert "execution_quality" in hint
