"use client";

import { useEffect, useState } from "react";
import { IntakeEvent, api } from "@/lib/api";

export default function IntakeSettingsPage() {
  const [events, setEvents] = useState<IntakeEvent[]>([]);
  const [error, setError] = useState<string>("");

  async function load() {
    try {
      setEvents(await api.intakeEvents());
      setError("");
    } catch (err) {
      setError(String((err as Error).message ?? err));
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">Settings</div>
        <h1>Webhook Intake</h1>
        <p>
          Intake is off by default. Set <code>CTO_OS_ENABLE_WEBHOOK_INTAKE=1</code> AND
          <code> CTO_OS_WEBHOOK_SECRET</code> to a non-empty string, then POST to{" "}
          <code>/intake/events</code> with header{" "}
          <code>X-CTO-OS-Signature: sha256=&lt;hmac-sha256(body, secret)&gt;</code>.
          Events are stored as <code>IntakeEvent</code> rows; CTO OS never auto-runs an LLM
          in response — it only creates a single <code>StatusSuggestion</code> when{" "}
          <code>?create_suggestion=1</code> is passed.
        </p>
      </div>
      <section className="panel">
        <h2>Accepted sources</h2>
        <ul>
          <li><code>linear.issue.created</code></li>
          <li><code>linear.issue.updated</code></li>
          <li><code>sentry.issue.created</code></li>
          <li><code>github.webhook.raw</code></li>
          <li><code>manual.note</code></li>
        </ul>
      </section>
      <section className="stack">
        <h2>Recent events</h2>
        {error && <p className="warn">{error}</p>}
        {!error && events.length === 0 && <p>No intake events yet.</p>}
        {events.map((event) => (
          <article className="card stack" key={event.id}>
            <div className="spread">
              <h3>{event.source}</h3>
              <small>{new Date(event.received_at).toLocaleString()}</small>
            </div>
            <p>
              project_id: {event.project_id ?? "—"} · suggestion_id:{" "}
              {event.suggestion_id ?? "—"}
            </p>
            {event.note && <p>{event.note}</p>}
            <details>
              <summary>Payload</summary>
              <pre className="output">{JSON.stringify(event.payload, null, 2)}</pre>
            </details>
          </article>
        ))}
      </section>
    </div>
  );
}
