from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from threading import RLock
from typing import TypeVar

from pydantic import BaseModel

from .models import (
    Decision,
    DecisionCreate,
    GeneratedOutput,
    Memory,
    MemoryCreate,
    Project,
    ProjectCreate,
    PromptTemplate,
    PromptTemplateCreate,
    Task,
    TaskCreate,
    TaskUpdate,
    utc_now,
)

T = TypeVar("T", bound=BaseModel)


class JsonStore:
    def __init__(self, path: str | None = None) -> None:
        default_path = Path(__file__).parent / "data" / "cto_os.json"
        self.path = Path(path or os.getenv("CTO_OS_DATA_PATH", default_path))
        self.lock = RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(self._empty_data(), backup=False)

    def _empty_data(self) -> dict:
        return {
            "projects": [],
            "memories": [],
            "decisions": [],
            "outputs": [],
            "prompt_templates": [],
            "tasks": [],
        }

    def _read(self) -> dict:
        with self.lock:
            if not self.path.exists():
                self._write(self._empty_data(), backup=False)
            data = json.loads(self.path.read_text() or "{}")
            changed = False
            for key, value in self._empty_data().items():
                if key not in data:
                    data[key] = value
                    changed = True
            if changed:
                self._write(data)
            return data

    def _write(self, data: dict, backup: bool = True) -> None:
        with self.lock:
            if backup and self.path.exists():
                backup_dir = self.path.parent / "backups"
                backup_dir.mkdir(parents=True, exist_ok=True)
                stamp = utc_now().strftime("%Y%m%d%H%M%S%f")
                shutil.copy2(self.path, backup_dir / f"{self.path.stem}.{stamp}.json")

            content = json.dumps(data, indent=2, default=str) + "\n"
            with tempfile.NamedTemporaryFile("w", dir=self.path.parent, delete=False) as tmp:
                tmp.write(content)
                tmp_path = Path(tmp.name)
            tmp_path.replace(self.path)

    def _load_many(self, key: str, model: type[T]) -> list[T]:
        return [model.model_validate(item) for item in self._read().get(key, [])]

    def _save_many(self, key: str, items: list[BaseModel]) -> None:
        data = self._read()
        data[key] = [item.model_dump(mode="json") for item in items]
        self._write(data)

    def list_projects(self) -> list[Project]:
        return sorted(self._load_many("projects", Project), key=lambda p: p.updated_at, reverse=True)

    def create_project(self, payload: ProjectCreate) -> Project:
        project = Project(**payload.model_dump())
        projects = self.list_projects()
        projects.append(project)
        self._save_many("projects", projects)
        return project

    def get_project(self, project_id: str) -> Project:
        for project in self.list_projects():
            if project.id == project_id:
                return project
        raise KeyError(project_id)

    def touch_project(self, project_id: str) -> None:
        projects = self.list_projects()
        for project in projects:
            if project.id == project_id:
                project.updated_at = utc_now()
                break
        self._save_many("projects", projects)

    def list_memories(self, project_id: str | None = None, pinned: bool | None = None) -> list[Memory]:
        memories = self._load_many("memories", Memory)
        if project_id:
            memories = [memory for memory in memories if memory.project_id == project_id]
        if pinned is not None:
            memories = [memory for memory in memories if memory.pinned is pinned]
        return sorted(memories, key=lambda m: (m.pinned, m.updated_at), reverse=True)

    def create_memory(self, project_id: str, payload: MemoryCreate) -> Memory:
        self.get_project(project_id)
        memory = Memory(project_id=project_id, **payload.model_dump())
        memories = self._load_many("memories", Memory)
        memories.append(memory)
        self._save_many("memories", memories)
        self.touch_project(project_id)
        return memory

    def update_memory_pin(self, project_id: str, memory_id: str, pinned: bool) -> Memory:
        memories = self._load_many("memories", Memory)
        updated: Memory | None = None
        for memory in memories:
            if memory.id == memory_id and memory.project_id == project_id:
                memory.pinned = pinned
                memory.updated_at = utc_now()
                updated = memory
                break
        if updated is None:
            raise KeyError(memory_id)
        self._save_many("memories", memories)
        self.touch_project(project_id)
        return updated

    def list_decisions(self, project_id: str) -> list[Decision]:
        decisions = [d for d in self._load_many("decisions", Decision) if d.project_id == project_id]
        return sorted(decisions, key=lambda d: d.created_at, reverse=True)

    def create_decision(self, project_id: str, payload: DecisionCreate) -> Decision:
        self.get_project(project_id)
        decision = Decision(project_id=project_id, **payload.model_dump())
        decisions = self._load_many("decisions", Decision)
        decisions.append(decision)
        self._save_many("decisions", decisions)
        self.touch_project(project_id)
        return decision

    def list_tasks(self, project_id: str) -> list[Task]:
        tasks = [task for task in self._load_many("tasks", Task) if task.project_id == project_id]
        return sorted(tasks, key=lambda task: task.updated_at, reverse=True)

    def create_task(self, project_id: str, payload: TaskCreate) -> Task:
        self.get_project(project_id)
        task = Task(project_id=project_id, **payload.model_dump())
        tasks = self._load_many("tasks", Task)
        tasks.append(task)
        self._save_many("tasks", tasks)
        self.touch_project(project_id)
        return task

    def update_task(self, project_id: str, task_id: str, payload: TaskUpdate) -> Task:
        tasks = self._load_many("tasks", Task)
        updated: Task | None = None
        changes = payload.model_dump(exclude_unset=True)
        for task in tasks:
            if task.id == task_id and task.project_id == project_id:
                for key, value in changes.items():
                    setattr(task, key, value)
                task.updated_at = utc_now()
                updated = task
                break
        if updated is None:
            raise KeyError(task_id)
        self._save_many("tasks", tasks)
        self.touch_project(project_id)
        return updated

    def delete_task(self, project_id: str, task_id: str) -> None:
        tasks = self._load_many("tasks", Task)
        remaining = [task for task in tasks if not (task.id == task_id and task.project_id == project_id)]
        if len(remaining) == len(tasks):
            raise KeyError(task_id)
        self._save_many("tasks", remaining)
        self.touch_project(project_id)

    def list_outputs(self, project_id: str) -> list[GeneratedOutput]:
        outputs = [o for o in self._load_many("outputs", GeneratedOutput) if o.project_id == project_id]
        return sorted(outputs, key=lambda o: o.created_at, reverse=True)

    def save_output(self, output: GeneratedOutput) -> GeneratedOutput:
        outputs = self._load_many("outputs", GeneratedOutput)
        outputs.append(output)
        self._save_many("outputs", outputs)
        self.touch_project(output.project_id)
        return output

    def get_output(self, project_id: str, output_id: str) -> GeneratedOutput:
        for output in self.list_outputs(project_id):
            if output.id == output_id:
                return output
        raise KeyError(output_id)

    def list_prompt_templates(self, project_id: str | None = None, include_global: bool = True) -> list[PromptTemplate]:
        templates = self._load_many("prompt_templates", PromptTemplate)
        if project_id:
            templates = [
                template
                for template in templates
                if template.project_id == project_id or (include_global and template.project_id is None)
            ]
        return sorted(templates, key=lambda t: t.updated_at, reverse=True)

    def create_prompt_template(self, payload: PromptTemplateCreate) -> PromptTemplate:
        if not payload.template_body and payload.template:
            payload.template_body = payload.template
        if not payload.template and payload.template_body:
            payload.template = payload.template_body
        template = PromptTemplate(**payload.model_dump())
        templates = self._load_many("prompt_templates", PromptTemplate)
        templates.append(template)
        self._save_many("prompt_templates", templates)
        return template

    def save_prompt_template(self, template: PromptTemplate) -> PromptTemplate:
        templates = self._load_many("prompt_templates", PromptTemplate)
        templates.append(template)
        self._save_many("prompt_templates", templates)
        return template

    def get_prompt_template(self, template_id: str) -> PromptTemplate:
        for template in self._load_many("prompt_templates", PromptTemplate):
            if template.id == template_id:
                return template
        raise KeyError(template_id)

    def duplicate_prompt_template(self, template_id: str, project_id: str | None = None) -> PromptTemplate:
        original = self.get_prompt_template(template_id)
        duplicate = PromptTemplate(
            project_id=project_id if project_id is not None else original.project_id,
            name=f"{original.name} Copy",
            description=original.description,
            category=original.category,
            agent_type=original.agent_type,
            template_body=original.template_body or original.template,
            input_variables=original.input_variables,
            template=original.template or original.template_body,
            agent_id=original.agent_id,
        )
        return self.save_prompt_template(duplicate)
