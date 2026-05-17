"use client";

import { useEffect, useState } from "react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { WorkflowRun, api } from "@/lib/api";

export default function WorkflowsPage({ params }: { params: { id: string } }) {
  const [defaults, setDefaults] = useState<Record<string, Array<Record<string, unknown>>>>({});
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [selected, setSelected] = useState("Weekly CTO Review");

  async function load() {
    const [workflowDefaults, workflowRuns] = await Promise.all([api.defaultWorkflows(), api.workflows(params.id)]);
    setDefaults(workflowDefaults);
    setRuns(workflowRuns);
    setSelected(Object.keys(workflowDefaults)[0] ?? "Weekly CTO Review");
  }

  useEffect(() => {
    load();
  }, []);

  async function run() {
    await api.runWorkflow(params.id, { name: selected, payload_json: {} });
    await load();
  }

  return (
    <div className="stack">
      <div><div className="eyebrow">Operational Workflows</div><h1>Workflows</h1><p>Reusable chains for CTO reviews, risk scans, architecture refreshes, and build packets.</p></div>
      <ProjectTabs projectId={params.id} />
      <section className="panel stack">
        <div className="row">
          <select value={selected} onChange={(event) => setSelected(event.target.value)}>
            {Object.keys(defaults).map((name) => <option key={name}>{name}</option>)}
          </select>
          <button className="button" onClick={run}>Run workflow</button>
        </div>
        <div className="output">{JSON.stringify(defaults[selected] ?? [], null, 2)}</div>
      </section>
      <section className="stack">
        {runs.map((run) => (
          <article className="card stack" key={run.id}>
            <div className="spread"><h2>{run.name}</h2><span className="badge">{run.status}</span></div>
            <p>{run.result_summary || "No result yet."}</p>
            <div className="output">{JSON.stringify(run.steps, null, 2)}</div>
          </article>
        ))}
      </section>
    </div>
  );
}
