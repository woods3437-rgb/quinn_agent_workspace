"""Safe git state reader test (Phase 6 verification)."""
from __future__ import annotations

from cto_os_api.git_reader import GitReader


def test_git_status_is_read_only(repository):
    reader = GitReader()
    status = reader.status(repository)

    assert status.repository_id == repository.id
    # tiny_repo fixture left README.md modified after the initial commit
    assert any("README.md" in path for path in status.changed_files)
    assert status.current_branch  # whatever branch git defaults to


def test_git_diff_only_returns_body_when_requested(repository):
    reader = GitReader()

    stats_only = reader.diff(repository, include_diff=False)
    assert stats_only.diff_text == ""

    with_body = reader.diff(repository, include_diff=True)
    assert "README" in with_body.diff_text or with_body.diff_stats
