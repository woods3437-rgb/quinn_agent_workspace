from __future__ import annotations

import os
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .models import ApprovedCommand, ApprovedCommandCreate, TestRun, TestRunStatus
from .repo_scanner import RepoScanner
from .sqlite_store import SQLiteStore


# Phase 15: ``git`` removed from BLOCKED_WORDS — the binary alone isn't
# dangerous, only specific subcommands are. The validator now allows
# ``git <read-subcommand>`` (status/diff/log/check-ignore/ls-files/etc.)
# and rejects every other git invocation along with the explicit write
# tokens below.
BLOCKED_WORDS = {
    "rm", "sudo", "curl", "wget", "ssh", "scp",
    "publish", "install",
    "commit", "push", "reset", "checkout", "merge", "rebase", "clean",
    "pull", "fetch",
}
BLOCKED_CHARS = {"|", ">", "<", ";", "&", "`", "$("}
ALLOWED_PREFIXES = {
    "npm run", "pnpm run", "yarn",
    "python -m pytest", "pytest",
    "npx tsc",
    "npm test", "pnpm test", "yarn test",
    # Phase 15: explicit safe git read-only verbs.
    "git status", "git diff", "git log", "git check-ignore", "git ls-files",
    "git show-ref", "git branch --show-current", "git rev-parse",
}
GIT_READ_SUBCOMMANDS = {
    "status", "diff", "log", "check-ignore", "ls-files",
    "show-ref", "branch", "rev-parse",
}


class CommandSafetyError(ValueError):
    pass


class CommandRunner:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self.scanner = RepoScanner()

    def approve(self, project_id: str, repository_id: str, payload: ApprovedCommandCreate) -> ApprovedCommand:
        self.validate_command(payload.command)
        repository = self.store.get_repository(project_id, repository_id)
        root = self.scanner.resolve_root(repository)
        working = (root / payload.working_directory).resolve()
        if not str(working).startswith(str(root)):
            raise CommandSafetyError("Working directory must stay inside repository root.")
        return self.store.create_approved_command(project_id, repository_id, payload)

    def run(self, project_id: str, repository_id: str, command_id: str) -> TestRun:
        command = self.store.get_approved_command(project_id, repository_id, command_id)
        self.validate_command(command.command)
        repository = self.store.get_repository(project_id, repository_id)
        root = self.scanner.resolve_root(repository)
        cwd = (root / command.working_directory).resolve()
        if not str(cwd).startswith(str(root)):
            raise CommandSafetyError("Working directory must stay inside repository root.")
        args = shlex.split(command.command)
        try:
            result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=int(os.getenv("CTO_OS_COMMAND_TIMEOUT_SECONDS", "60")))
            output = (result.stdout + "\n" + result.stderr).strip()
            status = TestRunStatus.passed if result.returncode == 0 else TestRunStatus.failed
        except Exception as exc:
            output = str(exc)
            status = TestRunStatus.failed
        command.last_run_at = datetime.now(timezone.utc)
        self.store.save_approved_command(command)
        return self.store.save_test_run(TestRun(project_id=project_id, repository_id=repository_id, command=command.command, status=status, output=output))

    def validate_command(self, command: str) -> None:
        stripped = command.strip()
        if not stripped:
            raise CommandSafetyError("Command is required.")
        if any(char in stripped for char in BLOCKED_CHARS):
            raise CommandSafetyError("Shell control operators are not allowed.")
        tokens = shlex.split(stripped)
        if not tokens:
            raise CommandSafetyError("Command is required.")
        lowered = {token.lower() for token in tokens}
        if lowered & BLOCKED_WORDS:
            raise CommandSafetyError(f"Blocked command token: {sorted(lowered & BLOCKED_WORDS)[0]}")
        # Phase 15: special-case git — only the explicit read-only subcommand
        # allow-list passes. Anything else with ``git`` as the first token
        # is rejected even if a write token (commit/push) isn't present (e.g.
        # ``git remote set-url`` or ``git config --global``).
        if tokens[0].lower() == "git":
            if len(tokens) < 2 or tokens[1].lower() not in GIT_READ_SUBCOMMANDS:
                raise CommandSafetyError(
                    "git subcommand not on the read-only allow-list "
                    f"({sorted(GIT_READ_SUBCOMMANDS)})."
                )
            # `git branch` is read; `git branch -D foo` is delete. Refuse any
            # ``branch`` invocation that includes a delete/force flag.
            if tokens[1].lower() == "branch" and any(
                arg in {"-D", "-d", "--delete", "-m", "--move", "-c", "--copy", "-f", "--force"}
                for arg in tokens[2:]
            ):
                raise CommandSafetyError("git branch mutation flags are not allowed.")
        if not any(stripped.startswith(prefix) for prefix in ALLOWED_PREFIXES):
            raise CommandSafetyError("Command must be an approved test/lint/typecheck/build command.")
