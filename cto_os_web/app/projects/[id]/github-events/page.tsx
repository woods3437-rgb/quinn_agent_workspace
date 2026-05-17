"use client";

import { useEffect, useState } from "react";
import { GitHubWriteEvent, api } from "@/lib/api";
import { ProjectTabs } from "@/components/ProjectTabs";

const STATUS_BADGE: Record<string, string> = {
  previewed: "muted",
  completed: "ok",
  failed: "warn",
  blocked: "warn"
};

export default function GitHubEventsPage({ params }: { params: { id: string } }) {
  const [events, setEvents] = useState<GitHubWriteEvent[]>([]);
  const [filter, setFilter] = useState<string>("");

  async function load() {
    setEvents(await api.githubWriteEvents(params.id));
  }

  useEffect(() => {
    load();
  }, []);

  const filtered = filter
    ? events.filter((event) => event.action === filter || event.entity_type === filter || event.status === filter)
    : events;

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">GitHub Write Audit</div>
        <h1>GitHub Events</h1>
        <p>
          Every preview, create, blocked, and failed GitHub write attempt is logged here. Writes are off by default;
          set <code>CTO_OS_ALLOW_GITHUB_WRITES=1</code> + approve per-call to actually send.
        </p>
      </div>
      <ProjectTabs projectId={params.id} />
      <section className="panel row">
        <label className="field">
          <span>Filter</span>
          <select value={filter} onChange={(event) => setFilter(event.target.value)}>
            <option value="">All</option>
            <option value="task">Task</option>
            <option value="risk">Risk</option>
            <option value="branch_plan">Branch plan</option>
            <option value="pr_packet">PR packet</option>
            <option value="previewed">Previewed</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="blocked">Blocked</option>
          </select>
        </label>
        <button className="button secondary" onClick={load}>
          Refresh
        </button>
      </section>
      <section className="stack">
        {filtered.length === 0 && <p>No GitHub write attempts yet.</p>}
        {filtered.map((event) => (
          <article className="card stack" key={event.id}>
            <div className="spread">
              <h2>
                {event.action} · {event.entity_type}/{event.entity_id}
              </h2>
              <span className={`badge ${STATUS_BADGE[event.status] ?? ""}`}>{event.status}</span>
            </div>
            <p>
              <strong>dry_run:</strong> {String(event.dry_run)} · <strong>approved:</strong> {String(event.approved)} ·{" "}
              <span>{new Date(event.created_at).toLocaleString()}</span>
            </p>
            {event.error_message && <p className="warn">{event.error_message}</p>}
            <details>
              <summary>Payload</summary>
              <pre className="output">{JSON.stringify(event.payload_json, null, 2)}</pre>
            </details>
            {Object.keys(event.response_json ?? {}).length > 0 && (
              <details>
                <summary>Response</summary>
                <pre className="output">{JSON.stringify(event.response_json, null, 2)}</pre>
              </details>
            )}
          </article>
        ))}
      </section>
    </div>
  );
}
