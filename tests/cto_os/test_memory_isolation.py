"""Project-scoped memory isolation test (Phase 6 verification)."""
from __future__ import annotations

from cto_os_api.models import MemoryCreate, ProjectCreate


def test_memories_are_project_scoped(store, memory_engine):
    project_a = store.create_project(ProjectCreate(name="A"))
    project_b = store.create_project(ProjectCreate(name="B"))

    store.create_memory(
        project_a.id, MemoryCreate(title="A secret", content="alpha-only knowledge")
    )
    store.create_memory(
        project_b.id, MemoryCreate(title="B secret", content="bravo-only knowledge")
    )

    a_memories = memory_engine.search(project_a.id, "knowledge", cross_project=False)
    b_memories = memory_engine.search(project_b.id, "knowledge", cross_project=False)

    a_contents = " ".join(memory.content for memory in a_memories)
    b_contents = " ".join(memory.content for memory in b_memories)

    assert "alpha-only" in a_contents
    assert "bravo-only" not in a_contents
    assert "bravo-only" in b_contents
    assert "alpha-only" not in b_contents

    cross = memory_engine.search(project_a.id, "knowledge", cross_project=True)
    titles = {memory.title for memory in cross}
    assert {"A secret", "B secret"}.issubset(titles)
