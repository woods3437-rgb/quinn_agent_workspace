"""Phase 9 — Outcome scoring service."""
from __future__ import annotations

from collections import defaultdict
from statistics import mean

from .models import OutcomeScore, OutcomeScoreCreate
from .sqlite_store import SQLiteStore


class OutcomeScoringService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def record(self, project_id: str, payload: OutcomeScoreCreate) -> OutcomeScore:
        return self.store.create_outcome_score(project_id, payload)

    def project_scores(self, project_id: str) -> list[OutcomeScore]:
        return self.store.list_outcome_scores(project_id)

    def system_scores(self) -> list[OutcomeScore]:
        return self.store.list_outcome_scores(None)

    def system_averages(self) -> dict[str, float]:
        scores = self.system_scores()
        buckets: dict[str, list[int]] = defaultdict(list)
        for score in scores:
            buckets[score.score_type.value].append(score.score)
        return {key: round(mean(values), 2) for key, values in buckets.items() if values}

    def prompt_hint(self, project_id: str) -> str:
        """Compact summary to inject into future LLM prompts.

        Returns at most one short line per score type. Never includes raw notes.
        """
        scores = self.project_scores(project_id)
        if not scores:
            return ""
        buckets: dict[str, list[int]] = defaultdict(list)
        for score in scores:
            buckets[score.score_type.value].append(score.score)
        parts = [
            f"{kind}={round(mean(values), 2)}/5 over {len(values)} sample(s)"
            for kind, values in buckets.items()
            if values
        ]
        return "Historical outcome scores: " + ", ".join(parts) + "."
