"use client";

import { useEffect, useState } from "react";
import { MCPSession, api } from "@/lib/api";

export default function MCPSessionsPage() {
  const [sessions, setSessions] = useState<MCPSession[]>([]);
  const [sessionId, setSessionId] = useState("");
  const [label, setLabel] = useState("");
  const [readonly, setReadonly] = useState(false);

  async function load() {
    setSessions(await api.mcpSessions());
  }

  useEffect(() => {
    load();
  }, []);

  async function create() {
    if (!sessionId) return;
    await api.createMCPSession({ session_id: sessionId, label, readonly });
    setSessionId("");
    setLabel("");
    setReadonly(false);
    await load();
  }

  async function toggleReadonly(session: MCPSession) {
    await api.updateMCPSession(session.session_id, { readonly: !session.readonly });
    await load();
  }

  async function revoke(session: MCPSession) {
    await api.revokeMCPSession(session.session_id);
    await load();
  }

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">System</div>
        <h1>MCP Sessions</h1>
        <p>
          Per-session identity for MCP calls. Sessions are auto-created on first use
          (resolved from <code>params._meta.sessionId</code> → <code>CTO_OS_MCP_SESSION_ID</code> →{" "}
          <code>unknown</code>). Revoke a session to refuse all of its calls; set
          read-only to refuse only write tools.
        </p>
      </div>
      <section className="panel stack">
        <h2>Pre-create a session</h2>
        <label className="field">
          <span>Session id (opaque)</span>
          <input value={sessionId} onChange={(e) => setSessionId(e.target.value)} />
        </label>
        <label className="field">
          <span>Label</span>
          <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. cofounder-advisor" />
        </label>
        <label className="field">
          <span>Read-only</span>
          <input type="checkbox" checked={readonly} onChange={(e) => setReadonly(e.target.checked)} />
        </label>
        <button className="button" onClick={create} disabled={!sessionId}>
          Create
        </button>
      </section>
      <section className="stack">
        {sessions.map((session) => (
          <article className="card stack" key={session.id}>
            <div className="spread">
              <h3>
                {session.session_id} {session.label && <small>· {session.label}</small>}
              </h3>
              <span className="badge">
                {session.revoked ? "revoked" : session.readonly ? "read-only" : "active"}
              </span>
            </div>
            <small>
              last seen {new Date(session.last_seen_at).toLocaleString()} · created{" "}
              {new Date(session.created_at).toLocaleString()}
            </small>
            <div className="row">
              <button
                className="button secondary"
                onClick={() => toggleReadonly(session)}
                disabled={session.revoked}
              >
                {session.readonly ? "Make writable" : "Make read-only"}
              </button>
              <button className="button" onClick={() => revoke(session)} disabled={session.revoked}>
                Revoke
              </button>
            </div>
          </article>
        ))}
        {sessions.length === 0 && <p>No sessions yet.</p>}
      </section>
    </div>
  );
}
