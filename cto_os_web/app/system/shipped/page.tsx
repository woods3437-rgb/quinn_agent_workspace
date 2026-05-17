"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { SystemShippedSummary, api } from "@/lib/api";

export default function SystemShippedPage() {
  const [summary, setSummary] = useState<SystemShippedSummary | null>(null);

  useEffect(() => {
    api.systemShipped().then(setSummary);
  }, []);

  if (!summary) {
    return (
      <div className="stack">
        <h1>System Shipped</h1>
        <p>Loading…</p>
      </div>
    );
  }

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">System</div>
        <h1>What We Shipped (all projects)</h1>
      </div>
      <section className="grid">
        <article className="card">
          <h2>Velocity 7d</h2>
          <p>{summary.velocity_7d}</p>
        </article>
        <article className="card">
          <h2>Velocity 30d</h2>
          <p>{summary.velocity_30d}</p>
        </article>
        <article className="card">
          <h2>Velocity 90d</h2>
          <p>{summary.velocity_90d}</p>
        </article>
        <article className="card">
          <h2>Completed build sessions</h2>
          <p>{summary.completed_build_sessions}</p>
        </article>
        <article className="card">
          <h2>Merged PRs</h2>
          <p>{summary.merged_pull_requests}</p>
        </article>
        <article className="card">
          <h2>Closed issues</h2>
          <p>{summary.closed_issues}</p>
        </article>
      </section>
      <section className="stack">
        <h2>Per project</h2>
        {summary.projects.map((project) => (
          <article className="card" key={project.project_id}>
            <div className="spread">
              <h3>
                <Link href={`/projects/${project.project_id}/shipped`}>{project.name}</Link>
              </h3>
              <small>
                7d: {project.velocity_7d} · 30d: {project.velocity_30d} · 90d: {project.velocity_90d}
              </small>
            </div>
            <p>
              build sessions: {project.completed_build_sessions} · merged PRs: {project.merged_pull_requests} · closed
              issues: {project.closed_issues} · done tasks: {project.completed_tasks}
            </p>
          </article>
        ))}
      </section>
    </div>
  );
}
