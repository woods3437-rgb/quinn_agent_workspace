"""Phase 11 — verify subagent + workflow docs ship with the project."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

REQUIRED_AGENT = ROOT / ".claude/agents/cto-os.md"
REQUIRED_WORKFLOWS = [
    ROOT / ".claude/workflows/cto-os-start-task.md",
    ROOT / ".claude/workflows/cto-os-review-diff.md",
    ROOT / ".claude/workflows/cto-os-retrospective.md",
    ROOT / ".claude/workflows/cto-os-weekly-review.md",
    ROOT / ".claude/workflows/cto-os-save-lesson.md",
]


def test_subagent_file_exists_with_frontmatter():
    assert REQUIRED_AGENT.exists()
    text = REQUIRED_AGENT.read_text()
    assert text.startswith("---")
    assert "name: cto-os" in text
    assert "Hard rules" in text


def test_every_workflow_doc_exists_with_steps_and_safety():
    for path in REQUIRED_WORKFLOWS:
        assert path.exists(), f"missing workflow: {path.name}"
        text = path.read_text()
        assert "## Safety" in text, f"{path.name} missing Safety section"
        assert "## Steps" in text, f"{path.name} missing Steps section"
