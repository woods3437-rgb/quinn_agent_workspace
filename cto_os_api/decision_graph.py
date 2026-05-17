"""Phase 9 — decision graph builder (per-project and system-wide).

Returns a graph view suitable for either list/tree rendering or a future
force-directed layout. Cross-project graphs expose only titles + IDs to keep
project memory isolation intact.
"""
from __future__ import annotations

from .models import DecisionGraph, DecisionGraphEdge, DecisionGraphNode
from .sqlite_store import SQLiteStore


MAX_DECISIONS_PER_PROJECT = 50


class DecisionGraphBuilder:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def project(self, project_id: str) -> DecisionGraph:
        self.store.get_project(project_id)
        return self._build([project_id])

    def system(self) -> DecisionGraph:
        return self._build([project.id for project in self.store.list_projects()])

    def _build(self, project_ids: list[str]) -> DecisionGraph:
        nodes: dict[str, DecisionGraphNode] = {}
        edges: list[DecisionGraphEdge] = []

        for project_id in project_ids:
            decisions = self.store.list_decisions(project_id)[:MAX_DECISIONS_PER_PROJECT]
            tasks = {task.id: task for task in self.store.list_tasks(project_id)}
            memories = {memory.id: memory for memory in self.store.list_memories(project_id=project_id)}
            risks = {risk.id: risk for risk in self.store.list_risks(project_id)}
            retros = self.store.list_retrospectives(project_id)
            retros_by_decision: dict[str, list[str]] = {}
            for retro in retros:
                for decision_id in retro.decision_ids_created:
                    retros_by_decision.setdefault(decision_id, []).append(retro.id)

            for decision in decisions:
                self._node(nodes, decision.id, "decision", decision.title, project_id)
                if decision.supersedes_decision_id:
                    self._node(
                        nodes,
                        decision.supersedes_decision_id,
                        "decision",
                        decision.supersedes_decision_id,
                        project_id,
                    )
                    edges.append(
                        DecisionGraphEdge(
                            source=decision.id,
                            target=decision.supersedes_decision_id,
                            relation="supersedes",
                        )
                    )
                for task_id in decision.linked_task_ids[:5]:
                    task = tasks.get(task_id)
                    if not task:
                        continue
                    self._node(nodes, task.id, "task", task.title, project_id)
                    edges.append(
                        DecisionGraphEdge(
                            source=decision.id, target=task.id, relation="linked_to_task"
                        )
                    )
                for output_id in decision.linked_output_ids[:3]:
                    self._node(nodes, output_id, "output", output_id, project_id)
                    edges.append(
                        DecisionGraphEdge(
                            source=decision.id, target=output_id, relation="linked_to_output"
                        )
                    )
                for retro_id in retros_by_decision.get(decision.id, []):
                    self._node(nodes, retro_id, "retrospective", retro_id, project_id)
                    edges.append(
                        DecisionGraphEdge(
                            source=retro_id,
                            target=decision.id,
                            relation="produced_by_retrospective",
                        )
                    )

            # risks that mitigated by tasks linked to decisions
            for risk in risks.values():
                for task_id in risk.linked_task_ids:
                    if task_id in tasks:
                        self._node(nodes, risk.id, "risk", risk.title, project_id)
                        self._node(nodes, task_id, "task", tasks[task_id].title, project_id)
                        edges.append(
                            DecisionGraphEdge(
                                source=task_id, target=risk.id, relation="mitigates_risk"
                            )
                        )

            # memories linked into decisions (decisions don't directly link
            # to memory ids, so we surface pinned memories as influence nodes)
            for memory in list(memories.values())[:20]:
                if memory.pinned:
                    self._node(nodes, memory.id, "memory", memory.title, project_id)

        return DecisionGraph(nodes=list(nodes.values()), edges=edges)

    def _node(
        self,
        nodes: dict[str, DecisionGraphNode],
        node_id: str,
        kind: str,
        title: str,
        project_id: str,
    ) -> None:
        if node_id in nodes:
            return
        nodes[node_id] = DecisionGraphNode(
            id=node_id, kind=kind, title=title, project_id=project_id
        )
