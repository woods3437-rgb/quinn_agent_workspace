"""Phase 16.4 — Real Review Routing.

Routing decisions must:

- Be rule-driven (every decision maps to a named rule).
- Expose rules_triggered + evidence + risks_considered + the recommended
  intensity (even when an override changed the final pick).
- Reuse the Phase 16.5 classifier and Phase 16.1 risk evaluator without
  inventing new classifications.
- Be reachable as a read-only MCP tool.
- Require no Anthropic / OpenAI keys to run.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from cto_os_api.mcp_tools import MCPToolset, WRITE_TOOL_NAMES
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import (
    ClassificationConfidence,
    ProjectCreate,
    RepositoryCreate,
    RepositoryProvider,
    ReviewIntensity,
    RiskKind,
)
from cto_os_api.review_router import ReviewRouter


# -------------------------------------------------------------------- helpers


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=repo, check=True, capture_output=True,
    )


def _init_repo(tmp_data_dir: Path, name: str, files: dict[str, str]) -> Path:
    repo = tmp_data_dir / f"{name}_rr"
    repo.mkdir()
    for rel, content in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


def _register(store, repo: Path, name: str = "rr"):
    project = store.create_project(ProjectCreate(name=name))
    repository = store.create_repository(
        project.id,
        RepositoryCreate(
            provider=RepositoryProvider.local, name=name, local_path=str(repo)
        ),
    )
    return project, repository


def _route_wt(store, tmp_data_dir, name: str, before: dict[str, str], after_edits):
    """Helper: set up a repo with ``before`` state, apply ``after_edits``,
    run the router against the working tree, return the result.
    """
    repo = _init_repo(tmp_data_dir, name, before)
    after_edits(repo)
    project, repository = _register(store, repo, name)
    return ReviewRouter().route_from_working_tree(repository)


# ----------------------------------------------------------- intensity rules


def test_clean_working_tree_routes_to_lightweight(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "clean", {".gitignore": "", "README.md": "# x"})
    _, repository = _register(store, repo, "clean")
    result = ReviewRouter().route_from_working_tree(repository)

    assert result.selected_intensity == ReviewIntensity.lightweight
    assert result.recommended_intensity == ReviewIntensity.lightweight
    assert "route.default-lightweight" in result.rules_triggered
    assert result.override_applied is False
    assert result.risks_considered == []
    # Working-tree summary is embedded so the operator can drill into it.
    assert result.working_tree_summary is not None
    assert result.working_tree_summary.changed_files == []


def test_docs_only_changes_route_to_docs_only(store, tmp_data_dir):
    result = _route_wt(
        store, tmp_data_dir, "docs",
        before={".gitignore": "", "README.md": "# x", "docs/api.md": "# api"},
        after_edits=lambda r: (
            (r / "README.md").write_text("# updated"),
            (r / "docs/api.md").write_text("# api v2"),
        ),
    )
    assert result.selected_intensity == ReviewIntensity.docs_only
    assert "route.docs_only" in result.rules_triggered


def test_env_file_change_routes_to_security(store, tmp_data_dir):
    result = _route_wt(
        store, tmp_data_dir, "env",
        before={".gitignore": "", ".env.example": "FOO=bar\n"},
        after_edits=lambda r: (r / ".env.example").write_text("FOO=baz\n"),
    )
    assert result.selected_intensity == ReviewIntensity.security
    assert "route.env_change->security" in result.rules_triggered
    assert RiskKind.env_change in result.risks_considered


def test_auth_path_change_routes_to_security(store, tmp_data_dir):
    result = _route_wt(
        store, tmp_data_dir, "auth",
        before={".gitignore": "", "src/auth/session.py": "x=1\n"},
        after_edits=lambda r: (r / "src/auth/session.py").write_text("x=2\n"),
    )
    assert result.selected_intensity == ReviewIntensity.security
    assert "route.auth_path_touched->security" in result.rules_triggered


def test_migration_change_routes_to_migration(store, tmp_data_dir):
    result = _route_wt(
        store, tmp_data_dir, "mig",
        before={
            ".gitignore": "",
            "prisma/migrations/20240101_init/migration.sql": "SELECT 1;\n",
        },
        after_edits=lambda r: (
            r / "prisma/migrations/20240101_init/migration.sql"
        ).write_text("ALTER TABLE users ADD COLUMN bio TEXT;\n"),
    )
    assert result.selected_intensity == ReviewIntensity.migration
    assert "route.migration_change->migration" in result.rules_triggered


def test_dependency_bump_routes_to_dependency(store, tmp_data_dir):
    result = _route_wt(
        store, tmp_data_dir, "dep",
        before={
            ".gitignore": "",
            "package.json": '{"name":"x","version":"0.0.1"}',
            "package-lock.json": '{"lockfileVersion":1}',
        },
        after_edits=lambda r: (
            (r / "package.json").write_text('{"name":"x","version":"0.0.2"}'),
            (r / "package-lock.json").write_text('{"lockfileVersion":2}'),
        ),
    )
    assert result.selected_intensity == ReviewIntensity.dependency
    assert "route.dependency_bump->dependency" in result.rules_triggered
    # Spec: the manifest+lockfile change should NOT also produce a
    # lockfile_only_change risk in the same diff.
    assert RiskKind.lockfile_only_change not in result.risks_considered


def test_lockfile_only_change_routes_to_dependency(store, tmp_data_dir):
    result = _route_wt(
        store, tmp_data_dir, "lo",
        before={
            ".gitignore": "",
            "package.json": '{"name":"x","version":"0.0.1"}',
            "package-lock.json": '{"lockfileVersion":1}',
        },
        after_edits=lambda r: (
            r / "package-lock.json"
        ).write_text('{"lockfileVersion":2}'),
    )
    assert result.selected_intensity == ReviewIntensity.dependency
    assert "route.lockfile_only_change->dependency" in result.rules_triggered


def test_infra_change_routes_to_config(store, tmp_data_dir):
    result = _route_wt(
        store, tmp_data_dir, "infra",
        before={".gitignore": "", "Dockerfile": "FROM node:18\n"},
        after_edits=lambda r: (r / "Dockerfile").write_text("FROM node:20\n"),
    )
    assert result.selected_intensity == ReviewIntensity.config
    assert "route.infra_change->config" in result.rules_triggered


def test_ci_change_routes_to_config(store, tmp_data_dir):
    result = _route_wt(
        store, tmp_data_dir, "ci",
        before={".gitignore": "", ".github/workflows/ci.yml": "name: ci\n"},
        after_edits=lambda r: (
            r / ".github/workflows/ci.yml"
        ).write_text("name: ci v2\n"),
    )
    assert result.selected_intensity == ReviewIntensity.config
    assert "route.ci_change->config" in result.rules_triggered


def test_source_without_test_routes_to_full_with_low_confidence(store, tmp_data_dir):
    result = _route_wt(
        store, tmp_data_dir, "notest",
        before={".gitignore": "", "src/billing/checkout.py": "x=1\n"},
        after_edits=lambda r: (
            r / "src/billing/checkout.py"
        ).write_text("x=2\n"),
    )
    assert result.selected_intensity == ReviewIntensity.full
    assert "route.source_changed_without_test->full" in result.rules_triggered
    # The winning route's confidence is reported on the result; spec
    # demands LOW for this rule so the operator sees it as a hint.
    assert result.confidence == ClassificationConfidence.low


def test_large_diff_routes_to_full(store, tmp_data_dir):
    result = _route_wt(
        store, tmp_data_dir, "big",
        before={
            ".gitignore": "",
            "src/big.py": "\n".join(f"x_{i}={i}" for i in range(5)) + "\n",
            "src/big.test.py": "test = 1\n",  # add a test so source_without_test doesn't fire
        },
        after_edits=lambda r: (r / "src/big.py").write_text(
            "\n".join(f"y_{i}={i}" for i in range(300)) + "\n"
        ),
    )
    assert result.selected_intensity == ReviewIntensity.full
    assert "route.large_diff->full" in result.rules_triggered


# ------------------------------------------------- priority resolution


def test_multiple_rules_pick_highest_priority(store, tmp_data_dir):
    """env_change (security) must outrank migration_change (migration)
    when both fire. The spec priority is security > migration."""
    result = _route_wt(
        store, tmp_data_dir, "multi",
        before={
            ".gitignore": "",
            ".env.example": "FOO=bar\n",
            "prisma/migrations/20240101_init/migration.sql": "SELECT 1;\n",
        },
        after_edits=lambda r: (
            (r / ".env.example").write_text("FOO=baz\n"),
            (r / "prisma/migrations/20240101_init/migration.sql").write_text(
                "ALTER TABLE x ADD COLUMN y TEXT;\n"
            ),
        ),
    )
    # Winner: security (env outranks migration).
    assert result.selected_intensity == ReviewIntensity.security
    # But BOTH rules remain visible in the audit trail.
    assert "route.env_change->security" in result.rules_triggered
    assert "route.migration_change->migration" in result.rules_triggered
    assert {RiskKind.env_change, RiskKind.migration_change} <= set(result.risks_considered)
    # And every fired route is in routes_considered (not just the winner).
    intensities = {r.intensity for r in result.routes_considered}
    assert ReviewIntensity.security in intensities
    assert ReviewIntensity.migration in intensities


# ------------------------------------------------- override behavior


def test_intensity_override_is_honored_but_recommendation_preserved(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "ov", {
        ".gitignore": "",
        ".env.example": "FOO=bar\n",
    })
    (repo / ".env.example").write_text("FOO=baz\n")
    _, repository = _register(store, repo, "ov")

    result = ReviewRouter().route_from_working_tree(
        repository, intensity_override=ReviewIntensity.lightweight,
    )
    # Operator's choice is what ships.
    assert result.selected_intensity == ReviewIntensity.lightweight
    # But the recommended decision is preserved so the override is auditable.
    assert result.recommended_intensity == ReviewIntensity.security
    assert result.override_applied is True
    # And the original rule still appears in the audit trail.
    assert "route.env_change->security" in result.rules_triggered
    assert any("Operator override applied" in line for line in result.evidence)


def test_override_matching_recommendation_does_not_flag_override(store, tmp_data_dir):
    """If the override matches what was recommended, override_applied
    should be False — there's nothing for an audit reader to notice."""
    repo = _init_repo(tmp_data_dir, "match", {
        ".gitignore": "",
        ".env.example": "FOO=bar\n",
    })
    (repo / ".env.example").write_text("FOO=baz\n")
    _, repository = _register(store, repo, "match")

    result = ReviewRouter().route_from_working_tree(
        repository, intensity_override=ReviewIntensity.security,
    )
    assert result.selected_intensity == ReviewIntensity.security
    assert result.recommended_intensity == ReviewIntensity.security
    assert result.override_applied is False


# ----------------------------------------------- diff_text entry path


_SAMPLE_DIFF = """diff --git a/src/auth/session.py b/src/auth/session.py
index 1111111..2222222 100644
--- a/src/auth/session.py
+++ b/src/auth/session.py
@@ -1,3 +1,3 @@
 a
-b
+c
"""


def test_route_from_diff_text_classifies_and_routes_without_repo():
    """Routing from a raw diff must not require git access at all —
    same rules apply on parsed paths."""
    result = ReviewRouter().route_from_diff_text(_SAMPLE_DIFF)
    assert result.diff_source == "diff_text"
    assert result.working_tree_summary is None
    assert result.selected_intensity == ReviewIntensity.security
    assert "route.auth_path_touched->security" in result.rules_triggered


def test_route_from_diff_text_picks_lightweight_for_neutral_change():
    diff = """diff --git a/src/util.py b/src/util.py
index 1..2 100644
--- a/src/util.py
+++ b/src/util.py
@@ -1,1 +1,1 @@
-old
+new
"""
    result = ReviewRouter().route_from_diff_text(diff)
    # Only a single non-auth source file changed → source_without_test
    # fires → full review.
    assert result.selected_intensity == ReviewIntensity.full
    assert "route.source_changed_without_test->full" in result.rules_triggered


def test_route_from_diff_text_empty_diff_routes_to_lightweight():
    result = ReviewRouter().route_from_diff_text("")
    assert result.selected_intensity == ReviewIntensity.lightweight
    assert "route.default-lightweight" in result.rules_triggered


# ----------------------------------------------- raw-facts contract


def test_every_route_carries_rule_name_and_evidence(store, tmp_data_dir):
    """Operator-audit invariant: every route in routes_considered must
    have a rule_name and at least one piece of evidence."""
    result = _route_wt(
        store, tmp_data_dir, "audit",
        before={".gitignore": "", "src/auth/session.py": "x=1\n"},
        after_edits=lambda r: (r / "src/auth/session.py").write_text("x=2\n"),
    )
    assert result.routes_considered
    for route in result.routes_considered:
        assert route.rule_name, route
        assert route.evidence, route


# --------------------------------------------------------- MCP tool surface


def test_route_review_is_registered_and_read_only(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "mcp", {".gitignore": "", "README.md": "# x"})
    _register(store, repo, "mcp")
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))
    names = {t.name for t in toolset.tools()}
    assert "route_review" in names
    assert "route_review" not in WRITE_TOOL_NAMES


def test_route_review_mcp_tool_returns_full_result(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "mcp2", {
        ".gitignore": "",
        ".env.example": "FOO=bar\n",
    })
    (repo / ".env.example").write_text("FOO=baz\n")
    project, repository = _register(store, repo, "mcp2")
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))

    result = toolset.call("route_review", {
        "project_id": project.id, "repository_id": repository.id,
    })
    assert isinstance(result, dict)
    assert result["selected_intensity"] == "security"
    assert result["recommended_intensity"] == "security"
    assert "route.env_change->security" in result["rules_triggered"]
    assert "env_change" in result["risks_considered"]
    assert result["routes_considered"]
    assert result["working_tree_summary"] is not None


def test_route_review_mcp_tool_honors_override(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "mcp3", {
        ".gitignore": "",
        ".env.example": "FOO=bar\n",
    })
    (repo / ".env.example").write_text("FOO=baz\n")
    project, repository = _register(store, repo, "mcp3")
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))

    result = toolset.call("route_review", {
        "project_id": project.id, "repository_id": repository.id,
        "intensity_override": "lightweight",
    })
    assert result["selected_intensity"] == "lightweight"
    assert result["recommended_intensity"] == "security"
    assert result["override_applied"] is True


def test_route_review_mcp_tool_accepts_diff_text(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "mcp4", {".gitignore": "", "README.md": "# x"})
    project, repository = _register(store, repo, "mcp4")
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))

    result = toolset.call("route_review", {
        "project_id": project.id, "repository_id": repository.id,
        "diff_text": _SAMPLE_DIFF,
    })
    assert result["diff_source"] == "diff_text"
    assert result["selected_intensity"] == "security"
    assert result["working_tree_summary"] is None


def test_review_diff_from_git_attaches_routing_metadata(store, tmp_data_dir):
    repo = _init_repo(tmp_data_dir, "rdg", {
        ".gitignore": "",
        "src/auth/session.py": "x=1\n",
    })
    (repo / "src/auth/session.py").write_text("x=2\n")
    project, repository = _register(store, repo, "rdg")
    toolset = MCPToolset(store=store, memory_engine=LocalMemoryEngine(store))

    review = toolset.call("review_diff_from_git", {
        "project_id": project.id, "repository_id": repository.id,
    })
    assert "routing" in review and review["routing"] is not None
    assert review["routing"]["selected_intensity"] == "security"
    assert "route.auth_path_touched->security" in review["routing"]["rules_triggered"]


# -------------------------------------------------- no-key requirement


def test_router_runs_without_any_llm_credentials(store, tmp_data_dir, monkeypatch):
    """The routing layer must work in environments with no Anthropic /
    OpenAI keys set. Strip both and run a route end-to-end."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CTO_OS_LLM_PROVIDER", raising=False)

    repo = _init_repo(tmp_data_dir, "nokey", {
        ".gitignore": "",
        "src/auth/session.py": "x=1\n",
    })
    (repo / "src/auth/session.py").write_text("x=2\n")
    _, repository = _register(store, repo, "nokey")

    result = ReviewRouter().route_from_working_tree(repository)
    assert result.selected_intensity == ReviewIntensity.security
