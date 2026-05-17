"""Phase 15 — build packet uses real repo signals, not CTO OS defaults."""
from __future__ import annotations

import subprocess
from pathlib import Path

from cto_os_api.execution_engine import ExecutionEngine
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import (
    BuildPacketGenerateRequest,
    ProjectCreate,
    RepositoryCreate,
    RepositoryProvider,
    TaskCreate,
)
from cto_os_api.repo_operator import RepoOperator
from cto_os_api.workspace_generators import WorkspaceGenerator


def _git_init(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"], cwd=path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init"],
        cwd=path, check=True,
    )


def _engine(store):
    memory = LocalMemoryEngine(store)
    workspace = WorkspaceGenerator(store, memory)
    repo_op = RepoOperator(store, memory)
    return ExecutionEngine(store, memory, workspace, lambda *a, **k: None, repo_op)


def test_files_likely_involved_populated_from_task_text(store, tmp_data_dir):
    repo = tmp_data_dir / "pkt"
    repo.mkdir()
    (repo / ".gitignore").write_text("")
    (repo / "package.json").write_text('{"name":"x","scripts":{"test":"echo ok"}}')
    _git_init(repo)
    project = store.create_project(ProjectCreate(name="pkt"))
    repo_row = store.create_repository(
        project.id,
        RepositoryCreate(provider=RepositoryProvider.local, name="r", local_path=str(repo)),
    )
    RepoOperator(store, LocalMemoryEngine(store)).scan_repository(project.id, repo_row.id)
    task = store.create_task(project.id, TaskCreate(title="Update package.json scripts for CI"))

    engine = _engine(store)
    packet = engine.generate_build_packet(
        project.id, BuildPacketGenerateRequest(task_id=task.id)
    )
    assert "package.json" in packet.files_likely_involved
    # Test plan reflects the detected npm test script — NOT compileall/tsc defaults.
    assert any("npm run test" in cmd for cmd in packet.test_plan)
    assert not any("compileall" in cmd for cmd in packet.test_plan)


def test_test_plan_honest_when_no_commands(store, tmp_data_dir):
    repo = tmp_data_dir / "no_tests"
    repo.mkdir()
    (repo / ".gitignore").write_text("")
    # package.json with no test/build/lint scripts (Expo-style).
    (repo / "package.json").write_text(
        '{"name":"x","scripts":{"start":"expo start","ios":"expo run:ios"}}'
    )
    _git_init(repo)
    project = store.create_project(ProjectCreate(name="no_tests"))
    repo_row = store.create_repository(
        project.id,
        RepositoryCreate(provider=RepositoryProvider.local, name="r", local_path=str(repo)),
    )
    RepoOperator(store, LocalMemoryEngine(store)).scan_repository(project.id, repo_row.id)
    task = store.create_task(project.id, TaskCreate(title="tidy something"))

    packet = _engine(store).generate_build_packet(
        project.id, BuildPacketGenerateRequest(task_id=task.id)
    )
    assert packet.test_plan
    msg = " ".join(packet.test_plan)
    assert "No test/build/lint commands detected" in msg
    assert "compileall" not in msg


def test_no_repo_returns_honest_empty(store):
    project = store.create_project(ProjectCreate(name="empty"))
    task = store.create_task(project.id, TaskCreate(title="something"))
    packet = _engine(store).generate_build_packet(
        project.id, BuildPacketGenerateRequest(task_id=task.id)
    )
    assert packet.files_likely_involved == []
    assert any("No repository registered" in line for line in packet.test_plan)
