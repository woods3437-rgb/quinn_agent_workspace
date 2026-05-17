"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { RiskConcentrationSummary, api } from "@/lib/api";

export default function SystemRisksPage() {
  const [summary, setSummary] = useState<RiskConcentrationSummary | null>(null);

  useEffect(() => {
    api.systemRisks().then(setSummary);
  }, []);

  if (!summary) {
    return (
      <div className="stack">
        <h1>System Risks</h1>
        <p>Loading…</p>
      </div>
    );
  }

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">System</div>
        <h1>Risk Concentration</h1>
      </div>
      <section className="panel">
        <h2>Recurring themes</h2>
        {summary.recurring_themes.length === 0 && <p>No recurring keywords across risks.</p>}
        <ul>
          {summary.recurring_themes.map((theme) => (
            <li key={theme}>{theme}</li>
          ))}
        </ul>
      </section>
      <section className="stack">
        {summary.groups.map((group) => (
          <article className="card" key={group.project_id}>
            <div className="spread">
              <h2>
                <Link href={`/projects/${group.project_id}/risks`}>{group.name}</Link>
              </h2>
              <small>{group.open_critical_high} open critical/high</small>
            </div>
            <p>
              severity: {Object.entries(group.severity_counts).map(([k, v]) => `${k}=${v}`).join(", ") || "none"}
            </p>
            <p>without mitigation: {group.risks_without_mitigation.length}</p>
            <p>linked to stale tasks: {group.risks_linked_to_stale_tasks.length}</p>
          </article>
        ))}
      </section>
    </div>
  );
}
