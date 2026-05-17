from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ValidationError

from .models import StructuredValidationResult


class StructuredArchitectureOutput(BaseModel):
    recommended_tech_stack: list[str] = []
    frontend_architecture: str = ""
    backend_architecture: str = ""
    database_schema: str = ""
    api_structure: list[str] = []
    security_considerations: list[str] = []
    build_complexity_score: int | None = None


class StructuredRoadmapOutput(BaseModel):
    phases: list[dict[str, Any]] = []
    risks: list[str] = []
    recommended_build_order: list[str] = []


class StructuredRiskOutput(BaseModel):
    risks: list[dict[str, Any]] = []


class StructuredBuildPacketOutput(BaseModel):
    title: str
    implementation_steps: list[str] = []
    acceptance_criteria: list[str] = []
    test_plan: list[str] = []
    codex_prompt: str = ""


class StructuredImplementationReviewOutput(BaseModel):
    recommendation: str
    lessons_learned: str = ""
    follow_up_tasks: list[str] = []


class StructuredWeeklyBriefOutput(BaseModel):
    what_changed: list[str] = []
    decisions_made: list[str] = []
    open_risks: list[str] = []
    next_recommended_actions: list[str] = []


class StructuredCodeReviewOutput(BaseModel):
    """Phase 8 — schema for the code review LLM response."""

    recommendation: str = "revise"
    summary: str = ""
    blocking_issues: list[str] = []
    non_blocking_suggestions: list[str] = []
    missing_tests: list[str] = []
    security_concerns: list[str] = []
    acceptance_criteria_check: str = ""
    confidence: float | None = None


class StructuredRetrospectiveOutput(BaseModel):
    """Phase 8 — schema for the post-ship retrospective LLM response."""

    summary: str = ""
    what_changed: list[str] = []
    what_worked: list[str] = []
    what_broke: list[str] = []
    test_results: str = ""
    risks_found: list[str] = []
    follow_up_tasks: list[str] = []
    lessons_learned: str = ""


def extract_json_object(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except Exception:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            pass
    return {}


def validate_structured_output(model: type[BaseModel], text: str) -> StructuredValidationResult:
    data = extract_json_object(text)
    if not data:
        return StructuredValidationResult(valid=False, error="No JSON object found in model output.")
    try:
        parsed = model.model_validate(data)
        return StructuredValidationResult(valid=True, data=parsed.model_dump(mode="json"))
    except ValidationError as exc:
        return StructuredValidationResult(valid=False, data=data, error=str(exc))
