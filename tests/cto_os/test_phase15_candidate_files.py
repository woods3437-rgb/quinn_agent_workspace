"""Phase 15 — _candidate_files surfaces real matches; falls back sanely."""
from __future__ import annotations

import subprocess
from pathlib import Path

from cto_os_api.models import ProjectCreate, RepositoryCreate, RepositoryProvider
from cto_os_api.repo_operator import RepoOperator
from cto_os_api.memory_engine import LocalMemoryEngine


def _git_init(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"], cwd=path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init"],
        cwd=path, check=True,
    )


def _make_repo(store, tmp_data_dir, name: str = "cand") -> tuple[str, str, RepoOperator]:
    repo = tmp_data_dir / f"{name}_repo"
    repo.mkdir()
    (repo / ".gitignore").write_text("")
    (repo / "package.json").write_text('{"name":"x"}')
    (repo / "tsconfig.json").write_text('{}')
    (repo / "README.md").write_text("# x")
    src = repo / "src"
    src.mkdir()
    (src / "App.tsx").write_text("export default () => null;")
    auth_dir = src / "auth"
    auth_dir.mkdir()
    (auth_dir / "login.tsx").write_text("export default () => null;")
    # Noise mimicking dscvr's Pods overflow:
    pods = repo / "ios" / "Pods" / "boost"
    pods.mkdir(parents=True)
    for i in range(8):
        (pods / f"header_{i}.hpp").write_text("// boost")
    _git_init(repo)

    project = store.create_project(ProjectCreate(name=name))
    repo_row = store.create_repository(
        project.id,
        RepositoryCreate(provider=RepositoryProvider.local, name=name, local_path=str(repo)),
    )
    operator = RepoOperator(store, LocalMemoryEngine(store))
    operator.scan_repository(project.id, repo_row.id)
    return project.id, repo_row.id, operator


def test_filename_in_task_text_ranks_first(store, tmp_data_dir):
    project_id, repo_id, op = _make_repo(store, tmp_data_dir, "fn_hit")
    files = op._candidate_files(project_id, repo_id, "Update package.json scripts for CI")
    assert files
    assert files[0].path == "package.json"


def test_specific_path_in_task_text_wins_over_alpha(store, tmp_data_dir):
    project_id, repo_id, op = _make_repo(store, tmp_data_dir, "path_hit")
    files = op._candidate_files(project_id, repo_id, "Refactor src/auth/login.tsx error states")
    assert files
    assert files[0].path == "src/auth/login.tsx"


def test_unmatchable_objective_does_not_return_pods_headers(store, tmp_data_dir):
    project_id, repo_id, op = _make_repo(store, tmp_data_dir, "fallback")
    files = op._candidate_files(project_id, repo_id, "qzqzqz nothing matches xyzzy")
    paths = [f.path for f in files]
    # Pods should never show up by the new fallback.
    assert not any("Pods" in p for p in paths), paths


def test_stopwords_filtered_out(store, tmp_data_dir):
    project_id, repo_id, op = _make_repo(store, tmp_data_dir, "stop")
    # "add to the README" — only "readme" is meaningful.
    files = op._candidate_files(project_id, repo_id, "Add to the README")
    assert files[0].path == "README.md"


def test_slug_drops_stopwords_and_caps_length(store, tmp_data_dir):
    _, _, op = _make_repo(store, tmp_data_dir, "slug")
    slug = op._slug("Gitignore one-off dev helper scripts to ignore from build")
    assert len(slug) <= 40
    assert "to" not in slug.split("-")
    assert "from" not in slug.split("-")
    assert slug.startswith("gitignore-one-off-dev")
