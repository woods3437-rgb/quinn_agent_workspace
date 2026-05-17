"""Phase 11 — writer lease acquire / release / conflict / expire."""
from __future__ import annotations

import time

import pytest

from cto_os_api.writer_lease import WriterLease, WriterLeaseBusy


def test_acquire_and_release(store):
    with WriterLease(store, "snapshot_restore", holder="A", ttl_seconds=5) as info:
        assert info.holder == "A"
        held = store.get_writer_lease("snapshot_restore")
        assert held is not None and held.holder == "A"
    assert store.get_writer_lease("snapshot_restore") is None


def test_second_holder_blocks_while_lease_active(store):
    lease = WriterLease(store, "import", holder="A", ttl_seconds=10)
    lease.__enter__()
    try:
        with pytest.raises(WriterLeaseBusy):
            WriterLease(store, "import", holder="B", ttl_seconds=10).__enter__()
    finally:
        lease.__exit__(None, None, None)


def test_same_holder_can_re_acquire(store):
    with WriterLease(store, "import", holder="A", ttl_seconds=10):
        with WriterLease(store, "import", holder="A", ttl_seconds=10):
            held = store.get_writer_lease("import")
            assert held.holder == "A"


def test_expired_lease_can_be_re_acquired(store):
    # 1-second TTL is fine for a single test; the lease check uses real time.
    WriterLease(store, "short", holder="A", ttl_seconds=1).__enter__()
    time.sleep(1.2)
    with WriterLease(store, "short", holder="B", ttl_seconds=5) as info:
        assert info.holder == "B"
