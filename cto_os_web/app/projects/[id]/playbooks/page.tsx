"use client";

import { useEffect, useState } from "react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { BuildSession, Playbook, Task, api } from "@/lib/api";

export default function ProjectPlaybooksPage({ params }: { params: { id: string } }) {
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [sessions, setSessions] = useState<BuildSession[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [sessionId, setSessionId] = useState("");
  const [taskId, setTaskId] = useState("");
  const [name, setName] = useState("");
  const [category, setCategory] = useState("engineering");
  const [selectedPlaybook, setSelectedPlaybook] = useState("");

  async function load() {
    const [pbs, s, t] = await Promise.all([
      api.projectPlaybooks(params.id),
      api.buildSessions(params.id),
      api.tasks(params.id)
    ]);
    setPlaybooks(pbs);
    setSessions(s);
    setTasks(t);
    if (!sessionId && s[0]) setSessionId(s[0].id);
    if (!taskId && t[0]) setTaskId(t[0].id);
    if (!selectedPlaybook && pbs[0]) setSelectedPlaybook(pbs[0].id);
  }

  useEffect(() => {
    load();
  }, []);

  async function generate() {
    if (!sessionId) return;
    await api.generatePlaybook(params.id, sessionId, { name: name || undefined, category });
    setName("");
    await load();
  }

  async function apply() {
    if (!taskId || !selectedPlaybook) return;
    await api.applyPlaybook(params.id, taskId, { playbook_id: selectedPlaybook });
  }

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">Project</div>
        <h1>Playbooks</h1>
      </div>
      <ProjectTabs projectId={params.id} />
      <section className="panel stack">
        <h2>Generate from build session</h2>
        <label className="field">
          <span>Build session</span>
          <select value={sessionId} onChange={(e) => setSessionId(e.target.value)}>
            {sessions.map((s) => (
              <option value={s.id} key={s.id}>
                {s.title} ({s.status})
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="field">
          <span>Category</span>
          <input value={category} onChange={(e) => setCategory(e.target.value)} />
        </label>
        <button className="button" onClick={generate} disabled={!sessionId}>
          Generate playbook
        </button>
      </section>
      <section className="panel stack">
        <h2>Apply playbook to task</h2>
        <label className="field">
          <span>Playbook</span>
          <select value={selectedPlaybook} onChange={(e) => setSelectedPlaybook(e.target.value)}>
            {playbooks.map((pb) => (
              <option value={pb.id} key={pb.id}>
                {pb.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Task</span>
          <select value={taskId} onChange={(e) => setTaskId(e.target.value)}>
            {tasks.map((t) => (
              <option value={t.id} key={t.id}>
                {t.title}
              </option>
            ))}
          </select>
        </label>
        <button className="button secondary" onClick={apply} disabled={!selectedPlaybook || !taskId}>
          Apply (creates a new output)
        </button>
      </section>
      <section className="stack">
        <h2>Project playbooks</h2>
        {playbooks.map((pb) => (
          <article className="card" key={pb.id}>
            <h3>{pb.name}</h3>
            <p>{pb.description}</p>
            <ol>
              {pb.steps.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
          </article>
        ))}
      </section>
    </div>
  );
}
