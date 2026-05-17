"""Phase 9 regression — memory isolation + GitHub write guard still in force."""
from __future__ import annotations

import inspect

from cto_os_api import control_room, decision_graph, risk_concentration, system_shipped
from cto_os_api.github_write_guard import GitHubWriteError, GitHubWriteGuard
import pytest


SYSTEM_MODULES = [control_room, decision_graph, risk_concentration, system_shipped]


def test_system_aggregators_never_call_cross_project_search():
    """Cross-project rollups must not silently call cross_project=True searches."""
    for module in SYSTEM_MODULES:
        source = inspect.getsource(module)
        assert "cross_project=True" not in source, (
            f"{module.__name__} uses cross_project=True; this would violate "
            "Phase 9's project-scoped memory isolation."
        )


def test_write_guard_still_blocks_by_default(monkeypatch):
    monkeypatch.delenv("CTO_OS_ALLOW_GITHUB_WRITES", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "stub")
    with pytest.raises(GitHubWriteError):
        GitHubWriteGuard().require_writeable("create_issue", approved=True, dry_run=False)
