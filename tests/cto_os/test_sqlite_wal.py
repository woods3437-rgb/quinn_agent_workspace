"""Phase 11 — WAL + busy_timeout pragma."""
from __future__ import annotations


def test_journal_mode_is_wal(store):
    with store._connect() as conn:
        row = conn.execute("PRAGMA journal_mode").fetchone()
        assert row[0].lower() == "wal"


def test_busy_timeout_is_set(store):
    with store._connect() as conn:
        row = conn.execute("PRAGMA busy_timeout").fetchone()
        assert int(row[0]) >= 5000
