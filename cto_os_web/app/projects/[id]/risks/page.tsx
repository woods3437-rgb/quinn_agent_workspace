"use client";

import { useEffect, useState } from "react";
import { ShieldAlert } from "lucide-react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { GitHubWriteEvent, Risk, api } from "@/lib/api";

export default function RisksPage({ params }: { params: { id: string } }) {
  const [risks, setRisks] = useState<Risk[]>([]);
  const [previews, setPreviews] = useState<Record<string, GitHubWriteEvent>>({});
  const [results, setResults] = useState<Record<string, GitHubWriteEvent>>({});

  async function previewIssue(risk: Risk) {
    const event = await api.githubPreviewRiskIssue(params.id, risk.id);
    setPreviews({ ...previews, [risk.id]: event });
    setResults({ ...results, [risk.id]: undefined as unknown as GitHubWriteEvent });
  }

  async function createIssue(risk: Risk) {
    try {
      const event = await api.githubCreateRiskIssue(params.id, risk.id, { approved: true, dry_run: false });
      setResults({ ...results, [risk.id]: event });
      await load();
    } catch (err) {
      setResults({
        ...results,
        [risk.id]: {
          id: "local",
          project_id: params.id,
          entity_type: "risk",
          entity_id: risk.id,
          action: "create_issue",
          dry_run: false,
          approved: true,
          payload_json: {},
          response_json: {},
          status: "failed",
          error_message: String((err as Error).message ?? err),
          created_at: new Date().toISOString()
        }
      });
    }
  }

  async function load() {
    setRisks(await api.risks(params.id));
  }

  useEffect(() => {
    load();
  }, []);

  async function generate() {
    await api.generateRisks(params.id);
    await load();
  }

  async function setStatus(risk: Risk, status: Risk["status"]) {
    await api.updateRisk(params.id, risk.id, { status });
    await load();
  }

  return (
    <div className="stack">
      <div className="spread">
        <div><div className="eyebrow">Risk Dashboard</div><h1>Risks</h1><p>Detected from memory, decisions, architecture, roadmap, and task state.</p></div>
        <button className="button row" onClick={generate}><ShieldAlert size={17} /> Generate risks</button>
      </div>
      <ProjectTabs projectId={params.id} />
      <section className="grid">
        {risks.map((risk) => (
          <article className="card stack" key={risk.id}>
            <div className="spread"><h2>{risk.title}</h2><span className={`priority ${risk.severity}`}>{risk.severity}</span></div>
            <div className="row"><span className="badge">{risk.category}</span><span className="badge">{risk.likelihood}</span><span className="badge">{risk.status}</span></div>
            <p><strong>Evidence:</strong> {risk.evidence}</p>
            <p><strong>Recommendation:</strong> {risk.recommendation}</p>
            <label className="field"><span>Status</span><select value={risk.status} onChange={(e) => setStatus(risk, e.target.value as Risk["status"])}>{["open", "watching", "mitigated", "accepted"].map((item) => <option key={item}>{item}</option>)}</select></label>
            {risk.github_issue_url && (
              <p>
                Issue: <a href={risk.github_issue_url}>#{risk.github_issue_number}</a> ({risk.github_sync_status})
              </p>
            )}
            <div className="row">
              <button className="button secondary" onClick={() => previewIssue(risk)}>Preview issue</button>
              {previews[risk.id] && (
                <button className="button" onClick={() => createIssue(risk)}>
                  Confirm + create issue
                </button>
              )}
            </div>
            {previews[risk.id] && (
              <details>
                <summary>Preview payload</summary>
                <pre className="output">{JSON.stringify(previews[risk.id].payload_json, null, 2)}</pre>
              </details>
            )}
            {results[risk.id] && (
              <p className={results[risk.id].status === "completed" ? "" : "warn"}>
                GitHub: {results[risk.id].status} {results[risk.id].error_message}
              </p>
            )}
          </article>
        ))}
      </section>
    </div>
  );
}
