"use client";

import { useEffect, useState } from "react";
import { HealthHistorySummary, SystemHealth, api } from "@/lib/api";

const STATUS_LABEL: Record<string, string> = {
  ok: "OK",
  degraded: "DEGRADED",
  down: "DOWN"
};

export default function HealthPage() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [history, setHistory] = useState<HealthHistorySummary | null>(null);
  const [error, setError] = useState("");

  async function load() {
    try {
      const [now, hist] = await Promise.all([api.systemHealth(), api.healthHistory()]);
      setHealth(now);
      setHistory(hist);
      setError("");
    } catch (err) {
      setError(String((err as Error).message ?? err));
    }
  }

  async function snapshot() {
    await api.healthSnapshot();
    await load();
  }

  useEffect(() => {
    load();
  }, []);

  if (error) {
    return (
      <div className="stack">
        <h1>Health</h1>
        <p className="warn">{error}</p>
      </div>
    );
  }
  if (!health) {
    return (
      <div className="stack">
        <h1>Health</h1>
        <p>Loading…</p>
      </div>
    );
  }

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">System</div>
        <h1>
          Health — <span className={`badge ${health.status}`}>{STATUS_LABEL[health.status]}</span>
        </h1>
        <p>Generated {new Date(health.generated_at).toLocaleString()}</p>
        <div className="row">
          <button className="button secondary" onClick={load}>
            Refresh
          </button>
          <button className="button secondary" onClick={snapshot}>
            Save snapshot now
          </button>
        </div>
      </div>
      {history && (
        <section className="grid">
          <article className="card">
            <h2>Last 24h</h2>
            <p>{history.sample_count_24h} samples</p>
            <p>{history.degraded_count_24h} degraded</p>
          </article>
          <article className="card">
            <h2>Last 7d</h2>
            <p>{history.sample_count_7d} samples</p>
            <p>{history.degraded_count_7d} degraded · {history.down_count_7d} down</p>
          </article>
          <article className="card">
            <h2>Latest degraded reasons</h2>
            {history.latest_degraded_reasons.length === 0 && <p>(none)</p>}
            <ul>
              {history.latest_degraded_reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </article>
        </section>
      )}
      <section className="grid">
        <article className="card">
          <h2>SQLite</h2>
          <pre className="output">{JSON.stringify(health.sqlite, null, 2)}</pre>
        </article>
        <article className="card">
          <h2>MemPalace</h2>
          <pre className="output">{JSON.stringify(health.mempalace, null, 2)}</pre>
        </article>
        <article className="card">
          <h2>MCP</h2>
          <pre className="output">{JSON.stringify(health.mcp, null, 2)}</pre>
        </article>
        <article className="card">
          <h2>GitHub</h2>
          <pre className="output">{JSON.stringify(health.github, null, 2)}</pre>
        </article>
        <article className="card">
          <h2>Intake</h2>
          <pre className="output">{JSON.stringify(health.intake, null, 2)}</pre>
        </article>
        <article className="card">
          <h2>Notifications</h2>
          <pre className="output">{JSON.stringify(health.notifications, null, 2)}</pre>
        </article>
        <article className="card">
          <h2>Backups</h2>
          <pre className="output">{JSON.stringify(health.backups, null, 2)}</pre>
        </article>
      </section>
      <section className="stack">
        <h2>Workers</h2>
        {health.workers.length === 0 && <p>No workers have written a heartbeat yet.</p>}
        {health.workers.map((worker) => (
          <article className="card" key={worker.id}>
            <strong>{worker.worker_name}</strong> · pid {worker.pid} · {worker.status}
            <small> · last seen {new Date(worker.last_seen_at).toLocaleString()}</small>
          </article>
        ))}
      </section>
      <section className="stack">
        <h2>Recent failures</h2>
        <article className="card">
          <h3>Failed jobs</h3>
          {health.recent_failed_jobs.length === 0 && <p>None.</p>}
          {health.recent_failed_jobs.map((job) => (
            <p key={job.id}>
              {job.title} — {job.error_message}
            </p>
          ))}
        </article>
        <article className="card">
          <h3>Failed/blocked GitHub writes</h3>
          {health.recent_failed_write_events.length === 0 && <p>None.</p>}
          {health.recent_failed_write_events.map((event) => (
            <p key={event.id}>
              {event.action} → {event.status} — {event.error_message}
            </p>
          ))}
        </article>
        <article className="card">
          <h3>Dismissed status suggestions</h3>
          {health.recent_blocked_suggestions.length === 0 && <p>None.</p>}
          {health.recent_blocked_suggestions.map((sugg) => (
            <p key={sugg.id}>
              {sugg.entity_type}/{sugg.entity_id} → {sugg.suggested_status}
            </p>
          ))}
        </article>
      </section>
    </div>
  );
}
