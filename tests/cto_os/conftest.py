"""Test fixtures for the CTO OS Phase 6 verification suite.

Each test gets an isolated SQLite + JSON store under a temp directory so we
never touch the user's real `cto_os.sqlite3`. We do NOT spin up MemPalace —
the LocalMemoryEngine is enough for unit-level coverage and avoids ChromaDB
startup time.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def _reset_mcp_cache():
    """Shadow the MemPalace-suite autouse fixture so we never import mcp_server.

    `mempalace.mcp_server` parses CLI args at module load, which crashes when
    pytest passes its own argv. Phase 6 tests don't need it, so this overrides
    the parent autouse with a no-op.
    """

    yield


@pytest.fixture
def tmp_data_dir():
    path = Path(tempfile.mkdtemp(prefix="cto_os_test_"))
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def store(tmp_data_dir, monkeypatch):
    from cto_os_api.sqlite_store import SQLiteStore

    sqlite_path = tmp_data_dir / "cto_os.sqlite3"
    json_path = tmp_data_dir / "cto_os.json"
    monkeypatch.setenv("CTO_OS_SQLITE_PATH", str(sqlite_path))
    monkeypatch.setenv("CTO_OS_DATA_PATH", str(json_path))
    return SQLiteStore(path=str(sqlite_path), json_path=str(json_path))


@pytest.fixture
def memory_engine(store):
    from cto_os_api.memory_engine import LocalMemoryEngine

    return LocalMemoryEngine(store)


@pytest.fixture
def project(store):
    from cto_os_api.models import ProjectCreate

    return store.create_project(ProjectCreate(name="Phase 6 Test", description="phase 6"))


@pytest.fixture
def tiny_python_repo(tmp_data_dir):
    """Tiny git-initialised repo with a FastAPI-flavoured module + a TS file."""
    repo = tmp_data_dir / "tiny_repo"
    repo.mkdir()
    (repo / "package.json").write_text(
        '{"name":"tiny","scripts":{"test":"echo ok","build":"echo ok","lint":"echo ok"}}'
    )
    (repo / "main.py").write_text(
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n\n"
        "@app.get('/health')\n"
        "def health():\n"
        "    return {'status': 'ok'}\n\n"
        "@app.post('/items')\n"
        "async def create_item(payload: dict):\n"
        "    return payload\n\n"
        "class Service:\n"
        "    def run(self):\n"
        "        return 42\n"
    )
    (repo / "app").mkdir()
    (repo / "app" / "page.tsx").write_text(
        "import { useState } from 'react';\n"
        "export default function HomePage() { return <div />; }\n"
        "export const helper = (x: number) => x + 1;\n"
        "export async function GET(req: Request) { return new Response('ok'); }\n"
    )
    (repo / "README.md").write_text("# tiny\n")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        cwd=repo,
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
        cwd=repo,
        check=True,
    )
    # Leave one unstaged change so git status has something to report.
    (repo / "README.md").write_text("# tiny\n\nupdated\n")
    return repo


@pytest.fixture
def repository(store, project, tiny_python_repo):
    from cto_os_api.models import RepositoryCreate, RepositoryProvider

    return store.create_repository(
        project.id,
        RepositoryCreate(
            provider=RepositoryProvider.local,
            name="tiny",
            local_path=str(tiny_python_repo),
        ),
    )
