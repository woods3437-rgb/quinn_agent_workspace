"""Phase 11 — MCP safety self-check tool."""
from __future__ import annotations

from cto_os_api.mcp_tools import MCPToolset
from cto_os_api.memory_engine import LocalMemoryEngine


def test_safety_report_advertises_no_github_writes_or_shell(store, monkeypatch):
    monkeypatch.delenv("CTO_OS_ALLOW_GITHUB_WRITES", raising=False)
    monkeypatch.delenv("CTO_OS_ENABLE_NOTIFICATIONS", raising=False)
    monkeypatch.delenv("CTO_OS_ALLOW_AUTO_RECONCILE", raising=False)
    monkeypatch.delenv("CTO_OS_ENABLE_WEBHOOK_INTAKE", raising=False)
    monkeypatch.setenv("CTO_OS_LLM_PROVIDER", "deterministic")

    report = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store)).call(
        "get_mcp_safety_report"
    )
    assert report["github_writes_in_mcp"] is False
    assert report["shell_in_mcp"] is False
    assert report["provider_mode"] == "deterministic"
    assert report["github_writes_env"] is False
    assert report["notifications_env"] is False
    assert report["auto_reconcile_env"] is False
    assert report["intake_env"] is False
    # Preview-only — no create_* GitHub tools.
    assert all(not t.startswith("create_github") for t in report["preview_tools"])
    assert any(t.startswith("preview_github") for t in report["preview_tools"])
    # sqlite path is reported as a string
    assert report["sqlite_path"]
    # WAL active after schema init
    assert report["sqlite_journal_mode"].lower() == "wal"
