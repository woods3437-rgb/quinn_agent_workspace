"""Phase 9 — system-wide risk concentration view."""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from .models import (
    RiskConcentrationGroup,
    RiskConcentrationSummary,
    RiskStatus,
    TaskStatus,
)
from .sqlite_store import SQLiteStore


def _ensure_aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


_KEYWORD_RE = re.compile(r"[a-zA-Z]{4,}")
_STOPWORDS = {
    "with", "from", "this", "that", "have", "will", "into", "their",
    "when", "what", "which", "should", "without",
}


class RiskConcentrationService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def build(self) -> RiskConcentrationSummary:
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        groups: list[RiskConcentrationGroup] = []
        all_keywords: Counter[str] = Counter()

        for project in self.store.list_projects():
            risks = self.store.list_risks(project.id)
            if not risks:
                continue
            tasks_by_id = {task.id: task for task in self.store.list_tasks(project.id)}
            severity_counts: dict[str, int] = {}
            no_mitigation: list[str] = []
            stale_links: list[str] = []
            critical_high = 0
            for risk in risks:
                severity_counts[risk.severity.value] = (
                    severity_counts.get(risk.severity.value, 0) + 1
                )
                if risk.status == RiskStatus.open and risk.severity.value in {"high", "critical"}:
                    critical_high += 1
                if risk.status == RiskStatus.open and not risk.linked_task_ids:
                    no_mitigation.append(risk.id)
                for task_id in risk.linked_task_ids:
                    task = tasks_by_id.get(task_id)
                    if task is None:
                        continue
                    if (
                        task.status != TaskStatus.done
                        and _ensure_aware(task.updated_at) < seven_days_ago
                    ):
                        stale_links.append(risk.id)
                        break
                for keyword in _KEYWORD_RE.findall(risk.title.lower()):
                    if keyword in _STOPWORDS:
                        continue
                    all_keywords[keyword] += 1

            groups.append(
                RiskConcentrationGroup(
                    project_id=project.id,
                    name=project.name,
                    severity_counts=severity_counts,
                    open_critical_high=critical_high,
                    risks_without_mitigation=no_mitigation,
                    risks_linked_to_stale_tasks=stale_links,
                )
            )

        themes = [
            keyword for keyword, count in all_keywords.most_common(8) if count >= 2
        ]
        groups.sort(key=lambda group: group.open_critical_high, reverse=True)
        return RiskConcentrationSummary(groups=groups, recurring_themes=themes)
