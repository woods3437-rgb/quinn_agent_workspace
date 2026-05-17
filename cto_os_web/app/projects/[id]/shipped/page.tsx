"use client";

import { useEffect, useState } from "react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { ShippedSummary, api } from "@/lib/api";

export default function ShippedPage({ params }: { params: { id: string } }) {
  const [summary, setSummary] = useState<ShippedSummary | null>(null);

  async function load() {
    setSummary(await api.shippedDashboard(params.id));
  }

  useEffect(() => {
    load();
  }, []);

  if (!summary) {
    return (
      <div className="stack">
        <h1>Shipped</h1>
        <ProjectTabs projectId={params.id} />
        <p>Loading…</p>
      </div>
    );
  }

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">Lifecycle Loop</div>
        <h1>What We Shipped</h1>
        <p>Aggregate of completed work in this project, distinct from the planning-focused weekly brief.</p>
      </div>
      <ProjectTabs projectId={params.id} />
      <section className="grid">
        <article className="card">
          <h2>Velocity</h2>
          <p>
            <strong>{summary.velocity_7d}</strong> tasks completed in the last 7 days
          </p>
          <p>
            <strong>{summary.velocity_30d}</strong> tasks completed in the last 30 days
          </p>
        </article>
        <article className="card">
          <h2>Completed build sessions</h2>
          <p>{summary.completed_build_sessions.length}</p>
        </article>
        <article className="card">
          <h2>Merged PRs</h2>
          <p>{summary.merged_pull_requests.length}</p>
        </article>
        <article className="card">
          <h2>Closed issues</h2>
          <p>{summary.closed_issues.length}</p>
        </article>
      </section>
      <section className="stack">
        <h2>Completed tasks</h2>
        {summary.completed_tasks.length === 0 && <p>No completed tasks yet.</p>}
        {summary.completed_tasks.map((task) => (
          <article className="card" key={task.id}>
            <h3>{task.title}</h3>
            <p>{task.description}</p>
            {task.github_issue_url && (
              <p>
                <a href={task.github_issue_url}>#{task.github_issue_number}</a>
              </p>
            )}
          </article>
        ))}
      </section>
      <section className="stack">
        <h2>Lessons learned</h2>
        {summary.lessons_learned.length === 0 && <p>No lessons recorded yet.</p>}
        {summary.lessons_learned.map((memory) => (
          <article className="card" key={memory.id}>
            <h3>{memory.title}</h3>
            <p>{memory.content}</p>
          </article>
        ))}
      </section>
      <section className="stack">
        <h2>Follow-up tasks</h2>
        {summary.follow_up_tasks.length === 0 && <p>No follow-up tasks.</p>}
        {summary.follow_up_tasks.map((task) => (
          <article className="card" key={task.id}>
            <h3>{task.title}</h3>
            <p>{task.description}</p>
          </article>
        ))}
      </section>
    </div>
  );
}
