"use client";

import { useEffect, useState } from "react";
import { BuildSession, Repository, Task, api } from "@/lib/api";
import { ProjectTabs } from "@/components/ProjectTabs";

export default function BuildSessionsPage({ params }: { params: { id: string } }) {
  const [sessions, setSessions] = useState<BuildSession[]>([]);
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [repositoryId, setRepositoryId] = useState("");
  const [taskId, setTaskId] = useState("");
  const [title, setTitle] = useState("");

  async function load() {
    const [sessionItems, repoItems, taskItems] = await Promise.all([api.buildSessions(params.id), api.repositories(params.id), api.tasks(params.id)]);
    setSessions(sessionItems); setRepositories(repoItems); setTasks(taskItems);
    if (!repositoryId && repoItems[0]) setRepositoryId(repoItems[0].id);
  }
  useEffect(() => { load(); }, []);

  async function create() {
    if (!title) return;
    await api.createBuildSession(params.id, { title, repository_id: repositoryId || null, task_id: taskId || null, status: "planning" });
    setTitle("");
    await load();
  }

  async function summarize(session: BuildSession) {
    await api.summarizeBuildSession(params.id, session.id);
    await load();
  }

  async function saveLessons(session: BuildSession) {
    await api.saveBuildSessionLessons(params.id, session.id);
  }

  return (
    <div className="stack">
      <div><div className="eyebrow">Build Timeline</div><h1>Build Sessions</h1><p>Connect tasks, branch plans, test runs, reviews, and lessons into one timeline.</p></div>
      <ProjectTabs projectId={params.id} />
      <section className="panel stack">
        <div className="grid">
          <label className="field"><span>Repository</span><select value={repositoryId} onChange={(e) => setRepositoryId(e.target.value)}><option value="">None</option>{repositories.map((repo) => <option value={repo.id} key={repo.id}>{repo.name}</option>)}</select></label>
          <label className="field"><span>Task</span><select value={taskId} onChange={(e) => setTaskId(e.target.value)}><option value="">None</option>{tasks.map((task) => <option value={task.id} key={task.id}>{task.title}</option>)}</select></label>
        </div>
        <label className="field"><span>Title</span><input value={title} onChange={(e) => setTitle(e.target.value)} /></label>
        <button className="button" onClick={create}>Create build session</button>
      </section>
      <section className="stack">{sessions.map((session) => <article className="card stack" key={session.id}><div className="spread"><h2>{session.title}</h2><span className="badge">{session.status}</span></div><p>{session.summary || "No summary yet."}</p><div className="row"><button className="button secondary" onClick={() => summarize(session)}>Summarize</button><button className="button secondary" onClick={() => saveLessons(session)}>Save lessons to memory</button></div></article>)}</section>
    </div>
  );
}
