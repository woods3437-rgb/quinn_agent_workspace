"""Phase 16.1 — Working Tree Intelligence detectors + raw-facts visibility.

Design constraints under test:

- Rule-driven. Every cluster + risk has a deterministic trigger.
- Evidence-backed. Every cluster + risk exposes ``rules_triggered`` and
  human-readable ``evidence`` strings.
- Raw facts always available. The summary includes the full
  ``changed_files`` list, the ``noise_suppressed`` list, AND the raw
  ``git diff --stat`` output, regardless of what's in the synthesized
  ``summary_lines`` view.
- No adaptive suggestions. The summary describes the current state; it
  does not advise actions. (Adaptive suggestions were explicitly
  deferred during the Phase 16 design review.)
- The MCP entrypoint is read-only.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cto_os_api.mcp_tools import MCPToolset, WRITE_TOOL_NAMES
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import (
    ChangedFileStatus,
    ClassificationConfidence,
    DiffClusterType,
    FileSemanticType,
    ProjectCreate,
    RepositoryCreate,
    RepositoryProvider,
    RiskKind,
    RiskSeverity,
)
from cto_os_api.working_tree import WorkingTreeAnalyzer


# -------------------------------------------------------------------- helpers


def _git(repo: Path, *args: str, allow_fail: bool = False) -> None:
    env_args = ["-c", "user.email=t@t", "-c", "user.name=t"]
    cmd = ["git", *env_args, *args]
    result = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
    if not allow_fail and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")


def _init_repo(tmp_data_dir: Path, name: str, files: dict[str, str]) -> Path:
    repo = tmp_data_dir / f"{name}_wt"
    repo.mkdir()
    for rel, content in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


def _register(store, repo: Path, name: str = "wt"):
    project = store.create_project(ProjectCreate(name=name))
    repository = store.create_repository(
        project.id,
        RepositoryCreate(
            provider=RepositoryProvider.local, name=name, local_path=str(repo)
        ),
    )
    return project, repository


# --------------------------------------------------------------- clean tree


def test_clean_working_tree_produces_empty_summary(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "clean", {
        ".gitignore": "",
        "README.md": "# clean",
        "src/app.py": "x = 1\n",
    })
    project, repository = _register(store, repo, "clean")
    summary = WorkingTreeAnalyzer.default().analyze(repository)

    assert summary.changed_files == []
    assert summary.clusters == []
    assert summary.risks == []
    assert summary.noise_suppressed == []
    assert summary.raw_diff_stat == ""
    assert summary.summary_lines == ["Working tree clean."]
    assert summary.current_branch  # branch name is always reported


# ---------------------------------------------- per-file change classification


def test_modified_source_file_appears_in_changed_files(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "mod", {
        ".gitignore": "",
        "src/login.tsx": "export default () => null;\n",
    })
    (repo / "src/login.tsx").write_text("export default () => 'changed';\n")
    project, repository = _register(store, repo, "mod")

    summary = WorkingTreeAnalyzer.default().analyze(repository)
    assert len(summary.changed_files) == 1
    cf = summary.changed_files[0]
    assert cf.path == "src/login.tsx"
    assert cf.status == ChangedFileStatus.modified
    assert cf.added_lines >= 1
    assert cf.semantic_type == FileSemanticType.source
    assert "default.source-by-extension" in cf.classification_rules
    assert cf.is_noise is False


def test_untracked_file_is_captured(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "untr", {
        ".gitignore": "",
        "README.md": "# x",
    })
    (repo / "src").mkdir()
    (repo / "src/new.py").write_text("y = 2\n")
    project, repository = _register(store, repo, "untr")

    summary = WorkingTreeAnalyzer.default().analyze(repository)
    paths = {cf.path for cf in summary.changed_files}
    assert "src/new.py" in paths
    new_cf = next(cf for cf in summary.changed_files if cf.path == "src/new.py")
    assert new_cf.status == ChangedFileStatus.untracked


# ---------------------------------------------------------------- noise split


def test_noise_files_are_segregated_but_kept_in_raw_view(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "noise", {
        ".gitignore": "",
        "package.json": '{"name":"x"}',
        "package-lock.json": '{"lockfileVersion":1}',
    })
    # Touch both manifest and lockfile so both show up in the diff.
    (repo / "package.json").write_text('{"name":"x","version":"0.0.2"}')
    (repo / "package-lock.json").write_text('{"lockfileVersion":2}')
    project, repository = _register(store, repo, "noise")

    summary = WorkingTreeAnalyzer.default().analyze(repository)
    # Raw view: lockfile is still in changed_files.
    paths_all = {cf.path for cf in summary.changed_files}
    assert {"package.json", "package-lock.json"} <= paths_all
    # Suppression view: lockfile is explicitly recorded as suppressed.
    noise_paths = {cf.path for cf in summary.noise_suppressed}
    assert "package-lock.json" in noise_paths
    assert "package.json" not in noise_paths
    # And the suppression line in summary_lines mentions it.
    assert any("Suppressed" in line for line in summary.summary_lines)


# ------------------------------------------------------------------- clusters


def test_directory_cluster_groups_files_under_same_parent(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "dir", {
        ".gitignore": "",
        "src/auth/session.py": "pass\n",
        "src/auth/middleware.py": "pass\n",
        "src/auth/utils.py": "pass\n",
        "src/billing/checkout.py": "pass\n",
    })
    for rel in ("src/auth/session.py", "src/auth/middleware.py",
                "src/auth/utils.py"):
        (repo / rel).write_text("changed\n")
    project, repository = _register(store, repo, "dir")

    summary = WorkingTreeAnalyzer.default().analyze(repository)
    dir_clusters = [c for c in summary.clusters
                    if c.cluster_type == DiffClusterType.directory]
    assert dir_clusters, summary
    auth_cluster = next((c for c in dir_clusters if c.name.startswith("src/auth")), None)
    assert auth_cluster is not None
    assert set(auth_cluster.files) == {
        "src/auth/session.py", "src/auth/middleware.py", "src/auth/utils.py",
    }
    assert auth_cluster.rules_triggered == ["cluster.directory-leaf"]
    assert auth_cluster.confidence == ClassificationConfidence.high  # 3+ files
    assert auth_cluster.evidence and "src/auth" in auth_cluster.evidence[0]


def test_semantic_cluster_groups_migration_files(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "sem", {
        ".gitignore": "",
        "db/migrate/20240101_initial.rb": "class Initial; end\n",
        "db/migrate/20240102_add_users.rb": "class AddUsers; end\n",
    })
    (repo / "db/migrate/20240101_initial.rb").write_text("# changed\n")
    (repo / "db/migrate/20240102_add_users.rb").write_text("# changed\n")
    project, repository = _register(store, repo, "sem")

    summary = WorkingTreeAnalyzer.default().analyze(repository)
    sem_clusters = [c for c in summary.clusters
                    if c.cluster_type == DiffClusterType.semantic]
    mig = next((c for c in sem_clusters if c.name == "migration"), None)
    assert mig is not None, sem_clusters
    assert mig.rules_triggered == ["cluster.semantic.migration"]
    assert mig.confidence == ClassificationConfidence.high
    assert set(mig.files) == {
        "db/migrate/20240101_initial.rb",
        "db/migrate/20240102_add_users.rb",
    }


# ------------------------------------------------------------ risk detectors


def test_migration_change_risk_fires_with_evidence(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "mig", {
        ".gitignore": "",
        "prisma/schema.prisma": "// schema\n",
        "prisma/migrations/20240101_init/migration.sql": "SELECT 1;\n",
    })
    (repo / "prisma/migrations/20240101_init/migration.sql").write_text(
        "ALTER TABLE users ADD COLUMN bio TEXT;\n"
    )
    project, repository = _register(store, repo, "mig")
    summary = WorkingTreeAnalyzer.default().analyze(repository)

    risks = {r.kind for r in summary.risks}
    assert RiskKind.migration_change in risks
    mig_risk = next(r for r in summary.risks if r.kind == RiskKind.migration_change)
    assert mig_risk.severity == RiskSeverity.high
    assert mig_risk.confidence == ClassificationConfidence.high
    assert "risk.migration_change" in mig_risk.rules_triggered
    assert any("Migration file present" in line for line in mig_risk.evidence)


def test_schema_change_risk_fires(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "sch", {
        ".gitignore": "",
        "prisma/schema.prisma": "// schema\n",
    })
    (repo / "prisma/schema.prisma").write_text("// changed schema\n")
    project, repository = _register(store, repo, "sch")
    summary = WorkingTreeAnalyzer.default().analyze(repository)

    risks = {r.kind for r in summary.risks}
    assert RiskKind.schema_change in risks


def test_env_change_risk_fires_high_severity(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "env", {
        # Track an env-shaped file; project repos sometimes commit .env.example.
        ".gitignore": "",
        ".env.example": "FOO=bar\n",
    })
    (repo / ".env.example").write_text("FOO=baz\n")
    project, repository = _register(store, repo, "env")
    summary = WorkingTreeAnalyzer.default().analyze(repository)

    env_risks = [r for r in summary.risks if r.kind == RiskKind.env_change]
    assert env_risks
    assert env_risks[0].severity == RiskSeverity.high


def test_dependency_bump_risk_fires_when_manifest_and_lockfile_both_change(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "dep", {
        ".gitignore": "",
        "package.json": '{"name":"x","version":"0.0.1"}',
        "package-lock.json": '{"lockfileVersion":1}',
    })
    (repo / "package.json").write_text('{"name":"x","version":"0.0.2"}')
    (repo / "package-lock.json").write_text('{"lockfileVersion":2}')
    project, repository = _register(store, repo, "dep")
    summary = WorkingTreeAnalyzer.default().analyze(repository)

    bump = next((r for r in summary.risks if r.kind == RiskKind.dependency_bump), None)
    assert bump is not None
    assert bump.severity == RiskSeverity.low
    assert set(bump.files) == {"package.json", "package-lock.json"}
    # Both pieces of evidence are present.
    joined = "\n".join(bump.evidence)
    assert "Manifest changed" in joined
    assert "Lockfile changed" in joined
    # And the lockfile_only risk should NOT also fire when the manifest is present.
    assert not any(r.kind == RiskKind.lockfile_only_change for r in summary.risks)


def test_lockfile_only_change_risk_fires_when_manifest_unchanged(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "lo", {
        ".gitignore": "",
        "package.json": '{"name":"x","version":"0.0.1"}',
        "package-lock.json": '{"lockfileVersion":1}',
    })
    (repo / "package-lock.json").write_text('{"lockfileVersion":2}')
    project, repository = _register(store, repo, "lo")
    summary = WorkingTreeAnalyzer.default().analyze(repository)

    lo = next((r for r in summary.risks if r.kind == RiskKind.lockfile_only_change), None)
    assert lo is not None
    assert lo.severity == RiskSeverity.medium
    assert lo.files == ["package-lock.json"]


def test_auth_path_touched_risk_fires_for_auth_directory(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "authrisk", {
        ".gitignore": "",
        "src/auth/session.py": "pass\n",
        "src/billing/checkout.py": "pass\n",
    })
    (repo / "src/auth/session.py").write_text("# changed\n")
    project, repository = _register(store, repo, "authrisk")
    summary = WorkingTreeAnalyzer.default().analyze(repository)

    auth = next((r for r in summary.risks if r.kind == RiskKind.auth_path_touched), None)
    assert auth is not None
    assert "src/auth/session.py" in auth.files
    assert auth.confidence == ClassificationConfidence.medium  # path-based heuristic


def test_large_diff_risk_fires_above_threshold(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "big", {
        ".gitignore": "",
        "src/big.py": "\n".join(f"x_{i} = {i}" for i in range(10)) + "\n",
    })
    (repo / "src/big.py").write_text(
        "\n".join(f"y_{i} = {i}" for i in range(300)) + "\n"
    )
    project, repository = _register(store, repo, "big")
    summary = WorkingTreeAnalyzer.default().analyze(repository)

    big = next((r for r in summary.risks if r.kind == RiskKind.large_diff), None)
    assert big is not None
    assert big.files == ["src/big.py"]


def test_source_changed_without_test_risk_is_low_confidence_hint(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "notest", {
        ".gitignore": "",
        "src/login.tsx": "export default () => null;\n",
    })
    (repo / "src/login.tsx").write_text("export default () => 'changed';\n")
    project, repository = _register(store, repo, "notest")
    summary = WorkingTreeAnalyzer.default().analyze(repository)

    risk = next((r for r in summary.risks
                 if r.kind == RiskKind.source_changed_without_test), None)
    assert risk is not None
    # Conservative on purpose: low confidence so it doesn't generate fatigue.
    assert risk.confidence == ClassificationConfidence.low


def test_source_changed_without_test_does_not_fire_when_tests_present(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "withtest", {
        ".gitignore": "",
        "src/login.tsx": "export default () => null;\n",
        "src/login.test.ts": "test('ok', () => {})\n",
    })
    (repo / "src/login.tsx").write_text("export default () => 'changed';\n")
    (repo / "src/login.test.ts").write_text("test('updated', () => {})\n")
    project, repository = _register(store, repo, "withtest")
    summary = WorkingTreeAnalyzer.default().analyze(repository)

    assert not any(r.kind == RiskKind.source_changed_without_test for r in summary.risks)


def test_infra_change_risk_fires_for_dockerfile_edit(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "infra", {
        ".gitignore": "",
        "Dockerfile": "FROM node:18\n",
    })
    (repo / "Dockerfile").write_text("FROM node:20\n")
    project, repository = _register(store, repo, "infra")
    summary = WorkingTreeAnalyzer.default().analyze(repository)
    assert any(r.kind == RiskKind.infra_change for r in summary.risks)


def test_ci_change_risk_fires_for_workflow_edit(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "ci", {
        ".gitignore": "",
        ".github/workflows/ci.yml": "name: ci\n",
    })
    (repo / ".github/workflows/ci.yml").write_text("name: ci v2\n")
    project, repository = _register(store, repo, "ci")
    summary = WorkingTreeAnalyzer.default().analyze(repository)
    assert any(r.kind == RiskKind.ci_change for r in summary.risks)


# --------------------------------------------------------- raw-facts contract


def test_every_cluster_carries_rules_and_evidence(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "rules", {
        ".gitignore": "",
        "src/auth/a.py": "x=1\n",
        "src/auth/b.py": "x=1\n",
        "prisma/schema.prisma": "// s\n",
    })
    (repo / "src/auth/a.py").write_text("x=2\n")
    (repo / "src/auth/b.py").write_text("x=2\n")
    (repo / "prisma/schema.prisma").write_text("// s2\n")
    project, repository = _register(store, repo, "rules")
    summary = WorkingTreeAnalyzer.default().analyze(repository)

    assert summary.clusters
    for cluster in summary.clusters:
        assert cluster.rules_triggered, cluster
        assert cluster.evidence, cluster
    for risk in summary.risks:
        assert risk.rules_triggered, risk
        assert risk.evidence, risk


def test_raw_diff_stat_is_always_included_when_there_are_changes(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "stat", {
        ".gitignore": "",
        "src/x.py": "a=1\n",
    })
    (repo / "src/x.py").write_text("a=2\n")
    project, repository = _register(store, repo, "stat")
    summary = WorkingTreeAnalyzer.default().analyze(repository)

    # The unvarnished `git diff --stat` is always reachable so the
    # operator can see what really changed, not just our cluster view.
    assert summary.raw_diff_stat, summary
    assert "src/x.py" in summary.raw_diff_stat


# ----------------------------------------------------------------- MCP tool


def test_summarize_working_tree_is_registered_and_read_only(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "mcp", {".gitignore": "", "README.md": "# x"})
    project, repository = _register(store, repo, "mcp")
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    names = {t.name for t in toolset.tools()}
    assert "summarize_working_tree" in names
    # Read-only: must NOT appear in WRITE_TOOL_NAMES.
    assert "summarize_working_tree" not in WRITE_TOOL_NAMES


def test_summarize_working_tree_returns_serialised_summary(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "mcp2", {
        ".gitignore": "",
        "src/login.tsx": "export default () => null;\n",
    })
    (repo / "src/login.tsx").write_text("export default () => 'x';\n")
    project, repository = _register(store, repo, "mcp2")
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))

    result = toolset.call("summarize_working_tree", {
        "project_id": project.id, "repository_id": repository.id,
    })
    assert isinstance(result, dict)
    assert result["repository_id"] == repository.id
    assert result["changed_files"]
    cf = result["changed_files"][0]
    # Each changed file carries its full classification + rule evidence.
    assert {"path", "status", "semantic_type", "classification_confidence",
            "classification_rules", "is_noise"} <= cf.keys()
    assert result["raw_diff_stat"]
    assert result["summary_lines"]
