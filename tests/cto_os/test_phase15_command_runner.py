"""Phase 15 — CommandRunner allows safe git reads, still blocks writes."""
from __future__ import annotations

import pytest

from cto_os_api.command_runner import CommandRunner, CommandSafetyError
from cto_os_api.models import ApprovedCommandCreate, ApprovedCommandType


@pytest.mark.parametrize(
    "cmd",
    [
        "git status",
        "git status --porcelain",
        "git diff --stat",
        "git log --oneline -5",
        "git check-ignore fix.sh",
        "git ls-files",
        "git ls-files src/",
        "git show-ref",
        "git branch --show-current",
        "git rev-parse HEAD",
    ],
)
def test_git_read_subcommands_allowed(store, project, repository, cmd):
    runner = CommandRunner(store)
    approved = runner.approve(
        project.id, repository.id,
        ApprovedCommandCreate(command=cmd, command_type=ApprovedCommandType.test),
    )
    assert approved.command == cmd


@pytest.mark.parametrize(
    "cmd",
    [
        "git commit -m hi",
        "git push",
        "git push origin main",
        "git reset --hard HEAD~1",
        "git checkout -- .",
        "git checkout main",
        "git merge feature",
        "git rebase -i HEAD~2",
        "git clean -fd",
        "git pull",
        "git fetch --prune",
        "git config --global user.name foo",  # config not in allow-list
        "git remote set-url origin foo",
        "git branch -D feature",
        "git branch --delete feature",
    ],
)
def test_git_write_subcommands_still_blocked(store, project, repository, cmd):
    runner = CommandRunner(store)
    with pytest.raises(CommandSafetyError):
        runner.approve(
            project.id, repository.id,
            ApprovedCommandCreate(command=cmd, command_type=ApprovedCommandType.test),
        )


def test_regular_blocks_still_apply(store, project, repository):
    runner = CommandRunner(store)
    for bad in ["rm -rf /", "sudo reboot", "npm install foo", "git commit"]:
        with pytest.raises(CommandSafetyError):
            runner.approve(
                project.id, repository.id,
                ApprovedCommandCreate(command=bad, command_type=ApprovedCommandType.test),
            )


def test_npm_test_still_allowed(store, project, repository):
    runner = CommandRunner(store)
    runner.approve(
        project.id, repository.id,
        ApprovedCommandCreate(command="npm test", command_type=ApprovedCommandType.test),
    )
