"use client";

import { useEffect, useState } from "react";
import { CronCadence, CronJob, CronJobType, CronRunResult, api } from "@/lib/api";

const CADENCES: CronCadence[] = ["manual", "hourly", "daily", "weekly"];
const TYPES: CronJobType[] = [
  "daily_review",
  "weekly_review",
  "backup",
  "health_snapshot",
  "risk_scan",
  "github_reconcile"
];

export default function CronSettingsPage() {
  const [jobs, setJobs] = useState<CronJob[]>([]);
  const [lastRun, setLastRun] = useState<CronRunResult | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setJobs(await api.cronJobs());
  }

  useEffect(() => {
    load();
  }, []);

  async function toggle(job: CronJob) {
    await api.updateCronJob(job.id, { enabled: !job.enabled });
    await load();
  }

  async function setCadence(job: CronJob, cadence: CronCadence) {
    await api.updateCronJob(job.id, { cadence });
    await load();
  }

  async function setProject(job: CronJob, project_id: string) {
    await api.updateCronJob(job.id, { project_id: project_id || null });
    await load();
  }

  async function run(job: CronJob) {
    setBusy(true);
    try {
      setLastRun(await api.runCronJob(job.id));
      await load();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">Settings</div>
        <h1>Cron</h1>
        <p>
          Internal scheduler. <strong>Disabled by default.</strong> Worker picks up enabled jobs
          on each polling loop. Cron never starts an LLM call — <code>weekly_review</code> uses{" "}
          <code>CTO_OS_LLM_PROVIDER</code> (deterministic by default, so no API call).
        </p>
      </div>
      {lastRun && (
        <section className="panel">
          <strong>Last run:</strong> {lastRun.job.name} → ran={String(lastRun.ran)}{" "}
          {lastRun.reason && `· ${lastRun.reason}`}
          {lastRun.output_summary && <pre className="output">{lastRun.output_summary}</pre>}
        </section>
      )}
      <section className="stack">
        {jobs.map((job) => (
          <article className="card stack" key={job.id}>
            <div className="spread">
              <h3>
                {job.name} <small>({job.job_type})</small>
              </h3>
              <span className="badge">{job.enabled ? "enabled" : "disabled"}</span>
            </div>
            <div className="row">
              <label className="field">
                <span>Cadence</span>
                <select value={job.cadence} onChange={(e) => setCadence(job, e.target.value as CronCadence)}>
                  {CADENCES.map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Project id (for project-scoped jobs)</span>
                <input
                  value={job.project_id ?? ""}
                  onChange={(e) => setProject(job, e.target.value)}
                  placeholder="proj_..."
                />
              </label>
            </div>
            <p>
              <small>
                status: {job.status} · last run: {job.last_run_at ?? "never"} · next run:{" "}
                {job.next_run_at ?? "—"}
                {job.last_error && ` · last error: ${job.last_error}`}
              </small>
            </p>
            <div className="row">
              <button className="button secondary" onClick={() => toggle(job)}>
                {job.enabled ? "Disable" : "Enable"}
              </button>
              <button className="button" onClick={() => run(job)} disabled={busy || !job.enabled}>
                Run now
              </button>
            </div>
          </article>
        ))}
        {jobs.length === 0 && <p>No cron jobs yet. The worker seeds the six defaults on first boot.</p>}
      </section>
    </div>
  );
}
