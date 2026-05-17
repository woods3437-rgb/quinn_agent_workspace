"""Phase 12 — new endpoints work with no OpenAI/Anthropic keys."""
from __future__ import annotations

from cto_os_api.backups import BackupService
from cto_os_api.daily_review import DailyReviewService
from cto_os_api.health import HealthService
from cto_os_api.snapshots import SnapshotManager


def test_health_daily_review_and_backups_work_without_keys(store, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("CTO_OS_LLM_PROVIDER", "deterministic")

    snapshots = SnapshotManager(store)
    backups = BackupService(store, snapshots)
    health = HealthService(store, snapshots, backups).build()
    assert health.api["reachable"] is True

    review = DailyReviewService(store).build()
    assert review.markdown.startswith("# Daily CTO Review")
