"use client";

import { useEffect, useState } from "react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { ExecutionLog, api } from "@/lib/api";

export default function LogsPage({ params }: { params: { id: string } }) {
  const [logs, setLogs] = useState<ExecutionLog[]>([]);

  useEffect(() => {
    api.logs(params.id).then(setLogs);
  }, []);

  return (
    <div className="stack">
      <div><div className="eyebrow">Operational Control</div><h1>Execution Logs</h1><p>Automatic record of generation, task, decision, memory, and review events.</p></div>
      <ProjectTabs projectId={params.id} />
      <section className="stack">
        {logs.map((log) => (
          <article className="card stack" key={log.id}>
            <div className="spread"><h2>{log.title}</h2><span className="badge">{log.event_type}</span></div>
            <p>{log.summary || "No summary."}</p>
            <span className="muted">{new Date(log.created_at).toLocaleString()}</span>
          </article>
        ))}
      </section>
    </div>
  );
}
