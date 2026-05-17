"""Phase 15 — project brief no longer leaks CTO OS's own stack."""
from __future__ import annotations

import subprocess
from pathlib import Path

from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import (
    MemoryCreate,
    ProjectCreate,
    RepositoryCreate,
    RepositoryProvider,
)
from cto_os_api.repo_operator import RepoOperator
from cto_os_api.workspace_generators import WorkspaceGenerator


def test_tech_stack_uses_repo_scan_when_available(store, tmp_data_dir):
    repo = tmp_data_dir / "brief_repo"
    repo.mkdir()
    (repo / ".gitignore").write_text("")
    (repo / "package.json").write_text(
        '{"name":"x","dependencies":{"expo":"~54","react":"^19","react-native":"^0.74"}}'
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init"],
        cwd=repo, check=True,
    )
    project = store.create_project(ProjectCreate(name="dscvr-shaped"))
    repo_row = store.create_repository(
        project.id,
        RepositoryCreate(provider=RepositoryProvider.local, name="r", local_path=str(repo)),
    )
    RepoOperator(store, LocalMemoryEngine(store)).scan_repository(project.id, repo_row.id)

    brief = WorkspaceGenerator(store, LocalMemoryEngine(store)).current_brief(project.id)
    # Must NOT contain CTO OS's own stack string.
    assert "FastAPI" not in brief.current_tech_stack
    assert "MemPalace" not in brief.current_tech_stack
    # Must contain detected items.
    assert "Node.js" in brief.current_tech_stack
    assert "Expo" in brief.current_tech_stack


def test_tech_stack_falls_back_to_pinned_memory(store):
    project = store.create_project(ProjectCreate(name="no_repo"))
    store.create_memory(
        project.id,
        MemoryCreate(
            title="dscvr — stack",
            content="React Native, Firebase, Sentry",
            tags=["stack"],
            pinned=True,
        ),
    )
    brief = WorkspaceGenerator(store, LocalMemoryEngine(store)).current_brief(project.id)
    assert "React Native" in brief.current_tech_stack
    assert "FastAPI" not in brief.current_tech_stack


def test_tech_stack_empty_state_gives_honest_hint(store):
    project = store.create_project(ProjectCreate(name="bare"))
    brief = WorkspaceGenerator(store, LocalMemoryEngine(store)).current_brief(project.id)
    assert "Not detected yet" in brief.current_tech_stack
    assert "FastAPI" not in brief.current_tech_stack
    # Open risks must not include the old "JSON metadata should move to SQLite" CTO OS line.
    assert not any("JSON metadata" in r for r in brief.open_risks)
