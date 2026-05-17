"""Phase 9 — Playbook service.

Generates reusable playbooks from successful build sessions. Sanitises any
step text that looks like a secret or env file path so a playbook can be
safely shared across projects.
"""
from __future__ import annotations

import re

from .models import (
    BuildSession,
    GeneratedOutput,
    Playbook,
    PlaybookApplyRequest,
    PlaybookCreate,
    PlaybookGenerateRequest,
    Task,
)
from .sqlite_store import SQLiteStore


_SECRET_RE = re.compile(r"(?i)(password|secret|api[_-]?key|token)\s*[:=]")
_ENV_FILE_RE = re.compile(r"(?i)\.env(\.[a-z]+)?\b")


def _safe(text: str) -> bool:
    if not text:
        return False
    if _SECRET_RE.search(text):
        return False
    if _ENV_FILE_RE.search(text):
        return False
    return True


def sanitise_steps(steps: list[str]) -> list[str]:
    return [step for step in steps if _safe(step)]


class PlaybookService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def generate(
        self,
        project_id: str,
        session_id: str,
        request: PlaybookGenerateRequest,
    ) -> Playbook:
        session = self._session(project_id, session_id)
        steps = self._steps_from_session(project_id, session)
        acceptance = self._acceptance_from_session(project_id, session)
        risks = self._risks_from_session(project_id, session)
        title = request.name or f"Playbook from {session.title}"
        description = (
            f"Auto-generated from completed build session '{session.title}' in project {project_id}. "
            "Review and edit before reuse."
        )
        playbook = self.store.create_playbook(
            PlaybookCreate(
                source_project_id=project_id,
                source_build_session_id=session.id,
                name=title,
                description=description,
                category=request.category,
                trigger_conditions=[
                    f"Task category matches '{request.category}'",
                    "Similar acceptance criteria",
                ],
                steps=sanitise_steps(steps),
                required_inputs=["Linked task or build packet"],
                expected_outputs=[
                    "Build packet ready to hand off",
                    "Branch plan with sanitised files-to-change list",
                ],
                risks=sanitise_steps(risks),
                acceptance_criteria=sanitise_steps(acceptance),
            )
        )
        return playbook

    def apply(
        self,
        project_id: str,
        task_id: str,
        request: PlaybookApplyRequest,
    ) -> GeneratedOutput:
        playbook = self.store.get_playbook(request.playbook_id)
        task = self.store.get_task(project_id, task_id)
        output_text = self._render_application(task, playbook)
        output = GeneratedOutput(
            project_id=project_id,
            agent_id="engineering-builder",
            prompt=f"Apply playbook '{playbook.name}' to task {task.title}",
            output=output_text,
            metadata={
                "output_type": "playbook_application",
                "playbook_id": playbook.id,
                "task_id": task.id,
            },
        )
        self.store.save_output(output)
        return output

    # ------------------------------------------------------------- internal

    def _session(self, project_id: str, session_id: str) -> BuildSession:
        session = next(
            (item for item in self.store.list_build_sessions(project_id) if item.id == session_id),
            None,
        )
        if session is None:
            raise KeyError(session_id)
        return session

    def _steps_from_session(self, project_id: str, session: BuildSession) -> list[str]:
        steps: list[str] = []
        if session.linked_build_packet_id:
            try:
                packet = self.store.get_build_packet(project_id, session.linked_build_packet_id)
                steps.extend(packet.implementation_steps)
            except KeyError:
                pass
        if session.linked_branch_plan_id:
            try:
                plan = self.store.get_branch_plan(project_id, session.linked_branch_plan_id)
                steps.extend(plan.implementation_steps)
            except KeyError:
                pass
        if not steps:
            steps.append("Capture the smallest viable plan from the linked task.")
            steps.append("Identify files to change before writing code.")
            steps.append("Run the detected test/build commands before requesting review.")
        return steps

    def _acceptance_from_session(self, project_id: str, session: BuildSession) -> list[str]:
        acceptance: list[str] = []
        if session.task_id:
            try:
                task = self.store.get_task(project_id, session.task_id)
                acceptance.extend(task.acceptance_criteria)
            except KeyError:
                pass
        if session.linked_build_packet_id:
            try:
                packet = self.store.get_build_packet(project_id, session.linked_build_packet_id)
                acceptance.extend(packet.acceptance_criteria)
            except KeyError:
                pass
        return acceptance or ["Tests/checks recorded.", "No secrets in diff."]

    def _risks_from_session(self, project_id: str, session: BuildSession) -> list[str]:
        risks: list[str] = []
        if session.linked_branch_plan_id:
            try:
                plan = self.store.get_branch_plan(project_id, session.linked_branch_plan_id)
                risks.extend(plan.risk_notes)
            except KeyError:
                pass
        return risks

    def _render_application(self, task: Task, playbook: Playbook) -> str:
        lines = [
            f"# Applying playbook: {playbook.name}",
            "",
            f"## Target task: {task.title}",
            task.description or "(no description)",
            "",
            "## Steps",
        ]
        lines.extend(f"- [ ] {step}" for step in playbook.steps)
        if playbook.acceptance_criteria:
            lines.append("")
            lines.append("## Acceptance criteria")
            lines.extend(f"- [ ] {item}" for item in playbook.acceptance_criteria)
        if playbook.risks:
            lines.append("")
            lines.append("## Risks to watch")
            lines.extend(f"- {item}" for item in playbook.risks)
        lines.append("")
        lines.append(
            f"_Playbook source: project {playbook.source_project_id} · session {playbook.source_build_session_id}_"
        )
        return "\n".join(lines)
