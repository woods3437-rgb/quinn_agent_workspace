"use client";

import { useEffect, useState } from "react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { MCPAuditEvent, api } from "@/lib/api";

export default function ProjectMcpAuditPage({ params }: { params: { id: string } }) {
  const [events, setEvents] = useState<MCPAuditEvent[]>([]);

  async function load() {
    setEvents(await api.projectMcpAudit(params.id));
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">Project</div>
        <h1>MCP Audit</h1>
      </div>
      <ProjectTabs projectId={params.id} />
      <section className="stack">
        {events.length === 0 && <p>No audit events for this project.</p>}
        {events.map((event) => (
          <article className="card stack" key={event.id}>
            <div className="spread">
              <h3>
                {event.tool_name} · {event.action_type}
              </h3>
              <span className="badge">
                {event.blocked ? "blocked" : "ok"}
                {event.readonly_mode ? " · readonly" : ""}
              </span>
            </div>
            <small>
              session: {event.session_id} · {new Date(event.created_at).toLocaleString()}
            </small>
            <details>
              <summary>Request summary</summary>
              <pre className="output">{event.request_summary}</pre>
            </details>
          </article>
        ))}
      </section>
    </div>
  );
}
