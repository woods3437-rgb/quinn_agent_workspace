"""Phase 12 — demo seed script (idempotent)."""
from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_PATH = REPO_ROOT / "scripts" / "seed_demo_project.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("seed_demo_project", SEED_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_seed_creates_demo_project(store):
    seed = _load_module().seed
    result = seed(store)
    assert result["created"] is True
    project = result["project"]
    assert project.name == "Demo · CTO OS Tour"
    assert len(result["memories"]) >= 3
    assert len(result["tasks"]) >= 3
    assert result["decision"] is not None
    assert result["risk"] is not None
    assert result["build_session"] is not None


def test_seed_is_idempotent(store):
    seed = _load_module().seed
    seed(store)
    result_again = seed(store)
    assert result_again["created"] is False
    projects = [p for p in store.list_projects() if p.name == "Demo · CTO OS Tour"]
    assert len(projects) == 1
