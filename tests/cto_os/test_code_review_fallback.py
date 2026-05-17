"""AI code review deterministic fallback (Phase 6 verification).

CTO_OS_LLM_PROVIDER defaults to `deterministic`. The deterministic
provider echoes the prompt and is treated as a fallback for review
purposes, so `_llm_review` must return an empty string and the
deterministic review path must still produce a meaningful CodeReview.
"""
from __future__ import annotations

from cto_os_api.models import ApprovalRecommendation, CodeReviewCreate
from cto_os_api.repo_operator import RepoOperator


def test_deterministic_review_flags_secret(monkeypatch, store, memory_engine, project, repository):
    monkeypatch.setenv("CTO_OS_LLM_PROVIDER", "deterministic")
    operator = RepoOperator(store, memory_engine)

    review = operator.review_diff(
        project.id,
        CodeReviewCreate(
            repository_id=repository.id,
            diff_text="+ const api_key = 'sk-live-XYZ'\n",
        ),
    )

    assert review.risk_level == "high"
    assert review.approval_recommendation == ApprovalRecommendation.block
    assert any("secret" in finding.lower() for finding in review.findings)


def test_deterministic_review_clean_diff(monkeypatch, store, memory_engine, project, repository):
    monkeypatch.setenv("CTO_OS_LLM_PROVIDER", "deterministic")
    operator = RepoOperator(store, memory_engine)

    review = operator.review_diff(
        project.id,
        CodeReviewCreate(
            repository_id=repository.id,
            diff_text="+ const greeting = 'hello world';\n",
        ),
    )
    assert review.approval_recommendation in {
        ApprovalRecommendation.approve,
        ApprovalRecommendation.revise,
    }
