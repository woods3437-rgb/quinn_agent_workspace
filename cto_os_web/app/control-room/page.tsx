"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ControlRoomSummary, api } from "@/lib/api";

export default function ControlRoomPage() {
  const [summary, setSummary] = useState<ControlRoomSummary | null>(null);

  useEffect(() => {
    api.systemControlRoom().then(setSummary);
  }, []);

  if (!summary) {
    return (
      <div className="stack">
        <h1>Control Room</h1>
        <p>Loading…</p>
      </div>
    );
  }

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">System</div>
        <h1>Control Room</h1>
        <p>One-glance status across every project.</p>
      </div>
      <section className="grid">
        <article className="card">
          <h2>Open risks</h2>
          <p>{summary.open_risks_total}</p>
        </article>
        <article className="card">
          <h2>Blocked tasks</h2>
          <p>{summary.blocked_tasks_total}</p>
        </article>
        <article className="card">
          <h2>Pending suggestions</h2>
          <p>{summary.pending_suggestions_total}</p>
        </article>
        <article className="card">
          <h2>Stale projects</h2>
          <p>{summary.stale_projects.length}</p>
        </article>
      </section>
      <section className="stack">
        <h2>Recommended next actions</h2>
        {summary.recommended_next_actions.length === 0 && <p>Nothing urgent.</p>}
        <ul>
          {summary.recommended_next_actions.map((action) => (
            <li key={action}>{action}</li>
          ))}
        </ul>
      </section>
      <section className="stack">
        <h2>Active projects</h2>
        {summary.active_projects.map((project) => (
          <article className="card" key={project.project_id}>
            <div className="spread">
              <h3>
                <Link href={`/projects/${project.project_id}`}>{project.name}</Link>
              </h3>
              <small>
                {project.open_risks} risks · {project.blocked_tasks} blocked · {project.pending_suggestions} pending ·{" "}
                {project.completed_sessions_7d} shipped (7d)
              </small>
            </div>
          </article>
        ))}
      </section>
      <section className="stack">
        <h2>Recent activity</h2>
        <article className="card">
          <h3>Completed build sessions</h3>
          <ul>
            {summary.recent_completed_sessions.map((session) => (
              <li key={session.id}>{session.title}</li>
            ))}
            {summary.recent_completed_sessions.length === 0 && <li>None.</li>}
          </ul>
        </article>
        <article className="card">
          <h3>Retrospectives</h3>
          <ul>
            {summary.recent_retrospectives.map((retro) => (
              <li key={retro.id}>{retro.title}</li>
            ))}
            {summary.recent_retrospectives.length === 0 && <li>None.</li>}
          </ul>
        </article>
        <article className="card">
          <h3>GitHub writes</h3>
          <ul>
            {summary.recent_github_write_events.map((event) => (
              <li key={event.id}>
                {event.action} → {event.status}
              </li>
            ))}
            {summary.recent_github_write_events.length === 0 && <li>None.</li>}
          </ul>
        </article>
        <article className="card">
          <h3>Jobs needing attention</h3>
          <ul>
            {summary.jobs_needing_attention.map((job) => (
              <li key={job.id}>
                {job.title} — {job.status}
              </li>
            ))}
            {summary.jobs_needing_attention.length === 0 && <li>None.</li>}
          </ul>
        </article>
      </section>
    </div>
  );
}
