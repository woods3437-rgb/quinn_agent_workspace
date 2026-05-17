"""Phase 16.5 — FileClassifier rules + integration + raw-facts visibility.

Design constraints under test (carried over from the Phase 16 review):

- Every classification carries ``rules_triggered``.
- Noise (lockfile / generated / vendored / snapshot / build_artifact) is
  suppressed from candidate-file selection and packet derivation by
  default, but the operator can override by naming a noise file
  explicitly.
- The classifier itself is reachable via the read-only
  ``classify_repo_files`` MCP tool so an operator can always see WHAT
  was filtered and WHY.
- The classifier is rule-driven, not LLM-driven — same input always
  produces the same output.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cto_os_api.file_classifier import (
    NOISE_TYPES,
    ClassificationConfidence,
    FileClassifier,
    FileSemanticType,
    is_noise,
)
from cto_os_api.mcp_tools import MCPToolset, WRITE_TOOL_NAMES
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import (
    BuildPacketGenerateRequest,
    ProjectCreate,
    RepositoryCreate,
    RepositoryProvider,
    TaskCreate,
)
from cto_os_api.repo_operator import RepoOperator


# -------------------------------------------------------------- pure classifier


@pytest.mark.parametrize(
    "path, expected_type, must_contain_rule",
    [
        # lockfiles
        ("package-lock.json", FileSemanticType.lockfile, "lockfile.npm-package-lock"),
        ("yarn.lock", FileSemanticType.lockfile, "lockfile.yarn"),
        ("pnpm-lock.yaml", FileSemanticType.lockfile, "lockfile.pnpm"),
        ("uv.lock", FileSemanticType.lockfile, "lockfile.python"),
        ("Cargo.lock", FileSemanticType.lockfile, "lockfile.rust"),
        ("Gemfile.lock", FileSemanticType.lockfile, "lockfile.ruby"),
        # vendored
        ("node_modules/foo/index.js", FileSemanticType.vendored, "vendored.node_modules"),
        ("vendor/foo.go", FileSemanticType.vendored, "vendored.vendor-dir"),
        ("ios/Pods/boost/header.hpp", FileSemanticType.vendored, "vendored.cocoapods"),
        # build artifacts
        ("dist/main.js", FileSemanticType.build_artifact, "build_artifact.js-output"),
        ("apps/web/.next/server/foo.js", FileSemanticType.build_artifact, "build_artifact.js-output"),
        ("coverage/lcov.info", FileSemanticType.build_artifact, "build_artifact.coverage"),
        ("__pycache__/foo.cpython-311.pyc", FileSemanticType.build_artifact, "build_artifact.pycache"),
        # snapshots
        ("__snapshots__/Button.test.tsx.snap", FileSemanticType.snapshot, "snapshot.jest"),
        ("src/foo.snap", FileSemanticType.snapshot, "snapshot.snap-ext"),
        # generated
        ("protos/foo.pb.go", FileSemanticType.generated, "generated.protobuf"),
        ("src/types.generated.ts", FileSemanticType.generated, "generated.dot-generated"),
        ("generated/prisma/index.d.ts", FileSemanticType.generated, "generated.prisma-client"),
        # schema
        ("prisma/schema.prisma", FileSemanticType.schema, "schema.prisma"),
        ("openapi.yaml", FileSemanticType.schema, "schema.openapi"),
        ("api/foo.proto", FileSemanticType.schema, "schema.proto"),
        # migration
        ("prisma/migrations/20240101_init/migration.sql", FileSemanticType.migration, "migration.prisma"),
        ("db/migrate/20230101_create_users.rb", FileSemanticType.migration, "migration.rails"),
        ("app/users/migrations/0001_initial.py", FileSemanticType.migration, "migration.directory"),
        # env
        (".env", FileSemanticType.env, "env.dotenv"),
        (".env.production", FileSemanticType.env, "env.dotenv"),
        # ci
        (".github/workflows/ci.yml", FileSemanticType.ci, "ci.github-actions"),
        (".gitlab-ci.yml", FileSemanticType.ci, "ci.gitlab"),
        # infra
        ("Dockerfile", FileSemanticType.infra, "infra.dockerfile"),
        ("Dockerfile.prod", FileSemanticType.infra, "infra.dockerfile"),
        ("docker-compose.yml", FileSemanticType.infra, "infra.docker-compose"),
        ("infra/main.tf", FileSemanticType.infra, "infra.terraform"),
        # config
        ("package.json", FileSemanticType.config, "config.package-json"),
        ("tsconfig.json", FileSemanticType.config, "config.tsconfig"),
        ("pyproject.toml", FileSemanticType.config, "config.pyproject"),
        ("next.config.js", FileSemanticType.config, "config.next"),
        # tests
        ("src/auth/login.test.ts", FileSemanticType.test, "test.spec-or-test-suffix"),
        ("tests/test_auth.py", FileSemanticType.test, "test.spec-or-test-suffix"),
        ("src/__tests__/login.tsx", FileSemanticType.test, "test.directory"),
        # docs
        ("README.md", FileSemanticType.docs, "docs.readme-and-friends"),
        ("docs/api.md", FileSemanticType.docs, "docs.directory"),
        # assets
        ("assets/logo.png", FileSemanticType.asset, "asset.image"),
        ("fonts/Inter.woff2", FileSemanticType.asset, "asset.font"),
    ],
)
def test_classifier_assigns_expected_type_with_rule_evidence(path, expected_type, must_contain_rule):
    result = FileClassifier().classify(path)
    assert result.semantic_type == expected_type, (path, result)
    # Raw evidence is always exposed.
    assert must_contain_rule in result.rules_triggered, (path, result.rules_triggered)


def test_classifier_default_source_when_no_rule_but_code_extension():
    r = FileClassifier().classify("service/main.py")
    assert r.semantic_type == FileSemanticType.source
    assert r.confidence == ClassificationConfidence.low
    assert "default.source-by-extension" in r.rules_triggered


def test_classifier_unknown_when_no_rule_and_no_code_extension():
    r = FileClassifier().classify("notes/random.xyz")
    assert r.semantic_type == FileSemanticType.unknown
    assert r.confidence == ClassificationConfidence.low
    assert "default.unknown" in r.rules_triggered


def test_classifier_is_deterministic_and_pure():
    c = FileClassifier()
    a = c.classify("src/auth/login.tsx")
    b = c.classify("src/auth/login.tsx")
    assert a == b
    # Different instance, same rule table → same result.
    assert c.classify("package-lock.json") == FileClassifier().classify("package-lock.json")


def test_noise_helper_matches_noise_types():
    c = FileClassifier()
    for sample in ["package-lock.json", "dist/main.js", "node_modules/x.js",
                   "__snapshots__/foo.snap", "protos/x.pb.go"]:
        result = c.classify(sample)
        assert is_noise(result) is True
        assert result.semantic_type in NOISE_TYPES

    for sample in ["package.json", "src/auth/login.tsx", "README.md",
                   "tests/test_x.py", ".env.production"]:
        result = c.classify(sample)
        assert is_noise(result) is False
        assert result.semantic_type not in NOISE_TYPES


def test_classifier_records_all_matching_rules_not_just_primary():
    # README.md matches both docs.readme-and-friends (high) and
    # docs.markdown-other (low). Primary is the first one; both must
    # appear in rules_triggered so the operator sees all the evidence.
    r = FileClassifier().classify("README.md")
    assert r.semantic_type == FileSemanticType.docs
    assert "docs.readme-and-friends" in r.rules_triggered
    assert "docs.markdown-other" in r.rules_triggered


# ------------------------------------------------------ scanner integration


def _git_init(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"],
                   cwd=path, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "-m", "init"], cwd=path, check=True)


def _make_repo(store, tmp_data_dir, name: str = "p16") -> tuple[str, str, Path]:
    repo = tmp_data_dir / f"{name}_repo"
    repo.mkdir()
    (repo / ".gitignore").write_text("")
    (repo / "package.json").write_text('{"name":"x","scripts":{"test":"echo ok"}}')
    (repo / "package-lock.json").write_text('{"lockfileVersion":3}')
    (repo / "tsconfig.json").write_text("{}")
    (repo / "README.md").write_text("# x")
    src = repo / "src"
    src.mkdir()
    (src / "App.tsx").write_text("export default () => null;")
    auth = src / "auth"
    auth.mkdir()
    (auth / "login.tsx").write_text("export default () => null;")
    snaps = src / "__snapshots__"
    snaps.mkdir()
    (snaps / "Button.test.tsx.snap").write_text("// snapshot")
    gen = repo / "generated"
    (gen / "prisma").mkdir(parents=True)
    (gen / "prisma" / "index.d.ts").write_text("export {}")
    _git_init(repo)
    project = store.create_project(ProjectCreate(name=name))
    repo_row = store.create_repository(
        project.id,
        RepositoryCreate(provider=RepositoryProvider.local, name=name, local_path=str(repo)),
    )
    operator = RepoOperator(store, LocalMemoryEngine(store))
    operator.scan_repository(project.id, repo_row.id)
    return project.id, repo_row.id, repo


def test_scan_classifies_every_file_and_persists_evidence(store, tmp_data_dir):
    project_id, repo_id, _ = _make_repo(store, tmp_data_dir, "scan_p16")
    files = store.list_repo_files(project_id, repo_id)
    by_path = {f.path: f for f in files}

    # Every persisted RepoFile carries a classification + rule evidence.
    for f in files:
        assert f.classification_rules, f"{f.path} has no rules_triggered"
        assert f.semantic_type, f.path

    # Specific paths land in the right buckets.
    assert by_path["package.json"].semantic_type == FileSemanticType.config
    assert by_path["package-lock.json"].semantic_type == FileSemanticType.lockfile
    assert by_path["README.md"].semantic_type == FileSemanticType.docs
    assert by_path["src/auth/login.tsx"].semantic_type == FileSemanticType.source
    assert by_path["src/__snapshots__/Button.test.tsx.snap"].semantic_type == FileSemanticType.snapshot
    assert by_path["generated/prisma/index.d.ts"].semantic_type == FileSemanticType.generated


def test_scan_key_files_no_longer_includes_lockfiles(store, tmp_data_dir):
    project_id, repo_id, _ = _make_repo(store, tmp_data_dir, "keyfiles_p16")
    scan = next(iter(store.list_repo_scans(project_id, repo_id)), None)
    assert scan is not None
    assert "package-lock.json" not in scan.key_files, scan.key_files
    # but the manifest itself is still surfaced
    assert "package.json" in scan.key_files


# ------------------------------------------------------ candidates + packet


def test_candidate_files_suppress_noise_by_default(store, tmp_data_dir):
    project_id, repo_id, _ = _make_repo(store, tmp_data_dir, "cand_p16")
    op = RepoOperator(store, LocalMemoryEngine(store))
    # Bland objective — none of the noise files were named, so they must
    # not appear in the candidate list.
    files = op._candidate_files(project_id, repo_id, "Refactor login form")
    paths = [f.path for f in files]
    assert "package-lock.json" not in paths, paths
    assert "src/__snapshots__/Button.test.tsx.snap" not in paths, paths
    assert "generated/prisma/index.d.ts" not in paths, paths


def test_candidate_files_surface_lockfile_when_explicitly_named(store, tmp_data_dir):
    project_id, repo_id, _ = _make_repo(store, tmp_data_dir, "explicit_p16")
    op = RepoOperator(store, LocalMemoryEngine(store))
    # Operator explicitly named the lockfile — they want it surfaced.
    files = op._candidate_files(project_id, repo_id, "Regenerate package-lock.json")
    paths = [f.path for f in files]
    assert "package-lock.json" in paths, paths
    # And it ranks at the top because of the filename-hint boost.
    assert paths[0] == "package-lock.json"


def test_build_packet_files_likely_involved_skips_noise(store, tmp_data_dir):
    project_id, repo_id, _ = _make_repo(store, tmp_data_dir, "packet_p16")
    task = store.create_task(project_id, TaskCreate(title="Refactor login form"))
    # Reuse the MCP toolset's engine — same wiring the operator gets via MCP.
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    packet = toolset.execution_engine.generate_build_packet(
        project_id,
        BuildPacketGenerateRequest(title="Refactor login form", task_id=task.id),
    )
    for noise_path in ("package-lock.json",
                       "src/__snapshots__/Button.test.tsx.snap",
                       "generated/prisma/index.d.ts"):
        assert noise_path not in packet.files_likely_involved, packet.files_likely_involved


# ---------------------------------------------------------- MCP tool surface


def test_classify_repo_files_tool_is_registered_and_read_only(store, tmp_data_dir):
    project_id, repo_id, _ = _make_repo(store, tmp_data_dir, "tool_p16")
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    names = {t.name for t in toolset.tools()}
    assert "classify_repo_files" in names
    # Read-only audit window — must NOT be a write tool.
    assert "classify_repo_files" not in WRITE_TOOL_NAMES


def test_classify_repo_files_returns_every_file_with_evidence(store, tmp_data_dir):
    project_id, repo_id, _ = _make_repo(store, tmp_data_dir, "tool2_p16")
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    result = toolset.call(
        "classify_repo_files",
        {"project_id": project_id, "repository_id": repo_id},
    )
    assert isinstance(result, dict)
    assert result["returned"] >= 1
    assert result["total_files"] == result["returned"]  # default limit isn't hit
    assert set(result["noise_types"]) == {t.value for t in NOISE_TYPES}
    by_path = {item["path"]: item for item in result["items"]}
    # Raw rules are always present — operator can audit any classification.
    for path, item in by_path.items():
        assert item["rules_triggered"], f"{path} returned no rules_triggered"
        assert "semantic_type" in item and "confidence" in item
    # And the noise files show up here (raw facts always reachable, even
    # if downstream consumers suppress them).
    assert by_path["package-lock.json"]["is_noise"] is True
    assert by_path["package-lock.json"]["semantic_type"] == "lockfile"


def test_classify_repo_files_filters_only_noise(store, tmp_data_dir):
    project_id, repo_id, _ = _make_repo(store, tmp_data_dir, "tool3_p16")
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    result = toolset.call(
        "classify_repo_files",
        {"project_id": project_id, "repository_id": repo_id, "only_noise": True},
    )
    assert result["returned"] >= 1
    for item in result["items"]:
        assert item["is_noise"] is True


def test_classify_repo_files_filters_by_type(store, tmp_data_dir):
    project_id, repo_id, _ = _make_repo(store, tmp_data_dir, "tool4_p16")
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    result = toolset.call(
        "classify_repo_files",
        {
            "project_id": project_id,
            "repository_id": repo_id,
            "only_types": ["config", "docs"],
        },
    )
    types = {item["semantic_type"] for item in result["items"]}
    assert types <= {"config", "docs"}, types
    assert "config" in types
