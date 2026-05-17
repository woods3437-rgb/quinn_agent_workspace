"""Phase 10 — save-back endpoints validate + persist host-model results."""
from __future__ import annotations

import pytest

from cto_os_api.llm_results import LLMResultsService
from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import (
    BuildPacketSaveRequest,
    CodeReviewSaveRequest,
    ImplementationPlanSaveRequest,
    ProjectCreate,
    RetrospectiveSaveRequest,
)


def test_save_code_review_validates_recommendation(store):
    project = store.create_project(ProjectCreate(name="LR"))
    svc = LLMResultsService(store, LocalMemoryEngine(store))
    with pytest.raises(ValueError, match="recommendation"):
        svc.save_code_review(
            project.id,
            CodeReviewSaveRequest(diff_text="x", recommendation="lgtm"),
        )


def test_save_code_review_persists(store):
    project = store.create_project(ProjectCreate(name="LR2"))
    svc = LLMResultsService(store, LocalMemoryEngine(store))
    review = svc.save_code_review(
        project.id,
        CodeReviewSaveRequest(
            diff_text="+ const x = 1;",
            recommendation="block",
            summary="hardcoded secret",
            blocking_issues=["secret in diff"],
            security_concerns=["api key visible"],
            create_follow_up_tasks=True,
        ),
    )
    assert review.approval_recommendation.value == "block"
    assert review.risk_level == "high"
    assert review.follow_up_task_ids
    assert any("Security" in finding for finding in review.findings)


def test_save_retrospective_creates_memory_decision_and_followups(store):
    project = store.create_project(ProjectCreate(name="LR3"))
    svc = LLMResultsService(store, LocalMemoryEngine(store))
    retro = svc.save_retrospective(
        project.id,
        RetrospectiveSaveRequest(
            title="X retro",
            summary="we shipped",
            lessons_learned="ship small",
            follow_up_tasks=["add e2e tests"],
            save_lessons_to_memory=True,
            create_decision=True,
            create_follow_up_tasks=True,
        ),
    )
    assert retro.memory_ids_created
    assert retro.decision_ids_created
    assert retro.follow_up_task_ids


def test_save_implementation_plan_creates_output(store):
    project = store.create_project(ProjectCreate(name="LR4"))
    svc = LLMResultsService(store, LocalMemoryEngine(store))
    output = svc.save_implementation_plan(
        project.id,
        ImplementationPlanSaveRequest(
            source_type="task",
            source_id="task_abc",
            title="impl",
            plan_markdown="# steps\n1. do it",
        ),
    )
    assert output.metadata["output_type"] == "implementation_plan"
    assert "do it" in output.output


def test_save_build_packet_persists(store):
    project = store.create_project(ProjectCreate(name="LR5"))
    svc = LLMResultsService(store, LocalMemoryEngine(store))
    packet = svc.save_build_packet(
        project.id,
        BuildPacketSaveRequest(
            title="ship X packet",
            implementation_steps=["a", "b"],
            acceptance_criteria=["ok"],
        ),
    )
    persisted = store.list_build_packets(project.id)
    assert any(p.id == packet.id for p in persisted)
