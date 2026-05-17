"use client";

import { useEffect, useState } from "react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { Job, api } from "@/lib/api";

export default function JobsPage({ params }: { params: { id: string } }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [type, setType] = useState<Job["type"]>("risk_scan");
  const [status, setStatus] = useState("");

  async function load() {
    setJobs(await api.jobs(params.id, { status, type: "" }));
  }

  useEffect(() => {
    load();
  }, [status]);

  async function createAndRun() {
    const job = await api.createJob(params.id, { type, title: `Run ${type.replaceAll("_", " ")}`, payload_json: {} });
    await api.runJob(params.id, job.id);
    await load();
  }

  async function retry(job: Job) {
    await api.runJob(params.id, job.id);
    await load();
  }

  return (
    <div className="stack">
      <div><div className="eyebrow">Execution Engine</div><h1>Jobs</h1><p>Local queue for repeatable long-running CTO OS operations.</p></div>
      <ProjectTabs projectId={params.id} />
      <section className="panel row">
        <select value={type} onChange={(event) => setType(event.target.value as Job["type"])}>
          {["semantic_indexing", "llm_generation", "weekly_brief", "risk_scan", "implementation_review", "import_export", "github_packet"].map((item) => <option key={item}>{item}</option>)}
        </select>
        <select value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">All statuses</option>
          {["queued", "running", "completed", "failed", "cancelled"].map((item) => <option key={item}>{item}</option>)}
        </select>
        <button className="button" onClick={createAndRun}>Create and run</button>
      </section>
      <section className="stack">
        {jobs.map((job) => (
          <article className="card stack" key={job.id}>
            <div className="spread"><h2>{job.title}</h2><span className="badge">{job.status}</span></div>
            <p>{job.type} · attempts {job.attempts} · {new Date(job.updated_at).toLocaleString()}</p>
            {job.error_message && <div className="output">{job.error_message}</div>}
            {Object.keys(job.result_json || {}).length > 0 && <div className="output">{JSON.stringify(job.result_json, null, 2)}</div>}
            <div className="row">
              {job.status === "failed" && <button className="button secondary" onClick={() => retry(job)}>Retry failed job</button>}
              {job.status === "queued" && <button className="button secondary" onClick={() => retry(job)}>Run now</button>}
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}
