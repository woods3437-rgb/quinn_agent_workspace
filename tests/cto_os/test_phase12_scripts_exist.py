"""Phase 12 — operations scripts ship + are executable."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_SCRIPTS = [
    "scripts/start_cto_os.sh",
    "scripts/stop_cto_os.sh",
    "scripts/status_cto_os.sh",
    "scripts/start_api.sh",
    "scripts/start_web.sh",
    "scripts/start_worker.sh",
    "scripts/start_mcp.sh",
    "scripts/seed_demo_project.py",
]


def test_scripts_exist_and_executable():
    for rel in REQUIRED_SCRIPTS:
        path = REPO_ROOT / rel
        assert path.exists(), f"missing script: {rel}"
        assert os.access(path, os.X_OK), f"not executable: {rel}"


def test_status_script_runs_clean():
    # status is read-only and should always succeed even with nothing running.
    result = subprocess.run(
        ["bash", str(REPO_ROOT / "scripts/status_cto_os.sh")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "api" in result.stdout
    assert "worker" in result.stdout
    assert "web" in result.stdout


def test_start_mcp_smoke_prints_config():
    result = subprocess.run(
        ["bash", str(REPO_ROOT / "scripts/start_mcp.sh")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0
    assert "mcpServers" in result.stdout
