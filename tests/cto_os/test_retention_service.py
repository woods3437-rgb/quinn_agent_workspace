"""Phase 14 — retention policies + cleanup + audit two-gate."""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

from cto_os_api.models import (
    MCPAuditEvent,
    RetentionPolicyUpdate,
    RetentionTarget,
    ResourceChangeEvent,
)
from cto_os_api.retention_service import RetentionService


def test_defaults_seeded(store):
    service = RetentionService(store)
    service.ensure_defaults()
    targets = {p.target for p in store.list_retention_policies()}
    assert targets == set(RetentionTarget)
    audit = next(p for p in store.list_retention_policies() if p.target == RetentionTarget.mcp_audit)
    assert audit.enabled is False
    assert audit.hard_delete_allowed is False


def test_health_snapshot_retention_deletes_old(store):
    from cto_os_api.models import HealthSnapshot, HealthStatus

    old = HealthSnapshot(status=HealthStatus.ok)
    old.created_at = datetime.now(timezone.utc) - timedelta(days=60)
    store.append_health_snapshot(old)
    new = HealthSnapshot(status=HealthStatus.ok)
    store.append_health_snapshot(new)

    service = RetentionService(store)
    service.ensure_defaults()
    result = service.run()
    health_outcome = next(
        o for o in result.outcomes if o.target == RetentionTarget.health_snapshots
    )
    assert health_outcome.deleted >= 1
    remaining = store.list_health_snapshots()
    assert all(s.id != old.id for s in remaining)


def test_mcp_audit_two_gate_blocks_deletion(store):
    # Insert an old audit row.
    old = MCPAuditEvent(tool_name="ancient")
    old.created_at = datetime.now(timezone.utc) - timedelta(days=400)
    store.append_mcp_audit(old)

    service = RetentionService(store)
    service.ensure_defaults()
    # Enable but leave hard_delete_allowed=False.
    service.update(
        RetentionTarget.mcp_audit,
        RetentionPolicyUpdate(enabled=True, days_to_keep=30),
    )
    result = service.run()
    audit_outcome = next(o for o in result.outcomes if o.target == RetentionTarget.mcp_audit)
    assert audit_outcome.skipped is True
    assert "hard_delete_allowed" in audit_outcome.reason
    assert any(e.id == old.id for e in store.list_mcp_audit(limit=500))

    # Now flip the second gate.
    service.update(
        RetentionTarget.mcp_audit,
        RetentionPolicyUpdate(hard_delete_allowed=True),
    )
    result = service.run()
    audit_outcome = next(o for o in result.outcomes if o.target == RetentionTarget.mcp_audit)
    assert audit_outcome.deleted >= 1
    assert not any(e.id == old.id for e in store.list_mcp_audit(limit=500))


def test_disabled_policy_records_skip(store):
    service = RetentionService(store)
    service.ensure_defaults()
    service.update(
        RetentionTarget.health_snapshots, RetentionPolicyUpdate(enabled=False)
    )
    result = service.run()
    out = next(o for o in result.outcomes if o.target == RetentionTarget.health_snapshots)
    assert out.skipped is True
    assert "disabled" in out.reason
