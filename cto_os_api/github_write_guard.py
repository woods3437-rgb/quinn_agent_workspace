"""Phase 7 — central GitHub write safety gate.

Every GitHub mutation in the private CTO OS funnels through ``GitHubWriteGuard``
so we keep the safety story in one place. The gate enforces three independent
checks and a hard-coded denylist of operations that the CTO OS will never
support, regardless of approval state.
"""
from __future__ import annotations

import os
import re

# Hard ban — no method may ever be added for any of these. Tested at import
# time so a future maintainer can't accidentally smuggle one in.
BLOCKED_GITHUB_OPS = frozenset(
    {
        "merge_pr",
        "delete_repo",
        "delete_branch",
        "force_push",
        "update_secrets",
        "change_visibility",
        "invite_collaborator",
        "create_public_repo",
    }
)

_ALLOWED_OPS = frozenset(
    {
        "create_issue",
        "create_branch",
        "create_draft_pr",
    }
)

# Branch names: only [a-zA-Z0-9-_/.] survive. We collapse runs, strip leading
# dots/slashes (which git refuses), and clamp length.
_SANITISE = re.compile(r"[^a-zA-Z0-9\-_/.]")


class GitHubWriteError(RuntimeError):
    """Raised when a GitHub mutation is not permitted."""


class GitHubWriteGuard:
    """Three-gate guard for GitHub mutations.

    Gate 1: ``CTO_OS_ALLOW_GITHUB_WRITES`` env var must be ``"1"``.
    Gate 2: ``GITHUB_TOKEN`` env var must be present.
    Gate 3: the caller must pass ``approved=True`` and ``dry_run=False``.
    """

    def assert_action_permitted(self, action: str) -> None:
        if action in BLOCKED_GITHUB_OPS:
            raise GitHubWriteError(
                f"Operation '{action}' is permanently blocked by CTO OS policy."
            )
        if action not in _ALLOWED_OPS:
            raise GitHubWriteError(f"Unknown GitHub write action: {action}")

    def env_writes_allowed(self) -> bool:
        return os.getenv("CTO_OS_ALLOW_GITHUB_WRITES", "0").strip() == "1"

    def token_present(self) -> bool:
        return bool(os.getenv("GITHUB_TOKEN", "").strip())

    def gate_reason(self, action: str, approved: bool, dry_run: bool) -> str | None:
        """Return ``None`` when the call may proceed, else a human reason."""
        try:
            self.assert_action_permitted(action)
        except GitHubWriteError as exc:
            return str(exc)
        if dry_run:
            return "dry_run is true; nothing was sent to GitHub."
        if not approved:
            return "Caller did not set approved=true; refusing to send."
        if not self.env_writes_allowed():
            return "CTO_OS_ALLOW_GITHUB_WRITES is not set to 1; refusing to send."
        if not self.token_present():
            return "GITHUB_TOKEN is not configured; refusing to send."
        return None

    def require_writeable(self, action: str, approved: bool, dry_run: bool) -> None:
        reason = self.gate_reason(action, approved, dry_run)
        if reason is not None:
            raise GitHubWriteError(reason)


def sanitise_branch_name(name: str, fallback: str = "cto-change") -> str:
    """Produce a safe git branch name.

    Empty / unsafe input collapses to ``fallback``. We refuse anything that
    git itself would reject (leading dot, slash, double-slash, ``..``,
    trailing dot/slash) by sanitising rather than raising — Phase 7 is a
    helper, not a validator.
    """
    cleaned = _SANITISE.sub("-", (name or "").strip())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-./")
    cleaned = cleaned.replace("..", "-")
    cleaned = cleaned.lstrip("/")
    cleaned = cleaned[:80]
    return cleaned or fallback
