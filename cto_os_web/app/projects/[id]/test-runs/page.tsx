"use client";

import { useEffect, useState } from "react";
import { Repository, Task, TestRun, api } from "@/lib/api";
import { ProjectTabs } from "@/components/ProjectTabs";

export default function TestRunsPage({ params }: { params: { id: string } }) {
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [repositoryId, setRepositoryId] = useState("");
  const [taskId, setTaskId] = useState("");
  const [command, setCommand] = useState("");
  const [status, setStatus] = useState<TestRun["status"]>("not_run");
  const [output, setOutput] = useState("");

  async function load() {
    const [repoItems, taskItems, runItems] = await Promise.all([api.repositories(params.id), api.tasks(params.id), api.testRuns(params.id)]);
    setRepositories(repoItems); setTasks(taskItems); setRuns(runItems);
    if (!repositoryId && repoItems[0]) setRepositoryId(repoItems[0].id);
  }
  useEffect(() => { load(); }, []);

  async function create() {
    if (!repositoryId || !command) return;
    await api.createTestRun(params.id, { repository_id: repositoryId, task_id: taskId || undefined, command, status, output });
    setCommand(""); setOutput("");
    await load();
  }

  return (
    <div className="stack">
      <div><div className="eyebrow">Verification Ledger</div><h1>Test Runs</h1><p>Record test/build/lint commands and results. CTO OS tracks, but does not execute shell commands here.</p></div>
      <ProjectTabs projectId={params.id} />
      <section className="panel stack">
        <div className="grid">
          <label className="field"><span>Repository</span><select value={repositoryId} onChange={(e) => setRepositoryId(e.target.value)}>{repositories.map((repo) => <option value={repo.id} key={repo.id}>{repo.name}</option>)}</select></label>
          <label className="field"><span>Task</span><select value={taskId} onChange={(e) => setTaskId(e.target.value)}><option value="">None</option>{tasks.map((task) => <option value={task.id} key={task.id}>{task.title}</option>)}</select></label>
          <label className="field"><span>Status</span><select value={status} onChange={(e) => setStatus(e.target.value as TestRun["status"])}>{["not_run", "passed", "failed", "skipped"].map((item) => <option key={item}>{item}</option>)}</select></label>
        </div>
        <label className="field"><span>Command</span><input value={command} onChange={(e) => setCommand(e.target.value)} /></label>
        <label className="field"><span>Output</span><textarea value={output} onChange={(e) => setOutput(e.target.value)} /></label>
        <button className="button" onClick={create}>Record test run</button>
      </section>
      <section className="stack">{runs.map((run) => <article className="card stack" key={run.id}><div className="spread"><h2>{run.command}</h2><span className="badge">{run.status}</span></div><div className="output">{run.output || "No output recorded."}</div></article>)}</section>
    </div>
  );
}
