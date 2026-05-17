"""Phase 15 — git_reader.check_ignore + ls_files + read_diff."""
from __future__ import annotations

from cto_os_api.git_reader import GitReader


def test_check_ignore_round_trip(repository):
    reader = GitReader()
    # README.md is tracked → not ignored. node_modules is gitignored in the
    # fixture's tiny repo (not present), so ask about a known-ignored path
    # via a fresh path that matches the .gitignore (the conftest fixture's
    # tiny repo has minimal .gitignore — use a structural example).
    out = reader.check_ignore(repository, ["README.md", "node_modules/foo"])
    assert "README.md" in out["not_ignored"]


def test_ls_files_returns_tracked_files(repository):
    reader = GitReader()
    files = reader.ls_files(repository)
    assert "README.md" in files


def test_read_diff_returns_string(repository):
    reader = GitReader()
    diff = reader.read_diff(repository)
    # Tiny fixture commits then writes README so there's usually a diff;
    # whether or not, the call must succeed and return a string.
    assert isinstance(diff, str)
