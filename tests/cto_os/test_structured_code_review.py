"""Phase 8 — structured code review validation + safety regressions."""
from __future__ import annotations

import json

import pytest

from cto_os_api import llm as llm_module
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import (
    ApprovalRecommendation,
    CodeReviewCreate,
    ProjectCreate,
    RepositoryCreate,
    RepositoryProvider,
)
from cto_os_api.repo_operator import RepoOperator


@pytest.fixture
def project_repo(store):
    project = store.create_project(ProjectCreate(name="phase8 review"))
    repo = store.create_repository(
        project.id,
        RepositoryCreate(provider=RepositoryProvider.manual, name="repo"),
    )
    return project, repo


def _patch_llm(monkeypatch, text: str, provider: str = "openai"):
    class FakeService:
        def generate(self, system, prompt, metadata=None):
            return llm_module.LLMResult(
                text=text, provider=provider, model="fake", fallback=False
            )

    monkeypatch.setenv("CTO_OS_LLM_PROVIDER", provider)
    monkeypatch.setattr(
        "cto_os_api.repo_operator.LLMService", lambda: FakeService()
    )


def test_structured_review_can_escalate(project_repo, store, monkeypatch):
    project, repo = project_repo
    _patch_llm(
        monkeypatch,
        json.dumps(
            {
                "recommendation": "revise",
                "summary": "Solid, but split the migration.",
                "non_blocking_suggestions": ["split migration into two PRs"],
                "missing_tests": ["coverage for empty input"],
            }
        ),
    )
    operator = RepoOperator(store, LocalMemoryEngine(store))

    review = operator.review_diff(
        project.id,
        CodeReviewCreate(repository_id=repo.id, diff_text="+ const ok = 1;\n"),
    )
    assert review.approval_recommendation == ApprovalRecommendation.revise
    assert "split the migration" in review.review_summary.lower()
    assert any("split migration" in finding.lower() for finding in review.findings)
    assert "coverage for empty input" in review.test_recommendations


def test_security_deterministic_not_downgraded_by_llm_approve(project_repo, store, monkeypatch):
    project, repo = project_repo
    _patch_llm(
        monkeypatch,
        json.dumps({"recommendation": "approve", "summary": "looks fine"}),
    )
    operator = RepoOperator(store, LocalMemoryEngine(store))

    review = operator.review_diff(
        project.id,
        CodeReviewCreate(
            repository_id=repo.id, diff_text="+ password = 'hunter2'\n"
        ),
    )
    assert review.approval_recommendation == ApprovalRecommendation.block


def test_malformed_json_falls_back_to_deterministic(project_repo, store, monkeypatch):
    project, repo = project_repo
    _patch_llm(monkeypatch, "not json at all just some prose")
    operator = RepoOperator(store, LocalMemoryEngine(store))

    review = operator.review_diff(
        project.id,
        CodeReviewCreate(repository_id=repo.id, diff_text="+ const ok = 2;\n"),
    )
    assert review.approval_recommendation in {
        ApprovalRecommendation.approve,
        ApprovalRecommendation.revise,
    }
    assert "Deterministic diff review" in review.review_summary


def test_deterministic_provider_path_unchanged(project_repo, store, monkeypatch):
    project, repo = project_repo
    monkeypatch.setenv("CTO_OS_LLM_PROVIDER", "deterministic")
    operator = RepoOperator(store, LocalMemoryEngine(store))

    review = operator.review_diff(
        project.id,
        CodeReviewCreate(repository_id=repo.id, diff_text="+ password = 'hunter2'\n"),
    )
    assert review.approval_recommendation == ApprovalRecommendation.block
