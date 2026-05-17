"use client";

import { useEffect, useState } from "react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { ReconciliationReport, StatusSuggestion, api } from "@/lib/api";

export default function StatusSuggestionsPage({ params }: { params: { id: string } }) {
  const [suggestions, setSuggestions] = useState<StatusSuggestion[]>([]);
  const [report, setReport] = useState<ReconciliationReport | null>(null);
  const [includeResolved, setIncludeResolved] = useState(false);
  const [busy, setBusy] = useState(false);

  async function load(resolved = includeResolved) {
    setSuggestions(await api.statusSuggestions(params.id, resolved));
  }

  useEffect(() => {
    load(includeResolved);
  }, []);

  async function reconcile(auto: boolean) {
    setBusy(true);
    try {
      setReport(await api.githubReconcile(params.id, { auto_reconcile: auto }));
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function apply(suggestion: StatusSuggestion) {
    await api.applyStatusSuggestion(params.id, suggestion.id);
    await load();
  }

  async function dismiss(suggestion: StatusSuggestion) {
    await api.dismissStatusSuggestion(params.id, suggestion.id);
    await load();
  }

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">Lifecycle Loop</div>
        <h1>Status Suggestions</h1>
        <p>
          Reconciling pulls GitHub state read-only; suggestions stay unapplied until you confirm. Auto-apply
          requires <code>CTO_OS_ALLOW_AUTO_RECONCILE=1</code>.
        </p>
      </div>
      <ProjectTabs projectId={params.id} />
      <section className="panel row">
        <button className="button" onClick={() => reconcile(false)} disabled={busy}>
          Reconcile (suggestions only)
        </button>
        <button className="button secondary" onClick={() => reconcile(true)} disabled={busy}>
          Reconcile + auto-apply
        </button>
        <label className="field">
          <span>Include resolved</span>
          <input
            type="checkbox"
            checked={includeResolved}
            onChange={(event) => {
              setIncludeResolved(event.target.checked);
              load(event.target.checked);
            }}
          />
        </label>
      </section>
      {report && (
        <section className="panel">
          <p>
            Last reconcile: {report.events.length} events · {report.suggestions.length} new suggestions ·
            auto-applied {report.auto_applied}
            {report.degraded ? ` · degraded (${report.reason})` : ""}
          </p>
        </section>
      )}
      <section className="stack">
        {suggestions.length === 0 && <p>No open suggestions.</p>}
        {suggestions.map((suggestion) => (
          <article className="card stack" key={suggestion.id}>
            <div className="spread">
              <h2>
                {suggestion.entity_type} → {suggestion.suggested_status}
              </h2>
              <span className="badge">{suggestion.applied ? "applied" : suggestion.dismissed ? "dismissed" : "open"}</span>
            </div>
            <p>{suggestion.reason}</p>
            <details>
              <summary>Evidence</summary>
              <pre className="output">{JSON.stringify(suggestion.evidence_json, null, 2)}</pre>
            </details>
            {!suggestion.applied && !suggestion.dismissed && (
              <div className="row">
                <button className="button" onClick={() => apply(suggestion)}>
                  Apply
                </button>
                <button className="button secondary" onClick={() => dismiss(suggestion)}>
                  Dismiss
                </button>
              </div>
            )}
          </article>
        ))}
      </section>
    </div>
  );
}
