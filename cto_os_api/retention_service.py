"""Phase 14 — retention policies + cleanup.

Per-target defaults are seeded once. ``run()`` iterates enabled policies
and deletes rows older than ``days_to_keep``. The audit table has a
two-gate guard: even when its policy is enabled, ``run()`` skips the
delete unless ``hard_delete_allowed`` is also true.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import (
    RetentionPolicy,
    RetentionPolicyUpdate,
    RetentionRunOutcome,
    RetentionRunResult,
    RetentionTarget,
)
from .sqlite_store import SQLiteStore


_DEFAULTS: dict[RetentionTarget, tuple[bool, int, bool]] = {
    RetentionTarget.mcp_audit: (False, 365, False),
    RetentionTarget.health_snapshots: (True, 30, True),
    RetentionTarget.resource_changes: (True, 30, True),
    RetentionTarget.execution_logs: (True, 90, True),
    RetentionTarget.github_events: (True, 90, True),
    RetentionTarget.intake_events: (True, 30, True),
}


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


class RetentionService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def ensure_defaults(self) -> list[RetentionPolicy]:
        existing = {p.target: p for p in self.store.list_retention_policies()}
        seeded: list[RetentionPolicy] = []
        for target, (enabled, days, hard_delete) in _DEFAULTS.items():
            if target in existing:
                continue
            policy = RetentionPolicy(
                id=f"retention_{target.value}",
                target=target,
                enabled=enabled,
                days_to_keep=days,
                hard_delete_allowed=hard_delete,
            )
            seeded.append(self.store.save_retention_policy(policy))
        return seeded

    def list_policies(self) -> list[RetentionPolicy]:
        self.ensure_defaults()
        return self.store.list_retention_policies()

    def update(
        self, target: RetentionTarget, payload: RetentionPolicyUpdate
    ) -> RetentionPolicy:
        self.ensure_defaults()
        return self.store.update_retention_policy(target, payload)

    def run(self) -> RetentionRunResult:
        self.ensure_defaults()
        now = datetime.now(timezone.utc)
        outcomes: list[RetentionRunOutcome] = []
        for policy in self.store.list_retention_policies():
            if not policy.enabled:
                outcomes.append(
                    RetentionRunOutcome(
                        target=policy.target, skipped=True, reason="policy disabled"
                    )
                )
                continue
            if (
                policy.target == RetentionTarget.mcp_audit
                and not policy.hard_delete_allowed
            ):
                outcomes.append(
                    RetentionRunOutcome(
                        target=policy.target,
                        skipped=True,
                        reason="mcp_audit deletion requires hard_delete_allowed=true",
                    )
                )
                continue
            cutoff = _iso(now - timedelta(days=max(policy.days_to_keep, 0)))
            try:
                deleted = self.store.delete_older_than(policy.target, cutoff)
            except Exception as exc:  # noqa: BLE001
                outcomes.append(
                    RetentionRunOutcome(
                        target=policy.target, skipped=True, reason=f"error: {exc}"
                    )
                )
                continue
            policy.last_run_at = now
            self.store.save_retention_policy(policy)
            outcomes.append(RetentionRunOutcome(target=policy.target, deleted=deleted))
        return RetentionRunResult(outcomes=outcomes, generated_at=now)
