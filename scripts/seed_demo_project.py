"""Phase 12 — seed a demo project for onboarding / quick tours.

Usage::

    .venv/bin/python scripts/seed_demo_project.py

Idempotent: if a project named "Demo · CTO OS Tour" already exists, the
script returns it without creating duplicates. Intentionally lightweight —
demonstrates memory + tasks + decision + risk + build session + repo,
nothing GitHub-flavoured.
"""
from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from cto_os_api.memory_engine import LocalMemoryEngine
from cto_os_api.models import (
    BuildSessionCreate,
    BuildSessionStatus,
    DecisionCreate,
    DecisionType,
    ImpactLevel,
    MemoryCreate,
    ProjectCreate,
    RepositoryCreate,
    RepositoryProvider,
    RiskCategory,
    RiskCreate,
    RiskSeverity,
    TaskCategory,
    TaskCreate,
    TaskPriority,
)
from cto_os_api.sqlite_store import SQLiteStore


DEMO_NAME = "Demo · CTO OS Tour"


def seed(store: SQLiteStore | None = None) -> dict:
    """Create the demo project + fixtures, or return the existing ones."""
    store = store or SQLiteStore()
    memory_engine = LocalMemoryEngine(store)

    existing = next((p for p in store.list_projects() if p.name == DEMO_NAME), None)
    if existing is not None:
        return {
            "project": existing,
            "created": False,
            "note": "Demo project already present; nothing seeded.",
        }

    project = store.create_project(
        ProjectCreate(
            name=DEMO_NAME,
            description="An on-rails tour of CTO OS — memory, tasks, decisions, risks, build sessions.",
            status="active",
        )
    )

    memories = []
    for title, content, pinned, tags in [
        (
            "North star",
            "Internal-only CTO OS. Never expose project memory across projects unless explicitly asked.",
            True,
            ["north-star"],
        ),
        (
            "Stack",
            "FastAPI + Next.js + SQLite + MemPalace + MCP server. Python 3.12+, Node 20+.",
            True,
            ["stack"],
        ),
        (
            "Open question",
            "Should retrospectives auto-publish to memory? Currently opt-in per generation.",
            False,
            ["question"],
        ),
    ]:
        memory = store.create_memory(
            project.id,
            MemoryCreate(title=title, content=content, pinned=pinned, tags=tags, source="demo-seed"),
        )
        memory_engine.index_memory(memory)
        memories.append(memory)

    decision = store.create_decision(
        project.id,
        DecisionCreate(
            title="Use SQLite, not Postgres",
            decision="Stay on SQLite + WAL until concurrent writers across machines become real.",
            decision_type=DecisionType.technical,
            rationale="Single-user internal tool; ops cost dominates correctness gains from Postgres.",
            tradeoffs="No horizontal scale; harder cross-machine sync.",
            impact_level=ImpactLevel.medium,
        ),
    )

    tasks = []
    for title, status, priority, category in [
        ("Tour the control room", "todo", TaskPriority.medium, TaskCategory.ops),
        ("Walk through the MCP server", "in_progress", TaskPriority.high, TaskCategory.backend),
        ("Read the daily review", "backlog", TaskPriority.low, TaskCategory.ops),
    ]:
        task = store.create_task(
            project.id,
            TaskCreate(
                title=title,
                description="Demo task. Edit or delete freely.",
                status=status,
                priority=priority,
                category=category,
                acceptance_criteria=["You see the relevant page in the web UI."],
            ),
        )
        tasks.append(task)

    risk = store.create_risk(
        project.id,
        RiskCreate(
            title="MCP host doesn't process change notifications",
            category=RiskCategory.technical,
            severity=RiskSeverity.low,
            evidence="Phase 12 ships notifications/resources/updated; some hosts ignore them.",
            recommendation="Document the limitation; revisit in Phase 13.",
        ),
    )

    repository = store.create_repository(
        project.id,
        RepositoryCreate(
            provider=RepositoryProvider.local,
            name="cto-os-itself",
            local_path=REPO_ROOT,
            notes="The repo you're reading right now.",
        ),
    )

    session = store.create_build_session(
        project.id,
        BuildSessionCreate(
            title="Demo build session",
            repository_id=repository.id,
            task_id=tasks[1].id,
            status=BuildSessionStatus.in_progress,
            summary="Sample build session. Move it to completed when you're done with the tour.",
        ),
    )

    return {
        "project": project,
        "created": True,
        "memories": memories,
        "decision": decision,
        "tasks": tasks,
        "risk": risk,
        "repository": repository,
        "build_session": session,
    }


def main() -> None:
    result = seed()
    project = result["project"]
    if result["created"]:
        print(f"Seeded demo project {project.id} '{project.name}'.")
        print(f"  Memories:  {len(result['memories'])}")
        print(f"  Tasks:     {len(result['tasks'])}")
        print("  Open the web UI at /projects to take the tour.")
    else:
        print(result["note"])
        print(f"Demo project id: {project.id}")


if __name__ == "__main__":
    main()
