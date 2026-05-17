"use client";

import { useEffect, useMemo, useState } from "react";
import { AuditVerificationReport, MCPAuditEvent, api } from "@/lib/api";

export default function MCPAuditPage() {
  const [events, setEvents] = useState<MCPAuditEvent[]>([]);
  const [toolFilter, setToolFilter] = useState("");
  const [sessionFilter, setSessionFilter] = useState("");
  const [blockedFilter, setBlockedFilter] = useState<"all" | "true" | "false">("all");
  const [readonlyFilter, setReadonlyFilter] = useState<"all" | "true" | "false">("all");
  const [signatureFilter, setSignatureFilter] = useState<"all" | "signed" | "unsigned">("all");
  const [verification, setVerification] = useState<AuditVerificationReport | null>(null);

  async function load() {
    const params: Parameters<typeof api.filteredMcpAudit>[0] = { limit: 500 };
    if (toolFilter) params.tool_name = toolFilter;
    if (sessionFilter) params.session_id = sessionFilter;
    if (blockedFilter !== "all") params.blocked = blockedFilter === "true";
    if (readonlyFilter !== "all") params.readonly = readonlyFilter === "true";
    setEvents(await api.filteredMcpAudit(params));
  }

  useEffect(() => {
    load();
  }, []);

  const filtered = useMemo(() => {
    if (signatureFilter === "all") return events;
    return events.filter((e) =>
      signatureFilter === "signed" ? !!e.signature : !e.signature
    );
  }, [events, signatureFilter]);

  async function verify() {
    setVerification(await api.verifyMcpAudit(500));
  }

  function exportJson() {
    const blob = new Blob([JSON.stringify(filtered, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `mcp-audit-${new Date().toISOString()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">System</div>
        <h1>MCP Audit</h1>
        <p>
          Append-only log of every MCP write attempt — including blocked read-only attempts.
          Stores tool name, arg key names (never values), session id, project id, outcome, and an
          optional HMAC signature when <code>CTO_OS_AUDIT_SIGNING_KEY</code> is set.
        </p>
      </div>
      <section className="panel row">
        <label className="field">
          <span>Tool</span>
          <input value={toolFilter} onChange={(e) => setToolFilter(e.target.value)} placeholder="create_task" />
        </label>
        <label className="field">
          <span>Session id</span>
          <input value={sessionFilter} onChange={(e) => setSessionFilter(e.target.value)} />
        </label>
        <label className="field">
          <span>Blocked</span>
          <select value={blockedFilter} onChange={(e) => setBlockedFilter(e.target.value as typeof blockedFilter)}>
            <option value="all">all</option>
            <option value="true">true</option>
            <option value="false">false</option>
          </select>
        </label>
        <label className="field">
          <span>Read-only</span>
          <select value={readonlyFilter} onChange={(e) => setReadonlyFilter(e.target.value as typeof readonlyFilter)}>
            <option value="all">all</option>
            <option value="true">true</option>
            <option value="false">false</option>
          </select>
        </label>
        <label className="field">
          <span>Signature</span>
          <select
            value={signatureFilter}
            onChange={(e) => setSignatureFilter(e.target.value as typeof signatureFilter)}
          >
            <option value="all">all</option>
            <option value="signed">signed</option>
            <option value="unsigned">unsigned</option>
          </select>
        </label>
        <button className="button secondary" onClick={load}>
          Apply
        </button>
        <button className="button secondary" onClick={verify}>
          Verify signatures
        </button>
        <button className="button secondary" onClick={exportJson}>
          Export JSON
        </button>
      </section>
      {verification && (
        <section className="panel">
          <p>
            Verified <strong>{verification.valid}</strong> / signed{" "}
            <strong>{verification.signed}</strong> / unsigned{" "}
            <strong>{verification.unsigned}</strong> / tampered{" "}
            <strong>{verification.tampered}</strong> / key_missing{" "}
            <strong>{verification.key_missing}</strong> across{" "}
            <strong>{verification.checked}</strong> rows.
          </p>
        </section>
      )}
      <section className="stack">
        {filtered.length === 0 && <p>No matching audit events.</p>}
        {filtered.map((event) => (
          <article className="card stack" key={event.id}>
            <div className="spread">
              <h3>
                {event.tool_name} · {event.action_type}
              </h3>
              <span className="badge">
                {event.blocked ? "blocked" : "ok"}
                {event.readonly_mode ? " · readonly" : ""}
                {event.signature ? " · signed" : " · unsigned"}
              </span>
            </div>
            <small>
              session: {event.session_id} · project: {event.project_id ?? "—"} ·{" "}
              {new Date(event.created_at).toLocaleString()}
            </small>
            <details>
              <summary>Request summary</summary>
              <pre className="output">{event.request_summary}</pre>
            </details>
            <details>
              <summary>Response summary</summary>
              <pre className="output">{event.response_summary}</pre>
            </details>
          </article>
        ))}
      </section>
    </div>
  );
}
