from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any

import httpx

from .github_write_guard import GitHubWriteError, GitHubWriteGuard
from .models import GitHubIssue, GitHubPullRequest, Repository


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


_PR_REF_RE = re.compile(r"#(\d+)")


class GitHubIntegration:
    """Read-mostly GitHub boundary for the private CTO OS.

    Phase 5 added status + sync. Phase 6 kept it strictly read. Phase 7 adds a
    *narrow* set of writes — create issue, create branch, create draft PR —
    all funnelled through ``GitHubWriteGuard``. Merge, delete, force-push,
    visibility changes, collaborator changes are not implemented and never
    will be.
    """

    def __init__(self, guard: GitHubWriteGuard | None = None) -> None:
        self.guard = guard or GitHubWriteGuard()

    # ------------------------------------------------------------------ read

    def status(self) -> dict[str, object]:
        token = os.getenv("GITHUB_TOKEN", "")
        owner = os.getenv("GITHUB_DEFAULT_OWNER", "")
        return {
            "configured": bool(token),
            "default_owner_configured": bool(owner),
            "writes_enabled": self.guard.env_writes_allowed(),
            "capabilities": ["config_validation", "issue_sync", "pr_sync"],
            "write_capabilities": ["create_issue", "create_branch", "create_draft_pr"],
            "disabled_capabilities": [
                "merge_pr",
                "delete_repo",
                "delete_branch",
                "force_push",
                "update_secrets",
                "change_visibility",
                "invite_collaborator",
                "create_public_repo",
            ],
            "message": (
                "GitHub writes require CTO_OS_ALLOW_GITHUB_WRITES=1, a valid "
                "GITHUB_TOKEN, and explicit per-call approval."
            ),
        }

    def list_repositories(self) -> list[dict[str, Any]]:
        token = os.getenv("GITHUB_TOKEN", "")
        owner = os.getenv("GITHUB_DEFAULT_OWNER", "")
        if not token or not owner:
            return []
        response = httpx.get(
            f"https://api.github.com/users/{owner}/repos",
            headers=self._headers(),
            timeout=20,
        )
        response.raise_for_status()
        return [
            {
                "name": repo["name"],
                "url": repo["html_url"],
                "default_branch": repo.get("default_branch", "main"),
            }
            for repo in response.json()
        ]

    def sync_repository(
        self, project_id: str, repository: Repository
    ) -> tuple[list[GitHubIssue], list[GitHubPullRequest]]:
        token = os.getenv("GITHUB_TOKEN", "")
        if not token:
            return [], []
        owner, repo_name = self._owner_and_name(repository)
        if not owner:
            return [], []
        response = httpx.get(
            f"https://api.github.com/repos/{owner}/{repo_name}/issues?state=all&per_page=25",
            headers=self._headers(),
            timeout=20,
        )
        response.raise_for_status()
        issues: list[GitHubIssue] = []
        prs: list[GitHubPullRequest] = []
        for item in response.json():
            if "pull_request" in item:
                # Items returned from the issues endpoint do not include
                # merge / draft state. Fetch the PR detail when present.
                detail: dict[str, Any] = {}
                try:
                    detail_response = httpx.get(
                        f"https://api.github.com/repos/{owner}/{repo_name}/pulls/{item['number']}",
                        headers=self._headers(),
                        timeout=20,
                    )
                    detail_response.raise_for_status()
                    detail = detail_response.json()
                except Exception:
                    detail = {}
                prs.append(self._pr_from(project_id, repository, {**item, **detail}))
            else:
                issues.append(self._issue_from(project_id, repository, item))
        return issues, prs

    def fetch_issue_state(self, repository: Repository, number: int) -> dict[str, Any]:
        token = os.getenv("GITHUB_TOKEN", "")
        if not token:
            return {}
        owner, repo_name = self._owner_and_name(repository)
        if not owner:
            return {}
        response = httpx.get(
            f"https://api.github.com/repos/{owner}/{repo_name}/issues/{number}",
            headers=self._headers(),
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def fetch_pr_state(self, repository: Repository, number: int) -> dict[str, Any]:
        token = os.getenv("GITHUB_TOKEN", "")
        if not token:
            return {}
        owner, repo_name = self._owner_and_name(repository)
        if not owner:
            return {}
        response = httpx.get(
            f"https://api.github.com/repos/{owner}/{repo_name}/pulls/{number}",
            headers=self._headers(),
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def _issue_from(
        self, project_id: str, repository: Repository, payload: dict[str, Any]
    ) -> GitHubIssue:
        labels = [
            label.get("name") if isinstance(label, dict) else str(label)
            for label in payload.get("labels", [])
        ]
        linked_pr: int | None = None
        body = payload.get("body") or ""
        match = _PR_REF_RE.search(body)
        if match:
            try:
                linked_pr = int(match.group(1))
            except ValueError:
                linked_pr = None
        return GitHubIssue(
            project_id=project_id,
            repository_id=repository.id,
            number=payload["number"],
            title=payload.get("title", ""),
            state=payload.get("state", ""),
            url=payload.get("html_url", ""),
            labels=[label for label in labels if label],
            closed_at=_parse_iso(payload.get("closed_at")),
            linked_pr_number=linked_pr,
        )

    def _pr_from(
        self, project_id: str, repository: Repository, payload: dict[str, Any]
    ) -> GitHubPullRequest:
        return GitHubPullRequest(
            project_id=project_id,
            repository_id=repository.id,
            number=payload["number"],
            title=payload.get("title", ""),
            state=payload.get("state", ""),
            url=payload.get("html_url", ""),
            summary=payload.get("body") or "",
            draft=bool(payload.get("draft", False)),
            merged=bool(payload.get("merged", False)),
            merged_at=_parse_iso(payload.get("merged_at")),
            closed_at=_parse_iso(payload.get("closed_at")),
            base_branch=(payload.get("base") or {}).get("ref", "") if isinstance(payload.get("base"), dict) else "",
            head_branch=(payload.get("head") or {}).get("ref", "") if isinstance(payload.get("head"), dict) else "",
            additions=int(payload.get("additions", 0) or 0),
            deletions=int(payload.get("deletions", 0) or 0),
            changed_files=int(payload.get("changed_files", 0) or 0),
        )

    # ----------------------------------------------------------------- write

    def create_issue(
        self,
        repository: Repository,
        payload: dict[str, Any],
        approved: bool,
        dry_run: bool,
    ) -> dict[str, Any]:
        self.guard.require_writeable("create_issue", approved=approved, dry_run=dry_run)
        owner, repo_name = self._require_owner_and_name(repository)
        response = httpx.post(
            f"https://api.github.com/repos/{owner}/{repo_name}/issues",
            headers=self._headers(),
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def create_branch(
        self,
        repository: Repository,
        branch_name: str,
        base_branch: str,
        approved: bool,
        dry_run: bool,
    ) -> dict[str, Any]:
        self.guard.require_writeable("create_branch", approved=approved, dry_run=dry_run)
        owner, repo_name = self._require_owner_and_name(repository)
        base = base_branch or repository.default_branch or "main"
        ref_response = httpx.get(
            f"https://api.github.com/repos/{owner}/{repo_name}/git/ref/heads/{base}",
            headers=self._headers(),
            timeout=20,
        )
        ref_response.raise_for_status()
        sha = ref_response.json().get("object", {}).get("sha")
        if not sha:
            raise GitHubWriteError(
                f"Could not resolve base SHA for {base} on {owner}/{repo_name}."
            )
        create_response = httpx.post(
            f"https://api.github.com/repos/{owner}/{repo_name}/git/refs",
            headers=self._headers(),
            json={"ref": f"refs/heads/{branch_name}", "sha": sha},
            timeout=20,
        )
        create_response.raise_for_status()
        return create_response.json()

    def create_draft_pr(
        self,
        repository: Repository,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
        approved: bool,
        dry_run: bool,
        reviewers: list[str] | None = None,
    ) -> dict[str, Any]:
        self.guard.require_writeable(
            "create_draft_pr", approved=approved, dry_run=dry_run
        )
        owner, repo_name = self._require_owner_and_name(repository)
        payload = {
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch or repository.default_branch or "main",
            "draft": True,
            "maintainer_can_modify": False,
        }
        response = httpx.post(
            f"https://api.github.com/repos/{owner}/{repo_name}/pulls",
            headers=self._headers(),
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        result = response.json()
        if reviewers:
            number = result.get("number")
            if number is not None:
                httpx.post(
                    f"https://api.github.com/repos/{owner}/{repo_name}/pulls/{number}/requested_reviewers",
                    headers=self._headers(),
                    json={"reviewers": reviewers},
                    timeout=20,
                )
        return result

    # ---------------------------------------------------------------- helpers

    def _headers(self) -> dict[str, str]:
        token = os.getenv("GITHUB_TOKEN", "")
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _owner_and_name(self, repository: Repository) -> tuple[str, str]:
        owner = os.getenv("GITHUB_DEFAULT_OWNER", "")
        repo_name = repository.name
        if repository.url and "github.com" in repository.url:
            parts = repository.url.rstrip("/").split("/")
            if len(parts) >= 2:
                owner = parts[-2]
                repo_name = parts[-1].removesuffix(".git")
        return owner, repo_name

    def _require_owner_and_name(self, repository: Repository) -> tuple[str, str]:
        owner, repo_name = self._owner_and_name(repository)
        if not owner or not repo_name:
            raise GitHubWriteError(
                "Cannot resolve GitHub owner/repo. Set GITHUB_DEFAULT_OWNER or "
                "repository.url to a github.com URL."
            )
        return owner, repo_name
