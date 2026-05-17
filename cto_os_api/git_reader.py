from __future__ import annotations

import subprocess
from pathlib import Path

from .models import GitDiff, GitStatus, Repository
from .repo_scanner import RepoScanner


class GitReader:
    def __init__(self) -> None:
        self.scanner = RepoScanner()

    def status(self, repository: Repository) -> GitStatus:
        root = self.scanner.resolve_root(repository)
        branch = self._run(root, ["git", "branch", "--show-current"])
        porcelain = self._run(root, ["git", "status", "--porcelain"], strip=False)
        staged: list[str] = []
        unstaged: list[str] = []
        changed: list[str] = []
        for line in porcelain.splitlines():
            if len(line) < 4:
                continue
            path = line[3:]
            changed.append(path)
            if line[0] != " " and line[0] != "?":
                staged.append(path)
            if line[1] != " " or line[0] == "?":
                unstaged.append(path)
        commits = self._run(root, ["git", "log", "--oneline", "-5"]).splitlines()
        diff_stats = self._run(root, ["git", "diff", "--stat"])
        return GitStatus(
            repository_id=repository.id,
            current_branch=branch.strip(),
            status_summary=porcelain.strip() or "clean",
            changed_files=changed,
            staged_files=staged,
            unstaged_files=unstaged,
            recent_commits=commits,
            diff_stats=diff_stats,
        )

    def diff(self, repository: Repository, include_diff: bool = False) -> GitDiff:
        root = self.scanner.resolve_root(repository)
        stats = self._run(root, ["git", "diff", "--stat"])
        diff_text = self._run(root, ["git", "diff"], strip=False) if include_diff else ""
        return GitDiff(repository_id=repository.id, diff_text=diff_text, diff_stats=stats)

    # Phase 15 — safe read-only conveniences used by MCP tools + the
    # /code-reviews/from-git route. Wrappers around ``git`` subcommands the
    # CommandRunner now allows.

    def read_diff(self, repository: Repository, paths: list[str] | None = None) -> str:
        """Return the unified diff body (working tree vs HEAD).

        ``paths`` optionally narrows the diff to a specific path list.
        """
        root = self.scanner.resolve_root(repository)
        args = ["git", "diff"]
        if paths:
            args.append("--")
            args.extend(paths)
        return self._run(root, args, strip=False)

    def check_ignore(
        self, repository: Repository, paths: list[str]
    ) -> dict[str, list[str]]:
        """Return which of ``paths`` are gitignored vs not.

        Uses ``git check-ignore -v`` so we can distinguish "not ignored"
        from "no .gitignore in repo". Output is grouped into two lists.
        """
        root = self.scanner.resolve_root(repository)
        if not paths:
            return {"ignored": [], "not_ignored": []}
        try:
            result = subprocess.run(
                ["git", "check-ignore", "--no-index", "--verbose", *paths],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception as exc:
            return {"ignored": [], "not_ignored": list(paths), "error": str(exc)}
        ignored: list[str] = []
        for line in (result.stdout or "").splitlines():
            # check-ignore --verbose output: "<source>:<lineno>:<pattern>\t<path>"
            if "\t" in line:
                ignored.append(line.split("\t", 1)[1].strip())
        ignored_set = set(ignored)
        not_ignored = [p for p in paths if p not in ignored_set]
        return {"ignored": ignored, "not_ignored": not_ignored}

    def ls_files(
        self, repository: Repository, pattern: str | None = None, limit: int = 500
    ) -> list[str]:
        """List tracked + untracked-but-not-ignored files (capped)."""
        root = self.scanner.resolve_root(repository)
        args = ["git", "ls-files", "--cached", "--others", "--exclude-standard"]
        if pattern:
            args.append(pattern)
        raw = self._run(root, args, strip=False)
        out = [line.strip() for line in raw.splitlines() if line.strip()]
        return out[:limit]

    def _run(self, cwd: Path, args: list[str], strip: bool = True) -> str:
        try:
            result = subprocess.run(
                args,
                cwd=cwd,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception as exc:
            return str(exc)
        output = result.stdout if result.stdout else result.stderr
        return output.strip() if strip else output.rstrip("\n")
