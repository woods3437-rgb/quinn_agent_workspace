"""Phase 15 — scanner respects .gitignore + ignores mobile/web junk dirs."""
from __future__ import annotations

import subprocess
from pathlib import Path

from cto_os_api.models import ProjectCreate, RepositoryCreate, RepositoryProvider
from cto_os_api.repo_operator import RepoOperator
from cto_os_api.memory_engine import LocalMemoryEngine


def _git_init(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "add",
            "-A",
        ],
        cwd=path,
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-q",
            "-m",
            "init",
        ],
        cwd=path,
        check=True,
    )


def test_scanner_honors_gitignore_and_skips_pods(store, tmp_data_dir):
    repo = tmp_data_dir / "rn_repo"
    repo.mkdir()
    (repo / ".gitignore").write_text(
        "build/\n*.local\nios/Pods/\n"
    )
    (repo / "README.md").write_text("# real")
    (repo / "package.json").write_text('{"name":"x","scripts":{"test":"echo ok"}}')
    src = repo / "src"
    src.mkdir()
    (src / "App.tsx").write_text("export default function App() { return null; }")
    # Junk that .gitignore should exclude:
    build = repo / "build"
    build.mkdir()
    (build / "bundle.js").write_text("x")
    pods = repo / "ios" / "Pods" / "boost"
    pods.mkdir(parents=True)
    (pods / "noisy.hpp").write_text("// noise")
    (repo / "settings.local").write_text("local-only")
    # .expo / .turbo / .gradle should be killed by IGNORE_DIRS.
    expo = repo / ".expo"
    expo.mkdir()
    (expo / "state.json").write_text("{}")
    gradle = repo / "android" / ".gradle"
    gradle.mkdir(parents=True)
    (gradle / "cache.bin").write_text("x")

    _git_init(repo)

    project = store.create_project(ProjectCreate(name="rn_scan"))
    repo_row = store.create_repository(
        project.id,
        RepositoryCreate(
            provider=RepositoryProvider.local, name="rn", local_path=str(repo)
        ),
    )
    operator = RepoOperator(store, LocalMemoryEngine(store))
    operator.scan_repository(project.id, repo_row.id)
    paths = {f.path for f in store.list_repo_files(project.id, repo_row.id)}

    # Real files survive.
    assert ".gitignore" in paths
    assert "README.md" in paths
    assert "src/App.tsx" in paths
    # Junk is gone.
    assert not any(p.startswith("build/") for p in paths)
    assert not any("Pods" in p for p in paths)
    assert "settings.local" not in paths
    assert not any(p.startswith(".expo/") for p in paths)
    assert not any(".gradle" in p.split("/") for p in paths)


def test_detect_stack_recognises_expo_and_firebase(store, tmp_data_dir):
    repo = tmp_data_dir / "expo_repo"
    repo.mkdir()
    (repo / ".gitignore").write_text("")
    (repo / "package.json").write_text(
        '{"name":"x","dependencies":{'
        '"expo":"~54","react":"^19","react-native":"^0.74",'
        '"firebase":"^11","@react-navigation/native":"^7","typescript":"^5"'
        '}}'
    )
    _git_init(repo)
    project = store.create_project(ProjectCreate(name="expo"))
    repo_row = store.create_repository(
        project.id,
        RepositoryCreate(provider=RepositoryProvider.local, name="rn", local_path=str(repo)),
    )
    operator = RepoOperator(store, LocalMemoryEngine(store))
    scan = operator.scan_repository(project.id, repo_row.id)
    assert "Expo" in scan.frameworks
    assert "React Native" in scan.frameworks
    assert "Firebase" in scan.frameworks
    assert "React Navigation" in scan.frameworks
    assert "TypeScript" in scan.tech_stack
